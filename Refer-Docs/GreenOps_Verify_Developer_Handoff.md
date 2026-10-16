# GreenOps Verify — Developer Handoff

**Prepared:** 16 October 2026 · **Status:** proposed implementation specification, not a built application.

**Goal:** retain GreenOps’ cloud audit, forecasting, cost/carbon comparison, controlled change and reporting concept. Add cross-source evidence through Zetaris, persistent experiment memory through Meterless, explicit critique/revision and one small AI Efficiency Lab.

**Read first:** the companion **Complete Blueprint**, especially sections 05–07, 10–17 and 19–25. The **Team Brief** is for daily scope alignment. This handoff defines proposed application interfaces; none of the routes below is represented as a vendor SDK/API contract.

## 1. Freeze these decisions

One engineering lead, one GCP-hosted service, six small VM histories, one support-agent workflow, at most three candidate plans per path (six total per investigation) and one action at a time. Keep Python, Google ADK and Streamlit. Use FastAPI for application contracts, PostgreSQL for transactional state and a private TypeScript H-MEM sidecar for memory.

**Ship the cloud path first.** The AI lab shares its investigation/approval/evidence infrastructure. Do not build a universal FinOps platform, a subscription manager, multi-cloud deployment, fine-tuning, Kubernetes orchestration or autonomous production shutdown.

### Rights and track gate

The inspected baseline is `niksm7/GreenOps`, branch `master`, commit `db38811fb653631892e6cbbe1275793bd9906858`. Selected source files were reviewed statically; no original deployment, credentials or model outputs were tested.

No licence grant was found in the inspected tree or README. Before including original code, assets, prompts or templates, obtain permission that covers the intended use and redistribution. Attribution does not replace permission. Ask organizers specifically about a derivative of another team's previously winning product and Wildcard eligibility. Do not assume Wildcard automatically resolves rights or eligibility.

Until those questions are resolved, independently implement this specification, acknowledge concept inspiration and target Track 02. Declare this planning pack, pre-event datasets and any permitted pre-existing components. Preserve a baseline and new-work commit history; do not imply all work was created during the event.

## 2. Repository layout to create

```text
project/
  README.md
  ATTRIBUTION.md
  PREEXISTING.md
  NEW_WORK.md
  SECURITY.md
  .env.example
  .gitignore
  compose.yaml
  dependency-lock-files/
  apps/
    api/                     # FastAPI; authentication; typed requests
    ui/                      # Streamlit; never holds cloud write credentials
  agents/
    coordinator.py
    investigator.py
    optimizer.py
    critic.py
    workflow.py              # bounded states and revision rules
  adapters/
    zetaris.py               # actual workspace query interface
    model.py                 # tested ADK/NVIDIA adapter
    memory.py                # private H-MEM wrapper client
    cloud_read.py
    cloud_execute.py         # disabled until explicit trial approval
  services/
    evidence.py
    forecasting.py
    capacity.py
    cost.py
    carbon.py
    trials.py
    approval.py
    execution.py
    verification.py
    reporting.py
  memory-sidecar/
    package.json
    lockfile
    src/                     # private HTTP wrapper over real H-MEM reference
    reference-manifest.json  # chosen reference revision + notices
  schemas/
  sql/                       # approved read-only query templates
  experiments/
    support_workflow.py
    verifier.py
    candidate_configs/
  data/
    samples/
    manifests/
    README.md
  scripts/
    bootstrap
    preflight
    run_demo
    reset_sandbox
  tests/
    unit/
    integration/
    acceptance/
  docs/
  output_examples/           # small, redacted, labelled actual results only
```

This is a proposed structure, not a collection of files that already exists. Use original independently written modules unless the reuse gate has passed. Do not copy the upstream `.env`, compiled files, screenshots or cloud identifiers.

## 3. Agent and deterministic-code responsibilities

| Role | Can decide | Cannot authorize |
|---|---|---|
| Coordinator | Which evidence or trial is required next; revise or escalate | A cloud write or an expired approval |
| Investigator | Which source records explain an anomaly or contradiction | An identity merge based solely on a similar name |
| Optimization engineer | A bounded candidate configuration and test plan | Invented prices, carbon factors or acceptable thresholds |
| Critic | Request evidence, reject a candidate, propose a revised investigation | Bypass deterministic constraints or human approval |

Forecasting, numerical accounting, typed validation, workload replay, approval checks, change execution and report formatting are ordinary application tools. They do not each need another language-model agent.

