"""Check memory budgets, act compatibility and the bounded runner-retry policy."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_resources
import prepare_act


class ResourceTests(unittest.TestCase):
    def test_reserves_ram_and_limits_parallelism(self):
        self.assertEqual(build_resources.build_jobs(4, 14 * build_resources.GIB), 3)
        self.assertEqual(build_resources.build_jobs(2, 64 * build_resources.GIB), 2)
        self.assertEqual(build_resources.build_jobs(4, 2 * build_resources.GIB), 1)

    def test_respects_container_memory_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'meminfo').write_text('MemAvailable: 16777216 kB\nSwapFree: 4194304 kB\n')
            (root / 'memory.max').write_text(str(8 * build_resources.GIB))
            (root / 'memory.current').write_text(str(2 * build_resources.GIB))
            info = build_resources.memory_info(root, root)
            self.assertEqual(info['available'], 6 * build_resources.GIB)
            self.assertEqual(info['swap_free'], 4 * build_resources.GIB)

    def test_unlimited_cgroup_keeps_host_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'meminfo').write_text('MemAvailable: 1048576 kB\n')
            (root / 'memory.max').write_text('max')
            (root / 'memory.current').write_text('100')
            self.assertEqual(build_resources.memory_info(root, root)['available'], build_resources.GIB)

    def test_respects_cpu_quota_instead_of_host_cpu_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'cpu.max').write_text('250000 100000')
            with patch.object(build_resources.os, 'sched_getaffinity', return_value=set(range(16))):
                self.assertEqual(build_resources.cpu_count(root), 2)
            (root / 'cpu.max').write_text('max 100000')
            with patch.object(build_resources.os, 'sched_getaffinity', return_value={0, 1}):
                self.assertEqual(build_resources.cpu_count(root), 2)

    def test_monitor_records_a_sample_and_can_be_stopped(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'resources.log'
            with subprocess.Popen([sys.executable, str(ROOT / 'scripts/build_resources.py'),
                                   'monitor', '--directory', directory, '--output', str(log)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as monitor:
                try:
                    monitor.communicate(timeout=1)
                    self.fail('Monitor exited before it could be stopped')
                except subprocess.TimeoutExpired:
                    monitor.terminate()
                    stdout, stderr = monitor.communicate(timeout=5)
                self.assertIn('Build resources:', stdout, stderr)
                sample = json.loads(log.read_text().splitlines()[0])
                self.assertGreater(sample['disk_free'], 0)
                self.assertIn('available', sample)


class ActTests(unittest.TestCase):
    def test_local_copy_changes_only_artifact_runtime_versions(self):
        cloud = (ROOT / '.github/workflows/immortalwrt.yml').read_text()
        local = prepare_act.render(cloud)
        self.assertIn('uses: actions/upload-artifact@v5', local)
        self.assertIn('uses: actions/download-artifact@v6', local)
        restored = local.replace('actions/upload-artifact@v5', 'actions/upload-artifact@v6')
        restored = restored.replace('actions/download-artifact@v6', 'actions/download-artifact@v7')
        self.assertEqual(restored, cloud)


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.case = {
            'run': {'id': 42, 'path': '.github/workflows/immortalwrt.yml',
                    'run_attempt': 1, 'conclusion': 'failure',
                    'head_repository': {'full_name': 'kxhubs/Actions-OpenWrt'}},
            'jobs': [{'id': 100, 'conclusion': 'failure', 'check_run_url': 'https://api.github.com/check-runs/100'}],
            'annotations': {'100': [{'annotation_level': 'failure',
                'message': 'The hosted runner lost communication with the server. More details.'}]},
        }

    def evaluate(self, case):
        workflow = (ROOT / '.github/workflows/retry-runner.yml').read_text()
        script = textwrap.dedent(workflow.split('          script: |\n', 1)[1])
        harness = '''
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const calls = [];
const listJobs = () => {}, listAnnotations = () => {};
const github = {
  rest: {actions: {listJobsForWorkflowRun:listJobs,
    reRunWorkflowFailedJobs: async args => calls.push(args)},
    checks: {listAnnotations}},
  paginate: async (method,args) => method === listJobs ? input.case.jobs : input.case.annotations[args.check_run_id]
};
const core = {info: () => {},summary:{addRaw(){return this},async write(){}}};
const context = {repo:{owner:'kxhubs',repo:'Actions-OpenWrt'},payload:{workflow_run:input.case.run}};
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
new AsyncFunction('github','context','core',input.script)(github,context,core)
  .then(() => process.stdout.write(JSON.stringify(calls)))
  .catch(error => { console.error(error); process.exitCode=1; });
'''
        result = subprocess.run(['node', '-e', harness], input=json.dumps({'script': script, 'case': case}),
                                text=True, capture_output=True, check=True)
        return json.loads(result.stdout)

    def test_retries_lost_runner_once(self):
        calls = self.evaluate(self.case)
        self.assertEqual(calls, [{'owner': 'kxhubs', 'repo': 'Actions-OpenWrt', 'run_id': 42}])

    def test_does_not_retry_a_second_attempt_or_foreign_repository(self):
        second = copy.deepcopy(self.case)
        second['run']['run_attempt'] = 2
        self.assertEqual(self.evaluate(second), [])
        foreign = copy.deepcopy(self.case)
        foreign['run']['head_repository']['full_name'] = 'someone/fork'
        self.assertEqual(self.evaluate(foreign), [])

    def test_compiler_failure_does_not_trigger_infrastructure_retry(self):
        self.case['annotations']['100'][0]['message'] = 'Process completed with exit code 2.'
        self.assertEqual(self.evaluate(self.case), [])

    def test_does_not_retry_when_another_job_has_a_code_failure(self):
        self.case['jobs'].append({'id': 101, 'conclusion': 'failure',
                                 'check_run_url': 'https://api.github.com/check-runs/101'})
        self.case['annotations']['101'] = [{'annotation_level': 'failure', 'message': 'compiler failed'}]
        self.assertEqual(self.evaluate(self.case), [])

    def test_does_not_retry_a_job_with_both_compiler_and_runner_errors(self):
        self.case['annotations']['100'].append({'annotation_level': 'failure', 'message': 'compiler failed'})
        self.assertEqual(self.evaluate(self.case), [])


if __name__ == '__main__':
    unittest.main()
