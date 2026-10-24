# Hackathon rules, evidence and decision gates

**Project:** GreenOps Verify  
**Reviewed:** 16 October 2026  
**Status:** Pre-event planning; no registration, organizer approval, sponsor access, implementation or submission is asserted by this document.  
**Owners to assign:** Team lead (rules), submission owner (packaging), sponsor owner (integration evidence).

This is the operational interpretation of the supplied event material and the live event page. The official rules control; this document does not grant eligibility or permission. Source documents are reference material, not authorization to create accounts, send messages, publish, upload or modify cloud infrastructure. The present task authorizes local documentation only.

## 1. Decisions to carry into implementation

1. **Prepare now; build during the eligible window.** Declare this planning pack and all other pre-event work. Do not delay committing old work merely to make it appear new.
2. **Provisional primary track: Track 02, The Agent That Can Explain Why.** The intended work is a sourced investigation that challenges a cheap-looking cloud change, validates a revised candidate and produces a usable decision record.
3. **Use real Zetaris and Meterless integrations and develop in Cursor.** These are requirements, not optional bonus-point features. NVIDIA is conditional on useful contribution under rule 5.2.
4. **Implement independently, as confirmed by the user.** GreenOps is third-party inspiration only; no upstream code, prompts or assets are reused. Organizer track guidance for the pre-event concept/planning remains separate from this settled implementation choice.
5. **Submit a complete working package early.** Internal target: 27 October, 18:00 UTC / 23:30 Asia/Kolkata. Official submission cutoff: 27 October, 23:45 UTC / 28 October, 05:15 Asia/Kolkata.

