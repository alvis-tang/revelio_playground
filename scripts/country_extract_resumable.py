"""Checkpoint country extracts at transaction boundaries, with transport retries."""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
from pathlib import Path
import shutil
import time

import malawi_extract as m

VERSION = 1
PRIORITY = '__extract_priority'
SNAPSHOTS = 'Frozen cohorts; separate repeatable-read snapshots per work unit; source contents can change.'


@contextmanager
def locked(folder):
    with (folder / '.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('This run already has a worker.') from None
        yield


class Queries:
    """Keep a healthy WRDS connection, but never retry a committed unit."""
    def __init__(self, settings):
        self.settings = settings
        self.stack = ExitStack()
        self.conn = None
        self.sources = None
        self.info = {'country': settings['country'], 'mw_people': [], 'posting_ids': [],
                     'mw_raw_batch_size': settings['raw_batch_size'],
                     'posting_batch_size': settings['posting_batch_size']}

    def close(self):
        self.stack.close()
        self.conn = None

    def call(self, action):
        from sqlalchemy.exc import OperationalError
        from psycopg2 import OperationalError as DriverOperationalError
        for attempt in range(3):
            try:
                fresh = self.conn is None
                if fresh:
                    self.conn = self.stack.enter_context(m.connection(preserve_transport_errors=True))
                with m.session(self.conn, self.settings['timeout']) as db:
                    db.exec_driver_sql('SET TRANSACTION READ ONLY')
                    db.info.update(self.info)
                    if fresh and self.sources is not None:
                        sources, unavailable = m.discover(db)
                        if unavailable or sources != self.sources:
                            raise ValueError('Source access or schema changed; start a fresh estimate.')
                    result = action(db)
                # Exiting the transaction is part of the unit: commit can fail too.
                return result
            except (OperationalError, DriverOperationalError) as exc:
                code = getattr(getattr(exc, 'orig', exc), 'pgcode', None)
                self.close()
                if code and not code.startswith('08'):
                    raise
                if attempt == 2:
                    raise
                print(f'WRDS transport failure; retrying unfinished unit ({attempt + 1}/2)', flush=True)
                time.sleep(2)


def clean(folder):
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)


def cohort_digest(folder):
    digest = hashlib.sha256()
    for path in sorted(folder.glob('part-*.parquet')):
        digest.update(path.name.encode())
        with path.open('rb') as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(block)
    return digest.hexdigest()


def load_ids(folder, column):
    import pyarrow.parquet as pq
    ids = []
    for path in sorted(folder.glob('part-*.parquet')):
        ids.extend(pq.read_table(path).column(column).to_pylist())
    return sorted(ids)


def cohort(queries, state, folder, kind):
    key, column, info_key = ('cohort', 'user_id', 'mw_people') if kind == 'people' else ('posting_cohort', 'job_id', 'posting_ids')
    target = folder / key
    if not state['cohorts'].get(kind):
        def collect(db):
            staging = folder / (key + '.pending')
            clean(staging)
            # Existing collectors create their own destination.
            destination = staging / 'ids'
            if kind == 'people':
                m.prepare(db, state['sources'], destination, m.footprint(folder))
            else:
                m.prepare_postings(db, state['sources'], destination, m.footprint(folder))
            return destination
        destination = queries.call(collect)
        if target.exists():
            shutil.rmtree(target)  # Only an uncommitted cohort from this run.
        destination.replace(target)
        shutil.rmtree(destination.parent)
        state['cohorts'][kind] = {'path': key, 'column': column, 'sha256': cohort_digest(target)}
        m.save(folder / 'checkpoint.json', state)
    if not target.is_dir() or cohort_digest(target) != state['cohorts'][kind]['sha256']:
        raise ValueError('Frozen cohort files changed or are missing.')
    queries.info[info_key] = load_ids(target, column)
    print(f'Frozen {kind} cohort: {len(queries.info[info_key]):,} IDs', flush=True)


def units(queries, sources, name, unmatched=False):
    """Deterministic units built only from frozen cohorts and saved settings."""
    from types import SimpleNamespace
    db = SimpleNamespace(info=queries.info)
    country = queries.settings['country']
    if name == 'individual_positions_raw':
        yield from m.raw_batches(db, sources, unmatched)
    elif name == 'postings_cosmos_raw':
        yield from m.posting_batches(db, sources, unmatched)
    elif unmatched and name == 'individual_user_education_raw':
        people = queries.info['mw_people']
        size = queries.settings['raw_batch_size']
        sql = (f"SELECT p.* FROM {sources['individual_user_education']['source']} p "
               "WHERE p.user_id = ANY(CAST(:people AS numeric[])) "
               f"AND NOT EXISTS (SELECT 1 FROM {sources[name]['source']} r "
               "WHERE r.user_id=p.user_id AND r.education_number=p.education_number)")
        for start in range(0, len(people), size):
            yield sql, {'people': people[start:start + size]}
    else:
        prefix = m.selection_prefix(sources, country)
        yield m.query(name, source_for(sources, name), prefix, country), {'people': queries.info['mw_people']}


