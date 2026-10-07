# Methodology: Hong Kong data inventory and migration replication (milestone 1)

This milestone builds and validates the measurement pipeline only. It produces
an inventory, coverage diagnostics, a quarterly person panel, migration
classifications, and an approximate replication of Kwan, Tang, and Wong (2024).
It does not estimate regressions, produce substantive figures, or make policy
claims. Retention, multinational decomposition, and policy analysis wait until
these measurements have been inspected.

Every rule below is set in [`config/analysis.yml`](../config/analysis.yml) or
[`config/title_taxonomy.yml`](../config/title_taxonomy.yml); changing either
file changes the run fingerprint.

## Inputs and run records

- **Extract.** The completed KLC download `data/hong_kong_20261004T140024976790Z/`:
  24 Revelio products plus the frozen `people_cohort`. The cohort is everyone
  with a Hong Kong profile location or any historical Hong Kong position, with
  their full available histories. Raw files are only read.
- **Immutability.** Stage 00 records every raw file's path, size, and
  modification time, plus a SHA-256 content hash. Every stage compares the listing
  at start and end. Stage 05 re-hashes all contents. Any change fails the run.
- **Fingerprints.** `run/<stage>.json` records the configuration and taxonomy
  SHA-256, the input manifest and listing hashes, a code hash, and DuckDB
  settings and version. It also lists outputs with row counts and bytes. A stage
  refuses to run on upstream outputs produced with different configuration,
  inputs, or bucket count.
- **Processing.** DuckDB with one thread and a 6 GB memory limit by default.
  Disk-backed intermediate databases and spilling are capped by
  `max_temp_directory_size`. Users are split into disjoint hash buckets, which
  bounds memory without changing results. Writing stages refuse to start below
  `storage.min_free_gb`.

## Stages

| Stage | Purpose | Main outputs (under the work root) |
|---|---|---|
| `00_inventory` | Manifest reconciliation, schemas, missingness, keys, duplicates, joins, absent fields | `docs/data_dictionary.md`, `output/diagnostics/inventory_*.csv`, `inventory.json` |
| `01_clean` | Deduplicate, quarantine, join titles, lookups, and profiles; apply title rules | `data/derived/positions_clean/`, `users_clean/`, `positions_quarantine.parquet` |
| `02_panel` | Quarter-end person-quarter panel for each end-date rule | `data/derived/person_quarter/<rule>/` |
| `03_diagnostics` | Coverage and location missingness | `output/diagnostics/data_coverage_by_year.csv`, `location_missingness.csv`, `title_rule_audit.csv` |
| `04_migration` | Hong Kong spells and persistence-confirmed transitions (full history) | `data/derived/migration/`, `output/tables/migration_transitions_by_quarter.csv` |
| `05_replication` | Endpoint and window-event replication; inspection sample | `output/tables/replication_summary.csv`, `data/derived/person_quarter_sample.parquet` |

Generated data and outputs are ignored by Git. The data dictionary is
regenerated from the extract rather than edited.

## Cleaning

- **Identifiers.** Identifiers stay strings throughout. Position IDs are signed
  64-bit values, and some exceed 2^63 in magnitude.
- **Duplicates.** Row identity is a 64-bit hash of the projected columns.
  Exact duplicate rows collapse to one. Every row of a key with conflicting
  contents is quarantined *before* any join. This rule applies to positions,
  raw titles (`position_id`, `user_id`, `title_raw`), profiles, role lookups, and
  the cohort. All joins are then on unique keys, and row counts are asserted
  unchanged after each join.
- **Raw titles.** A raw title is used only when the raw row's `user_id` matches
  the position's. Otherwise the position keeps a `title_status` of
  `no_raw_row`, `raw_user_mismatch`, `blank_title`, or `conflicting_raw_key`.
- **Quarantine.** These positions are excluded from the panel and written to
  `positions_quarantine.parquet` with a reason:
  - missing key;
  - user not in the cohort;
  - undated (no start or end);
  - missing start date;
  - start before 1950-01;
  - start after the cutoff month;
  - end before start;
  - conflicting duplicate key.

  Start dates are never invented.

## Dates

- **Month level.** Dates are month-level (day 1 in the source); days are ignored.
  A recorded end month is the last month worked (inclusive).
- **Cutoff.** The common cutoff is **2026-08-31**, the last observed profile
  refresh. Panel quarters run from 1950Q1 to the last complete quarter,
  **2026Q2**. 2026Q3 contains the cutoff. Coverage diagnostics report it as
  partial, measured in the cutoff month. It never enters complete-quarter results.
- **Missing end dates.** Two rules, each producing a full panel:
  - `carry_to_cutoff` (primary): the spell lasts to 2026-08.
  - `cap_at_last_refresh` (sensitivity): the spell lasts to the month of the
    person's `updated_dt`, and no later than the cutoff. This is strict: a May
    2026 refresh ends the spell after 2026Q1, because employment at the end of
    June is not observed.
