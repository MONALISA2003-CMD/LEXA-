-- LEXA Phase 6A brain foundation
-- Reconstructs the live LEXA brain persistence layer so fresh environments can reproduce it.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS brain_model_routes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  task_type varchar NOT NULL, complexity varchar NOT NULL DEFAULT 'STANDARD', execution_mode varchar NOT NULL DEFAULT 'DETERMINISTIC',
  handler_key varchar, provider_ref varchar, model_name varchar, priority integer NOT NULL DEFAULT 100, enabled boolean NOT NULL DEFAULT true,
  configuration jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT brain_model_routes_tenant_id_id_key UNIQUE (tenant_id,id),
  CONSTRAINT brain_model_routes_complexity_check CHECK (complexity IN ('LOW','STANDARD','HIGH')),
  CONSTRAINT brain_model_routes_execution_mode_check CHECK (execution_mode IN ('DETERMINISTIC','MODEL')),
  CONSTRAINT brain_model_routes_priority_check CHECK (priority >= 0),
  CONSTRAINT brain_model_routes_tenant_id_task_type_complexity_priority_key UNIQUE (tenant_id,task_type,complexity,priority)
);
CREATE INDEX IF NOT EXISTS idx_brain_model_routes_tenant_priority ON brain_model_routes (tenant_id,task_type,complexity,priority);

CREATE TABLE IF NOT EXISTS brain_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, actor_user_id uuid NOT NULL REFERENCES users(id) DEFERRABLE,
  task_type varchar NOT NULL, safety_level smallint NOT NULL DEFAULT 0, status varchar NOT NULL DEFAULT 'RUNNING', input_text text NOT NULL,
  context_json jsonb NOT NULL DEFAULT '{}'::jsonb, selected_route_id uuid NULL, output_text text NULL, confidence numeric NULL,
  assumptions jsonb NOT NULL DEFAULT '[]'::jsonb, started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz NULL, error_message text NULL, correlation_id uuid NULL,
  CONSTRAINT brain_runs_tenant_id_id_key UNIQUE (tenant_id,id),
  CONSTRAINT brain_runs_safety_level_check CHECK (safety_level BETWEEN 0 AND 3),
  CONSTRAINT brain_runs_status_check CHECK (status IN ('RUNNING','SUCCEEDED','FAILED','CANCELLED')),
  CONSTRAINT brain_runs_confidence_check CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  CONSTRAINT fk_brain_run_route_tenant FOREIGN KEY (tenant_id,selected_route_id) REFERENCES brain_model_routes(tenant_id,id) DEFERRABLE
);
CREATE INDEX IF NOT EXISTS idx_brain_runs_tenant_started ON brain_runs (tenant_id,started_at DESC);

CREATE TABLE IF NOT EXISTS brain_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, brain_run_id uuid NOT NULL,
  evidence_type varchar NOT NULL, source_type varchar NOT NULL, source_id uuid, claim text NOT NULL, value_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  freshness_at timestamptz, confidence numeric NOT NULL DEFAULT 1, citation_label varchar, created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT brain_evidence_tenant_id_id_key UNIQUE (tenant_id,id),
  CONSTRAINT brain_evidence_evidence_type_check CHECK (evidence_type IN ('TRANSACTION','ANALYTIC','MEMORY','MODEL','ASSUMPTION')),
  CONSTRAINT brain_evidence_confidence_check CHECK (confidence BETWEEN 0 AND 1),
  CONSTRAINT fk_brain_evidence_run_tenant FOREIGN KEY (tenant_id,brain_run_id) REFERENCES brain_runs(tenant_id,id) ON DELETE CASCADE DEFERRABLE
);
CREATE INDEX IF NOT EXISTS idx_brain_evidence_run ON brain_evidence (tenant_id,brain_run_id);

CREATE TABLE IF NOT EXISTS brain_memories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, memory_type varchar NOT NULL,
  title varchar NOT NULL, content text NOT NULL, source_type varchar, source_id uuid, entity_type varchar, entity_id uuid, confidence numeric NOT NULL DEFAULT 1,
  last_verified_at timestamptz, valid_until timestamptz, status varchar NOT NULL DEFAULT 'ACTIVE', metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid REFERENCES users(id) ON DELETE SET NULL, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT brain_memories_tenant_id_id_key UNIQUE (tenant_id,id),
  CONSTRAINT brain_memories_memory_type_check CHECK (memory_type IN ('FACT','PREFERENCE','OPERATING_RULE','OBSERVED_PATTERN','DECISION','OUTCOME')),
  CONSTRAINT brain_memories_status_check CHECK (status IN ('ACTIVE','EXPIRED','ARCHIVED')),
  CONSTRAINT brain_memories_confidence_check CHECK (confidence BETWEEN 0 AND 1),
  CONSTRAINT brain_memories_check CHECK (valid_until IS NULL OR valid_until >= created_at)
);
CREATE INDEX IF NOT EXISTS idx_brain_memories_entity ON brain_memories (tenant_id,entity_type,entity_id,status);

