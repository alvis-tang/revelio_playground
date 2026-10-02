"""Verify bounded WRDS queries and lossless preview artifacts offline."""
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/job_descriptions_smoke.py'
spec = importlib.util.spec_from_file_location('job_descriptions_smoke', SCRIPT)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)

try:
    import pandas as pd
except ImportError:
    pd = None
try:
    import duckdb
except ImportError:
    duckdb = None


class QueryTests(unittest.TestCase):
    def test_bounded_raw_sample_and_left_join(self):
        sql = preview.preview_sql()
        self.assertIn('WITH sample AS MATERIALIZED', sql)
        self.assertEqual(sql.count('LIMIT %(limit)s'), 2)
        self.assertIn("description ~ '[^[:space:]]'", sql)
        self.assertIn('LEFT JOIN revelio.postings_cosmos AS p ON p.job_id = CASE', sql)
        self.assertIn('THEN s.job_id::bigint END', sql)
        self.assertIn('s.job_id::text AS job_id', sql)
        for column in preview.POSTING_COLUMNS:
            self.assertIn('p.' + column, sql)

    def test_transaction_timeout_and_connection_restored(self):
        conn = MagicMock()
        original = conn.connection
        transaction = conn.engine.connect.return_value.__enter__.return_value.execution_options.return_value
        preview.fetch_preview(conn, 'SELECT test', 20)
        transaction.exec_driver_sql.assert_called_once_with("SET LOCAL statement_timeout = '60s'")
        conn.raw_sql.assert_called_once_with('SELECT test', params={'limit': 20}, coerce_float=False)
        self.assertIs(conn.connection, original)
        conn.raw_sql.side_effect = RuntimeError('permission denied')
        with self.assertRaisesRegex(RuntimeError, 'permission denied'):
            preview.fetch_preview(conn, 'SELECT test', 20)
        self.assertIs(conn.connection, original)

    def test_invalid_limits_do_not_connect(self):
        for limit in ('0', '-1', '101'):
            with self.subTest(limit=limit), patch.object(preview, 'connection') as connect, \
                    patch('sys.stderr', new=io.StringIO()), self.assertRaises(SystemExit):
                preview.main(['--limit', limit])
            connect.assert_not_called()

    def test_connection_and_query_failures_have_actionable_errors(self):
        with patch.object(preview, 'connection', side_effect=ValueError('authentication failed')), \
                redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'doctor.*authentication failed'):
            preview.main([])
        @contextmanager
        def connect():
            yield object()
        for message in ('permission denied', 'statement timeout'):
            with self.subTest(message=message), patch.object(preview, 'connection', connect), \
                    patch.object(preview, 'fetch_preview', side_effect=RuntimeError(message)), \
                    redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, message):
                preview.main([])


@unittest.skipIf(pd is None, 'Install pandas for preview serialization tests')
class ArtifactTests(unittest.TestCase):
    @unittest.skipIf(duckdb is None, 'Install duckdb for preview join integration tests')
    def test_query_join_and_nonempty_filter(self):
        with duckdb.connect(':memory:') as db:
            db.execute('CREATE SCHEMA revelio')
            db.execute('CREATE TABLE revelio.postings_cosmos_raw '
                       '(job_id DECIMAL(32,0), title_raw VARCHAR, jobtitle_translated VARCHAR, '
                       'location_raw VARCHAR, description VARCHAR)')
            columns = ', '.join(name + ' VARCHAR' for name in preview.POSTING_COLUMNS)
            db.execute('CREATE TABLE revelio.postings_cosmos (job_id BIGINT, ' + columns + ')')
            db.execute("INSERT INTO revelio.postings_cosmos (job_id, company) VALUES (42, 'Example')")
            db.executemany('INSERT INTO revelio.postings_cosmos_raw VALUES (?, ?, ?, ?, ?)', [
                ('42', 'Engineer', None, 'Chicago', 'Résumé\nFull text'),
                ('12345678901234567890123456789012', 'Analyst', None, None, 'Unmatched'),
                ('43', None, None, None, None),
                ('44', None, None, None, ' \t\n'),
            ])
            # DuckDB's ~ requires a full match; PostgreSQL's ~ searches anywhere.
            sql = preview.preview_sql().replace("description ~ '[^[:space:]]'",
                                                "regexp_matches(description, '[^[:space:]]')")
            frame = db.execute(sql.replace('%(limit)s', '20')).fetchdf()
            self.assertEqual(len(frame), 2)
            by_id = frame.set_index('job_id')
            self.assertEqual(by_id.loc['42', 'company'], 'Example')
            self.assertEqual(by_id.loc['42', 'description'], 'Résumé\nFull text')
            self.assertTrue(pd.isna(by_id.loc['12345678901234567890123456789012', 'company']))
            bounded = db.execute(sql.replace('%(limit)s', '1')).fetchdf()
            self.assertEqual(len(bounded), 1)

    def frame(self):
        return pd.DataFrame([
            dict(job_id='12345678901234567890123456789012', title_raw='Engineer',
                 description='Résumé, "quoted"\n第二行\t ', company='Example',
                 location_raw='Chicago', post_date=datetime(2026, 1, 2), salary=123.5),
            dict(job_id='42', title_raw='Analyst', description='Full description',
                 company=None, location_raw=None, post_date=None, salary=None),
        ])

    def test_artifacts_preserve_ids_text_and_missing_metadata(self):
        frame = self.frame()
        with tempfile.TemporaryDirectory() as root:
            output, records = preview.save_preview(frame, root, 'SELECT test', 20,
                                                   datetime.now(timezone.utc))
            saved = [json.loads(line) for line in (output / 'descriptions.jsonl').read_text().splitlines()]
            self.assertEqual(saved, records)
            self.assertEqual(saved[0]['job_id'], frame.iloc[0]['job_id'])
            self.assertEqual(saved[0]['description'], frame.iloc[0]['description'])
            self.assertIsNone(saved[1]['company'])
            self.assertIsNone(saved[1]['salary'])
            with (output / 'postings.csv').open(newline='', encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]['description'], frame.iloc[0]['description'])
            summary = json.loads((output / 'summary.json').read_text())
            self.assertEqual(summary['rows'], 2)
            self.assertEqual(summary['requested_limit'], 20)
            self.assertEqual(summary['missing_value_counts']['company'], 1)
            self.assertEqual(summary['columns'], list(frame.columns))
            self.assertEqual(summary['status'], 'complete')

    def test_empty_and_excess_rows_do_not_create_artifacts(self):
        for frame, limit in ((self.frame().iloc[:0], 20), (self.frame(), 1)):
            with tempfile.TemporaryDirectory() as root:
                with self.assertRaises(ValueError):
                    preview.save_preview(frame, root, 'SELECT test', limit, datetime.now(timezone.utc))
                self.assertEqual(list(Path(root).iterdir()), [])

    def test_cli_defaults_and_prints_preview(self):
        @contextmanager
        def connect():
            yield object()
        with tempfile.TemporaryDirectory() as root, patch.object(preview, 'connection', connect), \
                patch.object(preview, 'fetch_preview', return_value=self.frame()) as fetch, \
                patch.dict('os.environ', {'KLC_ROOT': root}), redirect_stdout(io.StringIO()) as log:
            preview.main([])
            self.assertEqual(fetch.call_args.args[2], 20)
            self.assertIn('Downloaded 2 rows', log.getvalue())
            self.assertIn('Example | Engineer | Chicago', log.getvalue())
            self.assertEqual(len(list((Path(root) / 'data').glob('*/summary.json'))), 1)


if __name__ == '__main__':
    unittest.main()