- **No interpolation.** Gaps are never interpolated in this milestone.

## Quarterly panel

- **Quarter-end activity.** A spell is active in quarter *q* if it covers *q*'s
  last month (March, June, September, or December). A spell that starts and
  ends between two quarter ends produces no observation. A move within a quarter
  is therefore recorded at the destination.
- **Primary position.** Among positions active at the same quarter end:
  1. positions matched by a title rule rank last;
  2. then the most recent start month;
  3. then `position_id` in ascending *string* order as a deterministic
     tie-breaker.

  No confidence, hours, or employment-type information exists, and none is
  invented.
- **Title rules.** Rules downrank clearly identified advisory, board
  (non-executive, supervisory, trustee, observer, governor), part-time, and
  internship titles. Titles are lower-cased and whitespace-collapsed, and
  "non-executive" and 非執行 are normalized first, so they never match
  executive patterns.

  Exclusions remove finance "trustee services" jobs, board secretaries, and
  combined executive titles (CEO, managing director, executive director,
  執行董事). Ambiguous titles are deliberately unmatched: "Advisor", "Financial
  Advisor", "Senior Advisor", "Chairman", 董事長, "Trainee", "Volunteer", and
  "Adjunct". Each position keeps every matched rule id. The stage 03 audit lists
  the top titles per rule.
- **Diagnostics per row.** Each row keeps:
  - number of active positions, and how many are downranked, in Hong Kong, or
    missing a country;
  - distinct countries and a conflict flag;
  - alternative countries of non-primary positions;
  - whether any active position is in Hong Kong;
  - whether downranking changed the primary position or its country.
- **Profile fields.** Each row also carries the profile country, the refresh
  date, and the refresh quarter.

## Location specifications

Hong Kong status uses the `country` field equal to `Hong Kong`. Macao, mainland
China, and metro or city text do not set status. Rows with a Hong Kong metro
area but a non-Hong Kong country are counted as a diagnostic.
`remote_suitability` describes the job, not residence, and is never used.

| Specification | Location of a position row | Unknown when |
|---|---|---|
| `position_with_profile_fallback` (primary) | Primary position's country; if missing, the profile country | Both are missing, or no row exists |
| `position_only` | Primary position's country | It is missing, or no row exists |

- **Fallback timing.** The profile country is a single current snapshot. Each
  fallback row records its timing: `snapshot` (the refresh quarter), `backcast`
  (earlier), or `forwardcast` (later).
- **Gaps.** Fallback applies only when an active primary position lacks a
  country. It never fills quarters without an active position.
- **Profile-only people.** People without any valid dated position get one
  `profile_snapshot` row in their refresh quarter if that quarter is complete,
  for the fallback specification only. People who refreshed in 2026Q3 get no row
  and are counted separately. No employment history is manufactured.

## Migration classification

For each specification and end-date rule, known Hong Kong (H) / non-Hong Kong
(N) quarters are split into **blocks** of consecutive known quarters. Any
unknown quarter starts a new block: a missing location or a quarter without an
active position. Within a block, consecutive equal statuses form **runs**.

**Contiguous Hong Kong spells** are the H runs. Each records its length, what
precedes and follows it (`record_start`/`record_end`, `non_hk`, `unknown_gap`),
and censoring flags.

**Persistence-confirmed transitions** (k = 1, 2, 4 quarters), with horizon *T*:

- **Confirmed status.** The first run of each block sets the confirmed status.
  The person's first observation is left-censored and is never an entry or exit.
- **Confirmed move.** A run of the other status lasting at least k quarters
  (counting only quarters up to *T*) confirms a move. The move is dated to the
  run's first quarter and becomes the confirmed status.
- **Shorter runs** of the other status are one of:
  - an **excursion**, if the person returns within the block (the confirmed
    status is not reset);
  - **unconfirmed before a gap**, if a gap follows;
  - an **unconfirmed terminal move**, if the record or horizon ends. This is
    censored, not a departure.
- **Gap changes.** When the confirmed status at the end of a block differs from
  the first status of the next block, the change is recorded as an undated
  `gap` transition. It is never counted as a migration event.
- **Record ends.** The end of a record is censoring, not departure.
- **Attributes.** Each transition records:
  - origin and destination countries;
  - location source and fallback timing at both ends;
  - same-employer status at the ultimate-parent level, and separately at the
    `rcid` level (missing employer IDs give `unknown`);
  - spell type: an entry is `first` if no earlier Hong Kong quarter exists,
    otherwise `return`; an exit is `first` if no earlier exit or gap exit
    exists, otherwise `return`.