Use the supported ADK loop/custom-workflow mechanism in the version selected after a smoke test. Keep the loop observable through tool calls, evidence IDs, decisions and test outputs. Do not expose private reasoning traces or present generated internal reasoning as proof of correctness.

### Bounded control flow — pseudocode

```text
start investigation with actor, tenant, target, horizon and budget
read current applicable policy
retrieve scoped prior experiments through H-MEM
query evidence through Zetaris; preserve source receipts

for at most six attempts, with no more than three per path:
    investigator resolves gaps or returns NEEDS_REVIEW
    optimizer proposes a typed candidate with evidence references
    deterministic checks reject invalid/unsupported candidates
    run bounded trial only when its preconditions hold
    critic reviews evidence + independent trial result
    record outcome and provenance
    if revision needed: return to investigator/optimizer
    if validated: stop proposing and wait for human approval
    if no acceptable option: finish with a justified NO_CHANGE result

on a separate authenticated approval request:
    bind approval to actor + target + plan hash + versions + expiry
    re-read authoritative state and recheck policy
    acquire execution lock and unique action key
    apply the allowlisted operation in the approved environment
    read back resulting configuration and run health checks
    record VERIFIED, PENDING_VERIFICATION, RECOVERY_REQUIRED or FAILED
    write a sourced learning receipt to H-MEM
```

Suggested limits, not event requirements: three candidates per path and six total; two retries for transient reads; explicit per-call and total deadlines; one target write at a time; configurable experiment-spend cap. Never retry an uncertain write as though it definitely did not execute. Read its operation state first.

## 4. Zetaris integration: make it indispensable

### Three physical sources

**Source A — BigQuery or an approved database:** resource registry, metric history and billing/sample cost records. Retain BigQuery when accessible; its use as a source does not compete with Zetaris’ query role.

**Source B — PostgreSQL:** actual AI call traces, outcome-check records and workflow configuration versions. Its application-action tables must not be exposed as arbitrary write tools to the model.

**Source C — supported file/object storage:** workload policies, dated price snapshots, carbon-method metadata and approved maintenance windows.

At least two physically independent sources must work through real Zetaris queries. Target all three. One database containing copied tables with a token sponsor query is not the intended design.

A hosted sponsor workspace cannot automatically access `localhost` on a developer laptop. Verify network reachability, TLS, source credentials and permitted connector types immediately. Put permitted samples in an approved reachable store; do not expose a personal database publicly without controls.

### Query contract — ours

```text
query_evidence(template_id, validated_parameters, as_of, max_rows)
    -> rows, source_refs, query_receipt_id, observed_at,
       retrieved_at, source_versions, completeness, warnings
```

Implement using the query collection/API for the provided workspace version. Handle its actual authentication, query tokens and pagination. Do not invent a generic `/zetaris/query` endpoint. Refresh credentials securely and never include tokens in query receipts.

Use a finite list of templates for resource history, cost breakdown, AI outcomes and policy lookup. Validate parameters server-side. Read-only database roles remain necessary even when SQL is validated. A simple “query starts with SELECT” check is not sufficient protection against all SQL forms.

### Join and evidence correctness

Use `(provider, project_id, resource_id)` rather than display names to identify resources. Use `(service_id, run_id, call_id)` for AI execution. Prices also need region, SKU, currency, unit and effective interval.

Aggregate metrics/cost at resource and time-window grain before joining service-level AI totals. Avoid multiplying billing amounts through a metrics-by-call many-to-many join. Return independently computed totals and source links.

Every important recommendation needs input record IDs, observation time, snapshot/version information and a query receipt. Cached evidence is allowed but visibly dated. Re-read the authoritative target through the cloud/configuration API immediately before a write; that does not remove Zetaris’ required role in the preceding investigation.

## 5. Meterless integration: real H-MEM, small wrapper

Use the Meterless Agentathon starter/reference, with its documented setup/vendor step. Pin the chosen revision and record the source, version and applicable notices. The upstream material is an implementation specification with a runnable reference, not a finished production engine. Do not spend the sprint recreating every H-MEM service.

Host the TypeScript reference behind an authenticated, private HTTP sidecar. Persist its data outside an ephemeral application filesystem. Use one sidecar writer initially unless the selected storage implementation has verified concurrency support. Test clean installation and persistence after process restart.

### Proposed private wrapper routes

