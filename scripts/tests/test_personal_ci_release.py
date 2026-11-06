"""Rehearse Actions provenance and draft-only gates in disposable Git repositories."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/personal'))
import ci_release
import publish
import release


class PersonalCIReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='toccata-actions-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.tag = 'personal-v1.2.3'
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.root / '.gitignore').write_text('.local-dev/\ndist/\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Upstream fixture')
        self.git('tag', 'v0.1.4')
        settings = json.loads((ROOT / 'scripts/personal/release.json').read_text())
        settings.update(version='1.2.3', upstream_sha=self.git('rev-parse', 'HEAD'))
        config = self.root / 'scripts/personal/release.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps(settings))
        self.notes = self.root / 'docs/releases' / (self.tag + '.md')
        self.notes.parent.mkdir(parents=True)
        self.notes.write_text('Fixture release notes.\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Accepted personal fixture')
        self.commit = self.git('rev-parse', 'HEAD')
        self.git('tag', '-a', self.tag, '-m', 'Fixed fixture release')
        self.tag_object = self.git('rev-parse', self.tag)
        self.git('update-ref', 'refs/remotes/origin/codex/personal', self.commit)
        self.git('checkout', '--detach', '-q', self.commit)
        self.event_path = self.root / '.local-dev/event.json'
        self.event_path.parent.mkdir()
        self.event_path.write_text(json.dumps({'created': True, 'deleted': False, 'forced': False}))
        env = {
            'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'EricGao-cn/Toccata',
            'GITHUB_SERVER_URL': 'https://github.com', 'GITHUB_EVENT_NAME': 'push',
            'GITHUB_REF': 'refs/tags/' + self.tag, 'GITHUB_SHA': self.commit,
            'GITHUB_EVENT_PATH': str(self.event_path), 'GITHUB_OUTPUT': '',
        }
        for patch in (mock.patch.object(release, 'ROOT', self.root), mock.patch.dict(os.environ, env),
                      mock.patch.object(publish, 'github', side_effect=AssertionError('Unexpected network access'))):
            patch.start()
            self.addCleanup(patch.stop)
        self.expected = {'tag': self.tag, 'commit': self.commit, 'tag_object': self.tag_object}
        self.archive = 'Toccata-Personal-1.2.3-arm64.dmg'
        self.metadata = dict(self.expected, archive=self.archive, files={
            self.archive: 'd' * 64, self.archive + '.sha256': 'e' * 64,
            'release.json': 'a' * 64, 'release.json.sha256': 'b' * 64,
            'RELEASE.md': hashlib.sha256(b'Fixture release notes.\n').hexdigest()})
        self.bundle = self.root / 'dist/assets'
        self.bundle.mkdir(parents=True)
        (self.bundle / 'RELEASE.md').write_text(self.notes.read_text())

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True, stderr=subprocess.PIPE).strip()

    def verify(self, **changes):
        args = dict(bundle=self.root / 'dist/assets', tag=self.tag, commit=self.commit,
                    tag_object=self.tag_object, archive_sha256='d' * 64)
        args.update(changes)
        return ci_release.verify_bundle(**args)

    def test_accepted_annotated_tag_prepares_personal_branch_without_changing_head(self):
        self.assertEqual(ci_release.checkout(self.tag), self.expected)
        self.assertEqual(self.git('rev-parse', 'codex/personal'), self.commit)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.commit)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_resolve_uses_clean_accepted_mainline_before_selecting_tag_code(self):
        self.assertEqual(ci_release.resolve(self.tag), self.expected)
        self.git('checkout', '-qb', 'unaccepted-tag')
        malicious = self.root / 'scripts/personal/ci_release.py'
        malicious.write_text('raise RuntimeError("unaccepted tag code must never run")\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Unaccepted tag code')
        unaccepted = self.git('rev-parse', 'HEAD')
        self.git('tag', '-a', 'personal-v9.0.0', '-m', 'Unaccepted tag')
        self.git('checkout', '--detach', '-q', self.commit)
        with mock.patch.dict(os.environ, {'GITHUB_REF': 'refs/tags/personal-v9.0.0', 'GITHUB_SHA': unaccepted}):
            with self.assertRaises(subprocess.CalledProcessError):
                ci_release.resolve('personal-v9.0.0')
        self.assertFalse(malicious.exists())
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.commit)
        publish.github.assert_not_called()

    def test_resolve_rejects_dirty_or_nonmainline_bootstrap(self):
        self.notes.write_text('dirty')
        with self.assertRaisesRegex(release.ReleaseError, 'clean fetched'):
            ci_release.resolve(self.tag)
        self.git('checkout', '--', str(self.notes.relative_to(self.root)))
        self.git('checkout', '--detach', '-q', 'v0.1.4')
        with self.assertRaisesRegex(release.ReleaseError, 'clean fetched'):
            ci_release.resolve(self.tag)

    def test_changed_annotation_after_resolution_blocks_build_before_remote_access(self):
        self.assertEqual(ci_release.resolve(self.tag), self.expected)
        self.git('tag', '-f', '-a', self.tag, '-m', 'Changed annotation')
        args = ['ci_release.py', 'check', '--tag', self.tag, '--commit', self.commit,
                '--tag-object', self.tag_object]
        with mock.patch.object(sys, 'argv', args), contextlib.redirect_stderr(io.StringIO()) as output:
            with self.assertRaises(SystemExit):
                ci_release.main()
            self.assertIn('Tag changed after resolution', output.getvalue())
        publish.github.assert_not_called()

    def test_context_rejects_other_repos_events_refs_and_injected_inputs_before_git(self):
        invalid = [
            {'GITHUB_ACTIONS': 'false'}, {'GITHUB_REPOSITORY': 'KMnO4-zx/Toccata'},
            {'GITHUB_SERVER_URL': 'https://example.invalid'}, {'GITHUB_EVENT_NAME': 'pull_request'},
            {'GITHUB_REF': 'refs/heads/main'}, {'GITHUB_SHA': 'not-a-sha'},
            {'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_REF': 'refs/heads/main'},
        ]
        for env in invalid:
            with self.subTest(env=env), mock.patch.dict(os.environ, env), mock.patch.object(release, 'git') as git:
                with self.assertRaises(release.ReleaseError):
                    ci_release.checkout(self.tag)
                git.assert_not_called()
        for tag in ('v1.2.3', 'personal-v01.2.3', 'personal-v1.2.3-rc1', 'personal-v1.2.3\ncommit=x', '$(touch injected)'):
            with self.subTest(tag=tag), mock.patch.object(release, 'git') as git:
                with self.assertRaises(release.ReleaseError):
                    ci_release.checkout(tag)
                git.assert_not_called()
        self.assertFalse((self.root / 'injected').exists())

    def test_deleted_forced_or_incomplete_push_payloads_are_refused(self):
        for payload in ({'created': True, 'deleted': True, 'forced': False},
                        {'created': True, 'deleted': False, 'forced': True},
                        {'created': False, 'deleted': False, 'forced': False}, {}, []):
            self.event_path.write_text(json.dumps(payload))
            with self.subTest(payload=payload), self.assertRaises(release.ReleaseError):
                ci_release.checkout(self.tag)

    def test_manual_run_can_rebuild_accepted_tag_after_mainline_advances(self):
        self.git('checkout', '-qb', 'accepted-next')
        (self.root / 'next.txt').write_text('Another accepted change')
        self.git('add', '.')
        self.git('commit', '-qm', 'Advance accepted mainline')
        next_commit = self.git('rev-parse', 'HEAD')
        self.git('update-ref', 'refs/remotes/origin/codex/personal', next_commit)
        self.git('checkout', '--detach', '-q', self.commit)
        with mock.patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'workflow_dispatch',
                                         'GITHUB_REF': 'refs/heads/codex/personal', 'GITHUB_SHA': next_commit}):
            self.git('checkout', '--detach', '-q', next_commit)
            self.assertEqual(ci_release.resolve(self.tag), self.expected)
            self.git('checkout', '--detach', '-q', self.commit)
            self.assertEqual(ci_release.checkout(self.tag), self.expected)

    def test_push_commit_mismatch_and_unaccepted_tag_are_refused(self):
        upstream = self.git('rev-parse', 'v0.1.4')
        with mock.patch.dict(os.environ, {'GITHUB_SHA': upstream}), self.assertRaises(release.ReleaseError):
            ci_release.checkout(self.tag)
        self.git('update-ref', 'refs/remotes/origin/codex/personal', upstream)
        with self.assertRaises(subprocess.CalledProcessError):
            ci_release.checkout(self.tag)

    def test_unaccepted_manual_workflow_source_is_refused(self):
        upstream = self.git('rev-parse', 'v0.1.4')
        self.git('checkout', '-qb', 'unaccepted', upstream)
        (self.root / 'unaccepted.txt').write_text('Never merged')
        self.git('add', '.')
        self.git('commit', '-qm', 'Unaccepted source')
        unaccepted = self.git('rev-parse', 'HEAD')
        self.git('checkout', '--detach', '-q', self.commit)
        with mock.patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'workflow_dispatch',
                                         'GITHUB_REF': 'refs/heads/codex/personal', 'GITHUB_SHA': unaccepted}):
            with self.assertRaises(subprocess.CalledProcessError):
                ci_release.checkout(self.tag)

    def test_dirty_checkout_and_mismatched_local_personal_ref_are_refused(self):
        self.notes.write_text('Uncommitted notes')
        with self.assertRaisesRegex(release.ReleaseError, 'clean accepted commit'):
            ci_release.checkout(self.tag)
        self.git('checkout', '--', str(self.notes.relative_to(self.root)))
        self.git('branch', '-f', 'codex/personal', 'v0.1.4')
        with self.assertRaisesRegex(release.ReleaseError, 'fetched accepted mainline'):
            ci_release.checkout(self.tag)

    def test_lightweight_nested_and_wrong_commit_tags_are_refused(self):
        for kind in ('lightweight', 'nested', 'wrong-commit'):
            with self.subTest(kind=kind):
                self.git('tag', '-d', self.tag)
                if kind == 'lightweight':
                    self.git('tag', self.tag, self.commit)
                elif kind == 'nested':
                    self.git('tag', '-a', 'inner-fixture', self.commit, '-m', 'Nested fixture')
                    self.git('tag', '-a', self.tag, 'inner-fixture', '-m', 'Nested fixture')
                else:
                    self.git('tag', '-a', self.tag, 'v0.1.4', '-m', 'Wrong commit')
                with self.assertRaises(release.ReleaseError):
                    ci_release.checkout(self.tag)

    def test_missing_empty_notes_and_version_mismatch_are_refused(self):
        for content in ('', None):
            with self.subTest(content=content):
                if content is None: self.notes.unlink()
                else: self.notes.write_text(content)
                # Notes policy is checked independently after the existing clean-provenance guard.
                with mock.patch.object(release, 'release_provenance', return_value=(self.commit, self.tag_object)):
                    with self.assertRaisesRegex(release.ReleaseError, 'nonempty release notes'):
                        ci_release.checkout(self.tag)
        with mock.patch.object(release, 'config', return_value={'version': '1.2.4'}):
            with self.assertRaisesRegex(release.ReleaseError, 'release configuration'):
                ci_release.checkout(self.tag)

    def test_remote_existing_release_blocks_check_and_writes_no_outputs(self):
        output = self.root / '.local-dev/output'
        responses = [{'object': {'type': 'tag', 'sha': self.tag_object}},
                     {'object': {'type': 'commit', 'sha': self.commit}}, [{'tag_name': self.tag}]]
        with mock.patch.object(sys, 'argv', ['ci_release.py', 'check', '--tag', self.tag,
                                           '--commit', self.commit, '--tag-object', self.tag_object]), \
             mock.patch.dict(os.environ, {'GITHUB_OUTPUT': str(output)}), \
             mock.patch.object(publish, 'github', side_effect=responses), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                ci_release.main()
        self.assertFalse(output.exists())

    def test_verified_bundle_must_match_independent_build_provenance_and_digest(self):
        with mock.patch.object(publish, 'verify_bundle', return_value=self.metadata):
            self.assertEqual(self.verify(), self.metadata)
            for changes in ({'commit': 'a' * 40}, {'tag_object': 'b' * 40}, {'archive_sha256': 'e' * 64}):
                with self.subTest(changes=changes), self.assertRaises(release.ReleaseError):
                    self.verify(**changes)
        for changes in ({'archive': self.archive.replace('arm64', 'x86_64')},
                        {'archive': self.archive.replace('.dmg', '.zip')}, {'commit': 'a' * 40}):
            with mock.patch.object(publish, 'verify_bundle', return_value=dict(self.metadata, **changes)):
                with self.assertRaises(release.ReleaseError):
                    self.verify()

    def test_self_consistent_artifact_cannot_replace_committed_release_notes(self):
        (self.bundle / 'RELEASE.md').write_text('Changed artifact notes\n')
        metadata = copy.deepcopy(self.metadata)
        metadata['files']['RELEASE.md'] = release.sha256(self.bundle / 'RELEASE.md')
        with mock.patch.object(publish, 'verify_bundle', return_value=metadata):
            with self.assertRaisesRegex(release.ReleaseError, 'committed tagged source'):
                self.verify()

    def test_draft_cli_requires_ack_and_defaults_to_plan(self):
        args = ['ci_release.py', 'draft', '--bundle', str(self.root / 'dist/assets'), '--tag', self.tag,
                '--commit', self.commit, '--tag-object', self.tag_object, '--archive-sha256', 'd' * 64]
        with mock.patch.object(ci_release, 'verify_bundle', return_value=self.metadata) as verify, \
             mock.patch.object(publish, 'create_draft', return_value={'published': False}) as draft, \
             mock.patch.object(ci_release, 'check_uploaded_draft', return_value='verified draft URL') as remote_verify:
            with mock.patch.object(sys, 'argv', args), contextlib.redirect_stdout(io.StringIO()) as output:
                ci_release.main()
                self.assertEqual(json.loads(output.getvalue())['mode'], 'plan-only')
                draft.assert_not_called()
                remote_verify.assert_not_called()
            verify.reset_mock()
            with mock.patch.object(sys, 'argv', args + ['--execute']), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit): ci_release.main()
                verify.assert_not_called()
                draft.assert_not_called()
                remote_verify.assert_not_called()
            with mock.patch.object(sys, 'argv', args + ['--execute', '--ack-upload']), contextlib.redirect_stdout(io.StringIO()):
                ci_release.main()
                draft.assert_called_once_with(self.root / 'dist/assets', expected_metadata=self.metadata)
                remote_verify.assert_called_once_with(self.metadata)

    def uploaded_draft(self):
        return {'id': 991, 'tag_name': self.tag, 'draft': True, 'prerelease': False, 'body': 'Fixture release notes.\n',
                'html_url': 'https://github.com/EricGao-cn/Toccata/releases/tag/untagged-fixture',
                'assets': [{'name': name, 'state': 'uploaded', 'digest': 'sha256:' + digest}
                           for name, digest in self.metadata['files'].items() if name != 'RELEASE.md']}

    def test_remote_draft_readback_requires_all_four_matching_assets_and_notes(self):
        draft = self.uploaded_draft()
        responses = [[{'id': 991, 'tag_name': self.tag}], draft,
                     {'object': {'type': 'tag', 'sha': self.tag_object}},
                     {'object': {'type': 'commit', 'sha': self.commit}}]
        with mock.patch.object(publish, 'github', side_effect=responses) as github:
            self.assertEqual(ci_release.check_uploaded_draft(self.metadata), draft['html_url'])
            self.assertEqual(github.call_args_list[:2], [
                mock.call('repos/EricGao-cn/Toccata/releases?per_page=100&page=1'),
                mock.call('repos/EricGao-cn/Toccata/releases/991')])
        invalid = [dict(draft, draft=False), dict(draft, prerelease=True), dict(draft, tag_name='v1.2.3'),
                   dict(draft, assets=draft['assets'][:-1]), dict(draft, body='Edited remotely'),
                   dict(draft, html_url='https://example.invalid/'), dict(draft, assets=[None] * 4),
                   dict(draft, id=992), dict(draft, published_at='2026-11-06'), []]
        for field, value in [('digest', 'sha256:' + '0' * 64), ('state', 'new'), ('name', 'extra.zip'), ('name', [])]:
            changed = copy.deepcopy(draft)
            changed['assets'][0][field] = value
            invalid.append(changed)
        for value in invalid:
            with self.subTest(value=value), mock.patch.object(publish, 'github', side_effect=[[{'id': 991, 'tag_name': self.tag}], value]):
                with self.assertRaisesRegex(release.ReleaseError, 'inspect the draft'):
                    ci_release.check_uploaded_draft(self.metadata)

    def test_draft_lookup_is_paginated_and_uses_numeric_id_not_published_tag_endpoint(self):
        responses = [[{'id': 1, 'tag_name': 'unrelated'}] * 100, [{'id': 991, 'tag_name': self.tag}],
                     self.uploaded_draft(), {'object': {'type': 'tag', 'sha': self.tag_object}},
                     {'object': {'type': 'commit', 'sha': self.commit}}]
        with mock.patch.object(publish, 'github', side_effect=responses) as github:
            ci_release.check_uploaded_draft(self.metadata)
            self.assertEqual(github.call_args_list[1], mock.call('repos/EricGao-cn/Toccata/releases?per_page=100&page=2'))
            self.assertFalse(any('/releases/tags/' in call.args[0] for call in github.call_args_list))

    def test_missing_ambiguous_or_invalid_draft_id_never_selects_a_release(self):
        for matches in ([], [{'tag_name': self.tag}], [{'tag_name': self.tag, 'id': True}],
                        [{'tag_name': self.tag, 'id': '991'}], [{'tag_name': self.tag, 'id': -1}],
                        [{'tag_name': self.tag, 'id': 991}, {'tag_name': self.tag, 'id': 992}]):
            with self.subTest(matches=matches), mock.patch.object(publish, 'github', return_value=matches) as network:
                with self.assertRaisesRegex(release.ReleaseError, 'identify one uploaded draft'):
                    ci_release.check_uploaded_draft(self.metadata)
                network.assert_called_once()

    def test_moved_remote_tag_during_upload_is_detected_without_mutation(self):
        responses = [[{'id': 991, 'tag_name': self.tag}], self.uploaded_draft(),
                     {'object': {'type': 'tag', 'sha': 'c' * 40}}]
        with mock.patch.object(publish, 'github', side_effect=responses) as network:
            with self.assertRaisesRegex(release.ReleaseError, 'remote tag does not match'):
                ci_release.check_uploaded_draft(self.metadata)
            self.assertEqual(network.call_count, 3)

    def test_failed_readback_after_upload_never_retries_deletes_or_publishes(self):
        args = ['ci_release.py', 'draft', '--bundle', str(self.root / 'dist/assets'), '--tag', self.tag,
                '--commit', self.commit, '--tag-object', self.tag_object, '--archive-sha256', 'd' * 64,
                '--execute', '--ack-upload']
        with mock.patch.object(sys, 'argv', args), \
             mock.patch.object(ci_release, 'verify_bundle', return_value=self.metadata), \
             mock.patch.object(publish, 'create_draft', return_value={'published': False}) as create, \
             mock.patch.object(publish, 'github', side_effect=subprocess.TimeoutExpired(['gh', 'api'], 30)) as network, \
             contextlib.redirect_stderr(io.StringIO()) as output:
            with self.assertRaises(SystemExit):
                ci_release.main()
            create.assert_called_once()
            network.assert_called_once()
            self.assertIn('A draft may exist', output.getvalue())


if __name__ == '__main__':
    unittest.main()
