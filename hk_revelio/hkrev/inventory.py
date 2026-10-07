"""Stage 00: inventory every downloaded table and generate the data dictionary."""
import json
from pathlib import Path
import re

from .common import StageRun, lit, now, save_json

NUMERIC = re.compile(r'^(TINYINT|SMALLINT|INTEGER|BIGINT|HUGEINT|DOUBLE|FLOAT|REAL|DECIMAL.*)$')
TEMPORAL = re.compile(r'^(DATE|TIME.*|TIMESTAMP.*)$')

# Short meanings, in our own words, for fields used by the measurement stages.
MEANINGS = {
    'individual_positions': {
        'user_id': 'Person identifier (numeric in WRDS; kept as text).',
        'position_id': 'Position identifier (signed 64-bit in WRDS; kept as text).',
        'country': 'Country of the position; determines Hong Kong status in the panel.',
        'metro_area': 'Metropolitan area of the position (diagnostic only).',
        'city': 'City of the position (diagnostic only).',
        'startdate': 'Position start; month-level (day 1).',
        'enddate': 'Position end; month-level and treated as inclusive. NULL means no recorded end.',
        'rcid': 'Employer company identifier (Revelio RCID).',
        'ultimate_parent_rcid': 'Ultimate parent company identifier; used for same-employer status.',
        'role_k1500_v2': 'Occupation cluster (v2, k=1500); joins individual_role_lookup_v2.',
        'role_k17000_v3': 'Occupation cluster (v3, k=17000); joins individual_role_lookup_v3.',
        'seniority': 'Modelled seniority level (1-7).',
        'salary': 'Modelled salary for the position.',
        'remote_suitability': 'Job remote suitability; does not establish residence and is not used.',
        'weight': 'Revelio sampling weight; counts in this milestone are unweighted.',
        'position_number': "Order of the position within the person's profile.",
    },
    'individual_positions_raw': {
        'title_raw': 'Job title as written on the profile; input to title role rules.',
        'company_raw': 'Employer as written on the profile.',
        'location_raw': 'Location as written on the profile.',
    },
    'individual_user': {
        'user_country': 'Current profile country: one snapshot at updated_dt, no history.',
        'user_location': 'Current profile location text.',
        'updated_dt': 'Last profile refresh date; sets the 2026-08-31 cutoff and the refresh-cap sensitivity.',
        'prestige': 'Revelio prestige score.',
        'numconnections': 'Number of connections (network size).',
        'highest_degree': 'Highest degree attained (modelled).',
    },
    'individual_user_education': {
        'rsid': 'School identifier; joins school_mapping.',
        'education_number': "Order of the education record within the person's profile.",
        'startdate': 'Education start date.',
        'enddate': 'Education end date (not verified graduation).',
    },
    'people_cohort': {'user_id': 'Frozen Hong Kong-linked cohort: HK residence or any historical HK position.'},
}

LIMITATIONS = [
    'Person histories cover the Hong Kong-linked cohort only (HK profile residence or any historical HK position). '
    'They are not a global sample.',
    'Downloaded workforce geography (`workforce_dynamics_geo`, `regions`) covers Hong Kong only. These files cannot '
    'establish complete global multinational footprints or global headcounts.',
    'Profile location (`user_country`) is a single current snapshot at `updated_dt`; no historical profile-location '
    'snapshots exist. Using it for earlier quarters is backcasting, and is flagged as such.',
    'Position dates are month-level. Recorded end months are treated as inclusive; missing end dates are not '
    'known to be current and are carried to a common cutoff (with a refresh-cap sensitivity).',
    'No age or birth year, employment hours or type, position confidence, position refresh timestamps, or '
    'THE university rankings exist in the downloaded schemas. No proxies are substituted.',
    'Each work unit of the download used its own read-only snapshot; frozen IDs and matching counts do not '
    'guarantee identical source contents across units.',
]


def q(name):
    return '"' + name.replace('"', '""') + '"'


