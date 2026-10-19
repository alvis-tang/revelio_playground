# KLC tasks

Hong Kong statuses last checked on October 7, 2026 (America/Chicago), using the
remote status command over SSH. Other jobs retain their previously recorded snapshots.
Philippines status last checked on October 18, 2026 at 20:35 CDT over SSH.
Launch dates below use America/Chicago (CDT, UTC−05:00), converted from the UTC
timestamp in each KLC job ID. Statuses are a snapshot; use the commands below
to check current progress.

| KLC task number (job ID) | Launch date and time (CDT) | Task description | Status | Check logs |
| --- | --- | --- | --- | --- |
| `20261002T023459-0b3b81` | 2026-10-01 21:34:59 | Count historical positions and distinct people by country from `revelio_individual.individual_positions`. | Failed: WRDS connection timeout | `./klc logs 20261002T023459-0b3b81` |
| `20261002T025453-64ba9e` | 2026-10-01 21:54:53 | Retrieve a 20-row job posting preview with descriptions and structured metadata (first attempt). | Failed | `./klc logs 20261002T025453-64ba9e` |
| `20261002T025657-e21631` | 2026-10-01 21:56:57 | Retrieve a 20-row job posting preview with descriptions and structured metadata (retry). | Complete | `./klc logs 20261002T025657-e21631` |
| `20261002T032127-aa5075` | 2026-10-01 22:21:27 | Estimate Malawi extraction storage, then download if accessibility checks and the 20 GB gate pass (`estimate --download-if-safe`). | Failed: WRDS connection timeout during raw-position count | `./klc logs 20261002T032127-aa5075` |
| `20261002T152310-a233db` | 2026-10-02 10:23:10 | Worldwide historical country coverage in resumable numeric person-ID batches (range width 1,000,000; 900-second query limit). | Running | `./klc logs 20261002T152310-a233db` |
| `20261002T153034-8dd58f` | 2026-10-02 10:30:34 | Restart Malawi storage estimate and gated download with TCP keepalives and revised raw-position joins (`estimate --download-if-safe`). | Failed: WRDS SSL EOF during raw-position count | `./klc logs 20261002T153034-8dd58f` |
| `20261002T214915-661800` | 2026-10-02 16:49:15 | Restart Malawi estimate and gated download with indexed raw-position person batches (`estimate --download-if-safe`). | Failed: WRDS SSL EOF during unmatched-education check | `./klc logs 20261002T214915-661800` |
| `20261003T034030-cc5164` | 2026-10-02 22:40:30 | Restart Malawi estimate and gated download with indexed unmatched-education batches (`estimate --download-if-safe`). | Running: connected to WRDS; selecting cohort | `./klc logs 20261003T034030-cc5164` |
| `20261003T235606-6f880b` | 2026-10-03 18:56:06 | First Hong Kong estimate-and-download launch from an isolated code copy. | Failed before WRDS connection: isolated copy lacked KLC settings link | `./klc logs 20261003T235606-6f880b` |
| `20261003T235630-408292` | 2026-10-03 18:56:30 | Estimate all Hong Kong-linked products, then download if access checks and the 20 GB gate pass. | Failed: WRDS SSL EOF while counting raw job descriptions; full download never started | `./klc logs 20261003T235630-408292` |
| `20261004T140024-56dfbb` | 2026-10-04 09:00:24 | Fresh Hong Kong estimate and gated download with 1,000-ID raw posting batches, checkpoints, and transport retries. | Stopped at 20 GB gate: completed estimate projects 21.01 GB; no full download started | `./klc logs 20261004T140024-56dfbb` |
| `20261005T144257-3445aa` | 2026-10-05 09:42:57 | Resume completed Hong Kong estimate with a per-run 25 GB cap, preserving all 24 products and saved work. | Complete: all 24 products and the cohort downloaded (9,371,963,844 bytes); global manifest `complete` at 2026-10-06 18:47:53 CDT | `./klc logs 20261005T144257-3445aa` |
| `20261007T161803-1bf289` | 2026-10-07 11:18:03 | Hong Kong measurement milestone 1, stages 00-05 (first launch). | Cancelled during raw hashing to relaunch with final configuration; no outputs written | `./klc logs 20261007T161803-1bf289` |
| `20261007T162019-6e8764` | 2026-10-07 11:20:19 | Hong Kong measurement milestone 1: inventory, cleaning, quarterly panel, diagnostics, migration events, and approximate replication (`hk_revelio/run.py --stages all`). | Complete in 1 h 51 min; raw listing and content hashes unchanged | `./klc logs 20261007T162019-6e8764` |
| `20261007T181351-e23ad8` | 2026-10-07 13:13:51 | Rerun milestone stages 00 and 03 (data-dictionary join labels; quarantine denominators). | Complete in 36 min; raw listing unchanged; code hash matches the committed code | `./klc logs 20261007T181351-e23ad8` |
| `20261019T013510-fd02fe` | 2026-10-18 20:35:10 | Estimate the full Philippines-linked extract, then download if all checks and the per-run 100 GB cap pass. | Running: WRDS connected; collecting Philippines person IDs; full download has not started | `./klc logs 20261019T013510-fd02fe` |

