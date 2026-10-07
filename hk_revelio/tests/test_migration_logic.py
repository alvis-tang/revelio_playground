"""Migration state machine: hand-built histories and a randomized reference check."""
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import duckdb
    from hkrev import migration
except ImportError:  # pragma: no cover
    duckdb = None
import reference

H, N = True, False


def panel_rows(user, start, states):
    """states: string of H/N/. (unknown) from quarter `start`."""
    rows = []
    for offset, code in enumerate(states):
        if code in 'HN':
            rows.append((user, start + offset, code == 'H'))
    return rows


@unittest.skipIf(duckdb is None, 'Install DuckDB and PyYAML (hk_revelio/requirements.txt)')
class MigrationLogicTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()

    def load(self, rows):
        self.con.execute('CREATE OR REPLACE TABLE panel (user_id VARCHAR, qidx INTEGER, hk_fallback BOOLEAN, '
                         'hk_position_only BOOLEAN, loc_country_fallback VARCHAR, loc_source_fallback VARCHAR, '
                         'fallback_timing VARCHAR, loc_country_position_only VARCHAR, primary_parent_rcid VARCHAR, '
                         'primary_rcid VARCHAR)')
        for user, quarter, hk in rows:
            country = 'Hong Kong' if hk else 'Singapore'
            self.con.execute('INSERT INTO panel VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                             [user, quarter, hk, hk, country, 'position', None, country, 'firm', 'firm'])
        self.con.execute(f"CREATE OR REPLACE TEMP TABLE runs AS {migration.runs_sql('panel', 'fallback')}")

    def derive(self, k, horizon=10 ** 6):
        migration.derive(self.con, 'runs', 'panel', 'fallback', k, horizon)
        events = self.con.execute("SELECT user_id, event_q, kind, direction FROM transitions ORDER BY ALL").fetchall()
        summary = {r[0]: r for r in self.con.execute(
            'SELECT user_id, excursions, unconfirmed_before_gap, terminal_unconfirmed, terminal_pending_direction '
            'FROM summary').fetchall()}
        return events, summary

    def test_short_excursion_is_not_a_move(self):
        self.load(panel_rows('a', 100, 'HHHNHHH'))
        events, summary = self.derive(2)
        self.assertEqual(events, [])
        self.assertEqual(summary['a'][1], 1)
        events, _ = self.derive(1)
        self.assertEqual(events, [('a', 103, 'confirmed', 'exit'), ('a', 104, 'confirmed', 'entry')])

    def test_persistent_move_dated_to_first_destination_quarter(self):
        self.load(panel_rows('a', 100, 'HHHNNNN'))
        for k in (1, 2, 4):
            events, _ = self.derive(k)
            self.assertEqual(events, [('a', 103, 'confirmed', 'exit')], k)

    def test_return_and_spell_types(self):
        self.load(panel_rows('a', 100, 'NNHHHNNNHHHH'))
        migration.derive(self.con, 'runs', 'panel', 'fallback', 2, 10 ** 6)
        rows = self.con.execute('SELECT event_q, direction, hk_spell_type, origin_country, destination_country, '
                                'same_employer FROM transitions ORDER BY event_q').fetchall()
        self.assertEqual(rows, [(102, 'entry', 'first', 'Singapore', 'Hong Kong', 'same'),
                                (105, 'exit', 'first', 'Hong Kong', 'Singapore', 'same'),
                                (108, 'entry', 'return', 'Singapore', 'Hong Kong', 'same')])

    def test_unknown_gap_breaks_inference(self):
        self.load(panel_rows('a', 100, 'HHH..NNNN'))
        events, summary = self.derive(1)
        self.assertEqual(events, [('a', 105, 'gap', 'exit')])
        self.load(panel_rows('a', 100, 'HHN.NNNN'))
        events, summary = self.derive(2)
        self.assertEqual(events, [('a', 104, 'gap', 'exit')])
        self.assertEqual(summary['a'][2], 1)  # pending move before the gap

    def test_censoring_left_and_right(self):
        self.load(panel_rows('a', 100, 'HHHHN') + panel_rows('b', 100, 'NHHHH'))
        events, summary = self.derive(2)
        self.assertEqual(events, [('b', 101, 'confirmed', 'entry')])
        self.assertTrue(summary['a'][3])
        self.assertEqual(summary['a'][4], 'exit')
        # First observed status is left-censored: a one-quarter start still anchors.
        self.load(panel_rows('c', 100, 'NHH'))
        events, _ = self.derive(2)
        self.assertEqual(events, [('c', 101, 'confirmed', 'entry')])

    def test_horizon_restricts_confirmation(self):
        self.load(panel_rows('a', 100, 'HHHHNNNN'))
        events, summary = self.derive(4, horizon=105)
        self.assertEqual(events, [])
        self.assertTrue(summary['a'][3])
        events, _ = self.derive(4, horizon=107)
        self.assertEqual(events, [('a', 104, 'confirmed', 'exit')])

    def test_matches_reference_on_random_histories(self):
        rng = random.Random(20261007)
        rows, histories = [], {}
        for person in range(600):
            length = rng.randint(1, 30)
            codes = ''.join(rng.choices('HHHNN.', k=length))
            user = f'u{person:04d}'
            rows += panel_rows(user, 200, codes)
            histories[user] = [(q, hk) for _, q, hk in panel_rows(user, 200, codes)]
        self.load(rows)
        for k in (1, 2, 4):
            for horizon in (210, 10 ** 6):
                events, summary = self.derive(k, horizon)
                for user, observations in histories.items():
                    expected = reference.classify(observations, k, horizon)
                    got_events = [(q, d) for u, q, kind, d in events if u == user and kind == 'confirmed']
                    got_gaps = [(q, d) for u, q, kind, d in events if u == user and kind == 'gap']
                    self.assertEqual(got_events, expected['events'], (user, k, horizon))
                    self.assertEqual(got_gaps, expected['gaps'], (user, k, horizon))
                    if user in summary:
                        _, excursions, before_gap, terminal, direction = summary[user]
                        self.assertEqual(excursions, expected['excursions'], (user, k))
                        self.assertEqual(before_gap, expected['unconfirmed_before_gap'], (user, k))
                        self.assertEqual(direction, expected['terminal'], (user, k))
                        self.assertEqual(terminal, expected['terminal'] is not None, (user, k))
                    else:
                        self.assertFalse([o for o in observations if o[0] <= horizon], user)


if __name__ == '__main__':
    unittest.main()
