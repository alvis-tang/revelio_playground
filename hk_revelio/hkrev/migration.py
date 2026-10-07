"""Stage 04: Hong Kong spells and persistence-confirmed migration events.

Known Hong Kong/non-Hong Kong quarters form contiguous blocks; any unknown
quarter (no active position, or no location under the specification) starts a
new block, so no transition is inferred across it. Within a block, runs of equal
status are classified for persistence k:

* the first run of a block sets the confirmed status (left-censored);
* a run of the other status lasting >= k quarters is a confirmed move dated to
  its first quarter, and becomes the confirmed status;
* a shorter run of the other status is an excursion (followed by a return in
  the same block), unconfirmed before a gap, or an unconfirmed terminal move
  (censored at the end of the record or horizon);
* a status difference between the confirmed status at the end of one block and
  the first status of the next block is an undated gap change, not an event.
"""
import shutil

from .common import SPECS, StageRun, lit, now

HK_COLUMN = {'fallback': 'hk_fallback', 'position_only': 'hk_position_only'}


def location(spec, alias):
    """(country, location source, fallback timing) SQL for a specification."""
    if spec == 'fallback':
        return (f'{alias}.loc_country_fallback', f'{alias}.loc_source_fallback', f'{alias}.fallback_timing')
    return (f'{alias}.loc_country_position_only',
            f"CASE WHEN {alias}.loc_country_position_only IS NOT NULL THEN 'position' END", 'NULL::VARCHAR')

def runs_sql(panel, spec):
    """Runs of equal Hong Kong status within contiguous known-quarter blocks."""
    hk = HK_COLUMN[spec]
    return f'''
    WITH s AS (SELECT user_id, qidx, {hk} AS hk FROM {panel} WHERE {hk} IS NOT NULL),
    a AS (SELECT *, qidx - lag(qidx) OVER w AS step, lag(hk) OVER w AS prev_hk
          FROM s WINDOW w AS (PARTITION BY user_id ORDER BY qidx)),
    b AS (SELECT *, sum(CASE WHEN step IS NULL OR step > 1 THEN 1 ELSE 0 END) OVER w AS block_no,
                    sum(CASE WHEN step IS NULL OR step > 1 OR hk <> prev_hk THEN 1 ELSE 0 END) OVER w AS run_no
          FROM a WINDOW w AS (PARTITION BY user_id ORDER BY qidx ROWS UNBOUNDED PRECEDING))
    SELECT user_id, block_no::INTEGER AS block_no, run_no::INTEGER AS run_no, any_value(hk) AS hk,
           min(qidx)::INTEGER AS start_q, max(qidx)::INTEGER AS end_q
    FROM b GROUP BY user_id, block_no, run_no'''


def classify_sql(runs, k, horizon):
    """Classify runs for persistence k using only quarters <= horizon."""
    return f'''
    WITH t AS (SELECT user_id, block_no, run_no, hk, start_q, least(end_q, {horizon}) AS end_q
               FROM {runs} WHERE start_q <= {horizon}),
    b AS (SELECT *, end_q - start_q + 1 AS len,
                 min(run_no) OVER (PARTITION BY user_id, block_no) AS first_run,
                 max(run_no) OVER (PARTITION BY user_id, block_no) AS last_run,
                 max(block_no) OVER (PARTITION BY user_id) AS last_block,
                 min(start_q) OVER (PARTITION BY user_id) AS person_first_q,
                 max(end_q) OVER (PARTITION BY user_id) AS person_last_q
          FROM t),
    c AS (SELECT *, run_no = first_run OR len >= {k} AS anchor FROM b),
    d AS (SELECT *,
                 last_value(CASE WHEN anchor THEN hk END IGNORE NULLS) OVER (
                     PARTITION BY user_id, block_no ORDER BY run_no
                     ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS confirmed_before,
                 last_value(CASE WHEN anchor THEN hk END IGNORE NULLS) OVER (
                     PARTITION BY user_id, block_no ORDER BY run_no
                     ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS block_final
          FROM c)
    SELECT *, CASE WHEN run_no = first_run THEN 'block_start'
                   WHEN hk = confirmed_before THEN 'stay'
                   WHEN len >= {k} THEN 'confirmed_move'
                   WHEN run_no < last_run THEN 'excursion'
                   WHEN block_no < last_block THEN 'unconfirmed_before_gap'
                   ELSE 'unconfirmed_terminal' END AS run_class
    FROM d'''