| Our route | Purpose |
|---|---|
| `POST /memory/remember` | Validate an experiment/correction envelope; invoke real memory mining/store services |
| `POST /memory/recall` | Invoke real retrieval; return memory IDs, supporting metadata and retrieval trace |
| `GET /memory/audit/{id}` | Return the reference engine's audit history for a memory |
| `GET /health` | Name loaded engine revision and report storage readiness without exposing secrets |

Map these to the reference version’s actual interfaces. Do not pretend these routes are official Meterless endpoints.

### Store a small application envelope

```json
{
  "kind": "rejected_trial",
  "tenant_id": "sandbox-tenant",
  "service_id": "support-demo",
  "target_id": "worker-02",
  "configuration_hash": "sha256:<computed>",
  "policy_version": "policy-v3",
  "workload_version": "workload-v2",
  "model_id": "<tested-model-id>",
  "test_set_hash": "sha256:<computed>",
  "finding": "Candidate exceeded the permitted memory envelope",
  "evidence_refs": ["evidence-017", "trial-009"],
  "source": "trial-009",
  "approved_correction_ref": null,
  "supersedes": null
}
```

This is **our envelope**, to be mapped to the H-MEM canonical record. Generate hashes; never retain literal placeholders as runtime evidence.

Memory should change a later investigation: avoid re-presenting the same failed candidate as already validated, recall a verified workload exception, or preserve why a corrected source changed a conclusion. Application code must check applicability against current tenant, service, workload, policy, model and test-set versions. A high retrieval score is not authorization or proof a fact is still current.

Keep approval records, idempotency keys, pending actions and transactional execution status in PostgreSQL. H-MEM is explicitly not a replay/rollback engine. Preserve failed and superseded history; do not automatically erase an inconvenient finding. Critical corrections require human review.

## 6. Shared records and state model

Use typed, versioned schemas. Reject unknown action types, invalid units, non-finite metrics and missing required evidence. Prefer explicit `unknown` to fabricated zeroes.

| Record | Minimum fields |
|---|---|
| EvidenceRef | ID, source system, source record ID, observed/retrieved times, version/hash, unit, query receipt |
| Investigation | ID, actor, tenant, service, question, horizon, budget, policy version, status |
| CandidatePlan | ID, target, action type, before/after, constraints, evidence refs, plan hash |
| TrialResult | ID, plan hash, workload/config/model/test versions, metrics, failure IDs, cost |
| ImpactEstimate | interval, currency, price source, baseline/candidate usage and costs, carbon method/coverage |
| Approval | ID, actor, plan hash, target version, allowed scope, expiry, status |
| ActionReceipt | action/idempotency IDs, target, before/after, provider operation ID, checks, final status |

Required state distinctions: `DRAFT`, `NEEDS_EVIDENCE`, `REJECTED`, `VALIDATED`, `AWAITING_APPROVAL`, `APPROVED`, `STALE`, `EXECUTING`, `PENDING_VERIFICATION`, `VERIFIED`, `RECOVERY_REQUIRED`, `RECOVERED`, `FAILED`.

Do not jump from `VALIDATED` to `EXECUTING` because the chat says “looks good.” Approval is a separate authenticated application operation.

### Minimum public application routes

```text
POST /investigations                  create a bounded investigation
GET  /investigations/{id}             findings and candidate states
POST /plans/{id}/trials               run an allowed experiment
POST /plans/{id}/approve              authenticated, scoped approval
POST /plans/{id}/execute              revalidate and execute once
GET  /actions/{id}                    status, read-back and health results
GET  /reports/{id}                    export evidence report
```

These are proposed application routes. Access-control and permission checks apply to every route, including reads of potentially sensitive traces. The prototype may use a single documented sandbox tenant rather than claiming production multi-tenancy.

## 7. Cloud trial implementation

Start with six resources × 21 days × 96 quarter-hour observations: **12,096 metric rows** before omitted/stale test records. Include CPU, memory, application latency/error rate, resource capacity, environment, state and version. The data is synthetic; its source manifest must say so.

Use seasonal-naive forecasts with an empirical residual envelope first. Backtest against later observations rather than training on the future. Label the interval method accurately; an empirical stress envelope is not a calibrated probability guarantee. Do not train large models during the demo.

Convert utilization into approximate resource demand before comparing targets. Example: 10% average CPU on 8 vCPU is 0.8 vCPU average demand, but a observed 6.4-vCPU peak rejects a 2-vCPU target. Check memory in absolute units too. This proportional calculation screens candidates; it is not a hardware-performance benchmark.

Required checks: complete/fresh evidence, peak/stress demand, target compatibility, headroom, current policy and maintenance window, and a matched workload test. Exclude stateful production systems, local SSD, GPU and architecture changes from the first executor.

