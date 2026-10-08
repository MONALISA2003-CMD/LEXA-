-- LEXA Phase 2 identity/tenancy convergence. Additive only.
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name varchar(200);
CREATE TABLE IF NOT EXISTS tenant_settings (tenant_id uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE, timezone varchar(64) NOT NULL DEFAULT 'Africa/Kampala', locale varchar(20) NOT NULL DEFAULT 'en-UG', business_type varchar(100), industry varchar(100), fiscal_year_start_month smallint NOT NULL DEFAULT 1, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), CONSTRAINT tenant_settings_fiscal_year_start_month_ck CHECK (fiscal_year_start_month BETWEEN 1 AND 12));
INSERT INTO tenant_settings(tenant_id) SELECT id FROM tenants ON CONFLICT (tenant_id) DO NOTHING;
CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_memberships_tenant_id ON tenant_memberships(tenant_id,id);
CREATE TABLE IF NOT EXISTS membership_branch_assignments (tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, membership_id uuid NOT NULL, branch_id uuid NOT NULL, assigned_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(membership_id,branch_id), UNIQUE(tenant_id,membership_id,branch_id), FOREIGN KEY(tenant_id,membership_id) REFERENCES tenant_memberships(tenant_id,id) ON DELETE CASCADE, FOREIGN KEY(tenant_id,branch_id) REFERENCES branches(tenant_id,id) ON DELETE CASCADE);
CREATE INDEX IF NOT EXISTS idx_membership_branch_assignments_tenant ON membership_branch_assignments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_membership_branch_assignments_branch ON membership_branch_assignments(tenant_id,branch_id);
CREATE TABLE IF NOT EXISTS tenant_invitations (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, email varchar(320) NOT NULL, token_hash varchar(64) NOT NULL UNIQUE, role_id uuid, invited_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL, status varchar(30) NOT NULL DEFAULT 'PENDING', expires_at timestamptz NOT NULL, accepted_at timestamptz, created_at timestamptz NOT NULL DEFAULT now());
ALTER TABLE tenant_invitations DROP CONSTRAINT IF EXISTS tenant_invitations_role_tenant_fk;
ALTER TABLE tenant_invitations ADD CONSTRAINT tenant_invitations_role_tenant_fk FOREIGN KEY (tenant_id,role_id) REFERENCES roles(tenant_id,id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_tenant_invitations_tenant ON tenant_invitations(tenant_id,status,expires_at);
CREATE INDEX IF NOT EXISTS idx_tenant_invitations_email ON tenant_invitations(tenant_id,email,status);
CREATE TABLE IF NOT EXISTS user_security_tokens (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, token_type varchar(40) NOT NULL, token_hash varchar(64) NOT NULL UNIQUE, expires_at timestamptz NOT NULL, used_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(), CONSTRAINT user_security_tokens_type_ck CHECK(token_type IN ('EMAIL_VERIFICATION','PASSWORD_RESET')));
CREATE INDEX IF NOT EXISTS idx_user_security_tokens_user_type ON user_security_tokens(user_id,token_type,expires_at);
ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY; ALTER TABLE tenant_settings FORCE ROW LEVEL SECURITY;
ALTER TABLE membership_branch_assignments ENABLE ROW LEVEL SECURITY; ALTER TABLE membership_branch_assignments FORCE ROW LEVEL SECURITY;
ALTER TABLE tenant_invitations ENABLE ROW LEVEL SECURITY; ALTER TABLE tenant_invitations FORCE ROW LEVEL SECURITY;
ALTER TABLE user_security_tokens ENABLE ROW LEVEL SECURITY; ALTER TABLE user_security_tokens FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_settings_tenant_isolation ON tenant_settings;
CREATE POLICY tenant_settings_tenant_isolation ON tenant_settings USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid);
DROP POLICY IF EXISTS membership_branch_assignments_tenant_isolation ON membership_branch_assignments;
CREATE POLICY membership_branch_assignments_tenant_isolation ON membership_branch_assignments USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid);
DROP POLICY IF EXISTS tenant_invitations_tenant_isolation ON tenant_invitations;
CREATE POLICY tenant_invitations_tenant_isolation ON tenant_invitations USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid);
DROP POLICY IF EXISTS user_security_tokens_user_isolation ON user_security_tokens;
CREATE POLICY user_security_tokens_user_isolation ON user_security_tokens USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
GRANT SELECT,INSERT,UPDATE,DELETE ON tenant_settings,membership_branch_assignments,tenant_invitations,user_security_tokens TO lexa_app;
INSERT INTO permissions(code,description) VALUES ('tenant.settings.read','Read tenant settings'),('tenant.settings.manage','Manage tenant settings'),('users.invite','Invite users to the tenant'),('users.suspend','Suspend tenant memberships'),('users.restore','Restore tenant memberships'),('users.sessions.read','Read user sessions'),('users.sessions.revoke','Revoke user sessions'),('branches.assign','Assign memberships to branches'),('security.manage','Manage tenant security controls') ON CONFLICT(code) DO NOTHING;
CREATE OR REPLACE FUNCTION public.lexa_can_access_branch(p_branch_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
  WITH ctx AS (
    SELECT NULLIF(current_setting('app.user_id', true), '')::uuid AS user_id,
           NULLIF(current_setting('app.tenant_id', true), '')::uuid AS tenant_id
  ), memberships AS (
    SELECT tm.id AS membership_id
    FROM public.tenant_memberships tm, ctx
    WHERE tm.tenant_id = ctx.tenant_id AND tm.user_id = ctx.user_id AND tm.status = 'ACTIVE'
  )
  SELECT (
    EXISTS (
      SELECT 1 FROM public.membership_roles mr
      JOIN public.roles r ON r.id = mr.role_id
      WHERE mr.membership_id IN (SELECT membership_id FROM memberships)
        AND r.tenant_id = (SELECT tenant_id FROM ctx)
        AND r.name IN ('Owner','Administrator','Manager')
    )
    OR NOT EXISTS (
      SELECT 1 FROM public.membership_branch_assignments a
      WHERE a.tenant_id = (SELECT tenant_id FROM ctx)
        AND a.membership_id IN (SELECT membership_id FROM memberships)
    )
    OR EXISTS (
      SELECT 1 FROM public.membership_branch_assignments a
      WHERE a.tenant_id = (SELECT tenant_id FROM ctx)
        AND a.branch_id = p_branch_id
        AND a.membership_id IN (SELECT membership_id FROM memberships)
    )
  );
$$;
REVOKE ALL ON FUNCTION public.lexa_can_access_branch(uuid) FROM PUBLIC; GRANT EXECUTE ON FUNCTION public.lexa_can_access_branch(uuid) TO lexa_app;
INSERT INTO schema_migrations(version) VALUES('023_phase2_identity_tenancy_authorization_foundation') ON CONFLICT(version) DO NOTHING;

-- Capability-based role templates used by the Administration workspace.
INSERT INTO roles (tenant_id, name, description)
SELECT t.id, v.name, v.description
FROM tenants t
CROSS JOIN (VALUES
  ('Administrator', 'Tenant administrator'),
  ('Manager', 'Business manager'),
  ('Finance / Accounting', 'Finance and accounting operator'),
  ('Sales', 'Sales and customer operator'),
  ('Inventory', 'Inventory operator'),
  ('Staff / Operator', 'Operational staff user'),
  ('Read-only', 'Read-only tenant access')
) AS v(name, description)
ON CONFLICT (tenant_id, name) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r JOIN permissions p ON TRUE
WHERE r.name='Owner' ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r JOIN permissions p ON p.code NOT LIKE 'kernel.%'
WHERE r.name='Administrator' ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r JOIN permissions p ON p.code LIKE '%.read' OR p.code IN ('context.read','tenant.settings.read')
WHERE r.name='Read-only' ON CONFLICT DO NOTHING;

-- Workspace picker function required by the production authentication flow.
CREATE OR REPLACE FUNCTION public.lexa_list_user_workspaces(p_user_id uuid)
RETURNS TABLE(tenant_id uuid, tenant_name varchar, membership_id uuid)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
  SELECT tm.tenant_id, t.name, tm.id
  FROM public.tenant_memberships tm
  JOIN public.tenants t ON t.id = tm.tenant_id
  WHERE tm.user_id = p_user_id
    AND tm.status = 'ACTIVE'
    AND t.status = 'ACTIVE'
  ORDER BY t.name ASC;
$$;
REVOKE ALL ON FUNCTION public.lexa_list_user_workspaces(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.lexa_list_user_workspaces(uuid) TO lexa_app;
