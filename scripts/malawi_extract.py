"""Estimate and extract country-linked Revelio products on KLC, with a storage gate."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from wrds_data import connection

BUDGET = 20_000_000_000
RESERVE = 1_000_000
VERSION = 2
COUNTRIES = ('Malawi', 'Hong Kong')


def country_sql(country):
    if country not in COUNTRIES:
        raise ValueError('Unsupported country: ' + str(country))
    return "'" + country + "'"

SCHEMAS = {
    'individual': 'revelio_individual', 'postings': 'revelio_job_postings',
    'common': 'revelio_common', 'sentiment': 'revelio_sentiment',
    'workforce': 'revelio_workforce_dynamics',
}
TABLES = {
    'individual': ['individual_positions', 'individual_positions_raw', 'individual_user',
                   'individual_user_raw', 'individual_user_education',
                   'individual_user_education_raw', 'individual_user_skills',
                   'individual_role_lookup_v2', 'individual_role_lookup_v3',
                   'individual_user_skill_lookup'],
    'postings': ['postings_cosmos', 'postings_cosmos_raw', 'postings_role_lookup_v2',
                 'postings_role_lookup_v3'],
    'common': ['company_mapping', 'school_mapping', 'regions', 'months'],
    'sentiment': ['sentiment_individual_reviews', 'sentiment_role_lookup', 'sentiment_scores'],
    'workforce': ['workforce_dynamics_geo'],
}
# Layoffs is exposed in the current aggregate schema, without its own product schema.
SOURCES = {name: f'{SCHEMAS[group]}.{name}' for group, names in TABLES.items() for name in names}
SOURCES['layoffs'] = 'revelio.layoffs'


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def footprint(path):
    return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file())


def write_part(frame, path, used, budget=None, schema=None):
    """Encode before writing so a part cannot overshoot the on-disk budget."""
    budget = BUDGET if budget is None else budget
    import pyarrow.parquet as pq
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False, compression='zstd', schema=schema)
    payload = buffer.getvalue()
    if used + len(payload) + RESERVE > budget:
        raise ValueError(f'{budget / 1e9:g} GB storage cap reached; extract remains incomplete.')
    if shutil.disk_usage(path.parent).free < len(payload) + RESERVE:
        raise ValueError('Insufficient KLC storage; extract remains incomplete.')
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(payload)
    # Read the encoded part back, not merely its footer.
    if pq.read_table(temporary).num_rows != len(frame):
        raise ValueError('Parquet row verification failed.')
    temporary.replace(path)
    return len(payload)


def storage_projection(rows, block_sizes, block_rows, retained):
    rates = [size / count for size, count in zip(block_sizes, block_rows) if count]
    expected = rows * (sum(block_sizes) / sum(block_rows)) if rates else 0
    upper = max(expected * 1.3, rows * max(rates, default=0) * 1.3)
    return dict(expected_bytes=math.ceil(expected), planning_bytes=math.ceil(upper),
                retained_pilot_bytes=retained)


def gate(report, resumable=False, budget=None):
    budget = report.get('budget_bytes', BUDGET) if budget is None else budget
    if report.get('resumable') and not resumable:
        raise ValueError('Use --resumable to download this estimate.')
    if report.get('status') != 'complete' or report.get('version') != VERSION:
        raise ValueError('A completed compatible estimate is required.')
    if report.get('unavailable'):
        raise ValueError('Missing products: report to the user before any partial download.')
    if report['planning_total_bytes'] + RESERVE > budget:
        raise ValueError(f'Estimate or uncertainty exceeds {budget / 1e9:g} GB; report before sampling.')


@contextmanager
def session(conn, timeout):
    """Keep every query on one read-only repeatable-read connection."""
    with conn.engine.connect() as db:
        db = db.execution_options(isolation_level='REPEATABLE READ')
        with db.begin():
            db.exec_driver_sql(f"SET LOCAL statement_timeout = '{int(timeout)}s'")
            yield db


def scalar(db, sql, params=None):
    from sqlalchemy import text
    return db.execute(text(sql), {'people': db.info.get('mw_people', []), **(params or {})}).scalar_one()


def execute(db, sql):
    from sqlalchemy import text
    db.execute(text(sql))


def discover(db):
    """Resolve only current schemas, falling back to the current aggregate views."""
    from sqlalchemy import text
    result, unavailable = {}, []
    for name, preferred in SOURCES.items():
        candidates = list(dict.fromkeys([preferred, 'revelio.' + name]))
        for source in candidates:
            accessible = scalar(db, "SELECT CASE WHEN to_regclass(:source) IS NULL THEN false "
                                "ELSE has_table_privilege(:source, 'SELECT') END", {'source': source})
            if not accessible:
                continue
            schema, table = source.split('.')
            columns = list(db.execute(text("SELECT column_name, data_type, numeric_precision, numeric_scale FROM information_schema.columns "
                "WHERE table_schema=:schema AND table_name=:table ORDER BY ordinal_position"),
                {'schema': schema, 'table': table}).mappings())
            if columns:
                result[name] = dict(source=source, columns=[dict(c) for c in columns])
                break
        else:
            unavailable.append(name)
    return result, unavailable


def prepare(db, sources, folder=None, budget_used=0, budget=None):
    required = {'individual_positions', 'individual_user', 'postings_cosmos',
                'company_mapping', 'school_mapping', 'individual_user_education',
                'sentiment_individual_reviews', 'workforce_dynamics_geo'}
    missing = required - sources.keys()
    if missing:
        raise ValueError('Cannot define complete selection; missing: ' + ', '.join(sorted(missing)))
    import pandas as pd
    from sqlalchemy import text
    country = db.info.get('country', 'Malawi')
    literal = country_sql(country)
    s = lambda name: sources[name]['source']
    print(f'Selecting {country} person IDs (one country scan per people source)', flush=True)
    sql = (f"SELECT user_id::text AS user_id FROM {s('individual_user')} WHERE user_country={literal} "
           f"AND user_id IS NOT NULL UNION SELECT user_id::text FROM {s('individual_positions')} "
           f"WHERE country={literal} AND user_id IS NOT NULL")
    people = []
    if folder:
        folder.mkdir()
    with db.execution_options(stream_results=True).execute(text(sql)) as result:
        part = 0
        while True:
            records = result.fetchmany(5000)
            if not records:
                break
            ids = [r[0] for r in records]
            people.extend(ids)
            if folder:
                frame = pd.DataFrame({'user_id': ids})
                budget_used += write_part(frame, folder / f'part-{part:06d}.parquet', budget_used, budget=budget)
            part += 1
    db.execution_options(stream_results=False)
    db.info['mw_people'] = people
    print(f'Cohort: {len(people):,} people', flush=True)
    # Inline ID array avoids repeatedly scanning the billion-row country sources.
    # Typed numeric keys retain exact IDs and allow use of the WRDS user_id indexes.
    return selection_prefix(sources, country)


def selection_prefix(sources, country='Malawi'):
    literal = country_sql(country)
    s = lambda name: sources[name]['source']
    return f"""WITH mw_people AS (
        SELECT unnest(CAST(:people AS numeric[])) AS user_id
    ), mw_positions AS (
        SELECT t.* FROM {s('individual_positions')} t
        WHERE t.user_id = ANY(CAST(:people AS numeric[])) OR (t.user_id IS NULL AND country={literal})
    ), mw_postings AS (
        SELECT * FROM {s('postings_cosmos')} WHERE country={literal}
    ), mw_education AS (
        SELECT t.* FROM {s('individual_user_education')} t
        WHERE t.user_id = ANY(CAST(:people AS numeric[]))
    ), mw_companies AS (
        SELECT rcid FROM {s('company_mapping')} WHERE hq_country={literal}
        UNION SELECT rcid FROM mw_positions UNION SELECT ultimate_parent_rcid FROM mw_positions
        UNION SELECT rcid FROM mw_postings UNION SELECT ultimate_parent_rcid FROM mw_postings
        UNION SELECT rcid FROM {s('sentiment_individual_reviews')} WHERE country={literal}
        UNION SELECT ultimate_parent_rcid FROM {s('sentiment_individual_reviews')} WHERE country={literal}
        UNION SELECT rcid FROM {s('workforce_dynamics_geo')} WHERE country={literal}
    ), mw_schools AS (
        SELECT rsid FROM {s('school_mapping')} WHERE country={literal}
        UNION SELECT rsid FROM mw_education
    ) """


def selection(name, country='Malawi'):
    literal = country_sql(country)
    if name == 'individual_positions':
        return 'FROM mw_positions t'
    if name == 'postings_cosmos':
        return 'FROM mw_postings t'
    if name == 'individual_user_education':
        return 'FROM mw_education t'
    if name == 'individual_positions_raw':
        # Separate NULL IDs so the normal branch can use indexed equality joins.
        # EXISTS preserves raw duplicates without multiplying structured matches;
        # the branches are disjoint, so UNION ALL preserves the selected rows.
        return ('FROM (SELECT r.* FROM {source} r WHERE r.user_id IS NOT NULL '
                'AND EXISTS (SELECT 1 FROM mw_positions p '
                'WHERE p.user_id=r.user_id AND p.position_id=r.position_id) '
                'UNION ALL SELECT r.* FROM {source} r WHERE r.user_id IS NULL '
                'AND EXISTS (SELECT 1 FROM mw_positions p WHERE p.user_id IS NULL '
                'AND p.position_id=r.position_id)) t')
    if name == 'individual_user_education_raw':
        return ('FROM {source} t WHERE EXISTS (SELECT 1 FROM mw_education e '
                'WHERE e.user_id=t.user_id AND e.education_number=t.education_number)')
    if name in ('individual_user', 'individual_user_raw', 'individual_user_skills'):
        return 'FROM {source} t WHERE EXISTS (SELECT 1 FROM mw_people c WHERE c.user_id=t.user_id)'
    if name == 'postings_cosmos_raw':
        return 'FROM {source} t WHERE EXISTS (SELECT 1 FROM mw_postings p WHERE p.job_id=t.job_id)'
    if name in ('workforce_dynamics_geo', 'sentiment_individual_reviews'):
        return "FROM {source} t WHERE country=" + literal
    if name in ('company_mapping', 'sentiment_scores', 'layoffs'):
        return 'FROM {source} t WHERE EXISTS (SELECT 1 FROM mw_companies c WHERE c.rcid=t.rcid)'
    if name == 'school_mapping':
        return 'FROM {source} t WHERE EXISTS (SELECT 1 FROM mw_schools c WHERE c.rsid=t.rsid)'
    if name == 'regions':
        return "FROM {source} t WHERE country=" + literal
    return 'FROM {source} t'


def arrow_schema(source):
    import pyarrow as pa
    types = {'smallint': pa.int16(), 'integer': pa.int32(), 'bigint': pa.int64(),
             'real': pa.float32(), 'double precision': pa.float64(), 'boolean': pa.bool_(),
             'date': pa.date32(), 'time without time zone': pa.time64('us'), 'timestamp without time zone': pa.timestamp('us'),
             'timestamp with time zone': pa.timestamp('us', tz='UTC')}
    fields = []
    for column in source['columns']:
        name, datatype = column['column_name'], column['data_type']
        if name.endswith('_id') or name in ('rcid', 'ultimate_parent_rcid', 'child_rcid',
                'rsid', 'ultimate_parent_rsid', 'corresponding_rcid', 'corresponding_rsid'):
            kind = pa.string()
        elif datatype == 'numeric':
            precision, scale = column.get('numeric_precision'), column.get('numeric_scale')
            if precision is None or scale is None:
                raise ValueError(f'{name}: unconstrained numeric requires an explicit Arrow type')
            kind = pa.decimal128(int(precision), int(scale))
        elif datatype in types:
            kind = types[datatype]
        elif datatype in ('text', 'character varying', 'character'):
            kind = pa.string()
        else:
            raise ValueError(f'{name}: unsupported source type {datatype}')
        fields.append(pa.field(name, kind))
    return pa.schema(fields)


def query(name, source, prefix='', country='Malawi'):
    fields = []
    for column in source['columns']:
        field = 't."' + column['column_name'].replace('"', '""') + '"'
        # All NUMERIC values remain Decimal, never pandas' default float coercion.
        # Identifiers are text even when BIGINT, preventing downstream loss.
        if column['column_name'].endswith('_id') or column['column_name'] in (
                'rcid', 'ultimate_parent_rcid', 'child_rcid', 'rsid', 'ultimate_parent_rsid',
                'corresponding_rcid', 'corresponding_rsid'):
            field += '::text AS "' + column['column_name'] + '"'
        fields.append(field)
    return prefix + 'SELECT ' + ', '.join(fields) + ' ' + selection(name, country).format(source=source['source'])


def raw_batches(db, sources, unmatched_rows=False):
    """Disjoint indexed person batches, followed by the country's NULL-person rows."""
    literal = country_sql(db.info.get('country', 'Malawi'))
    size = db.info.get('mw_raw_batch_size', 1000)
    if size < 1:
        raise ValueError('raw-batch-size must be positive')
    people = sorted(set(db.info.get('mw_people', [])))
    raw = sources['individual_positions_raw']['source']
    positions = sources['individual_positions']['source']
    for start in range(0, len(people), size):
        params = {'people': people[start:start + size]}
        if unmatched_rows:
            sql = (f'SELECT p.* FROM {positions} p WHERE p.user_id = ANY(CAST(:people AS numeric[])) '
                   f'AND NOT EXISTS (SELECT 1 FROM {raw} r '
                   'WHERE r.user_id=p.user_id AND r.position_id=p.position_id)')
        else:
            base = query('individual_positions_raw', sources['individual_positions_raw'])
            fields = base[:base.index(' FROM ')]
            sql = (fields + f' FROM {raw} t WHERE t.user_id = ANY(CAST(:people AS numeric[])) '
                   f'AND EXISTS (SELECT 1 FROM {positions} p '
                   'WHERE p.user_id=t.user_id AND p.position_id=t.position_id)')
        yield sql, params
    if unmatched_rows:
        sql = (f"SELECT p.* FROM {positions} p WHERE p.user_id IS NULL AND p.country={literal} "
               f'AND NOT EXISTS (SELECT 1 FROM {raw} r '
               'WHERE r.user_id IS NULL AND r.position_id=p.position_id)')
    else:
        base = query('individual_positions_raw', sources['individual_positions_raw'])
        fields = base[:base.index(' FROM ')]
        sql = (fields + f' FROM {raw} t WHERE t.user_id IS NULL '
               f'AND EXISTS (SELECT 1 FROM {positions} p '
               f"WHERE p.user_id IS NULL AND p.country={literal} AND p.position_id=t.position_id)")
    yield sql, {}