## Philippines download with a 100 GB cap

Job **`20261019T013510-fd02fe`** launched on October 18, 2026 at **20:35:10 CDT**
(America/Chicago), on `klc0503`. It uses the existing detached tmux task runner
with one CPU thread. At the initial post-launch check, the worker was running,
WRDS authentication succeeded, and all 23 source tables were accessible. The
worker was collecting the Philippine person cohort; the checkpoint was
`incomplete`, with no error. The full download has not started.

The extract includes the same 24 products as the Hong Kong and Malawi workflows
(23 source tables plus the people cohort). People qualify by Philippine
residence or any historical Philippine position, and their complete available
histories are retained. Philippine postings and original descriptions, linked
companies and schools, reviews, workforce observations, and lookup/context
products are included across all available dates. There is no sampling fallback.

Launch command from the Mac repository:

```sh
./klc run python logs/philippines_code_20261018/scripts/malawi_extract.py \
  estimate --country Philippines --resumable --posting-batch-size 1000 \
  --budget-gb 100 --download-if-safe
```

The isolated deployment is `logs/philippines_code_20261018/` beneath
`/gpfs/kellogg/proj/cxv7409/revelio_playground/`. Its `.klc` link uses the existing
KLC settings. Deployment SHA-256 checks verified all 60 copied source files.
The remote checkout's status and hashes of all 11 pre-existing changed/untracked
files matched their pre-deployment snapshot. Existing research edits were
preserved. Deployment metadata, preflight results, and test logs remain under
the ignored deployment directory.

All **177 repository tests passed on KLC, with no skips**, including Philippine
linked-data fixtures for full histories, geography filters, raw matches,
serialization and failure handling. Resume tests verify both 25 GB and 100 GB
caps reach every writer and survive resume without repeating completed
estimation. Tests used the existing `.venv-llm` interpreter and dependencies,
with the existing Hong Kong environment's DuckDB package appended to the test
import path; neither research environment was changed. The worker uses the
existing toolkit `.venv`.

The GPFS project fileset `kellogg_proj_cxv7409` has a **2 TiB quota**. Immediately
before launch, `df -B1` reported **120,728,846,336 bytes free** (120.7 decimal GB,
112.4 GiB). The **100,000,000,000-byte** run cap includes retained estimates and
download files, leaving about 20.7 GB at the cap if other usage stays constant.
Missing access, an oversized planning estimate, or insufficient available space
stops the workflow with its checkpoint preserved. The existing schema, row-count,
cohort-integrity, per-part writing, and completion checks remain in force.

Paths beneath the remote repository root:

- Estimate/checkpoint: `results/philippines_estimate_20261019T013511632138Z/`
- Planned data directory: `data/philippines_20261019T013511632138Z/`
- Job log: `logs/jobs/20261019T013510-fd02fe/output.log`

Monitor with `./klc status 20261019T013510-fd02fe` and
`./klc logs 20261019T013510-fd02fe`. Resume saved work through the same isolated
deployment:

```sh
./klc run python logs/philippines_code_20261018/scripts/malawi_extract.py \
  estimate --resume \
  /gpfs/kellogg/proj/cxv7409/revelio_playground/results/philippines_estimate_20261019T013511632138Z
```