def source_for(sources, name):
    return sources.get(name, {'source': 'mw_people', 'columns': [dict(column_name='user_id', data_type='numeric')]})


def sample_unit(db, sql, params, source, limit, seed):
    import pandas as pd
    from sqlalchemy import text
    count = m.scalar(db, f'SELECT count(*) FROM ({sql}) selected', params)
    m.execute(db, f'SELECT setseed({seed})')
    priority = PRIORITY
    while priority in {c['column_name'] for c in source['columns']}:
        priority += '_'
    frame = pd.read_sql_query(text(f'SELECT selected.*, random() AS "{priority}" FROM ({sql}) selected '
                                  f'ORDER BY "{priority}" LIMIT {limit}'), db, params=params, coerce_float=False)
    frame[priority] = pd.to_numeric(frame[priority])
    return count, frame, priority


def persist_sample(frame, path, source, priority, used):
    import pyarrow as pa
    schema = m.arrow_schema(source).append(pa.field(priority, pa.float64()))
    m.write_part(frame, path, used, schema=schema)


def estimate_tables(queries, state, folder, sources):
    import pandas as pd
    settings = state['settings']
    for name, source in sources.items():
        progress = state['estimate_units'].setdefault(name, {'counts': [], 'sample': None})
        table_folder = folder / name
        table_folder.mkdir(exist_ok=True)
        # Delete abandoned generations; the checkpoint references exactly one.
        for path in table_folder.glob('sample-*'):
            if path.name != progress['sample']:
                path.unlink()
        for index, (sql, params) in enumerate(units(queries, state['sources'], name)):
            if index < len(progress['counts']):
                continue
            count, candidate, priority = queries.call(lambda db: sample_unit(
                db, sql, params, source, settings['pilot_rows'], ((index * 7919 + 7409) % 100000) / 100000))
            previous = table_folder / progress['sample'] if progress['sample'] else None
            if previous:
                old = pd.read_parquet(previous)
                candidate = pd.concat([old, candidate], ignore_index=True)
            candidate[priority] = pd.to_numeric(candidate[priority])
            candidate = candidate.nsmallest(settings['pilot_rows'], priority).reset_index(drop=True)
            path = table_folder / f'sample-{index:06d}.parquet'
            persist_sample(candidate, path, source, priority, m.footprint(folder))
            progress['counts'].append(count)
            progress['sample'] = path.name
            progress['priority'] = priority
            m.save(folder / 'checkpoint.json', state)
            if previous:
                previous.unlink()
            print(f'{name}: estimate unit {index + 1}; cumulative {sum(progress["counts"]):,} rows', flush=True)
        if name in state['report']['tables']:
            continue
        frame = (pd.read_parquet(table_folder / progress['sample']).drop(columns=[progress['priority']])
                 if progress['sample'] else pd.DataFrame(columns=[c['column_name'] for c in source['columns']]))
        sizes, counts = [], []
        for path in table_folder.glob('pilot-*'):
            path.unlink()  # Rebuild only this not-yet-committed projection.
        width = max(1, math.ceil(len(frame) / 4))
        for start in range(0, len(frame), width):
            part = frame.iloc[start:start + width]
            sizes.append(m.write_part(part, table_folder / f'pilot-{start // width:02d}.parquet',
                                      m.footprint(folder), schema=m.arrow_schema(source)))
            counts.append(len(part))
        rows = sum(progress['counts'])
        projection = m.storage_projection(rows, sizes, counts, sum(sizes))
        if rows == len(frame):
            projection.update(expected_bytes=sum(sizes), planning_bytes=math.ceil(sum(sizes) * 1.3))
        state['report']['tables'][name] = dict(rows=rows, source=source['source'], pilot_rows=len(frame),
            execution='checkpointed_units', unit_counts=progress['counts'], **projection)
        m.save(folder / 'checkpoint.json', state)
        m.save(folder / 'estimate.json', state['report'])


