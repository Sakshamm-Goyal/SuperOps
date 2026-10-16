# Pre-existing work declaration

Status: inventory updated 16 October 2026, before the build window opens (22 October 2026, 00:00 UTC). Reconcile this file with the actual event submission form and organizer guidance; it is not an eligibility ruling.

**Important.** On 16 October 2026 the user explicitly instructed that the full application be implemented end to end that day, before the event. Under the event FAQ, "work committed before the build window opens is not eligible, except for clearly declared pre-existing components." **Everything listed below as created on 16 October is pre-existing product code and must be declared in the submission form.** It must not be presented as event-window work. The team should obtain an organizer ruling on how this affects Track 02 versus Wildcard [Tinkerer], where only new work is scored. See [docs/HACKATHON_RULES.md](docs/HACKATHON_RULES.md) §7 and [docs/DECISIONS_AND_RISKS.md](docs/DECISIONS_AND_RISKS.md) ADR-18.

## Inventory

| Component | Created | Use and disclosure |
|---|---|---|
| Six supplied event guides (workspace root) | Before 16 Oct (supplied by user) | Organizer guidance; retain source names; not our authorship |
| Five GreenOps Verify files in `Refer-Docs/` | Before 16 Oct (supplied by user) | Concept, blueprint and handoff; planning reference |
| Planning documentation pack (README, AGENTS, AGENT, `.cursor/rules`, `docs/*`) | 16 Oct; local git baseline commit `10a2cfd` | Research, architecture, contracts, backlog and test plans |
| **Application implementation** (`greenops/`, `experiments/`, `sandbox/`, `scripts/`, `sql/`, `migrations/`, `config/`, `tests/`, `Makefile`, `Dockerfile`, `docker-compose.yml`, `pyproject.toml`, `uv.lock`, `.env.example`) | **16 Oct, pre-event**, authored with Claude Code (not Cursor) at the user's instruction | Must be declared as pre-existing product code. Development tool used: Claude Code; the event's Cursor requirement (R08) is **not** satisfied by this work |
| **Memory sidecar** (`memory-sidecar/src`, tests, README, PATCHES) | **16 Oct, pre-event** | Our wrapper; declare as pre-existing |
| Vendored Meterless H-MEM reference (`memory-sidecar/vendor/hmem/`) | Upstream `0aa7417ba5c826396d91e891328be78c45e6fbf6` (2026-07-22); vendored 16 Oct | Apache-2.0 third-party code with three marked, attributed patches (`memory-sidecar/PATCHES.md`, `vendor/hmem.patch`); not our authorship |
| Synthetic data (`data/generated/`, `data/manifests/support-demo-data-v1.json`) and support cases (`experiments/support/dev/`, `manifest.json`) | 16 Oct; deterministic generators, seeds in the manifests | Prepared data: declare. Holdout cases live only in the evaluator directory (`.evaluator/`, git-ignored); the same author wrote both partitions (limitation) |
| Local evidence artifacts (`evidence/eval/*`) | 16 Oct | Sample-mode results (scripted roles, synthetic data); not sponsor or model evidence |
| niksm7/GreenOps, `master` `db38811fb653631892e6cbbe1275793bd9906858` | Exists externally | Concept inspiration only; no upstream code, prompts or assets copied |
| Frameworks and libraries | External | Exact versions in `uv.lock` and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |

## What was not done pre-event

No sponsor account was accessed. No real Zetaris query, NVIDIA model or embedding call, GCP action, deployment, publication, remote push or submission took place. All connected sponsor tests are BLOCKED pending credentials. The repository is local only, and nothing was backdated or rewritten.

## Provenance at submission

Include this declaration, the baseline commit (`10a2cfd`, planning only), the pre-event implementation commit(s) created on 16 October and [NEW_WORK.md](NEW_WORK.md), which lists only work actually done inside the window with dated commits. Commit time is one provenance signal; it does not prove eligibility.
