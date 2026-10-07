# hk_revelio: Hong Kong measurement pipeline (milestone 1)

Inventory, quarterly panel, migration classification, and an approximate
replication of Kwan, Tang, and Wong (2024). The pipeline runs on the completed
KLC extract. Rules and limitations are in [docs/methodology.md](docs/methodology.md).
Settings are in [config/analysis.yml](config/analysis.yml) and
[config/title_taxonomy.yml](config/title_taxonomy.yml).

This milestone stops after measurement. It contains no regressions, figures,
policy estimates, retention, or multinational decomposition.

## Layout

```
run.py                 # orchestrator: --stages all | 00 | 01-03 | 04,05
stages/00_inventory.py ... 05_replication.py   # one runnable script per stage
hkrev/                 # shared utilities and stage implementations
config/                # analysis.yml, title_taxonomy.yml
docs/methodology.md    # measurement rules (data_dictionary.md is generated)
tests/                 # synthetic end-to-end and state-machine tests
```

Each run writes under its `--work-root` (default: this directory):

- `docs/data_dictionary.md`
- `output/diagnostics/`
- `output/tables/`
- `data/derived/`
- `run/` (fingerprints)
- `tmp/` (spill)

All of these are ignored by Git.

## Run on KLC

DuckDB and PyYAML live in a dedicated environment, so the toolkit's shared
`.venv` is unchanged. Create it once in a KLC terminal:

```sh
cd /kellogg/proj/cxv7409/revelio_playground
.venv/bin/python -m venv logs/hk_revelio_env
logs/hk_revelio_env/bin/python -m pip install -r hk_revelio/requirements.txt
```

Launch from the Mac. `run.py` re-executes itself under `--python` when the
toolkit interpreter lacks DuckDB. Use a new work root for each full run:

```sh
./klc run python hk_revelio/run.py --stages all \
  --source /gpfs/kellogg/proj/cxv7409/revelio_playground/data/hong_kong_20261004T140024976790Z \
  --work-root /gpfs/kellogg/proj/cxv7409/revelio_playground/results/hk_revelio_RUN \
  --python /gpfs/kellogg/proj/cxv7409/revelio_playground/logs/hk_revelio_env/bin/python \
  --column-comments /gpfs/kellogg/proj/cxv7409/revelio_playground/revelio_tables.log
```

`--column-comments` is optional. It adds WRDS column comments to the generated
data dictionary. It expects a copy of the local `revelio_tables.log` on KLC;
that log is ignored by Git, so `git pull` does not bring it.

Defaults:

- one thread and a 6 GB DuckDB memory limit (`--threads`, `--memory-limit`);
- 32 user hash buckets (`--buckets`);
- a refusal to write when fewer than 25 GB are free.

Stages can be rerun individually. A stage refuses upstream outputs made with a
different configuration, extract, or bucket count. Raw files are verified
unchanged before and after every stage.

## Tests

```sh
python -m unittest discover -s hk_revelio/tests -v
```

Requires `requirements.txt` (DuckDB, PyArrow, PyYAML). Tests are skipped without
them. The repository's other tests run separately with
`python3 -m unittest discover -s tests -v`.
