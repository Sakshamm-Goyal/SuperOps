# Attribution and reuse record

GreenOps Verify is a working project name for this planning pack. Concept inspiration: [niksm7/GreenOps](https://github.com/niksm7/GreenOps), reviewed at `db38811fb653631892e6cbbe1275793bd9906858`. The supplied blueprint identifies Aishwarya Nathani and Nikhil Mankani as the original creators. This project is not presented as their submission, award, or affiliated product.

Confirmed by the user on 16 October 2026: GreenOps is third-party inspiration; build our own implementation. Independently author code, prompts and product visuals. No upstream source or asset reuse is part of this plan, so obtaining reuse permission is not a prerequisite for the selected approach. The inspected public tree has no LICENSE/NOTICE grant; public visibility is not a blanket reuse license. See the [GitHub licensing explanation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) and the team's static upstream review (kept local, not published). Do not copy upstream source, prompts, templates, screenshots, credentials or submission wording. Any later request to reuse material would be a new scope decision requiring the relevant rights and event checks.

Meterless H-MEM is **vendored** (16 Oct 2026) from [Meterless/Meterless](https://github.com/Meterless/Meterless) `engines/hmem/reference/src` at `0aa7417ba5c826396d91e891328be78c45e6fbf6`, under Apache-2.0. The license is kept at `memory-sidecar/vendor/hmem/LICENSE`. There is no upstream NOTICE file. Three modifications are marked in source and listed in [memory-sidecar/PATCHES.md](memory-sidecar/PATCHES.md), with the exact diff in `memory-sidecar/vendor/hmem.patch`. Per-file SHA-256 values are in `memory-sidecar/reference-manifest.json`. Other libraries require their own dependency/license inventory. No project-wide license has been selected on behalf of the team in this task.

| Material | Current treatment | Evidence still needed |
|---|---|---|
| Original GreenOps | Third-party concept inspiration only, confirmed by user | No reuse permission needed for the selected no-copy plan; revisit only if the user changes scope |
| User-supplied planning pack | Retained locally | Confirm redistribution permission before publishing attachments |
| Organizer guides | Local reference | Link official sources; do not republish full guides automatically |
| Meterless H-MEM reference | Vendored with 3 attributed patches | Done: manifest, license, patch list and diff |
| Synthetic datasets | Independently generated (`scripts/generate_data.py`, `experiments/support/generate_cases.py`) | Done: seeds, hashes and counts in `data/manifests/` and `experiments/support/manifest.json` |
| Python/Node libraries | Locked in `uv.lock`; sidecar has no npm runtime dependencies | Run a license inventory (e.g. pip-licenses) before publication |

Attribution does not resolve event eligibility. Track choice, pre-event disclosure and third-party reuse are separate questions.
