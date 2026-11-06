"""Rehearse development-CI triggers, read-only boundaries and push-range checks locally."""
import fnmatch
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('ruby'), 'Workflow policy checks use the bundled Ruby YAML parser')
class PersonalDevelopmentCITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parsed = subprocess.check_output(['ruby', '-r', 'yaml', '-r', 'json', '-e',
            'puts JSON.generate(YAML.safe_load(File.read(ARGV[0])))',
            str(ROOT / '.github/workflows/personal-ci.yml')], text=True)
        cls.workflow = json.loads(parsed)
        cls.job = cls.workflow['jobs']['checks']
        cls.steps = cls.job['steps']

    def test_only_personal_branch_pushes_are_enabled(self):
        events = self.workflow.get('on', self.workflow.get('true'))
        self.assertEqual(set(events), {'push'})
        self.assertEqual(set(events['push']), {'branches'})
        branches = events['push']['branches']
        self.assertEqual(set(branches), {'codex/feat/**', 'codex/sync/**', 'codex/personal'})
        allowed = ['codex/feat/search-notes', 'codex/feat/notes/search', 'codex/sync/v0.1.5', 'codex/personal']
        denied = ['main', 'feature/search', 'codex/feat-other/a', 'codex/personal/other',
                  'codex/random', 'personal-v1.2.0', 'refs/tags/personal-v1.2.0']
        for ref in allowed + denied:
            self.assertEqual(any(fnmatch.fnmatchcase(ref, pattern) for pattern in branches), ref in allowed, ref)
        guard = self.job['if']
        for required in ("github.repository == 'EricGao-cn/Toccata'", "github.event_name == 'push'",
                         'github.event.deleted == false', "github.ref == 'refs/heads/codex/personal'",
                         "startsWith(github.ref, 'refs/heads/codex/feat/')",
                         "startsWith(github.ref, 'refs/heads/codex/sync/')"):
            self.assertIn(required, guard)

    def test_only_read_permission_and_no_credentials_are_passed_to_test_commands(self):
        self.assertEqual(self.workflow['permissions'], {'contents': 'read'})
        self.assertNotIn('permissions', self.job)
        self.assertNotIn('secrets', json.dumps(self.workflow))
        self.assertNotIn('github.token', json.dumps(self.workflow))
        self.assertNotIn('GH_TOKEN', json.dumps(self.workflow))
        actions = [step for step in self.steps if 'uses' in step]
        self.assertEqual(len(actions), 1)
        self.assertRegex(actions[0]['uses'], r'^actions/checkout@[0-9a-f]{40}$')
        checkout = actions[0]['with']
        self.assertEqual(checkout['ref'], '${{ github.sha }}')
        self.assertIs(checkout['persist-credentials'], False)
        self.assertEqual(checkout['fetch-depth'], 0)

    def test_no_installer_publication_or_artifact_upload_entry_point(self):
        self.assertEqual(set(self.workflow['jobs']), {'checks'})
        commands = '\n'.join(step.get('run', '') for step in self.steps)
        for forbidden in ('release.py', 'publish.py', 'ci_release.py', 'maintenance.py', 'package-dmg',
                          'build-release', 'build-candidate', 'gh ', 'git push', 'git tag', 'codesign',
                          './scripts/personal/dev build', './scripts/personal/dev run', './scripts/personal/dev core'):
            self.assertNotIn(forbidden, commands)
        self.assertNotIn('outputs', self.job)
        for scope in (self.workflow, self.job, *self.steps):
            self.assertNotIn('environment', scope)
            self.assertNotIn('continue-on-error', scope)
        self.assertTrue(all(not step.get('uses', '').startswith(('actions/upload-artifact@', 'actions/download-artifact@'))
                            for step in self.steps))

    def test_only_latest_run_for_same_branch_is_kept_without_cancelling_release_jobs(self):
        group = self.workflow['concurrency']
        self.assertEqual(group['group'], 'personal-ci-${{ github.ref }}')
        self.assertIs(group['cancel-in-progress'], True)
        first = group['group'].replace('${{ github.ref }}', 'refs/heads/codex/feat/a')
        other = group['group'].replace('${{ github.ref }}', 'refs/heads/codex/feat/b')
        self.assertNotEqual(first, other)
        self.assertFalse(first.startswith('personal-release-'))

    def test_isolated_toolchain_and_separate_swift_distribution_policies(self):
        self.assertEqual(self.job['runs-on'], 'macos-26')
        self.assertEqual(self.job['env'], {'DEVELOPER_DIR': '/Applications/Xcode_26.2.app/Contents/Developer'})
        commands = '\n'.join(step.get('run', '') for step in self.steps)
        self.assertIn('dev init --state-root "$RUNNER_TEMP/toccata-ci" --tools-root "$RUNNER_TEMP/toccata-tools"', commands)
        for required in ('dev setup-rust', 'dev check', 'dev fetch', 'dev test-scripts',
                         'dev test-core --features personal-distribution'):
            self.assertIn(required, commands)
        self.assertNotIn('Application Support/Toccata-Personal', commands)
        self.assertNotIn('~/Applications', commands)
        swift = [step for step in self.steps if 'dev test-swift' in step.get('run', '')]
        self.assertEqual(len(swift), 2)
        upstream = next(step for step in swift if '-DTOCCATA_PERSONAL' not in step['run'])
        personal = next(step for step in swift if '-DTOCCATA_PERSONAL' in step['run'])
        self.assertIn('--skip MarkdownWebEditorTests', upstream['run'])
        self.assertNotIn('--filter', upstream['run'])
        self.assertIn("--filter 'PersonalDistributionTests|PersonalReleaseUpdateTests'", personal['run'])
        for step in self.steps:
            if 'dev test-' in step.get('run', ''):
                self.assertGreater(step['timeout-minutes'], 0)
                self.assertLessEqual(step['timeout-minutes'], 15)
        self.assertGreater(self.job['timeout-minutes'], 0)
        self.assertLessEqual(self.job['timeout-minutes'], 45)

    def test_canonical_resources_and_clean_worktree_are_required(self):
        resource = next(step['run'] for step in self.steps if './scripts/sync-assets.sh' in step.get('run', ''))
        self.assertIn('git diff --exit-code', resource)
        final = self.steps[-1]['run']
        for required in ('git diff --check', 'git diff --exit-code', 'git ls-files --others --exclude-standard'):
            self.assertIn(required, final)
        commands = '\n'.join(step.get('run', '') for step in self.steps)
        self.assertNotIn('git diff --quiet ||', commands)
        self.assertNotIn('git reset', commands)

    def git_fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix='toccata-ci-push-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(root), *args], text=True, stderr=subprocess.PIPE).strip()
        git('init', '-q')
        git('config', 'user.name', 'Fixture')
        git('config', 'user.email', 'fixture@example.invalid')
        (root / 'source.txt').write_text('accepted\n')
        git('add', '.')
        git('commit', '-qm', 'Accepted fixture')
        accepted = git('rev-parse', 'HEAD')
        git('update-ref', 'refs/remotes/origin/codex/personal', accepted)
        return root, git, accepted

    def check_changes(self, root, before):
        step = next(step for step in self.steps if step.get('id') == 'changes')
        self.assertEqual(step['env'], {'BEFORE_COMMIT': '${{ github.event.before }}'})
        self.assertNotIn('${{', step['run'])
        return subprocess.run(['bash', '--noprofile', '--norc', '-e', '-o', 'pipefail', '-c', step['run']],
            cwd=root, env=dict(os.environ, BEFORE_COMMIT=before), text=True, capture_output=True)

    def test_range_check_catches_whitespace_from_earlier_commit_in_same_push(self):
        root, git, accepted = self.git_fixture()
        (root / 'source.txt').write_text('bad trailing space \n')
        git('add', '.'); git('commit', '-qm', 'Earlier bad commit')
        (root / 'other.txt').write_text('clean later change\n')
        git('add', '.'); git('commit', '-qm', 'Later clean commit')
        result = self.check_changes(root, accepted)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('trailing whitespace', result.stdout)

    def test_new_and_rebased_branches_check_changes_against_personal_mainline(self):
        root, git, accepted = self.git_fixture()
        (root / 'source.txt').write_text('new clean change\n')
        git('add', '.'); git('commit', '-qm', 'New feature')
        for before in ('0' * 40, 'f' * 40):
            with self.subTest(before=before):
                self.assertEqual(self.check_changes(root, before).returncode, 0)
        (root / 'source.txt').write_text('new bad change \n')
        git('add', '.'); git('commit', '-qm', 'Bad feature')
        for before in ('0' * 40, 'f' * 40):
            with self.subTest(before=before):
                self.assertNotEqual(self.check_changes(root, before).returncode, 0)

    def test_untrusted_before_value_cannot_execute_shell_code(self):
        root, git, accepted = self.git_fixture()
        marker = root / 'injected'
        result = self.check_changes(root, '$(touch ' + str(marker) + ')')
        self.assertEqual(result.returncode, 0)
        self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
