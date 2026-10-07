"""Stage 02: quarter-end person-quarter panel under each missing-end-date rule."""
import shutil

from .common import StageRun, lit, now

PRIMARY = {
    'primary_position_id': 'position_id', 'position_country': 'country', 'position_metro_area': 'metro_area',
    'position_city': 'city', 'primary_rcid': 'rcid', 'primary_parent_rcid': 'ultimate_parent_rcid',
    'primary_title_raw': 'title_raw', 'primary_role_rule': 'role_rule_category',
    'primary_downranked': 'role_downranked', 'primary_startdate': 'startdate', 'primary_enddate': 'enddate',
    'primary_end_missing': 'open_ended', 'primary_seniority': 'seniority',
    'primary_role_k1500_v2': 'role_k1500_v2', 'primary_job_category_v2': 'job_category_v2',
}


def effective_end(ctx, rule):
    """Last month a spell counts as active (inclusive), capped at the common cutoff."""
    recorded = f'least(s.end_midx, {ctx.cutoff_midx})'
    if rule == 'carry_to_cutoff':
        missing = str(ctx.cutoff_midx)
    elif rule == 'cap_at_last_refresh':
        missing = f'least({ctx.cutoff_midx}, coalesce(u.refresh_midx, {ctx.cutoff_midx}))'
    else:
        raise ValueError(f'Unknown end rule {rule}')
    return f'CASE WHEN s.end_midx IS NOT NULL THEN {recorded} ELSE {missing} END'


def quarter_columns(column='qidx'):
    return (f"({column} // 4)::VARCHAR || 'Q' || ({column} % 4 + 1)::VARCHAR AS quarter, "
            f"({column} // 4)::SMALLINT AS year, "
            f"last_day(make_date(({column} // 4)::BIGINT, (({column} % 4) * 3 + 3)::BIGINT, 1)) AS quarter_end")


def panel_sql(ctx, rule, positions, users):
    """SELECT for one bucket's person-quarter rows (position rows + profile snapshots)."""
    hk = lit(ctx.hk)
    picks = ',\n'.join(f'any_value({src}) FILTER (WHERE rk = 1) AS {dst}' for dst, src in PRIMARY.items())
    location = f'''
        CASE WHEN g.position_country IS NOT NULL THEN g.position_country ELSE u.user_country END AS loc_country_fallback,
        CASE WHEN g.position_country IS NOT NULL THEN 'position'
             WHEN u.user_country IS NOT NULL THEN 'profile_fallback' END AS loc_source_fallback,
        CASE WHEN g.position_country IS NULL AND u.user_country IS NOT NULL THEN
             CASE WHEN g.qidx = u.refresh_qidx THEN 'snapshot' WHEN g.qidx < u.refresh_qidx THEN 'backcast'
                  ELSE 'forwardcast' END END AS fallback_timing,
        g.position_country AS loc_country_position_only'''
    return f'''
    WITH s AS (SELECT * FROM {positions}),
    e AS (SELECT s.*, {effective_end(ctx, rule)} AS eff_end_midx FROM s LEFT JOIN {users} u USING (user_id)),
    a AS (SELECT e.*, unnest(range(greatest(e.start_midx // 3, {ctx.panel_start_q}),
                                   least((e.eff_end_midx - 2) // 3, {ctx.last_q}) + 1)) AS qidx FROM e),
    r AS (SELECT a.*,
                 row_number() OVER (PARTITION BY user_id, qidx ORDER BY role_downranked, start_midx DESC, position_id) AS rk,
                 row_number() OVER (PARTITION BY user_id, qidx ORDER BY start_midx DESC, position_id) AS rk_naive
          FROM a),
    g AS (SELECT user_id, qidx,
                 count(*)::SMALLINT AS n_active,
                 count(*) FILTER (WHERE role_downranked)::SMALLINT AS n_active_downranked,
                 count(*) FILTER (WHERE country = {hk})::SMALLINT AS n_active_hk,
                 count(*) FILTER (WHERE country IS NULL)::SMALLINT AS n_active_missing_country,
                 count(DISTINCT country)::SMALLINT AS n_active_countries,
                 list(DISTINCT country) FILTER (WHERE rk > 1 AND country IS NOT NULL) AS other_countries,
                 any_value(position_id) FILTER (WHERE rk_naive = 1) AS naive_position_id,
                 any_value(country) FILTER (WHERE rk_naive = 1) AS naive_country,
                 {picks}
          FROM r GROUP BY user_id, qidx)
    SELECT g.user_id, {lit(rule)} AS end_rule, g.qidx, {quarter_columns('g.qidx')}, 'position' AS obs_type,
           g.n_active, g.n_active_downranked, g.n_active_hk, g.n_active_missing_country, g.n_active_countries,
           g.n_active_countries > 1 AS country_conflict,
           array_sort(list_filter(coalesce(g.other_countries, []), x -> x IS DISTINCT FROM g.position_country)) AS alt_countries,
           g.n_active_hk > 0 AS any_active_hk,
           g.primary_position_id IS DISTINCT FROM g.naive_position_id AS downrank_changed_primary,
           g.naive_country IS DISTINCT FROM g.position_country AS downrank_changed_country,
           {', '.join(f'g.{c}' for c in PRIMARY)},
           u.user_country AS profile_country, u.updated_dt AS profile_updated_dt, u.refresh_qidx AS profile_refresh_qidx,
           {location}
    FROM g LEFT JOIN {users} u USING (user_id)
    UNION ALL BY NAME
    SELECT u.user_id, {lit(rule)} AS end_rule, u.refresh_qidx AS qidx, {quarter_columns('u.refresh_qidx')},
           'profile_snapshot' AS obs_type, 0::SMALLINT AS n_active, 0::SMALLINT AS n_active_downranked,
           0::SMALLINT AS n_active_hk, 0::SMALLINT AS n_active_missing_country, 0::SMALLINT AS n_active_countries,
           false AS country_conflict, []::VARCHAR[] AS alt_countries, false AS any_active_hk,
           false AS downrank_changed_primary, false AS downrank_changed_country,
           u.user_country AS profile_country, u.updated_dt AS profile_updated_dt, u.refresh_qidx AS profile_refresh_qidx,
           u.user_country AS loc_country_fallback,
           CASE WHEN u.user_country IS NOT NULL THEN 'profile_snapshot' END AS loc_source_fallback,
           CASE WHEN u.user_country IS NOT NULL THEN 'snapshot' END AS fallback_timing,
           NULL::VARCHAR AS loc_country_position_only
    FROM {users} u
    WHERE u.profile_only AND u.refresh_qidx BETWEEN {ctx.panel_start_q} AND {ctx.last_q}'''


