CREATE TABLE IF NOT EXISTS incidents (
  incident_id TEXT PRIMARY KEY,
  current_layer TEXT NOT NULL,
  completed_layers JSONB NOT NULL DEFAULT '[]'::jsonb,
  state_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS runs (
  id BIGSERIAL PRIMARY KEY,
  incident_id TEXT NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
  layer TEXT NOT NULL,
  status TEXT NOT NULL,
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGSERIAL PRIMARY KEY,
  incident_id TEXT NOT NULL,
  action TEXT NOT NULL,
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidence_files (
  id BIGSERIAL PRIMARY KEY,
  incident_id TEXT NOT NULL,
  payload_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS normalized_records (
  id BIGSERIAL PRIMARY KEY,
  incident_id TEXT NOT NULL,
  payload_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pii_findings (
  id BIGSERIAL PRIMARY KEY,
  incident_id TEXT NOT NULL,
  payload_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS identity_links (
  id BIGSERIAL PRIMARY KEY,
  incident_id TEXT NOT NULL,
  payload_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS affected_people (
  id BIGSERIAL PRIMARY KEY,
  incident_id TEXT NOT NULL,
  payload_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS drafts (
  id BIGSERIAL PRIMARY KEY,
  incident_id TEXT NOT NULL,
  payload_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_runs_incident ON runs(incident_id);
CREATE INDEX IF NOT EXISTS idx_audit_incident ON audit_logs(incident_id);