Prefer a team-owned disposable GCP VM trial after permissions, budget and compatibility are confirmed. This stopped-VM path has downtime. Do not use original authors' infrastructure. An acceptable engineering fallback is a real local worker/configuration change with actual workload measurements and read-back, explicitly labelled as a local analogue. It is not a measured GCP resize or proof of an actual cloud invoice reduction.

## 8. AI Efficiency Lab implementation

One synthetic retail-support workflow: order status, returns, membership exceptions, missing fields and requests needing escalation. The verifier should check expected facts/actions against the synthetic records and policy, not merely judge whether prose sounds good.

Begin with the same model so the first improvement does not depend on proving a cheaper model is adequate. Test only bounded changes: eliminate duplicate side-effect-free lookups and retrieve relevant policy sections while preserving necessary exceptions. Do not cache private/dynamic results across customers or policy versions. Deduplication requires equivalent inputs and a suitable freshness rule.

Create 80 labelled cases: 40 development and 40 held out. Hold-out answers must not enter optimizer prompts or memory during tuning. Pin the candidate before final evaluation. Count retries, failed attempts and total tokens; a failed answer is not free.

An aggressive reduction may omit the premium return condition. The independent check should reject it. The optimizer can revise once or twice, or conclude no acceptable saving exists. Do not hardcode which candidate/model wins. A second model is optional only after this loop works.

Run genuine model calls and preserve traces from newly executed experiments. Distinguish a short live demonstration from a clearly labelled replay of a longer prior run. Do not present replayed measurements as newly generated.

## 9. Cost and carbon rules

Use decimal accounting with explicit units, currency, rate versions and horizons.

```text
cloud_cost = sum(billable_quantity × applicable_unit_rate)
ai_cost = input_cost + output_cost + tool_and_retry_cost
net_projected_saving = baseline_cost - candidate_cost
                       - experiment_cost - transition_cost
cost_per_accepted_task = total_run_cost / independently_accepted_tasks
```

If there are zero accepted tasks, the last metric is undefined, not zero. Include failed attempts in total cost. Report optimizer overhead separately and include it when claiming net benefit. Do not combine mutually exclusive candidate savings or different horizons. Public catalogue prices are not necessarily effective account rates; committed spend may not reduce when a VM shrinks.

Carbon is a separate, bounded estimate. Use documented current provider support or a versioned usage/energy methodology with clear factors, units and exclusions. Return `UNKNOWN` when factors are missing. The legacy Climatiq compute endpoint used upstream was not verified as available during this review; test the team's permitted current API before depending on it.

A calculation can take the form `estimated operational kgCO2e = estimated kWh × applicable kgCO2e/kWh`; disclose how energy is estimated and whether data-centre overhead is already included. Keep embodied allocation distinct. Do not double count a provider total and its components.

Compare the same interval and workload boundary. Do not multiply a 24-hour carbon total by 24 again. Key scenarios by scenario ID, provider, region, type and interval so identical machine types in different regions do not overwrite each other. External model token counts alone are not a defensible carbon measurement. Carbon may be unavailable for the AI portion even when its cost is measured.

## 10. Approval and execution guards

Before execution, verify the authenticated actor, approval expiry, exact plan hash, target identity and version, policy version, environment allowlist, window and current health. Lock the action record and enforce a unique idempotency key. Mutations are predefined typed operations, not model-generated shell commands.

For a GCP trial: capture before-state; check compatibility; stop; wait for operation and state with deadlines; resize; start; verify machine type; run application health/workload checks. A running instance can still contain a failed application. Separate a provider operation failure from an unknown outcome.

If verification fails, recover only within the approved scope and only when current state still matches the expected failed transition. A conflicting human change must block automatic restoration. Record unresolved effects and escalate. Do not promise recovery always succeeds.

For an AI configuration update, use a versioned compare-and-set, retain the previous configuration and run fresh smoke cases. Verify the configuration actually used by new runs, not only the database field that was changed.

## 11. Acceptance suite

