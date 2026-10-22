-- LEXA Phase 1: security, transactional outbox, idempotency and audit hardening.
-- Additive and non-destructive. Production must receive this only after branch validation.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lexa_app') THEN
    CREATE ROLE lexa_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
  END IF;
END $$;

GRANT lexa_app TO CURRENT_USER;
GRANT USAGE ON SCHEMA public TO lexa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO lexa_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO lexa_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO lexa_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO lexa_app;

CREATE TABLE IF NOT EXISTS role_permissions (
  role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  permission_id uuid NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
  PRIMARY KEY (role_id, permission_id)
);

CREATE INDEX IF NOT EXISTS idx_role_permissions_permission ON role_permissions(permission_id);

CREATE TABLE IF NOT EXISTS outbox_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  event_type varchar(100) NOT NULL,
  event_version integer NOT NULL DEFAULT 1,
  aggregate_type varchar(80) NOT NULL,
  aggregate_id uuid NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  recorded_at timestamptz NOT NULL DEFAULT now(),
  actor_id uuid REFERENCES users(id) ON DELETE SET NULL,
  correlation_id uuid,
  causation_id uuid,
  idempotency_key varchar(200),
  payload jsonb NOT NULL,
  status varchar(30) NOT NULL DEFAULT 'PENDING',
  attempt_count integer NOT NULL DEFAULT 0,
  available_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT outbox_events_status_check CHECK (status IN ('PENDING','PROCESSING','PUBLISHED','FAILED','DEAD_LETTER')),
  CONSTRAINT outbox_events_attempt_check CHECK (attempt_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_outbox_status_available ON outbox_events(status, available_at);
CREATE INDEX IF NOT EXISTS idx_outbox_tenant_occurred ON outbox_events(tenant_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_outbox_aggregate ON outbox_events(aggregate_type, aggregate_id);
CREATE INDEX IF NOT EXISTS idx_outbox_correlation ON outbox_events(correlation_id);

CREATE TABLE IF NOT EXISTS event_consumptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  consumer_name varchar(150) NOT NULL,
  event_id uuid NOT NULL REFERENCES outbox_events(id) ON DELETE RESTRICT,
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  processed_at timestamptz,
  status varchar(30) NOT NULL DEFAULT 'PROCESSED',
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (consumer_name, event_id),
  CONSTRAINT event_consumptions_status_check CHECK (status IN ('PROCESSED','FAILED','DEAD_LETTER'))
);

CREATE INDEX IF NOT EXISTS idx_event_consumptions_tenant ON event_consumptions(tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS idempotency_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  idempotency_key varchar(200) NOT NULL,
  operation_type varchar(120) NOT NULL,
  request_hash varchar(128) NOT NULL,
  response_status integer,
  response_body jsonb,
  resource_type varchar(100),
  resource_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz,
  UNIQUE (tenant_id, idempotency_key, operation_type)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_tenant_created ON idempotency_records(tenant_id, created_at DESC);

ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_consumptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency_records ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS role_permissions_tenant_isolation ON role_permissions;
CREATE POLICY role_permissions_tenant_isolation ON role_permissions
USING (EXISTS (
  SELECT 1 FROM roles r
  WHERE r.id = role_id
    AND r.tenant_id = current_setting('app.tenant_id', true)::uuid
))
WITH CHECK (EXISTS (
  SELECT 1 FROM roles r
  WHERE r.id = role_id
    AND r.tenant_id = current_setting('app.tenant_id', true)::uuid
));

DROP POLICY IF EXISTS outbox_events_tenant_isolation ON outbox_events;
CREATE POLICY outbox_events_tenant_isolation ON outbox_events
USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

DROP POLICY IF EXISTS event_consumptions_tenant_isolation ON event_consumptions;
CREATE POLICY event_consumptions_tenant_isolation ON event_consumptions
USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

DROP POLICY IF EXISTS idempotency_records_tenant_isolation ON idempotency_records;
CREATE POLICY idempotency_records_tenant_isolation ON idempotency_records
USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- The application connection uses the database owner role, so FORCE RLS is required.
DO $$
DECLARE table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'tenant_memberships','audit_logs','roles','membership_roles','business_profiles',
    'branches','warehouses','locations','pos_terminals','devices','sessions',
    'role_permissions','outbox_events','event_consumptions','idempotency_records'
  ] LOOP
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
  END LOOP;
END $$;

-- Audit records are append-only from the application perspective.
CREATE OR REPLACE FUNCTION prevent_audit_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'audit_logs is append-only';
END;
$$;

DROP TRIGGER IF EXISTS audit_logs_append_only ON audit_logs;
CREATE TRIGGER audit_logs_append_only
BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();

-- Prevent a role from another tenant being attached to a membership.
CREATE OR REPLACE FUNCTION validate_membership_role_tenant()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE membership_tenant uuid;
DECLARE role_tenant uuid;
BEGIN
  SELECT tenant_id INTO membership_tenant FROM tenant_memberships WHERE id = NEW.membership_id;
  SELECT tenant_id INTO role_tenant FROM roles WHERE id = NEW.role_id;
  IF membership_tenant IS NULL OR role_tenant IS NULL OR membership_tenant <> role_tenant THEN
    RAISE EXCEPTION 'membership and role must belong to the same tenant';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS membership_roles_tenant_guard ON membership_roles;
CREATE TRIGGER membership_roles_tenant_guard
BEFORE INSERT OR UPDATE ON membership_roles
FOR EACH ROW EXECUTE FUNCTION validate_membership_role_tenant();

-- Record this migration only after all statements above succeed.
CREATE TABLE IF NOT EXISTS schema_migrations (
  version varchar(100) PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO schema_migrations(version) VALUES ('001_phase1_foundation'), ('002_identity_rbac_organization'), ('003_rbac_sessions_organization_completion'), ('006_phase1_security_reliability')
ON CONFLICT (version) DO NOTHING;
