-- LEXA Phase 3 Increments 02–03: resumable workspace context, invitations and branch assignments.
-- ADDITIVE ONLY. Do not execute until historical migrations 010/011/023/024/025/026 are recovered,
-- migration 021 is provenance-repaired, and a clean isolated replay has been reviewed.

DO $$
BEGIN
  IF to_regclass('public.tenants') IS NULL
     OR to_regclass('public.users') IS NULL
     OR to_regclass('public.tenant_memberships') IS NULL
     OR to_regclass('public.roles') IS NULL
     OR to_regclass('public.membership_roles') IS NULL
     OR to_regclass('public.role_permissions') IS NULL
     OR to_regclass('public.permissions') IS NULL
     OR to_regclass('public.branches') IS NULL
     OR to_regclass('public.sessions') IS NULL
     OR to_regclass('public.audit_logs') IS NULL
     OR to_regclass('public.outbox_events') IS NULL
     OR to_regclass('public.idempotency_records') IS NULL THEN
    RAISE EXCEPTION 'Phase 3 migration prerequisites are missing; recover and replay the complete LEXA migration history first';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'lexa_app') THEN
    RAISE EXCEPTION 'The lexa_app application role is missing; reconcile the approved role model before applying Phase 3';
  END IF;
  IF to_regclass('public.workspace_invitations') IS NOT NULL
     OR to_regclass('public.membership_branch_assignments') IS NOT NULL THEN
    RAISE EXCEPTION 'A Phase 3 target table already exists; inspect its provenance instead of assuming it matches this migration';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.tenant_memberships GROUP BY tenant_id, user_id HAVING count(*) > 1
  ) THEN
    RAISE EXCEPTION 'Duplicate tenant memberships exist; reconcile them before adding the membership uniqueness guard';
  END IF;
END $$;

-- Composite candidate keys make tenant agreement enforceable at the database boundary.
CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_memberships_id_tenant
  ON public.tenant_memberships(id, tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_branches_id_tenant
  ON public.branches(id, tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_roles_id_tenant
  ON public.roles(id, tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_memberships_tenant_user
  ON public.tenant_memberships(tenant_id, user_id);

CREATE TABLE public.workspace_invitations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  email varchar(320) NOT NULL,
  token_hash varchar(64) NOT NULL UNIQUE CHECK (token_hash ~ '^[0-9a-f]{64}$'),
  status varchar(20) NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING','ACCEPTED','REVOKED','EXPIRED')),
  invited_by_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
  role_id uuid NOT NULL,
  branch_ids jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(branch_ids) = 'array'),
  expires_at timestamptz NOT NULL,
  accepted_by_user_id uuid REFERENCES public.users(id) ON DELETE SET NULL,
  accepted_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_workspace_invitations_role_tenant
    FOREIGN KEY (role_id, tenant_id) REFERENCES public.roles(id, tenant_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_workspace_invitations_tenant_created
  ON public.workspace_invitations(tenant_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_workspace_invitations_pending_email
  ON public.workspace_invitations(tenant_id, lower(email)) WHERE status = 'PENDING';

CREATE TABLE public.membership_branch_assignments (
  membership_id uuid NOT NULL,
  branch_id uuid NOT NULL,
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  assigned_by_user_id uuid REFERENCES public.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (membership_id, branch_id),
  CONSTRAINT fk_membership_branch_assignment_membership_tenant
    FOREIGN KEY (membership_id, tenant_id)
    REFERENCES public.tenant_memberships(id, tenant_id) ON DELETE CASCADE,
  CONSTRAINT fk_membership_branch_assignment_branch_tenant
    FOREIGN KEY (branch_id, tenant_id)
    REFERENCES public.branches(id, tenant_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_membership_branch_assignments_tenant_branch
  ON public.membership_branch_assignments(tenant_id, branch_id);

ALTER TABLE public.workspace_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.membership_branch_assignments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS workspace_invitations_tenant_scope ON public.workspace_invitations;
CREATE POLICY workspace_invitations_tenant_scope ON public.workspace_invitations
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
DROP POLICY IF EXISTS membership_branch_assignments_tenant_scope ON public.membership_branch_assignments;
CREATE POLICY membership_branch_assignments_tenant_scope ON public.membership_branch_assignments
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

-- Public invitation endpoints can only resolve a one-way hash into a minimal locator.
-- The raw token is never stored or included in audit/outbox payloads.
CREATE OR REPLACE FUNCTION public.lexa_find_workspace_invitation(p_token_hash text)
RETURNS TABLE(invitation_id uuid, tenant_id uuid)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
  SELECT i.id, i.tenant_id
  FROM public.workspace_invitations AS i
  WHERE i.token_hash = p_token_hash
    AND i.status = 'PENDING'
    AND i.expires_at > now()
  LIMIT 1
$$;
REVOKE ALL ON FUNCTION public.lexa_find_workspace_invitation(text) FROM PUBLIC;

-- Workspace listing is membership-backed and excludes suspended tenants. It returns no user PII.
CREATE OR REPLACE FUNCTION public.lexa_list_active_user_workspaces(p_user_id uuid)
RETURNS TABLE(tenant_id uuid, tenant_name text, membership_id uuid)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
  SELECT t.id, t.name::text, tm.id
  FROM public.tenant_memberships AS tm
  JOIN public.tenants AS t ON t.id = tm.tenant_id
  WHERE tm.user_id = p_user_id
    AND tm.status = 'ACTIVE'
    AND t.status = 'ACTIVE'
  ORDER BY t.name, t.id
$$;
REVOKE ALL ON FUNCTION public.lexa_list_active_user_workspaces(uuid) FROM PUBLIC;

INSERT INTO public.permissions (id, code, description)
VALUES
  (gen_random_uuid(), 'members.read', 'View workspace memberships and invitations'),
  (gen_random_uuid(), 'members.manage', 'Invite, deactivate, and assign branches to workspace members')
ON CONFLICT (code) DO NOTHING;

-- Keep the first-release default conservative: only established Owner roles receive member management.
INSERT INTO public.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM public.roles r
JOIN public.permissions p ON p.code IN ('members.read', 'members.manage')
WHERE lower(r.name) = 'owner'
ON CONFLICT DO NOTHING;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.workspace_invitations TO lexa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.membership_branch_assignments TO lexa_app;
GRANT EXECUTE ON FUNCTION public.lexa_find_workspace_invitation(text) TO lexa_app;
GRANT EXECUTE ON FUNCTION public.lexa_list_active_user_workspaces(uuid) TO lexa_app;