def table_batches(db, name, sources, sql):
    if name == 'individual_positions_raw':
        yield from raw_batches(db, sources)
    elif name == 'postings_cosmos_raw':
        yield from posting_batches(db, sources)
    else:
        yield sql, {'people': db.info['mw_people']}


def prepare_postings(db, sources, folder=None, budget_used=0, budget=None):
    """Collect exact unique country posting IDs without downloading descriptions."""
    import pandas as pd
    from sqlalchemy import text
    literal = country_sql(db.info.get('country', 'Malawi'))
    sql = (f"SELECT DISTINCT job_id::text AS job_id FROM {sources['postings_cosmos']['source']} "
           f"WHERE country={literal} AND job_id IS NOT NULL")
    if folder:
        folder.mkdir()
    jobs = []
    with db.execution_options(stream_results=True).execute(text(sql)) as result:
        part = 0
        while True:
            rows = result.fetchmany(5000)
            if not rows:
                break
            ids = [row[0] for row in rows]
            jobs.extend(ids)
            if folder:
                budget_used += write_part(pd.DataFrame({'job_id': ids}),
                    folder / f'part-{part:06d}.parquet', budget_used, budget=budget)
            part += 1
    db.execution_options(stream_results=False)
    db.info['posting_ids'] = sorted(jobs)
    print(f"Posting cohort: {len(jobs):,} unique job IDs", flush=True)