Resume retains the saved Philippines selection, 100 GB cap, and automatic-download
setting. A running worker does not establish download completion: the final
global data `manifest.json` must report `complete` before using the extract.

### Preliminary Philippine ad-language check

A read-only pilot during planning inspected **150 unique Philippine posting
IDs**, 50 each from 2022, 2024, and 2026. **147 descriptions (98%) classified as
English**; three short descriptions remained uncertain. The yearly counts were
47 English and three uncertain in 2022, and 50 English in each of 2024 and 2026.
This supports a preliminary conclusion that the available ads are mostly English,
but it is not a representative population estimate.

For each year, the query filtered `revelio.postings_cosmos.country='Philippines'`
and the interval August 31 inclusive through September 7 exclusive, ordered by
descending `post_date`, and limited candidates to 50 before indexed lateral
lookups in `revelio.postings_cosmos_raw`. Posting-date index use was verified.
Date ties were arbitrary, and IDs were deduplicated. Up to two raw matches per
candidate were checked; missing/empty text or conflicting descriptions would
have remained separate categories, but none occurred in these 150 records.
A 2020 query hit its 60-second timeout and is excluded from the reported sample.

Classification used original `description` text after HTML tags, script/style
content, and HTML entities were handled with Python's HTML parser; translated
titles were not used. Lingua **2.1.1**, with all supported languages including
Tagalog, assigned a dominant language only with at least 40 alphabetic characters,
top confidence at least 0.60, and a lead of at least 0.20 over the next language.
This measures dominant document language rather than the absence of bilingual
passages. Text stayed on KLC and was processed in memory; sampled records and
credentials were not added to Git.

## Revelio LLM GPU pilot

Setup completed on October 18, 2026. The fresh WRDS extract contains 20 postings
under `results/revelio_llm_20261018T152442841200Z/` on KLC, and package validation
passed. The dedicated environment is `.venv-llm`; the editable package checkout
is `/kellogg/proj/cxv7409/llm-batch_pipeline`. Installation revision and dependency
versions are recorded under `.venv-llm/` and copied into each execution's metadata.
All eight new workflow tests passed on KLC, including real package preparation
with long string IDs and server cleanup after failure or cancellation.

The first native Slurm job, **4304976**, started earlier than the scheduler's
initial estimate, downloaded the model, and started Ollama successfully on an
A100 GPU node. It failed during package preparation because the compute node
lacked a Git executable. The submission script now loads the native
`git/2.47.0-gcc-12.4.0` module and checks Git through Python before inference.
The downloaded weights remain cached.

Retry job **4306579** requests one GPU, four CPU cores, 16 GB RAM, and 30 minutes
on account/partition `kellogg`, processing four postings with `llama3.1:8b`, seed 42.
The retry was pending at the final setup check. The user elected to leave the
pilot queued and finish setup; live inference, GPU offload, and the final result
audit remain pending.

In a KLC terminal, check `squeue -j 4306579`,
`sacct -j 4306579 --format=JobID,State,ExitCode,Elapsed`, and
`logs/revelio_llm_4306579.log` once execution begins. Outputs will be under the
project's `executions/4306579_TIMESTAMP/` directory. `pilot.json` reports complete
only after four valid results and GPU offload are confirmed. Existing remote
research changes were preserved. See the README's local LLM section for reuse.

## Independent multilingual Qwen3 pilot

Submitted native Slurm job **4313662** (`revelio-multilingual`) on October 18,
2026 at **11:16:56 CDT** (America/Chicago). The submission requests account and
partition `kellogg`, one GPU, four CPU cores, 16 GB RAM, and 30 minutes. It runs
all 16 frozen ads, one posting per request, using `qwen3:8b`, temperature `0.7`,
`reasoning_effort: none`, and a 3,000-token output limit.

The project is
`/gpfs/kellogg/proj/cxv7409/revelio_playground/results/revelio_multilingual_20261018T161200Z/`.
Its Slurm log is
`/gpfs/kellogg/proj/cxv7409/revelio_playground/logs/revelio_multilingual_4313662.log`.
The isolated deployment is `logs/revelio_multilingual_code_20261018/`, under the
same repository root. Existing remote edits and the original Llama runner and
wrapper were preserved. All 10 SHA-256 hashes for the original Llama project's
source files and runners matched the pre-task snapshot; job **4306579** was
still pending with its original configuration and project.

