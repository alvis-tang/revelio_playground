"""Sample English Hong Kong postings from the completed KLC Parquet extract.

Run with the existing .venv-llm environment (PyArrow and Lingua 2.1.1).
Source files are read only. Each output JSON retains every raw column and nests
the complete structured record under ``posting``.
"""
import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import revelio_multilingual as multilingual

DEFAULT_SOURCE = Path('/kellogg/proj/cxv7409/revelio_playground/data/'
                      'hong_kong_20261004T140024976790Z')
RAW_FIELDS = {'job_id', 'title_raw', 'jobtitle_translated', 'location_raw', 'description'}
ALGORITHM = 'Sparse Fisher-Yates permutation of sorted raw-part row ordinals, v1'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f'Unsupported JSON value: {type(value).__name__}')


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                    indent=2, default=json_default) + '\n', encoding='utf-8')
    temporary.replace(path)


def row_order(size, seed):
    """Yield a uniform permutation lazily, with memory proportional to draws."""
    rng, swaps = random.Random(seed), {}
    for remaining in range(size, 0, -1):
        index = rng.randrange(remaining)
        chosen = swaps.get(index, index)
        last = remaining - 1
        replacement = swaps.pop(last, last)
        if index != last:
            swaps[index] = replacement
        yield chosen


def catalog_raw(source, expected_rows):
    import pyarrow as pa
    import pyarrow.parquet as pq

    parts, ends, total, names = [], [], 0, None
    for path in sorted((source / 'postings_cosmos_raw').rglob('*.parquet')):
        parquet = pq.ParquetFile(path)
        schema = parquet.schema_arrow
        if names is None:
            names = schema.names
            if not RAW_FIELDS.issubset(names) or 'posting' in names:
                raise ValueError('Raw schema lacks required fields or conflicts with posting.')
            first_schema = schema.remove_metadata()
        if not schema.remove_metadata().equals(first_schema):
            raise ValueError(f'Inconsistent raw schema: {path}')
        if not pa.types.is_string(schema.field('job_id').type):
            raise ValueError('Source job IDs must already be lossless strings.')
        rows = parquet.metadata.num_rows
        parts.append({'part': str(path.relative_to(source)), 'rows': rows})
        total += rows
        ends.append(total)
    if not parts or total != expected_rows:
        raise ValueError(f'Raw row count {total} differs from manifest {expected_rows}.')
    return parts, ends, names


def positions_for(ordinals, parts, ends):
    result = []
    for ordinal in ordinals:
        index = bisect_right(ends, ordinal)
        start = ends[index - 1] if index else 0
        result.append({'ordinal': ordinal, 'part': parts[index]['part'], 'row': ordinal - start})
    return result


def read_positions(source, positions):
    """Read requested rows by row group, returning their original requested order."""
    import pyarrow.parquet as pq

    grouped, result = defaultdict(list), [None] * len(positions)
    for index, position in enumerate(positions):
        grouped[position['part']].append((index, position['row']))
    for part, requests in grouped.items():
        path = (source / part).resolve()
        if not path.is_relative_to(source.resolve() / 'postings_cosmos_raw'):
            raise ValueError('Raw part escapes the source table directory.')
        parquet = pq.ParquetFile(path)
        ends, total = [], 0
        for group in range(parquet.num_row_groups):
            total += parquet.metadata.row_group(group).num_rows
            ends.append(total)
        by_group = defaultdict(list)
        for index, row in requests:
            if not 0 <= row < total:
                raise ValueError(f'Raw row out of range: {part}:{row}')
            group = bisect_right(ends, row)
            start = ends[group - 1] if group else 0
            by_group[group].append((index, row - start))
        for group, members in by_group.items():
            table = parquet.read_row_group(group, use_threads=False)
            for index, row in members:
                result[index] = table.slice(row, 1).to_pylist()[0]
    return result


def english_check(text, language_detector):
    if not isinstance(text, str) or not text.strip():
        return {'accepted': False, 'reason': 'empty_description'}
    # Script maps are unnecessary: every substantial non-English passage fails.
    report = multilingual.classify(text, language_detector, (set(), set()))
    other = any(span['language'] != 'English' for span in report['passages'])
    accepted = report['group'] == 'English' and not other
    return {**report, 'accepted': accepted,
            'reason': 'english' if accepted else 'non_english_mixed_or_uncertain'}


