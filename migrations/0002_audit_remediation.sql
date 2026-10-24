-- 17 Oct 2026 audit remediation: durable budget reservations (A08) and frozen holdout verdicts gating AI promotion (A15).

CREATE TABLE budget_reservations (
  id uuid PRIMARY KEY,
  investigation_id uuid,
  trial_id uuid,
  eval_run text,
  conservative_cost_usd numeric NOT NULL CHECK (conservative_cost_usd >= 0),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON budget_reservations (investigation_id);
CREATE INDEX ON budget_reservations (trial_id);
CREATE INDEX ON budget_reservations (eval_run);
CREATE INDEX ON budget_reservations (created_at);

CREATE TABLE evaluation_verdicts (
  id uuid PRIMARY KEY,
  tenant_id text NOT NULL,
  service_id text NOT NULL,
  candidate_config_hash text NOT NULL,
  model_id text NOT NULL,
  freeze_hash text NOT NULL,
  decision text NOT NULL CHECK (decision IN ('ROLLOUT_ELIGIBLE', 'NO_CHANGE')),
  run_id text NOT NULL UNIQUE,
  metrics jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON evaluation_verdicts (tenant_id, service_id, candidate_config_hash, model_id);
