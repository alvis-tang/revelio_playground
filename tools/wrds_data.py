"""SQL discovery, bounded streaming extraction, and small Stata exports."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def connect_args():
    """Preserve WRDS defaults while keeping long, silent queries connected."""
    from wrds.sql import WRDS_CONNECT_ARGS
    return {**WRDS_CONNECT_ARGS, 'connect_timeout': 30, 'keepalives': 1,
            'keepalives_idle': 30, 'keepalives_interval': 30,
            'keepalives_count': 9}


@contextmanager
def connection():
    import wrds
    settings = json.loads((ROOT / '.klc/config.json').read_text())
    # Never let WRDS fall back to password prompts in background job logs.
    if not (Path.home() / '.pgpass').exists():
        raise ValueError('Run ./klc credentials before connecting to WRDS.')
    from unittest.mock import patch
    try:
        with patch('builtins.input', side_effect=ValueError('WRDS authentication failed; run credentials and doctor interactively.')):
            conn = wrds.Connection(wrds_username=settings['wrds_username'],
                                   wrds_connect_args=connect_args())
    except Exception:
        raise ValueError('WRDS connection failed. Check credentials, network, and Duo using ./klc doctor.') from None
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def streaming(conn, sql, params, chunksize):
    # WRDS defaults to AUTOCOMMIT; PostgreSQL named cursors need a transaction.
    original = conn.connection
    with conn.engine.connect() as stream:
        stream = stream.execution_options(isolation_level='READ COMMITTED',
                                          stream_results=True, max_row_buffer=chunksize)
        with stream.begin():
            conn.connection = stream
            try:
                yield conn.raw_sql(sql, params=params, chunksize=chunksize, return_iter=True)
            finally:
                conn.connection = original


def extract(conn, sql, params, output, chunksize=100_000):
    if chunksize < 1:
        raise ValueError('Chunk size must be positive.')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(status='incomplete', rows=0, parts=0, sql=sql, parameters=params,
                    chunksize=chunksize)
    def checkpoint():
        temporary = output / 'manifest.tmp'
        temporary.write_text(json.dumps(manifest, indent=2) + '\n')
        temporary.replace(output / 'manifest.json')
    checkpoint()
    # return_iter is necessary: chunksize alone can still concatenate every chunk.
    try:
        with streaming(conn, sql, params, chunksize) as chunks:
            for frame in chunks:
                if frame.empty:
                    continue
                part = output / f'part-{manifest["parts"]:06d}.parquet'
                temporary = part.with_suffix('.parquet.tmp')
                frame.to_parquet(temporary, index=False)
                temporary.replace(part)
                manifest['rows'] += len(frame)
                manifest['parts'] += 1
                checkpoint()
        manifest['status'] = 'complete'
        checkpoint()
    except BaseException:
        # Initial manifest also survives hard termination or machine restart.
        checkpoint()
        raise
    return manifest


def export_stata(source, output, max_rows):
    import pandas as pd
    import pyarrow.dataset as ds
    if max_rows < 1:
        raise ValueError('max-rows must be positive.')
    source = Path(source)
    manifest = source / 'manifest.json'
    if manifest.exists() and json.loads(manifest.read_text())['status'] != 'complete':
        raise ValueError('Cannot export an incomplete extract.')
    files = sorted(source.glob('*.parquet')) if source.is_dir() else [source]
    if not files:
        raise ValueError('No Parquet data found.')
    dataset = ds.dataset([str(p) for p in files], format='parquet')
    if dataset.count_rows() > max_rows:
        raise ValueError('Dataset exceeds max-rows. Aggregate or filter before exporting to Stata.')
    frame = dataset.to_table().to_pandas()
    for name in frame.columns:
        column = frame[name]
        if pd.api.types.is_integer_dtype(column.dtype):
            values = column.dropna()
            if ((values > 2**53) | (values < -(2**53))).any():
                raise ValueError(f'{name} exceeds exact Stata integer precision; keep this identifier as text.')
            frame[name] = column.astype('float64' if column.isna().any() else 'int64')
        elif pd.api.types.is_bool_dtype(column.dtype):
            frame[name] = column.astype('float64' if column.isna().any() else 'int8')
        elif isinstance(column.dtype, pd.StringDtype):
            frame[name] = column.fillna('').astype(object)
        elif pd.api.types.is_extension_array_dtype(column.dtype) and pd.api.types.is_float_dtype(column.dtype):
            frame[name] = column.astype('float64')
        elif column.dtype == object:
            from datetime import date, datetime
            values = column.dropna()
            if not values.empty and all(isinstance(value, (date, datetime)) for value in values):
                frame[name] = pd.to_datetime(column)
    output = Path(output)
    if output.exists():
        raise ValueError('Output already exists.')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.dta.tmp')
    frame.to_stata(temporary, write_index=False, version=118)
    temporary.replace(output)


def main(argv=None):
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    discover = commands.add_parser('discover')
    discover.add_argument('--schema')
    discover.add_argument('--table')
    query = commands.add_parser('extract')
    query.add_argument('sql_file')
    query.add_argument('--params', default='{}', help='JSON object of SQL bind parameters')
    query.add_argument('--output', required=True)
    query.add_argument('--chunksize', type=int, default=100_000)
    export = commands.add_parser('export-stata')
    export.add_argument('source')
    export.add_argument('output')
    export.add_argument('--max-rows', type=int, default=100_000)
    ns = parser.parse_args(argv)
    if ns.command == 'export-stata':
        export_stata(ns.source, ns.output, ns.max_rows)
        return
    if ns.command == 'discover' and ns.table and not ns.schema:
        parser.error('--table requires --schema')
    with connection() as conn:
        if ns.command == 'discover':
            if ns.table:
                print(conn.describe_table(library=ns.schema, table=ns.table).to_string(index=False))
            elif ns.schema:
                print('\n'.join(conn.list_tables(library=ns.schema)))
            else:
                libraries = [x for x in conn.list_libraries() if 'revelio' in x.lower()]
                if not libraries:
                    raise ValueError('No accessible Revelio schemas found. Verify your WRDS subscription permissions.')
                print('\n'.join(libraries))
        else:
            params = json.loads(ns.params)
            if not isinstance(params, dict):
                raise ValueError('--params must be a JSON object.')
            print(json.dumps(extract(conn, Path(ns.sql_file).read_text(), params,
                                     ns.output, ns.chunksize), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyboardInterrupt) as exc:
        print(f'WRDS: {exc}', file=sys.stderr)
        sys.exit(1)
