-- LEXA Phase 0 final hardening. Additive and safe to re-run.
-- Fixes the pre-tenant refresh lookup and empty transaction-local RLS context.

CREATE OR REPLACE FUNCTION public.lexa_find_session_by_refresh_hash(p_hash text)
RETURNS TABLE(session_id uuid, tenant_id uuid, user_id uuid)
LANGUAGE sql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
  SELECT s.id, s.tenant_id, s.user_id
  FROM public.sessions AS s
  WHERE s.refresh_token_hash = p_hash
    AND s.revoked_at IS NULL
    AND s.expires_at > now()
  LIMIT 1;
$function$;

REVOKE ALL ON FUNCTION public.lexa_find_session_by_refresh_hash(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.lexa_find_session_by_refresh_hash(text) TO lexa_app;

-- Existing policies that cast an empty custom GUC directly to UUID can turn
-- a missing context into an internal 500. NULLIF makes absence fail closed.
DO $migration$
DECLARE
  p record;
  fixed_using text;
  fixed_check text;
BEGIN
  FOR p IN
    SELECT schemaname, tablename, policyname, qual, with_check
    FROM pg_policies
    WHERE schemaname = 'public'
      AND (COALESCE(qual, '') LIKE '%current_setting(%'
        OR COALESCE(with_check, '') LIKE '%current_setting(%')
  LOOP
    fixed_using := p.qual;
    fixed_check := p.with_check;
    IF fixed_using IS NOT NULL THEN
      fixed_using := replace(fixed_using,
        'current_setting(''app.tenant_id''::text, true)',
        'NULLIF(current_setting(''app.tenant_id''::text, true), ''''::text)');
      fixed_using := replace(fixed_using,
        'current_setting(''app.user_id''::text, true)',
        'NULLIF(current_setting(''app.user_id''::text, true), ''''::text)');
    END IF;
    IF fixed_check IS NOT NULL THEN
      fixed_check := replace(fixed_check,
        'current_setting(''app.tenant_id''::text, true)',
        'NULLIF(current_setting(''app.tenant_id''::text, true), ''''::text)');
      fixed_check := replace(fixed_check,
        'current_setting(''app.user_id''::text, true)',
        'NULLIF(current_setting(''app.user_id''::text, true), ''''::text)');
    END IF;
    IF fixed_using IS DISTINCT FROM p.qual THEN
      EXECUTE format('ALTER POLICY %I ON %I.%I USING (%s)', p.policyname, p.schemaname, p.tablename, fixed_using);
    END IF;
    IF fixed_check IS DISTINCT FROM p.with_check THEN
      EXECUTE format('ALTER POLICY %I ON %I.%I WITH CHECK (%s)', p.policyname, p.schemaname, p.tablename, fixed_check);
    END IF;
  END LOOP;
END;
$migration$;

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
