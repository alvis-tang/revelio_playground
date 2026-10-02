"""Validate Malawi cohort selection, serialization, and budget gates."""
from decimal import Decimal
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/malawi_extract.py'
spec = importlib.util.spec_from_file_location('malawi', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
try:
    import duckdb
    import pandas as pd
    import pyarrow.parquet as pq
except ImportError:
    duckdb = None


class GateTests(unittest.TestCase):
    def report(self):
        return dict(status='complete', version=m.VERSION, unavailable=[], planning_total_bytes=1000)

    def test_small_complete_estimate_allowed(self):
        m.gate(self.report())

    def test_incomplete_missing_and_oversized_estimates_blocked(self):
        for change in ({'status': 'incomplete'}, {'unavailable': ['layoffs']},
                       {'planning_total_bytes': m.BUDGET}, {'version': 0}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.gate({**self.report(), **change})

    def test_pilot_variability_increases_planning_bound(self):
        result = m.storage_projection(1000, [100, 900], [100, 100], 1000)
        self.assertEqual(result['expected_bytes'], 5000)
        self.assertEqual(result['planning_bytes'], 11700)
        self.assertEqual(m.storage_projection(0, [], [], 0)['planning_bytes'], 0)

    def test_partition_and_old_sources_excluded(self):
        self.assertFalse(any('_p0' in x or '_old' in x or '_samp' in x for x in m.SOURCES.values()))

    def test_missing_core_sources_fail_before_cohort(self):
        with self.assertRaisesRegex(ValueError, 'missing'):
            m.prepare(None, {})


@unittest.skipIf(duckdb is None, 'Install pandas, pyarrow, and duckdb for integration tests')
class LinkedDataTests(unittest.TestCase):
    def setUp(self):
        self.db = duckdb.connect()
        self.db.execute('CREATE SCHEMA fixture')
        fixtures = {
            'individual_user': ('user_id BIGINT, user_country VARCHAR', [(1, 'Malawi'), (2, 'Zambia'), (3, 'Zambia')]),
            'individual_positions': ('user_id BIGINT, position_id BIGINT, country VARCHAR, rcid BIGINT, ultimate_parent_rcid BIGINT',
                [(1, 11, 'Zambia', 101, 100), (2, 21, 'Malawi', 102, 100),
                 (2, 22, 'Zambia', 103, 100), (2, 21, 'Malawi', 102, 100),
                 (3, 31, 'Zambia', 104, 100), (None, 41, 'Malawi', 105, 100)]),
            'individual_positions_raw': ('user_id BIGINT, position_id BIGINT, description VARCHAR',
                [(2, 21, 'valid'), (3, 21, 'wrong person'), (2, 31, 'wrong position')]),
            'individual_user_education': ('user_id BIGINT, education_number INTEGER, rsid INTEGER', [(2, 1, 201), (3, 1, 202)]),
            'individual_user_education_raw': ('user_id BIGINT, education_number INTEGER, description VARCHAR',
                [(2, 1, 'valid'), (2, 2, 'wrong education'), (3, 1, 'wrong person')]),
            'postings_cosmos': ('job_id BIGINT, country VARCHAR, rcid BIGINT, ultimate_parent_rcid BIGINT',
                [(91, 'Malawi', 106, 100), (92, 'Zambia', 104, 100), (91, 'Malawi', 106, 100)]),
            'postings_cosmos_raw': ('job_id BIGINT, description VARCHAR', [(91, 'valid'), (92, 'outside')]),
            'company_mapping': ('rcid BIGINT, hq_country VARCHAR', [(100, 'USA'), (101, 'Zambia'), (102, 'Malawi'), (107, 'Malawi'), (104, 'Zambia')]),
            'school_mapping': ('rsid INTEGER, country VARCHAR', [(201, 'Zambia'), (202, 'Zambia'), (203, 'Malawi')]),
            'sentiment_individual_reviews': ('rcid BIGINT, ultimate_parent_rcid BIGINT, country VARCHAR', [(108, 100, 'Malawi')]),
            'workforce_dynamics_geo': ('rcid BIGINT, country VARCHAR', [(109, 'Malawi')]),
        }
        self.sources = {}
        for name, (columns, records) in fixtures.items():
            self.db.execute(f'CREATE TABLE fixture.{name} ({columns})')
            if records:
                self.db.executemany(f"INSERT INTO fixture.{name} VALUES ({','.join('?' for _ in records[0])})", records)
            self.sources[name] = dict(source='fixture.' + name, columns=[dict(column_name=x.strip().split()[0], data_type={'BIGINT': 'bigint', 'INTEGER': 'integer', 'VARCHAR': 'character varying'}[x.strip().split()[1]]) for x in columns.split(',')])
        outer = self
        class Result:
            def __init__(self, cursor):
                self.cursor = cursor
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def fetchmany(self, count):
                return self.cursor.fetchmany(count)
            def scalar_one(self):
                return self.cursor.fetchone()[0]
            def keys(self):
                return [x[0] for x in self.cursor.description]
        class Adapter:
            info = {}
            def execution_options(self, **kwargs):
                return self
            def execute(self, sql, params=None):
                sql = str(sql).replace('numeric[]', 'DECIMAL(38,0)[]').replace(':people', '$people')
                return Result(outer.db.execute(sql, {'people': (params or {}).get('people', self.info.get('mw_people', []))} if '$people' in sql else None))
        self.adapter = Adapter()
        self.prefix = m.prepare(self.adapter, self.sources).replace('numeric[]', 'DECIMAL(38,0)[]').replace(':people', '$people')

    def tearDown(self):
        self.db.close()

    def rows(self, name):
        sql = m.query(name, self.sources[name], self.prefix)
        return self.db.execute(sql, {'people': self.adapter.info['mw_people']}).fetchall()

    def test_cohort_union_and_full_history(self):
        self.assertEqual(set(self.adapter.info['mw_people']), {'1', '2'})
        records = self.rows('individual_positions')
        self.assertIn(('2', '22', 'Zambia', '103', '100'), records)
        self.assertFalse(any(row[0] == '3' for row in records))
        self.assertTrue(any(row[0] is None for row in records))

    def test_raw_matching_does_not_multiply_rows(self):
        self.assertEqual(self.rows('individual_positions_raw'), [('2', '21', 'valid')])
        self.assertEqual(self.rows('individual_user_education_raw'), [('2', 1, 'valid')])
        self.assertEqual(self.rows('postings_cosmos_raw'), [('91', 'valid')])

    def batched_rows(self):
        records = []
        for sql, params in m.raw_batches(self.adapter, self.sources):
            records.extend(self.adapter.execute(sql, params).cursor.fetchall())
        return records

    def test_raw_batches_equal_full_selection_with_duplicates_and_nulls(self):
        from collections import Counter
        self.adapter.info['mw_raw_batch_size'] = 1
        self.db.execute("INSERT INTO fixture.individual_positions_raw VALUES "
                        "(2,21,'valid'), (1,11,'resident history'), "
                        "(NULL,41,'null match'), (NULL,41,'null match'), "
                        "(NULL,31,'outside'), (3,11,'wrong person')")
        self.assertEqual(Counter(self.batched_rows()), Counter(self.rows('individual_positions_raw')))
        batches = list(m.raw_batches(self.adapter, self.sources))
        self.assertEqual([params.get('people', []) for _, params in batches], [['1'], ['2'], []])
        self.assertTrue(all('mw_postings' not in sql and 'mw_companies' not in sql for sql, _ in batches))
        unmatched = m.count_batches(self.adapter, m.raw_batches(self.adapter, self.sources, True), 'fixture')
        self.assertEqual(unmatched, 1)  # User 2's foreign position lacks raw text.

    def test_raw_batches_empty_cohort_keeps_null_branch(self):
        self.adapter.info['mw_people'] = []
        self.db.execute("INSERT INTO fixture.individual_positions_raw VALUES (NULL,41,'null match')")
        self.assertEqual(self.batched_rows(), [(None, '41', 'null match')])
        self.assertEqual(len(list(m.raw_batches(self.adapter, self.sources))), 1)

    def test_batched_pilot_merges_global_priorities_and_caps_rows(self):
        self.adapter.info['mw_raw_batch_size'] = 1
        self.db.execute("INSERT INTO fixture.individual_positions_raw VALUES "
                        "(1,11,'resident'), (NULL,41,'null match')")
        priorities = iter([0.9, 0.5, 0.1])
        def read_sql(sql, db, params=None, **kwargs):
            frame = self.adapter.execute(sql, params).cursor.fetchdf()
            frame['__malawi_pilot_priority'] = [next(priorities)] * len(frame)
            return frame
        sql = m.query('individual_positions_raw', self.sources['individual_positions_raw'], self.prefix)
        with patch.object(pd, 'read_sql_query', side_effect=read_sql):
            rows, frame = m.estimate_selection(self.adapter, 'individual_positions_raw', self.sources, sql, 2)
        self.assertEqual(rows, 3)
        self.assertEqual(frame['description'].tolist(), ['null match', 'valid'])
        self.assertNotIn('__malawi_pilot_priority', frame)

    def test_empty_batched_pilot_handles_pandas_object_columns(self):
        sql = m.query('individual_positions_raw', self.sources['individual_positions_raw'], self.prefix)
        columns = [c['column_name'] for c in self.sources['individual_positions_raw']['columns']]
        empty = pd.DataFrame(columns=columns + ['__malawi_pilot_priority'])
        with patch.object(pd, 'read_sql_query', return_value=empty):
            _, frame = m.estimate_selection(self.adapter, 'individual_positions_raw', self.sources, sql, 2)
        self.assertTrue(frame.empty)
        self.assertEqual(list(frame.columns), columns)

    def test_download_connection_loss_after_raw_part_is_incomplete(self):
        import json
        self.db.execute("INSERT INTO fixture.individual_positions_raw VALUES (1,11,'resident')")
        original = m.raw_batches
        calls = 0
        def batches(db, sources, unmatched_rows=False):
            nonlocal calls
            calls += 1
            for index, batch in enumerate(original(db, sources, unmatched_rows)):
                if calls == 2 and index == 1:
                    raise RuntimeError('connection lost during raw download')
                yield batch
        with tempfile.TemporaryDirectory() as folder, patch.object(m, 'raw_batches', side_effect=batches):
            with self.assertRaisesRegex(RuntimeError, 'connection lost'):
                self.download_fixture(folder)
            manifest = json.loads((Path(folder) / 'data' / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'incomplete')
            self.assertEqual(manifest['tables']['individual_positions_raw']['status'], 'incomplete')
            self.assertEqual(manifest['tables']['individual_positions_raw']['rows'], 1)
            self.assertEqual(manifest['raw_batch_size'], 1)

    def test_estimate_batch_failure_retains_incomplete_report(self):
        import json
        def fail(*args, **kwargs):
            raise RuntimeError('connection lost during batch')
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'estimate'
            with patch.object(m, 'discover', return_value=(self.sources, [])), \
                    patch.object(m, 'estimate_selection', side_effect=fail):
                with self.assertRaisesRegex(RuntimeError, 'connection lost'):
                    m.estimate(self.adapter, Path(folder), output, 100, raw_batch_size=1)
            report = json.loads((output / 'estimate.json').read_text())
            self.assertEqual(report['status'], 'incomplete')
            self.assertEqual(report['raw_batch_size'], 1)
            self.assertIn('connection lost', report['error'])

    def test_download_uses_saved_raw_batch_size(self):
        original = m.raw_batches
        seen = []
        def batches(db, sources, unmatched_rows=False):
            seen.append(db.info['mw_raw_batch_size'])
            yield from original(db, sources, unmatched_rows)
        with tempfile.TemporaryDirectory() as folder, patch.object(m, 'raw_batches', side_effect=batches):
            self.download_fixture(folder)
        self.assertTrue(seen)
        self.assertEqual(set(seen), {1})

    def test_referenced_and_domestic_mappings(self):
        self.assertEqual({r[0] for r in self.rows('school_mapping')}, {'201', '203'})
        self.assertEqual({r[0] for r in self.rows('company_mapping')}, {'100', '101', '102', '107'})

    def test_empty_cohort_valid(self):
        self.db.execute('DELETE FROM fixture.individual_user')
        self.db.execute('DELETE FROM fixture.individual_positions')
        m.prepare(self.adapter, self.sources)
        self.assertEqual(self.adapter.info['mw_people'], [])
        self.assertEqual(self.rows('individual_positions'), [])

    def test_estimate_manifest_pilots_and_gate(self):
        import json
        def read_sql(sql, db, params=None, **kwargs):
            sql = str(sql).replace('numeric[]', 'DECIMAL(38,0)[]').replace(':people', '$people')
            return self.db.execute(sql, params).fetchdf()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'estimate'
            with patch.object(m, 'discover', return_value=(self.sources, [])), patch.object(pd, 'read_sql_query', side_effect=read_sql):
                report = m.estimate(self.adapter, Path(folder), output, 100)
            self.assertEqual(report['status'], 'complete')
            self.assertNotIn('people_cohort', report['sources'])
            self.assertEqual(report['tables']['people_cohort']['rows'], 2)
            self.assertEqual(report['tables']['individual_positions']['rows'], 5)
            self.assertGreater(report['planning_total_bytes'], report['expected_total_bytes'])
            self.assertEqual(json.loads((output / 'estimate.json').read_text())['status'], 'complete')
            self.assertTrue(list(output.rglob('pilot-*.parquet')))
            m.gate(report)

    def download_fixture(self, folder, changed=False):
        estimate_dir = Path(folder) / 'estimate'
        cohort = estimate_dir / 'cohort'
        cohort.mkdir(parents=True)
        pd.DataFrame({'user_id': ['1', '2']}).to_parquet(cohort / 'part.parquet')
        tables = {}
        for name in ('individual_positions', 'individual_positions_raw'):
            tables[name] = dict(sql=m.query(name, self.sources[name], self.prefix),
                                rows=len(self.rows(name)), source=self.sources[name]['source'])
        if changed:
            tables['individual_positions']['rows'] += 1
        report = dict(raw_batch_size=1, version=m.VERSION, status='complete', unavailable=[], planning_total_bytes=10000,
                      sources=self.sources, tables=tables)
        output = Path(folder) / 'data'
        with patch.object(m, 'discover', return_value=(self.sources, [])):
            m.download(self.adapter, report, estimate_dir, output, 2)
        return output

    def test_download_complete_manifests_and_chunks(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            output = self.download_fixture(folder)
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'complete')
            self.assertEqual(manifest['tables']['individual_positions']['rows'], 5)
            self.assertEqual(manifest['tables']['individual_positions']['parts'], 3)
            self.assertEqual(manifest['tables']['individual_positions_raw']['rows'], 1)
            self.assertEqual(manifest['unmatched_raw']['individual_positions_raw'], 3)
            self.assertTrue(all(pq.read_table(p).num_rows for p in output.rglob('*.parquet')))

    def test_changed_counts_leave_incomplete_manifest(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'row count changed'):
                self.download_fixture(folder, changed=True)
            manifest = json.loads((Path(folder) / 'data' / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'incomplete')
            self.assertIn('error', manifest)

    def test_empty_product_completes_without_parts(self):
        import json
        self.db.execute('DELETE FROM fixture.individual_positions_raw')
        with tempfile.TemporaryDirectory() as folder:
            output = self.download_fixture(folder)
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(manifest['tables']['individual_positions_raw']['rows'], 0)
            self.assertEqual(manifest['tables']['individual_positions_raw']['status'], 'complete')
            self.assertFalse(list((output / 'individual_positions_raw').glob('*.parquet')))

    def test_mid_download_budget_failure_keeps_incomplete_manifest(self):
        import json
        original = m.write_part
        calls = []
        def capped(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise ValueError('20 GB storage cap reached')
            return original(*args, **kwargs)
        with tempfile.TemporaryDirectory() as folder, patch.object(m, 'write_part', side_effect=capped):
            with self.assertRaisesRegex(ValueError, 'cap'):
                self.download_fixture(folder)
            output = Path(folder) / 'data'
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'incomplete')
            self.assertEqual(manifest['tables']['individual_positions']['parts'], 1)
            self.assertEqual(len(list(output.rglob('*.parquet'))), 1)

    def test_null_person_raw_matches_stable_position(self):
        self.db.execute("INSERT INTO fixture.individual_positions_raw VALUES (NULL, 41, 'null person')")
        self.assertIn((None, '41', 'null person'), self.rows('individual_positions_raw'))

    def test_raw_null_branches_preserve_duplicates_and_reject_wrong_people(self):
        self.db.execute("INSERT INTO fixture.individual_positions_raw VALUES "
                        "(NULL, 41, 'null person'), (NULL, 41, 'null person'), "
                        "(3, 41, 'wrong person'), (NULL, 21, 'wrong null person'), "
                        "(2, 21, 'valid')")
        records = self.rows('individual_positions_raw')
        self.assertEqual(records.count((None, '41', 'null person')), 2)
        self.assertEqual(records.count(('2', '21', 'valid')), 2)
        self.assertEqual(len(records), 4)

    def test_review_time_roundtrip(self):
        from datetime import time
        source = dict(columns=[dict(column_name='review_time', data_type='time without time zone')])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'part.parquet'
            m.write_part(pd.DataFrame({'review_time': [time(12, 34, 56), None]}), path, 0, schema=m.arrow_schema(source))
            self.assertEqual(pq.read_table(path).column('review_time').to_pylist(), [time(12, 34, 56), None])

    def test_large_ids_decimal_and_null_chunks(self):
        source = dict(columns=[dict(column_name='user_id', data_type='numeric'),
                               dict(column_name='salary', data_type='numeric', numeric_precision=19, numeric_scale=2)])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'part.parquet'
            frame = pd.DataFrame({'user_id': ['9999999999999999999', None], 'salary': [Decimal('12345678901234567.89'), None]})
            size = m.write_part(frame, path, 0, schema=m.arrow_schema(source))
            read = pq.read_table(path).to_pydict()
            self.assertEqual(read['user_id'], frame.user_id.tolist())
            self.assertEqual(read['salary'][0], Decimal('12345678901234567.89'))
            self.assertEqual(size, path.stat().st_size)
            null = pd.DataFrame({'user_id': [None], 'salary': [None]})
            m.write_part(null, Path(folder) / 'null.parquet', size, schema=m.arrow_schema(source))
            self.assertEqual(pq.read_schema(path), pq.read_schema(Path(folder) / 'null.parquet'))

    def test_budget_and_disk_failure_leave_no_part(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'part.parquet'
            frame = pd.DataFrame({'user_id': ['123']})
            with self.assertRaisesRegex(ValueError, 'cap'):
                m.write_part(frame, path, 0, budget=1)
            self.assertFalse(path.exists())
            with patch.object(m.shutil, 'disk_usage') as usage:
                usage.return_value.free = 0
                with self.assertRaisesRegex(ValueError, 'storage'):
                    m.write_part(frame, path, 0)
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