def posting_batches(db, sources, unmatched_rows=False):
    """Disjoint exact IDs preserve raw duplicates without multiplying matches."""
    size = db.info.get('posting_batch_size', 1000)
    if size < 1:
        raise ValueError('posting-batch-size must be positive')
    jobs = db.info['posting_ids']
    raw = sources['postings_cosmos_raw']['source']
    structured = sources['postings_cosmos']['source']
    literal = country_sql(db.info.get('country', 'Malawi'))
    fields = query('postings_cosmos_raw', sources['postings_cosmos_raw']).split(' FROM ', 1)[0]
    for start in range(0, len(jobs), size):
        if unmatched_rows:
            sql = (f"SELECT p.* FROM {structured} p WHERE p.country={literal} "
                   "AND p.job_id = ANY(CAST(:jobs AS bigint[])) "
                   f"AND NOT EXISTS (SELECT 1 FROM {raw} r WHERE r.job_id=p.job_id)")
        else:
            sql = fields + f' FROM {raw} t WHERE t.job_id = ANY(CAST(:jobs AS numeric[]))'
        yield sql, {'jobs': jobs[start:start + size]}
    if unmatched_rows:
        yield f"SELECT p.* FROM {structured} p WHERE p.country={literal} AND p.job_id IS NULL", {}
    elif not jobs:
        yield fields + f' FROM {raw} t WHERE false', {}


