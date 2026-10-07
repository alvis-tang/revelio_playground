"""Stage 03: coverage and location-missingness diagnostics."""
import json

from .common import SPECS, StageRun, lit, now

COLUMNS = ('section VARCHAR, measure VARCHAR, source_kind VARCHAR, end_rule VARCHAR, period_type VARCHAR, '
           'period VARCHAR, year INTEGER, quarter VARCHAR, country VARCHAR, country_group VARCHAR, value BIGINT, '
           'value_text VARCHAR, denominator BIGINT, share DOUBLE, is_partial_period BOOLEAN, note VARCHAR')
RETRO, SCRAPE, AUDIT = 'retrospective_employment_history', 'scrape_observation', 'join_and_quarantine_audit'


def group(column, hk):
    return (f"CASE WHEN {column} IS NULL THEN 'Missing country' WHEN {column} = {lit(hk)} THEN 'Hong Kong' "
            f"ELSE 'Other country' END")


def label(column):
    return f"({column} // 4)::VARCHAR || 'Q' || ({column} % 4 + 1)::VARCHAR"


def run(ctx):
    with StageRun(ctx, '03_diagnostics', requires=['00_inventory', '01_clean', '02_panel']) as stage:
        con = ctx.connect()
        hk, last, partial = ctx.hk, ctx.last_q, ctx.partial_q
        positions = f"read_parquet({lit(str(ctx.derived / 'positions_clean') + '/*/*.parquet')}, hive_partitioning=false)"
        users = f"read_parquet({lit(str(ctx.derived / 'users_clean') + '/*/*.parquet')}, hive_partitioning=false)"
        quarantine = f"read_parquet({lit(ctx.derived / 'positions_quarantine.parquet')})"
        con.execute(f'CREATE TEMP TABLE cov ({COLUMNS})')

        def add(query):
            con.execute(f'INSERT INTO cov BY NAME {query}')

        con.execute(f'CREATE TEMP VIEW pos AS SELECT * FROM {positions}')
        con.execute(f'CREATE TEMP VIEW usr AS SELECT * FROM {users}')
        g = group('country', hk)
        # A. Retrospective position starts and ends by year and country group.
        for measure, date in (('positions_started', 'startdate'), ('positions_ended', 'enddate')):
            add(f'''SELECT 'positions_by_year' AS section, {lit(measure)} AS measure, {lit(RETRO)} AS source_kind,
                           'year' AS period_type, year({date})::VARCHAR AS period, year({date}) AS year,
                           {g} AS country_group, count(*) AS value,
                           sum(count(*)) OVER (PARTITION BY year({date})) AS denominator
                    FROM pos WHERE {date} IS NOT NULL GROUP BY year({date}), {g}''')
        add(f'''SELECT 'positions_by_year' AS section, 'people_starting_a_position' AS measure, {lit(RETRO)} AS source_kind,
                       'year' AS period_type, year(startdate)::VARCHAR AS period, year(startdate) AS year,
                       {g} AS country_group, count(DISTINCT user_id) AS value
                FROM pos GROUP BY year(startdate), {g}''')
        # F. Missing fields among valid positions by start year.
        fields = {'country': 'country IS NULL', 'employer_rcid': 'rcid IS NULL',
                  'parent_rcid': 'ultimate_parent_rcid IS NULL', 'title': "title_status <> 'ok'",
                  'role_k17000_v3': 'role_k17000_v3 IS NULL', 'metro_area': 'metro_area IS NULL',
                  'city': 'city IS NULL', 'end_date': 'enddate IS NULL', 'seniority': 'seniority IS NULL'}
        for name, condition in fields.items():
            add(f'''SELECT 'missing_fields' AS section, {lit('missing_' + name)} AS measure, {lit(RETRO)} AS source_kind,
                           'year' AS period_type, year(startdate)::VARCHAR AS period, year(startdate) AS year,
                           'All' AS country_group, count(*) FILTER (WHERE {condition}) AS value, count(*) AS denominator
                    FROM pos GROUP BY year(startdate)''')
        # G. Quarantined (undated or invalid) spells.
        qg = group("NULLIF(trim(country), '')", hk)
        clean = json.loads((ctx.derived / 'clean_summary.json').read_text())
        all_positions = int(clean['dedupe']['positions']['rows_in'])
        people = con.execute('SELECT count(*) FILTER (WHERE n_positions > 0) FROM usr').fetchone()[0]
        for unit, value, denominator in (('positions', 'count(*)', all_positions),
                                         ('people', 'count(DISTINCT user_id)', people)):
            add(f'''SELECT 'quarantined_positions' AS section, quarantine_reason || ':{unit}' AS measure,
                           {lit(RETRO)} AS source_kind, 'all' AS period_type, 'all' AS period, {qg} AS country_group,
                           {value} AS value, {denominator} AS denominator,
                           {lit(f'denominator = all extract {unit}' if unit == 'positions' else 'denominator = people with any position')} AS note
                    FROM {quarantine} GROUP BY ALL''')
        # D. Profile refresh distribution (scrape observations, not employment history).
        pg = group('user_country', hk)
        add(f'''SELECT 'profile_refresh' AS section, 'profiles_refreshed' AS measure, {lit(SCRAPE)} AS source_kind,
                       'year' AS period_type, year(updated_dt)::VARCHAR AS period, year(updated_dt) AS year,
                       {pg} AS country_group, count(*) AS value
                FROM usr WHERE updated_dt IS NOT NULL GROUP BY ALL''')
        add(f'''SELECT 'profile_refresh' AS section, 'profiles_refreshed' AS measure, {lit(SCRAPE)} AS source_kind,
                       'month' AS period_type, strftime(updated_dt, '%Y-%m') AS period, year(updated_dt) AS year,
                       'All' AS country_group, count(*) AS value
                FROM usr WHERE updated_dt >= DATE '2024-01-01' GROUP BY ALL''')
        for p in (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99):
            add(f'''SELECT 'profile_refresh' AS section, {lit(f'updated_dt_quantile_p{round(p * 100):02d}')} AS measure,
                           {lit(SCRAPE)} AS source_kind, 'all' AS period_type, 'all' AS period, 'All' AS country_group,
                           quantile_disc(updated_dt, {p})::VARCHAR AS value_text FROM usr''')
        add(f'''SELECT 'profile_refresh' AS section, 'profile_only_people' AS measure, {lit(SCRAPE)} AS source_kind,
                       'quarter' AS period_type, {label('refresh_qidx')} AS period, (refresh_qidx // 4)::INTEGER AS year,
                       {label('refresh_qidx')} AS quarter, {pg} AS country_group, count(*) AS value,
                       refresh_qidx > {last} AS is_partial_period,
                       CASE WHEN refresh_qidx > {last} THEN 'refresh in partial quarter: reported separately, no panel row'
                            ELSE 'one dated profile snapshot row in the panel' END AS note
                FROM usr WHERE profile_only AND refresh_qidx IS NOT NULL GROUP BY ALL''')
        # Population counts.
        add(f'''SELECT 'population' AS section, unnest(['cohort_people', 'people_with_profile_row', 'people_with_any_position',
                       'people_with_valid_dated_position', 'profile_only_people', 'people_with_valid_hk_position']) AS measure,
                       {lit(SCRAPE)} AS source_kind, 'all' AS period_type, 'all' AS period, 'All' AS country_group,
                       unnest([count(*) FILTER (WHERE in_cohort), count(*) FILTER (WHERE profile_status = 'ok'),
                               count(*) FILTER (WHERE n_positions > 0), count(*) FILTER (WHERE NOT profile_only),
                               count(*) FILTER (WHERE profile_only), count(*) FILTER (WHERE n_valid_hk_positions > 0)]) AS value
                FROM usr''')
        # C/E/I. Quarterly activity, overlap effects, country-year coverage from the panel.
        for rule in ctx.end_rules:
            panel = f"read_parquet({lit(str(ctx.derived / 'person_quarter' / rule) + '/*.parquet')})"
            con.execute(f"CREATE OR REPLACE TEMP VIEW pq AS SELECT * FROM {panel} WHERE obs_type = 'position'")
            quarter = (f"'quarter' AS period_type, {label('qidx')} AS period, (qidx // 4)::INTEGER AS year, "
                       f"{label('qidx')} AS quarter, {lit(rule)} AS end_rule, {lit(RETRO)} AS source_kind")
            measures = {
                'active_positions': 'sum(n_active)', 'active_positions_hk': 'sum(n_active_hk)',
                'active_positions_missing_country': 'sum(n_active_missing_country)',
                'active_people': 'count(*)',
                'people_primary_hk': "count(*) FILTER (WHERE position_country = '{hk}')",
                'people_primary_other_country': "count(*) FILTER (WHERE position_country <> '{hk}')",
                'people_primary_missing_country': 'count(*) FILTER (WHERE position_country IS NULL)',
                'people_hk_with_profile_fallback': 'count(*) FILTER (WHERE hk_fallback)',
                'people_primary_end_date_missing': 'count(*) FILTER (WHERE primary_end_missing)',
            }
            for name, expr in measures.items():
                add(f'''SELECT 'quarterly_activity' AS section, {lit(name)} AS measure, {quarter},
                               'All' AS country_group, {expr.format(hk=hk)} AS value FROM pq GROUP BY qidx''')
            overlap = {
                'person_quarters': 'count(*)',
                'multiple_active_positions': 'count(*) FILTER (WHERE n_active > 1)',
                'conflicting_countries': 'count(*) FILTER (WHERE country_conflict)',
                'downranking_changed_primary': 'count(*) FILTER (WHERE downrank_changed_primary)',
                'downranking_changed_country': 'count(*) FILTER (WHERE downrank_changed_country)',
                'primary_is_downranked_role': 'count(*) FILTER (WHERE primary_downranked)',
                'primary_hk_with_non_hk_alternative': f"count(*) FILTER (WHERE position_country = {lit(hk)} AND len(alt_countries) > 0)",
                'primary_non_hk_with_hk_alternative': f"count(*) FILTER (WHERE position_country IS DISTINCT FROM {lit(hk)} AND any_active_hk)",
                'primary_missing_country_alternative_known': 'count(*) FILTER (WHERE position_country IS NULL AND len(alt_countries) > 0)',
                'metro_hk_but_country_not_hk': f"count(*) FILTER (WHERE position_metro_area ILIKE '%hong kong%' AND position_country IS DISTINCT FROM {lit(hk)})",
            }
            for name, expr in overlap.items():
                add(f'''SELECT 'overlap_effects' AS section, {lit(name)} AS measure, 'year' AS period_type,
                               (qidx // 4)::VARCHAR AS period, (qidx // 4)::INTEGER AS year, {lit(rule)} AS end_rule,
                               {lit(RETRO)} AS source_kind, 'All' AS country_group, {expr} AS value,
                               count(*) AS denominator, 'person-quarters summed over complete quarters' AS note
                        FROM pq GROUP BY qidx // 4''')
            if rule == ctx.primary_rule:
                add(f'''SELECT 'country_year_coverage' AS section, 'people_by_primary_position_country' AS measure,
                               'year' AS period_type, (qidx // 4)::VARCHAR AS period, (qidx // 4)::INTEGER AS year,
                               {label('qidx')} AS quarter, {lit(rule)} AS end_rule, {lit(RETRO)} AS source_kind,
                               coalesce(position_country, '(missing)') AS country, {group('position_country', hk)} AS country_group,
                               count(*) AS value, sum(count(*)) OVER (PARTITION BY qidx) AS denominator,
                               'people with an active position at the year''s last complete quarter end' AS note
                        FROM pq WHERE qidx % 4 = 3 OR qidx = {last} GROUP BY qidx, position_country''')
            # 2026 Q3 is partial: measured at the cutoff month, not a quarter end, and never ranked.
            effective = ('CASE WHEN end_midx IS NOT NULL THEN least(end_midx, {c}) ELSE {m} END'
                         .format(c=ctx.cutoff_midx, m=ctx.cutoff_midx if rule == 'carry_to_cutoff'
                                 else f'least({ctx.cutoff_midx}, coalesce(u.refresh_midx, {ctx.cutoff_midx}))'))
            for name, expr in (('active_positions', 'count(*)'), ('active_people', 'count(DISTINCT p.user_id)')):
                add(f'''SELECT 'quarterly_activity' AS section, {lit(name)} AS measure, 'quarter' AS period_type,
                               {lit(f'{partial // 4}Q{partial % 4 + 1}')} AS period, {partial // 4} AS year,
                               {lit(f'{partial // 4}Q{partial % 4 + 1}')} AS quarter, {lit(rule)} AS end_rule,
                               {lit(RETRO)} AS source_kind, {group('p.country', hk)} AS country_group, {expr} AS value,
                               true AS is_partial_period,
                               'partial quarter: active in cutoff month {ctx.cutoff}, by position country; excluded from complete-quarter results' AS note
                        FROM pos p LEFT JOIN usr u USING (user_id)
                        WHERE p.start_midx <= {ctx.cutoff_midx} AND {effective} >= {ctx.cutoff_midx} GROUP BY ALL''')
        # H. Join and quarantine audit (from stage 00 and 01 summaries).
        inventory = json.loads((ctx.diagnostics / 'inventory.json').read_text())
        for join in inventory['joins']:
            if join.get('status') != 'ok':
                continue
            for measure in ('unmatched_rows', 'left_null_key_rows', 'row_multiplication_if_naive'):
                con.execute(f'''INSERT INTO cov BY NAME SELECT 'join_coverage' AS section,
                    {lit(join['name'] + ':' + measure)} AS measure, {lit(AUDIT)} AS source_kind, 'all' AS period_type,
                    'all' AS period, 'All' AS country_group, {int(join[measure])} AS value,
                    {int(join['left_rows'])} AS denominator,
                    {lit(join['left'] + ' -> ' + join['right'])} AS note''')
        for name, value in clean['title_status'].items():
            add(f"""SELECT 'join_coverage' AS section, {lit('position_title:' + name)} AS measure, {lit(AUDIT)} AS source_kind,
                           'all' AS period_type, 'all' AS period, 'All' AS country_group, {int(value)} AS value,
                           'individual_positions -> individual_positions_raw after quarantine of conflicting raw keys' AS note""")
        for table, stats in clean['dedupe'].items():
            for name in ('exact_duplicate_rows_collapsed', 'conflicting_keys', 'rows_in_conflicting_keys', 'null_key_rows'):
                add(f"""SELECT 'duplicates' AS section, {lit(table + ':' + name)} AS measure, {lit(AUDIT)} AS source_kind,
                               'all' AS period_type, 'all' AS period, 'All' AS country_group, {int(stats[name])} AS value,
                               {int(stats['rows_in'])} AS denominator""")
        con.execute('UPDATE cov SET share = round(value / denominator, 6) WHERE denominator > 0 AND value IS NOT NULL')
        con.execute('UPDATE cov SET is_partial_period = false WHERE is_partial_period IS NULL')
        con.execute(f"UPDATE cov SET is_partial_period = true, note = coalesce(note || '; ', '') || "
                    f"'year {partial // 4} has complete quarters only through {last // 4}Q{last % 4 + 1}' "
                    f"WHERE year = {partial // 4} AND period_type = 'year'")
        coverage = ctx.copy(con, 'SELECT * FROM cov ORDER BY section, measure, end_rule, period_type, period, '
                                 'country_group, country', ctx.diagnostics / 'data_coverage_by_year.csv', fmt='csv')
        stage.output('data_coverage_by_year.csv', ctx.diagnostics / 'data_coverage_by_year.csv', coverage)
        missing = location_missingness(ctx, con)
        stage.output('location_missingness.csv', ctx.diagnostics / 'location_missingness.csv', missing)
        audit = title_audit(ctx, con)
        stage.output('title_rule_audit.csv', ctx.diagnostics / 'title_rule_audit.csv', audit)
        stage.summary.update(coverage_rows=coverage, missingness_rows=missing, title_audit_rows=audit)
        print(f'[{now()}] diagnostics written', flush=True)
        return stage.summary


