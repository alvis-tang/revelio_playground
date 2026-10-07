"""Stage 05: approximate replication of Hong Kong talent flows and the inspection sample."""
import hashlib
import shutil

from .common import SPECS, StageRun, lit, now, qidx, qlabel, save_json
from .migration import derive, location

PROFILE = "('profile_fallback', 'profile_snapshot')"
NOTE_ENDPOINT = ('Approximate: endpoint rule inferred (paper code unpublished); retrospective reconstruction from the '
                 '2026 extract, not the October 2023 snapshot.')
NOTE_EVENTS = ('Quarterly events confirmed within the window (k consecutive known quarters, horizon = window end); '
               'status changes across unknown gaps are excluded and reported as gap rows.')


def endpoint_sql(panel, spec, start, end):
    hk = {'fallback': 'hk_fallback', 'position_only': 'hk_position_only'}[spec]
    country, source, timing = location(spec, 'p')
    span = end - start + 1
    return f'''
    WITH w AS (SELECT p.user_id, p.qidx, p.{hk} AS hk, {country} AS country, {source} AS source, {timing} AS timing,
                      p.primary_parent_rcid AS parent, p.primary_rcid AS rcid
               FROM {panel} p WHERE p.qidx BETWEEN {start} AND {end}),
    a AS (SELECT user_id,
                 any_value(hk) FILTER (WHERE qidx = {start}) AS start_hk, any_value(hk) FILTER (WHERE qidx = {end}) AS end_hk,
                 any_value(country) FILTER (WHERE qidx = {start}) AS start_country,
                 any_value(country) FILTER (WHERE qidx = {end}) AS end_country,
                 any_value(source) FILTER (WHERE qidx = {start}) AS start_source,
                 any_value(source) FILTER (WHERE qidx = {end}) AS end_source,
                 any_value(timing) FILTER (WHERE qidx = {start}) AS start_fallback_timing,
                 any_value(timing) FILTER (WHERE qidx = {end}) AS end_fallback_timing,
                 any_value(parent) FILTER (WHERE qidx = {start}) AS start_parent_rcid,
                 any_value(parent) FILTER (WHERE qidx = {end}) AS end_parent_rcid,
                 any_value(rcid) FILTER (WHERE qidx = {start}) AS start_rcid,
                 any_value(rcid) FILTER (WHERE qidx = {end}) AS end_rcid,
                 count(*) FILTER (WHERE hk) AS hk_quarters, count(*) FILTER (WHERE NOT hk) AS non_hk_quarters,
                 {span} - count(hk) AS unknown_quarters
          FROM w GROUP BY user_id)
    SELECT *,
           CASE WHEN start_hk IS NULL OR end_hk IS NULL THEN 'unclassified'
                WHEN start_hk AND end_hk THEN 'stayed' WHEN end_hk THEN 'entered'
                WHEN start_hk THEN 'departed' ELSE 'outside_hk_at_both' END AS endpoint_class,
           CASE WHEN start_hk AND end_hk THEN CASE WHEN non_hk_quarters > 0 THEN 'round_trip_out'
                                                   WHEN unknown_quarters > 0 THEN 'hk_with_unknown_quarters'
                                                   ELSE 'continuous_hk' END
                WHEN NOT start_hk AND NOT end_hk THEN CASE WHEN hk_quarters > 0 THEN 'round_trip_in' ELSE 'no_hk_quarter' END
                WHEN start_hk IS NULL AND end_hk IS NULL THEN 'unknown_both_endpoints'
                WHEN start_hk IS NULL THEN 'unknown_start' WHEN end_hk IS NULL THEN 'unknown_end' END AS endpoint_path,
           CASE WHEN start_parent_rcid IS NULL OR end_parent_rcid IS NULL THEN 'unknown'
                WHEN start_parent_rcid = end_parent_rcid THEN 'same' ELSE 'different' END AS same_company,
           CASE WHEN start_rcid IS NULL OR end_rcid IS NULL THEN 'unknown'
                WHEN start_rcid = end_rcid THEN 'same' ELSE 'different' END AS same_rcid,
           coalesce(start_source IN {PROFILE} OR end_source IN {PROFILE}, false) AS uses_profile_location
    FROM a'''


