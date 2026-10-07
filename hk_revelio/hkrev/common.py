"""Shared configuration, DuckDB, fingerprint, and run-metadata utilities."""
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

PACKAGE = Path(__file__).resolve().parents[1]
CONFIG = PACKAGE / 'config/analysis.yml'
TAXONOMY = PACKAGE / 'config/title_taxonomy.yml'
STAGES = ['00_inventory', '01_clean', '02_panel', '03_diagnostics', '04_migration', '05_replication']
SPECS = {'position_with_profile_fallback': 'fallback', 'position_only': 'position_only'}


def now():
    return datetime.now(timezone.utc).isoformat()


def qidx(label):
    """'2019Q4' -> quarter index (year * 4 + quarter - 1)."""
    match = re.fullmatch(r'(\d{4})Q([1-4])', str(label))
    if not match:
        raise ValueError(f'Invalid quarter label: {label}')
    return int(match.group(1)) * 4 + int(match.group(2)) - 1


def qlabel(index):
    return f'{index // 4}Q{index % 4 + 1}'


def midx(value):
    """Month index (year * 12 + month - 1); days are ignored."""
    if isinstance(value, str):
        value = date.fromisoformat(value)
    return value.year * 12 + value.month - 1


def lit(value):
    """SQL string literal."""
    return "'" + str(value).replace("'", "''") + "'"


def sha256_file(path, chunk=1 << 22):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        while block := stream.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, default=str) + '\n')
    temporary.replace(path)


