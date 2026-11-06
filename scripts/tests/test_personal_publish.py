"""Exercise the personal release workflow with fixture packages and no GitHub writes."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/personal'))
import publish
import release
import test_personal_release as fixtures


@unittest.skipUnless(Path('/usr/bin/ditto').exists(), 'ZIP packaging uses macOS ditto')
class PersonalPublishTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PersonalReleaseTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.package = self.fixture.make_package()
        metadata = self.package / 'release.json'
        manifest = json.loads(metadata.read_text())
        manifest['architecture'] = 'arm64'
        metadata.write_text(json.dumps(manifest))
        (self.package / 'release.json.sha256').write_text(release.sha256(metadata))
        self.manifest = manifest
        self.notes = self.root / 'personal-v1.1.0.md'
        self.notes.write_text('# Personal 1.1.0\nLocal publication fixture.\n')
        self.bundle = self.root / 'bundle'
        # Exercise actual manifest/hash/mode validation, with synthetic unsigned apps.
        verify = release.verify_package
        patch = mock.patch.object(release, 'verify_package', side_effect=lambda path: verify(path, verify_signature=False))
        patch.start(); self.addCleanup(patch.stop)
        self.real_provenance = publish.provenance
        patch = mock.patch.object(publish, 'provenance')
        self.provenance = patch.start(); self.addCleanup(patch.stop)

    def prepare(self):
        return publish.prepare(self.package, self.notes, self.bundle, archive_format='zip')

    def refresh_checksums(self):
        path = self.bundle / 'github-release.json'
        metadata = json.loads(path.read_text())
        archive = metadata['archive']
        (self.bundle / (archive + '.sha256')).write_text(release.sha256(self.bundle / archive) + '  ' + archive + '\n')
        metadata['files'] = {key: value for key, value in release.tree_hashes(self.bundle).items() if key != 'github-release.json'}
        path.write_text(json.dumps(metadata))
        return metadata

    def test_local_preparation_is_allowlisted_verified_and_never_connects(self):
        (self.package / 'tasks.sqlite').write_bytes(b'private neighboring data, must never ship')
        with mock.patch.object(publish, 'github') as network:
            metadata = self.prepare()
            self.assertEqual(publish.verify_bundle(self.bundle), metadata)
            network.assert_not_called()
        self.assertEqual(metadata['repository'], 'EricGao-cn/Toccata')
        with zipfile.ZipFile(self.bundle / metadata['archive']) as zipped:
            self.assertNotIn('personal-v1.1.0/tasks.sqlite', zipped.namelist())
        self.assertEqual((self.package / 'tasks.sqlite').read_bytes(), b'private neighboring data, must never ship')
        command = publish.draft_command(self.bundle, metadata)
        self.assertIn('--draft', command)
        self.assertIn('--verify-tag', command)
        self.assertIn('github.com/EricGao-cn/Toccata', command)
        with self.assertRaises(release.ReleaseError):
            self.prepare()

    def test_candidates_and_mismatched_notes_are_rejected(self):
        candidate = self.fixture.make_package('1.2.0', candidate=True)
        with self.assertRaises(release.ReleaseError):
            publish.prepare(candidate, self.notes, self.bundle)
        wrong_notes = self.root / 'v1.1.0.md'
        wrong_notes.write_text('wrong channel')
        with self.assertRaises(release.ReleaseError):
            publish.prepare(self.package, wrong_notes, self.bundle)
        self.assertFalse(self.bundle.exists())

    def test_modified_assets_or_repository_are_rejected(self):
        self.prepare()
        asset = self.bundle / 'RELEASE.md'
        original = asset.read_bytes()
        asset.write_bytes(b'tampered')
        with self.assertRaises(release.ReleaseError):
            publish.verify_bundle(self.bundle)
        asset.write_bytes(original)
        metadata = self.bundle / 'github-release.json'
        value = json.loads(metadata.read_text()); value['repository'] = 'KMnO4-zx/Toccata'
        metadata.write_text(json.dumps(value))
        with self.assertRaises(release.ReleaseError):
            publish.verify_bundle(self.bundle)

    def test_unsafe_zip_is_rejected_before_extraction(self):
        for name in ['../outside', '/tmp/outside', 'personal-v1.1.0/../../outside', 'other-tag/file']:
            archive = self.root / 'malicious.zip'
            with zipfile.ZipFile(archive, 'w') as zipped:
                zipped.writestr(name, 'fixture')
            with mock.patch.object(subprocess, 'run') as run:
                with self.assertRaises(release.ReleaseError):
                    publish.unpack_verified(archive, self.root / 'unpack', 'personal-v1.1.0')
                run.assert_not_called()

    def test_remote_tag_or_release_conflict_never_creates_a_draft(self):
        self.prepare()
        for responses in [
            [{'object': {'type': 'commit', 'sha': 'a' * 40}}],
            [{'object': {'type': 'tag', 'sha': 'c' * 40}}],
            [{'object': {'type': 'tag', 'sha': 'b' * 40}}, {'object': {'type': 'commit', 'sha': 'c' * 40}}],
            [{'object': {'type': 'tag', 'sha': 'b' * 40}}, {'object': {'type': 'commit', 'sha': 'a' * 40}},
             [{'tag_name': 'personal-v1.1.0'}]],
        ]:
            with mock.patch.object(publish, 'github', side_effect=responses):
                real_run = subprocess.run
                calls = []
                def run(args, **kwargs):
                    if args[0] == 'gh': calls.append(args); return subprocess.CompletedProcess(args, 0)
                    return real_run(args, **kwargs)
                with mock.patch.object(subprocess, 'run', side_effect=run):
                    with self.assertRaises(release.ReleaseError):
                        publish.create_draft(self.bundle)
                self.assertEqual(calls, [])

    def test_explicit_upload_creates_only_a_draft_with_no_push_or_publish(self):
        self.prepare()
        responses = [{'object': {'type': 'tag', 'sha': 'b' * 40}},
                     {'object': {'type': 'commit', 'sha': 'a' * 40}}, []]
        calls = []
        real_run = subprocess.run
        def run(args, **kwargs):
            if args[0] == 'gh': calls.append(args); return subprocess.CompletedProcess(args, 0)
            return real_run(args, **kwargs)
        with mock.patch.object(publish, 'github', side_effect=responses), mock.patch.object(subprocess, 'run', side_effect=run):
            result = publish.create_draft(self.bundle)
        self.assertFalse(result['published'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][:2], ['gh', 'release'])
        self.assertIn('--draft', calls[0])
        self.assertNotIn('--clobber', calls[0])

    def test_cli_requires_ack_before_accessing_bundle_or_network(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/personal/publish.py'),
            'create-draft', '--bundle', str(self.root / 'missing'), '--execute'], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--ack-upload', result.stderr)

    def test_plan_and_default_draft_command_never_access_github(self):
        self.prepare()
        for command in ['plan', 'create-draft']:
            with mock.patch.object(sys, 'argv', ['publish.py', command, '--bundle', str(self.bundle)]), \
                 mock.patch.object(publish, 'github') as network, mock.patch('builtins.print') as output:
                publish.main()
                network.assert_not_called()
                self.assertEqual(json.loads(output.call_args.args[0])['mode'], 'plan-only')

    def test_api_and_upload_failure_never_push_publish_or_delete(self):
        self.prepare()
        real_run = subprocess.run
        mutations = []
        def run(args, **kwargs):
            if args[0] == 'gh':
                mutations.append(args)
                raise subprocess.CalledProcessError(1, args)
            return real_run(args, **kwargs)
        for error in [subprocess.CalledProcessError(1, ['gh', 'api']), subprocess.TimeoutExpired(['gh', 'api'], 30)]:
            with mock.patch.object(publish, 'github', side_effect=error), mock.patch.object(subprocess, 'run', side_effect=run):
                with self.assertRaises(subprocess.SubprocessError):
                    publish.create_draft(self.bundle)
        self.assertEqual(mutations, [])
        responses = [{'object': {'type': 'tag', 'sha': 'b' * 40}},
                     {'object': {'type': 'commit', 'sha': 'a' * 40}}, []]
        with mock.patch.object(publish, 'github', side_effect=responses), mock.patch.object(subprocess, 'run', side_effect=run):
            with self.assertRaises(subprocess.CalledProcessError):
                publish.create_draft(self.bundle)
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0][:3], ['gh', 'release', 'create'])
        self.assertIn('--draft', mutations[0])

    def test_extra_files_inside_zip_are_rejected_even_with_updated_checksums(self):
        metadata = self.prepare()
        with zipfile.ZipFile(self.bundle / metadata['archive'], 'a') as zipped:
            zipped.writestr('personal-v1.1.0/private-records.sqlite', b'must never be uploaded')
        self.refresh_checksums()
        with self.assertRaisesRegex(release.ReleaseError, 'unexpected neighboring'):
            publish.verify_bundle(self.bundle)

    def test_archive_name_cannot_mislabel_the_manifest_architecture(self):
        metadata = self.prepare()
        renamed = metadata['archive'].replace('arm64', 'x86_64')
        (self.bundle / metadata['archive']).rename(self.bundle / renamed)
        (self.bundle / (metadata['archive'] + '.sha256')).unlink()
        metadata['archive'] = renamed
        (self.bundle / 'github-release.json').write_text(json.dumps(metadata))
        self.refresh_checksums()
        with self.assertRaisesRegex(release.ReleaseError, 'metadata differs'):
            publish.verify_bundle(self.bundle)

    def test_upload_uses_the_verified_private_snapshot_when_source_is_edited(self):
        metadata = self.prepare()
        original_notes = (self.bundle / 'RELEASE.md').read_bytes()
        responses = [{'object': {'type': 'tag', 'sha': 'b' * 40}},
                     {'object': {'type': 'commit', 'sha': 'a' * 40}}, []]
        def remote(_):
            (self.bundle / 'RELEASE.md').write_text('edited during remote preflight')
            return responses.pop(0)
        calls = []
        real_run = subprocess.run
        def run(args, **kwargs):
            if args[0] == 'gh':
                notes = Path(args[args.index('--notes-file') + 1])
                self.assertNotEqual(notes.parent, self.bundle)
                self.assertEqual(notes.read_bytes(), original_notes)
                self.assertEqual(release.sha256(notes.parent / metadata['archive']), metadata['files'][metadata['archive']])
                calls.append(args)
                return subprocess.CompletedProcess(args, 0)
            return real_run(args, **kwargs)
        with mock.patch.object(publish, 'github', side_effect=remote), mock.patch.object(subprocess, 'run', side_effect=run):
            result = publish.create_draft(self.bundle)
        self.assertFalse(result['published'])
        self.assertEqual(len(calls), 1)

    def test_invalid_or_incomplete_remote_listing_never_uploads(self):
        self.prepare()
        for listing in [[None], [{'id': 1}], [{'tag_name': 12}], {'message': 'bad response'}]:
            responses = [{'object': {'type': 'tag', 'sha': 'b' * 40}},
                         {'object': {'type': 'commit', 'sha': 'a' * 40}}, listing]
            with mock.patch.object(publish, 'github', side_effect=responses), mock.patch.object(publish, 'draft_command') as command:
                with self.assertRaises(release.ReleaseError):
                    publish.create_draft(self.bundle)
                command.assert_not_called()
        with mock.patch.object(publish, 'github', return_value=[{'tag_name': 'unrelated'}] * 100) as remote:
            with self.assertRaisesRegex(release.ReleaseError, 'incomplete'):
                publish.remote_releases()
            self.assertEqual(remote.call_count, 10)

    def test_provenance_rejects_wrong_local_tag_and_unaccepted_commit(self):
        # Use the real provenance function despite the unsigned-fixture setup.
        real_provenance = self.real_provenance
        with mock.patch.object(release, 'git', return_value='c' * 40):
            with self.assertRaises(release.ReleaseError):
                real_provenance(self.manifest)
        with mock.patch.object(release, 'git', side_effect=['b' * 40, 'a' * 40]), \
             mock.patch.object(subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['git', 'merge-base'])):
            with self.assertRaises(subprocess.CalledProcessError):
                real_provenance(self.manifest)

    def test_dmg_preparation_and_verification_reuse_stable_provenance_without_network(self):
        def build(package, destination):
            self.assertEqual(release.verify_package(package), self.manifest)
            destination.write_bytes(b'fixture disk image')
            return self.manifest
        with mock.patch.object(publish.disk_image, 'build_image', side_effect=build), \
             mock.patch.object(publish.disk_image, 'verify_image', return_value=self.manifest) as verify, \
             mock.patch.object(publish, 'github') as network:
            metadata = publish.prepare(self.package, self.notes, self.bundle, archive_format='dmg')
            self.assertEqual(publish.verify_bundle(self.bundle), metadata)
            self.assertTrue(metadata['archive'].endswith('-arm64.dmg'))
            self.assertTrue((self.bundle / (metadata['archive'] + '.sha256')).is_file())
            verify.assert_called_once()
            network.assert_not_called()
            self.assertIn(str(self.bundle / metadata['archive']), publish.draft_command(self.bundle, metadata))

    def test_unknown_container_format_stops_before_creating_output(self):
        with self.assertRaises(release.ReleaseError):
            publish.prepare(self.package, self.notes, self.bundle, archive_format='pkg')
        self.assertFalse(self.bundle.exists())

    def test_cli_defaults_to_dmg_and_keeps_explicit_zip_option(self):
        for flags, expected in [([], 'dmg'), (['--format', 'zip'], 'zip')]:
            args = ['publish.py', 'prepare', '--package', str(self.package), '--notes', str(self.notes), '--output', str(self.bundle), *flags]
            with mock.patch.object(sys, 'argv', args), mock.patch.object(publish, 'prepare', return_value={}) as prepare, mock.patch('builtins.print'):
                publish.main()
                self.assertEqual(prepare.call_args.kwargs['archive_format'], expected)

    def test_zip_bundle_changed_during_verification_is_rejected(self):
        self.prepare()
        unpack = publish.unpack_verified
        def changed(*args):
            manifest = unpack(*args)
            (self.bundle / 'RELEASE.md').write_text('changed during verification')
            return manifest
        with mock.patch.object(publish, 'unpack_verified', side_effect=changed):
            with self.assertRaisesRegex(release.ReleaseError, 'changed during'):
                publish.verify_bundle(self.bundle)

    def test_dmg_bundle_changed_during_verification_is_rejected(self):
        def build(package, destination):
            destination.write_bytes(b'fixture disk image')
            return self.manifest
        with mock.patch.object(publish.disk_image, 'build_image', side_effect=build):
            publish.prepare(self.package, self.notes, self.bundle)
        def changed(_):
            (self.bundle / 'RELEASE.md').write_text('changed during mount')
            return self.manifest
        with mock.patch.object(publish.disk_image, 'verify_image', side_effect=changed):
            with self.assertRaisesRegex(release.ReleaseError, 'changed during'):
                publish.verify_bundle(self.bundle)


if __name__ == '__main__':
    unittest.main()
