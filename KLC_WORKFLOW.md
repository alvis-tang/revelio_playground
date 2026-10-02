# Working with Revelio Labs on KLC

This guide explains the toolkit and the steps to follow when you return to the
project. Run commands marked **Mac terminal** in your Mac's Terminal app, from
the local `revelio_playground` repository. Commands marked **KLC terminal** run
in the terminal inside a VS Code window connected to KLC.

## What the extension installation did

The output saying `ms-vscode-remote.remote-ssh` was successfully installed means
your Mac's VS Code now has support for connecting to remote computers over SSH.
The accompanying extensions help edit SSH settings and browse remote connections.

When you run `./klc code`, the toolkit does two things:

1. Installs or checks the Remote SSH extension in your local VS Code.
2. Asks VS Code to open your configured project folder on KLC over SSH.

Returning to your Mac's shell prompt is expected: the editor opens separately.
The installation message alone does **not** confirm that SSH connected, that
the remote project exists, or that WRDS is accessible. It also does not download
Revelio data or launch an analysis.

Look for the new VS Code window. Its remote indicator, usually in the lower-left
corner, should say `SSH: <your alias>`. Open **Terminal > New Terminal** there:

**KLC terminal:**

```sh
hostname
pwd
```

The hostname should identify your KLC host, and the working directory should be
your remote project folder. If you still see your Mac's hostname, you are in a
local window. Avoid starting a large analysis until you confirm the remote window.

If no remote window appears, run `./klc code` again from the Mac repository.
Alternatively, in VS Code use **Remote-SSH: Connect to Host...** from the Command
Palette, select your configured alias, then open your remote project folder.
For errors, use **Remote-SSH: Show Log** in the Command Palette and inspect the
connection message. `./klc connect` tests the underlying SSH connection separately.

## Where each part runs

| Part | Location | Purpose |
| --- | --- | --- |
| `./klc ...` command toolkit | Mac terminal | Connects to KLC and dispatches remote work |
| VS Code interface | Mac | Displays and edits remote files |
| VS Code remote terminal | KLC | Executes commands directly on KLC |
| Python/Stata research jobs | KLC | Process data and save outputs |
| WRDS PostgreSQL | WRDS servers | Executes your SQL filters and aggregations |
| Parquet extracts and `.dta` outputs | KLC project storage | Holds research data |
| GitHub | GitHub | Versions code and documentation |

The local and remote repositories are separate checkouts. Editing a file in the
remote VS Code window changes the KLC copy immediately, not the Mac copy. Git
transfers committed code between the two. It does not transfer ignored datasets.

Do not run `./klc ...` from the KLC terminal: it is a Mac-side dispatcher and would
attempt another SSH connection. Use a separate Mac Terminal window for these
commands while editing in remote VS Code.

## Finish first-time setup

Skip steps that have already succeeded. The extension installation can happen
before remote bootstrap or WRDS authentication, so verify each part separately.

**Mac terminal:**

```sh
cd /Users/alvis/work/github/revelio_playground
./klc setup
./klc doctor
./klc bootstrap
./klc credentials
./klc doctor
./klc code
```

- `setup` saves connection identifiers and adds an SSH alias. It does not log in
  or request a WRDS password. On later runs, press Enter to retain saved values;
  use `-` to clear an optional value.
- Project storage must be an **existing absolute path**, not just `revelio`.
  `/kellogg/proj/<netid>` is an example only; use your assigned writable directory.
  Bootstrap creates `revelio_playground` inside that directory.
- The first `doctor` checks connection and storage. Before bootstrap, a message
  asking you to bootstrap is expected. Afterwards it also tests WRDS with `SELECT 1`.
- `bootstrap` prepares the remote checkout, Python environment, and output folders.
  It uploads toolkit/example files; it is not a general synchronization command.
  Rerunning it can replace remote toolkit/example edits, so commit those edits first.
