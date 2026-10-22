-- LEXA Phase 3 Increments 02–03 — migration 030.
-- ADDITIVE ONLY. Targets already-existing tenant_invitations and membership_branch_assignments
-- from migration 023; do not create duplicate parallel invitation/branch-assignment tables.
-- Reconstructed additions are explicit because source SQL 010, 011 and 023–026 remains unavailable.
-- Validate on a clean isolated database and review schema parity before production use.

DO $$
BEGIN
  IF to_regclass('public.tenants') IS NULL OR to_regclass('public.users') IS NULL
     OR to_regclass('public.tenant_memberships') IS NULL OR to_regclass('public.roles') IS NULL
     OR to_regclass('public.membership_roles') IS NULL OR to_regclass('public.role_permissions') IS NULL
     OR to_regclass('public.permissions') IS NULL OR to_regclass('public.branches') IS NULL
     OR to_regclass('public.sessions') IS NULL OR to_regclass('public.audit_logs') IS NULL
     OR to_regclass('public.outbox_events') IS NULL OR to_regclass('public.idempotency_records') IS NULL
     OR to_regclass('public.tenant_invitations') IS NULL
     OR to_regclass('public.membership_branch_assignments') IS NULL THEN
    RAISE EXCEPTION 'Phase 3 prerequisites are missing; recover/review the complete Phase 0–2 migration chain first';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'lexa_app') THEN
    RAISE EXCEPTION 'lexa_app is missing; reconcile the approved application role before Phase 3';
  END IF;
  IF EXISTS (SELECT 1 FROM public.tenant_memberships GROUP BY tenant_id,user_id HAVING count(*) > 1) THEN
    RAISE EXCEPTION 'Duplicate tenant memberships exist; review before enforcing membership uniqueness';
  END IF;
  IF EXISTS (SELECT 1 FROM public.tenant_invitations WHERE token_hash IS NULL OR token_hash !~ '^[0-9a-f]{64}$') THEN
    RAISE EXCEPTION 'Existing invitation token_hash values do not meet the SHA-256 hex digest contract';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.tenant_invitations
    WHERE status='PENDING' AND expires_at>now() AND role_id IS NULL
  ) THEN
    RAISE EXCEPTION 'A live pending invitation has no role; reconcile that record before enabling role-bound invitation acceptance';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.tenant_invitations WHERE status='PENDING'
    GROUP BY tenant_id,lower(email) HAVING count(*)>1
  ) THEN
    RAISE EXCEPTION 'Duplicate pending invitations exist for the same workspace/email; reconcile before enforcing uniqueness';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='membership_branch_assignments' AND column_name='id')
     OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.membership_branch_assignments'::regclass AND contype='p' AND pg_get_constraintdef(oid)='PRIMARY KEY (id)') THEN
    RAISE EXCEPTION 'Membership branch assignment is missing the migration-026 UUID primary-key contract; repair/replay its labelled equivalent before applying 030';
  END IF;
END $$;

-- Migration 023 and earlier reviewed sources own the tenant-composite keys and the
-- (tenant_id,user_id) uniqueness contract. Do not add redundant indexes here.

-- Extend the existing migration-023 invitation record instead of creating a second invite store.
ALTER TABLE public.tenant_invitations ADD COLUMN IF NOT EXISTS branch_ids jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE public.tenant_invitations ADD COLUMN IF NOT EXISTS accepted_by_user_id uuid REFERENCES public.users(id) ON DELETE SET NULL;
ALTER TABLE public.tenant_invitations ADD COLUMN IF NOT EXISTS revoked_at timestamptz;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.tenant_invitations'::regclass AND conname='tenant_invitations_branch_ids_array_ck') THEN
    ALTER TABLE public.tenant_invitations ADD CONSTRAINT tenant_invitations_branch_ids_array_ck CHECK (jsonb_typeof(branch_ids)='array') NOT VALID;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.tenant_invitations'::regclass AND conname='tenant_invitations_status_ck') THEN
    ALTER TABLE public.tenant_invitations ADD CONSTRAINT tenant_invitations_status_ck CHECK (status IN ('PENDING','ACCEPTED','REVOKED','EXPIRED')) NOT VALID;
  END IF;