def derive(con, runs, panel, spec, k, horizon):
    """Create temp tables cls, transitions, summary for one spec/k/horizon."""
    con.execute(f'CREATE OR REPLACE TEMP TABLE cls AS {classify_sql(runs, k, horizon)}')
    con.execute('''CREATE OR REPLACE TEMP TABLE blocks AS
        SELECT user_id, block_no, min(start_q) AS block_start, max(end_q) AS block_end,
               any_value(hk) FILTER (WHERE run_no = first_run) AS initial_hk, any_value(block_final) AS block_final
        FROM cls GROUP BY user_id, block_no''')
    oc, osrc, otime = location(spec, 'og')
    dc, dsrc, dtime = location(spec, 'de')
    con.execute(f'''CREATE OR REPLACE TEMP TABLE transitions AS
        WITH moves AS (
            SELECT * EXCLUDE (run_class) FROM (
                SELECT user_id, start_q AS event_q, start_q - 1 AS origin_q, 'confirmed' AS kind,
                       CASE WHEN hk THEN 'entry' ELSE 'exit' END AS direction, len AS destination_run_quarters,
                       NULL::BIGINT AS gap_quarters, block_no, run_class,
                       coalesce(sum(CASE WHEN run_class = 'confirmed_move' THEN 1 ELSE 0 END) OVER (
                           PARTITION BY user_id, block_no ORDER BY run_no
                           ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS prior_moves_in_block
                FROM cls) WHERE run_class = 'confirmed_move'),
        gaps AS (
            SELECT user_id, block_start AS event_q, prev_end AS origin_q, 'gap' AS kind,
                   CASE WHEN initial_hk THEN 'entry' ELSE 'exit' END AS direction,
                   NULL::BIGINT AS destination_run_quarters, block_start - prev_end - 1 AS gap_quarters, block_no,
                   NULL::BIGINT AS prior_moves_in_block
            FROM (SELECT *, lag(block_final) OVER w AS prev_final, lag(block_end) OVER w AS prev_end
                  FROM blocks WINDOW w AS (PARTITION BY user_id ORDER BY block_no))
            WHERE prev_final IS NOT NULL AND prev_final <> initial_hk),
        u AS (SELECT * FROM moves UNION ALL BY NAME SELECT * FROM gaps),
        first_hk AS (SELECT user_id, min(start_q) FILTER (WHERE hk) AS first_hk_q FROM cls GROUP BY 1),
        o AS (SELECT u.*, coalesce(sum(CASE WHEN direction = 'exit' THEN 1 ELSE 0 END) OVER (
                         PARTITION BY u.user_id ORDER BY event_q ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0)
                         AS prior_exits, f.first_hk_q
              FROM u JOIN first_hk f USING (user_id))
        SELECT o.user_id, o.event_q, o.origin_q, o.kind, o.direction, o.destination_run_quarters, o.gap_quarters,
               o.block_no, o.prior_moves_in_block,
               CASE WHEN o.direction = 'entry' THEN CASE WHEN o.event_q = o.first_hk_q THEN 'first' ELSE 'return' END
                    ELSE CASE WHEN o.prior_exits = 0 THEN 'first' ELSE 'return' END END AS hk_spell_type,
               {oc} AS origin_country, {dc} AS destination_country,
               {osrc} AS origin_location_source, {dsrc} AS destination_location_source,
               {otime} AS origin_fallback_timing, {dtime} AS destination_fallback_timing,
               og.primary_parent_rcid AS origin_parent_rcid, de.primary_parent_rcid AS destination_parent_rcid,
               og.primary_rcid AS origin_rcid, de.primary_rcid AS destination_rcid,
               CASE WHEN og.primary_parent_rcid IS NULL OR de.primary_parent_rcid IS NULL THEN 'unknown'
                    WHEN og.primary_parent_rcid = de.primary_parent_rcid THEN 'same' ELSE 'different' END AS same_employer,
               CASE WHEN og.primary_rcid IS NULL OR de.primary_rcid IS NULL THEN 'unknown'
                    WHEN og.primary_rcid = de.primary_rcid THEN 'same' ELSE 'different' END AS same_rcid
        FROM o
        LEFT JOIN {panel} og ON og.user_id = o.user_id AND og.qidx = o.origin_q
        LEFT JOIN {panel} de ON de.user_id = o.user_id AND de.qidx = o.event_q''')
    con.execute('''CREATE OR REPLACE TEMP TABLE summary AS
        WITH g AS (SELECT user_id, count(*) FILTER (WHERE kind = 'gap' AND direction = 'entry') AS gap_entries,
                          count(*) FILTER (WHERE kind = 'gap' AND direction = 'exit') AS gap_exits
                   FROM transitions GROUP BY 1)
        SELECT c.user_id, min(start_q) AS first_q, max(end_q) AS last_q, max(block_no) AS n_blocks,
               any_value(hk) FILTER (WHERE block_no = 1 AND run_no = first_run) AS initial_hk,
               any_value(block_final) FILTER (WHERE block_no = last_block) AS final_confirmed_hk,
               count(*) FILTER (WHERE run_class = 'confirmed_move' AND hk) AS entries,
               count(*) FILTER (WHERE run_class = 'confirmed_move' AND NOT hk) AS exits,
               count(*) FILTER (WHERE run_class = 'excursion') AS excursions,
               count(*) FILTER (WHERE run_class = 'unconfirmed_before_gap') AS unconfirmed_before_gap,
               coalesce(bool_or(run_class = 'unconfirmed_terminal'), false) AS terminal_unconfirmed,
               any_value(CASE WHEN hk THEN 'entry' ELSE 'exit' END) FILTER (WHERE run_class = 'unconfirmed_terminal')
                   AS terminal_pending_direction,
               sum(len) FILTER (WHERE hk) AS hk_quarters, sum(len) FILTER (WHERE NOT hk) AS non_hk_quarters,
               coalesce(any_value(g.gap_entries), 0) AS gap_entries, coalesce(any_value(g.gap_exits), 0) AS gap_exits
        FROM cls c LEFT JOIN g USING (user_id) GROUP BY c.user_id''')


