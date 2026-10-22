-- Phase 3 runtime privilege surface hardening; applied 2026-10-21.
-- Keep permissions reference data readable but not mutable by the application role.
-- Keep migration metadata read-only to the application role so readiness can verify auth migrations.
BEGIN;
ALTER TABLE public.permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.permissions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS permissions_read_reference ON public.permissions;
CREATE POLICY permissions_read_reference ON public.permissions FOR SELECT TO lexa_app USING (true);
REVOKE ALL PRIVILEGES ON TABLE public.permissions FROM PUBLIC;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLE public.permissions FROM lexa_app;
GRANT SELECT ON TABLE public.permissions TO lexa_app;
ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.schema_migrations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS schema_migrations_app_access ON public.schema_migrations;
DROP POLICY IF EXISTS schema_migrations_app_read ON public.schema_migrations;
CREATE POLICY schema_migrations_app_read ON public.schema_migrations FOR SELECT TO lexa_app USING (true);
REVOKE ALL PRIVILEGES ON TABLE public.schema_migrations FROM PUBLIC;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLE public.schema_migrations FROM lexa_app;
GRANT SELECT ON TABLE public.schema_migrations TO lexa_app;
INSERT INTO public.schema_migrations(version) VALUES ('029_phase3_runtime_privilege_surface') ON CONFLICT (version) DO NOTHING;
COMMIT;