def table_names(ctx, manifest):
    on_disk = {p.name for p in ctx.source.iterdir() if p.is_dir() and any(p.rglob('*.parquet'))}
    return sorted(on_disk | set(manifest.get('tables', {})))


def schema(con, ctx, table):
    return [(r[0], r[1]) for r in con.execute(f'DESCRIBE SELECT * FROM {ctx.src(table)}').fetchall()]


def column_stats(con, ctx, table, columns):
    config = ctx.config['inventory']
    parts = ['count(*)']
    for name, kind in columns:
        parts.append(f'count({q(name)})')
        parts.append(f"count(*) FILTER (WHERE trim({q(name)}) = '')" if kind == 'VARCHAR'
                     and name not in config['free_text_columns'] else 'NULL')
        parts.append(f'count(DISTINCT {q(name)})' if name in config['distinct_columns'] else 'NULL')
        if NUMERIC.match(kind) or TEMPORAL.match(kind):
            parts += [f'min({q(name)})::VARCHAR', f'max({q(name)})::VARCHAR']
        else:
            parts += ['NULL', 'NULL']
    values = con.execute(f'SELECT {", ".join(parts)} FROM {ctx.src(table)}').fetchone()
    rows, out = values[0], []
    for i, (name, kind) in enumerate(columns):
        non_null, blank, distinct, low, high = values[1 + 5 * i: 6 + 5 * i]
        out.append({'table': table, 'column': name, 'type': kind, 'position': i + 1, 'rows': rows,
                    'non_null': non_null, 'nulls': rows - non_null,
                    'null_share': round((rows - non_null) / rows, 6) if rows else None,
                    'blank_strings': blank, 'distinct_values': distinct, 'min_value': low, 'max_value': high})
    return rows, out


def key_checks(con, ctx, table, columns, key):
    every = ', '.join(q(c) for c, _ in columns)
    if not key:
        rows, distinct = con.execute(f'SELECT count(*), count(DISTINCT hash({every})) FROM {ctx.src(table)}').fetchone()
        return {'declared_key': None, 'exact_duplicate_rows': rows - distinct, 'distinct_row_hashes': distinct,
                'duplicate_check': 'hash of all columns (64-bit)'}
    missing = [k for k in key if k not in dict(columns)]
    if missing:
        return {'declared_key': key, 'key_error': f'missing key columns {missing}'}
    keys = ', '.join(q(k) for k in key)
    null = ' OR '.join(f'{q(k)} IS NULL' for k in key)
    result = con.execute(f'''
        WITH t AS (SELECT {keys}, hash({every}) AS h FROM {ctx.src(table)}),
        g AS (SELECT {keys}, count(*) n, count(DISTINCT h) nh FROM t WHERE NOT ({null}) GROUP BY ALL HAVING count(*) > 1)
        SELECT (SELECT count(*) FROM t WHERE {null}), count(*), coalesce(sum(n), 0),
               count(*) FILTER (WHERE nh > 1), coalesce(sum(n) FILTER (WHERE nh > 1), 0),
               coalesce(sum(n - nh), 0)
        FROM g''').fetchone()
    return {'declared_key': key, 'null_key_rows': result[0], 'duplicate_key_groups': result[1],
            'rows_in_duplicate_keys': result[2], 'conflicting_keys': result[3],
            'rows_in_conflicting_keys': result[4], 'exact_duplicate_rows': result[5],
            'duplicate_check': 'declared key; row identity by 64-bit hash of all columns'}


