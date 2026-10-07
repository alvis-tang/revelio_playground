"""Run hk_revelio stages 00_inventory through 05_replication.

Example (KLC):
  python hk_revelio/run.py --stages all --source DATA_DIR --work-root WORK_DIR \
      --python /path/to/env/bin/python
"""
import argparse
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def ensure_dependencies(argv):
    """Re-execute under --python (or HK_REVELIO_PYTHON) when DuckDB/PyYAML are missing."""
    try:
        import duckdb  # noqa: F401
        import yaml  # noqa: F401
    except ImportError:
        python = os.environ.get('HK_REVELIO_PYTHON')
        if '--python' in argv:
            python = argv[argv.index('--python') + 1]
        if python and Path(python).absolute() != Path(sys.executable).absolute():
            os.execv(python, [python, str(HERE / 'run.py'), *argv])
        raise SystemExit('DuckDB and PyYAML are required: install hk_revelio/requirements.txt or pass --python PATH.')


def select(spec, names):
    if spec == 'all':
        return list(names)
    chosen = []
    for part in spec.split(','):
        bounds = part.split('-')
        index = [next(i for i, n in enumerate(names) if n.startswith(b.zfill(2)) or n == b) for b in bounds]
        chosen += names[index[0]:index[-1] + 1]
    return list(dict.fromkeys(chosen))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ensure_dependencies(argv)
    from hkrev import clean, common, diagnostics, inventory, migration, panel, replication
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--stages', default='all', help="'all', or e.g. '00', '01-03', '04,05'")
    parser.add_argument('--source', help='Completed extract directory (default: config source.extract_dir)')
    parser.add_argument('--work-root', default=str(HERE), help='Directory for data/, output/, docs/, run/, tmp/')
    parser.add_argument('--config', default=str(common.CONFIG))
    parser.add_argument('--taxonomy', default=str(common.TAXONOMY))
    parser.add_argument('--threads', type=int)
    parser.add_argument('--memory-limit')
    parser.add_argument('--buckets', type=int, help='User hash buckets (default: config storage.user_buckets)')
    parser.add_argument('--column-comments', help='Optional WRDS schema log with column comments (data dictionary)')
    parser.add_argument('--python', help='Interpreter with DuckDB/PyYAML for re-execution')
    ns = parser.parse_args(argv)
    ctx = common.Context(ns.source, ns.work_root, ns.config, ns.taxonomy, ns.threads, ns.memory_limit,
                         ns.buckets, ns.column_comments)
    modules = dict(zip(common.STAGES, [inventory, clean, panel, diagnostics, migration, replication]))
    stages = select(ns.stages, common.STAGES)
    print(f'hk_revelio: stages {stages}; source {ctx.source}; work root {ctx.root}', flush=True)
    for stage in stages:
        modules[stage].run(ctx)
    return 0


if __name__ == '__main__':
    sys.exit(main())