def lookup_postings(source, ids):
    import pyarrow as pa
    import pyarrow.dataset as ds

    files = sorted((source / 'postings_cosmos').rglob('*.parquet'))
    if not files:
        raise ValueError('No structured posting parts found.')
    dataset = ds.dataset([str(path) for path in files], format='parquet')
    for name in ('job_id', 'rcid', 'ultimate_parent_rcid'):
        if name in dataset.schema.names and not pa.types.is_string(dataset.schema.field(name).type):
            raise ValueError(f'Source {name} must already be a string.')
    found = {}
    scanner = dataset.scanner(filter=ds.field('job_id').isin(ids), batch_size=1024,
                              use_threads=False)
    for batch in scanner.to_batches():
        for row in batch.to_pylist():
            job_id = row['job_id']
            if job_id in found:
                raise ValueError(f'Duplicate structured job ID: {job_id}')
            if row['country'] != 'Hong Kong':
                raise ValueError(f'Non-Hong Kong structured record: {job_id}')
            found[job_id] = row
    if set(found) != set(ids):
        raise ValueError('Selected raw records lack matching structured postings.')
    return found, dataset.schema.names


def save_records(output, records, postings, selected):
    for raw, entry in zip(records, selected):
        job_id = raw['job_id']
        if not isinstance(job_id, str) or not re.fullmatch(r'-?[0-9]+', job_id):
            raise ValueError('Job ID is not a safe string filename.')
        filename = job_id + '.json'
        path = output / filename
        write_json(path, {**raw, 'posting': postings[job_id]})
        restored = json.loads(path.read_text(encoding='utf-8'))
        if {key: restored[key] for key in raw} != raw:
            raise ValueError(f'Raw JSON round trip changed source fields: {job_id}')
        entry.update(filename=filename, sha256=digest(path))


def verify_export(output, source=None, require_complete=True):
    output = Path(output)
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    if require_complete and manifest['status'] != 'complete':
        raise ValueError('Export manifest is incomplete.')
    selected = manifest['selected']
    ids = [entry['job_id'] for entry in selected]
    if len(ids) != manifest['requested_count'] or len(set(ids)) != len(ids):
        raise ValueError('Export count or unique job IDs failed validation.')
    expected_files = {entry['filename'] for entry in selected} | {'manifest.json'}
    if {path.name for path in output.iterdir()} != expected_files:
        raise ValueError('Export contains missing or unexpected files.')
    originals = None
    if source is not None:
        source = Path(source)
        if digest(source / 'manifest.json') != manifest['source_manifest_sha256']:
            raise ValueError('Source manifest has changed.')
        originals = read_positions(source, [entry['raw_position'] for entry in selected])
    for index, entry in enumerate(selected):
        if entry['filename'] != entry['job_id'] + '.json' or not re.fullmatch(r'-?[0-9]+', entry['job_id']):
            raise ValueError('Invalid export filename.')
        path = output / entry['filename']
        if digest(path) != entry['sha256']:
            raise ValueError(f'Checksum mismatch: {path.name}')
        record = json.loads(path.read_text(encoding='utf-8'))
        raw = {key: value for key, value in record.items() if key != 'posting'}
        if set(raw) != set(manifest['raw_columns']) or raw['job_id'] != entry['job_id']:
            raise ValueError('Raw schema or ID mismatch.')
        if originals is not None and raw != originals[index]:
            raise ValueError(f'Raw export differs from source: {entry["job_id"]}')
        posting = record['posting']
        if (posting['job_id'] != entry['job_id'] or posting['country'] != 'Hong Kong'
                or set(posting) != set(manifest['posting_columns'])):
            raise ValueError('Structured schema, geography, or ID mismatch.')
        language = entry['language']
        if (not language['accepted'] or language['group'] != 'English'
                or any(span['language'] != 'English' for span in language['passages'])
                or not language['letters']
                or language['language_letters'].get('English', 0) / language['letters']
                   < manifest['language_policy']['minimum_group_share']):
            raise ValueError('English language audit failed.')
    return {'rows': len(ids), 'checksums_verified': True,
            'raw_fields_verified_against_source': originals is not None}


