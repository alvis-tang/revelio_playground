"""Stage 01: deduplicate, quarantine, join titles/lookups/profiles, and bucket users."""
import shutil

from .common import StageRun, lit, save_json
from .titles import normalized, rule_columns

POSITION_COLUMNS = ['user_id', 'region', 'country', 'state', 'metro_area', 'msa', 'city', 'startdate', 'enddate',
                    'role_k1500_v2', 'role_k17000_v3', 'onet_code', 'remote_suitability', 'weight',
                    'start_salary', 'end_salary', 'seniority', 'salary', 'position_number', 'rcid',
                    'ultimate_parent_rcid', 'total_compensation', 'additional_compensation']
USER_COLUMNS = ['user_country', 'user_location', 'updated_dt', 'prestige', 'numconnections', 'highest_degree']


def q(name):
    return '"' + name + '"'


def dedupe(con, name, source, key, columns):
    """Collapse exact duplicates; quarantine NULL and conflicting keys.

    Creates `{name}` (one row per key) and `{name}_quarantine`; returns counts.
    Row identity uses a 64-bit hash of the projected columns.
    """
    every = ', '.join(q(c) for c in key + columns)
    keys = ', '.join(q(k) for k in key)
    null = ' OR '.join(f'{q(k)} IS NULL' for k in key)
    con.execute(f'CREATE TABLE {name}_in AS SELECT {every}, hash({every}) AS _h FROM {source}')
    con.execute(f'CREATE TABLE {name}_keys AS SELECT {keys}, count(*) AS n, count(DISTINCT _h) AS nh '
                f'FROM {name}_in WHERE NOT ({null}) GROUP BY ALL')
    con.execute(f'CREATE TABLE {name} AS SELECT DISTINCT ON ({keys}) i.* EXCLUDE (_h) FROM {name}_in i '
                f'JOIN {name}_keys k USING ({keys}) WHERE k.nh = 1 ORDER BY {keys}, i._h')
    con.execute(f'''CREATE TABLE {name}_quarantine AS
        SELECT i.* EXCLUDE (_h), 'conflicting_duplicate_key' AS quarantine_reason
        FROM {name}_in i JOIN {name}_keys k USING ({keys}) WHERE k.nh > 1
        UNION ALL SELECT * EXCLUDE (_h), 'missing_key' FROM {name}_in WHERE {null}''')
    rows, distinct_keys, collapsed, conflicting, conflicting_rows, kept = con.execute(f'''
        SELECT (SELECT count(*) FROM {name}_in), count(*), coalesce(sum(n - 1) FILTER (WHERE nh = 1), 0),
               count(*) FILTER (WHERE nh > 1), coalesce(sum(n) FILTER (WHERE nh > 1), 0),
               (SELECT count(*) FROM {name}) FROM {name}_keys''').fetchone()
    null_rows = con.execute(f'SELECT count(*) FROM {name}_in WHERE {null}').fetchone()[0]
    con.execute(f'DROP TABLE {name}_in')
    assert kept + collapsed + conflicting_rows + null_rows == rows, name
    return {'rows_in': rows, 'distinct_keys': distinct_keys, 'exact_duplicate_rows_collapsed': collapsed,
            'conflicting_keys': conflicting, 'rows_in_conflicting_keys': conflicting_rows,
            'null_key_rows': null_rows, 'rows_kept': kept}


def checked_count(con, table, expected, label):
    rows = con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
    if rows != expected:
        raise RuntimeError(f'{label}: join changed row count {expected} -> {rows}')
    return rows


