"""Verify additive distinct counts, checkpoint recovery, and batch boundaries."""
from contextlib import contextmanager, redirect_stdout
from decimal import Decimal
import fcntl
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import country_coverage_batches as batches
from country_coverage import coverage_sql, summarize

try:
    import duckdb
except ImportError:
    duckdb = None

try:
    from sqlalchemy.exc import OperationalError
except ImportError:
    OperationalError = None


@unittest.skipIf(OperationalError is None, 'Install sqlalchemy for connection tests')
class ConnectionTests(unittest.TestCase):
    def test_transport_failure_reconnects_and_restores_connections(self):
        first, second = MagicMock(), MagicMock()
        first.raw_sql.side_effect = OperationalError('query', {}, RuntimeError('connection timed out'))
        second.raw_sql.return_value.to_dict.return_value = [{'connected': 1}]
        originals = [first.connection, second.connection]
        opened, closed = [], []

        @contextmanager
        def connect():
            conn = [first, second][len(opened)]
            opened.append(conn)
            try:
                yield conn
            finally:
                closed.append(conn)

        with patch.object(batches, 'connection', connect), patch.object(batches.time, 'sleep'), redirect_stdout(io.StringIO()):
            with batches.queries(30) as query:
                self.assertEqual(query('SELECT 1', {'x': 1}), [{'connected': 1}])
        self.assertEqual(opened, [first, second])
        self.assertEqual(closed, [first, second])
        self.assertIs(first.connection, originals[0])
        self.assertIs(second.connection, originals[1])
        first.raw_sql.assert_called_once_with('SELECT 1', params={'x': 1})
        second.raw_sql.assert_called_once_with('SELECT 1', params={'x': 1})

    def test_statement_timeout_is_not_retried(self):
        conn = MagicMock()
        conn.raw_sql.side_effect = OperationalError('query', {}, SimpleNamespace(pgcode='57014'))
        with patch.object(batches, 'connection') as connect:
            connect.return_value.__enter__.return_value = conn
            with batches.queries(30) as query, self.assertRaises(OperationalError):
                query('SELECT 1')
        connect.assert_called_once_with()
        conn.raw_sql.assert_called_once()


@unittest.skipIf(duckdb is None, 'Install duckdb for batch integration tests')
class BatchTests(unittest.TestCase):
    def setUp(self):
        self.db = duckdb.connect()
        self.db.execute('CREATE TABLE positions(country VARCHAR, user_id DECIMAL(38,1))')
        self.folder = tempfile.TemporaryDirectory()
        self.args = SimpleNamespace(schema='main', table='positions', country_column='country',
                                    person_column='user_id', batches=True, batch_size=2,
                                    query_timeout=30, resume=None)
        self.calls = []
        self.fail_at = None

    def tearDown(self):
        self.db.close()
        self.folder.cleanup()

    @contextmanager
    def queries(self, timeout):
        def query(sql, params=None):
            if 'information_schema.columns' in sql:
                return [{'data_type': 'numeric'}]
            if sql.startswith('SELECT min'):
                row = self.db.execute(sql).fetchone()
                return [{'lower': row[0], 'upper': row[1]}]
            self.calls.append(params)
            if len(self.calls) == self.fail_at:
                raise RuntimeError('simulated disconnect')
            if params:
                sql = sql.replace('%(lower)s', '$lower').replace('%(upper)s', '$upper')
            result = self.db.execute(sql, params)
            columns = [c[0] for c in result.description]
            return [dict(zip(columns, row)) for row in result.fetchall()]
        yield query

    def run_batches(self):
        with patch.object(batches, 'queries', self.queries), \
                patch.dict('os.environ', {'KLC_ROOT': self.folder.name}), redirect_stdout(io.StringIO()):
            batches.run(self.args)

    def output(self):
        return next((Path(self.folder.name) / 'results').iterdir())

    def expected(self):
        result = self.db.execute(coverage_sql('main', 'positions', 'country', 'user_id', True))
        names = [c[0] for c in result.description]
        return summarize([dict(zip(names, row)) for row in result.fetchall()])

    def test_ranges_equal_single_query_with_repeated_cross_country_people(self):
        self.db.executemany('INSERT INTO positions VALUES (?, ?)', [
            (' US ', Decimal('-1.5')), ('US', Decimal('-1.5')), ('CA', Decimal('-1.5')),
            ('CA', 0), ('Unknown', 2), (None, 2), ('', None), ('US', None), ('US', 5)])
        self.run_batches()
        state = json.loads((self.output() / 'checkpoint.json').read_text())
        self.assertEqual(summarize(state['records']), self.expected())
        self.assertEqual(state['status'], 'complete')
        self.assertTrue(state['null_done'])
        self.assertEqual([c for c in self.calls if c], [
            {'lower': -2, 'upper': 0}, {'lower': 0, 'upper': 2},
            {'lower': 2, 'upper': 4}, {'lower': 4, 'upper': 6}])
        summary = json.loads((self.output() / 'summary.json').read_text())
        self.assertEqual(summary['people'], 4)
        self.assertEqual(summary['missing_person_records'], 2)
        self.assertIn('own snapshot', summary['consistency'])

    def test_failure_resume_skips_saved_ranges_and_does_not_double_count(self):
        self.db.execute("INSERT INTO positions VALUES ('US',1),('CA',1),('US',3),(NULL,NULL)")
        self.fail_at = 2
        with self.assertRaisesRegex(RuntimeError, 'disconnect'):
            self.run_batches()
        output = self.output()
        state = json.loads((output / 'checkpoint.json').read_text())
        self.assertEqual(state['completed_batches'], 1)
        self.assertEqual(state['next_lower'], 3)
        self.assertFalse((output / 'summary.json').exists())
        self.args.resume = output
        self.args.batch_size = 999  # Resume uses the saved partition width.
        self.calls = []
        self.fail_at = None
        self.run_batches()
        self.assertEqual(self.calls[0], {'lower': 3, 'upper': 4})
        self.assertEqual(summarize(json.loads((output / 'checkpoint.json').read_text())['records']), self.expected())
        previous = len(self.calls)
        self.run_batches()
        self.assertEqual(len(self.calls), previous)

    def test_empty_and_all_missing_ids(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                if missing:
                    self.db.execute("INSERT INTO positions VALUES ('US',NULL), (NULL,NULL)")
                self.run_batches()
                outputs = sorted((Path(self.folder.name) / 'results').iterdir())
                state = json.loads((outputs[-1] / 'checkpoint.json').read_text())
                self.assertEqual(summarize(state['records']), self.expected())
                self.assertEqual(state['completed_batches'], 1)

    def test_large_numeric_ids_keep_exact_boundaries(self):
        self.db.execute("INSERT INTO positions VALUES ('US',9007199254740993), ('CA',9007199254740995)")
        self.run_batches()
        self.assertEqual(self.calls[0]['lower'], 9007199254740993)
        self.assertEqual(summarize(json.loads((self.output() / 'checkpoint.json').read_text())['records']), self.expected())

    def test_resume_rejects_different_source_and_active_worker(self):
        self.run_batches()
        output = self.output()
        before = (output / 'checkpoint.json').read_bytes()
        self.args.resume = output
        self.args.table = 'other'
        with self.assertRaisesRegex(ValueError, 'does not match'):
            self.run_batches()
        self.assertEqual((output / 'checkpoint.json').read_bytes(), before)
        self.args.table = 'positions'
        with (output / '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, 'running worker'):
                self.run_batches()


if __name__ == '__main__':
    unittest.main()