The sample contains exactly two unique ads in each of eight groups: English,
Chinese, Spanish, French, Arabic, Japanese, Korean, and mixed Chinese/English.
The Chinese pair contains one simplified and one traditional description.
Candidate retrieval returned **1,800 descriptions**, within the 2,000-description
cap. All retrieval statements used a 60-second timeout; saved plans show the
posting-date index and indexed raw-ID lookups. An initial query that sorted date
ties timed out without returning descriptions; the successful query streams
from the date index. Geography guided retrieval, while local Lingua 2.1.1
passage classification and OpenCC character mappings determined inclusion.
Ambiguous classifications, conflicting duplicate IDs, and duplicate descriptions
were excluded. Candidate counts after classification/deduplication were 201
English, 322 Chinese, 42 Spanish, 112 French, 4 Arabic, 24 Japanese, 104 Korean,
and 5 mixed Chinese/English ads. Sorted IDs and seed 42 selected the frozen ads.

The project's `source.json` archives the candidate pool, classifications, queries,
parameters, plans, and dependency versions. `language_coverage.json` reports
complete coverage and freezes selected IDs, languages, script evidence, and
substantial passage offsets. `freeze.json` binds the inputs, classifications,
prompts, schema, configuration, and extraction metadata with SHA-256 hashes.
Its recorded digest is
`39872c65bf952a4aaee5a10ad6be745511e6ddebbbf22d10ee837aae02fb307e`.
Raw UTF-8 text and string IDs remain in the ignored project, including a local
copy under the same relative `results/` path.

All **153 repository tests passed locally**, with no skips. All **21 focused
LLM/multilingual tests passed on KLC**. The complete real-data project passed
local and KLC validation and preparation of all 16 requests, including exact
string IDs, unchanged Unicode/whitespace, Qwen3 model/options, and exclusion of
company and geography metadata. Preflight caught upstream whitespace trimming;
a scoped multilingual input adapter preserves the original text without changing
the default Llama path. Reports are `preflight_validation.json` and
`preflight_requests.json` in the project. No model inference was run on a login
node or the Mac.

Slurm's `sbatch --test-only` preflight passed **before submission**, estimating
**October 18, 2026 at 14:36:54 CDT** on `qgpu0518`. At the first post-submission
check, job 4313662 was **PENDING** and its actual `StartTime` was still `Unknown`;
the preflight estimate is provisional. Live inference, quote validation on model
outputs, exact final ID coverage, and GPU offload remain **pending**. Submission
is the handoff point while the job is queued. Runtime completion requires all
16 valid results, exact frozen ID coverage, valid evidence for every extracted
item, and positive GPU model offload in `gpu_usage.json`, with `pilot.json`
reporting `complete`.

Launch command, from the remote repository root:

```sh
sbatch --parsable --job-name=revelio-multilingual \
  --output=logs/revelio_multilingual_%j.log \
  --export=ALL,KLC_ROOT=/kellogg/proj/cxv7409/revelio_playground/logs/revelio_multilingual_code_20261018 \
  logs/revelio_multilingual_code_20261018/scripts/revelio_llm.sbatch \
  /kellogg/proj/cxv7409/revelio_playground/results/revelio_multilingual_20261018T161200Z \
  --profile multilingual
```

Monitor using `squeue -j 4313662`,
`sacct -j 4313662 --format=JobID,State,ExitCode,Elapsed,AllocTRES`, and the log
above. Execution artifacts will be under the project's
`executions/4313662_TIMESTAMP/`. Each extracted skill or education requirement
must include an English phrase and a short verbatim source-description quote;
missing or fabricated evidence fails the record. Detected languages and reading
status distinguish unreadable text from absent requirements. English normalization
and faithful interpretation still require researcher review; this is a
language-coverage smoke test, not an accuracy benchmark.

## Toolkit job commands

The command is `./klc logs JOB_ID` (plural). To check one toolkit job's current status,
run `./klc status JOB_ID`; run `./klc status` to list all recorded jobs.

