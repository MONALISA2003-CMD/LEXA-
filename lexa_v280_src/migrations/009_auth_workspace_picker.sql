-- LEXA Phase 2.5: workspace-aware sign-in
-- Additive only. No business data is removed or rewritten.

CREATE OR REPLACE FUNCTION public.lexa_list_user_workspaces(p_user_id uuid)
RETURNS TABLE (
  tenant_id uuid,
  tenant_name varchar,
  membership_id uuid
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
  SELECT tm.tenant_id, t.name, tm.id
  FROM public.tenant_memberships tm
  INNER JOIN public.tenants t ON t.id = tm.tenant_id
  WHERE tm.user_id = p_user_id
    AND tm.status = 'ACTIVE'
    AND t.status = 'ACTIVE'
  ORDER BY t.name ASC;
$$;

REVOKE ALL ON FUNCTION public.lexa_list_user_workspaces(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.lexa_list_user_workspaces(uuid) TO lexa_app;

INSERT INTO schema_migrations (version)
VALUES ('009_auth_workspace_picker')
ON CONFLICT (version) DO NOTHING;
