-- LEXA Phase 3: tenant/branch-scoped document intake, local extraction candidates and human review history.
-- Forward-only additive candidate. Do not apply until reviewed clean-replay and RLS tests pass.
-- Original files are stored only as bounded bytea. No external model is called.
BEGIN;

DO $$
BEGIN
  IF to_regclass('public.tenants') IS NULL
     OR to_regclass('public.branches') IS NULL
     OR to_regclass('public.users') IS NULL
     OR to_regclass('public.permissions') IS NULL
     OR to_regclass('public.role_permissions') IS NULL
     OR to_regclass('public.schema_migrations') IS NULL THEN
    RAISE EXCEPTION 'LEXA document-intelligence prerequisites are missing';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'lexa_app') THEN
    RAISE EXCEPTION 'LEXA application role lexa_app is missing';
  END IF;
  IF to_regprocedure('public.lexa_can_access_branch(uuid)') IS NULL THEN
    RAISE EXCEPTION 'LEXA branch-access function prerequisite is missing';
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.intelligence_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  branch_id uuid NOT NULL,
  document_type varchar(32) NOT NULL CHECK (document_type IN (
    'SUPPLIER_INVOICE','EXPENSE_RECEIPT','CUSTOMER_INVOICE','PURCHASE_ORDER','OTHER'
  )),
  status varchar(20) NOT NULL DEFAULT 'NEEDS_REVIEW'
    CHECK (status IN ('NEEDS_REVIEW','CONFIRMED','REJECTED')),
  original_filename varchar(180) NOT NULL
    CHECK (length(btrim(original_filename)) BETWEEN 1 AND 180
       AND position('/' in original_filename) = 0
       AND position(chr(92) in original_filename) = 0
       AND original_filename !~ '[[:cntrl:]]'),
  content_type varchar(64) NOT NULL CHECK (content_type IN ('application/pdf','image/jpeg','image/png','image/webp')),
  size_bytes integer NOT NULL CHECK (size_bytes BETWEEN 1 AND 10485760),
  content_sha256 char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  content_bytes bytea NOT NULL CHECK (octet_length(content_bytes) = size_bytes AND octet_length(content_bytes) <= 10485760),
  extraction_status varchar(16) NOT NULL CHECK (extraction_status IN ('SUCCEEDED','PARTIAL','UNAVAILABLE')),
  extraction_method varchar(32) NOT NULL CHECK (extraction_method IN ('PDF_TEXT_LAYER','PDF_RENDERED_OCR','TESSERACT_OCR','UNAVAILABLE')),
  extracted_text text NOT NULL DEFAULT '' CHECK (length(extracted_text) <= 12000),
  candidate_fields jsonb NOT NULL CHECK (
    jsonb_typeof(candidate_fields) = 'object'
    AND pg_column_size(candidate_fields) <= 32768
    AND candidate_fields->>'schema_version' = 'phase3.document_candidate.v1'
  ),
  confirmed_fields jsonb NULL CHECK (
    confirmed_fields IS NULL OR (jsonb_typeof(confirmed_fields) = 'object' AND pg_column_size(confirmed_fields) <= 8192)
  ),
  created_by_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
  reviewed_by_user_id uuid NULL REFERENCES public.users(id) ON DELETE RESTRICT,
  reviewed_at timestamptz NULL,
  review_reason varchar(500) NULL CHECK (review_reason IS NULL OR length(review_reason) <= 500),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, branch_id, id),
  UNIQUE (tenant_id, branch_id, content_sha256),
  CONSTRAINT intelligence_documents_branch_tenant_fk
    FOREIGN KEY (tenant_id, branch_id) REFERENCES public.branches(tenant_id, id) ON DELETE RESTRICT,
  CONSTRAINT intelligence_documents_review_state_ck CHECK (
    (status = 'NEEDS_REVIEW' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND confirmed_fields IS NULL)
    OR (status = 'CONFIRMED' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND confirmed_fields IS NOT NULL)
    OR (status = 'REJECTED' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL)
  )
);

