-- LEXA Strategic Phase 2: Universal Business Engine
-- Additive-only. Builds on the Phase 1 kernel, catalog and inventory.
-- Target: LEXA project wispy-mud-75323042, branch br-soft-star-b1dj2m2w, database neondb.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS business_capabilities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  code varchar(100) NOT NULL,
  name varchar(180) NOT NULL,
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  enabled boolean NOT NULL DEFAULT true,
  configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
  version integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT business_capabilities_status_check CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED')),
  CONSTRAINT business_capabilities_version_check CHECK (version > 0),
  CONSTRAINT business_capabilities_tenant_code_key UNIQUE (tenant_id, code),
  CONSTRAINT business_capabilities_tenant_id_id_key UNIQUE (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS business_configurations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  config_key varchar(160) NOT NULL,
  value_json jsonb,
  value_type varchar(30) NOT NULL DEFAULT 'JSON',
  version integer NOT NULL DEFAULT 1,
  updated_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT business_configurations_value_type_check CHECK (value_type IN ('JSON','STRING','NUMBER','BOOLEAN')),
  CONSTRAINT business_configurations_version_check CHECK (version > 0),
  CONSTRAINT business_configurations_tenant_key_key UNIQUE (tenant_id, config_key),
  CONSTRAINT business_configurations_tenant_id_id_key UNIQUE (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS party_relationships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  from_party_id uuid NOT NULL,
  to_party_id uuid NOT NULL,
  relationship_type varchar(80) NOT NULL,
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  valid_from timestamptz,
  valid_to timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT party_relationships_status_check CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED')),
  CONSTRAINT party_relationships_dates_check CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
  CONSTRAINT party_relationships_not_self_check CHECK (from_party_id <> to_party_id),
  CONSTRAINT party_relationships_unique UNIQUE (tenant_id, from_party_id, to_party_id, relationship_type),
  CONSTRAINT party_relationships_tenant_from_fk FOREIGN KEY (tenant_id, from_party_id) REFERENCES parties(tenant_id, id) ON DELETE CASCADE,
  CONSTRAINT party_relationships_tenant_to_fk FOREIGN KEY (tenant_id, to_party_id) REFERENCES parties(tenant_id, id) ON DELETE CASCADE,
  CONSTRAINT party_relationships_tenant_id_id_key UNIQUE (tenant_id, id)
);
CREATE INDEX IF NOT EXISTS idx_party_relationships_from ON party_relationships(tenant_id, from_party_id, status);
CREATE INDEX IF NOT EXISTS idx_party_relationships_to ON party_relationships(tenant_id, to_party_id, status);

CREATE TABLE IF NOT EXISTS transaction_types (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  code varchar(80) NOT NULL,
  name varchar(160) NOT NULL,
  category varchar(60) NOT NULL DEFAULT 'GENERAL',
  initial_status varchar(40) NOT NULL DEFAULT 'DRAFT',
  statuses jsonb NOT NULL DEFAULT '["DRAFT","CONFIRMED","COMPLETED","CANCELLED"]'::jsonb,
  transitions jsonb NOT NULL DEFAULT '{"DRAFT":["CONFIRMED","CANCELLED"],"CONFIRMED":["COMPLETED","CANCELLED"]}'::jsonb,
  active boolean NOT NULL DEFAULT true,
  configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT transaction_types_tenant_code_key UNIQUE (tenant_id, code),
  CONSTRAINT transaction_types_tenant_id_id_key UNIQUE (tenant_id, id)
);

ALTER TABLE business_transactions ADD COLUMN IF NOT EXISTS source_transaction_id uuid REFERENCES business_transactions(id) ON DELETE SET NULL;
ALTER TABLE business_transactions ADD COLUMN IF NOT EXISTS closed_at timestamptz;
CREATE INDEX IF NOT EXISTS idx_business_transactions_source ON business_transactions(tenant_id, source_transaction_id);

-- Existing Phase 1 models lacked composite tenant keys on a few universal tables;
-- create them before Phase 2 composite foreign keys reference the columns.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'services_tenant_id_id_key') THEN
    ALTER TABLE services ADD CONSTRAINT services_tenant_id_id_key UNIQUE (tenant_id, id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'resources_tenant_id_id_key') THEN
    ALTER TABLE resources ADD CONSTRAINT resources_tenant_id_id_key UNIQUE (tenant_id, id);
  END IF;
