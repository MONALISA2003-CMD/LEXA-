-- LEXA Phase 1: provision a separate, least-privilege runtime login.
--
-- IMPORTANT:
--   * Validate on an isolated Neon branch before any production rollout.
--   * This migration creates a role with NO password. After it passes, set its
--     password with Neon role management; never commit a connection string.
--   * Configure Render DATABASE_LOGIN_ROLE=lexa_runtime_safe and update the
--     pooled DATABASE_URL username/password together only during an approved
--     production release. Existing lexa_runtime is deliberately untouched.
--   * The app continues to use DATABASE_APP_ROLE=lexa_app inside transactions.

DO $create_role$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lexa_runtime_safe') THEN
        EXECUTE 'CREATE ROLE lexa_runtime_safe LOGIN NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS';
    END IF;
END
$create_role$;

DO $preflight$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lexa_runtime_safe' AND rolcanlogin
                   AND NOT rolsuper AND NOT rolinherit AND NOT rolcreatedb
                   AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls) THEN
        RAISE EXCEPTION 'LEXA Phase 1 preflight failed: lexa_runtime_safe is not a least-privilege login';
    END IF;
    IF pg_has_role('lexa_runtime_safe', 'neon_superuser', 'MEMBER') THEN
        RAISE EXCEPTION 'LEXA Phase 1 preflight failed: lexa_runtime_safe belongs to neon_superuser';
    END IF;
END
$preflight$;

-- The membership is SET-only: the login does not inherit the application's
-- broad object grants outside the transaction-local SET ROLE boundary.
GRANT lexa_app TO lexa_runtime_safe WITH INHERIT FALSE, SET TRUE;

-- A freshly created role has no direct table/sequence/function privileges.
-- Revoke defensively in case the migration is re-run after a manual grant.
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM lexa_runtime_safe;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM lexa_runtime_safe;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM lexa_runtime_safe;

DO $verify$
BEGIN
    IF NOT pg_has_role('lexa_runtime_safe', 'lexa_app', 'SET') THEN
        RAISE EXCEPTION 'LEXA Phase 1 verification failed: safe runtime cannot SET ROLE lexa_app';
    END IF;
    IF pg_has_role('lexa_runtime_safe', 'neon_superuser', 'MEMBER') THEN
        RAISE EXCEPTION 'LEXA Phase 1 verification failed: safe runtime belongs to neon_superuser';
    END IF;
    IF has_table_privilege('lexa_runtime_safe', 'public.users', 'SELECT')
       OR has_table_privilege('lexa_runtime_safe', 'public.schema_migrations', 'DELETE') THEN
        RAISE EXCEPTION 'LEXA Phase 1 verification failed: safe runtime has direct table privileges';
    END IF;
END
$verify$;

INSERT INTO public.schema_migrations(version)
VALUES ('029_phase1_runtime_role_least_privilege')
ON CONFLICT (version) DO NOTHING;
