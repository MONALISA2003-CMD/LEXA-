-- LEXA forecast history bootstrap. This is additive and does not run on deployment.
-- It creates a bounded SECURITY DEFINER worker entry point so the API's least-
-- privilege role can refresh a complete tenant-owned 56-day projection window.
-- Validate on an isolated Neon branch before applying to the live branch.
BEGIN;

DO $$
BEGIN
  IF to_regclass('public.tenants') IS NULL
     OR to_regclass('public.tenant_settings') IS NULL
     OR to_regclass('public.analytics_refresh_runs') IS NULL
     OR to_regclass('public.schema_migrations') IS NULL THEN
    RAISE EXCEPTION 'LEXA 56-day history backfill prerequisites are missing';
  END IF;
  IF to_regprocedure('public.refresh_analytics(uuid,date,date)') IS NULL
     OR to_regprocedure('public.lexa_business_date(timestamp with time zone,uuid)') IS NULL THEN
    RAISE EXCEPTION 'LEXA analytics refresh functions are missing';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'lexa_app') THEN
    RAISE EXCEPTION 'LEXA application role lexa_app is missing';
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.refresh_analytics_forecast_baselines(p_limit integer DEFAULT 1)
RETURNS TABLE(processed_count integer, failed_count integer)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  t record;
  v_from date;
  v_error text;
  v_processed integer := 0;
  v_failed integer := 0;
BEGIN
  IF p_limit < 1 OR p_limit > 5 THEN
    RAISE EXCEPTION 'History backfill batch size must be between 1 and 5';
  END IF;

  -- Do not repeatedly refresh every tenant on every poll. A tenant is selected
  -- only when no successful 56-day refresh covers the current tenant business
  -- date within 72 hours, and no recent attempt is running or cooling down.
  FOR t IN
    SELECT x.tenant_id, x.business_date
      FROM (
        SELECT tn.id AS tenant_id,
               public.lexa_business_date(now(), tn.id) AS business_date
          FROM public.tenants tn
         WHERE tn.status = 'ACTIVE'
      ) x
     WHERE NOT EXISTS (
       SELECT 1
         FROM public.analytics_refresh_runs r
        WHERE r.tenant_id = x.tenant_id
          AND r.status = 'SUCCEEDED'
          AND r.from_date <= x.business_date - 55
          AND r.to_date >= x.business_date
          AND r.completed_at >= now() - interval '72 hours'
     )
       AND NOT EXISTS (
       SELECT 1
         FROM public.analytics_refresh_runs r
        WHERE r.tenant_id = x.tenant_id
          AND r.status IN ('RUNNING', 'FAILED')
          AND r.from_date <= x.business_date - 55
          AND r.to_date >= x.business_date
          AND r.started_at >= now() - interval '15 minutes'
     )
     ORDER BY x.tenant_id
     LIMIT p_limit
  LOOP
    v_from := t.business_date - 55;

    -- Serialize overlapping backfills for this tenant across any API replicas.
    PERFORM pg_advisory_xact_lock(hashtextextended(t.tenant_id::text || ':analytics-history', 0));

    -- Recheck after acquiring the lock; another replica may have completed it.
    IF EXISTS (
      SELECT 1
        FROM public.analytics_refresh_runs r
       WHERE r.tenant_id = t.tenant_id
         AND r.status = 'SUCCEEDED'
         AND r.from_date <= v_from
         AND r.to_date >= t.business_date
         AND r.completed_at >= now() - interval '72 hours'
    ) OR EXISTS (
      SELECT 1
        FROM public.analytics_refresh_runs r
       WHERE r.tenant_id = t.tenant_id
         AND r.status IN ('RUNNING', 'FAILED')
         AND r.from_date <= v_from
         AND r.to_date >= t.business_date
         AND r.started_at >= now() - interval '15 minutes'
    ) THEN
      CONTINUE;
    END IF;

    BEGIN
      PERFORM public.refresh_analytics(t.tenant_id, v_from, t.business_date);
      v_processed := v_processed + 1;
    EXCEPTION WHEN OTHERS THEN
      GET STACKED DIAGNOSTICS v_error = MESSAGE_TEXT;
      -- The failed call's own transaction scope is rolled back by the exception
      -- block. Write a durable failure marker afterwards to provide a cooldown
      -- and avoid hammering the same tenant every few seconds.
      INSERT INTO public.analytics_refresh_runs (
        tenant_id, from_date, to_date, status, started_at, completed_at, error_message
      ) VALUES (
        t.tenant_id, v_from, t.business_date, 'FAILED', now(), now(), left(v_error, 1000)
      );
      v_failed := v_failed + 1;
      RAISE WARNING 'LEXA analytics history backfill failed for tenant %: %', t.tenant_id, left(v_error, 300);
    END;
  END LOOP;

  RETURN QUERY SELECT v_processed, v_failed;
END
$function$;

REVOKE ALL ON FUNCTION public.refresh_analytics_forecast_baselines(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.refresh_analytics_forecast_baselines(integer) TO lexa_app;

INSERT INTO public.schema_migrations(version)
VALUES ('047_analytics_forecast_history_backfill')
ON CONFLICT (version) DO NOTHING;
COMMIT;