def join_check(con, ctx, join, present):
    record = dict(join)
    declared = ctx.config['inventory']['keys'].get(join['right'])
    record['relationship'] = 'many-to-one' if declared and sorted(declared) == sorted(join['right_on']) else 'one-to-many'
    if join['left'] not in present or join['right'] not in present:
        record['status'] = 'table_missing'
        return record
    left_on, right_on = join['left_on'], join['right_on']
    lcols = ', '.join(f'{q(c)} AS k{i}' for i, c in enumerate(left_on))
    rcols = ', '.join(f'{q(c)} AS k{i}' for i, c in enumerate(right_on))
    rnull = ' OR '.join(f'{q(c)} IS NULL' for c in right_on)
    on = ' AND '.join(f'l.k{i} = r.k{i}' for i in range(len(left_on)))
    lnull = ' OR '.join(f'l.k{i} IS NULL' for i in range(len(left_on)))
    distinct_unmatched = (f'count(DISTINCT l.k0) FILTER (WHERE NOT ({lnull}) AND r.m IS NULL)'
                          if len(left_on) == 1 else 'NULL')
    values = con.execute(f'''
        WITH l AS (SELECT {lcols} FROM {ctx.src(join['left'])}),
        r AS (SELECT {', '.join(f'k{i}' for i in range(len(right_on)))}, count(*) m
              FROM (SELECT {rcols} FROM {ctx.src(join['right'])} WHERE NOT ({rnull})) GROUP BY ALL)
        SELECT count(*), count(*) FILTER (WHERE {lnull}), count(*) FILTER (WHERE r.m IS NOT NULL),
               count(*) FILTER (WHERE NOT ({lnull}) AND r.m IS NULL), {distinct_unmatched},
               coalesce(sum(r.m), 0), coalesce(max(r.m), 0),
               (SELECT count(*) FROM r WHERE m > 1)
        FROM l LEFT JOIN r ON {on}''').fetchone()
    names = ['left_rows', 'left_null_key_rows', 'matched_rows', 'unmatched_rows', 'unmatched_distinct_keys',
             'naive_inner_join_rows', 'max_right_matches_per_key', 'right_keys_with_duplicates']
    record.update(zip(names, values))
    keyed = record['left_rows'] - record['left_null_key_rows']
    record['match_share_of_keyed_rows'] = round(record['matched_rows'] / keyed, 6) if keyed else None
    record['row_multiplication_if_naive'] = record['naive_inner_join_rows'] - record['matched_rows']
    record['status'] = 'ok'
    return record


def absent_fields(ctx, schemas):
    out = []
    for item in ctx.config['absent_fields']:
        hits = []
        for table, columns in schemas.items():
            for name, _ in columns:
                tokens = name.lower().split('_')
                for term in item['search']:
                    parts = term.lower().split('_')
                    if any(tokens[i:i + len(parts)] == parts for i in range(len(tokens))):
                        hits.append(f'{table}.{name}')
        out.append({'field': item['field'], 'search_terms': item['search'], 'matching_columns': sorted(set(hits)),
                    'status': 'absent' if not hits else 'review: candidate columns found'})
    return out


