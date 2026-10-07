"""End-to-end checks of stages 00-05 on synthetic histories (see synthetic.scenario)."""
import csv
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import duckdb
    import yaml
    import synthetic
    from run import main
except ImportError:  # pragma: no cover
    duckdb = None

CARRY, CAP = 'carry_to_cutoff', 'cap_at_last_refresh'
FALLBACK, POSITION = 'position_with_profile_fallback', 'position_only'


def run_pipeline(folder, buckets=4, config=None, extract=None, stages='all'):
    folder = Path(folder)
    source = folder / 'extract'
    if not source.exists():
        (extract or synthetic.scenario()).write(source)
    args = ['--stages', stages, '--source', str(source), '--work-root', str(folder / 'work'), '--buckets', str(buckets)]
    if config:
        args += ['--config', str(config)]
    main(args)
    return folder / 'work'


@unittest.skipIf(duckdb is None, 'Install hk_revelio/requirements.txt (DuckDB, PyArrow, PyYAML)')
class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp()
        cls.work = run_pipeline(cls.folder)
        cls.db = duckdb.connect()
        cls.db.execute(f"CREATE VIEW pq AS SELECT * FROM read_parquet('{cls.work}/data/derived/person_quarter/*/*.parquet')")
        cls.db.execute(f"CREATE VIEW tr AS SELECT * FROM read_parquet('{cls.work}/data/derived/migration/transitions_all.parquet')")
        with open(cls.work / 'output/tables/replication_summary.csv') as stream:
            cls.summary = list(csv.DictReader(stream))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.folder)

    def rows(self, sql):
        return self.db.execute(sql).fetchall()

    def row(self, user, quarter, rule=CARRY):
        names = [d[0] for d in self.db.execute('SELECT * FROM pq LIMIT 0').description]
        found = self.rows(f"SELECT * FROM pq WHERE user_id = '{user}' AND quarter = '{quarter}' AND end_rule = '{rule}'")
        return dict(zip(names, found[0])) if found else None

    def estimate(self, measure, method='endpoint', window='primary', rule=CARRY, spec=FALLBACK, k=''):
        for r in self.summary:
            if (r['measure'], r['method'], r['window_name'], r['end_rule'], r['location_spec'],
                    r['persistence_quarters']) == (measure, method, window, rule, spec, str(k)):
                return int(r['estimate'])
        raise KeyError(measure)

    def test_within_quarter_moves_and_inclusive_end_months(self):
        self.assertEqual(self.row('p02', '2019Q4')['position_country'], 'Hong Kong')
        self.assertEqual(self.row('p02', '2020Q1')['position_country'], 'Singapore')  # HK ended in February
        self.assertEqual(self.row('p03', '2020Q1')['position_country'], 'Hong Kong')  # March end is inclusive
        self.assertEqual(self.row('p03', '2020Q2')['position_country'], 'Singapore')
        self.assertEqual(self.rows("SELECT count(*) FROM pq WHERE user_id = 'p04'"), [(0,)])  # Jan-Feb spell only

    def test_concurrent_jobs_and_conflicting_locations(self):
        row = self.row('p05', '2020Q2')
        self.assertEqual((row['primary_position_id'], row['position_country']), ('501', 'Hong Kong'))
        self.assertTrue(row['country_conflict'] and row['downrank_changed_primary'])
        self.assertEqual(row['alt_countries'], ['Singapore'])
        self.assertEqual(row['n_active'], 2)
        self.assertFalse(self.row('p05', '2020Q1')['country_conflict'])
        tie = self.row('p06', '2017Q1')  # same start month: position_id string order picks '1000'
        self.assertEqual((tie['primary_position_id'], tie['alt_countries']), ('1000', ['Hong Kong']))
        self.assertTrue(tie['any_active_hk'])

    def test_missing_dates_stale_profiles_fallback_and_profile_only(self):
        reasons = dict(self.rows(f"SELECT position_id, quarantine_reason FROM "
                                 f"read_parquet('{self.work}/data/derived/positions_quarantine.parquet')"))
        self.assertEqual(reasons['701'], 'undated')
        self.assertEqual(reasons['902'], 'start_after_cutoff')
        self.assertEqual(reasons['2301'], 'conflicting_duplicate_key')
        self.assertEqual(self.row('p07', '2015Q1')['position_country'], 'Hong Kong')
        fb = self.row('p10', '2020Q1')
        self.assertEqual((fb['loc_country_fallback'], fb['loc_source_fallback'], fb['fallback_timing']),
                         ('Hong Kong', 'profile_fallback', 'backcast'))
        self.assertIsNone(fb['loc_country_position_only'])
        self.assertIsNone(fb['hk_position_only'])
        self.assertEqual(self.row('p10', '2026Q2')['fallback_timing'], 'snapshot')
        timings = dict(self.rows("SELECT quarter, fallback_timing FROM pq WHERE user_id = 'p11' AND end_rule = 'carry_to_cutoff'"))
        self.assertEqual((timings['2016Q4'], timings['2017Q1'], timings['2018Q4']), ('backcast', 'snapshot', 'forwardcast'))
        self.assertNotIn('2019Q1', timings)  # fallback never fills quarters without an active position
        for user in ('p08', 'p12', 'p23'):  # profile-only: one dated snapshot in the complete refresh quarter
            self.assertEqual(self.rows(f"SELECT quarter, obs_type, hk_fallback, hk_position_only FROM pq "
                                       f"WHERE user_id = '{user}' AND end_rule = 'carry_to_cutoff'"),
                             [('2026Q2', 'profile_snapshot', True, None)])
        self.assertEqual(self.rows("SELECT count(*) FROM pq WHERE user_id = 'p13'"), [(0,)])  # 2026Q3 refresh
        panel = json.loads((self.work / 'run/02_panel.json').read_text())['summary']
        self.assertEqual(panel['profile_only']['refresh_in_partial_or_later_quarter'], 1)
        carry = self.rows("SELECT max(quarter) FROM pq WHERE user_id = 'p14' AND end_rule = 'carry_to_cutoff'")
        cap = self.rows("SELECT max(quarter) FROM pq WHERE user_id = 'p14' AND end_rule = 'cap_at_last_refresh'")
        self.assertEqual((carry, cap), ([('2026Q2',)], [('2020Q4',)]))

    def test_excursions_moves_returns_gaps_and_censoring(self):
        def events(user, k, spec=FALLBACK):
            return self.rows(f"SELECT event_q // 4 || 'Q' || (event_q % 4 + 1), kind, direction, hk_spell_type FROM tr "
                             f"WHERE user_id = '{user}' AND persistence_quarters = {k} AND end_rule = 'carry_to_cutoff' "
                             f"AND spec = '{spec}' ORDER BY event_q")
        self.assertEqual(events('p15', 1), [('2021Q1', 'confirmed', 'exit', 'first'),
                                            ('2021Q2', 'confirmed', 'entry', 'return')])
        self.assertEqual(events('p15', 2), [])  # one-quarter excursion
        for k in (1, 2, 4):
            self.assertEqual(events('p16', k), [('2020Q1', 'confirmed', 'exit', 'first'),
                                                ('2022Q1', 'confirmed', 'entry', 'return')])
            self.assertEqual(events('p17', k), [('2021Q1', 'gap', 'exit', 'first')])  # no inference across gap
        self.assertEqual(events('p18', 4), [('2023Q2', 'confirmed', 'entry', 'first')])  # full history confirms
        self.assertEqual(events('p01', 1), [])
        self.assertEqual(events('p19', 1), [])  # first observation is left-censored, not an entry
        self.assertEqual(self.estimate('people_censored_unconfirmed_at_window_end', 'quarterly_events', k=4), 1)
        self.assertEqual(self.estimate('entered_with_confirmed_entry', 'quarterly_events', k=4), 0)
        self.assertEqual(self.estimate('entered_with_confirmed_entry', 'quarterly_events', k=2), 1)
        spells = self.rows(f"SELECT start_q // 4 || 'Q' || (start_q % 4 + 1), quarters, preceded_by, followed_by FROM "
                           f"read_parquet('{self.work}/data/derived/migration/hk_spells.parquet') WHERE user_id = 'p17' "
                           f"AND end_rule = 'carry_to_cutoff' AND spec = '{FALLBACK}'")
        self.assertEqual(spells, [('2015Q1', 22, 'record_start', 'unknown_gap')])

    def test_large_identifiers_duplicates_and_joins(self):
        big = self.rows("SELECT DISTINCT primary_position_id FROM pq WHERE user_id = '2400288101' ORDER BY 1")
        self.assertEqual(big, [('-9223372036854775808',), ('18446744073709551615',), ('9223372036854775807',)])
        clean = json.loads((self.work / 'data/derived/clean_summary.json').read_text())
        self.assertEqual(clean['dedupe']['positions']['exact_duplicate_rows_collapsed'], 1)
        self.assertEqual(clean['dedupe']['positions']['conflicting_keys'], 1)
        self.assertEqual(clean['dedupe']['raw_titles']['exact_duplicate_rows_collapsed'], 1)
        self.assertEqual(clean['dedupe']['raw_titles']['conflicting_keys'], 1)
        self.assertEqual(clean['dedupe']['role_lookup_v3']['conflicting_keys'], 1)
        self.assertEqual(clean['title_status']['conflicting_raw_key'], 1)
        extract = synthetic.scenario()
        positions = len(extract.rows['individual_positions'])
        valid = clean['positions_by_quarantine_reason']['valid']
        quarantined = sum(v for k, v in clean['positions_by_quarantine_reason'].items() if k != 'valid')
        self.assertEqual(valid + quarantined + 1 + 2, positions)  # +1 collapsed duplicate, +2 conflicting rows
        joins = {j['name']: j for j in json.loads((self.work / 'output/diagnostics/inventory.json').read_text())['joins']}
        self.assertEqual(joins['positions_to_role_v3']['row_multiplication_if_naive'], 1)
        tables = {t['table']: t for t in json.loads((self.work / 'output/diagnostics/inventory.json').read_text())['tables']}
        self.assertEqual(tables['individual_positions']['exact_duplicate_rows'], 1)
        self.assertEqual(tables['individual_positions']['conflicting_keys'], 1)

    def test_endpoint_replication_versus_events(self):
        self.assertEqual([self.estimate(m) for m in ('stayed', 'entered', 'departed', 'net')], [9, 1, 6, -5])
        self.assertEqual(self.estimate('stayed', spec=POSITION), 8)  # profile-fallback stayer drops
        self.assertEqual(self.estimate('stayed', rule=CAP), 8)  # stale profile capped at refresh
        self.assertEqual(self.estimate('unclassified_hk_at_start_unknown_at_end', rule=CAP), 1)
        self.assertEqual(self.estimate('stayed_round_trip_out'), 2)
        self.assertEqual(self.estimate('stayed_continuous_hk'), 7)
        self.assertEqual(self.estimate('outside_hk_at_both'), 1)
        self.assertEqual(self.estimate('unclassified_unknown_at_start_hk_at_end'), 1)
        self.assertEqual(self.estimate('departed_same_company'), 1)
        self.assertEqual(self.estimate('departed_unknown_company'), 1)
        self.assertEqual(self.estimate('stayed_using_profile_location'), 1)
        events = {k: (self.estimate('entries', 'quarterly_events', k=k), self.estimate('exits', 'quarterly_events', k=k))
                  for k in (1, 2, 4)}
        self.assertEqual(events, {1: (3, 7), 2: (2, 6), 4: (1, 6)})
        self.assertEqual(self.estimate('gap_exits_undated', 'quarterly_events', k=1), 1)
        self.assertEqual(self.estimate('departed_via_gap_only', 'quarterly_events', k=1), 1)
        self.assertEqual(self.estimate('stayed_with_confirmed_exit', 'quarterly_events', k=1), 2)
        benchmark = [r for r in self.summary if r['measure'] == 'stayed' and r['primary_specification'] == 'true']
        self.assertEqual((len(benchmark), benchmark[0]['benchmark']), (1, '255911'))
        consistency = {r['measure']: (r['estimate'], r['benchmark']) for r in self.summary
                       if r['method'] == 'benchmark_consistency'}
        self.assertEqual(consistency['table3_total_departed'], ('26896', '26836'))
        self.assertIn('net_migration_by_age_group', {r['measure'] for r in self.summary if r['method'] == 'unavailable'})

    def test_unique_keys_manifest_reconciliation_and_immutability(self):
        self.assertEqual(self.rows('SELECT count(*) - count(DISTINCT (user_id, end_rule, qidx)) FROM pq'), [(0,)])
        tables = json.loads((self.work / 'output/diagnostics/inventory.json').read_text())['tables']
        self.assertTrue(all(t['rows_reconcile'] for t in tables))
        final = json.loads((self.work / 'run/05_replication.json').read_text())
        self.assertTrue(final['summary']['raw_content_hashes_unchanged'])
        for stage in ('00_inventory', '01_clean', '02_panel', '03_diagnostics', '04_migration', '05_replication'):
            record = json.loads((self.work / f'run/{stage}.json').read_text())
            self.assertEqual(record['status'], 'complete', stage)
            self.assertTrue(record['fingerprint']['config_sha256'] and record['fingerprint']['input_manifest_sha256'])

    def test_sample_contains_complete_histories(self):
        sample = self.work / 'data/derived/person_quarter_sample.parquet'
        people = self.rows(f"SELECT count(DISTINCT user_id) FROM read_parquet('{sample}')")[0][0]
        self.assertEqual(people, self.rows("SELECT count(DISTINCT user_id) FROM pq WHERE end_rule = 'carry_to_cutoff'")[0][0])
        gaps = self.rows(f"SELECT quarter FROM read_parquet('{sample}') WHERE user_id = 'p17' AND end_rule = 'carry_to_cutoff' "
                         f"AND obs_type = 'unobserved_gap' ORDER BY qidx")
        self.assertEqual(gaps, [('2020Q3',), ('2020Q4',)])
        flags = self.rows(f"SELECT transition_fallback_k1, transition_fallback_k2 FROM read_parquet('{sample}') "
                          f"WHERE user_id = 'p15' AND end_rule = 'carry_to_cutoff' AND quarter = '2021Q1'")
        self.assertEqual(flags, [('exit', None)])