- `credentials` asks for your WRDS password in a remote terminal and stores it in
  your private KLC `~/.pgpass`. Never put the password in Git or a command argument.
- `code` opens the remote editor. Approve SSH prompts and any required WRDS Duo
  requests yourself. Only accept an unfamiliar SSH host key after verifying it.

The Python environment requires Python 3.9–3.12. If bootstrap reports an incompatible
Python version, inspect `module avail python` in a KLC terminal, rerun setup with
an available module name, then bootstrap again. Reserve account and partition
can stay blank until you know your allocation; they are not your WRDS username.

## Every future work session

1. Open a Mac terminal in the local repository and run `./klc code`.
2. Confirm the remote indicator and open your project in the KLC VS Code window.
3. Edit or create research code there, normally under `scripts/`.
4. Launch a short job from your Mac terminal with `./klc run`.
5. Save its printed job ID; inspect status, logs, and expected output files.
6. Commit and push code from the checkout where you edited it.

You do not need setup, bootstrap, or credentials every session. Repeat setup
when connection settings change; repeat credentials when your WRDS password changes.

For a quick first check, use the supplied examples:

**Mac terminal:**

```sh
./klc run python examples/python_smoke.py
./klc run stata examples/stata_smoke.do
./klc status
```

Each `run` prints a different job ID. Replace `JOB_ID` below with that exact value:

```sh
./klc status JOB_ID
./klc logs JOB_ID
```

In the remote file explorer, verify `results/python_smoke.txt` and
`proc/stata_smoke.dta`. A successful launch is different from a completed job.
The Stata runner also checks the batch log for `r(number);` errors.

## Write and run your own code

Create scripts in the remote VS Code window. The toolkit runs each job in a
separate directory under `logs/jobs/`, so use `KLC_ROOT` to locate project data.
The examples below are templates to paste into new files, not terminal commands.

**Python template, `scripts/my_analysis.py`:**

```python
import os
from pathlib import Path
import pandas as pd

root = Path(os.environ["KLC_ROOT"])
sample = pd.read_stata(root / "proc/revelio_sample.dta")
print(sample.shape)
print(sample.head())
```

**Stata template, `scripts/my_analysis.do`:**

```stata
clear all
set more off
version 17.0
local root : environment KLC_ROOT
confirm file "`root'/proc/revelio_sample.dta"
use "`root'/proc/revelio_sample.dta", clear
describe
```

After creating the sample data described below, launch either template:

**Mac terminal:**

```sh
./klc run python scripts/my_analysis.py
./klc run stata scripts/my_analysis.do
```

Direct runs use detached `tmux` sessions. You may close VS Code or disconnect your
Mac while they run. Reconnect to the same host to check them. A KLC restart can
still interrupt them. Keep direct work short; choose Reserve for overnight or
substantial resource needs.

## Start with a small WRDS extract

First discover the Revelio schemas your account can actually access:

**Mac terminal:**

```sh
./klc wrds discover
```

Then inspect a returned schema and its tables. The following identifiers are
examples; replace them if discovery returns different names:

```sh
./klc wrds discover --schema revelio
./klc wrds discover --schema revelio --table individual_positions
```

In remote VS Code, review `examples/revelio_positions.sql`. It selects a small
set of position columns and filters by company, country, and overlapping dates.
The placeholders such as `%(rcid)s` receive values from `--params`; they are not
filled by string concatenation. Adjust table/column names to the discovered schema.

Before executing, replace company ID `123` with a verified `rcid` and verify the
country spelling against your data. Keep the 1,000-row limit for the first test.

**Mac terminal:**

```sh
./klc wrds extract examples/revelio_positions.sql \
  --params '{"rcid":123,"country":"United States","start_date":"2020-01-01","end_date":"2020-12-31","limit":1000}' \
  --output data/revelio_sample
