"""Regression checks for resumable exact-ID extraction and transaction recovery."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import country_extract_resumable as r
import test_malawi_extract as fixtures
duckdb = fixtures.duckdb


@unittest.skipIf(duckdb is None, 'Install SQL and Parquet test dependencies')
class PostingBatchesTests(fixtures.HongKongLinkedDataTests):
    def test_posting_batches_preserve_duplicates_and_large_ids(self):
        from collections import Counter
        self.db.execute("INSERT INTO fixture.postings_cosmos VALUES "
                        "(9223372036854775807,'Hong Kong',106,100), "
                        "(NULL,'Hong Kong',106,100), (93,'Hong Kong',106,100)")
        self.db.execute("INSERT INTO fixture.postings_cosmos_raw VALUES "
                        "(91,'valid'), (9223372036854775807,'large'), (NULL,'excluded')")
        r.m.prepare_postings(self.adapter, self.sources)
        self.adapter.info['posting_batch_size'] = 1
        rows = []
        for sql, params in r.m.posting_batches(self.adapter, self.sources):
            rows.extend(self.adapter.execute(sql, params).cursor.fetchall())
        self.assertEqual(Counter(rows), Counter(self.rows('postings_cosmos_raw')))
        counts = r.m.count_batches(self.adapter, r.m.posting_batches(self.adapter, self.sources, True), 'unmatched')
        self.assertEqual(counts, 2)
        self.assertEqual(self.adapter.info['posting_ids'], ['91', '9223372036854775807', '93'])

    def test_empty_posting_cohort(self):
        self.adapter.info['posting_ids'] = []
        self.assertEqual(len(list(r.m.posting_batches(self.adapter, self.sources))), 1)
        self.assertEqual(self.adapter.execute(*list(r.m.posting_batches(self.adapter, self.sources))[0]).cursor.fetchall(), [])

    def settings(self):
        return dict(country='Hong Kong', raw_batch_size=1, posting_batch_size=1,
                    pilot_rows=100, chunksize=1, timeout=60, download_if_safe=True)

    def fake_queries(self):
        outer = self
        class Queries:
            settings = outer.settings()
            info = outer.adapter.info
            def call(self, action):
                return action(outer.adapter)
            def close(self):
                pass
        return Queries()

    def state(self, folder):
        return dict(settings=self.settings(), sources=self.sources, estimate_units={}, unmatched_units={},
                    report={'tables': {}}, output=str(Path(folder) / 'data'))

    def read_sql(self, sql, db, params=None, **kwargs):
        # DuckDB has no PostgreSQL setseed scalar function; ignore it in tests.
        return self.adapter.execute(sql, params).cursor.fetchdf()

    def estimate(self, queries, state, folder, products):
        import pandas as pd
        with patch.object(r.m, 'execute'), patch.object(pd, 'read_sql_query', side_effect=self.read_sql):
            r.estimate_tables(queries, state, folder, products)

    def test_estimate_resume_skips_committed_unit_and_cleans_orphan_sample(self):
        queries = self.fake_queries()
        calls = 0
        def flaky(action):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('disconnect')
            return action(self.adapter)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'estimate'; folder.mkdir()
            state = self.state(tmp)
            products = {name: self.sources[name] for name in ('individual_positions_raw', 'postings_cosmos_raw')}
            queries.call = flaky
            with self.assertRaisesRegex(RuntimeError, 'disconnect'):
                self.estimate(queries, state, folder, products)
            saved = json.loads((folder / 'checkpoint.json').read_text())
            self.assertEqual(len(saved['estimate_units']['individual_positions_raw']['counts']), 1)
            orphan = folder / 'individual_positions_raw' / 'sample-999999.tmp'
            orphan.write_bytes(b'orphan')
            queries.call = lambda action: action(self.adapter)
            self.estimate(queries, saved, folder, products)
            self.assertFalse(orphan.exists())
            self.assertEqual(saved['report']['tables']['individual_positions_raw']['rows'], 1)
            self.assertEqual(saved['report']['tables']['postings_cosmos_raw']['rows'], 1)

    def test_download_resume_cleans_partial_and_preserves_committed_units(self):
        queries = self.fake_queries()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'estimate'; folder.mkdir()
            state = self.state(tmp)
            products = {'postings_cosmos_raw': self.sources['postings_cosmos_raw']}
            self.adapter.info['posting_batch_size'] = 1
            self.db.execute("INSERT INTO fixture.postings_cosmos VALUES (93,'Hong Kong',106,100)")
            self.db.execute("INSERT INTO fixture.postings_cosmos_raw VALUES (93,'another')")
            r.m.prepare_postings(self.adapter, self.sources)
            self.estimate(queries, state, folder, products)
            original = r.download_unit
            calls = 0
            def flaky(*args):
                nonlocal calls
                calls += 1
                if calls == 2:
                    original(*args)
                    raise RuntimeError('connection lost after writing')
                return original(*args)
            with patch.object(r, 'download_unit', side_effect=flaky), patch.object(r, 'unmatched_checks', return_value={}):
                with self.assertRaisesRegex(RuntimeError, 'connection lost'):
                    r.download_tables(queries, state, folder, products)
            saved = json.loads((folder / 'checkpoint.json').read_text())
            self.assertEqual(len(saved['manifest']['tables']['postings_cosmos_raw']['units']), 1)
            with patch.object(r, 'unmatched_checks', return_value={}):
                r.download_tables(queries, saved, folder, products)
            self.assertEqual(saved['manifest']['tables']['postings_cosmos_raw']['rows'], 2)
            self.assertEqual(saved['manifest']['status'], 'complete')
            self.assertEqual(len(list(Path(saved['output']).rglob('part-*.parquet'))), 2)

    def test_whole_run_and_completed_resume(self):
        import pandas as pd
        queries = self.fake_queries()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = SimpleNamespace(command='estimate', resume=None, estimate=None, **self.settings())
            with patch.object(r, 'Queries', return_value=queries), patch.object(r.m, 'discover', return_value=(self.sources, [])), \
                    patch.object(r.m, 'execute'), patch.object(pd, 'read_sql_query', side_effect=self.read_sql):
                r.run(args, root)
                folder = next((root / 'results').iterdir())
                state = json.loads((folder / 'checkpoint.json').read_text())
                self.assertEqual(state['status'], 'complete')
                manifest = json.loads((Path(state['output']) / 'manifest.json').read_text())
                self.assertEqual(manifest['tables']['postings_cosmos_raw']['rows'], 1)
                self.assertEqual(manifest['unmatched_raw']['postings_cosmos_raw'], 0)
                args.resume = folder
                r.run(args, root)
                self.assertEqual(json.loads((Path(state['output']) / 'manifest.json').read_text())['status'], 'complete')

    def test_frozen_cohort_tamper_rejected(self):
        queries = self.fake_queries()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            state = dict(sources=self.sources, cohorts={})
            r.cohort(queries, state, folder, 'postings')
            part = next((folder / 'posting_cohort').glob('*.parquet'))
            part.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'cohort files changed'):
                r.cohort(queries, state, folder, 'postings')

    def test_count_change_and_cap_stop_before_committing(self):
        queries = self.fake_queries()
        source = self.sources['postings_cosmos_raw']
        sql, params = next(r.m.posting_batches(self.adapter, self.sources))
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); staging = folder / 'data' / '.pending'; staging.parent.mkdir()
            with self.assertRaisesRegex(ValueError, 'count changed'):
                r.download_unit(self.adapter, sql, params, source, 99, staging, folder, staging.parent, 1)
            with patch.object(r.m, 'write_part', side_effect=ValueError('20 GB storage cap')):
                with self.assertRaisesRegex(ValueError, 'storage cap'):
                    r.download_unit(self.adapter, sql, params, source, 1, staging, folder, staging.parent, 1)
            self.assertFalse(list(staging.glob('part-*.parquet')))


class RecoveryTests(unittest.TestCase):
    def test_lock_rejects_second_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            with r.locked(Path(tmp)):
                with self.assertRaisesRegex(ValueError, 'already has'):
                    with r.locked(Path(tmp)):
                        pass

    def queries(self):
        return r.Queries(dict(country='Hong Kong', raw_batch_size=1000, posting_batch_size=1000, timeout=60))

    def test_transport_retry_and_timeout_not_retried(self):
        try:
            from sqlalchemy.exc import OperationalError
        except ImportError:
            self.skipTest('Install sqlalchemy')
        from contextlib import contextmanager
        calls = []
        db = SimpleNamespace(info={}, exec_driver_sql=lambda sql: None)
        @contextmanager
        def connection(**kwargs):
            calls.append('connect'); yield object()
        @contextmanager
        def session(conn, timeout):
            yield db
        failures = [OperationalError('sql', {}, Exception('EOF')), 42]
        def action(db):
            value = failures.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        with patch.object(r.m, 'connection', connection), patch.object(r.m, 'session', session), patch.object(r.time, 'sleep'):
            queries = self.queries()
            self.assertEqual(queries.call(action), 42)
            self.assertEqual(len(calls), 2)
            queries.close()
            timeout = Exception('statement timeout'); timeout.pgcode = '57014'
            with self.assertRaises(OperationalError):
                self.queries().call(lambda db: (_ for _ in ()).throw(OperationalError('sql', {}, timeout)))
            self.assertEqual(len(calls), 3)

    def test_connect_transport_failure_retries_and_exhausts_at_three(self):
        try:
            from sqlalchemy.exc import OperationalError
        except ImportError:
            self.skipTest('Install sqlalchemy')
        from contextlib import contextmanager
        failures = 0
        @contextmanager
        def connection(**kwargs):
            nonlocal failures
            failures += 1
            raise OperationalError('connect', {}, Exception('network down'))
            yield
        with patch.object(r.m, 'connection', connection), patch.object(r.time, 'sleep'):
            queries = self.queries()
            with self.assertRaises(OperationalError):
                queries.call(lambda db: None)
            self.assertEqual(failures, 3)
            queries.close()

    def test_changed_schema_on_reconnection_rejected(self):
        try:
            import sqlalchemy
        except ImportError:
            self.skipTest('Install sqlalchemy')
        from contextlib import contextmanager
        db = SimpleNamespace(info={}, exec_driver_sql=lambda sql: None)
        @contextmanager
        def context(*args, **kwargs):
            yield db
        queries = self.queries(); queries.sources = {'old': {}}
        with patch.object(r.m, 'connection', context), patch.object(r.m, 'session', context), patch.object(r.m, 'discover', return_value=({'new': {}}, [])):
            with self.assertRaisesRegex(ValueError, 'schema changed'):
                queries.call(lambda db: None)
            queries.close()

    def test_snapshot_download_rejects_resumable_estimate(self):
        with self.assertRaisesRegex(ValueError, '--resumable'):
            r.m.gate(dict(resumable=True))


if __name__ == '__main__':
    unittest.main()
