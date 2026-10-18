"""Exercise identifier fidelity, audit failures, and owned-server cleanup."""
import csv
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/revelio_llm.py'
spec = importlib.util.spec_from_file_location('revelio_llm', SCRIPT)
llm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(llm)

try:
    from kellogg_llm_batch.core import prepare_run
except ImportError:
    prepare_run = None

FAKE_SERVER = '''
import json, os
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({'version': 'test', 'pid': os.getpid()}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass
host, port = os.environ['OLLAMA_HOST'].split(':')
HTTPServer((host, int(port)), Handler).serve_forever()
'''


def records():
    return [
        {'job_id': '12345678901234567890123456789012', 'title_raw': 'Engineer',
         'description': 'Python, "SQL"\nRésumé 第二行', 'company': 'LOCAL_COMPANY_ONLY'},
        {'job_id': '00042', 'jobtitle_translated': 'Analyst',
         'description': 'Excel and a bachelor degree'},
    ]


class InputTests(unittest.TestCase):
    def test_lossless_archive_and_package_input(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'project'
            llm.save_project(records(), destination, {'sql': 'SELECT test'})
            archive = [json.loads(line) for line in (destination / 'input.jsonl').read_text().splitlines()]
            with (destination / 'input.csv').open(newline='', encoding='utf-8') as stream:
                actual = list(csv.DictReader(stream))
            for index, original in enumerate(records()):
                for field in ('job_id', 'description'):
                    self.assertEqual(actual[index][field], original[field])
                    self.assertEqual(archive[index][field], original[field])
            with self.assertRaises(FileExistsError):
                llm.save_project(records(), destination, {})

    def test_bad_inputs_leave_no_project(self):
        bad = [[], [records()[0]] * 2,
               [{'job_id': 42, 'description': 'Text'}],
               [{'job_id': ' 42', 'description': 'Text'}],
               [{'job_id': '42', 'description': ' \t\n'}]]
        for value in bad:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'project'
                with self.assertRaises(ValueError):
                    llm.save_project(value, destination, {})
                self.assertFalse(destination.exists())

    def test_limits_and_slurm_guard(self):
        for limit in (0, -1, 21):
            with self.assertRaisesRegex(ValueError, '--limit'):
                llm.extract(limit)
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, 'sbatch'):
            llm.run(Path('/does/not/exist'))

    def test_incomplete_or_wrong_size_audit_fails(self):
        llm.check_audit({'complete': True, 'expected_records': 4, 'valid_records': 4}, 4)
        for report in ({'complete': False, 'expected_records': 4, 'valid_records': 3},
                       {'complete': True, 'expected_records': 3, 'valid_records': 3}):
            with self.assertRaisesRegex(ValueError, 'Pilot incomplete'):
                llm.check_audit(report, 4)

    @unittest.skipIf(prepare_run is None, 'Install kellogg-llm-batch for real preparation checks')
    def test_real_package_preserves_ids_and_excludes_metadata_from_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            project = llm.save_project(records(), Path(folder) / 'project', {})
            run_dir = prepare_run(project / 'project.yaml', 'openai_compatible',
                                  sample_size=2, seed=42, execution='sync')
            requests = [json.loads(line) for path in (run_dir / 'api_requests').glob('*.jsonl')
                        for line in path.read_text().splitlines()]
            sent_ids = []
            for request in requests:
                text = request['body']['messages'][1]['content']
                # The input placeholder is a JSON array at the end of this prompt.
                sent = json.loads(text[text.index('['):])
                sent_ids.extend(record['record_id'] for record in sent)
                self.assertNotIn('LOCAL_COMPANY_ONLY', text)
                self.assertNotIn('company', sent[0])
            self.assertCountEqual(sent_ids, [row['job_id'] for row in records()])


class CleanupTests(unittest.TestCase):
    def test_server_stops_after_success_and_exception(self):
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as folder:
                pid = None
                old_handler = signal.getsignal(signal.SIGTERM)
                try:
                    with llm.ollama_server(Path(folder), Path(folder),
                            command=[sys.executable, '-c', FAKE_SERVER], startup_timeout=5) as url:
                        pid = llm.api(url, '/api/version')['pid']
                        if fail:
                            raise RuntimeError('simulated request failure')
                except RuntimeError:
                    if not fail:
                        raise
                self.assertIsNotNone(pid)
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)
                self.assertEqual(signal.getsignal(signal.SIGTERM), old_handler)

    def test_early_server_exit_is_actionable(self):
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(RuntimeError, 'ollama.log'):
            with llm.ollama_server(Path(folder), Path(folder),
                                  command=[sys.executable, '-c', 'raise SystemExit(7)'], startup_timeout=2):
                self.fail('A dead server must not be ready')

    def test_sigterm_stops_owned_server(self):
        with tempfile.TemporaryDirectory() as folder:
            ready = Path(folder) / 'ready.json'
            worker_code = f'''
import json, pathlib, sys, time
sys.path.insert(0, {str(SCRIPT.parent)!r})
import revelio_llm as llm
directory = pathlib.Path({folder!r})
with llm.ollama_server(directory, directory, command=[sys.executable, '-c', {FAKE_SERVER!r}]) as url:
    (directory / 'ready.json').write_text(json.dumps(llm.api(url, '/api/version')))
    time.sleep(30)
'''
            worker = subprocess.Popen([sys.executable, '-c', worker_code],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 8
                while not ready.exists() and worker.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(ready.exists(), 'Worker did not become ready')
                server_pid = json.loads(ready.read_text())['pid']
                worker.send_signal(signal.SIGTERM)
                _, error = worker.communicate(timeout=15)
                self.assertEqual(worker.returncode, 143, error.decode())
                with self.assertRaises(ProcessLookupError):
                    os.kill(server_pid, 0)
            finally:
                if worker.poll() is None:
                    worker.kill()
                worker.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
