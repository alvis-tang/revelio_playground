# KLC tasks

Statuses last checked on October 2, 2026 (America/Chicago), using the remote status command over SSH.
Launch dates below use America/Chicago (CDT, UTC−05:00), converted from the UTC
timestamp in each KLC job ID. Statuses are a snapshot; use the commands below
to check current progress.

| KLC task number (job ID) | Launch date and time (CDT) | Task description | Status | Check logs |
| --- | --- | --- | --- | --- |
| `20261002T023459-0b3b81` | 2026-10-01 21:34:59 | Count historical positions and distinct people by country from `revelio_individual.individual_positions`. | Failed: WRDS connection timeout | `./klc logs 20261002T023459-0b3b81` |
| `20261002T025453-64ba9e` | 2026-10-01 21:54:53 | Retrieve a 20-row job posting preview with descriptions and structured metadata (first attempt). | Failed | `./klc logs 20261002T025453-64ba9e` |
| `20261002T025657-e21631` | 2026-10-01 21:56:57 | Retrieve a 20-row job posting preview with descriptions and structured metadata (retry). | Complete | `./klc logs 20261002T025657-e21631` |
| `20261002T032127-aa5075` | 2026-10-01 22:21:27 | Estimate Malawi extraction storage, then download if accessibility checks and the 20 GB gate pass (`estimate --download-if-safe`). | Failed: WRDS connection timeout during raw-position count | `./klc logs 20261002T032127-aa5075` |

The command is `./klc logs JOB_ID` (plural). To check one job's current status,
run `./klc status JOB_ID`; run `./klc status` to list all recorded jobs.

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
or make expensive SQL faster. Failed jobs have not been restarted.

A synthetic-ID `EXPLAIN` showed that the raw-position null-safe join chose a
parallel full-table scan, while equality chose indexed position-ID lookups.
The raw selection now separates NULL and non-NULL person IDs into disjoint
`UNION ALL` branches, preserving matching semantics and duplicates. The plan
comparison used only ID zero, not the saved cohort; the full-cohort plan and
runtime remain unverified. Country coverage still requires a global aggregation.

Malawi retained its 258,626-person cohort, position pilots, and incomplete
estimate under `results/malawi_estimate_20261002T032128315901Z/`. The position
estimate counted 805,829 rows. No full Malawi data directory was created.
