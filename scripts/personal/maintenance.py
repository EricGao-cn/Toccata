#!/usr/bin/env python3
"""Offline personal install/backup/restore. Default is a plan; never launches apps."""
import argparse
from contextlib import contextmanager, closing
import errno
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import plistlib
import shutil
import sqlite3
import stat
import subprocess
import uuid

import release

ROOT = Path(__file__).resolve().parents[2]


class MaintenanceError(Exception):
    pass


def targets():
    home = Path.home()
    return home / 'Applications/Toccata Personal.app', home / 'Library/Application Support/Toccata-Personal'


def safe_path(path):
    path = Path(os.path.abspath(path))
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise MaintenanceError(f'Symlinked path rejected: {part}')
    return path


def disjoint(*paths):
    paths = [safe_path(p) for p in paths]
    for i, left in enumerate(paths):
        for right in paths[i + 1:]:
            if left == right or left in right.parents or right in left.parents:
                raise MaintenanceError(f'Paths overlap: {left} / {right}')


def ensure_stopped(app, data):
    """Observe only; never signal processes or stop someone else's app."""
    safe_path(app); safe_path(data)
    result = subprocess.run(['ps', '-axo', 'pid=,comm='], text=True, capture_output=True)
    if result.returncode:
        raise MaintenanceError('Cannot verify that the app is stopped; no changes made')
    prefix = str(Path(app)) + '/Contents/MacOS/'
    for line in result.stdout.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2 and (parts[1].startswith(prefix) or Path(parts[1]).name in
                              ['Toccata', 'ToccataPersonal', 'ToccataDevBinary', 'toccata-core']):
            raise MaintenanceError('Quit the app normally and wait for its helper to stop before continuing')
    lock = Path(data) / 'toccata.lock'
    safe_path(lock)
    if lock.exists():
        with lock.open('rb') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(handle, fcntl.LOCK_UN)
            except BlockingIOError as error:
                raise MaintenanceError('The collection helper still holds its data lock') from error


def sqlite_inventory(path):
    with closing(sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True, timeout=2)) as connection:
        connection.execute('PRAGMA query_only=ON')
        if connection.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise MaintenanceError(f'SQLite integrity check failed: {path}')
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        return {name: connection.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
                for (name,) in tables}


def application_database(relative):
    return len(relative.parts) == 1 and relative.name in [
        'tasks.sqlite', 'toccata.db', 'toccata.statistics-cache.sqlite']


def application_journal(relative):
    return relative.name.endswith(('-wal', '-shm')) and application_database(relative.with_name(relative.name[:-4]))


def runtime_entry(relative, path):
    if len(relative.parts) == 1 and path.name in ['toccata.lock', 'toccata.sock']:
        return True
    return relative.name.endswith('-shm') and application_journal(relative)


def source_state(root, data=False):
    state = {}
    if not root.exists():
        return state
    state['./'] = ['directory', root.stat().st_mode & 0o777]
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise MaintenanceError(f'Symlink in source: {relative}')
        if data and runtime_entry(relative, path):
            continue
        if path.is_dir():
            state[relative.as_posix() + '/'] = ['directory', path.stat().st_mode & 0o777]
        elif path.is_file():
            if data and application_journal(relative) and path.name.endswith('-wal') and path.stat().st_size == 0:
                continue
            state[relative.as_posix()] = [release.sha256(path), path.stat().st_mode & 0o777]
        else:
            raise MaintenanceError(f'Unsupported source entry: {relative}')
    return state


