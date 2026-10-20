-- SQL regression test for migration 030's active-workspace lookup.
-- Run only against a disposable isolated database where these existing
-- application tables and the migration-defined helper are already present.
-- Fixtures are random and deleted before the DO statement commits. If an
-- assertion fails, PostgreSQL rolls back the entire DO statement.
DO $test$
DECLARE
  tenant_a uuid := gen_random_uuid();
  tenant_b uuid := gen_random_uuid();
  user_a uuid := gen_random_uuid();
  user_b uuid := gen_random_uuid();
  found_count integer;
  found_tenant uuid;
BEGIN
  INSERT INTO public.tenants(id, name, status)
  VALUES (tenant_a, 'SQL regression A ' || tenant_a::text, 'ACTIVE'),
         (tenant_b, 'SQL regression B ' || tenant_b::text, 'ACTIVE');

  INSERT INTO public.users(id, email, password_hash, is_active)
  VALUES (user_a, 'sql-regression-' || user_a::text || '@invalid.example', 'not-a-real-password-hash', true),
         (user_b, 'sql-regression-' || user_b::text || '@invalid.example', 'not-a-real-password-hash', true);

  INSERT INTO public.tenant_memberships(id, tenant_id, user_id, status)
  VALUES (gen_random_uuid(), tenant_a, user_a, 'ACTIVE'),
         (gen_random_uuid(), tenant_b, user_b, 'ACTIVE');

  -- A caller authenticated as B must not enumerate A even when passing A's UUID.
  PERFORM set_config('app.tenant_id', tenant_b::text, true);
  PERFORM set_config('app.user_id', user_b::text, true);
  SELECT count(*) INTO found_count
  FROM public.lexa_list_active_user_workspaces(user_a);
  IF found_count <> 0 THEN
    RAISE EXCEPTION 'workspace identity leak: user B enumerated user A workspaces';
  END IF;

  SELECT count(*) INTO found_count
  FROM public.lexa_list_active_user_workspaces(user_b);
  SELECT tenant_id INTO found_tenant
  FROM public.lexa_list_active_user_workspaces(user_b) LIMIT 1;
  IF found_count <> 1 OR found_tenant IS DISTINCT FROM tenant_b THEN
    RAISE EXCEPTION 'authenticated user workspace lookup did not return only user B workspace';
  END IF;

  -- Missing transaction identity is fail-closed, even if an arbitrary ID is supplied.
  PERFORM set_config('app.user_id', '', true);
  SELECT count(*) INTO found_count
  FROM public.lexa_list_active_user_workspaces(user_b);
  IF found_count <> 0 THEN
    RAISE EXCEPTION 'workspace identity leak: missing app.user_id did not fail closed';
  END IF;

  DELETE FROM public.tenant_memberships WHERE tenant_id IN (tenant_a, tenant_b);
  DELETE FROM public.users WHERE id IN (user_a, user_b);
  DELETE FROM public.tenants WHERE id IN (tenant_a, tenant_b);
END;
$test$;