def count_batches(db, batches, label):
    total = 0
    for index, (sql, params) in enumerate(batches, 1):
        total += scalar(db, f'SELECT count(*) FROM ({sql}) selected', params)
        print(f'{label}: batch {index}; cumulative {total:,} rows', flush=True)
    return total


def estimate_selection(db, name, sources, sql, pilot_rows):
    """Merge local random-priority winners into one bounded global pilot."""
    import pandas as pd
    from sqlalchemy import text
    rows = count_batches(db, table_batches(db, name, sources, sql), name)
    execute(db, 'SELECT setseed(0.7409)')
    priority = '__malawi_pilot_priority'
    columns = {c['column_name'] for c in sources[name]['columns']}
    while priority in columns:
        priority += '_'
    winners = None
    for index, (batch_sql, params) in enumerate(table_batches(db, name, sources, sql), 1):
        sample_sql = (f'SELECT selected.*, random() AS "{priority}" FROM ({batch_sql}) selected '
                      f'ORDER BY "{priority}" LIMIT {pilot_rows}')
        frame = pd.read_sql_query(text(sample_sql), db, params=params, coerce_float=False)
        if winners is not None:
            frame = pd.concat([winners, frame], ignore_index=True)
        frame[priority] = pd.to_numeric(frame[priority])
        winners = frame.nsmallest(pilot_rows, priority)
        print(f'{name}: pilot batch {index}; retained {len(winners):,} rows', flush=True)
    return rows, winners.drop(columns=[priority]).reset_index(drop=True)