def unmatched_checks(queries, state, folder, phase):
    result = {}
    for name in ('individual_positions_raw', 'individual_user_education_raw', 'postings_cosmos_raw'):
        key = phase + ':' + name
        counts = state['unmatched_units'].setdefault(key, [])
        for index, (sql, params) in enumerate(units(queries, state['sources'], name, True)):
            if index < len(counts):
                continue
            count = queries.call(lambda db: m.scalar(db, f'SELECT count(*) FROM ({sql}) selected', params))
            counts.append(count)
            m.save(folder / 'checkpoint.json', state)
            print(f'{phase} unmatched {name}: unit {index + 1}; cumulative {sum(counts):,}', flush=True)
        result[name] = sum(counts)
    return result


def download_unit(db, sql, params, source, expected, staging, estimate_dir, output, chunksize):
    import pandas as pd
    from sqlalchemy import text
    clean(staging)
    count = m.scalar(db, f'SELECT count(*) FROM ({sql}) selected', params)
    if count != expected:
        raise ValueError('Unit row count changed; start a fresh estimate.')
    rows, parts, size = 0, 0, 0
    with db.execution_options(stream_results=True).execute(text(sql), params) as result:
        columns = list(result.keys())
        while True:
            records = result.fetchmany(chunksize)
            if not records:
                break
            frame = pd.DataFrame({name: pd.Series([r[i] for r in records], dtype=object)
                                  for i, name in enumerate(columns)})
            size += m.write_part(frame, staging / f'part-{parts:06d}.parquet',
                                 m.footprint(estimate_dir) + m.footprint(output), schema=m.arrow_schema(source))
            rows += len(frame)
            parts += 1
    if rows != expected:
        raise ValueError('Unit extracted row count mismatch.')
    return dict(rows=rows, parts=parts, bytes=size, finished_at_utc=m.now())


def download_tables(queries, state, folder, sources):
    import pyarrow.parquet as pq
    output = Path(state['output'])
    output.mkdir(exist_ok=True)
    manifest = state.setdefault('manifest', dict(status='incomplete', country=state['settings']['country'],
        started_at_utc=m.now(), estimate=str(folder), tables={}, budget_bytes=m.BUDGET,
        snapshots=SNAPSHOTS, resumable=True, raw_batch_size=state['settings']['raw_batch_size'],
        posting_batch_size=state['settings']['posting_batch_size']))
    m.save(output / 'manifest.json', manifest)
    for name, source in sources.items():
        table_folder = output / name
        table_folder.mkdir(exist_ok=True)
        progress = manifest['tables'].setdefault(name, dict(status='incomplete', units=[], rows=0, parts=0, bytes=0,
                                                           source=source['source'], expected_rows=state['report']['tables'][name]['rows']))
        committed = len(progress['units'])
        # Unit rename may have succeeded before checkpoint commit: rerun that unit.
        for path in table_folder.iterdir():
            if path.name == '.pending' or (path.name.startswith('unit-') and int(path.name[5:]) >= committed):
                shutil.rmtree(path)
        for index in range(committed):
            unit_folder = table_folder / f'unit-{index:06d}'
            paths = list(unit_folder.glob('part-*.parquet'))
            saved = progress['units'][index]
            if (len(paths) != saved['parts'] or sum(p.stat().st_size for p in paths) != saved['bytes']
                    or sum(pq.read_metadata(p).num_rows for p in paths) != saved['rows']):
                raise ValueError('Committed download files changed or are missing.')
        expected = state['report']['tables'][name]['unit_counts']
        for index, (sql, params) in enumerate(units(queries, state['sources'], name)):
            if index < committed:
                continue
            staging = table_folder / '.pending'
            saved = queries.call(lambda db: download_unit(db, sql, params, source, expected[index], staging,
                                                          folder, output, state['settings']['chunksize']))
            staging.replace(table_folder / f'unit-{index:06d}')
            progress['units'].append(saved)
            for key in ('rows', 'parts', 'bytes'):
                progress[key] += saved[key]
            m.save(folder / 'checkpoint.json', state)
            m.save(output / 'manifest.json', manifest)
            print(f'{name}: downloaded unit {index + 1}; {progress["rows"]:,} rows', flush=True)
        if progress['rows'] != state['report']['tables'][name]['rows']:
            raise ValueError('Table row count mismatch.')
        progress['status'] = 'complete'
        m.save(table_folder / 'manifest.json', progress)
        m.save(folder / 'checkpoint.json', state)
        m.save(output / 'manifest.json', manifest)
    manifest['unmatched_raw'] = unmatched_checks(queries, state, folder, 'download')
    manifest.update(status='complete', finished_at_utc=m.now(),
                    actual_bytes=sum(t['bytes'] for t in manifest['tables'].values()))
    manifest['stored_bytes_including_estimate'] = m.footprint(folder) + m.footprint(output)
    if manifest['stored_bytes_including_estimate'] + m.RESERVE > m.BUDGET:
        manifest['status'] = 'incomplete'
        raise ValueError('20 GB storage cap reached.')
    state['status'] = 'complete'
    m.save(folder / 'checkpoint.json', state)
    m.save(output / 'manifest.json', manifest)
    print(f'DOWNLOAD COMPLETE: {output}', flush=True)


