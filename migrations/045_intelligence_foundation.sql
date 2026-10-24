-- LEXA Phase 1 intelligence foundation. Forward-only, additive candidate migration.
-- Review and apply using the approved migration process; this file has NOT been run.
-- Phase 1 stores tenant-scoped job metadata and provenance only. No raw prompts,
-- document bytes, model output, provider secrets, or business mutations are stored.
-- Job rows are mutable to support a future idempotent worker. Run rows are
-- append-only for the runtime role, preserving finalized execution provenance.
BEGIN;

DO $$
BEGIN
  IF to_regclass('public.tenants') IS NULL
     OR to_regclass('public.branches') IS NULL
     OR to_regclass('public.users') IS NULL
     OR to_regclass('public.schema_migrations') IS NULL THEN
    RAISE EXCEPTION 'LEXA intelligence migration prerequisites are missing';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'lexa_app') THEN
    RAISE EXCEPTION 'LEXA application role lexa_app is missing';
  END IF;
  IF to_regprocedure('public.lexa_can_access_branch(uuid)') IS NULL THEN
    RAISE EXCEPTION 'LEXA branch-access function prerequisite is missing';
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.intelligence_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  branch_id uuid NULL,
  job_type varchar(40) NOT NULL CHECK (job_type IN (
    'business_insight', 'replenishment', 'classify', 'extract', 'explain',
    'summarize', 'analyze', 'forecast', 'reconcile', 'daily_brief'
  )),
  status varchar(16) NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED', 'DEAD_LETTER', 'CANCELLED')),
  idempotency_key varchar(128) NOT NULL
    CHECK (idempotency_key ~ '^[A-Za-z0-9._:-]{8,128}$'),
  source_type varchar(60) NULL CHECK (source_type IS NULL OR source_type IN (
    'sale', 'sale_return', 'payment', 'inventory_snapshot', 'inventory_movement',
    'product', 'customer', 'supplier', 'purchase_order', 'supplier_bill', 'expense',
    'journal_entry', 'receipt', 'document', 'analytics_projection', 'rule'
  )),
  source_id uuid NULL,
  -- Reference-only, bounded metadata. Never put user prompts, document OCR, or raw
  -- supplier/customer information here. Actual business rows are loaded via APIs.
  payload_ref jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (
    jsonb_typeof(payload_ref) = 'object'
    AND pg_column_size(payload_ref) <= 4096
    AND (payload_ref - ARRAY['business_date', 'currency_code', 'request_fingerprint', 'profile_code']) = '{}'::jsonb
    AND (NOT (payload_ref ? 'business_date') OR (
      jsonb_typeof(payload_ref->'business_date') = 'string'
      AND (payload_ref->>'business_date') ~ '^\d{4}-\d{2}-\d{2}$'
    ))
    AND (NOT (payload_ref ? 'currency_code') OR (
      jsonb_typeof(payload_ref->'currency_code') = 'string'
      AND (payload_ref->>'currency_code') ~ '^[A-Z]{3}$'
    ))
    AND (NOT (payload_ref ? 'request_fingerprint') OR (
      jsonb_typeof(payload_ref->'request_fingerprint') = 'string'
      AND (payload_ref->>'request_fingerprint') ~ '^[0-9a-f]{64}$'
    ))
    AND (NOT (payload_ref ? 'profile_code') OR (
      jsonb_typeof(payload_ref->'profile_code') = 'string'
      AND (payload_ref->>'profile_code') ~ '^[a-z][a-z0-9_.-]{0,79}$'
    ))
  ),
  attempt_count smallint NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND 20),
  available_at timestamptz NOT NULL DEFAULT now(),
  locked_at timestamptz NULL,
  locked_by varchar(100) NULL,
  last_error_code varchar(80) NULL,
  created_by_user_id uuid NULL REFERENCES public.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz NULL,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, idempotency_key),
  CONSTRAINT intelligence_jobs_branch_tenant_fk
    FOREIGN KEY (tenant_id, branch_id)
    REFERENCES public.branches(tenant_id, id) ON DELETE RESTRICT,
  CONSTRAINT intelligence_jobs_source_pair_ck
    CHECK ((source_type IS NULL) = (source_id IS NULL))
);