def run(ctx):
    with StageRun(ctx, '00_inventory', writes=True) as stage:
        manifest_path = ctx.source / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        con = ctx.connect()
        tables, columns_out, schemas, problems = [], [], {}, []
        required = ctx.config['source'].get('require_manifest_status')
        if required and manifest.get('status') != required:
            problems.append(f'manifest status {manifest.get("status")!r} != {required!r}')
        for table in table_names(ctx, manifest):
            entry = manifest.get('tables', {}).get(table, {})
            files = ctx.files(table)
            record = {'table': table, 'source': entry.get('source'), 'manifest_status': entry.get('status'),
                      'manifest_rows': entry.get('rows'), 'expected_rows': entry.get('expected_rows'),
                      'manifest_parts': entry.get('parts'), 'parquet_files': len(files),
                      'manifest_bytes': entry.get('bytes'), 'file_bytes': sum(f.stat().st_size for f in files)}
            if not files:
                record.update(parquet_rows=0, n_columns=0)
                if entry.get('rows'):
                    problems.append(f'{table}: manifest rows {entry.get("rows")} but no Parquet parts')
                tables.append(record)
                continue
            print(f'[{now()}] inventory {table} ({len(files)} files)', flush=True)
            cols = schema(con, ctx, table)
            schemas[table] = cols
            signatures = con.execute(
                f"SELECT count(DISTINCT sig) FROM (SELECT file_name, string_agg(name || ':' || coalesce(type, '') "
                f"|| ':' || coalesce(logical_type::VARCHAR, ''), ',' ORDER BY name) sig FROM "
                f"parquet_schema({lit(str(ctx.table_dir(table)) + '/**/*.parquet')}) GROUP BY file_name)").fetchone()[0]
            rows, stats = column_stats(con, ctx, table, cols)
            columns_out += stats
            record.update(parquet_rows=rows, n_columns=len(cols), distinct_file_schemas=signatures)
            record.update(key_checks(con, ctx, table, cols, ctx.config['inventory']['keys'].get(table)))
            record['rows_reconcile'] = (entry.get('rows') == rows and entry.get('expected_rows', rows) == rows)
            record['parts_reconcile'] = entry.get('parts') == len(files) if entry else None
            record['bytes_reconcile'] = entry.get('bytes') == record['file_bytes'] if entry else None
            if entry and not record['rows_reconcile']:
                problems.append(f'{table}: Parquet rows {rows} != manifest rows {entry.get("rows")} '
                                f'/ expected {entry.get("expected_rows")}')
            if entry and entry.get('status') != 'complete':
                problems.append(f'{table}: manifest table status {entry.get("status")!r}')
            if not entry:
                problems.append(f'{table}: present on disk but absent from the manifest')
            if signatures != 1:
                problems.append(f'{table}: {signatures} distinct Parquet schemas across parts')
            tables.append(record)
        present = set(schemas)
        joins = []
        for join in ctx.config['inventory']['joins']:
            print(f'[{now()}] join {join["name"]}', flush=True)
            joins.append(join_check(con, ctx, join, present))
        absent = absent_fields(ctx, schemas)
        mapping = []
        for item in ctx.config['field_mapping']:
            cols = dict(schemas.get(item['table'], []))
            found = [c for c in item['columns'] if c in cols]
            nulls = {c['column']: c['null_share'] for c in columns_out
                     if c['table'] == item['table'] and c['column'] in found}
            lookups = [t for t in item.get('lookups', []) if t not in present]
            mapping.append({**item, 'present_columns': found,
                            'missing_columns': [c for c in item['columns'] if c not in cols],
                            'missing_lookups': lookups, 'null_share': nulls})
        ctx.diagnostics.mkdir(parents=True, exist_ok=True)
        write_csv(ctx.diagnostics / 'inventory_tables.csv', tables)
        write_csv(ctx.diagnostics / 'inventory_columns.csv', columns_out)
        write_csv(ctx.diagnostics / 'inventory_joins.csv', joins)
        summary = {
            'generated_utc': now(), 'source': str(ctx.source), 'manifest_status': manifest.get('status'),
            'manifest_country': manifest.get('country'), 'manifest_finished_utc': manifest.get('finished_at_utc'),
            'manifest_actual_bytes': manifest.get('actual_bytes'), 'unmatched_raw': manifest.get('unmatched_raw'),
            'snapshots': manifest.get('snapshots'), 'tables': tables, 'joins': joins,
            'absent_fields': absent, 'field_mapping': mapping, 'problems': problems,
            'file_bytes_total': sum(t['file_bytes'] for t in tables),
        }
        save_json(ctx.diagnostics / 'inventory.json', summary)
        ctx.docs.mkdir(parents=True, exist_ok=True)
        (ctx.docs / 'data_dictionary.md').write_text(dictionary(ctx, summary, columns_out, schemas))
        for name in ('inventory_tables.csv', 'inventory_columns.csv', 'inventory_joins.csv', 'inventory.json'):
            stage.output(name, ctx.diagnostics / name)
        stage.output('data_dictionary.md', ctx.docs / 'data_dictionary.md')
        stage.summary.update(tables=len(tables), problems=problems,
                             rows={t['table']: t.get('parquet_rows') for t in tables})
        if problems:
            raise RuntimeError('Inventory reconciliation failed: ' + '; '.join(problems))
        return summary