END $$;
ALTER TABLE public.tenant_invitations VALIDATE CONSTRAINT tenant_invitations_branch_ids_array_ck;
ALTER TABLE public.tenant_invitations VALIDATE CONSTRAINT tenant_invitations_status_ck;
CREATE INDEX IF NOT EXISTS lexa_030_ix_invitations_tenant_created ON public.tenant_invitations(tenant_id,created_at DESC);
CREATE INDEX IF NOT EXISTS lexa_030_ix_invitations_email_status ON public.tenant_invitations(tenant_id,lower(email),status);
CREATE UNIQUE INDEX IF NOT EXISTS lexa_030_uq_invitations_pending_email ON public.tenant_invitations(tenant_id,lower(email)) WHERE status='PENDING';

-- Migration 023 created this table without the later surrogate-key and lifecycle contract.
ALTER TABLE public.membership_branch_assignments ADD COLUMN IF NOT EXISTS status varchar(30) NOT NULL DEFAULT 'ACTIVE';
ALTER TABLE public.membership_branch_assignments ADD COLUMN IF NOT EXISTS assigned_by_user_id uuid REFERENCES public.users(id) ON DELETE SET NULL;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.membership_branch_assignments'::regclass AND conname='membership_branch_assignments_status_ck') THEN
    ALTER TABLE public.membership_branch_assignments ADD CONSTRAINT membership_branch_assignments_status_ck CHECK(status IN ('ACTIVE','INACTIVE')) NOT VALID;
  END IF;
END $$;
ALTER TABLE public.membership_branch_assignments VALIDATE CONSTRAINT membership_branch_assignments_status_ck;
DO $$
BEGIN
  -- Reuse an equivalent index from the reviewed 026 migration when present.
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='membership_branch_assignments'
      AND indexdef ILIKE '%(tenant_id, branch_id, status)%'
  ) THEN
    CREATE INDEX lexa_030_ix_membership_branch_status
      ON public.membership_branch_assignments(tenant_id,branch_id,status);
  END IF;
END $$;

ALTER TABLE public.tenant_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_invitations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_invitations_tenant_isolation ON public.tenant_invitations;
CREATE POLICY tenant_invitations_tenant_isolation ON public.tenant_invitations
  USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid)
  WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid);
ALTER TABLE public.membership_branch_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.membership_branch_assignments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS membership_branch_assignments_tenant_isolation ON public.membership_branch_assignments;
CREATE POLICY membership_branch_assignments_tenant_isolation ON public.membership_branch_assignments
  USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid)
  WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid);

CREATE OR REPLACE FUNCTION public.lexa_find_workspace_invitation(p_token_hash text)
RETURNS TABLE(invitation_id uuid, tenant_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public
AS $$
  SELECT i.id, i.tenant_id FROM public.tenant_invitations i
  JOIN public.tenants t ON t.id=i.tenant_id AND t.status='ACTIVE'
  WHERE i.token_hash=p_token_hash AND i.status='PENDING' AND i.expires_at>now()
  LIMIT 1
$$;
REVOKE ALL ON FUNCTION public.lexa_find_workspace_invitation(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.lexa_find_workspace_invitation(text) TO lexa_app;

CREATE OR REPLACE FUNCTION public.lexa_list_active_user_workspaces(p_user_id uuid)
RETURNS TABLE(tenant_id uuid, tenant_name text, membership_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public
AS $$
  SELECT t.id, t.name::text, tm.id
  FROM public.tenant_memberships tm
  JOIN public.tenants t ON t.id=tm.tenant_id
  JOIN public.users u ON u.id=tm.user_id AND u.is_active
  WHERE tm.user_id=p_user_id
    AND tm.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
    AND tm.status='ACTIVE' AND t.status='ACTIVE'
  ORDER BY t.name,t.id
$$;
REVOKE ALL ON FUNCTION public.lexa_list_active_user_workspaces(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.lexa_list_active_user_workspaces(uuid) TO lexa_app;

INSERT INTO public.permissions(code,description) VALUES
 ('members.read','View workspace memberships and invitations'),
 ('members.manage','Invite, deactivate, and assign branches to workspace members')
ON CONFLICT(code) DO NOTHING;
INSERT INTO public.role_permissions(role_id,permission_id)
SELECT r.id,p.id FROM public.roles r CROSS JOIN public.permissions p
WHERE lower(r.name)='owner' AND p.code IN ('members.read','members.manage')
ON CONFLICT DO NOTHING;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.tenant_invitations TO lexa_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.membership_branch_assignments TO lexa_app;
INSERT INTO public.schema_migrations(version) VALUES ('030_phase3_workspace_memberships') ON CONFLICT(version) DO NOTHING;
