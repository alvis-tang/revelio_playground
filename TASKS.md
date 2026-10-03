# KLC tasks

Hong Kong statuses last checked on October 3, 2026 (America/Chicago), using the
remote status command over SSH. Earlier rows retain their October 2 snapshots.
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
| `20261003T235630-408292` | 2026-10-03 18:56:30 | Estimate all Hong Kong-linked products, then download if access checks and the 20 GB gate pass. | Running: connected to WRDS; selecting Hong Kong cohort | `./klc logs 20261003T235630-408292` |

The command is `./klc logs JOB_ID` (plural). To check one job's current status,
run `./klc status JOB_ID`; run `./klc status` to list all recorded jobs.

## Hong Kong download

Job `20261003T235630-408292` is running in a detached tmux session on KLC.
It connected to WRDS and started selecting people with Hong Kong residence or
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