CREATE TABLE IF NOT EXISTS brain_recommendations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, brain_run_id uuid NOT NULL,
  recommendation text NOT NULL, rationale text NOT NULL, confidence numeric NOT NULL DEFAULT 0, expected_impact text, risk text, next_action text,
  status varchar NOT NULL DEFAULT 'PROPOSED', created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT brain_recommendations_tenant_id_id_key UNIQUE (tenant_id,id),
  CONSTRAINT brain_recommendations_confidence_check CHECK (confidence BETWEEN 0 AND 1),
  CONSTRAINT brain_recommendations_status_check CHECK (status IN ('PROPOSED','ACKNOWLEDGED','REJECTED','EXPIRED')),
  CONSTRAINT fk_brain_recommendation_run_tenant FOREIGN KEY (tenant_id,brain_run_id) REFERENCES brain_runs(tenant_id,id) ON DELETE CASCADE DEFERRABLE
);
CREATE INDEX IF NOT EXISTS idx_brain_recommendations_status ON brain_recommendations (tenant_id,status,created_at DESC);

CREATE TABLE IF NOT EXISTS brain_tool_definitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, tool_key varchar NOT NULL, version integer NOT NULL DEFAULT 1,
  display_name varchar NOT NULL, tool_class varchar NOT NULL, description text NOT NULL, handler_key varchar NOT NULL, risk_level smallint NOT NULL DEFAULT 0,
  required_permission varchar, deterministic boolean NOT NULL DEFAULT true, enabled boolean NOT NULL DEFAULT true, input_schema jsonb NOT NULL DEFAULT '{}'::jsonb,
  output_schema jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT brain_tool_definitions_tenant_id_id_key UNIQUE (tenant_id,id),
  CONSTRAINT brain_tool_definitions_tenant_id_tool_key_version_key UNIQUE (tenant_id,tool_key,version),
  CONSTRAINT brain_tool_definitions_version_check CHECK (version > 0),
  CONSTRAINT brain_tool_definitions_risk_level_check CHECK (risk_level BETWEEN 0 AND 3),
  CONSTRAINT brain_tool_definitions_tool_class_check CHECK (tool_class IN ('READ','ANALYZE','PREDICT','RECOMMEND','PREPARE','EXECUTE'))
);

CREATE TABLE IF NOT EXISTS brain_tool_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, brain_run_id uuid NOT NULL, tool_definition_id uuid NOT NULL,
  status varchar NOT NULL, input_json jsonb NOT NULL DEFAULT '{}'::jsonb, output_json jsonb NOT NULL DEFAULT '{}'::jsonb, error_message text,
  started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz, CONSTRAINT brain_tool_runs_tenant_id_id_key UNIQUE (tenant_id,id),
  CONSTRAINT brain_tool_runs_status_check CHECK (status IN ('RUNNING','SUCCEEDED','FAILED','SKIPPED')),
  CONSTRAINT fk_brain_tool_run_brain_tenant FOREIGN KEY (tenant_id,brain_run_id) REFERENCES brain_runs(tenant_id,id) ON DELETE CASCADE DEFERRABLE,
  CONSTRAINT fk_brain_tool_run_definition_tenant FOREIGN KEY (tenant_id,tool_definition_id) REFERENCES brain_tool_definitions(tenant_id,id) DEFERRABLE
);
CREATE INDEX IF NOT EXISTS idx_brain_tool_runs_run ON brain_tool_runs (tenant_id,brain_run_id);

ALTER TABLE brain_model_routes ENABLE ROW LEVEL SECURITY; ALTER TABLE brain_runs ENABLE ROW LEVEL SECURITY; ALTER TABLE brain_evidence ENABLE ROW LEVEL SECURITY; ALTER TABLE brain_memories ENABLE ROW LEVEL SECURITY; ALTER TABLE brain_recommendations ENABLE ROW LEVEL SECURITY; ALTER TABLE brain_tool_definitions ENABLE ROW LEVEL SECURITY; ALTER TABLE brain_tool_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_model_routes FORCE ROW LEVEL SECURITY; ALTER TABLE brain_runs FORCE ROW LEVEL SECURITY; ALTER TABLE brain_evidence FORCE ROW LEVEL SECURITY; ALTER TABLE brain_memories FORCE ROW LEVEL SECURITY; ALTER TABLE brain_recommendations FORCE ROW LEVEL SECURITY; ALTER TABLE brain_tool_definitions FORCE ROW LEVEL SECURITY; ALTER TABLE brain_tool_runs FORCE ROW LEVEL SECURITY;

DO $$ DECLARE t text; BEGIN FOR t IN SELECT unnest(ARRAY['brain_model_routes','brain_runs','brain_evidence','brain_memories','brain_recommendations','brain_tool_definitions','brain_tool_runs']) LOOP EXECUTE format('DROP POLICY IF EXISTS %I_tenant_isolation ON %I', t, t); EXECUTE format('CREATE POLICY %I_tenant_isolation ON %I USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), )::uuid) WITH CHECK (tenant_id = NULLIF(current_setting(app.tenant_id, true), )::uuid)', t, t); END LOOP; END $$;

INSERT INTO schema_migrations(version) VALUES ('022_phase6a_brain_foundation') ON CONFLICT (version) DO NOTHING;