def run(ctx):
    with StageRun(ctx, '01_clean', requires=['00_inventory']) as stage:
        con, _ = ctx.stage_db('01_clean')
        stats = {}
        stats['positions'] = dedupe(con, 'pos', ctx.src('positions'), ['position_id'], POSITION_COLUMNS)
        stats['raw_titles'] = dedupe(con, 'raw', ctx.src('positions_raw'), ['position_id'], ['user_id', 'title_raw'])
        stats['users'] = dedupe(con, 'usr', ctx.src('users'), ['user_id'], USER_COLUMNS)
        stats['role_lookup_v2'] = dedupe(con, 'rv2', ctx.src('role_lookup_v2'), ['role_k1500_v2'],
                                         ['role_k150_v2', 'role_k50_v2', 'job_category_v2'])
        stats['role_lookup_v3'] = dedupe(con, 'rv3', ctx.src('role_lookup_v3'), ['role_k17000_v3'],
                                         ['role_k150_v3', 'role_k50_v3', 'role_k10_v3', 'onet_title'])
        stats['cohort'] = dedupe(con, 'coh', ctx.src('cohort'), ['user_id'], [])
        n_pos = stats['positions']['rows_kept']
        tax = ctx.taxonomy
        hk = lit(ctx.hk)
        con.execute(f'''CREATE TABLE pos_joined AS
            SELECT p.*, CASE WHEN r.position_id IS NULL THEN NULL WHEN r.user_id IS DISTINCT FROM p.user_id THEN NULL
                             ELSE NULLIF(trim(r.title_raw), '') END AS title_raw,
                   CASE WHEN rq.position_id IS NOT NULL THEN 'conflicting_raw_key'
                        WHEN r.position_id IS NULL THEN 'no_raw_row'
                        WHEN r.user_id IS DISTINCT FROM p.user_id THEN 'raw_user_mismatch'
                        WHEN NULLIF(trim(r.title_raw), '') IS NULL THEN 'blank_title' ELSE 'ok' END AS title_status,
                   v2.role_k150_v2, v2.role_k50_v2, v2.job_category_v2,
                   v3.role_k150_v3, v3.role_k50_v3, v3.onet_title,
                   CASE WHEN p.role_k1500_v2 IS NOT NULL AND v2.role_k1500_v2 IS NULL THEN true END AS role_v2_unmatched,
                   CASE WHEN p.role_k17000_v3 IS NOT NULL AND v3.role_k17000_v3 IS NULL THEN true END AS role_v3_unmatched,
                   c.user_id IS NOT NULL AS in_cohort
            FROM pos p
            LEFT JOIN raw r USING (position_id)
            LEFT JOIN (SELECT DISTINCT position_id FROM raw_quarantine WHERE position_id IS NOT NULL) rq USING (position_id)
            LEFT JOIN rv2 v2 ON v2.role_k1500_v2 = p.role_k1500_v2
            LEFT JOIN rv3 v3 ON v3.role_k17000_v3 = p.role_k17000_v3
            LEFT JOIN coh c ON c.user_id = p.user_id''')
        checked_count(con, 'pos_joined', n_pos, 'positions title/lookup/cohort join')
        start, end = 'year(startdate) * 12 + month(startdate) - 1', 'year(enddate) * 12 + month(enddate) - 1'
        con.execute(f'''CREATE TABLE positions AS
            WITH t AS (SELECT * EXCLUDE (country, state, metro_area, city, region, msa),
                              NULLIF(trim(country), '') AS country, NULLIF(trim(state), '') AS state,
                              NULLIF(trim(metro_area), '') AS metro_area, NULLIF(trim(city), '') AS city,
                              NULLIF(trim(region), '') AS region, NULLIF(trim(msa), '') AS msa,
                              {normalized('title_raw', tax)} AS title_norm,
                              {start} AS start_midx, {end} AS end_midx
                       FROM pos_joined),
            r AS (SELECT * EXCLUDE (title_norm), {rule_columns('title_norm', tax)} FROM t)
            SELECT *, role_rule_category IS NOT NULL AS role_downranked,
                   (hash(user_id) % {ctx.buckets})::INTEGER AS bucket,
                   enddate IS NULL AS open_ended,
                   country = {hk} AS hk_position,
                   CASE WHEN user_id IS NULL THEN 'missing_key'
                        WHEN NOT in_cohort THEN 'user_not_in_cohort'
                        WHEN startdate IS NULL AND enddate IS NULL THEN 'undated'
                        WHEN startdate IS NULL THEN 'missing_start_date'
                        WHEN startdate < DATE {lit(ctx.min_start)} THEN 'start_before_min_valid'
                        WHEN start_midx > {ctx.cutoff_midx} THEN 'start_after_cutoff'
                        WHEN end_midx < start_midx THEN 'end_before_start' END AS quarantine_reason
            FROM r''')
        checked_count(con, 'positions', n_pos, 'positions rules')
        con.execute(f'''CREATE TABLE users AS
            WITH counts AS (SELECT user_id, count(*) n_positions, count(*) FILTER (WHERE quarantine_reason IS NULL) n_valid,
                                   count(*) FILTER (WHERE quarantine_reason IS NULL AND hk_position) n_valid_hk
                            FROM positions WHERE user_id IS NOT NULL GROUP BY 1),
            ids AS (SELECT user_id FROM coh UNION SELECT user_id FROM usr UNION
                    SELECT user_id FROM usr_quarantine WHERE user_id IS NOT NULL)
            SELECT i.user_id, (hash(i.user_id) % {ctx.buckets})::INTEGER AS bucket,
                   c.user_id IS NOT NULL AS in_cohort,
                   CASE WHEN u.user_id IS NOT NULL THEN 'ok'
                        WHEN i.user_id IN (SELECT user_id FROM usr_quarantine WHERE user_id IS NOT NULL)
                        THEN 'conflicting_duplicate_key' ELSE 'no_profile_row' END AS profile_status,
                   NULLIF(trim(u.user_country), '') AS user_country, u.user_location, u.updated_dt,
                   year(u.updated_dt) * 12 + month(u.updated_dt) - 1 AS refresh_midx,
                   (year(u.updated_dt) * 12 + month(u.updated_dt) - 1) // 3 AS refresh_qidx,
                   u.prestige, u.numconnections, u.highest_degree,
                   coalesce(k.n_positions, 0) AS n_positions, coalesce(k.n_valid, 0) AS n_valid_positions,
                   coalesce(k.n_valid_hk, 0) AS n_valid_hk_positions,
                   coalesce(k.n_valid, 0) = 0 AS profile_only
            FROM ids i LEFT JOIN coh c USING (user_id) LEFT JOIN usr u USING (user_id) LEFT JOIN counts k USING (user_id)''')
        n_users = con.execute('SELECT count(*) FROM (SELECT user_id FROM coh UNION SELECT user_id FROM usr UNION '
                              'SELECT user_id FROM usr_quarantine WHERE user_id IS NOT NULL)').fetchone()[0]
        checked_count(con, 'users', n_users, 'user universe')
        for name in ('positions_clean', 'users_clean'):
            shutil.rmtree(ctx.derived / name, ignore_errors=True)
        ctx.derived.mkdir(parents=True, exist_ok=True)
        compression = ctx.config['storage']['parquet_compression']
        con.execute(f"COPY (SELECT * FROM positions WHERE quarantine_reason IS NULL) TO "
                    f"{lit(ctx.derived / 'positions_clean')} (FORMAT parquet, COMPRESSION {compression}, PARTITION_BY (bucket))")
        con.execute(f"COPY users TO {lit(ctx.derived / 'users_clean')} "
                    f"(FORMAT parquet, COMPRESSION {compression}, PARTITION_BY (bucket))")
        quarantined = ctx.copy(con, '''
            SELECT * FROM positions WHERE quarantine_reason IS NOT NULL
            UNION ALL BY NAME SELECT *, NULL AS bucket FROM pos_quarantine''', ctx.derived / 'positions_quarantine.parquet')
        other = ctx.copy(con, '''
            SELECT 'individual_positions_raw' AS source_table, position_id AS key_value, quarantine_reason, count(*) AS rows
              FROM raw_quarantine GROUP BY ALL
            UNION ALL SELECT 'individual_user', user_id, quarantine_reason, count(*) FROM usr_quarantine GROUP BY ALL
            UNION ALL SELECT 'individual_role_lookup_v2', role_k1500_v2, quarantine_reason, count(*) FROM rv2_quarantine GROUP BY ALL
            UNION ALL SELECT 'individual_role_lookup_v3', role_k17000_v3, quarantine_reason, count(*) FROM rv3_quarantine GROUP BY ALL
            UNION ALL SELECT 'people_cohort', user_id, quarantine_reason, count(*) FROM coh_quarantine GROUP BY ALL
            ORDER BY 1, 2''', ctx.derived / 'other_quarantine.parquet')
        summary = {
            'dedupe': stats,
            'positions_by_quarantine_reason': dict(con.execute(
                "SELECT coalesce(quarantine_reason, 'valid'), count(*) FROM positions GROUP BY 1 ORDER BY 1").fetchall()),
            'positions_conflicting_duplicate_key_rows': stats['positions']['rows_in_conflicting_keys'],
            'title_status': dict(con.execute('SELECT title_status, count(*) FROM positions GROUP BY 1 ORDER BY 1').fetchall()),
            'role_rule_category_valid': dict(con.execute(
                "SELECT coalesce(role_rule_category, 'none'), count(*) FROM positions WHERE quarantine_reason IS NULL "
                "GROUP BY 1 ORDER BY 1").fetchall()),
            'users': dict(zip(['users', 'in_cohort', 'with_profile', 'profile_only', 'with_valid_positions'], con.execute(
                "SELECT count(*), count(*) FILTER (WHERE in_cohort), count(*) FILTER (WHERE profile_status = 'ok'), "
                "count(*) FILTER (WHERE profile_only), count(*) FILTER (WHERE NOT profile_only) FROM users").fetchone())),
            'positions_quarantine_rows': quarantined, 'other_quarantine_groups': other,
        }
        save_json(ctx.derived / 'clean_summary.json', summary)
        save_json(ctx.diagnostics / 'clean_summary.json', summary)
        stage.output('positions_clean', ctx.derived / 'positions_clean',
                     summary['positions_by_quarantine_reason'].get('valid', 0))
        stage.output('users_clean', ctx.derived / 'users_clean', summary['users']['users'])
        stage.output('positions_quarantine', ctx.derived / 'positions_quarantine.parquet', quarantined)
        stage.output('other_quarantine', ctx.derived / 'other_quarantine.parquet', other)
        stage.summary.update(summary)
        con.close()
        return summary
