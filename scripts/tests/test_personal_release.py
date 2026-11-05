"""Rehearse packaging guards, offline SQLite backups and paired install/rollback on fixtures."""
import json
import fcntl
import os
from pathlib import Path
import plistlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/personal'))
import release
import maintenance


class PersonalReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='toccata-personal-rehearsal-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.app = self.root / 'Applications/Toccata Personal.app'
        self.data = self.root / 'Support/Toccata-Personal'
        self.check_stopped = mock.Mock()

    def make_app(self, path, version='1.0.0', bundle_id='cn.ericgao.toccata.personal', channel='personal-stable'):
        binary = path / 'Contents/MacOS'
        binary.mkdir(parents=True)
        for name in ['ToccataPersonal', 'toccata-core']:
            p = binary / name
            p.write_text('fixture: never executed\n' + version)
            p.chmod(0o755)
        info = dict(CFBundleIdentifier=bundle_id, CFBundleShortVersionString=version, CFBundleVersion='1',
                    CFBundleExecutable='ToccataPersonal', ToccataSourceCommit='a' * 40,
                    DTSDKName='macosx26.2', ToccataUpdateMode='manual', ToccataDistributionChannel=channel)
        (path / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))

    def make_data(self, path, value='old', wal=False):
        path.mkdir(parents=True)
        c = sqlite3.connect(path / 'tasks.sqlite')
        if wal:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('PRAGMA wal_autocheckpoint=0')
        c.execute('CREATE TABLE tasks(id TEXT PRIMARY KEY, details TEXT)')
        c.execute('INSERT INTO tasks VALUES (?,?)', ('id', value))
        c.commit()
        (path / 'daily-notes').mkdir()
        (path / 'daily-notes/2026-11-05.md').write_text('中文 $x^2$\n```py\n  x = 1\n```\n')
        (path / 'config.json').write_text(json.dumps({'db_path': str(path / 'toccata.db'),
            'socket_path': str(path / 'toccata.sock'), 'activity_window_secs': 6}))
        if wal:
            self.addCleanup(c.close)
            return c
        c.close()

    def make_package(self, version='1.1.0', candidate=False):
        package = self.root / ('package-' + version)
        identity = 'cn.ericgao.toccata.dev.fixture.candidate' if candidate else 'cn.ericgao.toccata.personal'
        channel = 'personal-candidate' if candidate else 'personal-stable'
        self.make_app(package / 'Toccata Personal.app', version, identity, channel)
        manifest = dict(schema_version=1, channel=channel, app='Toccata Personal.app',
            bundle_id=identity, version=version, build='1', sdk='26.2', commit='a' * 40,
            dirty=candidate, tag='personal-v' + version, tag_object='b' * 40,
            files=release.tree_hashes(package / 'Toccata Personal.app'),
            file_modes=release.tree_modes(package / 'Toccata Personal.app'))
        metadata = package / 'release.json'
        metadata.write_text(json.dumps(manifest))
        (package / 'release.json.sha256').write_text(release.sha256(metadata))
        return package

    def package_check(self, package):
        return release.verify_package(package, verify_signature=False)

    def details(self, folder):
        with sqlite3.connect(folder / 'tasks.sqlite') as c:
            return c.execute('SELECT details FROM tasks').fetchone()[0]

    def staged(self, value='new'):
        source = self.root / 'source-data'
        source_app = self.root / 'source.app'
        self.make_app(source_app)
        self.make_data(source, value)
        backup = self.root / 'source-backup'
        maintenance.snapshot(source_app, source, backup, stopped_check=self.check_stopped)
        return maintenance.stage_migration(backup, self.root / 'staged', self.data)

    def test_plan_commands_do_not_create_outputs_or_read_sources(self):
        missing = self.root / 'not-present'
        for args in [
            ['backup', '--app', str(missing), '--data', str(missing), '--output', str(self.root / 'backup')],
            ['install', '--package', str(missing), '--staged-data', str(missing), '--backup', str(self.root / 'backup')],
            ['rollback', '--backup', str(missing), '--recovery-backup', str(self.root / 'recovery')],
            ['recover', '--backup', str(missing)],
        ]:
            r = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/personal/maintenance.py'), *args], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)['mode'], 'plan-only')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_execution_without_shutdown_ack_is_rejected(self):
        r = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/personal/maintenance.py'), 'install',
            '--package', 'missing', '--staged-data', 'missing', '--backup', str(self.root / 'backup'), '--execute'],
            capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('ack-stopped', r.stderr)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_backup_contains_committed_wal_rows_and_exact_markdown(self):
        self.make_app(self.app)
        self.make_data(self.data, 'WAL committed row', wal=True)
        self.assertTrue((self.data / 'tasks.sqlite-wal').exists())
        backup = self.root / 'backup'
        maintenance.snapshot(self.app, self.data, backup, stopped_check=self.check_stopped)
        self.assertEqual(self.details(backup / 'data'), 'WAL committed row')
        self.assertFalse((backup / 'data/tasks.sqlite-wal').exists())
        self.assertEqual((backup / 'data/daily-notes/2026-11-05.md').read_bytes(), (self.data / 'daily-notes/2026-11-05.md').read_bytes())
        self.assertEqual(maintenance.verify_snapshot(backup)['sqlite_inventory']['tasks.sqlite'], {'tasks': 1})
        self.check_stopped.assert_called_once_with(self.app, self.data)

    def test_backup_is_never_overwritten_and_tampering_is_detected(self):
        self.make_app(self.app); self.make_data(self.data)
        backup = self.root / 'backup'
        maintenance.snapshot(self.app, self.data, backup, stopped_check=self.check_stopped)
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.snapshot(self.app, self.data, backup, stopped_check=self.check_stopped)
        (backup / 'data/daily-notes/2026-11-05.md').write_text('tampered')
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.verify_snapshot(backup)

    def test_symlink_and_overlapping_backup_paths_are_rejected(self):
        self.make_app(self.app); self.make_data(self.data)
        (self.data / 'outside.md').symlink_to(self.root / 'outside')
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.snapshot(self.app, self.data, self.root / 'backup', stopped_check=self.check_stopped)
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.snapshot(self.app, self.data, self.data / 'backup', stopped_check=self.check_stopped)
        self.assertFalse((self.data / 'backup').exists())

    def test_external_database_paths_require_separate_backup(self):
        self.make_app(self.app); self.make_data(self.data)
        (self.data / 'config.json').write_text(json.dumps({'db_path': str(self.root / 'external.db')}))
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.snapshot(self.app, self.data, self.root / 'backup', stopped_check=self.check_stopped)
        self.assertFalse((self.root / 'backup').exists())

    def test_migration_rewrites_paths_only_in_new_staging_copy(self):
        stage = self.staged()
        config = json.loads((stage / 'config.json').read_text())
        self.assertEqual(config['db_path'], str(self.data / 'toccata.db'))
        self.assertEqual(config['socket_path'], str(self.data / 'toccata.sock'))
        self.assertEqual(config['activity_window_secs'], 6)
        self.assertEqual(self.details(stage), 'new')
        original = json.loads((self.root / 'source-data/config.json').read_text())
        self.assertNotEqual(original['db_path'], config['db_path'])
        self.assertFalse(self.data.exists())

    def test_note_collision_never_publishes_partial_staging(self):
        self.make_app(self.app); self.make_data(self.data)
        backup = self.root / 'backup'
        maintenance.snapshot(self.app, self.data, backup, stopped_check=self.check_stopped)
        notes = self.root / 'trial-notes'; notes.mkdir()
        (notes / '2026-11-05.md').write_text('different trial note')
        output = self.root / 'staged'
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.stage_migration(backup, output, self.root / 'target-data', notes)
        self.assertFalse(output.exists())
        maintenance.verify_snapshot(backup)

    def test_install_and_rollback_restore_app_and_database_together(self):
        self.make_app(self.app); self.make_data(self.data, 'old')
        package = self.make_package(); stage = self.staged('new')
        backup = self.root / 'before-install'
        maintenance.install(package, stage, self.app, self.data, backup,
                            stopped_check=self.check_stopped, package_check=self.package_check)
        self.assertEqual(self.details(self.data), 'new')
        self.assertEqual(plistlib.loads((self.app / 'Contents/Info.plist').read_bytes())['CFBundleShortVersionString'], '1.1.0')
        (self.data / 'daily-notes/after-install.md').write_text('new work to preserve')
        recovery = self.root / 'before-rollback'
        maintenance.rollback(backup, self.app, self.data, recovery, stopped_check=self.check_stopped)
        self.assertEqual(self.details(self.data), 'old')
        self.assertEqual(plistlib.loads((self.app / 'Contents/Info.plist').read_bytes())['CFBundleShortVersionString'], '1.0.0')
        self.assertEqual((recovery / 'data/daily-notes/after-install.md').read_text(), 'new work to preserve')
        self.assertEqual(self.details(recovery / 'data'), 'new')

    def test_failed_second_swap_restores_original_pair(self):
        self.make_app(self.app); self.make_data(self.data, 'old')
        package = self.make_package(); stage = self.staged('new')
        real_replace = release.publish_new
        failed = False
        def replace(source, target):
            nonlocal failed
            if not failed and '.prepared-' in str(source) and Path(target) == self.data:
                failed = True
                raise OSError('simulated second-volume install failure')
            return real_replace(source, target)
        with mock.patch.object(release, 'publish_new', side_effect=replace):
            with self.assertRaises(OSError):
                maintenance.install(package, stage, self.app, self.data, self.root / 'backup',
                                    stopped_check=self.check_stopped, package_check=self.package_check)
        self.assertTrue(failed)
        self.assertEqual(self.details(self.data), 'old')
        self.assertEqual(plistlib.loads((self.app / 'Contents/Info.plist').read_bytes())['CFBundleShortVersionString'], '1.0.0')

    def test_first_install_rolls_back_to_absence_without_touching_source(self):
        package = self.make_package(); stage = self.staged()
        backup = self.root / 'before-install'
        maintenance.install(package, stage, self.app, self.data, backup,
                            stopped_check=self.check_stopped, package_check=self.package_check)
        maintenance.rollback(backup, self.app, self.data, self.root / 'newer-data', stopped_check=self.check_stopped)
        self.assertFalse(self.app.exists()); self.assertFalse(self.data.exists())
        self.assertTrue((self.root / 'source-data/tasks.sqlite').exists())

    def test_running_app_blocks_backup_before_any_output_is_created(self):
        def running(*_): raise maintenance.MaintenanceError('running')
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.snapshot(self.app, self.data, self.root / 'backup', stopped_check=running)
        self.assertFalse((self.root / 'backup').exists())

    def test_installer_rejects_candidate_and_foreign_existing_app(self):
        package = self.make_package(candidate=True); stage = self.staged()
        with self.assertRaises(release.ReleaseError):
            maintenance.install(package, stage, self.app, self.data, self.root / 'backup',
                                stopped_check=self.check_stopped, package_check=self.package_check)
        self.assertFalse(self.app.exists()); self.assertFalse(self.data.exists())
        package = self.make_package('1.2.0')
        self.make_app(self.app, bundle_id='com.toccata.studio')
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.install(package, stage, self.app, self.data, self.root / 'backup',
                                stopped_check=self.check_stopped, package_check=self.package_check)
        self.assertFalse((self.root / 'backup').exists())

    def test_package_tampering_and_manual_update_policy_are_checked(self):
        package = self.make_package()
        self.package_check(package)
        (package / 'Toccata Personal.app/Contents/MacOS/toccata-core').write_text('changed helper')
        with self.assertRaises(release.ReleaseError): self.package_check(package)

    def test_stable_packaging_requires_clean_fixed_tag_and_accepted_commit(self):
        settings = release.config()
        with mock.patch.object(release, 'git', return_value=' M changed'):
            with self.assertRaises(release.ReleaseError): release.release_provenance(settings, 'personal-v1.0.0')
        with self.assertRaises(release.ReleaseError): release.release_provenance(settings, 'v0.1.4')
        def git(*args):
            if args[0] == 'status': return ''
            if args == ('rev-parse', 'HEAD'): return 'a' * 40
            if args[-1] == 'refs/tags/personal-v1.0.0^{commit}': return 'a' * 40
            if args[-1] == 'refs/tags/personal-v1.0.0^{tag}': return 'b' * 40
            return settings['upstream_sha']
        with mock.patch.object(release, 'git', side_effect=git), mock.patch.object(release.subprocess, 'run') as run:
            self.assertEqual(release.release_provenance(settings, 'personal-v1.0.0'), ('a' * 40, 'b' * 40))
            self.assertIn('codex/personal', run.call_args.args[0])

    def test_rollback_rejects_foreign_app_identity_before_replacing_anything(self):
        self.make_app(self.app, bundle_id='com.toccata.studio'); self.make_data(self.data, 'original')
        backup = self.root / 'foreign-backup'
        maintenance.snapshot(self.app, self.data, backup, stopped_check=self.check_stopped)
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.rollback(backup, self.app, self.data, self.root / 'recovery', stopped_check=self.check_stopped)
        self.assertEqual(self.details(self.data), 'original')
        self.assertFalse((self.root / 'recovery').exists())

    def test_shutdown_inspection_rejects_running_apps_and_unknown_process_state(self):
        for result in [
            subprocess.CompletedProcess([], 0, stdout='123 ' + str(self.app / 'Contents/MacOS/ToccataPersonal') + '\n', stderr=''),
            subprocess.CompletedProcess([], 0, stdout='123 toccata-core\n', stderr=''),
            subprocess.CompletedProcess([], 1, stdout='', stderr='inspection denied'),
        ]:
            with mock.patch.object(maintenance.subprocess, 'run', return_value=result):
                with self.assertRaises(maintenance.MaintenanceError): maintenance.ensure_stopped(self.app, self.data)

    def test_active_data_lock_blocks_offline_operations(self):
        self.data.mkdir(parents=True)
        lock = self.data / 'toccata.lock'
        lock.write_bytes(b'')
        with lock.open('rb') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = subprocess.CompletedProcess([], 0, stdout='', stderr='')
            with mock.patch.object(maintenance.subprocess, 'run', return_value=result):
                with self.assertRaises(maintenance.MaintenanceError): maintenance.ensure_stopped(self.app, self.data)
            fcntl.flock(handle, fcntl.LOCK_UN)

    def test_backup_detects_permission_changes_and_preserves_runtime_named_attachments(self):
        self.make_app(self.app); self.make_data(self.data)
        attachment = self.data / 'daily-notes/toccata.lock'
        attachment.write_text('attachment, not the root runtime lock')
        backup = self.root / 'backup'
        maintenance.snapshot(self.app, self.data, backup, stopped_check=self.check_stopped)
        self.assertEqual((backup / 'data/daily-notes/toccata.lock').read_text(), attachment.read_text())
        (backup / 'app/Contents/MacOS/ToccataPersonal').chmod(0o644)
        with self.assertRaises(maintenance.MaintenanceError): maintenance.verify_snapshot(backup)

    def test_backup_refuses_source_changes_during_copy(self):
        self.make_app(self.app); self.make_data(self.data)
        real_copy = maintenance.copy_data
        def changed(source, destination):
            result = real_copy(source, destination)
            (source / 'daily-notes/2026-11-05.md').write_text('late external edit')
            return result
        with mock.patch.object(maintenance, 'copy_data', side_effect=changed):
            with self.assertRaises(maintenance.MaintenanceError):
                maintenance.snapshot(self.app, self.data, self.root / 'backup', stopped_check=self.check_stopped)
        self.assertFalse((self.root / 'backup').exists())

    def test_atomic_publication_never_replaces_an_existing_empty_directory(self):
        source, destination = self.root / 'source', self.root / 'destination'
        source.mkdir(); destination.mkdir()
        inode = destination.stat().st_ino
        with self.assertRaises(OSError): release.publish_new(source, destination)
        self.assertTrue(source.exists())
        self.assertEqual(destination.stat().st_ino, inode)

    def test_install_rechecks_copied_package_before_touching_live_targets(self):
        self.make_app(self.app); self.make_data(self.data)
        package, stage = self.make_package(), self.staged()
        original_check = self.package_check
        def changed(path):
            result = original_check(path)
            (path / 'Toccata Personal.app/Contents/MacOS/toccata-core').write_text('changed after validation')
            return result
        with self.assertRaises(release.ReleaseError):
            maintenance.install(package, stage, self.app, self.data, self.root / 'backup',
                stopped_check=self.check_stopped, package_check=changed)
        self.assertEqual(self.details(self.data), 'old')
        self.assertEqual(plistlib.loads((self.app / 'Contents/Info.plist').read_bytes())['CFBundleShortVersionString'], '1.0.0')

    def test_process_exit_mid_install_recovers_using_durable_journal(self):
        self.make_app(self.app); self.make_data(self.data, 'old')
        package, stage, backup = self.make_package(), self.staged(), self.root / 'backup'
        script = '''
import sys, os
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import maintenance, release
package, stage, app, data, backup = map(Path, sys.argv[2:])
real = release.publish_new
def interrupted(source, destination):
    real(source, destination)
    if '.prepared-' in str(source) and Path(destination) == app:
        os._exit(23)
release.publish_new = interrupted
maintenance.install(package, stage, app, data, backup, stopped_check=lambda *_:None,
    package_check=lambda p:release.verify_package(p, verify_signature=False))
'''
        result = subprocess.run([sys.executable, '-B', '-c', script, str(ROOT / 'scripts/personal'),
            *map(str, [package, stage, self.app, self.data, backup])])
        self.assertEqual(result.returncode, 23)
        self.assertTrue(maintenance.pending_path(self.data).exists())
        self.assertEqual(plistlib.loads((self.app / 'Contents/Info.plist').read_bytes())['CFBundleShortVersionString'], '1.1.0')
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.install(package, stage, self.app, self.data, self.root / 'another-backup',
                stopped_check=self.check_stopped, package_check=self.package_check)
        outcome = maintenance.recover_transaction(backup, self.app, self.data, stopped_check=self.check_stopped)
        self.assertEqual(outcome['state'], 'recovered')
        self.assertEqual(self.details(self.data), 'old')
        self.assertEqual(plistlib.loads((self.app / 'Contents/Info.plist').read_bytes())['CFBundleShortVersionString'], '1.0.0')
        self.assertFalse(maintenance.pending_path(self.data).exists())
        self.assertEqual(maintenance.recover_transaction(backup, self.app, self.data, stopped_check=self.check_stopped)['state'], 'recovered')

    def test_interrupted_rollback_can_restore_the_pre_rollback_pair(self):
        self.make_app(self.app); self.make_data(self.data)
        package, stage, backup = self.make_package(), self.staged(), self.root / 'before-install'
        maintenance.install(package, stage, self.app, self.data, backup,
            stopped_check=self.check_stopped, package_check=self.package_check)
        recovery = self.root / 'before-rollback'
        real = release.publish_new
        def interrupted(source, target):
            real(source, target)
            if '.prepared-' in str(source) and Path(target) == self.app:
                raise KeyboardInterrupt('simulated hard interruption')
        with mock.patch.object(release, 'publish_new', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                maintenance.rollback(backup, self.app, self.data, recovery, stopped_check=self.check_stopped)
        maintenance.recover_transaction(recovery, self.app, self.data, stopped_check=self.check_stopped)
        self.assertEqual(self.details(self.data), 'new')
        self.assertEqual(plistlib.loads((self.app / 'Contents/Info.plist').read_bytes())['CFBundleShortVersionString'], '1.1.0')

    def test_stale_never_started_journal_cannot_remove_a_newer_first_install(self):
        package, stage, backup = self.make_package(), self.staged(), self.root / 'abandoned'
        real_write = maintenance.write_record
        def interrupted(path, value, create=False):
            if path == maintenance.pending_path(self.data):
                raise KeyboardInterrupt('before ownership marker')
            return real_write(path, value, create=create)
        with mock.patch.object(maintenance, 'write_record', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                maintenance.install(package, stage, self.app, self.data, backup,
                    stopped_check=self.check_stopped, package_check=self.package_check)
        self.assertFalse(self.app.exists()); self.assertFalse(self.data.exists())
        maintenance.install(package, stage, self.app, self.data, self.root / 'completed',
            stopped_check=self.check_stopped, package_check=self.package_check)
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.recover_transaction(backup, self.app, self.data, stopped_check=self.check_stopped)
        self.assertEqual(self.details(self.data), 'new')

    def test_mutations_are_serialized(self):
        with maintenance.mutation_lock(self.app, self.data):
            with self.assertRaises(maintenance.MaintenanceError):
                with maintenance.mutation_lock(self.app, self.data):
                    self.fail('concurrent mutation should be rejected')

    def test_backup_retains_database_and_private_directory_permissions(self):
        self.make_app(self.app); self.make_data(self.data)
        (self.data / 'tasks.sqlite').chmod(0o600)
        (self.data / 'daily-notes').chmod(0o700)
        backup = self.root / 'backup'
        maintenance.snapshot(self.app, self.data, backup, stopped_check=self.check_stopped)
        self.assertEqual((backup / 'data/tasks.sqlite').stat().st_mode & 0o777, 0o600)
        self.assertEqual((backup / 'data/daily-notes').stat().st_mode & 0o777, 0o700)
        maintenance.verify_snapshot(backup)

    def test_last_shutdown_check_aborts_without_discarding_late_work(self):
        self.make_app(self.app); self.make_data(self.data)
        package, stage = self.make_package(), self.staged()
        checks = 0
        def stopped(*_):
            nonlocal checks
            checks += 1
            if checks == 4:
                (self.data / 'daily-notes/late.md').write_text('late work from restarted app')
                raise maintenance.MaintenanceError('app restarted')
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.install(package, stage, self.app, self.data, self.root / 'backup',
                stopped_check=stopped, package_check=self.package_check)
        self.assertEqual(self.details(self.data), 'old')
        self.assertEqual((self.data / 'daily-notes/late.md').read_text(), 'late work from restarted app')
        self.assertFalse(maintenance.pending_path(self.data).exists())

    def test_database_named_attachments_are_copied_as_original_bytes(self):
        self.make_app(self.app); self.make_data(self.data)
        for name in ['experiment.db', 'experiment.db-wal', 'experiment.db-shm']:
            (self.data / 'daily-notes' / name).write_bytes(b'non-SQLite experimental attachment')
        backup = self.root / 'backup'
        maintenance.snapshot(self.app, self.data, backup, stopped_check=self.check_stopped)
        for name in ['experiment.db', 'experiment.db-wal', 'experiment.db-shm']:
            self.assertEqual((backup / 'data/daily-notes' / name).read_bytes(), b'non-SQLite experimental attachment')

    def test_custom_local_database_name_is_not_silently_retargeted(self):
        self.make_app(self.app); self.make_data(self.data)
        (self.data / 'config.json').write_text(json.dumps({'db_path': str(self.data / 'custom-history.db')}))
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.snapshot(self.app, self.data, self.root / 'backup', stopped_check=self.check_stopped)
        self.assertFalse((self.root / 'backup').exists())

    def test_cleanup_error_after_commit_does_not_report_a_rollback(self):
        self.make_app(self.app); self.make_data(self.data)
        package, stage = self.make_package(), self.staged()
        real = Path.unlink
        failed = False
        def unlink(path, *args, **kwargs):
            nonlocal failed
            if path == maintenance.pending_path(self.data) and not failed:
                failed = True
                raise OSError('simulated cleanup failure')
            return real(path, *args, **kwargs)
        with mock.patch.object(Path, 'unlink', unlink):
            with self.assertRaisesRegex(maintenance.MaintenanceError, 'already committed'):
                maintenance.install(package, stage, self.app, self.data, self.root / 'backup',
                    stopped_check=self.check_stopped, package_check=self.package_check)
        self.assertEqual(self.details(self.data), 'new')
        self.assertEqual(maintenance.recover_transaction(self.root / 'backup', self.app, self.data,
            stopped_check=self.check_stopped)['state'], 'complete')

    def test_prepared_database_is_revalidated_before_live_swap(self):
        self.make_app(self.app); self.make_data(self.data)
        package, stage = self.make_package(), self.staged()
        original = maintenance.snapshot
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            (stage / 'tasks.sqlite').write_bytes(b'corrupted after the first staging check')
            return result
        with mock.patch.object(maintenance, 'snapshot', side_effect=changed):
            with self.assertRaises(sqlite3.Error):
                maintenance.install(package, stage, self.app, self.data, self.root / 'backup',
                    stopped_check=self.check_stopped, package_check=self.package_check)
        self.assertEqual(self.details(self.data), 'old')
        self.assertFalse(maintenance.pending_path(self.data).exists())


if __name__ == '__main__':
    unittest.main()