def unmatched(db, sources, prefix=''):
    result = {}
    for structured, raw, temporary_table, keys in [
        ('individual_positions', 'individual_positions_raw', 'mw_positions', ['user_id', 'position_id']),
        ('individual_user_education', 'individual_user_education_raw', 'mw_education', ['user_id', 'education_number']),
        ('postings_cosmos', 'postings_cosmos_raw', 'mw_postings', ['job_id']),
    ]:
        if raw == 'individual_positions_raw' and raw in sources:
            result[raw] = count_batches(db, raw_batches(db, sources, unmatched_rows=True), 'Unmatched positions')
            continue
        if raw == 'postings_cosmos_raw' and raw in sources:
            result[raw] = count_batches(db, posting_batches(db, sources, True), 'Unmatched postings')
            continue
        if raw == 'individual_user_education_raw' and raw in sources:
            # mw_education contains only non-NULL cohort IDs. Equality preserves
            # its matching semantics and permits indexed lookups on both keys.
            people = sorted(set(db.info.get('mw_people', [])))
            size = db.info.get('mw_raw_batch_size', 1000)
            if size < 1:
                raise ValueError('raw-batch-size must be positive')
            sql = (f"SELECT p.* FROM {sources[structured]['source']} p "
                   "WHERE p.user_id = ANY(CAST(:people AS numeric[])) "
                   f"AND NOT EXISTS (SELECT 1 FROM {sources[raw]['source']} r "
                   "WHERE r.user_id=p.user_id AND r.education_number=p.education_number)")
            batches = ((sql, {'people': people[start:start + size]})
                       for start in range(0, len(people), size))
            result[raw] = count_batches(db, batches, 'Unmatched education')
            continue
        if raw in sources:
            match = ' AND '.join(f'r.{key} IS NOT DISTINCT FROM p.{key}' if key == 'user_id' else f'r.{key}=p.{key}' for key in keys)
            result[raw] = scalar(db, prefix + f"SELECT count(*) FROM {temporary_table} p WHERE NOT EXISTS "
                                f"(SELECT 1 FROM {sources[raw]['source']} r WHERE {match})")
    return result


