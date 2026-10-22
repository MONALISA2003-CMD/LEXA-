-- LEXA Phase 2: identity, tenancy and authorization foundation.
-- Additive only. No reset or destructive rewrite.

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS display_name varchar(200);

CREATE TABLE IF NOT EXISTS tenant_settings (
  tenant_id uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
  timezone varchar(64) NOT NULL DEFAULT 'Africa/Kampala',
  locale varchar(20) NOT NULL DEFAULT 'en-UG',
  business_type varchar(100),
  industry varchar(100),
  fiscal_year_start_month smallint NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT tenant_settings_fiscal_year_start_month_ck CHECK (fiscal_year_start_month BETWEEN 1 AND 12)
);

INSERT INTO tenant_settings (tenant_id)
SELECT id FROM tenants
ON CONFLICT (tenant_id) DO NOTHING;

CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_memberships_tenant_id
  ON tenant_memberships(tenant_id, id);

CREATE TABLE IF NOT EXISTS membership_branch_assignments (
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  membership_id uuid NOT NULL,
  branch_id uuid NOT NULL,
  assigned_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (membership_id, branch_id),
  UNIQUE (tenant_id, membership_id, branch_id),
  CONSTRAINT membership_branch_membership_tenant_fk
    FOREIGN KEY (tenant_id, membership_id) REFERENCES tenant_memberships(tenant_id, id) ON DELETE CASCADE,
  CONSTRAINT membership_branch_branch_tenant_fk
    FOREIGN KEY (tenant_id, branch_id) REFERENCES branches(tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_membership_branch_assignments_tenant
  ON membership_branch_assignments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_membership_branch_assignments_branch
  ON membership_branch_assignments(tenant_id, branch_id);

CREATE TABLE IF NOT EXISTS tenant_invitations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  email varchar(320) NOT NULL,
  token_hash varchar(64) NOT NULL UNIQUE,
  role_id uuid,
  invited_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  status varchar(30) NOT NULL DEFAULT 'PENDING',
  expires_at timestamptz NOT NULL,
  accepted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE tenant_invitations
  DROP CONSTRAINT IF EXISTS tenant_invitations_role_tenant_fk;
ALTER TABLE tenant_invitations
  ADD CONSTRAINT tenant_invitations_role_tenant_fk
  FOREIGN KEY (tenant_id, role_id) REFERENCES roles(tenant_id, id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_tenant_invitations_tenant
  ON tenant_invitations(tenant_id, status, expires_at);
CREATE INDEX IF NOT EXISTS idx_tenant_invitations_email
  ON tenant_invitations(tenant_id, email, status);

CREATE TABLE IF NOT EXISTS user_security_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_type varchar(40) NOT NULL,
  token_hash varchar(64) NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT user_security_tokens_type_ck CHECK (token_type IN ('EMAIL_VERIFICATION','PASSWORD_RESET'))
);

CREATE INDEX IF NOT EXISTS idx_user_security_tokens_user_type
  ON user_security_tokens(user_id, token_type, expires_at);

ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_settings FORCE ROW LEVEL SECURITY;
ALTER TABLE membership_branch_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE membership_branch_assignments FORCE ROW LEVEL SECURITY;
ALTER TABLE tenant_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_invitations FORCE ROW LEVEL SECURITY;
ALTER TABLE user_security_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_security_tokens FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_settings_tenant_isolation ON tenant_settings;
CREATE POLICY tenant_settings_tenant_isolation ON tenant_settings
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS membership_branch_assignments_tenant_isolation ON membership_branch_assignments;
CREATE POLICY membership_branch_assignments_tenant_isolation ON membership_branch_assignments
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS tenant_invitations_tenant_isolation ON tenant_invitations;
CREATE POLICY tenant_invitations_tenant_isolation ON tenant_invitations
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS user_security_tokens_user_isolation ON user_security_tokens;
CREATE POLICY user_security_tokens_user_isolation ON user_security_tokens
  USING (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
  WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_settings TO lexa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON membership_branch_assignments TO lexa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_invitations TO lexa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_security_tokens TO lexa_app;

INSERT INTO permissions (code, description) VALUES
 ('tenant.settings.read', 'Read tenant settings'),
 ('tenant.settings.manage', 'Manage tenant settings'),
 ('users.invite', 'Invite users to the tenant'),
 ('users.suspend', 'Suspend tenant memberships'),
 ('users.restore', 'Restore tenant memberships'),
 ('users.sessions.read', 'Read user sessions'),
 ('users.sessions.revoke', 'Revoke user sessions'),
 ('branches.assign', 'Assign memberships to branches'),
 ('security.manage', 'Manage tenant security controls')
ON CONFLICT (code) DO NOTHING;

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

-- Owner keeps every current capability.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON TRUE
WHERE r.name = 'Owner'
ON CONFLICT DO NOTHING;

-- Administrator can operate the tenant except internal Business Engine controls.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code NOT LIKE 'kernel.%'
WHERE r.name = 'Administrator'
ON CONFLICT DO NOTHING;

-- Read-only receives capabilities explicitly designed as reads plus workspace context.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code LIKE '%.read' OR p.code IN ('context.read','tenant.settings.read')
WHERE r.name = 'Read-only'
ON CONFLICT DO NOTHING;

-- Functional business roles are capability-based rather than screen-based.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON (
  (r.name = 'Manager' AND p.code IN (
    'tenant.read','tenant.settings.read','tenant.settings.manage','business.read','business.manage',
    'users.read','organization.read','organization.manage','branches.assign','roles.read',
    'catalog.read','catalog.manage','catalog.pricing.manage','customers.read','customers.manage',
    'sales.read','sales.manage','sales.complete','sales.return','inventory.read','inventory.manage',
    'inventory.adjust.approve','inventory.adjust.post','inventory.count.manage','inventory.count.approve','inventory.count.post',
    'inventory.transfer.create','inventory.transfer.approve','inventory.transfer.dispatch','inventory.transfer.receive','inventory.transfer.complete',
    'payments.read','payments.manage','payments.allocate','receivables.read','receivables.manage',
    'analytics.read','brain.read','brain.query'))
  OR (r.name = 'Finance / Accounting' AND (p.code LIKE 'accounting.%' OR p.code IN (
    'tenant.read','tenant.settings.read','customers.read','payments.read','payments.manage','payments.allocate',
    'receivables.read','receivables.manage','expenses.read','expenses.manage','reconciliation.read','reconciliation.manage',
    'reconciliation.resolve','reconciliation.close','tax.read','tax.manage','efris.read','efris.submit','efris.manage','analytics.read')))
  OR (r.name = 'Sales' AND p.code IN (
    'tenant.read','tenant.settings.read','catalog.read','customers.read','customers.manage','sales.read','sales.manage',
    'sales.complete','sales.return','payments.read','payments.manage','payments.allocate','receivables.read','receivables.manage','credits.read','credits.manage'))
  OR (r.name = 'Inventory' AND p.code IN (
    'tenant.read','tenant.settings.read','catalog.read','catalog.manage','inventory.read','inventory.manage',
    'inventory.adjust.approve','inventory.adjust.post','inventory.count.manage','inventory.count.approve','inventory.count.post',
    'inventory.transfer.create','inventory.transfer.approve','inventory.transfer.dispatch','inventory.transfer.receive','inventory.transfer.complete'))
  OR (r.name = 'Staff / Operator' AND p.code IN (
    'tenant.read','tenant.settings.read','catalog.read','customers.read','sales.read','sales.complete','payments.read','inventory.read','context.read'))
)
ON CONFLICT DO NOTHING;

-- Branch-aware direct SQL protection for tables that carry a branch_id.
CREATE OR REPLACE FUNCTION public.lexa_can_access_branch(p_branch_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
  WITH ctx AS (
    SELECT
      NULLIF(current_setting('app.user_id', true), '')::uuid AS user_id,
      NULLIF(current_setting('app.tenant_id', true), '')::uuid AS tenant_id
  ),
  memberships AS (
    SELECT tm.id AS membership_id
    FROM public.tenant_memberships tm, ctx
    WHERE tm.tenant_id = ctx.tenant_id
      AND tm.user_id = ctx.user_id
      AND tm.status = 'ACTIVE'
  )
  SELECT
    (
      EXISTS (
        SELECT 1
        FROM public.membership_roles mr
        JOIN public.roles r ON r.id = mr.role_id
        WHERE mr.membership_id IN (SELECT membership_id FROM memberships)
          AND r.tenant_id = (SELECT tenant_id FROM ctx)
          AND r.name IN ('Owner', 'Administrator', 'Manager')
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

REVOKE ALL ON FUNCTION public.lexa_can_access_branch(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.lexa_can_access_branch(uuid) TO lexa_app;

-- Branch-scoped tables retain tenant isolation and additionally respect assignment scope.
DROP POLICY IF EXISTS branches_tenant_isolation ON branches;
CREATE POLICY branches_tenant_isolation ON branches
USING (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND public.lexa_can_access_branch(id)
)
WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS warehouses_tenant_isolation ON warehouses;
CREATE POLICY warehouses_tenant_isolation ON warehouses
USING (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id))
)
WITH CHECK (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id))
);

DROP POLICY IF EXISTS pos_terminals_tenant_isolation ON pos_terminals;
CREATE POLICY pos_terminals_tenant_isolation ON pos_terminals
USING (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND public.lexa_can_access_branch(branch_id)
)
WITH CHECK (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND public.lexa_can_access_branch(branch_id)
);

DROP POLICY IF EXISTS business_transactions_tenant_isolation ON business_transactions;
CREATE POLICY business_transactions_tenant_isolation ON business_transactions
USING (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id))
)
WITH CHECK (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id))
);