END$$;
CREATE INDEX IF NOT EXISTS idx_services_tenant_status ON services(tenant_id, status, name);
CREATE INDEX IF NOT EXISTS idx_resources_tenant_status ON resources(tenant_id, status, name);

CREATE TABLE IF NOT EXISTS transaction_lines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  transaction_id uuid NOT NULL,
  line_no integer NOT NULL,
  line_type varchar(20) NOT NULL DEFAULT 'MISC',
  product_variant_id uuid,
  service_id uuid,
  resource_id uuid,
  description text,
  quantity numeric(20,6) NOT NULL DEFAULT 1,
  unit_price numeric(20,6) NOT NULL DEFAULT 0,
  line_total numeric(20,4) NOT NULL DEFAULT 0,
  currency_code varchar(3) NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT transaction_lines_line_no_check CHECK (line_no > 0),
  CONSTRAINT transaction_lines_type_check CHECK (line_type IN ('PRODUCT','SERVICE','MISC')),
  CONSTRAINT transaction_lines_quantity_check CHECK (quantity > 0),
  CONSTRAINT transaction_lines_unit_price_check CHECK (unit_price >= 0),
  CONSTRAINT transaction_lines_total_check CHECK (line_total >= 0),
  CONSTRAINT transaction_lines_reference_check CHECK (
    (line_type = 'PRODUCT' AND product_variant_id IS NOT NULL AND service_id IS NULL) OR
    (line_type = 'SERVICE' AND service_id IS NOT NULL AND product_variant_id IS NULL) OR
    (line_type = 'MISC' AND product_variant_id IS NULL AND service_id IS NULL)
  ),
  CONSTRAINT transaction_lines_tenant_transaction_fk FOREIGN KEY (tenant_id, transaction_id) REFERENCES business_transactions(tenant_id, id) ON DELETE CASCADE,
  CONSTRAINT transaction_lines_tenant_id_id_key UNIQUE (tenant_id, id),
  CONSTRAINT transaction_lines_tenant_variant_fk FOREIGN KEY (tenant_id, product_variant_id) REFERENCES product_variants(tenant_id, id) ON DELETE RESTRICT,
  CONSTRAINT transaction_lines_tenant_service_fk FOREIGN KEY (tenant_id, service_id) REFERENCES services(tenant_id, id) ON DELETE RESTRICT,
  CONSTRAINT transaction_lines_tenant_resource_fk FOREIGN KEY (tenant_id, resource_id) REFERENCES resources(tenant_id, id) ON DELETE RESTRICT,
  CONSTRAINT transaction_lines_transaction_line_no_key UNIQUE (tenant_id, transaction_id, line_no)
);
CREATE INDEX IF NOT EXISTS idx_transaction_lines_transaction ON transaction_lines(tenant_id, transaction_id, line_no);

CREATE TABLE IF NOT EXISTS transaction_status_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  transaction_id uuid NOT NULL,
  from_status varchar(40),
  to_status varchar(40) NOT NULL,
  reason text,
  changed_by uuid REFERENCES users(id) ON DELETE SET NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  changed_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT transaction_status_history_tenant_transaction_fk FOREIGN KEY (tenant_id, transaction_id) REFERENCES business_transactions(tenant_id, id) ON DELETE CASCADE,
  CONSTRAINT transaction_status_history_tenant_id_id_key UNIQUE (tenant_id, id)
);
CREATE INDEX IF NOT EXISTS idx_transaction_status_history_transaction ON transaction_status_history(tenant_id, transaction_id, changed_at DESC);

