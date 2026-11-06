"""Test DMG policy and mount cleanup with disposable packages and mocked devices."""
from pathlib import Path
import json
import os
import plistlib
import shutil
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/personal'))
import disk_image
import release
import test_personal_release as fixtures


class PersonalDiskImageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PersonalReleaseTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.package = self.fixture.make_package()
        verify = release.verify_package
        self.original_verify = verify
        patch = mock.patch.object(release, 'verify_package', side_effect=lambda p: verify(p, verify_signature=False))
        patch.start(); self.addCleanup(patch.stop)
        self.manifest = release.verify_package(self.package)

    def test_build_preserves_verified_app_and_creates_only_a_readonly_container(self):
        destination = self.root / 'result.dmg'
        (self.package / 'tasks.sqlite').write_bytes(b'private neighboring data; never include')
        before = release.tree_hashes(self.package)
        def command(args, **kwargs):
            self.assertEqual(args[:2], ['/usr/bin/hdiutil', 'create'])
            self.assertIn('UDZO', args)
            self.assertIn('-nospotlight', args)
            self.assertNotIn('-attach', args)
            payload = Path(args[args.index('-srcfolder') + 1])
            self.assertEqual({p.name for p in payload.iterdir()},
                             {'Toccata Personal.app', 'release.json', 'release.json.sha256', '安装说明.txt'})
            self.assertIn('~/Applications', (payload / '安装说明.txt').read_text())
            self.assertEqual(release.verify_package(payload), self.manifest)
            Path(args[-1]).write_bytes(b'synthetic image')
            return subprocess.CompletedProcess(args, 0)
        with mock.patch.object(subprocess, 'run', side_effect=command), \
             mock.patch.object(disk_image, 'verify_image', return_value=self.manifest):
            self.assertEqual(disk_image.build_image(self.package, destination), self.manifest)
        self.assertEqual(destination.read_bytes(), b'synthetic image')
        self.assertEqual(release.tree_hashes(self.package), before)
        with self.assertRaises(release.ReleaseError):
            disk_image.build_image(self.package, destination)

    def test_candidates_are_refused_before_image_creation(self):
        candidate = self.fixture.make_package('1.2.0', candidate=True)
        with mock.patch.object(subprocess, 'run') as command:
            with self.assertRaises(release.ReleaseError):
                disk_image.build_image(candidate, self.root / 'result.dmg')
            command.assert_not_called()

    def verify_fixture(self, extra=False, hidden=False, readonly=True, detach_fails=False,
                       attach_error=None, malformed=False, lingering=False, encrypted=False,
                       info_fails=False, notes=None, corrupt_app=False, special_meta=None, image_format='UDZO', shared_device=False):
        image = self.root / 'fixture.dmg'; image.write_bytes(b'fixture')
        workspace = self.root / 'mount-work'; workspace.mkdir()
        calls = []
        state = {'attached': False, 'attempted': False}
        self.last_workspace, self.last_calls, self.last_state = workspace, calls, state
        private_image = workspace / 'image.dmg'
        def output(args, **kwargs):
            self.assertEqual(kwargs.get('stdin'), subprocess.DEVNULL)
            calls.append(args)
            if args[1] == 'imageinfo':
                return plistlib.dumps({'Format': image_format, 'Properties': {'Encrypted': encrypted, 'Software License Agreement': False}})
            if args[1] == 'info':
                if info_fails: raise subprocess.CalledProcessError(1, args)
                # An unrelated/pre-existing source-image mount must never be ejected.
                images = [{'image-path': str(image), 'system-entities': [{'dev-entry': '/dev/disk999' if shared_device else '/dev/disk41'}]}]
                if state['attached']:
                    images.append({'image-path': str(private_image), 'system-entities': [
                        {'dev-entry': '/dev/disk999'}, {'dev-entry': '/dev/disk999s1', 'mount-point': str(workspace / 'volume')}]})
                return plistlib.dumps({'images': images})
            self.assertEqual(args[1], 'attach')
            self.assertEqual(Path(args[-1]), private_image)
            self.assertNotEqual(Path(args[-1]), image)
            self.assertEqual(private_image.stat().st_mode & 0o777, 0o400)
            self.assertIn('-readonly', args); self.assertIn('-nobrowse', args); self.assertIn('-noautoopen', args)
            state['attempted'] = True
            if attach_error == 'before': raise subprocess.CalledProcessError(1, args)
            mount = Path(args[args.index('-mountpoint') + 1])
            for path in self.package.iterdir():
                if path.is_dir(): shutil.copytree(path, mount / path.name)
                else: shutil.copy2(path, mount / path.name)
            (mount / '安装说明.txt').write_text(notes if notes is not None else disk_image.installation_notes(self.manifest['version']))
            if extra: (mount / 'unexpected.sqlite').write_bytes(b'must not ship')
            if hidden:
                (mount / '.Trashes').mkdir()
                (mount / '.Trashes/private.sqlite').write_bytes(b'must not hide')
            if corrupt_app: (mount / 'Toccata Personal.app/Contents/MacOS/ToccataPersonal').write_bytes(b'corrupt')
            if special_meta:
                metadata = mount / 'release.json'
                metadata.unlink()
                if special_meta == 'symlink': metadata.symlink_to(self.package / 'release.json')
                else: os.mkfifo(metadata)
            state['attached'] = True
            if attach_error == 'timeout': raise subprocess.TimeoutExpired(args, 120)
            if attach_error == 'interrupt': raise KeyboardInterrupt()
            if malformed: return b'not plist'
            return plistlib.dumps({'system-entities': [{'mount-point': str(mount), 'dev-entry': '/dev/disk999s1'}]})
        def command(args, **kwargs):
            self.assertEqual(kwargs.get('stdin'), subprocess.DEVNULL)
            calls.append(args)
            if args[1] == 'detach':
                self.assertEqual(args[-1], '/dev/disk999')
                self.assertNotIn('-force', args)
                if detach_fails: raise subprocess.CalledProcessError(1, args)
                if not lingering: state['attached'] = False
            return subprocess.CompletedProcess(args, 0)
        with mock.patch.object(disk_image.tempfile, 'mkdtemp', return_value=str(workspace)), \
             mock.patch.object(subprocess, 'check_output', side_effect=output), \
             mock.patch.object(subprocess, 'run', side_effect=command), \
             mock.patch.object(os, 'statvfs', return_value=mock.Mock(f_flag=os.ST_RDONLY if readonly else 0)):
            result = disk_image.verify_image(image)
        return result, workspace

    def test_mount_is_private_readonly_and_whole_owned_device_is_detached(self):
        result, workspace = self.verify_fixture()
        self.assertEqual(result, self.manifest)
        self.assertFalse(workspace.exists())
        self.assertFalse(self.last_state['attached'])
        self.assertTrue(any(args[1] == 'detach' for args in self.last_calls))

    def test_unexpected_payload_is_rejected_and_image_detached(self):
        with self.assertRaisesRegex(release.ReleaseError, 'unexpected payload'):
            self.verify_fixture(extra=True)
        self.assertFalse((self.root / 'mount-work').exists())

    def test_hidden_metadata_cannot_hide_user_files(self):
        with self.assertRaisesRegex(release.ReleaseError, 'hidden entries'):
            self.verify_fixture(hidden=True)
        self.assertFalse(self.last_state['attached'])

    def test_writable_mount_is_rejected_and_detached(self):
        with self.assertRaisesRegex(release.ReleaseError, 'read-only'):
            self.verify_fixture(readonly=False)
        self.assertFalse(self.last_state['attached'])

    def test_detach_failure_preserves_mount_workspace_without_force_ejection(self):
        with self.assertRaises(disk_image.DetachError):
            self.verify_fixture(detach_fails=True)
        self.assertTrue((self.root / 'mount-work/volume/Toccata Personal.app').exists())
        self.assertTrue((self.root / 'mount-work/recovery.json').exists())

    def test_detach_success_without_device_disappearance_preserves_workspace(self):
        with self.assertRaises(disk_image.DetachError):
            self.verify_fixture(lingering=True)
        self.assertTrue(self.last_workspace.exists())

    def test_unknown_device_ownership_never_ejects_or_deletes_workspace(self):
        with self.assertRaises(disk_image.DetachError):
            self.verify_fixture(info_fails=True)
        self.assertTrue(self.last_workspace.exists())
        self.assertFalse(any(args[1] == 'detach' for args in self.last_calls))

    def test_attach_timeout_after_device_creation_still_detaches_owned_device(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            self.verify_fixture(attach_error='timeout')
        self.assertFalse(self.last_state['attached'])
        self.assertFalse(self.last_workspace.exists())

    def test_attach_failure_without_device_information_retains_recovery_receipt(self):
        with self.assertRaises(disk_image.DetachError):
            self.verify_fixture(attach_error='before')
        self.assertTrue((self.last_workspace / 'image.dmg').exists())
        self.assertTrue((self.last_workspace / 'recovery.json').exists())

    def test_malformed_attach_reply_is_cleaned_using_device_inventory(self):
        with self.assertRaises(plistlib.InvalidFileException):
            self.verify_fixture(malformed=True)
        self.assertFalse(self.last_state['attached'])
        self.assertFalse(self.last_workspace.exists())

    def test_interrupted_attach_preserves_user_mount_and_cleans_owned_device(self):
        with self.assertRaises(KeyboardInterrupt):
            self.verify_fixture(attach_error='interrupt')
        self.assertFalse(self.last_state['attached'])
        self.assertFalse(self.last_workspace.exists())

    def test_old_instruction_wording_remains_verifiable(self):
        result, _ = self.verify_fixture(notes='Toccata Personal 1.1.0 安装说明\n较早版本的安装说明。\n')
        self.assertEqual(result, self.manifest)

    def test_large_notes_and_corrupt_app_are_rejected_and_detached(self):
        with self.assertRaisesRegex(release.ReleaseError, 'oversized'):
            self.verify_fixture(notes='Toccata Personal 1.1.0\n' + 'x' * 65536)
        self.assertFalse(self.last_state['attached'])
        with self.assertRaises(release.ReleaseError):
            self.verify_fixture(corrupt_app=True)
        self.assertFalse(self.last_state['attached'])

    def test_encrypted_image_is_refused_without_any_attach_or_prompt(self):
        with self.assertRaisesRegex(release.ReleaseError, 'unencrypted'):
            self.verify_fixture(encrypted=True)
        self.assertFalse(self.last_state['attempted'])
        self.assertFalse(self.last_workspace.exists())

    def test_failed_verification_does_not_publish_or_delete_recovery_build_files(self):
        destination = self.root / 'result.dmg'
        def create(args, **kwargs):
            Path(args[-1]).write_bytes(b'fixture')
        with mock.patch.object(subprocess, 'run', side_effect=create), \
             mock.patch.object(disk_image, 'verify_image', side_effect=disk_image.DetachError('busy')):
            with self.assertRaises(disk_image.DetachError):
                disk_image.build_image(self.package, destination)
        self.assertFalse(destination.exists())
        self.assertTrue(list(self.root.glob('.personal-dmg-*/image.dmg')))

    def test_interrupted_image_creation_preserves_build_files_and_never_publishes(self):
        destination = self.root / 'result.dmg'
        def interrupted(args, **kwargs):
            Path(args[-1]).write_bytes(b'incomplete image')
            raise subprocess.TimeoutExpired(args, 180)
        with mock.patch.object(subprocess, 'run', side_effect=interrupted):
            with self.assertRaisesRegex(release.ReleaseError, 'preserve build files'):
                disk_image.build_image(self.package, destination)
        self.assertFalse(destination.exists())
        self.assertTrue(list(self.root.glob('.personal-dmg-*/image.dmg')))
        self.assertTrue(list(self.root.glob('.personal-dmg-*/recovery.json')))

    def test_symlink_and_fifo_metadata_are_refused_before_json_is_opened(self):
        for kind in ['symlink', 'fifo']:
            with self.subTest(kind=kind), mock.patch.object(release, 'verify_package', side_effect=AssertionError('must not open metadata')):
                with self.assertRaisesRegex(release.ReleaseError, 'Invalid or oversized'):
                    self.verify_fixture(special_meta=kind)
            self.assertFalse(self.last_state['attached'])

    def test_writable_container_format_is_rejected_before_attach(self):
        with self.assertRaisesRegex(release.ReleaseError, 'UDZO'):
            self.verify_fixture(image_format='UDRW')
        self.assertFalse(self.last_state['attempted'])

    def test_device_alias_shared_with_user_image_is_not_ejected(self):
        with self.assertRaises(disk_image.DetachError):
            self.verify_fixture(shared_device=True)
        self.assertTrue(self.last_workspace.exists())
        self.assertFalse(any(args[1] == 'detach' for args in self.last_calls))

    @unittest.skipUnless(sys.platform == 'darwin', 'native macOS code-signature validation')
    def test_rehashed_manifest_cannot_hide_a_broken_native_signature(self):
        app = self.package / 'Toccata Personal.app'
        for name in ['ToccataPersonal', 'toccata-core']:
            binary = app / 'Contents/MacOS' / name
            shutil.copyfile('/usr/bin/true', binary)
            binary.chmod(0o755)
        for target in [app / 'Contents/MacOS/toccata-core', app]:
            subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', str(target)],
                           check=True, capture_output=True)
        def refresh():
            manifest = json.loads((self.package / 'release.json').read_text())
            manifest['files'] = release.tree_hashes(app)
            manifest['file_modes'] = release.tree_modes(app)
            (self.package / 'release.json').write_text(json.dumps(manifest))
            (self.package / 'release.json.sha256').write_text(release.sha256(self.package / 'release.json'))
        refresh()
        (self.package / '安装说明.txt').write_text(disk_image.installation_notes('1.1.0'))
        native_run = subprocess.run
        def quiet(args, **kwargs):
            return native_run(args, **kwargs, capture_output=True)
        with mock.patch.object(release, 'verify_package', side_effect=self.original_verify), \
             mock.patch.object(subprocess, 'run', side_effect=quiet):
            disk_image._verified_payload(self.package)
            helper = app / 'Contents/MacOS/toccata-core'
            content = bytearray(helper.read_bytes()); content[4096] ^= 1; helper.write_bytes(content)
            refresh()  # All ordinary hashes now match, while code signing must still fail.
            with self.assertRaises(subprocess.CalledProcessError):
                disk_image._verified_payload(self.package)

    def test_ownership_inspection_does_not_resolve_unrelated_image_paths(self):
        private = self.root / 'private.dmg'
        info = {'images': [
            {'image-path': '/Volumes/private-user-image/locked.dmg', 'system-entities': [{'dev-entry': '/dev/disk41'}]},
            {'image-path': str(private), 'system-entities': [{'dev-entry': '/dev/disk999'}]}]}
        with mock.patch.object(subprocess, 'check_output', return_value=plistlib.dumps(info)), \
             mock.patch.object(Path, 'resolve', side_effect=AssertionError('must not access unrelated paths')):
            self.assertEqual(disk_image._attached_devices(private), {'/dev/disk999'})