class Context:
    """Paths, settings, and DuckDB connections for one work root."""

    def __init__(self, source=None, work_root=None, config=CONFIG, taxonomy=TAXONOMY,
                 threads=None, memory_limit=None, buckets=None, column_comments=None):
        import yaml
        self.config_path, self.taxonomy_path = Path(config), Path(taxonomy)
        self.config = yaml.safe_load(self.config_path.read_text())
        self.taxonomy = yaml.safe_load(self.taxonomy_path.read_text())
        self.source = Path(source or self.config['source']['extract_dir']).resolve()
        self.root = Path(work_root or PACKAGE).resolve()
        self.derived = self.root / 'data/derived'
        self.diagnostics = self.root / 'output/diagnostics'
        self.tables = self.root / 'output/tables'
        self.docs = self.root / 'docs'
        self.run_dir = self.root / 'run'
        self.tmp = self.root / 'tmp'
        settings = self.config['duckdb']
        self.threads = int(threads or settings['threads'])
        self.memory_limit = memory_limit or settings['memory_limit']
        self.buckets = int(buckets or self.config['storage']['user_buckets'])
        self.column_comments = Path(column_comments) if column_comments else None
        dates = self.config['dates']
        self.cutoff = dates['common_cutoff']
        self.cutoff_midx = midx(self.cutoff)
        self.min_start = dates['min_valid_start']
        self.panel_start_q = qidx(dates['panel_start_quarter'])
        self.last_q = qidx(dates['last_complete_quarter'])
        self.partial_q = qidx(dates['partial_quarter'])
        if self.partial_q != self.cutoff_midx // 3 or self.last_q != self.partial_q - 1:
            raise ValueError('partial_quarter must contain the cutoff and follow last_complete_quarter.')
        self.end_rules = list(dates['end_rules'])
        self.primary_rule = next(k for k, v in dates['end_rules'].items() if v.get('primary'))
        self.hk = self.config['location']['hong_kong_country']
        self.ks = [int(k) for k in self.config['migration']['persistence_quarters']]

    # Source tables -----------------------------------------------------------
    def table_dir(self, logical_or_name):
        name = self.config['source']['tables'].get(logical_or_name, logical_or_name)
        return self.source / name

    def files(self, logical_or_name):
        return sorted(self.table_dir(logical_or_name).rglob('*.parquet'))

    def src(self, logical_or_name):
        """read_parquet expression for a source table (all parts, recursively)."""
        folder = self.table_dir(logical_or_name)
        if not self.files(logical_or_name):
            raise FileNotFoundError(f'No Parquet parts under {folder}')
        return f"read_parquet({lit(str(folder) + '/**/*.parquet')})"

    def connect(self, database=None):
        import duckdb
        spill = self.config['duckdb'].get('temp_directory') or str(self.tmp / 'duckdb')
        Path(spill).mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(str(database) if database else ':memory:')
        con.execute(f'SET threads={self.threads}')
        con.execute(f'SET memory_limit={lit(self.memory_limit)}')
        con.execute(f'SET temp_directory={lit(spill)}')
        con.execute(f"SET max_temp_directory_size={lit(self.config['duckdb']['max_temp_directory_size'])}")
        con.execute(f"SET preserve_insertion_order={str(bool(self.config['duckdb']['preserve_insertion_order'])).lower()}")
        return con

    def stage_db(self, stage):
        """Fresh disk-backed DuckDB database for a stage's intermediate tables."""
        path = self.tmp / f'{stage}.duckdb'
        for old in (path, Path(str(path) + '.wal')):
            old.unlink(missing_ok=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        return self.connect(path), path

    def copy(self, con, query, path, fmt='parquet'):
        """Write a query to Parquet (zstd) or CSV atomically; returns row count."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.tmp')
        temporary.unlink(missing_ok=True)
        if fmt == 'parquet':
            options = f"FORMAT parquet, COMPRESSION {self.config['storage']['parquet_compression']}"
        else:
            options = 'FORMAT csv, HEADER true'
        con.execute(f'COPY ({query}) TO {lit(temporary)} ({options})')
        temporary.replace(path)
        if fmt == 'parquet':
            return con.execute(f'SELECT count(*) FROM read_parquet({lit(path)})').fetchone()[0]
        return con.execute(f'SELECT count(*) FROM read_csv({lit(path)}, header=true, all_varchar=true)').fetchone()[0]

    # Fingerprints --------------------------------------------------------------
    def raw_listing(self):
        lines = []
        for path in sorted(p for p in self.source.rglob('*') if p.is_file()):
            stat = path.stat()
            lines.append(f'{path.relative_to(self.source)}\t{stat.st_size}\t{stat.st_mtime_ns}')
        return lines

    def raw_content_hashes(self):
        return {str(p.relative_to(self.source)): sha256_file(p)
                for p in sorted(p for p in self.source.rglob('*') if p.is_file())}

    def code_fingerprint(self):
        files = sorted([*PACKAGE.glob('hkrev/*.py'), PACKAGE / 'run.py', *PACKAGE.glob('stages/*.py')])
        digest = hashlib.sha256()
        for path in files:
            digest.update(str(path.relative_to(PACKAGE)).encode() + b'\0' + path.read_bytes() + b'\0')
        # Only report a commit when these files are tracked (isolated deployments are not).
        tracked = subprocess.run(['git', '-C', str(PACKAGE), 'ls-files', '--error-unmatch', 'run.py'],
                                 capture_output=True, text=True).returncode == 0
        commit = subprocess.run(['git', '-C', str(PACKAGE), 'rev-parse', 'HEAD'], capture_output=True, text=True)
        dirty = subprocess.run(['git', '-C', str(PACKAGE), 'status', '--porcelain', '--', '.'],
                               capture_output=True, text=True)
        return {'code_sha256': digest.hexdigest(),
                'git_commit': commit.stdout.strip() if tracked else None,
                'git_dirty': bool(dirty.stdout.strip()) if tracked else None}

    def fingerprint(self):
        manifest = self.source / 'manifest.json'
        return {
            'config_sha256': sha256_file(self.config_path),
            'taxonomy_sha256': sha256_file(self.taxonomy_path),
            'input_manifest_sha256': sha256_file(manifest) if manifest.exists() else None,
            'input_listing_sha256': sha256_text('\n'.join(self.raw_listing())),
            'source': str(self.source),
            'settings': {'threads': self.threads, 'memory_limit': self.memory_limit,
                         'user_buckets': self.buckets},
        }

    def free_bytes(self):
        self.root.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(self.root).free

    def require_space(self):
        need = float(self.config['storage']['min_free_gb']) * 1e9
        if self.free_bytes() < need:
            raise RuntimeError(f'Work-root file system has {self.free_bytes() / 1e9:.1f} GB free; '
                               f'{need / 1e9:.0f} GB required (storage.min_free_gb).')


class StageRun:
    """Records stage metadata, checks upstream consistency and raw immutability."""

    def __init__(self, ctx, stage, requires=(), writes=True):
        self.ctx, self.stage, self.requires, self.writes = ctx, stage, requires, writes
        self.path = ctx.run_dir / f'{stage}.json'
        self.outputs, self.summary = {}, {}

    def __enter__(self):
        ctx = self.ctx
        self.fingerprint = ctx.fingerprint()
        baseline = ctx.run_dir / 'raw_baseline.json'
        if self.stage == STAGES[0]:
            record = {'created_utc': now(), 'listing': ctx.raw_listing(),
                      'listing_sha256': self.fingerprint['input_listing_sha256']}
            if ctx.config['storage'].get('content_hash_raw_files'):
                record['content_sha256'] = ctx.raw_content_hashes()
            save_json(baseline, record)
        elif not baseline.exists():
            raise RuntimeError('Run stage 00_inventory first: no raw-file baseline in this work root.')
        self.baseline = json.loads(baseline.read_text())
        self.check_listing('start')
        for upstream in self.requires:
            path = ctx.run_dir / f'{upstream}.json'
            if not path.exists():
                raise RuntimeError(f'{self.stage} requires completed stage {upstream}.')
            record = json.loads(path.read_text())
            if record.get('status') != 'complete':
                raise RuntimeError(f'Upstream stage {upstream} is {record.get("status")}.')
            for key in ('config_sha256', 'taxonomy_sha256', 'input_manifest_sha256', 'input_listing_sha256'):
                if record['fingerprint'].get(key) != self.fingerprint[key]:
                    raise RuntimeError(f'{upstream} was run with a different {key}; rerun from it.')
            if record['fingerprint']['settings'].get('user_buckets') != self.ctx.buckets:
                raise RuntimeError(f'{upstream} used a different user_buckets setting.')
        if self.writes:
            ctx.require_space()
        self.record = {'stage': self.stage, 'status': 'running', 'started_utc': now(),
                       'fingerprint': self.fingerprint, 'code': ctx.code_fingerprint(),
                       'requires': {u: json.loads((ctx.run_dir / f'{u}.json').read_text())['code']
                                    for u in self.requires}}
        import duckdb
        self.record['duckdb_version'] = duckdb.__version__
        save_json(self.path, self.record)
        print(f'[{now()}] {self.stage}: started', flush=True)
        return self

    def check_listing(self, when):
        current = self.ctx.raw_listing()
        if current != self.baseline['listing']:
            changed = sorted(set(current) ^ set(self.baseline['listing']))[:5]
            raise RuntimeError(f'Raw extract changed ({when} of {self.stage}): {changed}')

    def output(self, name, path, rows=None):
        path = Path(path)
        size = sum(p.stat().st_size for p in path.rglob('*') if p.is_file()) if path.is_dir() else path.stat().st_size
        self.outputs[name] = {'path': str(path.relative_to(self.ctx.root)), 'rows': rows, 'bytes': size}

    def __exit__(self, kind, value, trace):
        error = None if kind is None else f'{kind.__name__}: {value}'
        late = None
        try:
            self.check_listing('end')
            if kind is None and self.stage == STAGES[-1] and 'content_sha256' in self.baseline:
                if self.ctx.raw_content_hashes() != self.baseline['content_sha256']:
                    raise RuntimeError('Raw extract content hashes changed during the run.')
                self.summary['raw_content_hashes_unchanged'] = True
            self.summary['raw_listing_unchanged'] = True
        except RuntimeError as exc:
            late = exc
            error = error or f'RuntimeError: {exc}'
        self.record.update(status='complete' if error is None else 'failed', finished_utc=now(),
                           outputs=self.outputs, summary=self.summary, error=error)
        save_json(self.path, self.record)
        with open(self.ctx.run_dir / 'history.jsonl', 'a') as stream:
            keys = ('stage', 'status', 'started_utc', 'finished_utc', 'error')
            stream.write(json.dumps({k: self.record[k] for k in keys}) + '\n')
        print(f'[{now()}] {self.stage}: {self.record["status"]}', flush=True)
        if error is None:
            for path in self.ctx.tmp.glob(f'{self.stage}.duckdb*'):
                path.unlink()
        if kind is None and late is not None:
            raise late
        return False