CREATE TABLE IF NOT EXISTS workflow_definitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  code varchar(100) NOT NULL,
  name varchar(180) NOT NULL,
  description text,
  status varchar(30) NOT NULL DEFAULT 'DRAFT',
  trigger_event varchar(120),
  version integer NOT NULL DEFAULT 1,
  configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT workflow_definitions_status_check CHECK (status IN ('DRAFT','ACTIVE','ARCHIVED')),
  CONSTRAINT workflow_definitions_version_check CHECK (version > 0),
  CONSTRAINT workflow_definitions_tenant_code_key UNIQUE (tenant_id, code),
  CONSTRAINT workflow_definitions_tenant_id_id_key UNIQUE (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS workflow_steps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  workflow_definition_id uuid NOT NULL,
  step_key varchar(100) NOT NULL,
  name varchar(180) NOT NULL,
  step_type varchar(30) NOT NULL DEFAULT 'TASK',
  position integer NOT NULL,
  configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT workflow_steps_type_check CHECK (step_type IN ('TASK','APPROVAL','ACTION','CONDITION','NOTIFICATION')),
  CONSTRAINT workflow_steps_position_check CHECK (position > 0),
  CONSTRAINT workflow_steps_tenant_definition_fk FOREIGN KEY (tenant_id, workflow_definition_id) REFERENCES workflow_definitions(tenant_id, id) ON DELETE CASCADE,
  CONSTRAINT workflow_steps_tenant_id_id_key UNIQUE (tenant_id, id),
  CONSTRAINT workflow_steps_definition_key UNIQUE (tenant_id, workflow_definition_id, step_key),
  CONSTRAINT workflow_steps_definition_position_key UNIQUE (tenant_id, workflow_definition_id, position)
);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_definition ON workflow_steps(tenant_id, workflow_definition_id, position);

CREATE TABLE IF NOT EXISTS workflow_instances (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  workflow_definition_id uuid NOT NULL,
  entity_type varchar(80) NOT NULL,
  entity_id uuid NOT NULL,
  current_step_id uuid,
  status varchar(30) NOT NULL DEFAULT 'RUNNING',
  context jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  CONSTRAINT workflow_instances_status_check CHECK (status IN ('RUNNING','PAUSED','COMPLETED','FAILED','CANCELLED')),
  CONSTRAINT workflow_instances_tenant_definition_fk FOREIGN KEY (tenant_id, workflow_definition_id) REFERENCES workflow_definitions(tenant_id, id) ON DELETE RESTRICT,
  CONSTRAINT workflow_instances_tenant_step_fk FOREIGN KEY (tenant_id, current_step_id) REFERENCES workflow_steps(tenant_id, id) ON DELETE SET NULL,
  CONSTRAINT workflow_instances_tenant_id_id_key UNIQUE (tenant_id, id)
);
CREATE INDEX IF NOT EXISTS idx_workflow_instances_entity ON workflow_instances(tenant_id, entity_type, entity_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_instances_status ON workflow_instances(tenant_id, status, started_at DESC);

CREATE TABLE IF NOT EXISTS workflow_step_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  workflow_instance_id uuid NOT NULL,
  workflow_step_id uuid NOT NULL,
  status varchar(30) NOT NULL DEFAULT 'RUNNING',
  output jsonb NOT NULL DEFAULT '{}'::jsonb,
  task_id uuid REFERENCES tasks(id) ON DELETE SET NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  CONSTRAINT workflow_step_runs_status_check CHECK (status IN ('RUNNING','COMPLETED','SKIPPED','FAILED')),
  CONSTRAINT workflow_step_runs_tenant_instance_fk FOREIGN KEY (tenant_id, workflow_instance_id) REFERENCES workflow_instances(tenant_id, id) ON DELETE CASCADE,
  CONSTRAINT workflow_step_runs_tenant_step_fk FOREIGN KEY (tenant_id, workflow_step_id) REFERENCES workflow_steps(tenant_id, id) ON DELETE RESTRICT,
  CONSTRAINT workflow_step_runs_tenant_id_id_key UNIQUE (tenant_id, id)
);
CREATE INDEX IF NOT EXISTS idx_workflow_step_runs_instance ON workflow_step_runs(tenant_id, workflow_instance_id, started_at);

GRANT SELECT, INSERT, UPDATE, DELETE ON business_capabilities TO lexa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON business_configurations TO lexa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON party_relationships TO lexa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON transaction_types TO lexa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON transaction_lines TO lexa_app;
GRANT SELECT, INSERT ON transaction_status_history TO lexa_app;
REVOKE UPDATE, DELETE ON transaction_status_history FROM lexa_app;
REVOKE UPDATE, DELETE ON transaction_status_history FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON workflow_definitions TO lexa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON workflow_steps TO lexa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON workflow_instances TO lexa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON workflow_step_runs TO lexa_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO lexa_app;