def copy_data(source, destination):
    """Snapshot SQLite with its committed WAL, copy Markdown/assets without transformation."""
    source, destination = safe_path(source), safe_path(destination)
    disjoint(source, destination)
    destination.mkdir(parents=True, exist_ok=False)
    if not source.exists():
        return {}
    if not source.is_dir():
        raise MaintenanceError('Data source must be a directory')
    inventories = {}
    config = source / 'config.json'
    if config.exists():
        settings = json.loads(config.read_text())
        if not isinstance(settings, dict):
            raise MaintenanceError('Data configuration must be a JSON object')
        for key in ['db_path', 'socket_path']:
            if settings.get(key) is not None:
                if not isinstance(settings[key], str) or not settings[key]:
                    raise MaintenanceError(f'Invalid {key} in source configuration')
                configured = Path(settings[key])
                if not configured.is_absolute():
                    raise MaintenanceError(f'Relative {key} needs manual review before backup')
                if configured.parent != source:
                    raise MaintenanceError(f'External {key} needs a separately verified backup')
                expected_name = 'toccata.db' if key == 'db_path' else 'toccata.sock'
                if configured.name != expected_name:
                    raise MaintenanceError(f'Custom {key} filename needs an explicit migration mapping before backup')
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if path.is_symlink():
            raise MaintenanceError(f'Data symlink rejected: {relative}')
        mode = path.stat().st_mode
        if len(relative.parts) == 1 and path.name in ['toccata.lock', 'toccata.sock']:
            continue
        if path.is_dir():
            (destination / relative).mkdir(exist_ok=True)
            continue
        if not stat.S_ISREG(mode):
            raise MaintenanceError(f'Unsupported data entry: {relative}')
        if application_journal(relative):
            if not path.with_name(path.name[:-4]).is_file():
                raise MaintenanceError(f'Orphan SQLite journal requires recovery first: {relative}')
            continue
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        if application_database(relative):
            # A read-only source connection includes committed WAL frames. Merely
            # copying a live main database file can omit recent tasks.
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)) as original:
                with closing(sqlite3.connect(output)) as copied:
                    original.backup(copied)
                    copied.execute('PRAGMA journal_mode=DELETE')
            inventories[relative.as_posix()] = sqlite_inventory(output)
            output.chmod(stat.S_IMODE(path.stat().st_mode))
        else:
            shutil.copy2(path, output)
    for directory in sorted([p for p in source.rglob('*') if p.is_dir()], key=lambda p: len(p.parts), reverse=True):
        shutil.copystat(directory, destination / directory.relative_to(source))
    destination.chmod(stat.S_IMODE(source.stat().st_mode))
    return inventories


def write_manifest(folder, manifest):
    metadata = folder / 'backup.json'
    metadata.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    (folder / 'backup.json.sha256').write_text(release.sha256(metadata) + '\n')


def snapshot(app, data, output, stopped_check=ensure_stopped):
    app, data, output = safe_path(app), safe_path(data), safe_path(output)
    disjoint(app, data, output)
    if output.exists():
        raise MaintenanceError('Backup output already exists; backups are never overwritten')
    stopped_check(app, data)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.parent / ('.backup-' + uuid.uuid4().hex)
    staging.mkdir(mode=0o700)
    before_app, before_data = source_state(app), source_state(data, data=True)
    manifest = {'schema_version': 2, 'created_at': datetime.now(timezone.utc).isoformat(),
                'source_app': str(app), 'source_data': str(data),
                'app_present': app.exists(), 'data_present': data.exists(),
                'source_states': {'app': before_app, 'data': before_data}}
    if app.exists():
        release.tree_hashes(app)
        shutil.copytree(app, staging / 'app')
    if data.exists():
        manifest['sqlite_inventory'] = copy_data(data, staging / 'data')
    else:
        manifest['sqlite_inventory'] = {}
    if before_app != source_state(app) or before_data != source_state(data, data=True):
        raise MaintenanceError('Source changed during backup; quit all writers and create a fresh snapshot')
    manifest['files'] = release.tree_hashes(staging)
    manifest['modes'] = release.tree_modes(staging)
    write_manifest(staging, manifest)
    verify_snapshot(staging)
    sync_tree(staging)
    release.publish_new(staging, output)
    sync_directory(output.parent)
    return manifest


def verify_snapshot(folder):
    folder = safe_path(folder)
    metadata = folder / 'backup.json'
    expected = folder / 'backup.json.sha256'
    if metadata.is_symlink() or expected.is_symlink() or release.sha256(metadata) != expected.read_text().strip():
        raise MaintenanceError('Backup manifest checksum mismatch')
    manifest = json.loads(metadata.read_text())
    if manifest.get('schema_version') != 2:
        raise MaintenanceError('Unsupported backup schema')
    actual = release.tree_hashes(folder)
    actual.pop('backup.json', None); actual.pop('backup.json.sha256', None)
    if actual != manifest.get('files'):
        raise MaintenanceError('Backup payload checksum mismatch')
    modes = release.tree_modes(folder)
    modes.pop('backup.json', None); modes.pop('backup.json.sha256', None)
    if modes != manifest.get('modes'):
        raise MaintenanceError('Backup file permissions differ from its manifest')
    for name, inventory in manifest.get('sqlite_inventory', {}).items():
        if Path(name).is_absolute() or '..' in Path(name).parts or 'data/' + name not in actual:
            raise MaintenanceError('Invalid database inventory path')
        if sqlite_inventory(folder / 'data' / name) != inventory:
            raise MaintenanceError('Backup SQLite inventory mismatch')
    return manifest


