"""Exercise country coverage SQL on small data and validate saved artifacts.

Install duckdb in a development environment to run the SQL integration cases.
It is not required on KLC; production queries execute on WRDS PostgreSQL.
"""
import csv
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/country_coverage.py'
spec = importlib.util.spec_from_file_location('country_coverage', SCRIPT)
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)

try:
    import duckdb
except ImportError:
    duckdb = None


class CoverageTests(unittest.TestCase):
    def test_unsafe_identifiers_rejected(self):
        for value in ('revelio.positions', 'country; DROP TABLE positions', '', 'a"b'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                coverage.identifier(value)
        self.assertEqual(coverage.identifier('user_id'), '"user_id"')

    def test_inconsistent_counts_rejected(self):
        records = [dict(country=None, is_total=1, position_records=2,
                        people=1, missing_person_records=0)]
        with self.assertRaisesRegex(ValueError, 'global total'):
            coverage.summarize(records)

    @unittest.skipIf(duckdb is None, 'Install duckdb for SQL integration tests')
    def test_sql_counts_and_outputs(self):
        with duckdb.connect(':memory:') as conn:
            conn.execute('CREATE SCHEMA revelio')
            conn.execute('CREATE TABLE revelio.positions (country VARCHAR, user_id VARCHAR)')
            conn.executemany('INSERT INTO revelio.positions VALUES (?, ?)', [
                ('US', 'alice'), (' US ', 'alice'), ('CA', 'alice'),
                ('CA', 'bob'), (None, 'carol'), ('  ', None),
                ('US', ''), ('Unknown', 'dave'),
            ])
            cursor = conn.execute(coverage.coverage_sql('revelio', 'positions', 'country', 'user_id'))
            names = [column[0] for column in cursor.description]
            records = [dict(zip(names, row)) for row in cursor.fetchall()]
        countries, summary = coverage.summarize(records)
        self.assertEqual(summary, dict(position_records=8, people=4, missing_person_records=2,
                                       named_countries=3, unknown_country_position_records=2))
        by_country = {(row['country'], row['country_missing']): row for row in countries}
        self.assertEqual(by_country[('US', False)]['position_records'], 3)
        self.assertEqual(by_country[('US', False)]['people'], 1)
        self.assertEqual(by_country[('CA', False)]['people'], 2)
        self.assertEqual(by_country[('Unknown', True)]['missing_person_records'], 1)
        self.assertEqual(by_country[('Unknown', False)]['people'], 1)
        self.assertEqual(sum(r['people'] for r in countries), 5)
        self.assertAlmostEqual(sum(r['position_share_pct'] for r in countries), 100)
        stamp = datetime(2026, 10, 1, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            output = coverage.save_results(folder, countries, summary, stamp)
            with (output / 'countries.csv').open(newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 4)
            self.assertEqual(json.loads((output / 'summary.json').read_text()), summary)
            with self.assertRaises(FileExistsError):
                coverage.save_results(folder, countries, summary, stamp)

    @unittest.skipIf(duckdb is None, 'Install duckdb for SQL integration tests')
    def test_empty_table_and_numeric_person_ids(self):
        with duckdb.connect(':memory:') as conn:
            conn.execute('CREATE TABLE positions (country VARCHAR, user_id BIGINT)')
            sql = coverage.coverage_sql('main', 'positions', 'country', 'user_id', person_is_numeric=True)
            cursor = conn.execute(sql)
            names = [c[0] for c in cursor.description]
            countries, summary = coverage.summarize([dict(zip(names, row)) for row in cursor.fetchall()])
            self.assertEqual(countries, [])
            self.assertEqual(summary['position_records'], 0)
            self.assertEqual(summary['people'], 0)
            conn.execute("INSERT INTO positions VALUES ('US', 123), ('US', 123), ('CA', 123)")
            cursor = conn.execute(sql)
            countries, summary = coverage.summarize([dict(zip(names, row)) for row in cursor.fetchall()])
            self.assertEqual(summary['people'], 1)
            self.assertEqual(summary['position_records'], 3)

    @unittest.skipIf(duckdb is None, 'Install duckdb for SQL integration tests')
    def test_cli_writes_metadata_and_uses_project_root(self):
        with duckdb.connect(':memory:') as db, tempfile.TemporaryDirectory() as folder:
            db.execute('CREATE TABLE positions (country VARCHAR, user_id BIGINT)')
            db.execute("INSERT INTO positions VALUES ('US', 1), (NULL, NULL)")

            class Connection:
                def raw_sql(self, sql, params=None):
                    if params:
                        return db.execute("SELECT 'bigint' AS data_type").fetchdf()
                    return db.execute(sql).fetchdf()

            @contextmanager
            def connect():
                yield Connection()

            log = io.StringIO()
            with patch.object(coverage, 'connection', connect), \
                    patch.dict('os.environ', {'KLC_ROOT': folder}), redirect_stdout(log):
                coverage.main(['--schema', 'main', '--table', 'positions',
                               '--country-column', 'country', '--person-column', 'user_id'])
            outputs = list((Path(folder) / 'results').glob('country_coverage_*'))
            self.assertEqual(len(outputs), 1)
            summary = json.loads((outputs[0] / 'summary.json').read_text())
            self.assertEqual(summary['status'], 'complete')
            self.assertEqual(summary['position_records'], 2)
            self.assertEqual(summary['people'], 1)
            self.assertEqual(summary['missing_person_records'], 1)
            self.assertEqual(summary['source']['table'], 'positions')
            self.assertEqual(summary['source']['person_data_type'], 'bigint')
            self.assertIn('GROUPING SETS', summary['sql'])
            self.assertIn('All available history', summary['definitions']['time_range'])
            self.assertIn('+00:00', summary['started_at_utc'])
            self.assertGreaterEqual(summary['elapsed_seconds'], 0)
            self.assertTrue((outputs[0] / 'countries.csv').is_file())
            self.assertIn('Globally distinct people: 1', log.getvalue())


if __name__ == '__main__':
    unittest.main()
