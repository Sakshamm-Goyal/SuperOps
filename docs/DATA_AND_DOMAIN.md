# Data contracts and domain invariants

Status: proposed canonical domain contract, version 1, 16 October 2026. Example quantities are synthetic test inputs, not provider prices or measurements. [API_REFERENCE.md](API_REFERENCE.md) owns HTTP details; [EVALUATION_SPEC.md](EVALUATION_SPEC.md) owns experiment acceptance.

## Shared representation

Use UUIDs for our record IDs, full provider identity for external targets, UTC RFC3339 timestamps, explicit schema versions and immutable source receipts. Serialize money and exact rates as decimal strings plus ISO currency; utilization includes its unit and must never silently switch between 0–1 and 0–100. Use `null` plus a reason for unknown, never fabricated zero, NaN or infinity. Intervals are half-open `[start,end)` and include timezone and duration units.

Every derived claim has independent fields: `result_kind=measured|projected|estimated|unknown`, `data_origin=synthetic|real_permitted`, and `runtime_mode=sample|connected_demo|replay`, plus evidence references, observation window, calculation/model version and limitations. Example: a replay of an actual trial on synthetic cases has result_kind=measured, data_origin=synthetic, runtime_mode=replay and the original measured_at timestamp. None of these fields implies another; UNKNOWN carries a reason.

## Records and persistence

| Record | Required fields beyond id/schema_version |
|---|---|
| EvidenceRef | tenant_id, service_id, source_system, source_record_id, observed_at, retrieved_at, source_version/hash, units, query_receipt_id, result_kind, data_origin, quality_flags |
| QueryReceipt | template_id/version, parameter_hash, Zetaris request ID, source IDs/versions, start/end, row/page counts, completeness, result hash, warnings; redact auth/query tokens |
| Investigation | actor_id, tenant_id, service_id, question, interval, policy_version, runtime_mode, budget_snapshot, approved_trial_profile_id if any, status, stages, cancellation state |
| CandidatePlan | investigation_id, revision, action_type, exact target identity, target_version, before/after, recovery_scope, workload/policy/config versions, evidence refs, impacts, plan_hash |
| TrialResult | plan_hash, dataset/test hash, model/prompt/config versions, workload/request mix, time window, environment, deterministic checks, observations, costs, outcome |
| ImpactEstimate | baseline and candidate quantities, horizon, rate source/effective interval, currency, gross/net, optimizer/trial/transition costs, uncertainty, carbon coverage/method |
| Approval | actor, tenant, plan_hash, target/version, trial_id/hash, policy_version, recovery scope, created_at, expires_at, status, consumed_action_id |
| ActionReceipt | approval/plan IDs, idempotency key hash, operation IDs, before/after versions, stage journal, health evidence, verified_at, outcome, recovery references |
| MemoryEnvelope | application_receipt_id, kind, scope, finding, evidence refs, applicability versions, supersedes/correction approval, content hash, engine ID, embedding profile |
| Job / Event / Outbox | durable state, lease, attempts, deadlines and monotonic per-run event sequence; unique outbox key per receipt/version |

Use database foreign keys and unique constraints for plan revision, action idempotency, one active target action and outbox identity. Scoped repositories require tenant/service context; never accept caller-provided tenant as authority. Append immutable evidence/results; supersede with a new record rather than editing a successful historical receipt.

## Physical data and grain

Source A: cloud inventory, 15-minute resource telemetry, dated billing/cost rows, ideally BigQuery. Source B: separate reachable PostgreSQL dataset with permitted development AI calls, outcomes and workflow versions; expose read-only source views, not application authority tables. Every trace/outcome carries evaluation_partition and access_class. Exclude all holdout inputs, labels, per-case outcomes and answer-level artifacts from agent-readable Zetaris views and memory; keep them in an evaluator-only schema/storage with separate credentials. Public final reports may expose authorized aggregates only. Source C: supported file/object-store policy and rate records. At least two distinct physical sources must be genuinely queried through Zetaris; target three when provisioning permits.

| Dataset | Grain and key |
|---|---|
| Resource inventory | provider + project_id + resource_id + effective interval |
| Telemetry | Baseline wide row: resource identity + observed_at; CPU percent, memory bytes, latency milliseconds, error numerator/denominator. An adapter may normalize to metric-name rows with separately documented counts |
| Billing | billing_record_id + SKU + resource identity + usage interval + rate version |
| AI calls | service_id + run_id + call_id + attempt; includes failed/retried calls |
| Outcome checks | run_id + case_id + check_id + evaluator version |
| Policy | service_id + policy_id + version + effective interval |
| Price | provider + region + SKU + unit + currency + effective interval |

