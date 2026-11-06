#!/usr/bin/env python3
"""Prepare a personal GitHub release locally; remote draft creation is opt-in."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import uuid
import zipfile

import maintenance
import release
import disk_image

REPOSITORY = 'EricGao-cn/Toccata'
VERSION = r'(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)'


def provenance(manifest):
    tag = manifest['tag']
    if not re.fullmatch('personal-v' + VERSION, tag):
        raise release.ReleaseError('Only canonical personal stable tags can be uploaded')
    if (release.git('rev-parse', '--verify', f'refs/tags/{tag}^{{tag}}') != manifest['tag_object']
            or release.git('rev-parse', '--verify', f'refs/tags/{tag}^{{commit}}') != manifest['commit']):
        raise release.ReleaseError('Fixed local tag differs from the package provenance')
    subprocess.run(['git', '-C', str(release.ROOT), 'merge-base', '--is-ancestor', manifest['commit'], 'codex/personal'], check=True)


def unpack_verified(archive, destination, tag):
    # Check paths/types/expanded size before passing a downloaded or edited ZIP to ditto.
    with zipfile.ZipFile(archive) as zipped:
        names = set()
        total = 0
        for entry in zipped.infolist():
            parts = Path(entry.filename).parts
            mode = entry.external_attr >> 16
            if (not parts or parts[0] != tag or Path(entry.filename).is_absolute()
                    or '..' in parts or '\\' in entry.filename or entry.filename in names
                    or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in [0, stat.S_IFREG, stat.S_IFDIR])):
                raise release.ReleaseError('Unsafe release ZIP entry')
            names.add(entry.filename)
            total += entry.file_size
            if total > 2_147_483_648:
                raise release.ReleaseError('Expanded release ZIP is too large')
    subprocess.run(['/usr/bin/ditto', '-x', '-k', str(archive), str(destination)], check=True)
    payload = destination / tag
    manifest = release.verify_package(payload)
    if {path.name for path in payload.iterdir()} != {manifest['app'], 'release.json', 'release.json.sha256'}:
        raise release.ReleaseError('Release ZIP contains unexpected neighboring files')
    return manifest


def prepare(package, notes, output, archive_format='dmg'):
    if archive_format not in ['zip', 'dmg']:
        raise release.ReleaseError('Choose zip or dmg as the release container')
    package, notes, output = map(maintenance.safe_path, [package, notes, output])
    maintenance.disjoint(package, notes, output)
    if output.exists():
        raise release.ReleaseError('Release output already exists; refusing to overwrite')
    manifest = release.verify_package(package)
    provenance(manifest)
    architecture = manifest.get('architecture')
    if architecture not in ['arm64', 'x86_64', 'universal']:
        raise release.ReleaseError('Unsupported package architecture')
    if notes.name != manifest['tag'] + '.md' or not notes.is_file() or not notes.read_text().strip():
        raise release.ReleaseError('Provide nonempty notes named <personal-tag>.md')
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.parent / ('.github-release-' + uuid.uuid4().hex)
    staging.mkdir(mode=0o700)
    with tempfile.TemporaryDirectory(prefix='toccata-release-assets-') as temporary:
        scratch = Path(temporary).resolve()
        payload = scratch / manifest['tag']
        payload.mkdir()
        # Explicit allowlist: no development state, databases or neighboring files.
        shutil.copytree(package / manifest['app'], payload / manifest['app'])
        for name in ['release.json', 'release.json.sha256']:
            shutil.copy2(package / name, payload / name)
            shutil.copy2(package / name, staging / name)
        if release.verify_package(payload) != manifest or release.verify_package(package) != manifest:
            raise release.ReleaseError('Package changed while preparing the release')
        filename = f'Toccata-Personal-{manifest["version"]}-{architecture}.{archive_format}'
        archive = staging / filename
        if archive_format == 'dmg':
            if disk_image.build_image(payload, archive) != manifest:
                raise release.ReleaseError('DMG content differs from the verified package')
        else:
            subprocess.run(['/usr/bin/ditto', '--norsrc', '--noextattr', '--noacl', '-c', '-k', '--keepParent',
                            str(payload), str(archive)], check=True)
            if unpack_verified(archive, scratch / 'unpacked', manifest['tag']) != manifest:
                raise release.ReleaseError('ZIP content differs from the verified package')
        (staging / (filename + '.sha256')).write_text(release.sha256(archive) + '  ' + filename + '\n')
        (staging / 'RELEASE.md').write_text(notes.read_text())
        metadata = {'schema_version': 1, 'repository': REPOSITORY, 'tag': manifest['tag'],
                    'version': manifest['version'], 'commit': manifest['commit'], 'tag_object': manifest['tag_object'],
                    'archive': filename, 'title': 'Toccata Personal ' + manifest['version'],
                    'files': release.tree_hashes(staging)}
        (staging / 'github-release.json').write_text(json.dumps(metadata, indent=2) + '\n')
    maintenance.sync_tree(staging)
    release.publish_new(staging, output)
    maintenance.sync_directory(output.parent)
    return metadata


def verify_bundle(bundle):
    bundle = maintenance.safe_path(bundle)
    metadata = json.loads((bundle / 'github-release.json').read_text())
    if metadata.get('schema_version') != 1 or metadata.get('repository') != REPOSITORY:
        raise release.ReleaseError('Unexpected publication repository or bundle schema')
    tag, version = metadata.get('tag', ''), metadata.get('version', '')
    if not re.fullmatch(VERSION, version) or tag != 'personal-v' + version:
        raise release.ReleaseError('Unexpected personal release tag')
    archive = metadata.get('archive', '')
    if not re.fullmatch(r'Toccata-Personal-' + re.escape(version) + r'-(?:arm64|x86_64|universal)\.(?:zip|dmg)', archive):
        raise release.ReleaseError('Unexpected release archive name')
    files = release.tree_hashes(bundle)
    files.pop('github-release.json', None)
    if set(files) != {archive, archive + '.sha256', 'release.json', 'release.json.sha256', 'RELEASE.md'} or files != metadata.get('files'):
        raise release.ReleaseError('Publication assets changed or contain unexpected files')
    if (bundle / (archive + '.sha256')).read_text() != release.sha256(bundle / archive) + '  ' + archive + '\n':
        raise release.ReleaseError('Archive checksum mismatch')
    with tempfile.TemporaryDirectory(prefix='toccata-release-verify-') as temporary:
        manifest = (disk_image.verify_image(bundle / archive) if archive.endswith('.dmg')
                    else unpack_verified(bundle / archive, Path(temporary).resolve(), tag))
    if (manifest['tag'] != tag or manifest['version'] != version or manifest['commit'] != metadata.get('commit')
            or manifest['tag_object'] != metadata.get('tag_object')
            or manifest.get('architecture') not in ['arm64', 'x86_64', 'universal']
            or archive != f'Toccata-Personal-{version}-{manifest.get("architecture")}.{Path(archive).suffix[1:]}'
            or json.loads((bundle / 'release.json').read_text()) != manifest
            or release.sha256(bundle / 'release.json') != (bundle / 'release.json.sha256').read_text().strip()):
        raise release.ReleaseError('Publication metadata differs from the verified archive')
    after = release.tree_hashes(bundle)
    after.pop('github-release.json', None)
    if after != files or json.loads((bundle / 'github-release.json').read_text()) != metadata:
        raise release.ReleaseError('Publication assets changed during archive verification')
    provenance(manifest)
    return metadata


def draft_command(bundle, metadata):
    assets = [metadata['archive'], metadata['archive'] + '.sha256', 'release.json', 'release.json.sha256']
    return ['gh', 'release', 'create', metadata['tag'], *[str(bundle / name) for name in assets],
            '--repo', 'github.com/' + REPOSITORY, '--draft', '--verify-tag', '--title', 'Toccata Personal ' + metadata['version'],
            '--notes-file', str(bundle / 'RELEASE.md')]


def github(endpoint):
    return json.loads(subprocess.check_output(['gh', 'api', '--hostname', 'github.com', endpoint], text=True, timeout=30))


def remote_releases():
    found = []
    for page in range(1, 11):
        values = github(f'repos/{REPOSITORY}/releases?per_page=100&page={page}')
        if (not isinstance(values, list) or len(values) > 100
                or any(not isinstance(item, dict) or not isinstance(item.get('tag_name'), str) for item in values)):
            raise release.ReleaseError('Invalid GitHub releases response')
        found.extend(values)
        if len(values) < 100:
            return found
    raise release.ReleaseError('Release listing was incomplete; no changes made')


def create_draft(bundle, *, expected_metadata=None):
    bundle = maintenance.safe_path(bundle)
    metadata = verify_bundle(bundle)
    if expected_metadata is not None and metadata != expected_metadata:
        raise release.ReleaseError('Publication assets differ from the expected verified build')
    # Keep the bytes approved by local validation separate from editable source
    # files for the entire network/upload operation. Never upload the live bundle.
    with tempfile.TemporaryDirectory(prefix='toccata-upload-') as temporary:
        snapshot = Path(temporary).resolve() / 'bundle'
        shutil.copytree(bundle, snapshot)
        if verify_bundle(snapshot) != metadata:
            raise release.ReleaseError('Publication assets changed while preparing the upload')
        return upload_draft(snapshot, metadata)


def check_remote_tag(metadata):
    reference = github(f'repos/{REPOSITORY}/git/ref/tags/{metadata["tag"]}')
    target = reference.get('object') if isinstance(reference, dict) else None
    if (not isinstance(target, dict) or target.get('type') != 'tag'
            or target.get('sha') != metadata['tag_object']):
        raise release.ReleaseError('Push the reviewed fixed annotated tag separately; remote tag does not match')
    tag = github(f'repos/{REPOSITORY}/git/tags/{metadata["tag_object"]}')
    target = tag.get('object') if isinstance(tag, dict) else None
    if not isinstance(target, dict) or target.get('type') != 'commit' or target.get('sha') != metadata['commit']:
        raise release.ReleaseError('Remote tag commit differs from the package')


def check_remote(metadata):
    check_remote_tag(metadata)
    if any(item.get('tag_name') == metadata['tag'] for item in remote_releases()):
        raise release.ReleaseError('Release or draft already exists; refusing to replace it')


def upload_draft(snapshot, metadata):
    check_remote(metadata)
    if verify_bundle(snapshot) != metadata:
        raise release.ReleaseError('Publication assets changed before upload')
    subprocess.run(draft_command(snapshot, metadata), check=True, timeout=600)
    # Deliberately never publish or delete a draft, including after an upload failure.
    return {'draft_created': True, 'published': False, 'repository': REPOSITORY, 'tag': metadata['tag']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    local = commands.add_parser('prepare')
    local.add_argument('--package', type=Path, required=True)
    local.add_argument('--notes', type=Path, required=True)
    local.add_argument('--output', type=Path, required=True)
    local.add_argument('--format', dest='archive_format', choices=['zip', 'dmg'], default='dmg',
                       help='Release container (default: dmg); zip is retained for compatibility')
    for name in ['plan', 'create-draft']:
        command = commands.add_parser(name)
        command.add_argument('--bundle', type=Path, required=True)
        if name == 'create-draft':
            command.add_argument('--execute', action='store_true')
            command.add_argument('--ack-upload', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            result = prepare(args.package, args.notes, args.output, archive_format=args.archive_format)
        elif args.command == 'create-draft' and args.execute:
            if not args.ack_upload:
                raise release.ReleaseError('Remote upload requires --execute --ack-upload and separate authorization')
            result = create_draft(args.bundle)
        else:
            metadata = verify_bundle(args.bundle)
            result = {'mode': 'plan-only', 'repository': REPOSITORY, 'publishes': False, 'pushes': False,
                      'command': draft_command(maintenance.safe_path(args.bundle), metadata)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (release.ReleaseError, maintenance.MaintenanceError, OSError, ValueError, zipfile.BadZipFile,
            subprocess.SubprocessError) as error:
        parser.exit(1, f'Personal publication: {error}\n')


if __name__ == '__main__':
    main()
