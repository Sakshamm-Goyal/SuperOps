# Security design and reporting

Current status: planned sandbox application, not a security-certified or production-deployed service. Never place real customer messages, upstream credentials or production write access in this demo.

The application starts with one sandbox tenant, server-side bearer credentials for named roles, TLS at ingress, read-only sponsor data roles and a private memory sidecar. Only the executor receives restricted target-write credentials. Public judge access is read-only; operator routes require a separate authenticated context. Tokens, authorization headers and connection strings must be redacted from errors, traces and videos.

| Threat | Required control and verification |
|---|---|
| Prompt injection in evidence or memory | Treat text as data; schema/role/tool allowlists; injection cannot authorize mutation |
| Unauthorized record access | Derive actor/tenant from server authentication; scope every lookup; deny unknown IDs without exposing cross-scope existence |
| Approval bypass or replay | Immutable plan hash, expiry, target/version checks, role validation, target lock and idempotency |
| SQL injection or expensive scans | Server-owned query templates, typed parameters, row/time limits, read-only source role |
| Provider timeout after write | Reconcile operation and resource state before any retry |
| Memory poisoning or stale learning | Evidence-backed write envelopes, explicit scope/version filters, append corrections, inspect disagreements |
| Holdout leakage | Separate evaluator credentials/storage; optimizer cannot query answer keys or retrieve them from memory |
| Exposed dependencies or files | Lockfiles, vulnerability scan, license inventory, secret scan and private durable volumes |
| Export leakage | Scope exports to requesting actor, redact source secrets, no automatic public Drive sharing |
| Shared mutable UI state | API owns durable truth; UI state and cached pages never confer authorization |

If a credential leak is discovered, stop exposure, notify the repository owner privately using an authorized channel, rotate/revoke affected credentials, and assess history/logs. Do not paste the secret into issues or this file. This task has not verified a private reporting address; do not invent one.

Operational controls, recovery and retention are in [OPERATIONS.md](docs/OPERATIONS.md). Mandatory adverse cases are in [TEST_STRATEGY.md](docs/TEST_STRATEGY.md). Passing those cases does not establish safety for production infrastructure.
