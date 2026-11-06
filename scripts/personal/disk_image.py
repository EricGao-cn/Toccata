"""Read-only personal DMG containers; never installs or launches an App."""
import os
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile

import maintenance
import release


class DetachError(release.ReleaseError):
    pass


def installation_notes(version):
    return f'''Toccata Personal {version} 安装说明

1. 在 Finder 中选择“前往 → 前往文件夹”，输入 ~/Applications；没有此文件夹时先新建。
2. 如已有个人版，先备份数据并从菜单栏正常退出。将 Toccata Personal.app 拖到上述文件夹。
3. 推出此磁盘映像，再从 ~/Applications/Toccata Personal.app 打开；不要直接从 DMG 运行。
4. 数据独立保存在 ~/Library/Application Support/Toccata-Personal。首次使用可从空数据开始，原版 App 与数据保留，不自动迁移。
5. 需要键盘统计时，在“系统设置 → 隐私与安全性 → 输入监控”确认个人版权限。勿同时运行两套采集服务。

关于窗口从 EricGao-cn/Toccata 检查个人正式版本；安装更新仍需手动进行。
DMG 只改变外层封装，内含 App 与对应版本的已验收正式包一致。
此 App 为本机 ad-hoc 签名，未做 Developer ID 公证；磁盘映像不会修改权限、登录项或数据。
'''


def _attached_devices(image):
    """Only return devices backed by this invocation's private image copy."""
    info = plistlib.loads(subprocess.check_output(['/usr/bin/hdiutil', 'info', '-plist'],
                                                stdin=subprocess.DEVNULL, timeout=30))
    images = info.get('images') if isinstance(info, dict) else None
    if not isinstance(images, list):
        raise release.ReleaseError('Cannot inspect attached disk images')
    devices = set()
    other_devices = set()
    for record in images:
        if not isinstance(record, dict) or not isinstance(record.get('image-path'), str):
            raise release.ReleaseError('Invalid disk image ownership information')
        # Compare the OS-reported path without touching unrelated users' image files.
        owned = os.path.abspath(record['image-path']) == str(image)
        entities = record.get('system-entities')
        if not isinstance(entities, list):
            raise release.ReleaseError('Missing owned disk device information')
        found = set()
        for entry in entities:
            if not isinstance(entry, dict) or not isinstance(entry.get('dev-entry'), str):
                raise release.ReleaseError('Invalid owned disk device entry')
            device = entry.get('dev-entry', '')
            match = re.fullmatch(r'(/dev/disk[0-9]+)(?:s[0-9]+)*', device)
            if match:
                found.add(match.group(1))
        if owned and len(found) != 1:
            raise release.ReleaseError('Ambiguous owned disk device information')
        if owned:
            devices.update(found)
        else:
            other_devices.update(found)
    if devices & other_devices:
        raise release.ReleaseError('Verification device is shared with another image; refuse to eject it')
    if len(devices) > 1:
        raise release.ReleaseError('Multiple devices unexpectedly use the private verification image')
    return devices


def _finish_mount(image, mount, workspace):
    """Never recursively remove a workspace until its owned device is gone."""
    devices = set()
    try:
        devices = _attached_devices(image)
        if not devices:
            raise release.ReleaseError('Cannot confirm ownership after an attach attempt')
        for device in devices:
            subprocess.run(['/usr/bin/hdiutil', 'detach', '-quiet', device], check=True,
                           stdin=subprocess.DEVNULL, timeout=30)
        if _attached_devices(image) or os.path.ismount(mount):
            raise release.ReleaseError('Verification device remains attached after detach')
    except BaseException as error:
        try:
            (workspace / 'recovery.json').write_text(json.dumps({
                'image': str(image), 'mount': str(mount), 'owned_devices': sorted(devices),
                'state': 'cleanup_unconfirmed', 'error': str(error),
                'instruction': 'Do not remove this directory until its image device is detached.'}, indent=2) + '\n')
        except OSError:
            pass
        raise DetachError(f'Cannot confirm verification image is detached; preserve {workspace}. '
                          f'Inspect {image}, devices {sorted(devices)}, and recovery.json before cleanup') from error


def _verified_payload(mount):
    # Inspect file types before opening JSON or notes: no FIFO/device/symlink reads.
    expected = {'Toccata Personal.app', 'release.json', 'release.json.sha256', '安装说明.txt'}
    if {entry.name for entry in mount.iterdir()} != expected:
        raise release.ReleaseError('DMG contains unexpected payload files, including hidden entries')
    app = mount / 'Toccata Personal.app'
    if app.is_symlink() or not app.is_dir():
        raise release.ReleaseError('Invalid DMG App entry')
    for name, limit in [('release.json', 4_194_304), ('release.json.sha256', 1024), ('安装说明.txt', 65_536)]:
        path = mount / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise release.ReleaseError(f'Invalid or oversized DMG metadata: {name}')
    manifest = release.verify_package(mount)
    notes = (mount / '安装说明.txt').read_text(encoding='utf-8')
    # Old DMGs remain verifiable when wording changes in a later packaging tool.
    # The enclosing SHA-256 checks the exact original notes bytes.
    prefix = 'Toccata Personal ' + manifest['version']
    header = notes.splitlines()[0] if notes else ''
    if not (header == prefix or header.startswith(prefix + ' ')) or '\x00' in notes:
        raise release.ReleaseError('Invalid DMG installation notes')
    return manifest