def finish_sql(body, hk):
    return f'''SELECT *, loc_country_fallback = {lit(hk)} AS hk_fallback,
                      loc_country_position_only = {lit(hk)} AS hk_position_only
               FROM ({body}) ORDER BY user_id, qidx'''


def bucket_path(ctx, rule, bucket):
    return ctx.derived / 'person_quarter' / rule / f'bucket_{bucket:03d}.parquet'


def read_bucket(ctx, name, bucket):
    """SELECT for one hash bucket of a stage-01 output (empty with schema if absent)."""
    folder = ctx.derived / name / f'bucket={bucket}'
    if folder.exists():
        return f"SELECT * FROM read_parquet({lit(str(folder) + '/*.parquet')}, hive_partitioning=false)"
    return f"SELECT * FROM read_parquet({lit(str(ctx.derived / name) + '/*/*.parquet')}, hive_partitioning=false) LIMIT 0"


def run(ctx):
    with StageRun(ctx, '02_panel', requires=['00_inventory', '01_clean']) as stage:
        shutil.rmtree(ctx.derived / 'person_quarter', ignore_errors=True)
        con = ctx.connect()
        totals = {rule: {'rows': 0, 'position_rows': 0, 'snapshot_rows': 0, 'people': 0} for rule in ctx.end_rules}
        for bucket in range(ctx.buckets):
            con.execute('DROP TABLE IF EXISTS p; DROP TABLE IF EXISTS u')
            con.execute(f"CREATE TEMP TABLE p AS {read_bucket(ctx, 'positions_clean', bucket)}")
            con.execute(f"CREATE TEMP TABLE u AS {read_bucket(ctx, 'users_clean', bucket)}")
            for rule in ctx.end_rules:
                path = bucket_path(ctx, rule, bucket)
                rows = ctx.copy(con, finish_sql(panel_sql(ctx, rule, 'p', 'u'), ctx.hk), path)
                dup, people, position_rows, snapshot_rows = con.execute(
                    f"SELECT count(*) - count(DISTINCT (user_id, qidx)), count(DISTINCT user_id), "
                    f"count(*) FILTER (WHERE obs_type = 'position'), count(*) FILTER (WHERE obs_type = 'profile_snapshot') "
                    f"FROM read_parquet({lit(path)})").fetchone()
                if dup:
                    raise RuntimeError(f'{path}: {dup} duplicate person-quarter keys')
                for key, value in zip(('rows', 'people', 'position_rows', 'snapshot_rows'),
                                      (rows, people, position_rows, snapshot_rows)):
                    totals[rule][key] += value
            print(f'[{now()}] panel bucket {bucket + 1}/{ctx.buckets}: '
                  + ', '.join(f"{r}={totals[r]['rows']:,}" for r in ctx.end_rules), flush=True)
        users = f"read_parquet({lit(str(ctx.derived / 'users_clean') + '/*/*.parquet')})"
        partial_profile_only = con.execute(
            f'SELECT count(*) FILTER (WHERE profile_only AND refresh_qidx > {ctx.last_q}), '
            f'count(*) FILTER (WHERE profile_only AND refresh_qidx < {ctx.panel_start_q}), '
            f'count(*) FILTER (WHERE profile_only AND refresh_qidx IS NULL), '
            f'count(*) FILTER (WHERE profile_only AND refresh_qidx BETWEEN {ctx.panel_start_q} AND {ctx.last_q}) '
            f'FROM {users}').fetchone()
        stage.summary.update(rows=totals, profile_only=dict(zip(
            ['refresh_in_partial_or_later_quarter', 'refresh_before_panel_start', 'no_refresh_date',
             'snapshot_in_complete_quarter'], partial_profile_only)))
        for rule in ctx.end_rules:
            stage.output(f'person_quarter/{rule}', ctx.derived / 'person_quarter' / rule, totals[rule]['rows'])
        return stage.summary
