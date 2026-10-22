-- Phase 3 auth-surface RLS completion.
-- Apply only after the API deploy sets app.pre_tenant_access for login/registration.
-- RLS policies use transaction-local context; backend must not expose arbitrary SQL.
DO $$
BEGIN
  IF to_regclass('public.permissions') IS NULL
     OR to_regclass('public.schema_migrations') IS NULL
     OR to_regclass('public.users') IS NULL
     OR to_regclass('public.tenants') IS NULL
     OR to_regclass('public.registration_requests') IS NULL THEN
    RAISE EXCEPTION 'Required Phase 3 auth-surface tables are missing';
  END IF;
END $$;

GRANT SELECT ON public.permissions, public.schema_migrations TO lexa_app;
ALTER TABLE public.permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.permissions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lexa_permissions_catalog_read ON public.permissions;
CREATE POLICY lexa_permissions_catalog_read ON public.permissions
  FOR SELECT TO lexa_app USING (true);

ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.schema_migrations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lexa_schema_migrations_read ON public.schema_migrations;
CREATE POLICY lexa_schema_migrations_read ON public.schema_migrations
  FOR SELECT TO lexa_app USING (true);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lexa_users_self_or_pretenant_read ON public.users;
CREATE POLICY lexa_users_self_or_pretenant_read ON public.users
  FOR SELECT TO lexa_app
  USING (
    id = NULLIF(current_setting('app.user_id', true), '')::uuid
    OR (
      current_setting('app.pre_tenant_access', true) IN ('login', 'registration')
      AND lower(email) = lower(NULLIF(current_setting('app.pre_tenant_email', true), ''))
    )
  );
DROP POLICY IF EXISTS lexa_users_registration_insert ON public.users;
CREATE POLICY lexa_users_registration_insert ON public.users
  FOR INSERT TO lexa_app
  WITH CHECK (current_setting('app.pre_tenant_access', true) = 'registration');
DROP POLICY IF EXISTS lexa_users_self_update ON public.users;
CREATE POLICY lexa_users_self_update ON public.users
  FOR UPDATE TO lexa_app
  USING (id = NULLIF(current_setting('app.user_id', true), '')::uuid)
  WITH CHECK (id = NULLIF(current_setting('app.user_id', true), '')::uuid);

ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenants FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lexa_tenants_current_or_registration_read ON public.tenants;
CREATE POLICY lexa_tenants_current_or_registration_read ON public.tenants
  FOR SELECT TO lexa_app
  USING (
    id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  );
DROP POLICY IF EXISTS lexa_tenants_registration_insert ON public.tenants;
CREATE POLICY lexa_tenants_registration_insert ON public.tenants
  FOR INSERT TO lexa_app
  WITH CHECK (current_setting('app.pre_tenant_access', true) = 'registration');
DROP POLICY IF EXISTS lexa_tenants_current_update ON public.tenants;
CREATE POLICY lexa_tenants_current_update ON public.tenants
  FOR UPDATE TO lexa_app
  USING (id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE public.registration_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.registration_requests FORCE ROW LEVEL SECURITY;
REVOKE DELETE ON public.registration_requests FROM lexa_app;
DROP POLICY IF EXISTS lexa_registration_requests_pretenant ON public.registration_requests;
CREATE POLICY lexa_registration_requests_pretenant ON public.registration_requests
  FOR ALL TO lexa_app
  USING (
    current_setting('app.pre_tenant_access', true) = 'registration'
    AND idempotency_key = NULLIF(current_setting('app.registration_key', true), '')
  )
  WITH CHECK (
    current_setting('app.pre_tenant_access', true) = 'registration'
    AND idempotency_key = NULLIF(current_setting('app.registration_key', true), '')
  );

INSERT INTO public.schema_migrations(version)
VALUES ('031_phase3_auth_surface_rls')
ON CONFLICT (version) DO NOTHING;
