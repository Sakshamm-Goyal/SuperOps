-- Ops Copilot conversations: advisory chat only. Nothing here is read by approval, execution or memory authority.
CREATE TABLE copilot_conversations (
    id uuid PRIMARY KEY,
    tenant_id text NOT NULL,
    actor_id text NOT NULL,
    investigation_id uuid,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE copilot_messages (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES copilot_conversations(id),
    seq integer NOT NULL,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL,
    tool_calls jsonb NOT NULL DEFAULT '[]',
    citations jsonb NOT NULL DEFAULT '[]',
    model_id text,
    input_tokens integer,
    output_tokens integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (conversation_id, seq)
);
