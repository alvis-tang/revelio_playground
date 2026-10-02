"""Summarize historical position records and people by recorded country on WRDS."""
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from wrds_data import connection


def identifier(value):
    """Quote a single SQL identifier, never an SQL expression or dotted name."""
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value):
        raise ValueError(f'Invalid SQL identifier: {value!r}')
    return '"' + value + '"'


def coverage_sql(schema, table, country_column, person_column, person_is_numeric=False):
    source = f'{identifier(schema)}.{identifier(table)}'
    country, person = identifier(country_column), identifier(person_column)
    person_expression = person if person_is_numeric else f"NULLIF(TRIM(CAST({person} AS TEXT)), '')"
    # GROUPING distinguishes the global total from the missing-country group.
    # One statement gives country and global counts from the same snapshot.
    return f'''
SELECT country,
       GROUPING(country) AS is_total,
       COUNT(*) AS position_records,
       COUNT(DISTINCT person_id) AS people,
       COUNT(*) - COUNT(person_id) AS missing_person_records
FROM (
    SELECT NULLIF(TRIM(CAST({country} AS TEXT)), '') AS country,
           {person_expression} AS person_id
    FROM {source}
) AS positions
GROUP BY GROUPING SETS ((country), ())
ORDER BY is_total, position_records DESC, country
'''.strip()


def summarize(records):
    totals = [r for r in records if int(r['is_total']) == 1]
    if len(totals) != 1:
        raise ValueError('Expected exactly one global total from WRDS.')
    total = totals[0]
    counts = ('position_records', 'people', 'missing_person_records')
    for record in records:
        for key in counts:
            value = record[key]
            if value is None or int(value) != value or int(value) < 0:
                raise ValueError(f'Invalid aggregate count: {key}.')
        if int(record['people']) + int(record['missing_person_records']) > int(record['position_records']):
            raise ValueError('Person counts exceed position records.')
    countries = []
    position_total = int(total['position_records'])
    for record in records:
        if int(record['is_total']) == 1:
            continue
        missing = record['country'] is None
        countries.append(dict(
            country='Unknown' if missing else record['country'],
            country_missing=missing,
            **{key: int(record[key]) for key in counts},
            position_share_pct=(100 * int(record['position_records']) / position_total
                                if position_total else 0.0),
        ))
    countries.sort(key=lambda r: (-r['position_records'], r['country'], r['country_missing']))
    if sum(r['position_records'] for r in countries) != position_total:
        raise ValueError('Country position counts do not match the global total.')
    if sum(r['missing_person_records'] for r in countries) != int(total['missing_person_records']):
        raise ValueError('Country missing-ID counts do not match the global total.')
    if any(r['people'] > int(total['people']) for r in countries):
        raise ValueError('Country people count exceeds the global distinct count.')
    if position_total and abs(sum(r['position_share_pct'] for r in countries) - 100) > 1e-8:
        raise ValueError('Country shares do not sum to 100 percent.')
    summary = {key: int(total[key]) for key in counts}
    summary['named_countries'] = sum(not r['country_missing'] for r in countries)
    summary['unknown_country_position_records'] = sum(
        r['position_records'] for r in countries if r['country_missing'])
    return countries, summary


def save_results(root, countries, summary, started_at):
    output = Path(root) / 'results' / ('country_coverage_' + started_at.strftime('%Y%m%dT%H%M%S%fZ'))
    output.mkdir(parents=True, exist_ok=False)
    columns = ('country', 'country_missing', 'position_records', 'people',
               'missing_person_records', 'position_share_pct')
    with (output / 'countries.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(countries)
    # summary.json is the completion marker; failed writes leave no complete summary.
    temporary = output / 'summary.json.tmp'
    temporary.write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(output / 'summary.json')
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('schema', 'table', 'country-column', 'person-column'):
        parser.add_argument('--' + name, required=True,
                            help='Verified WRDS identifier; run ./klc wrds discover first')
    args = parser.parse_args(argv)
    # Validate identifiers before any network access.
    coverage_sql(args.schema, args.table, args.country_column, args.person_column)
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    print(f'Source: {args.schema}.{args.table}; all available history', flush=True)
    print('Querying WRDS for country and global aggregates...', flush=True)
    with connection() as conn:
        metadata = conn.raw_sql('''
SELECT data_type FROM information_schema.columns
WHERE table_schema = %(schema)s AND table_name = %(table)s
  AND column_name = %(person_column)s
''', params=dict(schema=args.schema, table=args.table, person_column=args.person_column))
        if len(metadata) != 1:
            raise ValueError('Person column not found; verify identifiers with WRDS discovery.')
        person_type = metadata.iloc[0]['data_type']
        numeric_types = {'numeric', 'decimal', 'smallint', 'integer', 'bigint', 'real', 'double precision'}
        sql = coverage_sql(args.schema, args.table, args.country_column, args.person_column,
                           person_is_numeric=person_type in numeric_types)
        records = conn.raw_sql(sql).to_dict(orient='records')
    countries, summary = summarize(records)
    finished_at = datetime.now(timezone.utc)
    summary.update(
        status='complete',
        source=dict(schema=args.schema, table=args.table,
                    country_column=args.country_column, person_column=args.person_column,
                    person_data_type=person_type),
        started_at_utc=started_at.isoformat(),
        finished_at_utc=finished_at.isoformat(),
        elapsed_seconds=round(time.monotonic() - started, 3),
        sql=sql,
        definitions=dict(
            position_records='Source row count; verify that each row represents one position.',
            people='Distinct nonmissing person IDs; country counts are not additive.',
            country='Recorded position country, trimmed; NULL/blank is Unknown.',
            missing_person_records='Rows with NULL or blank person IDs after trimming.',
            position_share_pct='Country records / all records, including Unknown, times 100.',
            named_countries='Distinct nonmissing country labels, without geographic recoding.',
            time_range='All available history; no date filter; not current employment.',
        ),
    )
    output = save_results(os.environ.get('KLC_ROOT', str(ROOT)), countries, summary, started_at)
    print(f"Total position records: {summary['position_records']:,}")
    print(f"Globally distinct people: {summary['people']:,}")
    print(f"Named countries: {summary['named_countries']:,}")
    print(f"Missing person-ID records: {summary['missing_person_records']:,}")
    print(f"Unknown-country records: {summary['unknown_country_position_records']:,}")
    print('Largest 20 countries (positions, people, position share):')
    for row in countries[:20]:
        label = row['country'] + (' [missing country]' if row['country_missing'] else '')
        print(f"{label}: {row['position_records']:,}; {row['people']:,}; {row['position_share_pct']:.2f}%")
    print(f'Results: {output}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Country coverage failed: {exc}', file=sys.stderr)
        sys.exit(1)
