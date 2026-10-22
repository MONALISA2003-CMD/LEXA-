-- LEXA Phase 0 final hardening. Additive and safe to re-run.
-- Fixes the pre-tenant refresh lookup and empty transaction-local RLS context.

CREATE OR REPLACE FUNCTION public.lexa_find_session_by_refresh_hash(p_hash text)
RETURNS TABLE(session_id uuid, tenant_id uuid, user_id uuid)
LANGUAGE sql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS 'SELECT s.id, s.tenant_id, s.user_id
    FROM public.sessions AS s
    WHERE s.refresh_token_hash = p_hash
      AND s.revoked_at IS NULL
      AND s.expires_at > now()
    LIMIT 1';

REVOKE ALL ON FUNCTION public.lexa_find_session_by_refresh_hash(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.lexa_find_session_by_refresh_hash(text) TO lexa_app;

-- Existing policies that cast an empty custom GUC directly to UUID can turn
-- a missing context into an internal 500. Normalize the known Phase 0 policies
-- directly and safely re-run them.
ALTER POLICY audit_logs_isolation ON public.audit_logs
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER POLICY business_profiles_tenant_isolation ON public.business_profiles
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER POLICY devices_tenant_isolation ON public.devices
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER POLICY event_consumptions_tenant_isolation ON public.event_consumptions
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER POLICY idempotency_records_tenant_isolation ON public.idempotency_records
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER POLICY locations_tenant_isolation ON public.locations
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER POLICY membership_roles_tenant_isolation ON public.membership_roles
  USING (EXISTS (SELECT 1 FROM public.tenant_memberships m
    WHERE m.id = membership_roles.membership_id
      AND m.tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid))
  WITH CHECK (EXISTS (SELECT 1 FROM public.tenant_memberships m
    WHERE m.id = membership_roles.membership_id
      AND m.tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid));
ALTER POLICY outbox_events_tenant_isolation ON public.outbox_events
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER POLICY role_permissions_tenant_isolation ON public.role_permissions
  USING (EXISTS (SELECT 1 FROM public.roles r
    WHERE r.id = role_permissions.role_id
      AND r.tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid))
  WITH CHECK (EXISTS (SELECT 1 FROM public.roles r
    WHERE r.id = role_permissions.role_id
      AND r.tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid));
ALTER POLICY roles_tenant_isolation ON public.roles
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER POLICY sessions_tenant_isolation ON public.sessions
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER POLICY tenant_memberships_isolation ON public.tenant_memberships
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

-- Active memberships without a role can authenticate but otherwise hit 403s
-- across every module. Give only those memberships a least-privilege Member
-- role. Never grant Owner/Admin or mutation permissions automatically.
INSERT INTO public.roles (tenant_id, name, description)
SELECT DISTINCT tm.tenant_id, 'Member', 'Default read-only role assigned by Phase 0 authorization repair'
FROM public.tenant_memberships AS tm
WHERE tm.status = 'ACTIVE'
  AND NOT EXISTS (SELECT 1 FROM public.membership_roles mr WHERE mr.membership_id = tm.id)
  AND NOT EXISTS (SELECT 1 FROM public.roles r WHERE r.tenant_id = tm.tenant_id AND r.name = 'Member')
ON CONFLICT (tenant_id, name) DO NOTHING;

INSERT INTO public.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM public.roles AS r
JOIN public.permissions AS p ON p.code IN (
  'analytics.read', 'business.read', 'catalog.read', 'context.read',
  'customers.read', 'inventory.read', 'kernel.read', 'organization.read',
  'payments.read', 'procurement.read', 'purchasing.read', 'receivables.read',
  'roles.read', 'sales.read', 'tax.read', 'tenant.read',
  'tenant.settings.read', 'users.read', 'workflows.read', 'accounting.read',
  'credits.read', 'expenses.read', 'efris.read', 'reconciliation.read', 'brain.read'
)
WHERE r.name = 'Member'
  AND NOT EXISTS (
    SELECT 1 FROM public.role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

INSERT INTO public.membership_roles (membership_id, role_id)
SELECT tm.id, r.id
FROM public.tenant_memberships AS tm
JOIN public.roles AS r ON r.tenant_id = tm.tenant_id AND r.name = 'Member'
WHERE tm.status = 'ACTIVE'
  AND NOT EXISTS (SELECT 1 FROM public.membership_roles mr WHERE mr.membership_id = tm.id)
ON CONFLICT DO NOTHING;

INSERT INTO public.schema_migrations(version) VALUES ('028_phase0_auth_rls_runtime_hardening') ON CONFLICT (version) DO NOTHING;
