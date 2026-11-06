"""Check release workflow boundaries and failed-job artifact bindings without GitHub."""
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
class PersonalWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parsed = subprocess.check_output(['ruby', '-r', 'yaml', '-r', 'json', '-e',
            'puts JSON.generate(YAML.safe_load(File.read(ARGV[0])))',
            str(ROOT / '.github/workflows/personal-release.yml')], text=True)
        cls.workflow = json.loads(parsed)
        cls.build = cls.workflow['jobs']['build']
        cls.draft = cls.workflow['jobs']['draft']

    def test_only_personal_tag_pushes_and_personal_branch_manual_runs_can_release(self):
        # Ruby YAML 1.1 parses the unquoted Actions key "on" as boolean true.
        events = self.workflow.get('on', self.workflow.get('true'))
        self.assertEqual(set(events), {'push', 'workflow_dispatch'})
        self.assertEqual(events['push'], {'tags': ['personal-v*']})
        self.assertEqual(set(events['workflow_dispatch']['inputs']), {'tag'})
        self.assertIn("github.repository == 'EricGao-cn/Toccata'", self.build['if'])
        self.assertIn("github.ref == 'refs/heads/codex/personal'", self.build['if'])
        self.assertEqual(self.draft['needs'], 'build')
        self.assertNotIn('if', self.draft)  # No always() path after a failed build.
        self.assertIs(self.workflow['concurrency']['cancel-in-progress'], False)

    def test_build_is_readonly_and_draft_only_adds_required_release_and_artifact_access(self):
        self.assertEqual(self.workflow['permissions'], {'contents': 'read'})
        self.assertNotIn('permissions', self.build)
        self.assertEqual(self.draft['permissions'], {'contents': 'write', 'actions': 'read'})
        for scope in (self.workflow, self.build, self.draft):
            self.assertNotIn('GH_TOKEN', scope.get('env', {}))
        for job in (self.build, self.draft):
            for step in job['steps']:
                if 'uses' in step:
                    self.assertRegex(step['uses'], r'^actions/[a-z-]+@[0-9a-f]{40}$')
                if step.get('uses', '').startswith('actions/checkout@'):
                    self.assertIs(step['with']['persist-credentials'], False)
        for step in self.build['steps']:
            if 'dev test-' in step.get('run', '') or 'build-release' in step.get('run', ''):
                self.assertNotIn('GH_TOKEN', step.get('env', {}))
        final = self.draft['steps'][-1]['run']
        self.assertIn('ci_release.py draft', final)
        self.assertIn('--execute --ack-upload', final)
        for forbidden in ('--publish', 'release edit', 'release upload', '--clobber'):
            self.assertNotIn(forbidden, final)

    def test_tag_code_runs_only_after_accepted_mainline_resolution(self):
        steps = self.build['steps']
        self.assertEqual(steps[0]['with']['ref'], 'codex/personal')
        source = next(i for i, step in enumerate(steps) if step.get('id') == 'source')
        self.assertIn('ci_release.py resolve', steps[source]['run'])
        checkout = next(i for i, step in enumerate(steps) if step.get('with', {}).get('ref') == '${{ steps.source.outputs.commit }}')
        self.assertLess(source, checkout)
        checked = next(i for i, step in enumerate(steps) if 'ci_release.py check' in step.get('run', ''))
        self.assertLess(checkout, checked)
        self.assertIn('--tag-object "$TAG_OBJECT"', steps[checked]['run'])

    def test_upstream_installer_tests_and_personal_guards_use_separate_compilations(self):
        swift = [step for step in self.build['steps'] if 'dev test-swift' in step.get('run', '')]
        self.assertEqual(len(swift), 2)
        upstream = next(step for step in swift if '-DTOCCATA_PERSONAL' not in step['run'])
        personal = next(step for step in swift if '-DTOCCATA_PERSONAL' in step['run'])
        self.assertIn('--skip MarkdownWebEditorTests', upstream['run'])
        self.assertNotIn('--filter', upstream['run'])
        self.assertIn("--filter 'PersonalDistributionTests|PersonalReleaseUpdateTests'", personal['run'])
        for step in swift:
            self.assertGreater(step['timeout-minutes'], 0)
            self.assertLessEqual(step['timeout-minutes'], 15)

    def test_failed_job_reruns_keep_original_artifact_id_and_workflow_run(self):
        download = next(step['with'] for step in self.draft['steps']
                        if step.get('uses', '').startswith('actions/download-artifact@'))
        self.assertNotIn('name', download)
        self.assertNotIn('pattern', download)
        self.assertIs(download['merge-multiple'], True)
        bound = []
        for attempt in (1, 2):
            contexts = {'github': {'run_id': '1001', 'run_attempt': str(attempt),
                                   'repository': 'EricGao-cn/Toccata', 'token': 'fixture-token'},
                        'needs': {'build': {'outputs': {'artifact_id': '2002'}}}}
            def evaluate(value):
                if not isinstance(value, str): return value
                match = re.fullmatch(r'\$\{\{\s*([\w.]+)\s*\}\}', value)
                if not match: return value
                result = contexts
                for key in match.group(1).split('.'): result = result[key]
                return result
            bound.append({key: evaluate(value) for key, value in download.items()})
        self.assertEqual(bound[0], bound[1])
        self.assertEqual(bound[1]['artifact-ids'], '2002')
        self.assertEqual(bound[1]['run-id'], '1001')
        self.assertEqual(bound[1]['repository'], 'EricGao-cn/Toccata')
        self.assertEqual(bound[1]['github-token'], 'fixture-token')

    def test_invalid_artifact_ids_stop_before_checkout_or_download(self):
        guard = self.draft['steps'][0]['run']
        self.assertEqual(self.workflow['defaults']['run']['shell'], 'bash')
        with tempfile.TemporaryDirectory(prefix='toccata-artifact-id-') as temporary:
            marker = Path(temporary) / 'injected'
            for value in ('2002', '', '0', '-1', '1,2', 'all', '2002\n', '$(touch ' + str(marker) + ')'):
                result = subprocess.run(['bash', '-c', guard], env=dict(os.environ, ARTIFACT_ID=value))
                self.assertEqual(result.returncode == 0, value == '2002', value)
            self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