Aggregate billing at resource/day and AI cost at service/run before joining service totals. Telemetry, call and billing rows must not be joined raw and then summed. Synthetic oracle: two metric rows, three call rows and one $4 bill must still produce $4 cloud cost, not $24. Distinguish exact duplicate source records from legitimate repeated observations. Do not merge resources on display names.

## Dataset plan and freshness

Six resources × 21 days × 96 quarter-hour timestamps = 12,096 telemetry observations when each row holds all metrics. If using long-format metric rows, multiply and document the count instead. Canonical six scenario roles: safely rightsizeable staging worker, low-average/high-peak worker, memory-constrained worker, missing/stale-evidence worker, unsupported stateful resource, and policy/window-restricted worker. Already-efficient behavior is a derived fixture, not a seventh baseline resource. Give each a stable provider-style fictional ID.

Use a generation seed, manifest hashes, units, source license, coverage counts and designed anomalies. Baseline dataset is complete; tests intentionally remove records to verify blocking behavior. A current deployment cannot claim old synthetic timestamps are live. Use a named scenario `as_of` for historical analysis, while real trial, approval, execution and credential timestamps use the actual clock. A scenario clock can never extend an approval or authorize a live write from stale provider state.

Initial sandbox policies: telemetry last observation within 30 minutes of analysis `as_of`; full expected critical CPU/memory coverage for the declared window; prices/policies effective over the comparison interval; explicit peak/stress coverage. Missing critical data blocks validation even when average coverage looks high. These are local chosen thresholds and may be versioned before final evaluation, not changed after seeing failures.

## Capacity and forecast screening

Convert observed CPU into demand: `observed_vcpu = cpu_percent / 100 × source_vcpu`; memory into absolute bytes/GiB. Demand/candidate capacity must be at most 0.80 under the selected stress envelope; equivalently candidate capacity must be at least demand/0.80. Do not multiply demand by 1.20 and call that equivalent to 20% capacity headroom.

For an 8-vCPU source with 10% average and 80% observed peak, average demand is 0.8 vCPU and peak is 6.4 vCPU. A 2-vCPU target fails; an 8-vCPU target is exactly at the 80% CPU threshold but still needs every other check. A 5-GiB observed memory requirement rejects a 4-GiB candidate regardless of CPU.

Use the evaluation protocol's daily seasonal-naive baseline (lag 96 observations), predicting the next 96 quarter-hours at each daily origin. Days 1–14 are development (8,064 rows), days 15–17 calibration (1,728), days 18–21 final temporal evaluation (2,304). Freeze the residual-envelope method before final evaluation; later origins may use only observations already available at that time, without retuning. A stress envelope is not a calibrated probability interval. Persist splits/errors, never use future data or a fixed divisor for missing rows, and test maxima plus forecasts against a matched workload. See EVALUATION_SPEC.md for the canonical protocol.