def run(ctx):
    with StageRun(ctx, '05_replication',
                  requires=['00_inventory', '01_clean', '02_panel', '04_migration']) as stage:
        out = ctx.derived / 'replication'
        shutil.rmtree(out, ignore_errors=True)
        con, _ = ctx.stage_db('05_replication')
        windows = {name: (qidx(w['start']), qidx(w['end'])) for name, w in ctx.config['replication']['windows'].items()}
        created = set()
        for bucket in range(ctx.buckets):
            runs = ctx.derived / 'migration' / 'runs' / f'bucket_{bucket:03d}.parquet'
            con.execute(f'CREATE OR REPLACE TEMP TABLE runs_all AS SELECT * FROM read_parquet({lit(runs)})')
            for rule in ctx.end_rules:
                panel = ctx.derived / 'person_quarter' / rule / f'bucket_{bucket:03d}.parquet'
                con.execute(f'CREATE OR REPLACE TEMP TABLE panel AS SELECT * FROM read_parquet({lit(panel)})')
                for spec_name, spec in SPECS.items():
                    con.execute(f'CREATE OR REPLACE TEMP TABLE runs AS SELECT * EXCLUDE (end_rule, spec) FROM runs_all '
                                f'WHERE end_rule = {lit(rule)} AND spec = {lit(spec_name)}')
                    for window, (start, end) in windows.items():
                        tag = f"{lit(window)} AS window_name, {lit(rule)} AS end_rule, {lit(spec_name)} AS location_spec"
                        con.execute(f'CREATE OR REPLACE TEMP TABLE ep AS {endpoint_sql("panel", spec, start, end)}')
                        for k in ctx.ks:
                            derive(con, 'runs', 'panel', spec, k, end)
                            con.execute(f'''CREATE OR REPLACE TEMP TABLE ev{k} AS
                                SELECT user_id,
                                       count(*) FILTER (WHERE kind = 'confirmed' AND direction = 'entry') AS entries_k{k},
                                       count(*) FILTER (WHERE kind = 'confirmed' AND direction = 'exit') AS exits_k{k},
                                       count(*) FILTER (WHERE kind = 'gap' AND direction = 'entry') AS gap_entries_k{k},
                                       count(*) FILTER (WHERE kind = 'gap' AND direction = 'exit') AS gap_exits_k{k}
                                FROM transitions WHERE event_q > {start} AND event_q <= {end} GROUP BY 1''')
                            con.execute(f'''CREATE OR REPLACE TEMP TABLE tm{k} AS SELECT user_id,
                                terminal_unconfirmed AS terminal_unconfirmed_k{k}, excursions AS excursions_k{k}
                                FROM summary''')
                            insert(con, 'window_transitions', f'''
                                SELECT {tag}, {k} AS persistence_quarters, * FROM transitions
                                WHERE event_q > {start} AND event_q <= {end}''', created)
                        joins = ' '.join(f'LEFT JOIN ev{k} USING (user_id) LEFT JOIN tm{k} USING (user_id)' for k in ctx.ks)
                        fills = ', '.join(f'coalesce(entries_k{k}, 0) AS entries_k{k}, coalesce(exits_k{k}, 0) AS exits_k{k}, '
                                          f'coalesce(gap_entries_k{k}, 0) AS gap_entries_k{k}, '
                                          f'coalesce(gap_exits_k{k}, 0) AS gap_exits_k{k}, '
                                          f'coalesce(terminal_unconfirmed_k{k}, false) AS terminal_unconfirmed_k{k}, '
                                          f'coalesce(excursions_k{k}, 0) AS excursions_k{k}' for k in ctx.ks)
                        drop = ', '.join(f'entries_k{k}, exits_k{k}, gap_entries_k{k}, gap_exits_k{k}, '
                                         f'terminal_unconfirmed_k{k}, excursions_k{k}' for k in ctx.ks)
                        insert(con, 'endpoint', f'SELECT {tag}, * EXCLUDE ({drop}), {fills} FROM ep {joins}', created)
            print(f'[{now()}] replication bucket {bucket + 1}/{ctx.buckets}', flush=True)
        rows = ctx.copy(con, 'SELECT * FROM endpoint', out / 'endpoint_classification.parquet')
        stage.output('endpoint_classification', out / 'endpoint_classification.parquet', rows)
        trows = ctx.copy(con, 'SELECT * FROM window_transitions', out / 'window_transitions.parquet')
        stage.output('window_transitions', out / 'window_transitions.parquet', trows)
        summary_rows = summarize(ctx, con, windows)
        stage.output('replication_summary.csv', ctx.tables / 'replication_summary.csv', summary_rows)
        sample = export_sample(ctx, con)
        stage.output('person_quarter_sample.parquet', ctx.derived / 'person_quarter_sample.parquet', sample['rows'])
        stage.summary.update(sample=sample, replication_rows=summary_rows, primary=primary_view(ctx, con))
        con.close()
        return stage.summary