def verify_image(image):
    image = maintenance.safe_path(image)
    if not image.is_file():
        raise release.ReleaseError('Provide a local DMG file')
    workspace = Path(tempfile.mkdtemp(prefix='toccata-dmg-verify-')).resolve()
    mount = workspace / 'volume'
    private_image = workspace / 'image.dmg'
    attempted = False
    try:
        mount.mkdir(mode=0o700)
        original_hash = release.sha256(image)
        shutil.copy2(image, private_image)
        if release.sha256(private_image) != original_hash or release.sha256(image) != original_hash:
            raise release.ReleaseError('DMG changed while preparing its private verification copy')
        private_image.chmod(0o400)
        info = plistlib.loads(subprocess.check_output(['/usr/bin/hdiutil', 'imageinfo', '-plist', str(private_image)],
                                                    stdin=subprocess.DEVNULL, timeout=30))
        properties = info.get('Properties') if isinstance(info, dict) else None
        if (not isinstance(properties, dict) or info.get('Format') != 'UDZO'
                or properties.get('Encrypted') is not False or properties.get('Software License Agreement') is not False):
            raise release.ReleaseError('DMG must be unencrypted UDZO without an interactive license')
        subprocess.run(['/usr/bin/hdiutil', 'verify', '-quiet', str(private_image)], check=True,
                       stdin=subprocess.DEVNULL, timeout=120)
        (workspace / 'recovery.json').write_text(json.dumps({'source': str(image), 'image': str(private_image),
            'mount': str(mount), 'state': 'attach_planned'}, indent=2) + '\n')
        attempted = True
        output = subprocess.check_output(['/usr/bin/hdiutil', 'attach', '-readonly', '-nobrowse', '-noautoopen',
                                          '-mountpoint', str(mount), '-plist', str(private_image)],
                                         stdin=subprocess.DEVNULL, timeout=120)
        attached = plistlib.loads(output)
        entities = attached.get('system-entities') if isinstance(attached, dict) else None
        if not isinstance(entities, list) or any(not isinstance(entry, dict) for entry in entities):
            raise release.ReleaseError('Invalid DMG attach response')
        points = [entry['mount-point'] for entry in entities if 'mount-point' in entry]
        if points != [str(mount)] or not os.statvfs(mount).f_flag & os.ST_RDONLY:
            raise release.ReleaseError('DMG was not mounted read-only at the private verification path')
        manifest = _verified_payload(mount)
        if release.sha256(image) != original_hash:
            raise release.ReleaseError('Source DMG changed during verification')
        return manifest
    finally:
        if attempted:
            # If attachment timed out, parsing failed, or validation was interrupted,
            # query the private image's whole device instead of guessing a mountpoint.
            _finish_mount(private_image, mount, workspace)
        shutil.rmtree(workspace)


def build_image(package, destination):
    package, destination = map(maintenance.safe_path, [package, destination])
    maintenance.disjoint(package, destination)
    if destination.exists():
        raise release.ReleaseError('DMG output exists; refusing to overwrite')
    manifest = release.verify_package(package)
    destination.parent.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix='.personal-dmg-', dir=destination.parent))
    preserve = False
    try:
        payload = workspace / 'payload'
        payload.mkdir(mode=0o700)
        shutil.copytree(package / manifest['app'], payload / manifest['app'])
        for name in ['release.json', 'release.json.sha256']:
            shutil.copy2(package / name, payload / name)
        if release.verify_package(payload) != manifest or release.verify_package(package) != manifest:
            raise release.ReleaseError('Package changed while preparing DMG payload')
        (payload / '安装说明.txt').write_text(installation_notes(manifest['version']))
        staged = workspace / 'image.dmg'
        try:
            subprocess.run(['/usr/bin/hdiutil', 'create', '-quiet', '-volname', 'Toccata Personal ' + manifest['version'],
                            '-srcfolder', str(payload), '-fs', 'HFS+', '-format', 'UDZO', '-nospotlight',
                            '-imagekey', 'zlib-level=9', str(staged)], check=True, stdin=subprocess.DEVNULL, timeout=180)
        except BaseException as error:
            preserve = True
            (workspace / 'recovery.json').write_text(json.dumps({'image': str(staged), 'state': 'creation_interrupted',
                'error': str(error), 'instruction': 'Inspect hdiutil info before removing this build directory.'}, indent=2) + '\n')
            raise release.ReleaseError(f'DMG creation did not complete; preserve build files at {workspace}') from error
        if verify_image(staged) != manifest:
            raise release.ReleaseError('DMG payload differs from the verified source package')
        with staged.open('rb') as handle:
            os.fsync(handle.fileno())
        release.publish_new(staged, destination)
        maintenance.sync_directory(destination.parent)
        return manifest
    except DetachError as error:
        preserve = True
        raise DetachError(f'{error}; preserve DMG build files at {workspace}') from error
    finally:
        if not preserve:
            shutil.rmtree(workspace)