def spells_sql(runs, horizon):
    """Contiguous Hong Kong spells (raw runs, independent of persistence)."""
    return f'''
    WITH t AS (SELECT *, min(start_q) OVER (PARTITION BY user_id) AS person_first_q,
                         max(end_q) OVER (PARTITION BY user_id) AS person_last_q,
                         min(run_no) OVER (PARTITION BY user_id, block_no) AS first_run,
                         max(run_no) OVER (PARTITION BY user_id, block_no) AS last_run
               FROM {runs} WHERE start_q <= {horizon})
    SELECT user_id, row_number() OVER (PARTITION BY user_id ORDER BY start_q) AS spell_no, start_q, end_q,
           end_q - start_q + 1 AS quarters,
           CASE WHEN start_q = person_first_q THEN 'record_start' WHEN run_no = first_run THEN 'unknown_gap'
                ELSE 'non_hk' END AS preceded_by,
           CASE WHEN end_q = person_last_q THEN 'record_end' WHEN run_no = last_run THEN 'unknown_gap'
                ELSE 'non_hk' END AS followed_by,
           start_q = person_first_q AS left_censored, end_q = person_last_q AS right_censored,
           end_q = {horizon} AS ongoing_at_horizon
    FROM t WHERE hk'''


def panel_file(ctx, rule, bucket):
    return ctx.derived / 'person_quarter' / rule / f'bucket_{bucket:03d}.parquet'


def runs_file(ctx, bucket):
    return ctx.derived / 'migration' / 'runs' / f'bucket_{bucket:03d}.parquet'


