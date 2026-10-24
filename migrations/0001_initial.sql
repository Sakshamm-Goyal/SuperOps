-- GreenOps Verify authority schema v1. PostgreSQL owns workflow truth, approvals, actions and the memory outbox.

CREATE TABLE actors (
  actor_id text PRIMARY KEY,
  tenant_id text NOT NULL,
  display_name text NOT NULL,
  role text NOT NULL CHECK (role IN ('viewer', 'operator', 'admin')),
  token_sha256 text NOT NULL UNIQUE,
  disabled boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE services (
  tenant_id text NOT NULL,
  service_id text NOT NULL,
  display_name text NOT NULL,
  runtime_modes text[] NOT NULL,
  PRIMARY KEY (tenant_id, service_id)
);

CREATE TABLE budget_profiles (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  max_run_cost_usd numeric NOT NULL CHECK (max_run_cost_usd >= 0),
  max_model_calls integer NOT NULL CHECK (max_model_calls > 0),
  max_evidence_seconds integer NOT NULL DEFAULT 180,
  max_conservative_cost_per_call_usd numeric NOT NULL CHECK (max_conservative_cost_per_call_usd > 0)
);

CREATE TABLE trial_profiles (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  service_id text NOT NULL,
  document jsonb NOT NULL,
  profile_hash text NOT NULL,
  approved_by text NOT NULL REFERENCES actors(actor_id),
  approved_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  status text NOT NULL CHECK (status IN ('ACTIVE', 'REVOKED'))
);

CREATE TABLE investigations (
  id uuid PRIMARY KEY,
  tenant_id text NOT NULL,
  service_id text NOT NULL,
  actor_id text NOT NULL REFERENCES actors(actor_id),
  question text NOT NULL,
  interval_start timestamptz NOT NULL,
  interval_end timestamptz NOT NULL,
  as_of timestamptz NOT NULL,
  runtime_mode text NOT NULL CHECK (runtime_mode IN ('sample', 'connected_demo', 'replay')),
  data_origin text NOT NULL DEFAULT 'synthetic',
  policy_version text NOT NULL,
  data_manifest_id text NOT NULL,
  budget_profile_id text NOT NULL REFERENCES budget_profiles(id),
  budget_snapshot jsonb NOT NULL,
  trial_profile_id text REFERENCES trial_profiles(id),
  memory_mode text NOT NULL CHECK (memory_mode IN ('on', 'off')),
  status text NOT NULL,
  stage text NOT NULL,
  cancel_requested boolean NOT NULL DEFAULT false,
  summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON investigations (tenant_id, service_id, created_at DESC);

CREATE TABLE investigation_events (
  investigation_id uuid NOT NULL REFERENCES investigations(id),
  seq integer NOT NULL,
  at timestamptz NOT NULL DEFAULT now(),
  kind text NOT NULL,
  actor text NOT NULL,
  payload jsonb NOT NULL,
  PRIMARY KEY (investigation_id, seq)
);

CREATE TABLE query_receipts (
  id uuid PRIMARY KEY,
  investigation_id uuid REFERENCES investigations(id),
  tenant_id text NOT NULL,
  service_id text NOT NULL,
  template_id text NOT NULL,
  template_version text NOT NULL,
  source_system text NOT NULL,
  runtime_mode text NOT NULL,
  completeness text NOT NULL CHECK (completeness IN ('complete', 'partial', 'failed')),
  row_count integer NOT NULL,
  result_hash text NOT NULL,
  receipt jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE evidence (
  id uuid PRIMARY KEY,
  receipt_id uuid NOT NULL REFERENCES query_receipts(id),
  investigation_id uuid REFERENCES investigations(id),
  tenant_id text NOT NULL,
  service_id text NOT NULL,
  kind text NOT NULL,
  subject text,
  observed_from timestamptz,
  observed_to timestamptz,
  retrieved_at timestamptz NOT NULL,
  result_kind text NOT NULL CHECK (result_kind IN ('measured', 'projected', 'estimated', 'unknown')),
  data_origin text NOT NULL CHECK (data_origin IN ('synthetic', 'real_permitted')),
  quality_flags jsonb NOT NULL DEFAULT '[]'::jsonb,
  data jsonb NOT NULL
);

CREATE TABLE plans (
  id uuid PRIMARY KEY,
  investigation_id uuid NOT NULL REFERENCES investigations(id),
  tenant_id text NOT NULL,
  service_id text NOT NULL,
  path text NOT NULL CHECK (path IN ('cloud', 'ai')),
  candidate_no integer NOT NULL CHECK (candidate_no BETWEEN 1 AND 3),
  revision integer NOT NULL,
  parent_plan_id uuid REFERENCES plans(id),
  target_key text NOT NULL,
  action_type text NOT NULL,
  core jsonb NOT NULL,
  canonical_json text NOT NULL,
  plan_hash text NOT NULL,
  status text NOT NULL,
  screening jsonb,
  critic jsonb,
  impacts jsonb,
  rationale text,
  memory_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  stale_reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (investigation_id, path, candidate_no)
);

CREATE TABLE trials (
  id uuid PRIMARY KEY,
  plan_id uuid NOT NULL REFERENCES plans(id),
  tenant_id text NOT NULL,
  service_id text NOT NULL,
  actor_id text NOT NULL,
  plan_hash text NOT NULL,
  trial_profile_id text REFERENCES trial_profiles(id),
  suite_id text NOT NULL,
  status text NOT NULL,
  trial_hash text,
  result jsonb,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX trials_one_active_per_plan ON trials (plan_id) WHERE status IN ('QUEUED', 'RUNNING');

CREATE TABLE approvals (
  id uuid PRIMARY KEY,
  plan_id uuid NOT NULL REFERENCES plans(id),
  tenant_id text NOT NULL,
  service_id text NOT NULL,
  actor_id text NOT NULL REFERENCES actors(actor_id),
  plan_hash text NOT NULL,
  trial_id uuid NOT NULL REFERENCES trials(id),
  trial_hash text NOT NULL,
  policy_version text NOT NULL,
  recovery_scope text NOT NULL,
  acknowledge_downtime boolean NOT NULL,
  created_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  status text NOT NULL,
  consumed_action_id uuid
);
CREATE UNIQUE INDEX approvals_one_active_per_plan ON approvals (plan_id) WHERE status = 'ACTIVE';

CREATE TABLE actions (
  id uuid PRIMARY KEY,
  approval_id uuid NOT NULL UNIQUE REFERENCES approvals(id),
  plan_id uuid NOT NULL REFERENCES plans(id),
  tenant_id text NOT NULL,
  service_id text NOT NULL,
  actor_id text NOT NULL,
  target_key text NOT NULL,
  executor text NOT NULL,
  status text NOT NULL,
  before_state jsonb,
  after_state jsonb,
  operation_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  verification jsonb,
  recovery jsonb,
  error jsonb,
  memory_sync_status text NOT NULL DEFAULT 'NOT_REQUIRED',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  verified_at timestamptz
);
CREATE UNIQUE INDEX actions_one_active_per_target ON actions (target_key)
  WHERE status IN ('QUEUED', 'EXECUTING', 'PENDING_VERIFICATION', 'RECOVERING', 'RECOVERY_REQUIRED');

CREATE TABLE action_journal (
  action_id uuid NOT NULL REFERENCES actions(id),
  seq integer NOT NULL,
  at timestamptz NOT NULL DEFAULT now(),
  stage text NOT NULL,
  detail jsonb NOT NULL,
  PRIMARY KEY (action_id, seq)
);

-- One durable global mutation slot for trials, actions and recovery (P0).
CREATE TABLE execution_slot (
  id integer PRIMARY KEY CHECK (id = 1),
  holder_kind text,
  holder_id uuid,
  acquired_at timestamptz
);
INSERT INTO execution_slot (id) VALUES (1);

CREATE TABLE jobs (
  id uuid PRIMARY KEY,
  kind text NOT NULL CHECK (kind IN ('investigation', 'trial', 'action', 'memory_outbox')),
  ref_id uuid NOT NULL,
  status text NOT NULL CHECK (status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED')),
  attempts integer NOT NULL DEFAULT 0,
  lease_owner text,
  lease_expires_at timestamptz,
  run_after timestamptz NOT NULL DEFAULT now(),
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON jobs (status, run_after);

CREATE TABLE idempotency (
  actor_id text NOT NULL,
  idem_key uuid NOT NULL,
  method text NOT NULL,
  route text NOT NULL,
  request_hash text NOT NULL,
  status_code integer,
  response jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (actor_id, idem_key)
);

CREATE TABLE model_calls (
  id uuid PRIMARY KEY,
  investigation_id uuid REFERENCES investigations(id),
  trial_id uuid REFERENCES trials(id),
  role text NOT NULL,
  model_id text NOT NULL,
  runtime_mode text NOT NULL,
  status text NOT NULL,
  input_tokens integer,
  output_tokens integer,
  tool_calls integer NOT NULL DEFAULT 0,
  requests integer NOT NULL DEFAULT 1,
  duration_ms integer NOT NULL,
  error_code text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE memory_outbox (
  id uuid PRIMARY KEY,
  tenant_id text NOT NULL,
  service_id text NOT NULL,
  receipt_kind text NOT NULL,
  application_receipt_id uuid NOT NULL UNIQUE,
  source_ref text NOT NULL,
  signature text,
  envelope jsonb NOT NULL,
  content_hash text NOT NULL,
  status text NOT NULL CHECK (status IN ('PENDING', 'SENT', 'FAILED')),
  attempts integer NOT NULL DEFAULT 0,
  engine_memory_id text,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz
);

CREATE TABLE memory_corrections (
  id uuid PRIMARY KEY,
  tenant_id text NOT NULL,
  service_id text NOT NULL,
  superseded_receipt_id uuid NOT NULL REFERENCES memory_outbox(application_receipt_id),
  new_receipt_id uuid NOT NULL,
  correction jsonb NOT NULL,
  review_hash text NOT NULL,
  reviewer text REFERENCES actors(actor_id),
  status text NOT NULL CHECK (status IN ('PREVIEW', 'APPLIED')),
  created_at timestamptz NOT NULL DEFAULT now()
);