Basis: official rules §§3–6; supplied FAQ §§4–7; supplied handoff §§1, 12 and 15. See [source register](#10-source-register).

## 2. Calendar with local conversions

All controlling deadlines are UTC. Asia/Kolkata is UTC+05:30; a new local calendar date does not extend an event deadline. Dates below are 2026.

| Milestone | UTC | Asia/Kolkata | Source and confidence |
|---|---|---|---|
| Registration opens | 14 Aug, 00:00 | 14 Aug, 05:30 | Live event Key dates; guides agree |
| Zetaris Data Day | 12 Oct; time not specified | Exact local time unknown | Guides say recording is on HackOS; recording not accessed in this review |
| Build Day / Power Day | To be confirmed | To be confirmed | Local guides; check current HackOS announcement |
| Participant onboarding | 21 Oct, 12:00–13:30 | 21 Oct, 17:30–19:00 | Calendar §3 and Welcome §6; not independently verified in logged-in HackOS |
| Build opens | **22 Oct, 00:00** | **22 Oct, 05:30** | Expanded live rule 4.1 and guides agree |
| Registration: live page | 22 Oct, 23:59 | 23 Oct, 05:29 | Live event Key dates |
| Registration: supplied guides | 22 Oct, 23:45 | 23 Oct, 05:15 | FAQ §2, Calendar §§1/7, Welcome §5 |
| Registration: team operating cutoff | **Before 22 Oct, 23:45** | **Before 23 Oct, 05:15** | Conservative team deadline; register earlier if possible |
| Suggested integration checkpoint | 24 Oct, 16:00 | 24 Oct, 21:30 | Calendar §8 recommendation, not an event requirement |
| Team feature freeze | 26 Oct, 12:00 | 26 Oct, 17:30 | Project decision; not organizer policy |
| Team final validation | 27 Oct, 12:00 | 27 Oct, 17:30 | Project decision, consistent with Calendar §8 |
| **Team submission target** | **27 Oct, 18:00** | **27 Oct, 23:30** | Handoff §12; allows 5h45m before official cutoff |
| **Submissions close** | **27 Oct, 23:45** | **28 Oct, 05:15** | Expanded live rule 4.1, live Key dates and all supplied guides agree |
| Judging opens: live Key dates | 27 Oct, 00:00 | 27 Oct, 05:30 | Contradicts supplied guides; unresolved |
| Judging opens: supplied guides | From 28 Oct, described as immediately after close | Exact local start unknown | Calendar §4 / FAQ §8; no precise clock time given |
| Results | 6 Nov, 16:00 | 6 Nov, 21:30 | Live Key dates and guides agree |

The advertised “144 hours” is rounded: the stated start and end span **143 hours 45 minutes**. Use the timestamps, not a six-day duration calculation. Do not infer a judging start from the inconsistent calendar.

## 3. Compliance matrix

Nothing in the status column is a claim that the team has completed a requirement. The implementation team fills the evidence reference and records an owner before submission.

| ID | Requirement / guidance | Classification and source | GreenOps Verify proof required | Current state |
|---|---|---|---|---|
| R01 | Participants at least 16 when building begins; one account each; organizer/judging-sponsor employees excluded from cash prizes | Official §§1.1–1.3; FAQ §2 | Team lead checks eligibility privately; no identity documents in repository | Unverified |
| R02 | One to five people; each participant belongs to one team | Official §§2.1/2.3; FAQ §3 | Final roster and responsibilities | User confirmed 4–5 builders; exact roster and one-team membership still unverified |
| R03 | First created submission locks team composition | Official §2.2; FAQ §3 | Finalize roster before creating submission; do not use a draft submission to test the form casually | Pending |
| R04 | Exactly one primary track; may change before deadline; cross-track relevance not double-scored | Official §§3.2–3.4; Welcome §4 | Selected track recorded in README, deck and submission | Proposed Track 02 |
| R05 | Build between published start/end; declare prior components | Official §§4.1–4.3/5.4; FAQ §5 | Baseline commit, dated declarations and new-work commit log | **At risk:** full implementation built pre-event on 16 Oct at the user's instruction and declared in PREEXISTING.md; organizer ruling needed (RISK-17) |
| R06 | Zetaris must be integrated | Official §5.1; Welcome §8 | Real bounded query across independent sources; source IDs and query receipt; access/setup instructions | Adapter and templates built; live tests BLOCKED (no credentials) |
| R07 | Meterless must be integrated | Official §5.1; Welcome §8 | Real H-MEM reference use; persistence and recall evidence; version and notices | Vendored engine in use; restart/recall tests pass with hash embedder; semantic embeddings BLOCKED |
| R08 | Cursor used for development | Official §5.1; Welcome §8 | Honest development log/screenshots linked to actual new code, with secrets removed | **Not met** by the pre-event code (built with Claude Code); in-window work must be done in Cursor |
| R09 | NVIDIA contributes where appropriate | Official §5.2; Welcome §8 | Tested model/tool role and results if used; factual explanation if unavailable/not used | Candidate integration; not established |
| R10 | Languages/frameworks/models/clouds are open choice, including closed APIs; AI-generated code allowed and team accountable | Official §§5.3/5.5; FAQ §5 | Tested version lock; original/reused/generated provenance and dependency notices | Architecture decision pending implementation |
| R11 | Demo video 1–4 minutes, including core workflow and Zetaris/Meterless role | Official §6.1; Welcome §9 | Accessible final video, measured duration, real run IDs and correct labels | Storyboard only |
| R12 | Deck covers problem/users, solution, architecture, stack, sponsors/unique use, visuals and future work | Official §6.2; Welcome §9 | Final deck matches actual product and evidence | Outline only |
| R13 | GitHub repository includes all source, README setup/usage/dependencies; Colab links if used | Official §6.3; FAQ §7 | Clean checkout successfully reproduces documented path; judge access checked | Application exists locally; clean-checkout run on a second machine not done; no remote repository |
| R14 | Explain Zetaris, Meterless, Cursor, NVIDIA and distinctive sponsor use | Official §6.4; Welcome §9 | Integration evidence table with source revisions and screenshots/receipts | Planned |
| R15 | Submit through HackOS before cutoff; declare pre-existing product code | FAQ §7; Calendar §3 submission section | Receipt, timestamp, links, exact repository revision; pre-existing declaration included | Not submitted |
| R16 | Keep credentials out of source, examples, screenshots and logs | Guide rule: Welcome §8, FAQ §7 | Placeholder-only environment example, secret scan, redaction review | Must verify after build |
| R17 | Use permitted accessible data; avoid real personal/confidential records; declare prepared data | Guide guidance: FAQ §5; Solutioning §§5–7/12 | Data manifest with origin, licence/use basis, row counts, versions and synthetic labels | Synthetic samples planned |
| R18 | Useful output, visible critique/revision, bounded execution and runnable examples | Guide expectations: Welcome §§2–3; Solutioning §§8–14 | End-to-end accepted and rejected cases, traces, failure evidence, report | Acceptance plan only |
| R19 | Team retains rights to its work; event receives promotional rights on submission | Official §§9.1–9.3; FAQ §9 | Only owned/permitted content in public materials; review disclosure scope before submission | Not submitted |
| R20 | Schedule may change; organizer disqualification is final | Official §10; FAQ §10 | Refresh rules at onboarding, build start and submission; record dated differences | Last reviewed 16 Oct |

**Meaningful-integration quality gates are project choices, not extra organizer rules.** The event does not publish a minimum number of Zetaris data sources, memory records, agents or tests. This project requires at least two physically independent sources through Zetaris and a Meterless recall that affects a later decision because those make sponsor value testable. A logo, dependency import or simulated response is not our integration evidence.

## 4. Track decision and prior-work boundary

### Recommended track rationale

Track 02 matches the central question: **“Which cloud change can we justify, what evidence would make it unsafe, and what happened when we tested it?”** The decisive output is an evidence-backed recommendation with rejected alternatives, limitations and verification. Track 01 would emphasize reconciling fragmented sources; Track 03 would emphasize decision architecture. Those are supporting capabilities, not additional entries.

This recommendation is conditional, not an eligibility ruling. The public bonus-track description includes existing projects, prototypes **or concepts**. The existence of prior GreenOps work and this pre-event planning pack therefore warrants a specific organizer ruling on the intended entry. The user has confirmed original implementation with no upstream code/assets reused. A later change to that choice would require separate rights and track reassessment. Only new work is scored in Wildcard. [Official track description](https://hackathon.genai.works/event/open-agent-hackathon-2026#tracks); supplied Solutioning §§6/19 and Handoff §1.

### Required provenance records

Maintain the following records without rewriting history:

| Record | What must be recorded |
|---|---|
| `PREEXISTING.md` | This planning pack and provided briefs; creation dates; upstream inspiration/revision; prior datasets; permitted reused files; owner/source; licence or permission; exact use |
| `ATTRIBUTION.md` | Actual authors of reused work; concept inspiration; permission/notice requirements; distinguish independent implementation from derivative |
| `NEW_WORK.md` | Capability, implementation commits/timestamps, test evidence, current limitations and which work was completed within the window |
| Baseline snapshot | Immutable pre-build revision and file inventory; no deceptive rebasing, squashing away provenance or backdating |
| Data manifest | Prepared date, source, usage basis, synthetic/real label, hash and exact subset |

The supplied handoff and current static repository review report no licence grant found in the inspected upstream tree. The confirmed plan uses concept inspiration only and independently authored implementation; do not copy upstream source, prompts, artwork, templates, screenshots or credential-bearing files. Concept inspiration can be credited without claiming authorship of the original product or its awards. Handoff §§1/15 is a proposed policy; it is not a licence or organizer decision.

General setup and sponsor-access preparation are encouraged by the supplied Calendar §3. That does not make prewritten product features eligible. Declare any experiments, data preparation or code completed early, regardless of whether it was committed. This turn produces only planning documents.

## 5. Judging and competitive priorities

| Criterion | Points | Our evidence focus |
|---|---:|---|
| Impact | 30 | One real operator decision; measured sandbox outcome; operational limitation and counterfactual baseline |
| Technical | 20 | Clean setup, real sponsor integration, deterministic constraints, approval binding, read-back and regression suite |
| Innovation | 15 | Evidence conflict → critic rejection → revised experiment → applicable memory on later run |
| Demo | 15 | Clear 3m45s narrative with visible evidence and an actual usable result |
| Product & UX | 10 | Operator can inspect why, compare a rejection, approve exact scope and understand final status |
| Sponsor tech | 10 | Zetaris supplies indispensable evidence; Meterless changes subsequent investigation; Cursor and any NVIDIA contribution documented |
| **Total** | **100** | Score evidence, not feature count |

At least three judges review an entry; ties use Impact then submission timestamp. Sources: official §7; supplied FAQ §8, Welcome §12, Solutioning §13. A polished demo and this evidence plan improve assessability; they cannot guarantee winning or a particular score. See [demo and submission plan](DEMO_AND_SUBMISSION.md).

## 6. Prize information and source conflicts

The live page and expanded rule §8 currently list **$13,000 cash + $7,000 in-kind**, up to $20,000 total. Track cash awards (first/second/third): Track 01 and Track 02 **$1,600/$1,200/$900** each; Track 03 **$1,500/$1,200/$900**; Wildcard **$1,000/$600/$400**. In-kind categories list NVIDIA Nemotron ($4,699 DGX Spark) and Cursor-built product ($2,301 credits). These are current advertised values, not guaranteed awards. [Live prizes](https://hackathon.genai.works/event/open-agent-hackathon-2026#prizes).

| Conflict | Supplied material | Live evidence reviewed 16 Oct | Operating decision |
|---|---|---|---|
| Registration deadline | 22 Oct 23:45 UTC | 22 Oct 23:59 UTC | Meet earlier time; request clarification |
| Judging opening | From 28 Oct, after close | Key dates: 27 Oct 00:00 UTC, before submission closes | Do not invent reconciliation; retain final submission cutoff and ask |
| Prize allocation | $15k cash/$5k in-kind; larger main-track awards | Expanded §8 and visible prizes: $13k/$7k | Use live values with date; recheck before public claims |
| Build length | “144 hours” | Rule 4.1 timestamps imply 143h45m | Use exact rule timestamps |
| Update channels | HackOS announcements; Discord mainly community | Rule 10.1 names page and Discord for schedule changes | Check HackOS, event page and official Discord announcements |
| Pre-event existing concept | Handoff proposes independent Track 02 | Wildcard description includes existing concepts | Organizer ruling remains pending; disclose all prior preparation |

Cash-payment timing, equal split absent an agreed written alternative, and recipient tax/local-charge responsibility are described in FAQ §§3/9 and official §8. No financial action is part of this planning task.

## 7. Unresolved questions and responsible next actions

| Question | Why it matters | Evidence required to close | Owner |
|---|---|---|---|
| Is this independent GreenOps-inspired concept eligible in Track 02 given pre-event planning? | Track eligibility and honest prior-work disclosure | Written organizer answer covering supplied prior materials | Team lead |
| Which registration/judging schedule is controlling? | Public/local discrepancy | Dated organizer clarification or corrected official page | Submission owner |
| Do current HackOS challenge pages add deliverables/constraints? | Logged-in challenge pages were not inspected here | Read current selected-track page and archive relevant requirement references | Submission owner |
| What sponsor workspace, credits, quotas and engine version are granted? | Public docs do not prove team access | Actual entitlement/setup details and successful authorized connection tests | Sponsor owner |
| What are final Build Day / Power Day times? | Local guides leave them unconfirmed | Current HackOS event announcement | Team lead |
| Does private GitHub judge access suffice, and what exact video/deck formats and size limits apply? | Public rule §6 gives components, not upload/access mechanics | Submission-form instructions or organizer answer | Submission owner |
| Does the in-kind competition have additional entry/eligibility steps? | Public prize names do not define complete criteria | Current sponsor-track/HackOS terms | Submission owner |

Do not treat silence as approval. Continue independent design and permitted preparation while these items remain open. Reuse permission is not an open prerequisite for the confirmed no-copy approach. Authenticated sponsor access and the organizer track clarification remain open.

### Draft organizer clarification — not sent

> We are planning GreenOps Verify, inspired by the public niksm7/GreenOps project. We will independently author our implementation and will not reuse the upstream code, prompts or assets. We have pre-event research, architecture documents and a proposed dataset/test plan, which we will declare. Does this qualify for Track 02, or should an existing concept enter Wildcard? Please also confirm the conflicting registration and judging dates, any selected-track requirements beyond public rule §6, judge repository-access requirements, and current sponsor-access instructions.

The official contact is stated in rule 10.3 and FAQ §10; outreach requires the user's explicit instruction. This document prepares the question and does not send it.

## 8. Submission readiness gate

- [ ] Team roster/eligibility checked and locked intentionally before first submission.
- [ ] Primary track and prior-work declaration match organizer guidance and actual implementation.
- [ ] Rights/attribution and every data manifest reviewed.
- [ ] Zetaris, Meterless and Cursor evidence reflects actual use; NVIDIA contribution stated accurately.
- [ ] Connected run and clean checkout pass the acceptance gates; replay clearly labelled.
- [ ] README, video, deck, sponsor statement and exact revision all agree.
- [ ] Video is between 1 and 4 minutes and assets are accessible to judges.
- [ ] Source, history, logs and media checked for secrets and private identifiers.
- [ ] HackOS submission accepted and receipt/timestamp recorded before the internal target.
- [ ] Final official-page/HackOS announcement check completed; no post-deadline patch assumed eligible.

## 9. What this review did and did not verify

Read all six local event guides, the pasted event text and the developer handoff. Opened the live official event page and expanded all ten rule sections on 16 October 2026. Verified the public scoring, rules, dates and prize discrepancy against visible page content.

Did not access the logged-in HackOS workspace, workshop recordings, current challenge-specific pages, submission form, sponsor accounts or organizer correspondence. Did not confirm the team's eligibility, registration, membership, quota, access or integration success. Did not submit or publish anything.

## 10. Source register

| ID | Source | Relevant sections / role |
|---|---|---|
| E1 | [Official Open Agent Hackathon 2026 page](https://hackathon.genai.works/event/open-agent-hackathon-2026) | Live expanded rules §§1–10; Key dates, tracks, scoring and prizes; reviewed 16 Oct 2026 |
| G1 | Hackathon overview (local reference, not published) | §§1/5/6/8–13/17: constraints, sponsors, eligibility, submissions, rubric and dates |
| G2 | Welcome guide (local reference, not published) | §§3–9/11–13: agent quality, tracks, support, sponsor requirements, submission and scoring |
| G3 | FAQ (local reference, not published) | §§2–9: precedence, team lock, old work, data, submissions, judging and rights |
| G4 | Event calendar (local reference, not published) | §§1/3/4/7–9: dates, suggested milestones and update channels |
| G5 | Participant journey map (local reference, not published) | Stages 1–8 and §§5.1–6.2: operational journey and submission gates |
| G6 | Solutioning guide (local reference, not published) | §§5–15/18–19: data/rights, bounded scope, real agent behaviour, runtime guidance and evaluation |
| P1 | Developer handoff (local reference, not published) | §§1/11–16: proposed product/track, tests, schedule, evidence labels, provenance and organizer question |
| P2 | User-pasted event text, supplied in this chat | Corroborates public date/prize differences; partial accordion text, so not sole source for complete rules |

The six guides are supplied local snapshots whose publisher/version metadata was not independently authenticated. They inform planning; explicit live official-rule conflicts are recorded above. Product-specific gates are our design decisions and must not be presented as organizer requirements.