def run(ctx):
    with StageRun(ctx, '04_migration', requires=['00_inventory', '01_clean', '02_panel']) as stage:
        out = ctx.derived / 'migration'
        shutil.rmtree(out, ignore_errors=True)
        con, _ = ctx.stage_db('04_migration')
        horizon = ctx.last_q
        created = set()
        for bucket in range(ctx.buckets):
            runs_parts = []
            for rule in ctx.end_rules:
                path = panel_file(ctx, rule, bucket)
                con.execute(f'CREATE OR REPLACE TEMP TABLE panel AS SELECT * FROM read_parquet({lit(path)})')
                for spec_name, spec in SPECS.items():
                    con.execute(f'CREATE OR REPLACE TEMP TABLE runs AS {runs_sql("panel", spec)}')
                    runs_parts.append(f"SELECT {lit(rule)} AS end_rule, {lit(spec_name)} AS spec, * FROM runs_{rule}_{spec}")
                    con.execute(f'CREATE OR REPLACE TEMP TABLE runs_{rule}_{spec} AS SELECT * FROM runs')
                    tag = f"{lit(rule)} AS end_rule, {lit(spec_name)} AS spec"
                    insert(con, 'hk_spells', f'SELECT {tag}, * FROM ({spells_sql("runs", horizon)})', created)
                    for k in ctx.ks:
                        derive(con, 'runs', 'panel', spec, k, horizon)
                        ktag = f'{tag}, {k} AS persistence_quarters, {horizon} AS horizon_q'
                        insert(con, 'transitions_all', f'SELECT {ktag}, * FROM transitions', created)
                        insert(con, 'person_summary', f'SELECT {ktag}, * FROM summary', created)
            ctx.copy(con, ' UNION ALL '.join(runs_parts), runs_file(ctx, bucket))
            print(f'[{now()}] migration bucket {bucket + 1}/{ctx.buckets}', flush=True)
        rows = {}
        for name in ('hk_spells', 'transitions_all', 'person_summary'):
            rows[name] = ctx.copy(con, f'SELECT * FROM {name}', out / f'{name}.parquet')
            stage.output(name, out / f'{name}.parquet', rows[name])
        stage.output('runs', out / 'runs')
        quarterly = ctx.copy(con, '''
            SELECT end_rule, spec, persistence_quarters, event_q AS qidx,
                   (event_q // 4)::VARCHAR || 'Q' || (event_q % 4 + 1)::VARCHAR AS quarter,
                   kind, direction, count(*) AS transitions, count(DISTINCT user_id) AS people,
                   count(*) FILTER (WHERE same_employer = 'same') AS same_employer,
                   count(*) FILTER (WHERE same_employer = 'different') AS different_employer,
                   count(*) FILTER (WHERE same_employer = 'unknown') AS unknown_employer,
                   count(*) FILTER (WHERE hk_spell_type = 'first') AS first_hk_spell,
                   count(*) FILTER (WHERE hk_spell_type = 'return') AS return_hk_spell,
                   count(*) FILTER (WHERE origin_location_source IN ('profile_fallback', 'profile_snapshot')
                                       OR destination_location_source IN ('profile_fallback', 'profile_snapshot'))
                       AS uses_profile_location
            FROM transitions_all GROUP BY ALL ORDER BY end_rule, spec, persistence_quarters, qidx, kind, direction''',
            ctx.tables / 'migration_transitions_by_quarter.csv', fmt='csv')
        stage.output('migration_transitions_by_quarter.csv', ctx.tables / 'migration_transitions_by_quarter.csv', quarterly)
        stage.summary['rows'] = rows
        stage.summary['totals'] = [dict(zip(['end_rule', 'spec', 'k', 'kind', 'direction', 'transitions', 'people'], r))
                                   for r in con.execute('''
            SELECT end_rule, spec, persistence_quarters, kind, direction, count(*), count(DISTINCT user_id)
            FROM transitions_all GROUP BY ALL ORDER BY ALL''').fetchall()]
        con.close()
        return stage.summary


def insert(con, table, query, created):
    if table in created:
        con.execute(f'INSERT INTO {table} BY NAME {query}')
    else:
        con.execute(f'CREATE OR REPLACE TABLE {table} AS {query}')
        created.add(table)