ALTER TABLE business_capabilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_capabilities FORCE ROW LEVEL SECURITY;
ALTER TABLE business_configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_configurations FORCE ROW LEVEL SECURITY;
ALTER TABLE party_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE party_relationships FORCE ROW LEVEL SECURITY;
ALTER TABLE transaction_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE transaction_types FORCE ROW LEVEL SECURITY;
ALTER TABLE transaction_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE transaction_lines FORCE ROW LEVEL SECURITY;
ALTER TABLE transaction_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE transaction_status_history FORCE ROW LEVEL SECURITY;
ALTER TABLE workflow_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_definitions FORCE ROW LEVEL SECURITY;
ALTER TABLE workflow_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_steps FORCE ROW LEVEL SECURITY;
ALTER TABLE workflow_instances ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_instances FORCE ROW LEVEL SECURITY;
ALTER TABLE workflow_step_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_step_runs FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS business_capabilities_tenant_isolation ON business_capabilities;
CREATE POLICY business_capabilities_tenant_isolation ON business_capabilities FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
DROP POLICY IF EXISTS business_configurations_tenant_isolation ON business_configurations;
CREATE POLICY business_configurations_tenant_isolation ON business_configurations FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
DROP POLICY IF EXISTS party_relationships_tenant_isolation ON party_relationships;
CREATE POLICY party_relationships_tenant_isolation ON party_relationships FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
DROP POLICY IF EXISTS transaction_types_tenant_isolation ON transaction_types;
CREATE POLICY transaction_types_tenant_isolation ON transaction_types FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
DROP POLICY IF EXISTS transaction_lines_tenant_isolation ON transaction_lines;
CREATE POLICY transaction_lines_tenant_isolation ON transaction_lines FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
DROP POLICY IF EXISTS transaction_status_history_tenant_read ON transaction_status_history;
CREATE POLICY transaction_status_history_tenant_read ON transaction_status_history FOR SELECT USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
DROP POLICY IF EXISTS transaction_status_history_tenant_insert ON transaction_status_history;
CREATE POLICY transaction_status_history_tenant_insert ON transaction_status_history FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

CREATE OR REPLACE FUNCTION lexa_prevent_transaction_status_history_mutation()
RETURNS trigger LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'transaction_status_history is append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_transaction_status_history_immutable ON transaction_status_history;
CREATE TRIGGER trg_transaction_status_history_immutable
BEFORE UPDATE OR DELETE ON transaction_status_history
FOR EACH ROW EXECUTE FUNCTION lexa_prevent_transaction_status_history_mutation();
DROP POLICY IF EXISTS workflow_definitions_tenant_isolation ON workflow_definitions;
CREATE POLICY workflow_definitions_tenant_isolation ON workflow_definitions FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
DROP POLICY IF EXISTS workflow_steps_tenant_isolation ON workflow_steps;
CREATE POLICY workflow_steps_tenant_isolation ON workflow_steps FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
DROP POLICY IF EXISTS workflow_instances_tenant_isolation ON workflow_instances;
CREATE POLICY workflow_instances_tenant_isolation ON workflow_instances FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
DROP POLICY IF EXISTS workflow_step_runs_tenant_isolation ON workflow_step_runs;
CREATE POLICY workflow_step_runs_tenant_isolation ON workflow_step_runs FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

INSERT INTO permissions (code, description) VALUES
  ('business.read','Read business configuration and capabilities'),
  ('business.manage','Manage business configuration and capabilities'),
  ('transactions.read','Read universal business transactions'),
  ('transactions.manage','Create and transition universal business transactions'),
  ('workflows.read','Read workflow definitions and runs'),
  ('workflows.manage','Create and execute workflow definitions and runs'),
  ('context.read','Read authorized universal business context')