## Hong Kong measurement milestone 1

Code: [`hk_revelio/`](hk_revelio/README.md), deployed for these runs to the isolated
KLC path `logs/hk_revelio_code_20261007/hk_revelio/`, so the remote checkout and its
uncommitted edits are untouched. DuckDB 1.5.6 and PyYAML live in
`logs/hk_revelio_env/`; the toolkit `.venv` is unchanged. Jobs used one thread and
a 6 GB DuckDB memory limit.

Input (read-only): `data/hong_kong_20261004T140024976790Z/`. Work root and all
derived data: `results/hk_revelio_m1_20261007/`, with per-stage fingerprints under
`run/`. The requested artifacts were copied to the local ignored paths
`hk_revelio/docs/data_dictionary.md`, `hk_revelio/output/diagnostics/`,
`hk_revelio/output/tables/replication_summary.csv`, and
`hk_revelio/data/derived/person_quarter_sample.parquet`.

The full run completed all six stages. Stages 00 and 03 were then rerun with
presentation-only fixes: join relationship labels in the data dictionary, and
denominators for quarantined-position counts. Stages 01, 02, 04, and 05 ran with
the earlier code hash, which differs only in those two files. All 18 pipeline
tests and all 132 repository tests passed. The milestone stops here until the
measurement results are inspected.

## Hong Kong 25 GB resume

Job `20261005T144257-3445aa` started at 09:42:57 CDT on October 5, using updated
isolated code in `logs/hong_kong_cap25_code/`. The previous worker had completed
all 24 product estimates and unmatched checks, then stopped at the 20 GB gate.
Expected storage was 15,615,738,207 bytes; the planning estimate including the
safety margin was 21,013,359,306 bytes. KLC reported about 125 GB free before
this resume. All 132 regression tests passed on KLC.

This resume reuses the existing estimate/checkpoint directory and data path:
`results/hong_kong_estimate_20261004T140024976790Z/` and
`data/hong_kong_20261004T140024976790Z/`. The cap is now 25,000,000,000 bytes for
this run only. Original checkpoint/report metadata is backed up inside the
estimate directory; the checkpoint records the old/new cap and timestamp.
Other runs retain their default or saved cap. Existing code and artifacts remain.
The worker connected to WRDS, loaded both frozen cohorts, passed the planning
gate, and created the download manifest with `budget_bytes=25000000000`. The
first employment-table unit is performing its count check before writing parts.

Launch command:

```sh
./klc run python logs/hong_kong_cap25_code/scripts/malawi_extract.py \
  estimate --resume /gpfs/kellogg/proj/cxv7409/revelio_playground/results/hong_kong_estimate_20261004T140024976790Z \
  --budget-gb 25
```

Future resumes use the same updated deployment and can omit `--budget-gb` to
retain the saved 25 GB cap. The download is complete only when the global
manifest says `complete`.

## Earlier Hong Kong resumable estimate

Replacement job: `20261004T140024-56dfbb`, launched at 09:00:24 CDT on October 4.
This worker completed estimation for all 24 products and stopped because the
21.01 GB planning estimate exceeded its 20 GB cap. It did not start the full
download; the October 5 job above resumes its completed work.

Estimate/checkpoint directory:
`results/hong_kong_estimate_20261004T140024976790Z/`.
Planned data directory: `data/hong_kong_20261004T140024976790Z/`.

The isolated code is under `logs/hong_kong_resume_code_20261004/`, with a link
to existing KLC settings. Existing remote edits, failed outputs, and other workers
were preserved. All 126 tests passed on KLC, including whole-run extraction,
resume, disconnect retries, duplicate preservation, partial-file cleanup,
cohort integrity, locking, storage limits, and schema/count mismatch checks.

Read-only checks used first, middle, and last 1,000-ID windows from the previous
Hong Kong structured-posting pilot. All plans used indexes. Raw-description
counts took 5.255, 3.908, and 5.174 seconds; unmatched checks took 2.955, 1.478,
and 1.487 seconds. Each window returned 1,000 descriptions and zero unmatched
postings. These pilot checks validate bounded query behavior, not full coverage.