def stage_migration(backup, output, target_data, extra_notes=None):
    backup, output = safe_path(backup), safe_path(output)
    target_data = safe_path(target_data)
    disjoint(backup, output, target_data)
    manifest = verify_snapshot(backup)
    if not manifest['data_present']:
        raise MaintenanceError('Source backup has no data')
    if output.exists():
        raise MaintenanceError('Staging output exists; refusing to overwrite')
    final_output = output
    output.parent.mkdir(parents=True, exist_ok=True)
    private_staging = output.parent / ('.migration-' + uuid.uuid4().hex)
    private_staging.mkdir(mode=0o700)
    output = private_staging / 'data'
    shutil.copytree(backup / 'data', output)
    output.chmod(0o700)
    settings_path = output / 'config.json'
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    settings['db_path'] = str(target_data / 'toccata.db')
    settings['socket_path'] = str(target_data / 'toccata.sock')
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + '\n')
    if extra_notes:
        source = safe_path(extra_notes)
        disjoint(source, output, backup, target_data)
        if not source.is_dir():
            raise MaintenanceError('Extra notes source must be a directory')
        for path in source.rglob('*'):
            if path.is_symlink() or (not path.is_file() and not path.is_dir()):
                raise MaintenanceError('Extra note folder contains an unsupported entry')
            target = output / 'daily-notes' / path.relative_to(source)
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                if target.exists() and release.sha256(target) != release.sha256(path):
                    raise MaintenanceError('Daily note name collision; resolve in staging before installing')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
    for name, inventory in manifest.get('sqlite_inventory', {}).items():
        if sqlite_inventory(output / name) != inventory:
            raise MaintenanceError('Migration staging changed database contents')
    sync_tree(output)
    release.publish_new(output, final_output)
    sync_directory(final_output.parent)
    return final_output


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        try:
            os.fsync(descriptor)
        except OSError as error:
            if error.errno not in [errno.EINVAL, errno.ENOTSUP]:
                raise
    finally:
        os.close(descriptor)


def sync_tree(path):
    for item in path.rglob('*'):
        if item.is_file():
            with item.open('rb') as handle:
                os.fsync(handle.fileno())
    for directory in sorted([p for p in path.rglob('*') if p.is_dir()], key=lambda p: len(p.parts), reverse=True):
        sync_directory(directory)
    sync_directory(path)


def pending_path(data):
    return data.parent / ('.' + data.name + '.maintenance.pending.json')


@contextmanager
def mutation_lock(app, data, allow_pending=False):
    safe_path(app); safe_path(data)
    data.parent.mkdir(parents=True, exist_ok=True)
    path = safe_path(data.parent / ('.' + data.name + '.maintenance.lock'))
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise MaintenanceError('Another maintenance operation is already running') from error
        if not allow_pending and pending_path(data).exists():
            raise MaintenanceError('An interrupted transaction is pending; use recover before another install or rollback')
        yield
    finally:
        os.close(descriptor)


def write_record(path, value, create=False):
    safe_path(path)
    temporary = path.parent / ('.record-' + uuid.uuid4().hex)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    if create:
        release.publish_new(temporary, path)
    else:
        os.replace(temporary, path)
    sync_directory(path.parent)


def journal_path(backup):
    return backup.parent / (backup.name + '.transaction.json')


