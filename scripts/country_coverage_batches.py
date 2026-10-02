"""Resumable counts using disjoint, indexed numeric person-ID ranges."""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR
import fcntl
import json
import os
from pathlib import Path
import time

from country_coverage import coverage_sql, identifier, summarize, write_results
from wrds_data import connection

COUNTS = ('position_records', 'people', 'missing_person_records')
VERSION = 1


def save(path, state):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def merge(records, batch):
    # Every nonmissing person belongs to exactly one range, making distinct
    # counts additive across batches, including the separately computed total.
    summarize(batch)
    merged = {(r['country'], int(r['is_total'])): dict(r) for r in records}
    for row in batch:
        key = (row['country'], int(row['is_total']))
        target = merged.setdefault(key, dict(country=key[0], is_total=key[1],
                                            **{name: 0 for name in COUNTS}))
        for name in COUNTS:
            target[name] += int(row[name])
    result = list(merged.values())
    summarize(result)
    return result


@contextmanager
def queries(timeout):
    """Reuse a healthy connection; reconnect only for transport failures."""
    from sqlalchemy.exc import OperationalError
    stack = ExitStack()
    conn = None

    def query(sql, params=None):
        nonlocal conn
        for attempt in range(3):
            try:
                if conn is None:
                    conn = stack.enter_context(connection())
                original = conn.connection
                with conn.engine.connect() as db:
                    db = db.execution_options(isolation_level='READ COMMITTED')
                    with db.begin():
                        db.exec_driver_sql('SET TRANSACTION READ ONLY')
                        db.exec_driver_sql(f"SET LOCAL statement_timeout = '{int(timeout)}s'")
                        conn.connection = db
                        try:
                            return conn.raw_sql(sql, params=params).to_dict(orient='records')
                        finally:
                            conn.connection = original
            except OperationalError as exc:
                code = getattr(exc.orig, 'pgcode', None)
                if code and not code.startswith('08'):
                    raise  # Includes statement cancellation; don't repeat expensive SQL.
                stack.close()
                conn = None
                if attempt == 2:
                    raise
                print(f'WRDS connection lost; retrying unsaved batch ({attempt + 1}/2)', flush=True)
                time.sleep(2)
    try:
        yield query
    finally:
        stack.close()


def run(args):
    source = dict(schema=args.schema, table=args.table, country_column=args.country_column,
                  person_column=args.person_column)
    root = Path(os.environ.get('KLC_ROOT', '.'))
    stamp = datetime.now(timezone.utc)
    output = args.resume or root / 'results' / ('country_coverage_' + stamp.strftime('%Y%m%dT%H%M%S%fZ'))
    output = output.resolve()
    if not args.resume:
        output.mkdir(parents=True, exist_ok=False)
    print(f'Batched worldwide coverage; results/checkpoint: {output}', flush=True)
    # A second resume must not race a running worker or overwrite its checkpoint.
    with (output / '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('This results directory already has a running worker.') from None
        checkpoint = output / 'checkpoint.json'
        state = None
        try:
            with queries(args.query_timeout) as query:
                if args.resume:
                    candidate = json.loads(checkpoint.read_text())
                    if candidate['version'] != VERSION or candidate['source'] != source:
                        raise ValueError('Resume source or checkpoint version does not match.')
                    state = candidate
                    if state['status'] == 'complete':
                        print('Coverage already complete.', flush=True)
                        return
                else:
                    metadata = query('SELECT data_type FROM information_schema.columns '
                                     'WHERE table_schema=%(schema)s AND table_name=%(table)s '
                                     'AND column_name=%(person_column)s', source)
                    if len(metadata) != 1 or metadata[0]['data_type'] not in {
                            'numeric', 'decimal', 'smallint', 'integer', 'bigint'}:
                        raise ValueError('Batches require an exact numeric person-ID column.')
                    person = identifier(args.person_column)
                    bounds = query(f'SELECT min({person})::text AS lower, max({person})::text AS upper '
                                   f'FROM {identifier(args.schema)}.{identifier(args.table)}')[0]
                    lower = int(Decimal(bounds['lower']).to_integral_value(rounding=ROUND_FLOOR)) if bounds['lower'] is not None else 0
                    upper = int(Decimal(bounds['upper']).to_integral_value(rounding=ROUND_FLOOR)) + 1 if bounds['upper'] is not None else 0
                    state = dict(version=VERSION, status='incomplete', source=source,
                                 person_data_type=metadata[0]['data_type'],
                                 started_at_utc=stamp.isoformat(), lower=lower, upper=upper,
                                 next_lower=lower, batch_size=args.batch_size, completed_batches=0,
                                 null_done=False, records=[])
                    save(checkpoint, state)
                state.pop('error', None)
                person = identifier(args.person_column)
                while state['next_lower'] < state['upper'] or not state['null_done']:
                    lower = state['next_lower']
                    numeric = lower < state['upper']
                    upper = min(lower + state['batch_size'], state['upper'])
                    where = f'{person} >= %(lower)s AND {person} < %(upper)s' if numeric else f'{person} IS NULL'
                    label = f'IDs [{lower}, {upper})' if numeric else 'missing person IDs'
                    print(f'Batch {state["completed_batches"] + 1}: {label}', flush=True)
                    started = time.monotonic()
                    sql = coverage_sql(args.schema, args.table, args.country_column,
                                       args.person_column, person_is_numeric=True, where=where)
                    batch = query(sql, {'lower': lower, 'upper': upper} if numeric else None)
                    records = merge(state['records'], batch)
                    # Advance only after a successful query and validated aggregate.
                    state.update(records=records, next_lower=upper if numeric else lower,
                                 null_done=not numeric, completed_batches=state['completed_batches'] + 1,
                                 updated_at_utc=datetime.now(timezone.utc).isoformat())
                    save(checkpoint, state)
                    _, totals = summarize(records)
                    print(f'Saved batch in {time.monotonic()-started:.1f}s; cumulative '
                          f'{totals["position_records"]:,} positions, {totals["people"]:,} people', flush=True)
            countries, summary = summarize(state['records'])
            summary.update(status='complete', source={**source, 'person_data_type': state['person_data_type']},
                           started_at_utc=state['started_at_utc'],
                           finished_at_utc=datetime.now(timezone.utc).isoformat(),
                           method='Disjoint numeric person-ID ranges plus a NULL-ID batch',
                           batch_size=state['batch_size'], completed_batches=state['completed_batches'],
                           consistency='Each batch uses its own snapshot; source updates during or between runs can affect totals.',
                           definitions=dict(time_range='All available history; no date filter; not current employment.',
                                            people='Distinct nonmissing person IDs; country counts are not additive.',
                                            country='Recorded position country, trimmed; NULL/blank is Unknown.'))
            write_results(output, countries, summary)
            state['status'] = 'complete'
            save(checkpoint, state)
            print(f'WORLDWIDE COVERAGE COMPLETE: {summary["position_records"]:,} positions; '
                  f'{summary["people"]:,} people; {summary["named_countries"]} named countries. '
                  f'Results: {output}', flush=True)
        except Exception as exc:
            if state is not None and state.get('source') == source and state.get('status') != 'complete':
                state['error'] = str(exc)
                save(checkpoint, state)
            print(f'Resume with the same source arguments and --resume {output}', flush=True)
            raise