def sample(source, output, count=300, seed=None, batch_size=128):
    if count < 1 or batch_size < 1:
        raise ValueError('Count and batch size must be positive.')
    source, output = Path(source), Path(output)
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError('Output must be outside the read-only source extract.')
    source_hash = digest(source / 'manifest.json')
    snapshot = json.loads((source / 'manifest.json').read_text())
    if (snapshot.get('status') != 'complete' or snapshot.get('country') != 'Hong Kong'
            or any(snapshot['tables'][name].get('status') != 'complete'
                   for name in ('postings_cosmos', 'postings_cosmos_raw'))):
        raise ValueError('A completed Hong Kong extract is required.')
    expected_rows = snapshot['tables']['postings_cosmos_raw']['rows']
    if count > expected_rows:
        raise ValueError('Requested count exceeds the source population.')
    print('Indexing raw Parquet parts...', flush=True)
    parts, ends, columns = catalog_raw(source, expected_rows)
    language_detector = multilingual.detector()
    seed = secrets.randbits(64) if seed is None else seed
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        'status': 'incomplete', 'requested_count': count, 'seed': seed,
        'sampling_algorithm': ALGORITHM,
        'sampling': 'Uniform raw-row candidates without replacement; accept the first requested '
                    'number of unique, confidently English descriptions. No date or source filter.',
        'source': str(source.resolve()), 'source_manifest_sha256': source_hash,
        'source_finished_at_utc': snapshot.get('finished_at_utc'),
        'source_tables': {name: snapshot['tables'][name]['source']
                          for name in ('postings_cosmos', 'postings_cosmos_raw')},
        'source_population_rows': expected_rows, 'raw_part_count': len(parts),
        'raw_part_inventory_sha256': hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest(),
        'raw_columns': columns, 'posting_columns': [],
        'language_policy': {**multilingual.POLICY, 'accept_group': 'English',
                           'reject_any_confident_substantial_non_english_passage': True},
        'environment': {'python': platform.python_version(),
                        'pyarrow': importlib.metadata.version('pyarrow'),
                        'lingua-language-detector': importlib.metadata.version('lingua-language-detector')},
        'code_sha256': {Path(__file__).name: digest(__file__),
                        Path(multilingual.__file__).name: digest(multilingual.__file__)},
        'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'batch_size': batch_size, 'candidates_evaluated': 0,
        'rejection_counts': {}, 'selected': [],
    }
    manifest_path = output / 'manifest.json'
    write_json(manifest_path, manifest)
    selected, records, seen_ids, rejected = manifest['selected'], [], set(), Counter()
    order = iter(row_order(expected_rows, seed))
    exhausted = False
    while len(records) < count and not exhausted:
        ordinals = []
        for _ in range(batch_size):
            ordinal = next(order, None)
            if ordinal is None:
                exhausted = True
                break
            ordinals.append(ordinal)
        positions = positions_for(ordinals, parts, ends)
        for raw, position in zip(read_positions(source, positions), positions):
            manifest['candidates_evaluated'] += 1
            job_id = raw['job_id']
            if not isinstance(job_id, str) or not re.fullmatch(r'-?[0-9]+', job_id):
                raise ValueError('Source contains an invalid job ID.')
            if job_id in seen_ids:
                raise ValueError(f'Duplicate raw source job ID encountered: {job_id}')
            seen_ids.add(job_id)
            language = english_check(raw['description'], language_detector)
            if language['accepted']:
                records.append(raw)
                selected.append({'job_id': job_id, 'raw_position': position,
                                 'candidate_index': manifest['candidates_evaluated'], 'language': language})
            else:
                rejected[language['reason']] += 1
            if manifest['candidates_evaluated'] % 25 == 0:
                print(f"Candidates {manifest['candidates_evaluated']}; English accepted {len(records)}/{count}",
                      flush=True)
            if len(records) == count:
                break
        manifest['rejection_counts'] = dict(rejected)
        write_json(manifest_path, manifest)
    if len(records) != count:
        raise ValueError(f'Only {len(records)} English descriptions found; export is incomplete.')
    print('Joining complete structured posting records...', flush=True)
    postings, manifest['posting_columns'] = lookup_postings(source, [row['job_id'] for row in records])
    save_records(output, records, postings, selected)
    write_json(manifest_path, manifest)
    print('Comparing all raw fields against source Parquet...', flush=True)
    manifest['validation'] = verify_export(output, source, require_complete=False)
    manifest['status'] = 'complete'
    manifest['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    write_json(manifest_path, manifest)
    print(json.dumps({'output': str(output), 'seed': seed, **manifest['validation']}), flush=True)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    extract = commands.add_parser('sample')
    extract.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    extract.add_argument('--output', type=Path)
    extract.add_argument('--count', type=int, default=300)
    extract.add_argument('--seed', type=int)
    extract.add_argument('--batch-size', type=int, default=128)
    verify = commands.add_parser('verify')
    verify.add_argument('directory', type=Path)
    verify.add_argument('--source', type=Path, help='Also compare all raw values against source Parquet')
    args = parser.parse_args(argv)
    if args.command == 'verify':
        print(json.dumps(verify_export(args.directory, args.source)))
    else:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        output = args.output or Path(os.environ.get('KLC_ROOT', ROOT)) / 'data' / (
            f'hk_english_postings_{args.count}_{stamp}')
        sample(args.source, output, args.count, args.seed, args.batch_size)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, TypeError) as exc:
        print(f'Hong Kong English sample: {exc}', file=sys.stderr)
        sys.exit(1)