def _recover_transaction(backup, app, data):
    manifest = verify_snapshot(backup)
    if manifest['source_app'] != str(app) or manifest['source_data'] != str(data):
        raise MaintenanceError('Recovery snapshot belongs to different destinations')
    record = journal_path(backup)
    safe_path(record)
    transaction = json.loads(record.read_text())
    token = transaction.get('token', '')
    if (transaction.get('schema_version') != 1 or not isinstance(token, str)
            or len(token) != 32 or any(c not in '0123456789abcdef' for c in token)
            or transaction.get('app') != str(app) or transaction.get('data') != str(data)
            or transaction.get('backup') != str(backup)
            or transaction.get('backup_sha256') != release.sha256(backup / 'backup.json')
            or transaction.get('state') not in ['prepared', 'complete', 'recovered']
            or not isinstance(transaction.get('mutation_started'), bool)):
        raise MaintenanceError('Invalid or mismatched transaction journal')
    pointer = pending_path(data)
    safe_path(pointer)
    if pointer.exists():
        pending = json.loads(pointer.read_text())
        if pending != {'journal': str(record), 'backup': str(backup), 'token': token}:
            raise MaintenanceError('A different transaction needs recovery first')
    if transaction['state'] != 'prepared':
        if pointer.exists():
            pointer.unlink(); sync_directory(pointer.parent)
        return {'state': transaction['state'], 'preserved_paths': []}
    pairs = transaction.get('pairs')
    if not isinstance(pairs, list) or len(pairs) != 2:
        raise MaintenanceError('Invalid recovery pairs')
    if not pointer.exists():
        # No live rename is allowed before the durable ownership marker exists.
        # An old, never-started journal must not roll back a newer installation.
        for index, target in enumerate([app, data]):
            key = 'app' if index == 0 else 'data'
            if (target.exists() != manifest[key + '_present']
                    or source_state(target, data=index == 1) != manifest['source_states'][key]):
                raise MaintenanceError('Prepared journal has no ownership marker and destinations changed; automatic recovery refused')
        transaction['state'] = 'recovered'
        write_record(record, transaction)
        return {'state': 'recovered', 'preserved_paths': []}
    if not transaction['mutation_started']:
        # The last shutdown check can fail after a program starts again. We have
        # not renamed any live path, so preserve that program's newer work.
        transaction['state'] = 'recovered'
        write_record(record, transaction)
        pointer.unlink(); sync_directory(pointer.parent)
        return {'state': 'recovered', 'preserved_paths': []}
    # Validate every original tree before changing either target.
    for index, target in enumerate([app, data]):
        original = pairs[index]
        previous = safe_path(target.parent / ('.' + target.name + '.previous-' + token))
        expected_present = manifest['app_present' if index == 0 else 'data_present']
        if original.get('original_present') != expected_present:
            raise MaintenanceError('Recovery presence state differs from snapshot')
        if original.get('original_state') != manifest['source_states']['app' if index == 0 else 'data']:
            raise MaintenanceError('Recovery original state differs from snapshot')
        if expected_present:
            candidate = previous if previous.exists() else target
            if not candidate.exists() or source_state(candidate, data=index == 1) != original.get('original_state'):
                raise MaintenanceError('Original recovery tree is missing or changed; preserve files and restore the verified backup explicitly')
    preserved = []
    for index, target in reversed(list(enumerate([app, data]))):
        previous = target.parent / ('.' + target.name + '.previous-' + token)
        needs_restore = previous.exists()
        if needs_restore or not pairs[index]['original_present']:
            if target.exists():
                archive = target.parent / ('.' + target.name + '.interrupted-' + uuid.uuid4().hex)
                release.publish_new(target, archive)
                preserved.append(str(archive))
                sync_directory(target.parent)
            if needs_restore:
                release.publish_new(previous, target)
                sync_directory(target.parent)
    transaction['state'] = 'recovered'
    write_record(record, transaction)
    if pointer.exists():
        pointer.unlink(); sync_directory(pointer.parent)
    return {'state': 'recovered', 'preserved_paths': preserved}


def recover_transaction(backup, app, data, stopped_check=ensure_stopped):
    backup, app, data = safe_path(backup), safe_path(app), safe_path(data)
    disjoint(backup, app, data)
    stopped_check(app, data)
    with mutation_lock(app, data, allow_pending=True):
        stopped_check(app, data)
        return _recover_transaction(backup, app, data)