@unittest.skipIf(duckdb is None, 'Install hk_revelio/requirements.txt (DuckDB, PyArrow, PyYAML)')
class SafeguardTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.folder)

    def test_manifest_mismatch_fails_inventory(self):
        synthetic.scenario().write(self.folder / 'extract', {'individual_positions': {'rows': 1}})
        with self.assertRaisesRegex(RuntimeError, 'reconciliation failed'):
            run_pipeline(self.folder, stages='00')
        record = json.loads((self.folder / 'work/run/00_inventory.json').read_text())
        self.assertEqual(record['status'], 'failed')
        with self.assertRaisesRegex(RuntimeError, 'is failed'):
            run_pipeline(self.folder, stages='01')

    def test_raw_file_change_is_detected(self):
        run_pipeline(self.folder, stages='00')
        part = sorted((self.folder / 'extract/individual_user').glob('*.parquet'))[0]
        part.write_bytes(part.read_bytes())  # same bytes, new modification time
        with self.assertRaisesRegex(RuntimeError, 'Raw extract changed'):
            run_pipeline(self.folder, stages='01')

    def test_sampling_is_reproducible_across_runs_and_buckets(self):
        config = yaml.safe_load((Path(__file__).resolve().parents[1] / 'config/analysis.yml').read_text())
        config['sampling']['max_people'] = 5
        path = self.folder / 'small_sample.yml'
        path.write_text(yaml.safe_dump(config))
        selections = []
        for name, buckets in (('a', 4), ('b', 4), ('c', 7)):
            work = run_pipeline(self.folder / name, buckets=buckets, config=path)
            record = json.loads((work / 'data/derived/person_quarter_sample.json').read_text())
            rows = duckdb.connect().execute(
                f"SELECT * EXCLUDE (sample_hash) FROM read_parquet('{work}/data/derived/person_quarter_sample.parquet') "
                "ORDER BY ALL").fetchall()
            selections.append((record['selected_ids_sha256'], record['selected_people'], rows))
        self.assertEqual(selections[0][1], 5)
        self.assertEqual(selections[0], selections[1])
        self.assertEqual(selections[0], selections[2])


if __name__ == '__main__':
    unittest.main()
