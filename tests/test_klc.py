"""Offline tests for repeatable setup, quoting, scheduling, and extraction failures."""
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock

PROJECT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, PROJECT / 'tools' / f'{name}.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


local, remote, data = [module(name) for name in ('klc', 'remote', 'wrds_data')]


class FakeConnection:
    def __init__(self):
        self.connection = object()
        self.engine = MagicMock()
        stream = self.engine.connect.return_value.__enter__.return_value
        stream.execution_options.return_value = stream


class Frame:
    empty = False
    def __len__(self):
        return 3
    def to_parquet(self, path, index):
        Path(path).write_bytes(b'fixture')


class ToolkitTests(unittest.TestCase):
    def test_wrds_keepalives_preserve_client_defaults(self):
        defaults = {'sslmode': 'require', 'application_name': 'wrds-test'}
        sql = types.ModuleType('wrds.sql')
        sql.WRDS_CONNECT_ARGS = defaults
        with patch.dict('sys.modules', {'wrds.sql': sql}):
            args = data.connect_args()
        self.assertEqual(args['sslmode'], 'require')
        self.assertEqual(args['application_name'], 'wrds-test')
        self.assertEqual(args['keepalives_idle'], 30)
        self.assertEqual(args['keepalives_interval'], 30)
        self.assertEqual(args['keepalives_count'], 9)
        self.assertEqual(args['keepalives'], 1)
        self.assertEqual(args['connect_timeout'], 30)
        self.assertEqual(defaults, {'sslmode': 'require', 'application_name': 'wrds-test'})

    def test_wrds_connection_passes_options_and_closes_on_failure(self):
        wrds = types.ModuleType('wrds')
        wrds.Connection = MagicMock()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.klc').mkdir()
            (root / '.klc/config.json').write_text(json.dumps({'wrds_username': 'fixture'}))
            (root / '.pgpass').touch()
            with patch.dict('sys.modules', {'wrds': wrds}), patch.object(data, 'ROOT', root), patch.object(data.Path, 'home', return_value=root), patch.object(data, 'connect_args', return_value={'keepalives_idle': 30}):
                with self.assertRaisesRegex(RuntimeError, 'query failed'):
                    with data.connection():
                        raise RuntimeError('query failed')
        wrds.Connection.assert_called_once_with(wrds_username='fixture', wrds_connect_args={'keepalives_idle': 30})
        wrds.Connection.return_value.close.assert_called_once_with()

    def test_missing_config(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(local, 'CONFIG', Path(folder) / 'missing'):
            with self.assertRaisesRegex(ValueError, 'setup'):
                local.load()

    def test_remote_command_quotes_arguments(self):
        payload = '$(touch /tmp/should-not-exist); "quoted"'
        command = local.remote_command(dict(remote_root='/project/space here'), ['run', 'python', payload])
        self.assertIn(shlex.quote(payload), command)
        self.assertIn("cd '/project/space here'", command)
        with patch.object(local.subprocess, 'run') as run:
            local.ssh({'alias': 'klc'}, command)
            self.assertEqual(shlex.split(run.call_args.args[0][-1]), ['bash', '-lc', command])

    def test_setup_repeat_preserves_ssh(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            (home / '.ssh').mkdir()
            ssh = home / '.ssh/config'
            original = 'Host other\n  HostName other.example\nHost *\n  User fallback\n'
            ssh.write_text(original)
            settings = home / 'repo/.klc/config.json'
            answers = ['abc123', '', '/kellogg/proj/abc123', 'wrds_user', '', '', '', '', '']
            result = subprocess.CompletedProcess([], 0, stdout='hostname klc-revelio\n')
            with patch.object(local, 'CONFIG', settings), patch.object(local.Path, 'home', return_value=home), patch('builtins.input', side_effect=answers + [''] * 9), patch.object(local.subprocess, 'check_output', return_value='https://github.com/example/repo\n'), patch.object(local.subprocess, 'run', return_value=result):
                local.setup()
                first = ssh.read_text()
                local.setup()
                self.assertEqual(ssh.read_text(), first)
                self.assertIn(original, first)
                self.assertEqual(first.count('# BEGIN'), 1)
                self.assertEqual(settings.stat().st_mode & 0o777, 0o600)

    def test_ssh_failure_propagates(self):
        with patch.object(local.subprocess, 'run', side_effect=subprocess.CalledProcessError(255, 'ssh')):
            with self.assertRaises(subprocess.CalledProcessError):
                local.ssh({'alias': 'klc'}, 'true')

    def test_reserve_missing_does_not_launch(self):
        with patch.object(remote.shutil, 'which', return_value=None), patch.object(remote.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'Reserve'):
                remote.launch({}, ['python', 'examples/python_smoke.py'], submit=True)
            run.assert_not_called()

    def test_reserve_rejection_does_not_launch(self):
        with patch.object(remote.shutil, 'which', return_value='/bin/sbatch'), patch.object(remote.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'sbatch')) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                remote.launch(dict(slurm_account='bad', slurm_partition='bad'), ['python', 'examples/python_smoke.py'], submit=True)
            self.assertEqual(run.call_count, 1)

    def test_bootstrap_repeat_never_deletes_or_pulls(self):
        c = dict(project='/project/with space', remote_root='/project/with space/revelio_playground',
                 repository='https://github.com/example/repo', alias='klc', python_module='')
        with patch.object(local, 'ssh') as ssh, patch.object(local.subprocess, 'run') as run:
            local.bootstrap(c)
            local.bootstrap(c)
            for call in ssh.call_args_list:
                command = call.args[1]
                self.assertNotIn('git pull', command)
                self.assertNotIn('rm ', command)
            self.assertIn('if test ! -e', ssh.call_args_list[0].args[1])
            self.assertNotIn('--delete', run.call_args.args[0])

    def test_tmux_detached_and_argument_preserved(self):
        payload = 'value; $(touch /tmp/never-run)'
        with tempfile.TemporaryDirectory() as folder, patch.object(remote, 'ROOT', Path(folder).resolve()), patch.object(remote.shutil, 'which', return_value='/bin/tmux'), patch.object(remote.subprocess, 'run') as run:
            script = Path(folder) / 'script.py'
            script.write_text('pass')
            remote.launch({}, ['python', 'script.py', payload])
            command = run.call_args.args[0]
            self.assertEqual(command[:3], ['tmux', 'new-session', '-d'])
            self.assertEqual(shlex.split(command[-1])[:2], ['bash', '-lc'])
            record = json.loads(next(Path(folder).glob('logs/jobs/*/job.json')).read_text())
            self.assertIn(shlex.quote(payload), record['command'])

    def test_streaming_manifest(self):
        class Connection(FakeConnection):
            def raw_sql(inner, sql, **kwargs):
                self.assertTrue(kwargs['return_iter'])
                self.assertEqual(kwargs['chunksize'], 100_000)
                return iter([Frame(), Frame()])
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'extract'
            result = data.extract(Connection(), 'SELECT %(x)s', {'x': 2}, output)
            self.assertEqual(result['status'], 'complete')
            self.assertEqual(result['rows'], 6)
            self.assertEqual(len(list(output.glob('*.parquet'))), 2)
            with self.assertRaises(FileExistsError):
                data.extract(Connection(), 'SELECT 1', {}, output)

    def test_interrupted_extract(self):
        class Connection(FakeConnection):
            def raw_sql(inner, *args, **kwargs):
                yield Frame()
                raise KeyboardInterrupt()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'extract'
            with self.assertRaises(KeyboardInterrupt):
                data.extract(Connection(), 'SELECT 1', {}, output)
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'incomplete')
            self.assertEqual(manifest['rows'], 3)

    def test_streaming_cursor_transaction_and_restore(self):
        conn = FakeConnection()
        original = conn.connection
        conn.raw_sql = MagicMock(return_value=iter([]))
        with data.streaming(conn, 'SELECT 1', {}, 10):
            self.assertIsNot(conn.connection, original)
        self.assertIs(conn.connection, original)
        stream = conn.engine.connect.return_value.__enter__.return_value
        stream.execution_options.assert_called_once_with(isolation_level='READ COMMITTED', stream_results=True, max_row_buffer=10)
        stream.begin.assert_called_once()

    def test_stata_log_error_overrides_exit_zero(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(remote, 'ROOT', Path(folder)):
            directory = Path(folder) / 'logs/jobs/test'
            directory.mkdir(parents=True)
            remote.save(directory / 'job.json', dict(language='stata', command='true'))
            (directory / 'stata.log').write_text('failure\nr(198);\n')
            self.assertEqual(remote.execute('test'), 1)
            self.assertEqual(json.loads((directory / 'job.json').read_text())['status'], 'failed')

    def test_credentials_preserve_entries_and_escape(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(remote.Path, 'home', return_value=Path(folder)), patch.object(remote.getpass, 'getpass', return_value='test:pass\\word'):
            path = Path(folder) / '.pgpass'
            path.write_text('other:5432:db:user:secret\n')
            remote.credentials({'wrds_username': 'test'})
            self.assertIn('other:5432:db:user:secret', path.read_text())
            self.assertIn('test\\:pass\\\\word', path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
