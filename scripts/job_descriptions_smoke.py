"""Download a small preview of accessible WRDS Revelio job postings."""
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from wrds_data import connection

POSTING_COLUMNS = (
    'rcid', 'company', 'role_k1500_v2', 'role_k17000_v3', 'onet_code',
    'country', 'state', 'metro_area', 'seniority', 'salary', 'salary_min',
    'salary_max', 'salary_predicted', 'post_date', 'remove_date',
    'ultimate_parent_rcid', 'ultimate_parent_company_name', 'remote_type',
    'expected_hires', 'source_company_sites', 'source_linkedin', 'source_indeed',
    'source_zhaopin', 'source_51job', 'source_liepin',
    'source_other_aggregators', 'source_staffingfirms', 'source_regional_aggregators',
)


def preview_sql():
    fields = ',\n       '.join('p.' + name for name in POSTING_COLUMNS)
    # Materialize the bounded raw sample before joining billion-row tables.
    # Match BIGINT metadata IDs without casting the indexed metadata column to
    # NUMERIC. Out-of-range raw IDs remain unmatched and retain their full text.
    return f'''WITH sample AS MATERIALIZED (
    SELECT job_id, title_raw, jobtitle_translated, location_raw, description
    FROM revelio.postings_cosmos_raw
    WHERE description IS NOT NULL AND description ~ '[^[:space:]]'
    LIMIT %(limit)s
)
SELECT s.job_id::text AS job_id, s.title_raw, s.jobtitle_translated,
       s.location_raw, s.description,
       {fields}
FROM sample AS s
LEFT JOIN revelio.postings_cosmos AS p ON p.job_id = CASE
    WHEN s.job_id BETWEEN -9223372036854775808 AND 9223372036854775807
    THEN s.job_id::bigint END
LIMIT %(limit)s'''


def fetch_preview(conn, sql, limit):
    # WRDS normally uses AUTOCOMMIT; SET LOCAL needs an explicit transaction.
    original = conn.connection
    with conn.engine.connect() as transaction:
        transaction = transaction.execution_options(isolation_level='READ COMMITTED')
        with transaction.begin():
            transaction.exec_driver_sql("SET LOCAL statement_timeout = '60s'")
            conn.connection = transaction
            try:
                return conn.raw_sql(sql, params={'limit': limit}, coerce_float=False)
            finally:
                conn.connection = original


def save_preview(frame, root, sql, limit, started_at):
    if frame.empty:
        raise ValueError('No nonempty job descriptions returned from WRDS.')
    if len(frame) > limit:
        raise ValueError('WRDS returned more rows than the requested limit.')
    # pandas handles NULL/NaN and dates; SQL already preserves IDs as strings.
    records = json.loads(frame.to_json(orient='records', date_format='iso', force_ascii=False))
    output = Path(root) / 'data' / ('job_postings_preview_' + started_at.strftime('%Y%m%dT%H%M%S%fZ'))
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'descriptions.jsonl').open('w', encoding='utf-8') as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
    with (output / 'postings.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(frame.columns))
        writer.writeheader()
        writer.writerows(records)
    summary = dict(
        status='complete', rows=len(records), requested_limit=limit,
        columns=list(frame.columns),
        missing_value_counts={name: int(frame[name].isna().sum()) for name in frame.columns},
        sql=sql, parameters={'limit': limit}, statement_timeout_seconds=60,
        started_at_utc=started_at.isoformat(),
        finished_at_utc=datetime.now(timezone.utc).isoformat(),
        sources=['revelio.postings_cosmos_raw', 'revelio.postings_cosmos'],
        sampling='Arbitrary nonempty descriptions; not a representative or ordered sample.',
    )
    temporary = output / 'summary.json.tmp'
    temporary.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    temporary.replace(output / 'summary.json')
    return output, records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=20, help='Number of preview rows (1–100; default: 20)')
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 100:
        parser.error('--limit must be between 1 and 100')
    started_at = datetime.now(timezone.utc)
    sql = preview_sql()
    print(f'Downloading up to {args.limit} postings with nonempty descriptions...', flush=True)
    try:
        with connection() as conn:
            frame = fetch_preview(conn, sql, args.limit)
    except Exception as exc:
        raise ValueError('WRDS preview query failed. Check table access and credentials with '
                         './klc doctor; approve Duo if required. Query timeout is 60 seconds. '
                         f'Details: {exc}') from exc
    output, records = save_preview(frame, os.environ.get('KLC_ROOT', str(ROOT)), sql, args.limit, started_at)
    print(f'Downloaded {len(records)} rows. Results: {output}')
    print('Available fields: ' + ', '.join(frame.columns))
    print('First five previews (full descriptions are in the saved files):')
    for record in records[:5]:
        title = record.get('title_raw') or record.get('jobtitle_translated')
        location = record.get('location_raw') or record.get('country')
        excerpt = ' '.join(record['description'].split())[:200]
        print(f"Job {record['job_id']} | {record.get('company')} | {title} | "
              f"{location} | {record.get('post_date')}\n  {excerpt}")


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Job postings preview failed: {exc}', file=sys.stderr)
        sys.exit(1)
