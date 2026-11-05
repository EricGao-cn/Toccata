#!/usr/bin/env python3
"""Build personal packages without installing, launching, or touching runtime data."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import uuid

import dev

ROOT = Path(__file__).resolve().parents[2]


class ReleaseError(Exception):
    pass


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def publish_new(source, destination):
    """Atomic publication without replacing an output created by another run."""
    library = ctypes.CDLL(None, use_errno=True)
    source, destination = os.fsencode(source), os.fsencode(destination)
    if sys.platform == 'darwin':
        function = library.renamex_np
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        result = function(source, destination, 0x00000004)  # RENAME_EXCL, macOS sys/stdio.h
    elif sys.platform.startswith('linux') and hasattr(library, 'renameat2'):
        function = library.renameat2
        function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = function(-100, source, -100, destination, 1)  # RENAME_NOREPLACE
    else:
        raise ReleaseError('This platform has no supported exclusive publication operation')
    if result:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), os.fsdecode(destination))


def tree_modes(root):
    # Contents and executable permissions are both part of a restorable App.
    root = Path(root)
    return {p.relative_to(root).as_posix(): p.stat().st_mode & 0o777
            for p in [root, *sorted(root.rglob('*'))] if not p.is_symlink()}


def tree_hashes(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ReleaseError(f'Symlink is not allowed in this package: {path}')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha256(path)
        elif not path.is_dir():
            raise ReleaseError(f'Unsupported package entry: {path}')
    return result


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def config():
    result = dev.read_json(ROOT / 'scripts/personal/release.json')
    if (result.get('schema_version') != 1 or result.get('bundle_id') != 'cn.ericgao.toccata.personal'
            or result.get('data_directory_name') != 'Toccata-Personal'
            or result.get('app_name') != 'Toccata Personal'
            or not re.fullmatch(r'\d+\.\d+\.\d+', result.get('version', ''))
            or not re.fullmatch(r'\d+', result.get('build', ''))
            or not re.fullmatch(r'\d+\.\d+', result.get('sdk_version', ''))
            or not re.fullmatch(r'[0-9a-f]{40}', result.get('upstream_sha', ''))):
        raise ReleaseError('Invalid personal release configuration')
    return result


def release_provenance(settings, tag):
    if tag != 'personal-v' + settings['version']:
        raise ReleaseError('Tag must match the personal version exactly')
    if git('status', '--porcelain'):
        raise ReleaseError('Stable packaging requires a clean accepted commit; use build-candidate for rehearsal')
    commit = git('rev-parse', 'HEAD')
    try:
        tagged = git('rev-parse', '--verify', f'refs/tags/{tag}^{{commit}}')
        tag_object = git('rev-parse', '--verify', f'refs/tags/{tag}^{{tag}}')
    except subprocess.CalledProcessError as error:
        raise ReleaseError('Create the fixed annotated personal tag only after acceptance') from error
    if tagged != commit:
        raise ReleaseError('HEAD differs from the fixed personal tag')
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', commit, 'codex/personal'], check=True)
    if git('rev-parse', settings['upstream_tag'] + '^{commit}') != settings['upstream_sha']:
        raise ReleaseError('Upstream tag identity differs from the pinned configuration')
    return commit, tag_object


def verify_package(package, require_stable=True, verify_signature=True):
    package = Path(package)
    if package.is_symlink() or not package.is_dir():
        raise ReleaseError('Package must be an extracted local directory')
    metadata = package / 'release.json'
    if metadata.is_symlink() or (package / 'release.json.sha256').is_symlink():
        raise ReleaseError('Manifest symlink rejected')
    if sha256(metadata) != (package / 'release.json.sha256').read_text().strip():
        raise ReleaseError('Manifest checksum mismatch')
    manifest = json.loads(metadata.read_text())
    if manifest.get('schema_version') != 1:
        raise ReleaseError('Unknown release manifest schema')
    if (not re.fullmatch(r'\d+\.\d+\.\d+', manifest.get('version', ''))
            or not re.fullmatch(r'\d+', manifest.get('build', ''))
            or not re.fullmatch(r'\d+\.\d+', manifest.get('sdk', ''))):
        raise ReleaseError('Invalid package version, build or SDK')
    if require_stable and (manifest.get('channel') != 'personal-stable' or manifest.get('dirty') is not False):
        raise ReleaseError('Candidate builds cannot be installed as a stable release')
    if require_stable and (manifest.get('tag') != 'personal-v' + manifest.get('version', '')
                           or not re.fullmatch(r'[0-9a-f]{40}', manifest.get('tag_object', ''))):
        raise ReleaseError('Stable package has no fixed personal tag')
    if not re.fullmatch(r'[0-9a-f]{40}', manifest.get('commit', '')):
        raise ReleaseError('Package has no source commit')
    expected_id = 'cn.ericgao.toccata.personal'
    if require_stable and manifest.get('bundle_id') != expected_id:
        raise ReleaseError('Wrong personal stable identity')
    app_name = manifest.get('app')
    if app_name != 'Toccata Personal.app':
        raise ReleaseError('Unexpected app name')
    app = package / app_name
    verify_payload(app, manifest, verify_signature=verify_signature)
    return manifest


def verify_payload(app, manifest, verify_signature=True):
    if app.is_symlink() or not app.is_dir() or tree_hashes(app) != manifest.get('files'):
        raise ReleaseError('App payload checksum mismatch')
    if tree_modes(app) != manifest.get('file_modes'):
        raise ReleaseError('App executable/file permissions differ from its manifest')
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    for key, value in [('CFBundleIdentifier', manifest['bundle_id']),
                       ('CFBundleShortVersionString', manifest['version']),
                       ('CFBundleVersion', manifest['build']),
                       ('ToccataSourceCommit', manifest['commit']),
                       ('DTSDKName', 'macosx' + manifest['sdk'])]:
        if info.get(key) != value:
            raise ReleaseError(f'App metadata differs from manifest: {key}')
    if info.get('ToccataUpdateMode') != 'manual' or info.get('ToccataDistributionChannel') != manifest['channel']:
        raise ReleaseError('Package distribution/update policy mismatch')
    for name in ['ToccataPersonal', 'toccata-core']:
        binary = app / 'Contents/MacOS' / name
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ReleaseError(f'Missing executable: {name}')
    if verify_signature:
        subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)


def build(candidate=False, tag=None):
    settings = config()
    commit, tag_object = (git('rev-parse', 'HEAD'), None) if candidate else release_provenance(settings, tag)
    dirty = bool(git('status', '--porcelain'))
    local = dev.validate(ROOT, dev.read_json(dev.local_config_path(ROOT)))
    if settings['sdk_version'] != local['sdk_version']:
        raise ReleaseError('Personal release SDK differs from the explicitly selected toolchain')
    env = dev.environment(ROOT, local)
    dev.require_sdk(local, env)
    cargo = dev.require_rust(local, env)
    # Separate release outputs from every task-only development build.
    env['CARGO_TARGET_DIR'] = str(ROOT / '.local-dev/personal-target')
    scratch = ROOT / '.local-dev' / ('personal-candidate-swift' if candidate else 'personal-stable-swift')
    run = lambda args: dev.run(args, ROOT, env)
    run(['bash', ROOT / 'scripts/sync-assets.sh'])
    run([cargo, 'build', '--locked', '--release', '--features', 'personal-distribution'])
    options = [*dev.swift_options(ROOT, env), '--configuration', 'release']
    options[options.index('--scratch-path') + 1] = scratch
    options += ['-Xswiftc', '-DTOCCATA_PERSONAL']
    if candidate:
        options += ['-Xswiftc', '-DTOCCATA_PERSONAL_CANDIDATE']
    run(['swift', 'build', *options])
    bin_dir = Path(subprocess.check_output(['swift', 'build', *map(str, options), '--show-bin-path'], cwd=ROOT, env=env, text=True).strip())
    studio = bin_dir / 'toccata-studio'
    helper = Path(env['CARGO_TARGET_DIR']) / 'release/toccata-core'
    architectures = []
    for binary in [studio, helper]:
        text = subprocess.check_output(['xcrun', 'vtool', '-show-build', str(binary)], env=env, text=True)
        sdks = set(re.findall(r'^\s*sdk\s+(\S+)', text, re.M))
        if sdks != {settings['sdk_version']}:
            raise ReleaseError(f'Wrong SDK in {binary}: {sdks}')
        architectures.append(subprocess.check_output(['/usr/bin/lipo', '-archs', str(binary)], text=True).strip())
    if architectures[0] != architectures[1]:
        raise ReleaseError('App/helper architecture mismatch')
    if not candidate:
        release_provenance(settings, tag)
    suffix = ('candidate-' + uuid.uuid4().hex[:10]) if candidate else tag
    package = ROOT / '.local-dev/personal-packages' / suffix
    package.mkdir(parents=True, exist_ok=False)
    app = package / 'Toccata Personal.app'
    macos, resources = app / 'Contents/MacOS', app / 'Contents/Resources'
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)
    shutil.copy2(studio, macos / 'ToccataPersonal')
    shutil.copy2(helper, macos / 'toccata-core')
    shutil.copytree(bin_dir / 'toccata-studio_toccata-studio.bundle', resources / 'toccata-studio_toccata-studio.bundle')
    shutil.copy2(ROOT / 'apps/toccata-studio/Resources/AppIcon.icns', resources / 'AppIcon.icns')
    for folder in (ROOT / 'shared/macos-localization').glob('*.lproj'):
        shutil.copytree(folder, resources / folder.name)
    identity = local['bundle_id'] + '.candidate' if candidate else settings['bundle_id']
    channel = 'personal-candidate' if candidate else 'personal-stable'
    info = {
        'CFBundleExecutable': 'ToccataPersonal', 'CFBundleIdentifier': identity,
        'CFBundleName': settings['app_name'], 'CFBundleDisplayName': settings['app_name'],
        'CFBundlePackageType': 'APPL', 'CFBundleIconFile': 'AppIcon',
        'CFBundleShortVersionString': settings['version'], 'CFBundleVersion': settings['build'],
        'LSMinimumSystemVersion': '13.0', 'LSUIElement': True, 'NSHighResolutionCapable': True,
        'NSSupportsAutomaticTermination': False, 'NSSupportsSuddenTermination': False,
        'DTSDKName': 'macosx' + settings['sdk_version'], 'ToccataSourceCommit': commit,
        'ToccataDistributionChannel': channel, 'ToccataUpdateMode': 'manual',
        'ToccataUpstreamTag': settings['upstream_tag'],
        'NSInputMonitoringUsageDescription': 'Personal keyboard activity records stay on this Mac.'
    }
    if candidate:
        info['ToccataCandidateDataDirectory'] = str(Path(local['data_dir']) / 'personal-candidate')
    (app / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    requirements = f'=designated => identifier "{identity}"'
    run(['/usr/bin/codesign', '--force', '--sign', '-', '--identifier', identity, '--requirements', requirements, macos / 'toccata-core'])
    run(['/usr/bin/codesign', '--force', '--sign', '-', '--requirements', requirements, app])
    manifest = dict(schema_version=1, channel=channel, app=app.name, bundle_id=identity,
                    version=settings['version'], build=settings['build'], sdk=settings['sdk_version'],
                    commit=commit, tag=tag if not candidate else None, tag_object=tag_object,
                    upstream_tag=settings['upstream_tag'], upstream_sha=settings['upstream_sha'],
                    dirty=dirty, architecture=architectures[0], files=tree_hashes(app), file_modes=tree_modes(app))
    metadata = package / 'release.json'
    metadata.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    (package / 'release.json.sha256').write_text(sha256(metadata) + '\n')
    verify_package(package, require_stable=not candidate)
    archive = package.parent / (package.name + '.zip')
    run(['/usr/bin/ditto', '-c', '-k', '--keepParent', package, archive])
    archive.with_suffix('.zip.sha256').write_text(sha256(archive) + '  ' + archive.name + '\n')
    print(json.dumps({'package': str(package), 'archive': str(archive), 'channel': channel}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('plan')
    commands.add_parser('build-candidate')
    stable = commands.add_parser('build-release')
    stable.add_argument('--tag', required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('package', type=Path)
    verify.add_argument('--candidate', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'plan':
            print(json.dumps(config(), ensure_ascii=False, indent=2))
        elif args.command == 'verify':
            manifest = verify_package(args.package, require_stable=not args.candidate)
            print(json.dumps({k: manifest[k] for k in ['channel', 'version', 'commit', 'sdk']}, indent=2))
        else:
            build(candidate=args.command == 'build-candidate', tag=getattr(args, 'tag', None))
    except (ReleaseError, dev.SetupError, subprocess.CalledProcessError, OSError, ValueError) as error:
        parser.exit(1, f'Personal packaging: {error}\n')


if __name__ == '__main__':
    main()