def run(args, root):
    root = root.resolve()
    if args.resume:
        folder = args.resume.resolve()
    elif args.command == 'download':
        if args.estimate is None:
            raise ValueError('Resumable download requires --estimate.')
        folder = args.estimate.resolve()
    else:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        folder = root / 'results' / (args.country.lower().replace(' ', '_') + '_estimate_' + stamp)
        folder.mkdir(parents=True, exist_ok=False)
    if not folder.is_relative_to(root / 'results'):
        raise ValueError('Run must remain under this KLC project results directory.')
    with locked(folder):
        path = folder / 'checkpoint.json'
        if args.resume or args.command == 'download':
            state = json.loads(path.read_text())
            if state['version'] != VERSION or state['root'] != str(root):
                raise ValueError('Incompatible checkpoint or project.')
            if args.command == 'download':
                state['settings']['download_if_safe'] = True
        else:
            settings = {key: getattr(args, key) for key in ('country', 'raw_batch_size', 'posting_batch_size',
                        'pilot_rows', 'chunksize', 'timeout', 'download_if_safe')}
            report = dict(status='incomplete', version=m.VERSION, country=args.country, resumable=True,
                          snapshots=SNAPSHOTS, started_at_utc=m.now(), tables={}, unavailable=[], budget_bytes=m.BUDGET)
            state = dict(version=VERSION, root=str(root), status='incomplete', settings=settings, cohorts={},
                         estimate_units={}, unmatched_units={}, report=report,
                         output=str(root / 'data' / (args.country.lower().replace(' ', '_') + '_' + stamp)))
            m.save(path, state)
        print(f'Resumable estimate: {folder}; data: {state["output"]}', flush=True)
        state.pop('error_type', None)
        if state.get('manifest'):
            state['manifest'].pop('error_type', None)
        queries = Queries(state['settings'])
        try:
            if state['status'] == 'complete':
                m.save(Path(state['output']) / 'manifest.json', state['manifest'])
                print('Run already complete.', flush=True)
                return
            sources, unavailable = queries.call(m.discover)
            if unavailable:
                state['report']['unavailable'] = unavailable
                raise ValueError('Missing products: ' + ', '.join(unavailable))
            if state.get('sources') and sources != state['sources']:
                raise ValueError('Source schema changed; start a fresh estimate.')
            state['sources'] = sources
            queries.sources = sources
            for source in sources.values():
                m.arrow_schema(source)
            m.save(path, state)
            for kind in ('people', 'postings'):
                cohort(queries, state, folder, kind)
            products = dict(sources)
            products['people_cohort'] = source_for(sources, 'people_cohort')
            if state['report']['status'] != 'complete':
                estimate_tables(queries, state, folder, products)
                report = state['report']
                report['unmatched_raw'] = unmatched_checks(queries, state, folder, 'estimate')
                report.update(sources=sources, raw_batch_size=state['settings']['raw_batch_size'],
                              posting_batch_size=state['settings']['posting_batch_size'])
                retained = m.footprint(folder)
                report['expected_total_bytes'] = sum(t['expected_bytes'] for t in report['tables'].values()) + retained
                report['planning_total_bytes'] = sum(t['planning_bytes'] for t in report['tables'].values()) + retained + m.RESERVE
                report.update(status='complete', finished_at_utc=m.now())
                m.save(path, state)
                m.save(folder / 'estimate.json', report)
            if not state['settings']['download_if_safe']:
                return
            m.gate(state['report'], resumable=True)
            output = Path(state['output'])
            output.parent.mkdir(exist_ok=True)
            committed_bytes = sum(t['bytes'] for t in state.get('manifest', {}).get('tables', {}).values())
            if shutil.disk_usage(output.parent).free + committed_bytes < state['report']['planning_total_bytes'] + m.RESERVE:
                raise ValueError('Insufficient KLC storage for planned extract.')
            download_tables(queries, state, folder, products)
        except BaseException as exc:
            # Do not persist exception SQL/parameters (which may contain millions of IDs).
            state['error_type'] = type(exc).__name__
            m.save(path, state)
            m.save(folder / 'estimate.json', state['report'])
            if state.get('manifest'):
                state['manifest']['error_type'] = type(exc).__name__
                m.save(Path(state['output']) / 'manifest.json', state['manifest'])
            raise
        finally:
            queries.close()