def location_missingness(ctx, con):
    hk, parts = ctx.hk, []
    for rule in ctx.end_rules:
        panel = f"read_parquet({lit(str(ctx.derived / 'person_quarter' / rule) + '/*.parquet')})"
        con.execute(f'CREATE OR REPLACE TEMP TABLE span AS SELECT user_id, min(qidx) AS first_q, max(qidx) AS last_q '
                    f'FROM {panel} GROUP BY 1')
        for spec_name, spec in SPECS.items():
            country = 'loc_country_fallback' if spec == 'fallback' else 'loc_country_position_only'
            source = 'loc_source_fallback' if spec == 'fallback' else "CASE WHEN loc_country_position_only IS NOT NULL THEN 'position' END"
            parts.append(f'''
            SELECT {lit(rule)} AS end_rule, {lit(spec_name)} AS location_spec, qidx,
                   count(*) AS person_quarters, count(*) FILTER (WHERE obs_type = 'position') AS position_rows,
                   count(*) FILTER (WHERE obs_type = 'profile_snapshot') AS profile_snapshot_rows,
                   count({country}) AS known_location, count(*) FILTER (WHERE {country} = {lit(hk)}) AS hong_kong,
                   count(*) FILTER (WHERE {country} <> {lit(hk)}) AS non_hong_kong,
                   count(*) - count({country}) AS unknown_location,
                   count(position_country) AS position_country_present,
                   count(*) FILTER (WHERE obs_type = 'position' AND position_country IS NULL) AS position_country_missing,
                   count(*) FILTER (WHERE ({source}) = 'profile_snapshot') AS located_by_profile_snapshot_row,
                   count(*) FILTER (WHERE ({source}) = 'profile_fallback' AND fallback_timing = 'snapshot') AS fallback_snapshot_quarter,
                   count(*) FILTER (WHERE ({source}) = 'profile_fallback' AND fallback_timing = 'backcast') AS fallback_backcast,
                   count(*) FILTER (WHERE ({source}) = 'profile_fallback' AND fallback_timing = 'forwardcast') AS fallback_forwardcast,
                   count(*) FILTER (WHERE country_conflict) AS conflicting_country_rows,
                   count(*) FILTER (WHERE len(alt_countries) > 0) AS rows_with_alternative_country,
                   count(*) FILTER (WHERE primary_end_missing) AS rows_primary_end_date_missing
            FROM {panel} GROUP BY qidx''')
        con.execute(f'''CREATE OR REPLACE TEMP TABLE span_{rule} AS
            WITH q AS (SELECT unnest(range({ctx.panel_start_q}, {ctx.last_q} + 1)) AS qidx),
            s AS (SELECT first_q AS qidx, count(*) AS starts FROM span GROUP BY 1),
            e AS (SELECT last_q + 1 AS qidx, count(*) AS ends FROM span GROUP BY 1)
            SELECT q.qidx, sum(coalesce(s.starts, 0) - coalesce(e.ends, 0)) OVER (ORDER BY q.qidx) AS people_in_span
            FROM q LEFT JOIN s USING (qidx) LEFT JOIN e USING (qidx)''')
    con.execute(f'CREATE OR REPLACE TEMP TABLE lm AS {" UNION ALL ".join(parts)}')
    spans = ' UNION ALL '.join(f"SELECT {lit(rule)} AS end_rule, * FROM span_{rule}" for rule in ctx.end_rules)
    query = f'''
        WITH q AS (SELECT unnest(range({ctx.panel_start_q}, {ctx.last_q} + 1)) AS qidx),
        grid AS (SELECT r.end_rule, s.location_spec, q.qidx FROM q,
                 (SELECT DISTINCT end_rule FROM lm) r, (SELECT DISTINCT location_spec FROM lm) s),
        j AS (SELECT g.end_rule, g.location_spec, g.qidx, lm.* EXCLUDE (end_rule, location_spec, qidx),
                     sp.people_in_span
              FROM grid g LEFT JOIN lm USING (end_rule, location_spec, qidx)
              LEFT JOIN ({spans}) sp ON sp.end_rule = g.end_rule AND sp.qidx = g.qidx)
        SELECT end_rule, location_spec, {label('qidx')} AS quarter, (qidx // 4)::INTEGER AS year, qidx,
               COLUMNS(* EXCLUDE (end_rule, location_spec, qidx, people_in_span)),
               people_in_span - coalesce(person_quarters, 0) AS unobserved_gap_quarters_within_span,
               people_in_span
        FROM j
        UNION ALL
        SELECT end_rule, location_spec, 'all', NULL, NULL,
               sum(COLUMNS(* EXCLUDE (end_rule, location_spec, qidx, people_in_span))),
               sum(people_in_span - coalesce(person_quarters, 0)), sum(people_in_span)
        FROM j GROUP BY end_rule, location_spec
        ORDER BY end_rule, location_spec, qidx NULLS LAST'''
    con.execute(f'CREATE OR REPLACE TEMP TABLE lm_out AS {query}')
    con.execute('ALTER TABLE lm_out ADD COLUMN unknown_share_of_rows DOUBLE')
    con.execute('UPDATE lm_out SET unknown_share_of_rows = round(unknown_location / person_quarters, 6) '
                'WHERE person_quarters > 0')
    return ctx.copy(con, 'SELECT * FROM lm_out ORDER BY end_rule, location_spec, qidx NULLS LAST',
                    ctx.diagnostics / 'location_missingness.csv', fmt='csv')


def title_audit(ctx, con):
    positions = f"read_parquet({lit(str(ctx.derived / 'positions_clean') + '/*/*.parquet')}, hive_partitioning=false)"
    return ctx.copy(con, f'''
        WITH r AS (SELECT unnest(role_rule_ids) AS rule_id, lower(title_raw) AS title FROM {positions}),
        c AS (SELECT rule_id, title, count(*) AS positions FROM r GROUP BY ALL),
        t AS (SELECT rule_id, sum(positions) AS rule_positions, count(*) AS distinct_titles FROM c GROUP BY 1)
        SELECT c.rule_id, t.rule_positions, t.distinct_titles, c.title, c.positions,
               row_number() OVER (PARTITION BY c.rule_id ORDER BY c.positions DESC, c.title) AS title_rank
        FROM c JOIN t USING (rule_id) QUALIFY title_rank <= 25 ORDER BY c.rule_id, title_rank''',
        ctx.diagnostics / 'title_rule_audit.csv', fmt='csv')
