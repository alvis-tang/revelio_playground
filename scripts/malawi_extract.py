"""Estimate and extract Malawi-linked Revelio products on KLC, with a storage gate."""
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
VERSION = 1
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


def write_part(frame, path, used, budget=BUDGET, schema=None):
    """Encode before writing so a part cannot overshoot the on-disk budget."""
    import pyarrow.parquet as pq
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False, compression='zstd', schema=schema)
    payload = buffer.getvalue()
    if used + len(payload) + RESERVE > budget:
        raise ValueError('20 GB storage cap reached; extract remains incomplete.')
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


def gate(report):
    if report.get('status') != 'complete' or report.get('version') != VERSION:
        raise ValueError('A completed compatible estimate is required.')
    if report.get('unavailable'):
        raise ValueError('Missing products: report to the user before any partial download.')
    if report['planning_total_bytes'] + RESERVE > BUDGET:
        raise ValueError('Estimate or uncertainty exceeds 20 GB; report before sampling.')


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


def prepare(db, sources, folder=None, budget_used=0):
    import pandas as pd
    from sqlalchemy import text
    required = {'individual_positions', 'individual_user', 'postings_cosmos',
                'company_mapping', 'school_mapping', 'individual_user_education',
                'sentiment_individual_reviews', 'workforce_dynamics_geo'}
    missing = required - sources.keys()
    if missing:
        raise ValueError('Cannot define complete selection; missing: ' + ', '.join(sorted(missing)))
    s = lambda name: sources[name]['source']
    print('Selecting Malawi person IDs (one country scan per people source)', flush=True)
    sql = (f"SELECT user_id::text AS user_id FROM {s('individual_user')} WHERE user_country='Malawi' "
           f"AND user_id IS NOT NULL UNION SELECT user_id::text FROM {s('individual_positions')} "
           "WHERE country='Malawi' AND user_id IS NOT NULL")
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
                budget_used += write_part(frame, folder / f'part-{part:06d}.parquet', budget_used)
            part += 1
    db.execution_options(stream_results=False)
    db.info['mw_people'] = people
    print(f'Cohort: {len(people):,} people', flush=True)
    # Inline ID array avoids repeatedly scanning the billion-row country sources.
    # Typed numeric keys retain exact IDs and allow use of the WRDS user_id indexes.
    return selection_prefix(sources)


def selection_prefix(sources):
    s = lambda name: sources[name]['source']
    return f"""WITH mw_people AS (
        SELECT unnest(CAST(:people AS numeric[])) AS user_id
    ), mw_positions AS (
        SELECT t.* FROM {s('individual_positions')} t
        WHERE t.user_id = ANY(CAST(:people AS numeric[])) OR (t.user_id IS NULL AND country='Malawi')
    ), mw_postings AS (
        SELECT * FROM {s('postings_cosmos')} WHERE country='Malawi'
    ), mw_education AS (
        SELECT t.* FROM {s('individual_user_education')} t
        WHERE t.user_id = ANY(CAST(:people AS numeric[]))
    ), mw_companies AS (
        SELECT rcid FROM {s('company_mapping')} WHERE hq_country='Malawi'
        UNION SELECT rcid FROM mw_positions UNION SELECT ultimate_parent_rcid FROM mw_positions
        UNION SELECT rcid FROM mw_postings UNION SELECT ultimate_parent_rcid FROM mw_postings
        UNION SELECT rcid FROM {s('sentiment_individual_reviews')} WHERE country='Malawi'
        UNION SELECT ultimate_parent_rcid FROM {s('sentiment_individual_reviews')} WHERE country='Malawi'
        UNION SELECT rcid FROM {s('workforce_dynamics_geo')} WHERE country='Malawi'
    ), mw_schools AS (
        SELECT rsid FROM {s('school_mapping')} WHERE country='Malawi'
        UNION SELECT rsid FROM mw_education
    ) """


def selection(name):
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
        return "FROM {source} t WHERE country='Malawi'"
    if name in ('company_mapping', 'sentiment_scores', 'layoffs'):
        return 'FROM {source} t WHERE EXISTS (SELECT 1 FROM mw_companies c WHERE c.rcid=t.rcid)'
    if name == 'school_mapping':
        return 'FROM {source} t WHERE EXISTS (SELECT 1 FROM mw_schools c WHERE c.rsid=t.rsid)'
    if name == 'regions':
        return "FROM {source} t WHERE country='Malawi'"
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


def query(name, source, prefix=''):
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
    return prefix + 'SELECT ' + ', '.join(fields) + ' ' + selection(name).format(source=source['source'])


def unmatched(db, sources, prefix=''):
    result = {}
    for structured, raw, temporary_table, keys in [
        ('individual_positions', 'individual_positions_raw', 'mw_positions', ['user_id', 'position_id']),
        ('individual_user_education', 'individual_user_education_raw', 'mw_education', ['user_id', 'education_number']),
        ('postings_cosmos', 'postings_cosmos_raw', 'mw_postings', ['job_id']),
    ]:
        if raw in sources:
            match = ' AND '.join(f'r.{key} IS NOT DISTINCT FROM p.{key}' if key == 'user_id' else f'r.{key}=p.{key}' for key in keys)
            result[raw] = scalar(db, prefix + f"SELECT count(*) FROM {temporary_table} p WHERE NOT EXISTS "
                                f"(SELECT 1 FROM {sources[raw]['source']} r WHERE {match})")
    return result