def insert(con, table, query, created):
    if table in created:
        con.execute(f'INSERT INTO {table} BY NAME {query}')
    else:
        con.execute(f'CREATE OR REPLACE TABLE {table} AS {query}')
        created.add(table)


def summarize(ctx, con, windows):
    rep = ctx.config['replication']
    narrative, table3 = rep['benchmarks']['narrative'], rep['benchmarks']['table3']
    con.execute('''CREATE OR REPLACE TEMP TABLE rs (window_name VARCHAR, end_rule VARCHAR, location_spec VARCHAR,
        method VARCHAR, persistence_quarters INTEGER, measure VARCHAR, estimate BIGINT, note VARCHAR)''')

    def add(query):
        con.execute(f'INSERT INTO rs BY NAME {query}')

    keys = 'window_name, end_rule, location_spec'
    endpoint = {
        'stayed': "endpoint_class = 'stayed'", 'entered': "endpoint_class = 'entered'",
        'departed': "endpoint_class = 'departed'", 'outside_hk_at_both': "endpoint_class = 'outside_hk_at_both'",
        'classified_hk_linked_total': "endpoint_class IN ('stayed', 'entered', 'departed')",
        'stayed_continuous_hk': "endpoint_path = 'continuous_hk'",
        'stayed_hk_with_unknown_quarters': "endpoint_path = 'hk_with_unknown_quarters'",
        'stayed_round_trip_out': "endpoint_path = 'round_trip_out'",
        'outside_round_trip_in': "endpoint_path = 'round_trip_in'",
        'unclassified_hk_at_start_unknown_at_end': "endpoint_class = 'unclassified' AND start_hk AND end_hk IS NULL",
        'unclassified_unknown_at_start_hk_at_end': "endpoint_class = 'unclassified' AND end_hk AND start_hk IS NULL",
        'unclassified_unknown_both_any_hk_quarter': "endpoint_path = 'unknown_both_endpoints' AND hk_quarters > 0",
    }
    for cls in ('stayed', 'entered', 'departed'):
        for status in ('same', 'different', 'unknown'):
            endpoint[f'{cls}_{status}_company'] = f"endpoint_class = '{cls}' AND same_company = '{status}'"
            endpoint[f'{cls}_{status}_rcid'] = f"endpoint_class = '{cls}' AND same_rcid = '{status}'"
        endpoint[f'{cls}_using_profile_location'] = f"endpoint_class = '{cls}' AND uses_profile_location"
        endpoint[f'{cls}_profile_backcast_at_endpoint'] = (
            f"endpoint_class = '{cls}' AND 'backcast' IN (coalesce(start_fallback_timing, ''), coalesce(end_fallback_timing, ''))")
    for measure, condition in endpoint.items():
        add(f'''SELECT {keys}, 'endpoint' AS method, {lit(measure)} AS measure,
                       count(*) FILTER (WHERE {condition}) AS estimate, {lit(NOTE_ENDPOINT)} AS note
                FROM endpoint GROUP BY ALL''')
    add(f'''SELECT {keys}, 'endpoint' AS method, 'net' AS measure,
                   count(*) FILTER (WHERE endpoint_class = 'entered') - count(*) FILTER (WHERE endpoint_class = 'departed') AS estimate,
                   {lit(NOTE_ENDPOINT)} AS note FROM endpoint GROUP BY ALL''')
    events = {
        'entries': "kind = 'confirmed' AND direction = 'entry'", 'exits': "kind = 'confirmed' AND direction = 'exit'",
        'gap_entries_undated': "kind = 'gap' AND direction = 'entry'", 'gap_exits_undated': "kind = 'gap' AND direction = 'exit'",
    }
    for status in ('same', 'different', 'unknown'):
        events[f'entries_{status}_company'] = f"kind = 'confirmed' AND direction = 'entry' AND same_employer = '{status}'"
        events[f'exits_{status}_company'] = f"kind = 'confirmed' AND direction = 'exit' AND same_employer = '{status}'"
    for spell in ('first', 'return'):
        events[f'entries_{spell}_hk_spell'] = f"kind = 'confirmed' AND direction = 'entry' AND hk_spell_type = '{spell}'"
        events[f'exits_{spell}_hk_spell'] = f"kind = 'confirmed' AND direction = 'exit' AND hk_spell_type = '{spell}'"
    events['events_using_profile_location'] = (f"kind = 'confirmed' AND (origin_location_source IN {PROFILE} "
                                               f"OR destination_location_source IN {PROFILE})")
    for measure, condition in events.items():
        add(f'''SELECT {keys}, 'quarterly_events' AS method, persistence_quarters, {lit(measure)} AS measure,
                       count(*) FILTER (WHERE {condition}) AS estimate, {lit(NOTE_EVENTS)} AS note
                FROM window_transitions GROUP BY ALL''')
    add(f'''SELECT {keys}, 'quarterly_events' AS method, persistence_quarters, 'net_events' AS measure,
                   count(*) FILTER (WHERE kind = 'confirmed' AND direction = 'entry')
                   - count(*) FILTER (WHERE kind = 'confirmed' AND direction = 'exit') AS estimate,
                   {lit(NOTE_EVENTS)} AS note FROM window_transitions GROUP BY ALL''')
    for k in ctx.ks:
        people = {
            'people_with_entry': f'entries_k{k} > 0', 'people_with_exit': f'exits_k{k} > 0',
            'people_censored_unconfirmed_at_window_end': f'terminal_unconfirmed_k{k}',
            'people_with_excursion': f'excursions_k{k} > 0',
            'stayed_with_confirmed_exit': f"endpoint_class = 'stayed' AND exits_k{k} > 0",
            'entered_with_confirmed_entry': f"endpoint_class = 'entered' AND entries_k{k} > 0",
            'entered_via_gap_only': f"endpoint_class = 'entered' AND entries_k{k} = 0 AND gap_entries_k{k} > 0",
            'departed_with_confirmed_exit': f"endpoint_class = 'departed' AND exits_k{k} > 0",
            'departed_via_gap_only': f"endpoint_class = 'departed' AND exits_k{k} = 0 AND gap_exits_k{k} > 0",
            'departed_censored_unconfirmed': f"endpoint_class = 'departed' AND exits_k{k} = 0 AND gap_exits_k{k} = 0",
        }
        for measure, condition in people.items():
            add(f'''SELECT {keys}, 'quarterly_events' AS method, {k} AS persistence_quarters, {lit(measure)} AS measure,
                           count(*) FILTER (WHERE {condition}) AS estimate,
                           'People (not events); confirmation horizon = window end.' AS note
                    FROM endpoint GROUP BY ALL''')
    bench = {'stayed': narrative['stayed'], 'entered': narrative['entered'], 'departed': narrative['departed'],
             'net': narrative['net']}
    con.execute('CREATE OR REPLACE TEMP TABLE bench (measure VARCHAR, benchmark BIGINT, benchmark_source VARCHAR)')
    for measure, value in bench.items():
        con.execute('INSERT INTO bench VALUES (?, ?, ?)', [measure, value, narrative['source']])
    for measure, value in table3['cells'].items():
        con.execute('INSERT INTO bench VALUES (?, ?, ?)', [measure, value, table3['source']])
    # Benchmark consistency rows: the paper's Table 3 totals differ from its narrative counts.
    for cls in ('stayed', 'entered', 'departed'):
        total = table3['cells'][f'{cls}_same_company'] + table3['cells'][f'{cls}_different_company']
        con.execute('''INSERT INTO rs BY NAME SELECT 'paper' AS window_name, NULL AS end_rule, NULL AS location_spec,
                       'benchmark_consistency' AS method, ? AS measure, ? AS estimate, ? AS note''',
                    [f'table3_total_{cls}', total, f'Sum of Table 3 {cls} cells compared with the narrative {cls} count; '
                     'preserved as published, not reconciled.'])
        con.execute('INSERT INTO bench VALUES (?, ?, ?)', [f'table3_total_{cls}', narrative[cls], narrative['source']])
    for item in rep.get('unavailable', []):
        con.execute('''INSERT INTO rs BY NAME SELECT 'all' AS window_name, 'unavailable' AS method, ? AS measure, ? AS note''',
                    [item['measure'], item['reason']])
    primary_window = next(iter(ctx.config['replication']['windows']))
    primary_spec = next(k for k, v in ctx.config['location']['specifications'].items() if v.get('primary'))
    spans = ' '.join(f"WHEN {lit(n)} THEN {lit(qlabel(s) + '-' + qlabel(e))}" for n, (s, e) in windows.items())
    query = f'''
        SELECT r.window_name, CASE r.window_name {spans} END AS window_quarters, r.end_rule, r.location_spec, r.method,
               r.persistence_quarters, r.measure, r.estimate,
               CASE WHEN r.method IN ('endpoint', 'benchmark_consistency') THEN b.benchmark END AS benchmark,
               CASE WHEN r.method IN ('endpoint', 'benchmark_consistency') THEN b.benchmark_source END AS benchmark_source,
               CASE WHEN r.method IN ('endpoint', 'benchmark_consistency') THEN r.estimate - b.benchmark END AS difference,
               CASE WHEN r.method IN ('endpoint', 'benchmark_consistency') AND b.benchmark <> 0
                    THEN round(r.estimate / b.benchmark, 4) END AS ratio_to_benchmark,
               coalesce(r.window_name = {lit(primary_window)} AND r.end_rule = {lit(ctx.primary_rule)}
                        AND r.location_spec = {lit(primary_spec)} AND r.method = 'endpoint', false) AS primary_specification,
               r.note
        FROM rs r LEFT JOIN bench b USING (measure)
        ORDER BY r.method = 'unavailable', r.method = 'benchmark_consistency', r.window_name, r.end_rule, r.location_spec,
                 r.method, r.persistence_quarters NULLS FIRST, r.measure'''
    return ctx.copy(con, query, ctx.tables / 'replication_summary.csv', fmt='csv')