./klc wrds export-stata data/revelio_sample proc/revelio_sample.dta
./klc run stata examples/analyze_revelio.do
```

The example analysis counts rows in the extracted sample, not population headcounts.
Check its job log and `proc/revelio_sample_counts.dta`.

`data/revelio_sample/` is on KLC. It contains Parquet parts and `manifest.json`.
The manifest must say `complete` before analysis. Extracts stream in 100,000-row
chunks by default. Chunking limits transfer memory; SQL filters still determine
the overall amount of work and disk space needed.

Use a **new output directory** for each extract. If the directory already exists,
the command refuses to overwrite it. Interrupted extracts stay `incomplete`; the
toolkit does not resume them. Inspect logs, fix the problem, and rerun into a new
directory. Stata export defaults to at most 100,000 rows; build a smaller aggregate
or subset in SQL for analysis instead of exporting the whole database.

## First country-coverage analysis: edit on Mac, run on KLC

This example counts position records and distinct people by recorded country
across all available history. Edit the code in the Mac checkout (including when
working through this chat), push it to GitHub, and pull it into the KLC checkout.
WRDS performs the aggregation; only country-level results are saved on KLC.

First verify your connection and discover the positions table and columns.

**Mac terminal:**

```sh
cd /Users/alvis/work/github/revelio_playground
./klc doctor
./klc wrds discover
./klc wrds discover --schema ACTUAL_SCHEMA
./klc wrds discover --schema ACTUAL_SCHEMA --table ACTUAL_TABLE
```

Replace `ACTUAL_SCHEMA` and `ACTUAL_TABLE` with identifiers returned by discovery.
Confirm the recorded position-country field and stable person identifier. Check
the source documentation to establish that one row represents one position,
rather than a monthly observation or another repeated record. The repository's
`revelio.individual_positions`, `country`, and `user_id` are examples, not verified
identifiers for your subscription. Do not select an arbitrary table if several
positions products are available.

Live discovery verified `revelio_individual.individual_positions`, with `country`
as the recorded country, numeric `user_id` as the person identifier, and
`position_id` as the position identifier. Its fields include position start/end
dates rather than monthly observation dates. WRDS estimated about 1.83 billion
rows at discovery, so exact full-history distinct counts can take hours. Counts
remain source-record counts; discovery does not establish position-ID uniqueness.
The script preserves numeric person IDs and trims blank text IDs when applicable.

Once the analysis code is committed and pushed, update the remote checkout.

**KLC terminal in remote VS Code:**

```sh
cd /kellogg/proj/cxv7409/revelio_playground
git status --short
git pull --ff-only
```

Review any remote changes before pulling; preserve them rather than resetting
the checkout. Bootstrap does not synchronize the new research script.

Launch the analysis with the verified identifiers. Replace all four uppercase
placeholders before running this command.

**Mac terminal:**

```sh
./klc run python scripts/country_coverage.py \
  --schema ACTUAL_SCHEMA --table ACTUAL_TABLE \
  --country-column ACTUAL_COUNTRY_COLUMN --person-column ACTUAL_PERSON_COLUMN
./klc status JOB_ID
./klc logs JOB_ID
```

For that verified source, the launch command is:

```sh
./klc run python scripts/country_coverage.py \
  --schema revelio_individual --table individual_positions \
  --country-column country --person-column user_id