def write_csv(path, records):
    import csv
    keys = []
    for record in records:
        keys += [k for k in record if k not in keys]
    with open(path, 'w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for record in records:
            writer.writerow({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in record.items()})


def vendor_comments(path):
    """Column comments from the WRDS schema-discovery log (optional)."""
    if not path or not Path(path).exists():
        return {}
    types = (r'NUMERIC\(\d+, ?\d+\)|VARCHAR\(\d+\)|CHARACTER VARYING(\(\d+\))?|DOUBLE PRECISION|DATE|INTEGER|'
             r'BIGINT|SMALLINT|BOOLEAN|TEXT|REAL|TIMESTAMP( WITH(OUT)? TIME ZONE)?|TIME( WITH(OUT)? TIME ZONE)?')
    row = re.compile(rf'^\s*(\w+)\s+(True|False)\s+({types})\s*(.*)$')
    comments, table = {}, None
    for line in Path(path).read_text(errors='replace').splitlines():
        match = re.search(r'Describing table \d+/\d+: \w+\.(\w+)', line)
        if match:
            table = match.group(1)
            continue
        match = row.match(line)
        if table and match and match.group(1) != 'name':
            comments.setdefault(table, {})[match.group(1)] = match.groups()[-1].strip()
    return comments


def fmt(value):
    if value is None:
        return ''
    if isinstance(value, float):
        return f'{value:.4f}'
    if isinstance(value, int):
        return f'{value:,}'
    return str(value)


def dictionary(ctx, summary, columns, schemas):
    vendor = vendor_comments(ctx.column_comments)
    tables = {t['table']: t for t in summary['tables']}
    people = tables.get('people_cohort', {}).get('parquet_rows')
    positions = tables.get('individual_positions', {}).get('parquet_rows')
    lines = [
        '# Hong Kong Revelio extract: data dictionary', '',
        f'Generated {summary["generated_utc"]} by `hk_revelio` stage `00_inventory` from the downloaded '
        'Parquet schemas and contents. Regenerate it with the pipeline; do not edit by hand.', '',
        f'- Extract: `{summary["source"]}`',
        f'- Manifest status: `{summary["manifest_status"]}`, country `{summary["manifest_country"]}`, '
        f'finished {summary["manifest_finished_utc"]}',
        f'- Tables on disk: {len(tables)} ({fmt(summary["file_bytes_total"])} bytes of Parquet parts; '
        f'manifest actual bytes {fmt(summary["manifest_actual_bytes"])})',
        f'- Frozen cohort: {fmt(people)} people; positions: {fmt(positions)}',
        f'- Unmatched raw records reported by the download: `{json.dumps(summary["unmatched_raw"])}`',
        f'- Snapshot note: {summary["snapshots"]}',
        f'- Reconciliation problems: {"none" if not summary["problems"] else "; ".join(summary["problems"])}', '',
        '## Scope and limitations', '', *[f'- {item}' for item in LIMITATIONS], '',
        '## Analytical field mapping', '',
        '| Analytical field | Source table | Columns | Missing columns | Null share |', '|---|---|---|---|---|']
    for item in summary['field_mapping']:
        nulls = ', '.join(f'{c} {v:.1%}' for c, v in item['null_share'].items() if v is not None)
        lookups = f" (+ {', '.join(item.get('lookups', []))})" if item.get('lookups') else ''
        lines.append(f"| {item['field']} | `{item['table']}`{lookups} | {', '.join(item['present_columns'])} | "
                     f"{', '.join(item['missing_columns']) or 'none'} | {nulls} |")
    lines += ['', '## Fields not available', '',
              'Verified by searching every downloaded column name for the listed terms. No proxies are used.', '',
              '| Field | Search terms | Status | Matching columns |', '|---|---|---|---|']
    for item in summary['absent_fields']:
        lines.append(f"| {item['field']} | {', '.join(item['search_terms'])} | {item['status']} | "
                     f"{', '.join(item['matching_columns']) or 'none'} |")
    lines += ['', '## Joins and coverage', '',
              'Coverage of left-table rows with a non-null key. "Naive extra rows" counts how many rows an '
              'unguarded inner join would add through duplicate right-side keys. For many-to-one joins (right '
              'key = its declared key) extra rows would signal duplication; the pipeline deduplicates or '
              'quarantines such keys before joining. For one-to-many joins (for example people to their '
              'positions) extra rows are expected matches, not duplicates.', '',
              '| Join | Left -> right | Relationship | Keys | Left rows | Null keys | Matched | Unmatched | Match share | Naive extra rows |',
              '|---|---|---|---|---|---|---|---|---|---|']
    for join in summary['joins']:
        if join.get('status') != 'ok':
            lines.append(f"| {join['name']} | `{join['left']}` -> `{join['right']}` | {join['relationship']} | | | | | | {join['status']} | |")
            continue
        keys = ', '.join(f'{a}={b}' if a != b else a for a, b in zip(join['left_on'], join['right_on']))
        share = join['match_share_of_keyed_rows']
        lines.append(f"| {join['name']} | `{join['left']}` -> `{join['right']}` | {join['relationship']} | {keys} | {fmt(join['left_rows'])} | "
                     f"{fmt(join['left_null_key_rows'])} | {fmt(join['matched_rows'])} | {fmt(join['unmatched_rows'])} | "
                     f"{'' if share is None else f'{share:.4%}'} | {fmt(join['row_multiplication_if_naive'])} |")
    lines += ['', '## Tables', '']
    by_table = {}
    for column in columns:
        by_table.setdefault(column['table'], []).append(column)
    for name, table in tables.items():
        lines += [f'### `{name}`', '',
                  f"- WRDS source: `{table.get('source')}`; manifest status `{table.get('manifest_status')}`",
                  f"- Rows: {fmt(table.get('parquet_rows'))} in Parquet; manifest {fmt(table.get('manifest_rows'))}, "
                  f"expected {fmt(table.get('expected_rows'))}; reconcile: {table.get('rows_reconcile')}",
                  f"- Parts: {fmt(table.get('parquet_files'))} files, {fmt(table.get('file_bytes'))} bytes; "
                  f"distinct schemas across parts: {table.get('distinct_file_schemas')}"]
        if table.get('declared_key'):
            lines.append(f"- Declared key `{', '.join(table['declared_key'])}`: null-key rows "
                         f"{fmt(table.get('null_key_rows'))}, duplicate keys {fmt(table.get('duplicate_key_groups'))}, "
                         f"conflicting keys {fmt(table.get('conflicting_keys'))}, exact duplicate rows "
                         f"{fmt(table.get('exact_duplicate_rows'))}")
        elif table.get('n_columns'):
            lines.append(f"- No declared key; exact duplicate rows {fmt(table.get('exact_duplicate_rows'))} "
                         '(hash of all columns)')
        lines += ['', '| Column | Type | Null share | Blank | Distinct | Min | Max | Meaning |',
                  '|---|---|---|---|---|---|---|---|']
        for column in by_table.get(name, []):
            meaning = MEANINGS.get(name, {}).get(column['column']) or vendor.get(name, {}).get(column['column'], '')
            share = column['null_share']
            note = ' (all null: unavailable)' if column['non_null'] == 0 and column['rows'] else ''
            lines.append(f"| `{column['column']}` | {column['type']} | {'' if share is None else f'{share:.2%}'}{note} | "
                         f"{fmt(column['blank_strings'])} | {fmt(column['distinct_values'])} | "
                         f"{fmt(column['min_value'])} | {fmt(column['max_value'])} | {meaning.replace('|', '/')} |")
        lines.append('')
    return '\n'.join(lines) + '\n'
