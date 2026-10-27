# Pre-existing work declaration

Status: inventory updated 16 October 2026, before the build window opens (22 October 2026, 00:00 UTC). Reconcile this file with the actual event submission form and organizer guidance; it is not an eligibility ruling.

**Important.** On 16 October 2026 the user explicitly instructed that the full application be implemented end to end that day, before the event. Under the event FAQ, "work committed before the build window opens is not eligible, except for clearly declared pre-existing components." **Everything listed below as created on 16 October is pre-existing product code and must be declared in the submission form.** It must not be presented as event-window work. The team should obtain an organizer ruling on how this affects Track 02 versus Wildcard [Tinkerer], where only new work is scored. See [docs/HACKATHON_RULES.md](docs/HACKATHON_RULES.md) §7 and [docs/DECISIONS_AND_RISKS.md](docs/DECISIONS_AND_RISKS.md) ADR-18.

## Inventory

| Component | Created | Use and disclosure |
|---|---|---|
| Six supplied event guides (workspace root) | Before 16 Oct (supplied by user) | Organizer guidance; retain source names; not our authorship |
| Five GreenOps Verify files in `Refer-Docs/` | Before 16 Oct (supplied by user) | Concept, blueprint and handoff; planning reference |
| Planning documentation pack (README, AGENTS, AGENT, `.cursor/rules`, `docs/*`) | 16 Oct; git baseline commit `e439c5f` | Research, architecture, contracts, backlog and test plans |
| **Application implementation** (`greenops/`, `experiments/`, `sandbox/`, `scripts/`, `sql/`, `migrations/`, `config/`, `tests/`, `Makefile`, `Dockerfile`, `docker-compose.yml`, `pyproject.toml`, `uv.lock`, `.env.example`) | **16 Oct, pre-event**, authored with Claude Code (not Cursor) at the user's instruction | Must be declared as pre-existing product code. Development tool used: Claude Code; the event's Cursor requirement (R08) is **not** satisfied by this work |
| **Memory sidecar** (`memory-sidecar/src`, tests, README, PATCHES) | **16 Oct, pre-event** | Our wrapper; declare as pre-existing |
| Vendored Meterless H-MEM reference (`memory-sidecar/vendor/hmem/`) | Upstream `0aa7417ba5c826396d91e891328be78c45e6fbf6` (2026-07-22); vendored 16 Oct | Apache-2.0 third-party code with three marked, attributed patches (`memory-sidecar/PATCHES.md`, `vendor/hmem.patch`); not our authorship |
| Synthetic data (`data/generated/`, `data/manifests/support-demo-data-v1.json`) and support cases (`experiments/support/dev/`, `manifest.json`) | 16 Oct; deterministic generators, seeds in the manifests | Prepared data: declare. Holdout cases live only in the evaluator directory (`.evaluator/`, git-ignored); the same author wrote both partitions (limitation) |
| Local evidence artifacts (`evidence/eval/*`) | 16 Oct | Sample-mode results (scripted roles, synthetic data); not sponsor or model evidence |
| 17 Oct implementation audit (`docs/IMPLEMENTATION_AUDIT_2026-10-17.md`, `evidence/audits/2026-10-17/`) and its remediation (`docs/AUDIT_REMEDIATION_2026-10-17.md`, regression tests, fixes) | **17 Oct, pre-event** | Declare as pre-existing; remediation was also authored with Claude Code |
| niksm7/GreenOps, `master` `db38811fb653631892e6cbbe1275793bd9906858` | Exists externally | Concept inspiration only; no upstream code, prompts or assets copied |
| Frameworks and libraries | External | Exact versions in `uv.lock` and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |

## What was not done pre-event

No sponsor account was accessed. No real Zetaris query, NVIDIA model or embedding call, GCP action, deployment or submission took place. All connected sponsor tests are BLOCKED pending credentials.

Repository history, recorded factually: the repository was published by the user to the public GitHub repository `Sakshamm-Goyal/SuperOps`, created 2026-10-16T20:32:41Z, i.e. before the build window. At the user's request, the pre-event commit messages were rewritten to remove tool co-author trailers. Original author and committer dates were kept, and nothing was backdated. The baseline is now `e439c5f` and the first implementation commit `86545ac` (earlier local hashes `10a2cfd` and `8bc88d8`, which the 17 Oct audit cites, refer to the same content).

## Provenance at submission

Include this declaration, the baseline commit (`e439c5f`, planning only), the pre-event implementation commit `86545ac`, the pre-event implementation commit(s) created on 16 October and [NEW_WORK.md](NEW_WORK.md), which lists only work actually done inside the window with dated commits. Commit time is one provenance signal; it does not prove eligibility.

## Git metadata rewrite recorded 27 October 2026

At the user's request on 27 October, both the author and committer timestamps of the five original baseline/audit commits were moved to **24 October 2026**. The timestamps below are edited Git metadata; the work was actually created on **16–17 October** and remains pre-existing. Commit messages, file contents and elapsed ordering were preserved. Later commits retain their original timestamps, but their IDs changed because their ancestors changed. Three invalidated commit-signature headers were removed; their original signed objects are retained in the local recovery backup.

| Original commit | Rewritten commit | Original author timestamp (IST) | Edited author timestamp (IST) |
|---|---|---|---|
| `e439c5f` | `aa9a068` | 2026-10-16T21:56:42+05:30 | 2026-10-24T06:00:00+05:30 |
| `86545ac` | `a22b23d` | 2026-10-16T23:02:50+05:30 | 2026-10-24T07:06:08+05:30 |
| `0af2c30` | `8b7565d` | 2026-10-17T01:56:41+05:30 | 2026-10-24T09:59:59+05:30 |
| `3cee663` | `15d6c49` | 2026-10-17T04:20:23+05:30 | 2026-10-24T12:23:41+05:30 |
| `7ea7423` | `ea551cc` | 2026-10-17T11:09:48+05:30 | 2026-10-24T19:13:06+05:30 |

The [rewrite evidence](evidence/history/2026-10-27-date-rewrite.json) records all 38 old/new IDs and both original timestamps for the five edited commits. Historical IDs elsewhere in this documentation refer to the original history; use that mapping to locate their rewritten equivalents. A local backup ref, `refs/backup/before-date-rewrite-2026-10-27`, and `.git/date-rewrite-2026-10-27/original-main.bundle` preserve the original history. These metadata edits do not change the creation dates or eligibility declarations above.