First executor excludes stateful production systems, local SSD, GPU, architecture changes and untested compatibility. Policy includes environment, allowed action types, maintenance window and workload/latency limits. GCP stopped-instance resize has downtime; passing capacity arithmetic does not remove that. [GCP machine-type changes](https://docs.cloud.google.com/compute/docs/instances/changing-machine-type-of-stopped-instance).

## Accounting

Use decimal arithmetic; round only at presentation or the documented billing boundary. Preserve the raw rate. Compare equivalent horizons and workload, and distinguish public list prices, negotiated rates and synthetic scenario rates.

```text
cloud projected cost = sum(usage quantity × applicable rate)
AI run cost = sum(input + output + tool charges for every attempt exactly once)
gross projected saving = baseline operating cost − candidate operating cost
net projected saving = gross − experiment − transition − optimizer overhead
cost per accepted task = total run cost / independently accepted tasks
```

The last metric is undefined if accepted tasks = 0. Include failed calls and repeated attempts once; retry count/cost subtotal is informational and is not added again when already included in attempt charges. Count optimizer overhead separately once. Do not add mutually exclusive savings or subtract one-time experiment cost from every daily interval. Expose break-even time only when recurrent benefit is positive and units align. Example: baseline $20/day, candidate $16/day, one-time trial+transition+optimizer $6 → 7-day gross $28 and net $22; break-even 1.5 days under those assumptions. This is a numerical oracle, not a business claim.

Credits can make cash paid differ from economic usage cost; show both if known. Reserved/committed spend may not decrease after resize. Missing billing/price data can permit a capacity finding but cannot support a quantified financial benefit. [Google Billing Catalog](https://docs.cloud.google.com/billing/v1/how-tos/catalog-api).

## Carbon boundary

Carbon is an estimate with method version, region/time factor, activity unit, coverage, exclusions and uncertainty description. A simple operational estimate uses `kWh × kgCO2e/kWh`; disclose energy estimation, whether PUE is already included, and embodied allocation separately. Do not infer external-model carbon from tokens alone or equate estimated lower allocation with measured emissions avoided.

Synthetic oracle: 24 kWh × 0.4 kgCO2e/kWh = 9.6 kgCO2e for that interval, not 230.4. Key scenarios by scenario ID + provider + region + machine type + interval; same type in two regions must not overwrite. Missing factors return UNKNOWN/partial coverage. Provider-reported carbon and modeled estimates must not be added together for the same boundary. [Google methodology](https://docs.cloud.google.com/carbon-footprint/docs/methodology), [CCF methodology](https://www.cloudcarbonfootprint.org/docs/methodology/).

## Allowed actions

The discriminated action union is LOCAL_WORKER_CONFIG_UPDATE (exact worker ID, expected config version, bounded max_concurrency), AI_CONFIG_UPDATE (exact workflow ID, expected config version, pinned retrieval/deduplication config), and optional GCP_MACHINE_TYPE_UPDATE (project/zone/instance ID, expected machine type/version, allowed new machine type). Each has an explicit before/after and recovery schema. Reject arbitrary keys, scripts, target URIs and unsupported action types. Local worker changes cannot be reported as a GCP resize. Trial-only fixture configuration operations use a separate approved trial profile and cannot target the eventual action resource.

## Plan and approval integrity

Create plan hashes from a versioned canonical JSON representation: sorted keys, defined decimal/timestamp encoding, no NaN, no volatile UI fields. Include target identity/version, before/after, action/recovery scope, policy/workload/config versions, evidence snapshot and calculation versions. Store the canonical bytes and digest. Do not hash free-form prose and assume it binds execution.

Trial result separately binds plan hash and evaluator/dataset/model versions. Approval binds both the plan hash and accepted trial hash, actor and scope. Initial TTL is 15 minutes; accepted trials expire after 24 hours or any applicable input/version change, whichever is earlier. Policies can tighten these defaults. The server sets times; the client cannot choose a later expiry.

Approval expiry still applies immediately before the first external write even after approval is consumed by queue creation. An expired queued action finishes FAILED with APPROVAL_EXPIRED and zero writes; it requires a new approval. Once a started operation crosses expiry, finish only the already authorized operation/reconciliation or permitted recovery; expiry does not authorize a second action. At execute: authenticate → fetch current scoped records → check expiry/trial/policy → acquire target lock → re-read target → compare approved state/version → persist intent → call allowlisted executor → read back → run health/workload smoke → finalize receipt. Consume approval atomically with action creation; repeat requests reference the same action. Same idempotency key with a different body is a conflict.

Provider APIs may lack atomic compare-and-set across the full stop/resize/start sequence. Use a dedicated sandbox target and restricted writer IAM, recheck between steps, and document the remaining external-writer race. If a human changes the target, stop automated recovery rather than overwriting the intervening change. No database lock protects an external resource from all actors.

## AI lab invariants

Use one synthetic retail-support workflow and the same tested model first. Optimize duplicate side-effect-free lookups and retrieval of relevant policy sections. Expected facts/actions come from independent synthetic records and policy, not the optimizing model's own grading. Preserve premium exceptions, customer/order binding, escalation and missing-field behavior.

80 authored cases split into 40 development and 40 held out by scenario families; deduplicate related examples across partitions. The evaluator owns holdout keys. Freeze prompts, config, model and test hash before final evaluation. Store only aggregate permitted outcomes for subsequent memory; no heldout labels or answer text go into optimizer context. Publish sample counts and limitations. Detailed checks and quality thresholds live in [EVALUATION_SPEC.md](EVALUATION_SPEC.md).