```sh
./klc run python logs/hong_kong_resume_code_20261004/scripts/malawi_extract.py \
  estimate --country 'Hong Kong' --resumable --posting-batch-size 1000 --download-if-safe
```

The original resume command below is retained for history. After the cap change,
use the updated October 5 deployment above:

```sh
./klc run python logs/hong_kong_resume_code_20261004/scripts/malawi_extract.py \
  estimate --resume /gpfs/kellogg/proj/cxv7409/revelio_playground/results/hong_kong_estimate_20261004T140024976790Z
```

The 20 GB cap and product-access checks remain in place. Each unit uses its own
read-only snapshot, with frozen cohorts and validated download counts. Check
both job status and the global download manifest before using the data.

## Earlier Hong Kong attempt

Job `20261003T235630-408292` failed with WRDS SSL EOF while counting raw job
descriptions after estimates for 11 products were saved. No full data directory
was created. It had connected to WRDS and selected people with Hong Kong residence or
any historical Hong Kong position. Their full histories and the same current
products as Malawi are selected, with no date restriction. Access checks and
the 20 GB planning/writing cap apply before and during download.

Estimate directory: `results/hong_kong_estimate_20261003T235631322838Z/`.
Planned data directory: `data/hong_kong_20261003T235631322838Z/`.

The code was uploaded to `logs/hong_kong_code_20261003/` to preserve existing
remote edits and workers. All 89 tests passed there, including Hong Kong and
Malawi linked-data integration checks. The isolated copy uses a link to the
existing `.klc` settings; the first launch failed before connecting because
that link was missing. No extraction began in that failed attempt.

Launch command:

```sh
./klc run python logs/hong_kong_code_20261003/scripts/malawi_extract.py \
  estimate --country 'Hong Kong' --download-if-safe
```

Check job status and the completed data manifest before using the extract.

## Malawi restart

Latest restart: `20261003T034030-cc5164` at 22:40:30 CDT on October 2.
The worker is running, connected to WRDS, and selecting the cohort for a fresh
estimate. The accessibility checks and 20 GB gate remain in place.
Estimate directory: `results/malawi_estimate_20261003T034031596069Z/`.
Planned data directory: `data/malawi_20261003T034031596069Z/`.

The previous job (`20261002T214915-661800`) failed with `SSL SYSCALL error:
EOF detected`; its log was last modified at 21:11:41 CDT on October 2.
All 24 products had saved counts and pilots (8,809,248 retained bytes), and
the batched unmatched-position check finished. The connection closed during
the unmatched-education query, before a full download started. The logs do not
establish why WRDS closed the connection.

The education query used a null-safe user-ID comparison that produced a costly
full-table anti-join. Selected education IDs are non-NULL, so equality preserves
the matching semantics. The check now uses indexed equality in disjoint
1,000-person batches in both estimation and download. First, middle, and last
live batches used indexes on both education tables and returned zero unmatched
rows in 0.62, 0.28, and 0.67 seconds. All 64 tests passed in an isolated KLC
directory, including the duplicate/NULL regression test. This validates the fix,
but does not establish completion of the replacement job.

The old script was preserved under `logs/malawi_restart_backup_20261003T034025Z/`.
Existing failed estimates and the worldwide coverage worker were preserved.

### Earlier afternoon restart

Job `20261002T214915-661800` started at 16:49:15 CDT on October 2 and connected
to WRDS. It runs a fresh estimate before any download, retaining the accessibility
checks and 20 GB storage gate. The worldwide coverage job was left running.

Estimate directory:
`/gpfs/kellogg/proj/cxv7409/revelio_playground/results/malawi_estimate_20261002T214916234061Z/`.
Planned data directory:
`/gpfs/kellogg/proj/cxv7409/revelio_playground/data/malawi_20261002T214916234061Z/`.

The morning retry (`20261002T153034-8dd58f`) failed at 13:02:56 CDT with
`SSL SYSCALL error: EOF detected` while counting raw positions. It selected
258,626 people and counted 805,829 structured positions; no full download began.
Its incomplete estimate and pilots remain under
`results/malawi_estimate_20261002T153035796452Z/` (1,837,385 bytes).
The logs establish connection loss, but do not identify why WRDS closed it.