def estimate(db, root, output, pilot_rows, raw_batch_size=1000, posting_batch_size=1000, budget=None):
    budget = BUDGET if budget is None else budget
    db.info['mw_raw_batch_size'] = raw_batch_size
    db.info['posting_batch_size'] = posting_batch_size
    country = db.info.get('country', 'Malawi')
    country_sql(country)
    report = dict(raw_batch_size=raw_batch_size, posting_batch_size=posting_batch_size, version=VERSION, status='incomplete', started_at_utc=now(), country=country,
        budget_bytes=budget, tables={}, unavailable=[], cohort=f'Residence or any historical {country} work; full histories.',
        sampling='Seeded random priority over selected rows; four independently encoded pilot blocks.',
        margin=0.3, context_tables=['layoffs', 'sentiment_scores'], root=str(root))
    output.mkdir(parents=True, exist_ok=False)
    path = output / 'estimate.json'
    save(path, report)
    try:
        sources, report['unavailable'] = discover(db)
        report['sources'] = sources
        save(path, report)
        for source in sources.values():
            arrow_schema(source)
        prefix = prepare(db, sources, output / 'cohort', footprint(output), budget=budget)
        prepare_postings(db, sources, output / 'posting_cohort', footprint(output), budget=budget)
        sources = dict(sources)
        sources['people_cohort'] = dict(source='mw_people', columns=[dict(column_name='user_id', data_type='numeric')])
        for name, source in sources.items():
            sql = query(name, source, prefix, country)
            print('Counting ' + name, flush=True)
            rows, frame = estimate_selection(db, name, sources, sql, pilot_rows)
            print(f'{name}: {rows:,} rows; pilot complete', flush=True)
            folder = output / name
            folder.mkdir()
            sizes, counts = [], []
            block = max(1, math.ceil(len(frame) / 4))
            for start in range(0, len(frame), block):
                part = frame.iloc[start:start + block]
                sizes.append(write_part(part, folder / f'pilot-{start // block:02d}.parquet', footprint(output), budget=budget, schema=arrow_schema(source)))
                counts.append(len(part))
            projected = storage_projection(rows, sizes, counts, sum(sizes))
            if rows == len(frame):
                projected['expected_bytes'] = sum(sizes)
                projected['planning_bytes'] = math.ceil(sum(sizes) * 1.3)
            report['tables'][name] = dict(source=source['source'], sql=sql, rows=rows,
                pilot_rows=len(frame), pilot_block_bytes=sizes, pilot_block_rows=counts, **projected)
            if name == 'individual_positions_raw':
                report['tables'][name]['execution'] = 'person_batches_and_null'
            save(path, report)
            print(f"{name}: projected {projected['planning_bytes'] / 1e9:.3f} GB", flush=True)
        report['unmatched_raw'] = unmatched(db, sources, prefix)
        report['expected_total_bytes'] = sum(t['expected_bytes'] for t in report['tables'].values()) + footprint(output)
        report['planning_total_bytes'] = sum(t['planning_bytes'] for t in report['tables'].values()) + footprint(output) + RESERVE
        report['finished_at_utc'] = now()
        report['status'] = 'complete'
        save(path, report)
    except BaseException as exc:
        report['error'] = str(exc)
        save(path, report)
        raise
    print(f"ESTIMATE: expected {report['expected_total_bytes']/1e9:.3f} GB; "
          f"planning {report['planning_total_bytes']/1e9:.3f} GB; unavailable {report['unavailable']}", flush=True)
    return report