def primary_view(ctx, con):
    window = next(iter(ctx.config['replication']['windows']))
    spec = next(k for k, v in ctx.config['location']['specifications'].items() if v.get('primary'))
    rows = con.execute(f'''SELECT measure, estimate FROM rs WHERE window_name = {lit(window)} AND end_rule = {lit(ctx.primary_rule)}
                           AND location_spec = {lit(spec)} AND method = 'endpoint'
                           AND measure IN ('stayed', 'entered', 'departed', 'net')''').fetchall()
    return dict(rows)


def export_sample(ctx, con):
    settings = ctx.config['sampling']
    rule_dir = ctx.derived / 'person_quarter'
    primary = f"read_parquet({lit(str(rule_dir / ctx.primary_rule) + '/*.parquet')})"
    con.execute(f'''CREATE OR REPLACE TEMP TABLE sample_people AS
        SELECT user_id, sha256({lit(settings['salt'])} || ':' || user_id) AS sample_hash,
               row_number() OVER (ORDER BY sha256({lit(settings['salt'])} || ':' || user_id), user_id) AS sample_rank
        FROM (SELECT DISTINCT user_id FROM {primary})
        QUALIFY sample_rank <= {int(settings['max_people'])}''')
    population = con.execute(f'SELECT count(DISTINCT user_id) FROM {primary}').fetchone()[0]
    transitions = f"read_parquet({lit(ctx.derived / 'migration' / 'transitions_all.parquet')})"
    flags = []
    for spec_name, spec in SPECS.items():
        for k in ctx.ks:
            flags.append(f"any_value(CASE WHEN kind = 'gap' THEN 'gap_' || direction ELSE direction END) "
                         f"FILTER (WHERE spec = {lit(spec_name)} AND persistence_quarters = {k}) AS transition_{spec}_k{k}")
    panels = ' UNION ALL BY NAME '.join(
        f"SELECT * FROM read_parquet({lit(str(rule_dir / rule) + '/*.parquet')}) WHERE user_id IN (SELECT user_id FROM sample_people)"
        for rule in ctx.end_rules)
    query = f'''
        WITH p AS ({panels}),
        span AS (SELECT user_id, end_rule, min(qidx) AS first_q, max(qidx) AS last_q FROM p GROUP BY ALL),
        grid AS (SELECT user_id, end_rule, unnest(range(first_q, last_q + 1)) AS qidx FROM span),
        t AS (SELECT user_id, end_rule, event_q AS qidx, {', '.join(flags)}
              FROM {transitions} WHERE user_id IN (SELECT user_id FROM sample_people) GROUP BY ALL)
        SELECT s.sample_rank, s.sample_hash, g.user_id, g.end_rule, g.qidx,
               (g.qidx // 4)::VARCHAR || 'Q' || (g.qidx % 4 + 1)::VARCHAR AS quarter,
               coalesce(p.obs_type, 'unobserved_gap') AS obs_type,
               p.* EXCLUDE (user_id, end_rule, qidx, quarter, obs_type), t.* EXCLUDE (user_id, end_rule, qidx)
        FROM grid g JOIN sample_people s USING (user_id)
        LEFT JOIN p USING (user_id, end_rule, qidx) LEFT JOIN t USING (user_id, end_rule, qidx)
        ORDER BY s.sample_rank, g.end_rule, g.qidx'''
    path = ctx.derived / 'person_quarter_sample.parquet'
    rows = ctx.copy(con, query, path)
    ids = [r[0] for r in con.execute('SELECT user_id FROM sample_people ORDER BY sample_rank').fetchall()]
    record = {'salt': settings['salt'], 'max_people': settings['max_people'], 'population_panel_participants': population,
              'selected_people': len(ids), 'rows': rows, 'method': settings['method'],
              'selected_ids_sha256': hashlib.sha256('\n'.join(sorted(ids)).encode()).hexdigest(),
              'end_rules': ctx.end_rules, 'population_rule': ctx.primary_rule}
    save_json(ctx.derived / 'person_quarter_sample.json', record)
    return record