| ID | Test | Expected behaviour |
|---|---|---|
| 01 | Same display name in two projects | No identity merge |
| 02 | Raw joins would duplicate bill rows | Independent totals remain correct |
| 03 | Missing memory metrics | Cloud proposal needs evidence; no approval |
| 04 | Low average, high CPU peak | Aggressive target rejected |
| 05 | Adequate CPU, inadequate memory | Candidate rejected |
| 06 | Unsupported target configuration | No executor call |
| 07 | Already-totalled 24-hour carbon | No second ×24 conversion |
| 08 | Same type in different regions | Two distinct scenario results |
| 09 | Missing price/carbon source | Partial/unknown, not invented values |
| 10 | Premium-policy exception omitted | AI candidate fails required check |
| 11 | Customer/order identity mismatch | Case fails; no tool side effect |
| 12 | Attempts to read held-out labels | Optimizer access denied |
| 13 | Memory process restart | Experiment can be recalled with source |
| 14 | Policy/config version changes | Old validation loses applicability |
| 15 | Conflicting memory correction | Preserve provenance; human review |
| 16 | Approval expired | No write |
| 17 | Target changes after approval | Approval marked stale |
| 18 | Repeated execute request | At most one actual change |
| 19 | Write times out with unknown outcome | Read operation state; no blind retry |
| 20 | Instance running but app unhealthy | Pending/recovery state, not verified |
| 21 | Sponsor/model service unavailable | Bounded failure; no unapproved write |
| 22 | Injected instruction inside record | Treated as data, not authority |
| 23 | Trial changes request mix | Do not call comparison equivalent |
| 24 | No candidate improves acceptably | Honest NO_CHANGE with evidence |

Compare the cloud system against a simple utilization-threshold baseline. Compare the complete design with memory enabled and disabled on repeated investigations; keep inputs, model, prompts and budget fixed. Publish counts, failures and runtime/cost overhead. These are local evaluations, not proof of universal reliability.

## 12. Six-day backlog and ownership

Assume three builders: A — data/sponsor integration; B — agents, domain logic and trials; C — API/UI, control flow and evaluation. C owns the acceptance suite from day one; everyone integrates daily.

| Work item | Owner / dependency | Done when |
|---|---|---|
| G0 Rights, track and access gate | All; before reuse | Written decision logged; sponsor reachability known |
| D1 Evidence schema + templates | A; G0 | Two-source query returns traceable receipts |
| M1 H-MEM sidecar | A; G0 | Remember/recall/audit work after restart |
| O1 Agent loop | B; D1 | Critic triggers a real revision on missing evidence |
| C1 Cloud trial | B; O1 | Target checks + measured workload comparison |
| U1 Investigation interface | C; D1 | Queue, evidence panel and candidate state visible |
| Q1 AI lab | B; C1 | Actual traces + independent verifier + locked hold-out |
| X1 Approval/action state | C; O1 | Stale/duplicate requests blocked; one change verified |
| E1 Acceptance and ablations | A/B/C | Results and limitations recorded, no fake metrics |
| R1 Report and submission | C; E1 | Clean setup, deck, video, sources and sponsor explanation |

22 October: G0/D1/M1/O1 skeleton. 23 October: cloud path and critic. 24 October: AI lab. 25 October: guarded execution and failure tests. 26 October: freeze, clean-install test, record video, complete deck. 27 October: final validation and submit. Target 18:00 UTC internally; guide deadline is 23:45 UTC.

Cut in order: auto-slide generation, recurring scheduler, second model, extra dashboards, then live GCP resize in favour of an honest executable sandbox. Do not cut either required sponsor, evidence, independent tests, the critic loop, approval or verification.

## 13. Environment, deployment and sample modes

Use placeholders only in `.env.example`. Proposed variable names:

```dotenv
APP_ENV=sandbox
CLOUD_WRITES_ENABLED=false
ZETARIS_WORKSPACE_URL=<provided-workspace>
ZETARIS_CREDENTIAL_REF=<secret-reference>
DATABASE_URL=<application-database>
MEMORY_BASE_URL=<private-sidecar>
MEMORY_AUTH_TOKEN=<placeholder>
HMEM_DATA_DIR=<durable-volume-path>
NVIDIA_NIM_API_KEY=<placeholder>
MODEL_ID=<tested-available-model>
GOOGLE_CLOUD_PROJECT=<team-owned-disposable-project>
CARBON_PROVIDER=<approved-provider-or-bounded-estimator>
CARBON_API_KEY=<placeholder-if-needed>
MAX_EXPERIMENT_COST=<team-approved-cap>
RUNTIME_MODE=connected_demo
```

Variable names other than provider-documented credentials are application choices. Use managed identity/application-default credentials where appropriate; no private credential files in version control. Load secrets lazily so a read-only startup is not broken by an unused connector.