def download(db, report, estimate_dir, output, chunksize, budget=None):
    import pandas as pd
    budget = report.get('budget_bytes', BUDGET) if budget is None else budget
    gate(report, budget=budget)
    country = report.get('country', 'Malawi')
    country_sql(country)
    if db.info.get('country', country) != country:
        raise ValueError('Estimate country differs from requested country.')
    db.info['country'] = country
    db.info['mw_raw_batch_size'] = report.get('raw_batch_size', 1000)
    db.info['posting_batch_size'] = report.get('posting_batch_size', 1000)
    if shutil.disk_usage(output.parent).free < report['planning_total_bytes'] + RESERVE:
        raise ValueError('Insufficient KLC free storage for the planned extract.')
    sources, unavailable = discover(db)
    if unavailable or sources != report['sources']:
        raise ValueError('Source access or schema changed; run a new estimate.')
    prefix = prepare(db, sources)
    prepare_postings(db, sources)
    import pyarrow.dataset as ds
    retained_ids = ds.dataset(estimate_dir / 'cohort', format='parquet').to_table().column('user_id').to_pylist() if list((estimate_dir / 'cohort').glob('*.parquet')) else []
    if set(retained_ids) != set(db.info['mw_people']):
        raise ValueError('People cohort changed; run a new estimate.')
    output.mkdir(exist_ok=False)
    manifest = dict(status='incomplete', started_at_utc=now(), estimate=str(estimate_dir),
                    tables={}, budget_bytes=budget, actual_bytes=0, country=country,
                    raw_batch_size=db.info['mw_raw_batch_size'])
    path = output / 'manifest.json'
    save(path, manifest)
    try:
        for name, table in report['tables'].items():
            sql = table['sql']
            count = count_batches(db, table_batches(db, name, sources, sql), name)
            if count != table['rows']:
                raise ValueError(f'{name} row count changed; run a new estimate.')
            folder = output / name
            folder.mkdir()
            state = dict(status='incomplete', expected_rows=count, rows=0, parts=0, bytes=0,
                         source=table['source'], sql=sql)
            manifest['tables'][name] = state
            save(path, manifest)
            print(f'Downloading {name}: {count:,} rows', flush=True)
            for batch_sql, params in table_batches(db, name, sources, sql):
                with db.execution_options(stream_results=True).execute(__import__('sqlalchemy').text(batch_sql), params) as result:
                    while True:
                        records = result.fetchmany(chunksize)
                        if not records:
                            break
                        frame = pd.DataFrame({name: pd.Series([r[index] for r in records], dtype=object)
                                              for index, name in enumerate(result.keys())})
                        size = write_part(frame, folder / f"part-{state['parts']:06d}.parquet",
                                          footprint(estimate_dir) + footprint(output), budget=budget,
                                          schema=arrow_schema(report['sources'].get(name, {'columns': [dict(column_name='user_id', data_type='text')]})))
                        state['rows'] += len(frame)
                        state['parts'] += 1
                        state['bytes'] += size
                        manifest['actual_bytes'] += size
                        save(path, manifest)
            db.execution_options(stream_results=False)
            if state['rows'] != count:
                raise ValueError(f'{name}: extracted row count mismatch.')
            state['status'] = 'complete'
            save(folder / 'manifest.json', state)
            save(path, manifest)
        manifest['unmatched_raw'] = unmatched(db, sources, prefix)
        manifest['status'] = 'complete'
        manifest['finished_at_utc'] = now()
        manifest['stored_bytes_including_estimate'] = footprint(output) + footprint(estimate_dir)
        save(path, manifest)
    except BaseException as exc:
        manifest['error'] = str(exc)
        save(path, manifest)
        raise
    print(f"DOWNLOAD COMPLETE: {output}; {manifest['actual_bytes']/1e9:.3f} GB", flush=True)