ON CONFLICT (code) DO UPDATE SET description = EXCLUDED.description;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r CROSS JOIN permissions p
WHERE r.name='Owner'
  AND p.code IN ('business.read','business.manage','transactions.read','transactions.manage','workflows.read','workflows.manage','context.read')
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION lexa_seed_business_engine(p_tenant_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO business_capabilities (tenant_id, code, name, enabled, configuration)
  VALUES
    (p_tenant_id,'CATALOG','Universal Catalog',true,'{}'::jsonb),
    (p_tenant_id,'INVENTORY','Inventory Operations',true,'{}'::jsonb),
    (p_tenant_id,'SALES','Sales Operations',true,'{}'::jsonb),
    (p_tenant_id,'PROCUREMENT','Procurement',true,'{}'::jsonb),
    (p_tenant_id,'CRM','Customer Relationships',true,'{}'::jsonb),
    (p_tenant_id,'WORKFLOWS','Business Workflows',true,'{}'::jsonb),
    (p_tenant_id,'INTELLIGENCE','Business Intelligence',true,'{}'::jsonb)
  ON CONFLICT (tenant_id, code) DO NOTHING;

  INSERT INTO business_configurations (tenant_id, config_key, value_json, value_type)
  SELECT p_tenant_id, 'business.operating_country', to_jsonb(coalesce(bp.country_code,'UG')), 'STRING'
  FROM business_profiles bp WHERE bp.tenant_id = p_tenant_id
  UNION ALL
  SELECT p_tenant_id, 'business.currency', to_jsonb(coalesce(bp.currency_code,'UGX')), 'STRING'
  FROM business_profiles bp WHERE bp.tenant_id = p_tenant_id
  ON CONFLICT (tenant_id, config_key) DO NOTHING;

  INSERT INTO transaction_types (tenant_id, code, name, category, initial_status, statuses, transitions, configuration) VALUES
    (p_tenant_id,'QUOTE','Quotation','COMMERCE','DRAFT','["DRAFT","SENT","ACCEPTED","REJECTED","CANCELLED","EXPIRED"]'::jsonb,'{"DRAFT":["SENT","CANCELLED"],"SENT":["ACCEPTED","REJECTED","EXPIRED","CANCELLED"],"ACCEPTED":["CANCELLED"]}'::jsonb,'{}'::jsonb),
    (p_tenant_id,'ORDER','Order','COMMERCE','DRAFT','["DRAFT","CONFIRMED","FULFILLING","COMPLETED","CANCELLED"]'::jsonb,'{"DRAFT":["CONFIRMED","CANCELLED"],"CONFIRMED":["FULFILLING","CANCELLED"],"FULFILLING":["COMPLETED","CANCELLED"]}'::jsonb,'{}'::jsonb),
    (p_tenant_id,'FULFILLMENT','Fulfillment','OPERATIONS','DRAFT','["DRAFT","DISPATCHED","RECEIVED","CANCELLED"]'::jsonb,'{"DRAFT":["DISPATCHED","CANCELLED"],"DISPATCHED":["RECEIVED","CANCELLED"]}'::jsonb,'{}'::jsonb),
    (p_tenant_id,'INVOICE','Invoice','FINANCE','DRAFT','["DRAFT","ISSUED","PARTIALLY_PAID","PAID","OVERDUE","CANCELLED"]'::jsonb,'{"DRAFT":["ISSUED","CANCELLED"],"ISSUED":["PARTIALLY_PAID","PAID","OVERDUE","CANCELLED"],"PARTIALLY_PAID":["PAID","OVERDUE","CANCELLED"],"OVERDUE":["PAID","CANCELLED"]}'::jsonb,'{}'::jsonb),
    (p_tenant_id,'PURCHASE_ORDER','Purchase Order','PROCUREMENT','DRAFT','["DRAFT","SUBMITTED","CONFIRMED","RECEIVING","COMPLETED","CANCELLED"]'::jsonb,'{"DRAFT":["SUBMITTED","CANCELLED"],"SUBMITTED":["CONFIRMED","CANCELLED"],"CONFIRMED":["RECEIVING","COMPLETED","CANCELLED"],"RECEIVING":["COMPLETED","CANCELLED"]}'::jsonb,'{}'::jsonb),
    (p_tenant_id,'SETTLEMENT','Settlement','FINANCE','DRAFT','["DRAFT","POSTED","RECONCILED","CANCELLED"]'::jsonb,'{"DRAFT":["POSTED","CANCELLED"],"POSTED":["RECONCILED","CANCELLED"]}'::jsonb,'{}'::jsonb)
  ON CONFLICT (tenant_id, code) DO NOTHING;
END;
$$;

SELECT lexa_seed_business_engine(id) FROM tenants;

INSERT INTO schema_migrations(version) VALUES ('013_phase2_universal_business_engine') ON CONFLICT (version) DO NOTHING;