def swap_pair(new_app, new_data, app, data, backup, app_validator=None, data_validator=None, pre_mutation_check=None):
    """Offline recoverable transaction; the journal survives process interruption."""
    app, data = safe_path(app), safe_path(data)
    disjoint(app, data)
    token = uuid.uuid4().hex
    pairs = []
    for index, (source, target) in enumerate([(new_app, app), (new_data, data)]):
        target.parent.mkdir(parents=True, exist_ok=True)
        private_staging = target.parent / ('.' + target.name + '.prepared-' + token)
        prepared = private_staging / 'payload'
        previous = target.parent / ('.' + target.name + '.previous-' + token)
        if source:
            source = safe_path(source)
            disjoint(source, target)
            expected = source_state(source, data=index == 1)
            private_staging.mkdir(mode=0o700)
            shutil.copytree(source, prepared)
            if expected != source_state(source, data=index == 1) or expected != source_state(prepared, data=index == 1):
                raise MaintenanceError('Payload changed while preparing the installation')
            if index == 0 and app_validator:
                app_validator(prepared)
            if index == 1 and data_validator:
                data_validator(prepared)
            sync_tree(prepared)
        pairs.append({'target': str(target), 'prepared': str(prepared) if source else None,
                      'previous': str(previous), 'original_present': target.exists(),
                      'original_state': source_state(target, data=index == 1),
                      'prepared_state': source_state(prepared, data=index == 1) if source else {}})
    transaction = {'schema_version': 1, 'token': token, 'state': 'prepared', 'mutation_started': False,
                   'app': str(app), 'data': str(data), 'backup': str(backup),
                   'backup_sha256': release.sha256(backup / 'backup.json'), 'pairs': pairs}
    snapshot_manifest = verify_snapshot(backup)
    for index, pair in enumerate(pairs):
        key = 'app' if index == 0 else 'data'
        if (pair['original_present'] != snapshot_manifest[key + '_present']
                or pair['original_state'] != snapshot_manifest['source_states'][key]):
            raise MaintenanceError('Destination changed since the pre-install snapshot')
    record = journal_path(backup)
    write_record(record, transaction, create=True)
    pointer = pending_path(data)
    write_record(pointer, {'journal': str(record), 'backup': str(backup), 'token': token}, create=True)
    try:
        if pre_mutation_check:
            pre_mutation_check()
        transaction['mutation_started'] = True
        write_record(record, transaction)
        for pair in pairs:
            target, previous = Path(pair['target']), Path(pair['previous'])
            prepared = Path(pair['prepared']) if pair['prepared'] else None
            if pair['original_present']:
                release.publish_new(target, previous)
                sync_directory(target.parent)
            if prepared:
                release.publish_new(prepared, target)
                sync_directory(target.parent)
        for index, pair in enumerate(pairs):
            if source_state(Path(pair['target']), data=index == 1) != pair['prepared_state']:
                raise MaintenanceError('Installed payload changed before transaction completion')
        transaction['state'] = 'complete'
        write_record(record, transaction)
        pointer.unlink(); sync_directory(pointer.parent)
    except Exception as failure:
        try:
            outcome = _recover_transaction(backup, app, data)
        except Exception as recovery_failure:
            raise MaintenanceError(f'Automatic recovery could not finish. Preserve all files and use recover with {backup}; journal: {record}') from recovery_failure
        if outcome['state'] == 'complete':
            raise MaintenanceError(f'Transaction already committed; cleanup was interrupted. Inspect journal: {record}') from failure
        raise
    return [pair['previous'] for pair in pairs if Path(pair['previous']).exists()]


def validate_staged_data(staged_data, data):
    staged_data = safe_path(staged_data)
    if not staged_data.is_dir():
        raise MaintenanceError('Prepare and review a staged data copy first')
    settings = json.loads((staged_data / 'config.json').read_text())
    if not isinstance(settings, dict):
        raise MaintenanceError('Staged configuration must be a JSON object')
    if settings.get('db_path') != str(data / 'toccata.db') or settings.get('socket_path') != str(data / 'toccata.sock'):
        raise MaintenanceError('Staged data still points to another data directory')
    release.tree_hashes(staged_data)
    for path in staged_data.rglob('*'):
        relative = path.relative_to(staged_data)
        if application_journal(relative):
            raise MaintenanceError('Staged data must contain standalone SQLite snapshots, not WAL/SHM files')
        if application_database(relative):
            sqlite_inventory(path)


def install(package, staged_data, app, data, backup, stopped_check=ensure_stopped, package_check=release.verify_package):
    app, data = safe_path(app), safe_path(data)
    package = safe_path(package)
    disjoint(package, staged_data, app, data, backup)
    manifest = package_check(package)
    source_app = package / manifest['app']
    staged_data = safe_path(staged_data)
    validate_staged_data(staged_data, data)
    stopped_check(app, data)
    with mutation_lock(app, data):
        stopped_check(app, data)
        if app.exists():
            info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
            if info.get('CFBundleIdentifier') != 'cn.ericgao.toccata.personal':
                raise MaintenanceError('Refusing to replace a non-personal app')
        snapshot(app, data, backup, stopped_check=stopped_check)
        return swap_pair(source_app, staged_data, app, data, safe_path(backup),
                         app_validator=lambda prepared: release.verify_payload(prepared, manifest, verify_signature=False),
                         data_validator=lambda prepared: validate_staged_data(prepared, data),
                         pre_mutation_check=lambda: stopped_check(app, data))