Stage 04 uses the full history (*T* = 2026Q2). Stage 05 recomputes transitions
with *T* equal to the window end, so persistence never looks beyond the
replication endpoint.

## Replication (approximate)

Kwan, Tang, and Wong (2024, Hong Kong Economic Policy Green Paper) report that
between pre- and post-pandemic dates:

- 255,911 LinkedIn users stayed in Hong Kong;
- 31,835 entered;
- 26,836 departed (net +4,999).

Table 3 splits these by same versus different company. The paper does not publish
its classification code, its exact dates, or its handling of concurrent or
undated positions. These estimates are therefore approximate. They are a
**retrospective reconstruction from the 2026 extract**, not a recreation of the
paper's October 2023 snapshot.

- **Windows.** Primary **2019Q4 to 2023Q3**; sensitivity **2018Q4 to 2023Q3**.
  Counts are unweighted people.
- **Endpoint classification** uses the status at the first and last window
  quarters. Both must be known.

  | Class | Status at start | Status at end |
  |---|---|---|
  | stayed | H | H |
  | entered | N | H |
  | departed | H | N |
  | outside both | N | N |

  Stayers are split into continuous Hong Kong, Hong Kong with unknown quarters,
  and round trips out (any N quarter in between). "Outside both" splits into
  round trips in versus no Hong Kong quarter. People with an unknown endpoint are
  reported as unclassified, by which endpoint is missing. Endpoint same-company
  status compares the primary employer's ultimate parent at the two endpoints;
  `rcid`-level status is reported too. Profile-location reliance at either
  endpoint is counted.
- **Window events** count transitions in the window (start < event quarter ≤
  end), confirmed with the window end as horizon. Rows include:
  - entries, exits, and the net;
  - undated gap transitions;
  - people censored at the window end;
  - cross-tabulations of endpoint classes against confirmed events, for example
    departures observed only through a gap.
- **Benchmarks.** Narrative counts are attached to the endpoint measures, and
  Table 3 cells to the same-company measures. The paper's Table 3 cells sum to
  26,896 departures, 32,911 entries, and 257,976 stayers, which do not match its
  narrative counts. These figures are preserved as published in
  `benchmark_consistency` rows and not reconciled.
- **Unavailable.** Age-group results are marked unavailable: there is no age or
  birth year, and age is not estimated from education dates in this milestone.
  THE-rank comparisons are also unavailable: the rankings are absent.

## Inspection sample

A reproducible sample of up to 1,000 panel participants (people with at least
one row under the primary end rule). Participants are ordered by
`sha256(salt || ':' || user_id)` and the first 1,000 are taken. The sample
exports their complete histories under both end rules:

- every panel row;
- explicit `unobserved_gap` rows between a person's first and last observation;
- per-quarter transition flags for each specification and k.

Selection does not depend on bucket count or input order. The selected-ID
SHA-256 is saved in `person_quarter_sample.json`.

## Validation

`tests/` runs with `python -m unittest discover -s hk_revelio/tests` and needs
`requirements.txt`. It covers:

- **Synthetic histories, stages 00 to 05 end to end:**
  - within-quarter moves and inclusive end months;
  - concurrent jobs, title downranking, string tie-breaks, and conflicting
    locations;
  - undated and after-cutoff spells;
  - stale profiles and the refresh cap;
  - profile fallback timing;
  - profile-only people in complete and partial quarters;
  - short excursions, persistent moves, returns, unknown gaps, and left and
    right censoring;
  - horizon-restricted confirmation;
  - large signed and unsigned 64-bit identifiers;
  - exact and conflicting duplicate keys, and lookup duplicates without row
    multiplication;
  - same-employer and unknown-employer transfers;
  - endpoint counts versus event counts.
- **Randomized check.** The SQL state machine is compared with an independent
  Python reference on 600 random histories with gaps, for k = 1, 2, 4 and two
  horizons.
- **Invariants:** unique person-quarter keys, manifest reconciliation failure,
  raw-file change detection, and identical samples across reruns and bucket
  counts.

## Known limitations

- **Cohort scope.** The cohort is Hong Kong-linked by construction, and
  downloaded workforce geography covers Hong Kong only. The files cannot measure
  global multinational footprints or global headcounts.
- **Retrospective data.** Histories are retrospective as of 2026. Positions
  added or edited after October 2023 change the 2019-2023 picture, and no
  position refresh timestamps exist to undo that.
- **Backcast profiles.** Profile locations are backcast for earlier quarters.
  Endpoint counts report how many classifications rely on them.
- **Open-ended spells.** Spells with missing end dates are not known to be
  current. The refresh-cap sensitivity bounds this.
- **Gaps.** Requiring known consecutive quarters undercounts dated moves that
  pass through job gaps. Those appear as undated gap transitions instead.