The full-cohort query plan scanned about 1.83 billion raw positions and included
an unnecessary postings scan. Raw positions now use disjoint 1,000-person batches
and a separate NULL-person query for counts, pilots, downloads, and unmatched
checks. Seeded random-priority candidates are merged into one bounded global
pilot; each phase retains its repeatable-read snapshot. Connection loss still
fails explicitly and leaves incomplete artifacts.

Live first, middle, last, and NULL-person batch counts returned 3,478, 3,726,
2,350, and zero rows in 0.44, 1.55, 1.04, and 0.02 seconds, respectively. Their
plans used indexes without scanning the full raw table. All 63 tests passed in
an isolated KLC test directory, including integration tests. These checks do not
establish completion of the new extraction.

The remote script was backed up before replacement under
`logs/malawi_restart_backup_20261002T214903Z/`; other remote edits were preserved.

## Batched worldwide coverage

The replacement worldwide job runs sequentially on KLC and saves cumulative
counts after each successful ID range. Distinct-person counts are additive
across these disjoint ranges; missing person IDs have a separate final batch.
The first range's live WRDS plan uses `individual_positions_user_id_idx`.
Only aggregates are saved; no individual position records are downloaded.

At the morning Malawi restart check, four worldwide batches had been saved: 7,235,667
position records and 1,930,400 globally distinct people within the processed
ranges. Batch five was running. These are partial counts, not worldwide totals.

Results and checkpoint:
`/gpfs/kellogg/proj/cxv7409/revelio_playground/results/country_coverage_20261002T152311370265Z/`.
If interrupted, resume with:

```sh
./klc run python scripts/country_coverage.py \
  --schema revelio_individual --table individual_positions \
  --country-column country --person-column user_id \
  --resume /gpfs/kellogg/proj/cxv7409/revelio_playground/results/country_coverage_20261002T152311370265Z
```

Final `countries.csv` and `summary.json` are written after all ranges and the
missing-ID batch finish. Batches use separate snapshots; source updates during
or between runs can affect the combined totals. The ID bounds are fixed when
the run starts. Full worldwide results are pending.

## Timeout investigation (October 2)

The country job failed at 23:51:05 CDT on October 1; Malawi failed at
01:02:04 CDT on October 2. Both logs report `could not receive data from
server: Connection timed out` and `SSL SYSCALL error: Connection timed out`.
These were KLC-to-WRDS database connection failures, not Mac-to-KLC SSH failures.
No other queries for this WRDS user were active during the diagnostic check.

The installed WRDS client inherited Linux TCP keepalive defaults: first probe
after 7,200 seconds, then nine probes spaced 75 seconds apart. This roughly
two-hour detection window is consistent with the failures. A dropped silent
network connection is the leading explanation; identifying the responsible
firewall, network hop, or server requires infrastructure logs. This is not proof
of a specific firewall timeout. The server's current statement timeout is 48
hours; Malawi explicitly sets six hours. Neither matches these failures.

Both positions tables have planner estimates of about 1.83 billion rows.
Country coverage uses a full-table aggregation; Malawi's raw count joins raw
positions to selected structured positions. Long-running queries expose the
connection to extended periods without result traffic. The preview's first
failure was different: an explicit 60-second statement timeout.

The connection helper now preserves WRDS defaults and requests TCP keepalives
after 30 seconds, repeated every 30 seconds, with nine missed probes tolerated.
Its 30-second connect timeout limits connection establishment only. Keepalives
can help with idle network expiry, but cannot guarantee recovery from outages
or make expensive SQL faster. Replacement jobs are listed above; the original
failed job records and artifacts are preserved.

A synthetic-ID `EXPLAIN` showed that the raw-position null-safe join chose a
parallel full-table scan, while equality chose indexed position-ID lookups.
The raw selection now separates NULL and non-NULL person IDs into disjoint
`UNION ALL` branches, preserving matching semantics and duplicates. The plan
comparison used only ID zero, not the saved cohort; the full-cohort plan and
runtime remain unverified. Country coverage still requires a global aggregation.

Malawi retained its 258,626-person cohort, position pilots, and incomplete
estimate under `results/malawi_estimate_20261002T032128315901Z/`. The position
estimate counted 805,829 rows. No full Malawi data directory was created.