def rollback(backup, app, data, recovery_backup, stopped_check=ensure_stopped):
    manifest = verify_snapshot(backup)
    app, data = safe_path(app), safe_path(data)
    disjoint(backup, recovery_backup, app, data)
    if manifest.get('source_app') != str(app) or manifest.get('source_data') != str(data):
        raise MaintenanceError('Rollback snapshot belongs to different destinations')
    if manifest['app_present']:
        info = plistlib.loads((Path(backup) / 'app/Contents/Info.plist').read_bytes())
        if info.get('CFBundleIdentifier') != 'cn.ericgao.toccata.personal':
            raise MaintenanceError('Rollback app must have the personal stable identity')
    stopped_check(app, data)
    # Preserve newer notes and records before restoring the old app/data pair.
    with mutation_lock(app, data):
        stopped_check(app, data)
        snapshot(app, data, recovery_backup, stopped_check=stopped_check)
        return swap_pair(Path(backup) / 'app' if manifest['app_present'] else None,
                         Path(backup) / 'data' if manifest['data_present'] else None, app, data, safe_path(recovery_backup),
                         pre_mutation_check=lambda: stopped_check(app, data))


def require_execution(args):
    if not args.execute:
        print(json.dumps({'action': args.command, 'mode': 'plan-only', 'arguments': {k: str(v) for k, v in vars(args).items() if k != 'execute'}}, ensure_ascii=False, indent=2))
        return False
    if not getattr(args, 'ack_stopped', False):
        raise MaintenanceError('Execution requires --ack-stopped after normal app/helper shutdown')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('plan')
    backup = commands.add_parser('backup')
    backup.add_argument('--app', type=Path, required=True); backup.add_argument('--data', type=Path, required=True)
    backup.add_argument('--output', type=Path, required=True)
    verify = commands.add_parser('verify-backup'); verify.add_argument('backup', type=Path)
    stage = commands.add_parser('stage-migration')
    stage.add_argument('--backup', type=Path, required=True); stage.add_argument('--output', type=Path, required=True)
    stage.add_argument('--extra-notes', type=Path)
    stage.add_argument('--target-data', type=Path, default=targets()[1])
    install_parser = commands.add_parser('install')
    install_parser.add_argument('--package', type=Path, required=True); install_parser.add_argument('--staged-data', type=Path, required=True)
    install_parser.add_argument('--backup', type=Path, required=True)
    restore = commands.add_parser('rollback')
    restore.add_argument('--backup', type=Path, required=True); restore.add_argument('--recovery-backup', type=Path, required=True)
    recover = commands.add_parser('recover')
    recover.add_argument('--backup', type=Path, required=True)
    for command in [backup, stage, install_parser, restore, recover]:
        command.add_argument('--execute', action='store_true')
        command.add_argument('--ack-stopped', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'plan':
            app, data = targets()
            print(json.dumps({'personal_app': str(app), 'personal_data': str(data),
                'sequence': ['fixed release package', 'normal shutdown', 'verified offline backup',
                             'staged data copy and validation', 'paired app/data install', 'manual acceptance',
                             'paired rollback with preservation of newer data if needed'],
                'launches_apps': False, 'changes_login_items_or_permissions': False}, ensure_ascii=False, indent=2))
        elif args.command == 'verify-backup':
            manifest = verify_snapshot(args.backup)
            print(json.dumps({'valid': True, 'sqlite_inventory': manifest['sqlite_inventory']}, ensure_ascii=False, indent=2))
        elif require_execution(args):
            if args.command == 'backup':
                snapshot(args.app, args.data, args.output)
            elif args.command == 'stage-migration':
                stage_migration(args.backup, args.output, args.target_data, args.extra_notes)
            elif args.command == 'install':
                app, data = targets()
                print(json.dumps({'preserved_paths': install(args.package, args.staged_data, app, data, args.backup)}, indent=2))
            elif args.command == 'rollback':
                app, data = targets()
                print(json.dumps({'preserved_paths': rollback(args.backup, app, data, args.recovery_backup)}, indent=2))
            elif args.command == 'recover':
                app, data = targets()
                print(json.dumps(recover_transaction(args.backup, app, data), indent=2))
    except (MaintenanceError, release.ReleaseError, OSError, ValueError, sqlite3.Error, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Personal maintenance: {error}\n')


if __name__ == '__main__':
    main()