CREATE TABLE IF NOT EXISTS public.intelligence_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  branch_id uuid NULL,
  job_id uuid NOT NULL,
  task_type varchar(40) NOT NULL CHECK (task_type IN (
    'business_insight', 'replenishment', 'classify', 'extract', 'explain',
    'summarize', 'analyze', 'forecast', 'reconcile', 'daily_brief'
  )),
  engine_type varchar(20) NOT NULL CHECK (engine_type IN ('deterministic', 'python', 'external_llm', 'none')),
  status varchar(16) NOT NULL
    CHECK (status IN ('SUCCEEDED', 'FAILED', 'BLOCKED', 'TIMED_OUT')),
  provider_id varchar(24) NULL CHECK (provider_id IS NULL OR provider_id IN (
    'gemini', 'groq', 'cerebras', 'openrouter', 'huggingface', 'openai'
  )),
  model_id varchar(160) NULL,
  policy_version varchar(80) NOT NULL,
  input_fingerprint char(64) NULL CHECK (input_fingerprint IS NULL OR input_fingerprint ~ '^[0-9a-f]{64}$'),
  output_fingerprint char(64) NULL CHECK (output_fingerprint IS NULL OR output_fingerprint ~ '^[0-9a-f]{64}$'),
  result_schema_version varchar(80) NULL,
  error_code varchar(80) NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz NOT NULL DEFAULT now(),
  latency_ms integer NULL CHECK (latency_ms IS NULL OR latency_ms >= 0),
  input_tokens integer NULL CHECK (input_tokens IS NULL OR input_tokens >= 0),
  output_tokens integer NULL CHECK (output_tokens IS NULL OR output_tokens >= 0),
  cost_microusd bigint NULL CHECK (cost_microusd IS NULL OR cost_microusd >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  CONSTRAINT intelligence_runs_time_order_ck CHECK (completed_at >= started_at),
  CONSTRAINT intelligence_runs_provider_engine_ck CHECK (
    (engine_type = 'external_llm' AND provider_id IS NOT NULL AND model_id IS NOT NULL AND btrim(model_id) <> '')
    OR (engine_type <> 'external_llm' AND provider_id IS NULL)
  ),
  CONSTRAINT intelligence_runs_job_tenant_fk
    FOREIGN KEY (tenant_id, job_id)
    REFERENCES public.intelligence_jobs(tenant_id, id) ON DELETE CASCADE,
  CONSTRAINT intelligence_runs_branch_tenant_fk
    FOREIGN KEY (tenant_id, branch_id)
    REFERENCES public.branches(tenant_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_intelligence_jobs_pending
  ON public.intelligence_jobs(status, available_at, created_at)
  WHERE status IN ('PENDING', 'FAILED');
CREATE INDEX IF NOT EXISTS idx_intelligence_jobs_tenant_recent
  ON public.intelligence_jobs(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_intelligence_jobs_tenant_branch_recent
  ON public.intelligence_jobs(tenant_id, branch_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_intelligence_runs_tenant_recent
  ON public.intelligence_runs(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_intelligence_runs_job
  ON public.intelligence_runs(tenant_id, job_id, started_at DESC);

ALTER TABLE public.intelligence_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_jobs FORCE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_runs FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS intelligence_jobs_tenant_branch_scope ON public.intelligence_jobs;
CREATE POLICY intelligence_jobs_tenant_branch_scope ON public.intelligence_jobs
  USING (
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id))
  )
  WITH CHECK (
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id))
  );

DROP POLICY IF EXISTS intelligence_runs_tenant_branch_scope ON public.intelligence_runs;
CREATE POLICY intelligence_runs_tenant_branch_scope ON public.intelligence_runs
  USING (
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id))
  )
  WITH CHECK (
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id))
  );

REVOKE ALL ON TABLE public.intelligence_jobs FROM PUBLIC;
REVOKE ALL ON TABLE public.intelligence_runs FROM PUBLIC;
REVOKE ALL ON TABLE public.intelligence_jobs FROM lexa_app;
REVOKE ALL ON TABLE public.intelligence_runs FROM lexa_app;
GRANT SELECT, INSERT, UPDATE ON TABLE public.intelligence_jobs TO lexa_app;
GRANT SELECT, INSERT ON TABLE public.intelligence_runs TO lexa_app;

INSERT INTO public.schema_migrations(version)
VALUES ('045_intelligence_foundation')
ON CONFLICT (version) DO NOTHING;
COMMIT;
