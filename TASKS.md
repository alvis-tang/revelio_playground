# KLC tasks

Statuses last checked with `./klc status` on October 1, 2026 (America/Chicago).
Launch dates below use America/Chicago (CDT, UTC−05:00), converted from the UTC
timestamp in each KLC job ID. Statuses are a snapshot; use the commands below
to check current progress.

| KLC task number (job ID) | Launch date and time (CDT) | Task description | Status | Check logs |
| --- | --- | --- | --- | --- |
| `20261002T023459-0b3b81` | 2026-10-01 21:34:59 | Count historical positions and distinct people by country from `revelio_individual.individual_positions`. | Running | `./klc logs 20261002T023459-0b3b81` |
| `20261002T025453-64ba9e` | 2026-10-01 21:54:53 | Retrieve a 20-row job posting preview with descriptions and structured metadata (first attempt). | Failed | `./klc logs 20261002T025453-64ba9e` |
| `20261002T025657-e21631` | 2026-10-01 21:56:57 | Retrieve a 20-row job posting preview with descriptions and structured metadata (retry). | Complete | `./klc logs 20261002T025657-e21631` |
| `20261002T032127-aa5075` | 2026-10-01 22:21:27 | Estimate Malawi extraction storage, then download if accessibility checks and the 20 GB gate pass (`estimate --download-if-safe`). | Running | `./klc logs 20261002T032127-aa5075` |

The command is `./klc logs JOB_ID` (plural). To check one job's current status,
run `./klc status JOB_ID`; run `./klc status` to list all recorded jobs.