DROP POLICY IF EXISTS price_contexts_tenant_isolation ON price_contexts;
CREATE POLICY price_contexts_tenant_isolation ON price_contexts
USING (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id))
)
WITH CHECK (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id))
);

DROP POLICY IF EXISTS sales_tenant_isolation ON sales;
CREATE POLICY sales_tenant_isolation ON sales
USING (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id))
)
WITH CHECK (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id))
);

DROP POLICY IF EXISTS analytics_branch_daily_metrics_tenant ON analytics_branch_daily_metrics;
DROP POLICY IF EXISTS analytics_branch_daily_metrics_tenant_isolation ON analytics_branch_daily_metrics;
CREATE POLICY analytics_branch_daily_metrics_tenant_isolation ON analytics_branch_daily_metrics
USING (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND public.lexa_can_access_branch(branch_id)
)
WITH CHECK (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND public.lexa_can_access_branch(branch_id)
);

CREATE OR REPLACE FUNCTION public.lexa_get_invitation_by_token(p_token_hash varchar(64))
RETURNS TABLE (
  invitation_id uuid,
  tenant_id uuid,
  email varchar(320),
  role_id uuid,
  status varchar(30),
  expires_at timestamptz
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
  SELECT id, tenant_id, email, role_id, status, expires_at
  FROM public.tenant_invitations
  WHERE token_hash = p_token_hash
  LIMIT 1;
$$;

REVOKE ALL ON FUNCTION public.lexa_get_invitation_by_token(varchar(64)) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.lexa_get_invitation_by_token(varchar(64)) TO lexa_app;

INSERT INTO schema_migrations (version)
VALUES ('023_phase2_identity_tenancy_authorization_foundation')
ON CONFLICT (version) DO NOTHING;