Deploy with Compose on one controlled host first. Persist PostgreSQL and H-MEM data, restrict network access and expose only the intended UI/API. Keep memory private. Lock compatible dependency versions after testing and check current security advisories. Do not copy the original model/package pins blindly.

`connected_demo`: real sponsor queries against permitted samples, real model calls, executable sandbox controls. `replay`: previous recorded evidence for resilience; visibly marked and all infrastructure writes disabled. Replay alone is not proof of a functioning sponsor integration. Validate actual integration before recording/submitting.

The bootstrap command should automate environment checks, sample loading, sidecar setup and health checks after users supply required authorized credentials. “Clean setup” does not mean commercial credentials magically appear. Provide a no-cloud-write default and honest instructions for missing sponsor access.

## 14. Cursor starter brief

Paste the following as a development brief **during the permitted build window**, with this handoff and the blueprint attached:

> Build the independently authored GreenOps Verify specification in this repository. Keep cloud optimization central and implement one small AI Efficiency Lab. Begin with typed records, read-only Zetaris evidence queries and the genuine Meterless H-MEM reference behind a private persistent sidecar. Use Python, Google ADK, FastAPI and Streamlit; test the chosen NVIDIA model adapter before freezing dependencies. Do not invent sponsor APIs, copy unlicensed upstream code, embed secrets or enable cloud writes by default. Separate model proposals from deterministic constraints and authenticated approvals. Produce tests for missing metrics, peak demand, carbon duration, identity collisions, failed policy cases, persistence, stale approvals and idempotency. Deliver a working cloud investigation with critic-driven revision before UI polish. Treat all initial data as synthetic unless its provenance says otherwise. Mark replay outputs and unimplemented features explicitly. Do not claim achieved savings or production safety. Work in small reviewable commits and update NEW_WORK.md after each completed capability.

## 15. Submission provenance templates

**PREEXISTING.md:** name each prior component, source/owner, revision, permission/licence, purpose, reused files and preparation date. List this planning pack and any data prepared before the build window. Keep permission evidence privately where necessary and describe its scope accurately.

**ATTRIBUTION.md:** “Concept inspiration: GreenOps by Aishwarya Nathani and Nikhil Mankani. This project is an independent implementation / permission-based derivative [select the true statement]. We do not claim authorship of the original GreenOps submission or its award.” Add required licence notices for actual dependencies and reused components.

**NEW_WORK.md:** capability; implementation commits; date; original-vs-new distinction; test proof; screenshots/traces created by this team; remaining limitations.

**Organizer question:** “We plan a GreenOps-inspired project and may reuse selected code only if the original authors grant suitable permission. Does a derivative of another team's previously winning project qualify, and should it enter Wildcard or a main track? What prior preparation/code must we declare? Please confirm the controlling registration/judging schedule and sponsor access requirements.”

## 16. Primary references

The Complete Blueprint provides the full source register and source-specific review findings. Key implementation sources:

- User-supplied **Welcome Guide**, §§4, 8, 9 and 12: mandatory sponsors, track, declaration, deliverables and rubric.
- [Original GreenOps baseline](https://github.com/niksm7/GreenOps/tree/db38811fb653631892e6cbbe1275793bd9906858).
- [GitHub licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
- [Zetaris connections](https://kbase.zetaris.com/knowledge/connect), [BigQuery connector](https://kbase.zetaris.com/knowledge/bigquery), [REST interface](https://kbase.zetaris.com/knowledge/rest-api).
- [Meterless H-MEM](https://github.com/Meterless/Meterless/tree/main/engines/hmem) and [starter](https://github.com/Meterless/Meterless/tree/main/templates/agentathon-starter).
- [ADK loop workflows](https://adk.dev/agents/workflow-agents/loop-agents/), [ADK model adapter](https://adk.dev/agents/models/litellm/), [NVIDIA APIs](https://docs.api.nvidia.com/nim/reference/llm-apis).
- [GCP machine-type changes](https://docs.cloud.google.com/compute/docs/instances/changing-machine-type-of-stopped-instance), [Cloud Billing catalogue](https://docs.cloud.google.com/billing/v1/how-tos/catalog-api).
- [GCP carbon exports](https://docs.cloud.google.com/carbon-footprint/docs/export), [Cloud Carbon Footprint methodology](https://www.cloudcarbonfootprint.org/docs/methodology/).

**Evidence boundary:** source capability descriptions informed this design; proposed application behaviour must still be implemented and tested. Current team access, quotas, dependency compatibility, eligibility, carbon-provider support and achieved results are not established by this handoff.