CREATE TABLE IF NOT EXISTS public.intelligence_document_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  branch_id uuid NOT NULL,
  document_id uuid NOT NULL,
  action varchar(16) NOT NULL CHECK (action IN ('CONFIRM','REJECT')),
  reason varchar(500) NULL CHECK (reason IS NULL OR length(reason) <= 500),
  fields_fingerprint char(64) NULL CHECK (fields_fingerprint IS NULL OR fields_fingerprint ~ '^[0-9a-f]{64}$'),
  actor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT intelligence_document_reviews_document_fk
    FOREIGN KEY (tenant_id, branch_id, document_id)
    REFERENCES public.intelligence_documents(tenant_id, branch_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_intelligence_documents_tenant_branch_recent
  ON public.intelligence_documents(tenant_id, branch_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_intelligence_documents_review_queue
  ON public.intelligence_documents(tenant_id, branch_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_intelligence_documents_content_hash
  ON public.intelligence_documents(tenant_id, branch_id, content_sha256);
CREATE INDEX IF NOT EXISTS idx_intelligence_document_reviews_document
  ON public.intelligence_document_reviews(tenant_id, document_id, created_at DESC);

ALTER TABLE public.intelligence_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_documents FORCE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_document_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_document_reviews FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS intelligence_documents_tenant_branch_scope ON public.intelligence_documents;
CREATE POLICY intelligence_documents_tenant_branch_scope ON public.intelligence_documents
  FOR ALL TO lexa_app
  USING (
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    AND public.lexa_can_access_branch(branch_id)
  )
  WITH CHECK (
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    AND public.lexa_can_access_branch(branch_id)
  );

DROP POLICY IF EXISTS intelligence_document_reviews_tenant_branch_scope ON public.intelligence_document_reviews;
CREATE POLICY intelligence_document_reviews_tenant_branch_scope ON public.intelligence_document_reviews
  FOR ALL TO lexa_app
  USING (
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    AND public.lexa_can_access_branch(branch_id)
  )
  WITH CHECK (
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    AND public.lexa_can_access_branch(branch_id)
  );

REVOKE ALL ON TABLE public.intelligence_documents FROM PUBLIC;
REVOKE ALL ON TABLE public.intelligence_document_reviews FROM PUBLIC;
REVOKE ALL ON TABLE public.intelligence_documents FROM lexa_app;
REVOKE ALL ON TABLE public.intelligence_document_reviews FROM lexa_app;
GRANT SELECT, INSERT, UPDATE ON TABLE public.intelligence_documents TO lexa_app;
GRANT SELECT, INSERT ON TABLE public.intelligence_document_reviews TO lexa_app;

INSERT INTO public.permissions(code, description) VALUES
 ('intelligence.documents.read', 'Read uploaded business documents and extraction candidates in assigned branches'),
 ('intelligence.documents.intake', 'Upload bounded business documents for local extraction and review'),
 ('intelligence.documents.review', 'Confirm or reject extracted document fields in assigned branches')
ON CONFLICT (code) DO NOTHING;

INSERT INTO public.role_permissions(role_id, permission_id)
SELECT r.id, p.id FROM public.roles r JOIN public.permissions p ON p.code='intelligence.documents.read'
WHERE r.name IN ('Owner','Administrator','Manager','Finance / Accounting','Purchasing','Sales','Staff / Operator','Read-only','Admin','Accountant','Auditor')
ON CONFLICT DO NOTHING;

INSERT INTO public.role_permissions(role_id, permission_id)
SELECT r.id, p.id FROM public.roles r JOIN public.permissions p ON p.code='intelligence.documents.intake'
WHERE r.name IN ('Owner','Administrator','Manager','Finance / Accounting','Purchasing','Sales','Staff / Operator','Admin','Accountant')
ON CONFLICT DO NOTHING;

INSERT INTO public.role_permissions(role_id, permission_id)
SELECT r.id, p.id FROM public.roles r JOIN public.permissions p ON p.code='intelligence.documents.review'
WHERE r.name IN ('Owner','Administrator','Manager','Finance / Accounting','Purchasing','Admin','Accountant')
ON CONFLICT DO NOTHING;

INSERT INTO public.schema_migrations(version)
VALUES ('046_intelligence_documents')
ON CONFLICT (version) DO NOTHING;
COMMIT;