```

Replace `JOB_ID` with the ID printed at launch. This is a full-history database
aggregation and may take time even though its output is small. Use `./klc submit`
instead of `./klc run` for overnight work once Reserve access is configured.
Approve any required Duo request and inspect failed job logs before retrying.

**Output location on KLC:** the job prints an absolute directory under
`results/country_coverage_<UTC timestamp>/`. Open it in remote VS Code to inspect:

- `countries.csv`: country, missing-country flag, position records, distinct
  people, records missing person IDs, and percentage of all position records.
- `summary.json`: completion status, global totals, named-country count,
  missing-country records, source identifiers, SQL, UTC execution times, elapsed
  seconds, and counting definitions. Its presence with `status: complete` is the
  output completion marker; also check that the job status is `complete`.

Country position counts add to the global record count, and position shares
include missing-country records in their denominator. Country people counts do
not add to the globally distinct total: someone with jobs in two countries
appears in both. NULL and blank person IDs are excluded from distinct counts and
reported separately. Country and person strings are trimmed; country labels are
not otherwise recoded. Missing/blank countries are labeled `Unknown` with
`country_missing=True`, so a literal source label `Unknown` remains distinguishable.
Historical counts describe the accessible dataset, not current employment or
national population headcounts. An empty source produces a header-only CSV and
zero totals.

Code belongs on GitHub; results remain on KLC and are ignored by Git. Offline
validation uses `python3 -m unittest discover -s tests -v`; install
`requirements-klc.txt` and the development-only `duckdb` package to run all
serialization and country-query tests. DuckDB is not needed for production.

## Large or overnight jobs

Find your actual Reserve account and partition through your existing allocation
or Kellogg Research Support. Enter them with `./klc setup`, then run bootstrap
again to update the remote settings.

**Mac terminal:**

```sh
./klc submit --cpus 4 --memory 16G --time 02:00:00 python scripts/my_analysis.py
./klc status JOB_ID
./klc logs JOB_ID
```

These resource values are examples, not a recommendation for every dataset.
Reserve uses SLURM to queue the job and reserve resources. Submission validates
your account/partition first. Missing access causes an error, with no fallback
to running a large job directly. To stop a job, use `./klc cancel JOB_ID`.
WRDS may require a new Duo approval even for background work; validate authentication
interactively before submission and inspect logs if a background query fails.

## Keep code synchronized with GitHub

When editing in remote VS Code, Git commands in its integrated terminal operate
on the **KLC checkout**. Commit and push there, then update your Mac checkout.
Choose specific code/documentation paths; do not stage datasets or unrelated changes.

**KLC terminal, after editing:**

```sh
git status
git add scripts/my_analysis.py
git commit -m "Add Revelio sample analysis"
git push
```

**Mac terminal, to receive the committed code:**

```sh
git status
git pull --ff-only
```

For code edited on the Mac, reverse the direction: commit/push on the Mac, then
pull on KLC. Review local changes before pulling. This Mac checkout currently
has unrelated deletions; preserve or resolve them deliberately if Git blocks a
pull. Do not use a hard reset to bypass that check.

The remote checkout needs its own GitHub authentication to push. KLC login and
WRDS credentials do not automatically grant GitHub access. If authentication fails,
configure GitHub authentication on KLC before retrying; your local commit remains.

Data, processed files, environments, logs, and results are ignored by Git. They
stay on KLC. Do not assume remote edits or output files appear on your Mac unless
you explicitly transfer them.

## Quick troubleshooting

| Symptom | Next step |
| --- | --- |
| Only extension installation output | Find the remote VS Code window and verify `hostname` |
| `Run ./klc setup first` | Run setup from the local repository |
| Absolute project path required | Supply your existing full storage path |
| SSH timeout or connection refused | Check host spelling and campus/VPN network; try `./klc connect` |
| Remote folder/environment missing | Run `./klc bootstrap` from your Mac |
| Unsupported Python version | Select an available Python 3.9–3.12 module in setup |
| WRDS authentication failure | Run credentials, then doctor; approve Duo if requested |
| No accessible Revelio schemas | Verify your WRDS subscription permissions |
| Stata unavailable | Configure an installed Stata module, then bootstrap again |
| Reserve unavailable or unconfigured | Set your assigned account/partition; no direct fallback |
| Job status is `failed` or worker missing | Inspect `./klc logs JOB_ID` and expected artifacts |
| Extract output already exists | Choose a new output directory |

See [README.md](README.md) for command references and official documentation links.
