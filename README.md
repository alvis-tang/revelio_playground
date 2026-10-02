# Revelio Labs on KLC

Edit code from your Mac in VS Code; run Python and Stata on Kellogg Linux Cluster.
WRDS remains the PostgreSQL data source. Large extracts stay on KLC project storage.

For a detailed walkthrough explaining the extension installation, where to run
commands, and what to do in future sessions, see [KLC_WORKFLOW.md](KLC_WORKFLOW.md).

## First-time setup

1. Confirm your KLC login and an existing, writable project directory, such as
   `/kellogg/proj/<netid>`. Ask Kellogg Research Support for storage if needed.
   WRDS must separately grant your account Revelio access. Use Northwestern VPN
   if your network requires it.
2. Run `./klc setup` from this repository. Enter your NetID, host, project directory,
   and WRDS username. Leave Reserve account/partition blank if unknown. Supply a
   Python 3.9–3.12 module if the remote default is outside that range or lacks `venv`.
3. Run `./klc doctor`, then `./klc bootstrap`. Bootstrap clones the repository if
   absent, uploads toolkit files, creates a project-local Python environment, and
   discovers Stata modules. It never deletes remote files or pulls over research
   changes. GitHub clone access is required; private repos need remote Git authentication.
4. Run `./klc credentials`. Enter your WRDS password in the remote terminal.
   It stays only in KLC `~/.pgpass`, mode `600`; other entries are preserved.
5. Run `./klc doctor` again and approve any WRDS Duo prompt. Run `./klc code`
   to install Remote SSH and open the project in your installed VS Code.

Settings live in ignored `.klc/config.json`. Setup adds a managed block to
`~/.ssh/config`; rerunning updates that block and preserves other settings. Choose
another alias if yours already exists elsewhere. Password SSH works initially.
Enter `-` during setup to clear an optional setting.
Optional `./klc key` creates a dedicated Ed25519 key, installs its public key, and
loads it into the macOS SSH agent. Never share the private key.

## Daily use

```sh
./klc code
./klc connect
./klc run python examples/python_smoke.py
./klc run stata examples/stata_smoke.do
./klc status
./klc logs JOB_ID
./klc cancel JOB_ID
```

`run` prints a job ID and starts a detached `tmux` session. Disconnecting your Mac
leaves it running. Reconnect to the same host. Logs/metadata are under
`logs/jobs/JOB_ID/`. Scripts run in that job directory; use environment variable
`KLC_ROOT` for project paths. Smoke artifacts are `results/python_smoke.txt` and
`proc/stata_smoke.dta`. Stata logs are checked for `r(number);` even when its process
exits zero. Check your analysis artifacts too. `status` flags missing workers.
Host restarts can interrupt tmux jobs.

Direct jobs are for short development work. Threads default to one. KLC's 24-core
normal-priority limit applies across all your processes, not per job. For overnight
work or guaranteed memory, configure your actual Reserve account and partition
with setup, then bootstrap again:

```sh
./klc submit --cpus 4 --memory 16G --time 02:00:00 python scripts/my_analysis.py
```

SLURM validates resources/account/partition before submission. Rejection or missing
access fails explicitly, with no direct-job fallback. Resource options precede the
language; subsequent arguments belong to your script.

## WRDS PostgreSQL and large data

KLC account storage is limited. The intended workflow retrieves aggregate counts
and results: raw Revelio records stay on WRDS, and aggregation runs in WRDS
PostgreSQL. Only the small aggregate results are returned to KLC.

Use [revelio_tables.log](revelio_tables.log) as the data dictionary for Revelio
tables available directly through the SQL server. It lists the tables, approximate
row counts, column names, data types, nullability, and column descriptions from
the September 30, 2026 schema discovery. Refer to it when choosing tables and
fields for queries; use the discovery commands below to check the current schema.

```sh
./klc wrds discover
./klc wrds discover --schema revelio
./klc wrds discover --schema revelio --table individual_positions
```

For historical country coverage, run the counts-only script against
`revelio_individual.individual_positions`:

```sh
./klc run python scripts/country_coverage.py \
  --schema revelio_individual --table individual_positions \
  --country-column country --person-column user_id
```

This computes position counts and distinct people by country and globally across
all available history on WRDS. It saves only `countries.csv` and `summary.json`
under `results/country_coverage_<timestamp>/`, plus job logs and metadata under
`logs/jobs/JOB_ID/`, on KLC. It does not download individual position records.
Use `./klc status JOB_ID` and `./klc logs JOB_ID` to check completion; the finished
log prints the totals and results directory. A full-history query can take time
even though its output is small.

To inspect accessible job posting data, download a small preview with full job
descriptions and structured posting fields:

```sh
./klc run python scripts/job_descriptions_smoke.py --limit 20
./klc status JOB_ID
./klc logs JOB_ID
```

Make sure the new script is present in your KLC checkout before running it;
bootstrap uploads only toolkit files. After committing and pushing code, pull it
in the remote checkout after checking for local changes.

The script samples nonempty descriptions from `revelio.postings_cosmos_raw` and
left-joins `revelio.postings_cosmos` by `job_id`. It returns up to 20 observations
with titles, company, geography, dates, salary, role, remote status, and source
flags. Missing structured metadata remains null. This is an arbitrary sample,
not a representative sample; the final output is capped even if joins duplicate
rows. `--limit` accepts 1–100, and the query has a 60-second timeout.

Full text is saved on KLC under `data/job_postings_preview_<timestamp>/` in
`descriptions.jsonl` and `postings.csv`. Job IDs are strings to preserve precision;
use text columns when importing CSV into spreadsheets. `summary.json` records
completion, row count, returned fields, null counts, and SQL. Logs show five
compact previews and the output path. Zero results or query/access failures fail
the job; check permissions and authenticate interactively with `./klc doctor`
before retrying if needed.

The extraction and Stata export examples below are optional workflows. They
download records to KLC as Parquet files and create a local Stata dataset,
consuming KLC storage; they are not needed for counts-only country coverage.

Inspect actual tables/columns for your subscription. Example SQL assumes
`revelio.individual_positions`; adjust identifiers after discovery. Values use bound
parameters. Begin with one known company, country, date range, and a small limit:

```sh
./klc wrds extract examples/revelio_positions.sql \
  --params '{"rcid":123,"country":"United States","start_date":"2020-01-01","end_date":"2020-12-31","limit":1000}' \
  --output data/revelio_sample
./klc wrds export-stata data/revelio_sample proc/revelio_sample.dta
./klc run stata examples/analyze_revelio.do
```

`123` is a placeholder, not a verified company ID. Verify country values too. Keep
limits until filters are validated. For production, select only necessary columns
and filter/aggregate in SQL. Run extraction as a persistent Python job:

```sh
./klc submit --memory 16G --time 04:00:00 python tools/wrds_data.py extract \
  examples/revelio_positions.sql \
  --params '{"rcid":123,"country":"United States","start_date":"2020-01-01","end_date":"2020-12-31","limit":1000}' \
  --output data/revelio_batch
```

Authenticate interactively first. WRDS may request Duo again for new connections;
background authentication is not guaranteed. Review failed job logs and authenticate
again when necessary.

Extraction streams 100,000-row chunks (`--chunksize` overrides this) into separate
Parquet files. The manifest records SQL, parameters, rows, parts, and completion.
Interrupted extracts remain `incomplete`; output directories must be new. Rerun
into a new directory after failure; automatic resume is not provided. Never put
credentials in SQL parameters, which are saved as metadata.

Stata export refuses incomplete extracts and datasets above 100,000 rows by default
(`--max-rows` overrides this). Export small aggregates/filtered datasets instead of
loading a full extract into memory.

## Code, storage, and validation

Environments, data, outputs, logs, and local settings are ignored by Git. Use Git
for code: commit/push from the checkout where you edit, then pull elsewhere after
checking local changes. Bootstrap refreshes toolkit files, not arbitrary scripts.
Install Python/Jupyter extensions in remote VS Code as needed.

Legacy `scripts/00_run.do` belongs to another project; it is not this workflow's
entry point. Existing unrelated deletions are outside this setup.

Offline checks: `python3 -m unittest discover -s tests -v`.
Install `requirements-klc.txt` in a Python 3.9–3.12 environment to include the real
Parquet/Stata serialization tests; otherwise those two tests are skipped.
Live checks: doctor succeeds; a scoped extract completes; both smoke artifacts
exist; a job finishes after disconnect/reconnect; a Reserve smoke job succeeds if
access is available. Offline tests do not establish remote account/software access.

References: [KLC SSH](https://rs-kellogg.github.io/krs-documentation/services/klc/user-guide/klc-ssh.html),
[VS Code](https://rs-kellogg.github.io/krs-documentation/services/klc/user-guide/klc-vscode.html),
[WRDS from KLC](https://rs-kellogg.github.io/krs-documentation/services/kellogg-data-hosting/wrds/wrds.html),
[KLC Reserve](https://rs-kellogg.github.io/krs-documentation/services/klc-reserve/when-to-use.html),
[WRDS PostgreSQL (login required)](https://wrds-www.wharton.upenn.edu/pages/support/programming-wrds/wrds-data-postgresql/wrds-data-in-postgresql/).