def estimate(db, root, output, pilot_rows):
    import pandas as pd
    report = dict(version=VERSION, status='incomplete', started_at_utc=now(), country='Malawi',
        budget_bytes=BUDGET, tables={}, unavailable=[], cohort='Residence or any historical Malawi work; full histories.',
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
        prefix = prepare(db, sources, output / 'cohort', footprint(output))
        sources = dict(sources)
        sources['people_cohort'] = dict(source='mw_people', columns=[dict(column_name='user_id', data_type='numeric')])
        for name, source in sources.items():
            sql = query(name, source, prefix)
            print('Counting ' + name, flush=True)
            rows = scalar(db, f'SELECT count(*) FROM ({sql}) selected')
            print(f'{name}: {rows:,} rows; sampling', flush=True)
            # ORDER BY seeded random priorities samples the entire selected population.
            execute(db, 'SELECT setseed(0.7409)')
            from sqlalchemy import text
            frame = pd.read_sql_query(text(sql + f' ORDER BY random() LIMIT {pilot_rows}'), db,
                                      params={'people': db.info['mw_people']}, coerce_float=False)
            folder = output / name
            folder.mkdir()
            sizes, counts = [], []
            block = max(1, math.ceil(len(frame) / 4))
            for start in range(0, len(frame), block):
                part = frame.iloc[start:start + block]
                sizes.append(write_part(part, folder / f'pilot-{start // block:02d}.parquet', footprint(output), schema=arrow_schema(source)))
                counts.append(len(part))
            projected = storage_projection(rows, sizes, counts, sum(sizes))
            if rows == len(frame):
                projected['expected_bytes'] = sum(sizes)
                projected['planning_bytes'] = math.ceil(sum(sizes) * 1.3)
            report['tables'][name] = dict(source=source['source'], sql=sql, rows=rows,
                pilot_rows=len(frame), pilot_block_bytes=sizes, pilot_block_rows=counts, **projected)
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


def download(db, report, estimate_dir, output, chunksize):
    import pandas as pd
    gate(report)
    if shutil.disk_usage(output.parent).free < report['planning_total_bytes'] + RESERVE:
        raise ValueError('Insufficient KLC free storage for the planned extract.')
    sources, unavailable = discover(db)
    if unavailable or sources != report['sources']:
        raise ValueError('Source access or schema changed; run a new estimate.')
    prefix = prepare(db, sources)
    import pyarrow.dataset as ds
    retained_ids = ds.dataset(estimate_dir / 'cohort', format='parquet').to_table().column('user_id').to_pylist() if list((estimate_dir / 'cohort').glob('*.parquet')) else []
    if set(retained_ids) != set(db.info['mw_people']):
        raise ValueError('People cohort changed; run a new estimate.')
    output.mkdir(exist_ok=False)
    manifest = dict(status='incomplete', started_at_utc=now(), estimate=str(estimate_dir),
                    tables={}, budget_bytes=BUDGET, actual_bytes=0)
    path = output / 'manifest.json'
    save(path, manifest)
    try:
        for name, table in report['tables'].items():
            sql = table['sql']
            count = scalar(db, f'SELECT count(*) FROM ({sql}) selected')
            if count != table['rows']:
                raise ValueError(f'{name} row count changed; run a new estimate.')
            folder = output / name
            folder.mkdir()
            state = dict(status='incomplete', expected_rows=count, rows=0, parts=0, bytes=0,
                         source=table['source'], sql=sql)
            manifest['tables'][name] = state
            save(path, manifest)
            print(f'Downloading {name}: {count:,} rows', flush=True)
            with db.execution_options(stream_results=True).execute(__import__('sqlalchemy').text(sql), {'people': db.info['mw_people']}) as result:
                while True:
                    records = result.fetchmany(chunksize)
                    if not records:
                        break
                    frame = pd.DataFrame({name: pd.Series([r[index] for r in records], dtype=object)
                                          for index, name in enumerate(result.keys())})
                    size = write_part(frame, folder / f"part-{state['parts']:06d}.parquet",
                                      footprint(estimate_dir) + footprint(output),
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


def main(argv=None):
    import pyarrow as pa
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['estimate', 'download'])
    parser.add_argument('--estimate', type=Path, help='Completed estimate directory for download')
    parser.add_argument('--pilot-rows', type=int, default=2000)
    parser.add_argument('--chunksize', type=int, default=5000)
    parser.add_argument('--timeout', type=int, default=21600, help='Per-statement timeout in seconds')
    parser.add_argument('--download-if-safe', action='store_true', help='Download after estimate passes all gates')
    args = parser.parse_args(argv)
    if args.pilot_rows < 100 or args.chunksize < 1 or args.timeout < 1:
        parser.error('pilot-rows >= 100, chunksize >= 1 and timeout >= 1 required')
    root = Path(os.environ.get('KLC_ROOT', str(ROOT))).resolve()
    if not os.environ.get('KLC_ROOT') or not str(root).startswith(('/kellogg/proj/', '/gpfs/kellogg/proj/')):
        parser.error('Run through the KLC job toolkit; data must remain on KLC project storage')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = root / 'data' / ('malawi_' + stamp)
    output.parent.mkdir(exist_ok=True)
    estimate_dir = args.estimate or root / 'results' / ('malawi_estimate_' + stamp)
    print(f'Estimate directory: {estimate_dir}; data directory: {output}', flush=True)
    with connection() as conn:
        if args.command == 'estimate':
            with session(conn, args.timeout) as db:
                report = estimate(db, root, estimate_dir, args.pilot_rows)
            if not args.download_if_safe:
                return
        else:
            if args.estimate is None:
                parser.error('download requires --estimate')
            report = json.loads((estimate_dir / 'estimate.json').read_text())
        gate(report)
        with session(conn, args.timeout) as db:
            download(db, report, estimate_dir, output, args.chunksize)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Malawi workflow stopped: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
