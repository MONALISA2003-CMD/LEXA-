-- LEXA Phase 1/2 hardening: workspace registration reliability.
-- Additive and non-destructive. No reset, delete, or reseed of business data.

CREATE TABLE IF NOT EXISTS registration_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  idempotency_key varchar(200) NOT NULL,
  email varchar(320) NOT NULL,
  request_hash varchar(128) NOT NULL,
  response_status integer,
  response_body jsonb,
  user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  tenant_id uuid REFERENCES tenants(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL DEFAULT (now() + interval '24 hours'),
  UNIQUE (idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_registration_requests_email ON registration_requests(email);
CREATE INDEX IF NOT EXISTS idx_registration_requests_expires ON registration_requests(expires_at);

GRANT SELECT, INSERT, UPDATE, DELETE ON registration_requests TO lexa_app;

INSERT INTO schema_migrations (version)
VALUES ('008_workspace_registration_hardening')
ON CONFLICT (version) DO NOTHING;