def positive_gb(value):
    try:
        result = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('budget-gb must be a positive whole number') from None
    if result < 1:
        raise argparse.ArgumentTypeError('budget-gb must be a positive whole number')
    return result


def main(argv=None):
    import pyarrow as pa
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['estimate', 'download'])
    parser.add_argument('--country', choices=COUNTRIES, default='Malawi')
    parser.add_argument('--budget-gb', type=positive_gb, help='Whole decimal GB cap; default 20 for new runs, saved cap on resume')
    parser.add_argument('--estimate', type=Path, help='Completed estimate directory for download')
    parser.add_argument('--pilot-rows', type=int, default=2000)
    parser.add_argument('--raw-batch-size', type=int, default=1000, help='People per raw-position query; download uses saved estimate value')
    parser.add_argument('--posting-batch-size', type=int, default=1000)
    parser.add_argument('--resumable', action='store_true', help='Checkpoint work units; reconnect using separate snapshots')
    parser.add_argument('--resume', type=Path, help='Resume a run from its estimate directory using saved settings')
    parser.add_argument('--chunksize', type=int, default=5000)
    parser.add_argument('--timeout', type=int, default=21600, help='Per-statement timeout in seconds')
    parser.add_argument('--download-if-safe', action='store_true', help='Download after estimate passes all gates')
    args = parser.parse_args(argv)
    if args.pilot_rows < 100 or min(args.chunksize, args.timeout, args.raw_batch_size, args.posting_batch_size) < 1:
        parser.error('pilot-rows >= 100, chunksize >= 1 and timeout >= 1 and raw-batch-size >= 1 required')
    root = Path(os.environ.get('KLC_ROOT', str(ROOT))).resolve()
    if not os.environ.get('KLC_ROOT') or not str(root).startswith(('/kellogg/proj/', '/gpfs/kellogg/proj/')):
        parser.error('Run through the KLC job toolkit; data must remain on KLC project storage')
    if args.resumable or args.resume:
        from country_extract_resumable import run
        return run(args, root)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    slug = args.country.lower().replace(' ', '_')
    output = root / 'data' / (slug + '_' + stamp)
    output.parent.mkdir(exist_ok=True)
    estimate_dir = args.estimate or root / 'results' / (slug + '_estimate_' + stamp)
    print(f'Estimate directory: {estimate_dir}; data directory: {output}', flush=True)
    with connection() as conn:
        if args.command == 'estimate':
            with session(conn, args.timeout) as db:
                db.info['country'] = args.country
                report = estimate(db, root, estimate_dir, args.pilot_rows, args.raw_batch_size, args.posting_batch_size,
                                  budget=args.budget_gb * 1_000_000_000 if args.budget_gb is not None else BUDGET)
            if not args.download_if_safe:
                return
        else:
            if args.estimate is None:
                parser.error('download requires --estimate')
            report = json.loads((estimate_dir / 'estimate.json').read_text())
        if args.budget_gb is not None:
            report['budget_bytes'] = args.budget_gb * 1_000_000_000
            save(estimate_dir / 'estimate.json', report)
        gate(report)
        with session(conn, args.timeout) as db:
            db.info['country'] = args.country
            download(db, report, estimate_dir, output, args.chunksize)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Country workflow stopped: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
