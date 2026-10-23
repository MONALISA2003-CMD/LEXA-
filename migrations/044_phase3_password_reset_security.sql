-- Phase 3 security increment: one-time password-reset tokens and safe session revocation.
-- Apply through the reviewed migration runner before releasing API code that requires 044.
-- Additive only. Does not modify passwords, existing tokens, or user sessions at migration time.

DO $$
DECLARE
  v_owner_bypasses_rls boolean;
BEGIN
  IF to_regclass('public.users') IS NULL
     OR to_regclass('public.sessions') IS NULL
     OR to_regclass('public.user_security_tokens') IS NULL
     OR to_regclass('public.schema_migrations') IS NULL THEN
    RAISE EXCEPTION 'Phase 3 password-reset prerequisites are missing';
  END IF;
  SELECT rolbypassrls INTO v_owner_bypasses_rls
    FROM pg_catalog.pg_roles WHERE rolname = current_user;
  IF NOT COALESCE(v_owner_bypasses_rls, false) THEN
    RAISE EXCEPTION 'Phase 3 password-reset functions must be installed by a database migration role that safely bypasses forced RLS';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'lexa_app') THEN
    RAISE EXCEPTION 'LEXA application role is missing';
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_user_security_tokens_password_reset_expiry
  ON public.user_security_tokens(expires_at)
  WHERE token_type='PASSWORD_RESET' AND used_at IS NULL;

-- The app can request a reset for an email address; the database returns minimal
-- user identity only to the server-side runtime. The HTTP handler always sends the
-- same public response for existing and unknown accounts.
CREATE OR REPLACE FUNCTION public.lexa_issue_password_reset(
  p_email text,
  p_token_hash text,
  p_expires_at timestamptz
)
RETURNS TABLE(user_id uuid, email text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_user_id uuid;
  v_email text;
BEGIN
  IF p_email IS NULL OR length(btrim(p_email)) = 0
     OR p_token_hash IS NULL OR p_token_hash !~ '^[0-9a-f]{64}$'
     OR p_expires_at IS NULL OR p_expires_at <= now()
     OR p_expires_at > now() + interval '60 minutes' THEN
    RETURN;
  END IF;

  SELECT u.id, u.email
    INTO v_user_id, v_email
    FROM public.users u
   WHERE lower(u.email) = lower(btrim(p_email))
     AND u.is_active = true
   FOR UPDATE;
  IF v_user_id IS NULL THEN
    RETURN;
  END IF;

  -- Only the newest link for an account remains valid.
  UPDATE public.user_security_tokens
     SET used_at = now()
   WHERE user_security_tokens.user_id = v_user_id
     AND token_type = 'PASSWORD_RESET'
     AND used_at IS NULL;

  INSERT INTO public.user_security_tokens(user_id, token_type, token_hash, expires_at)
  VALUES (v_user_id, 'PASSWORD_RESET', p_token_hash, p_expires_at);

  RETURN QUERY SELECT v_user_id, v_email;
END
$$;

-- Consumes the bearer token exactly once, changes the password, and revokes sessions
-- for this user across every tenant. A reset never silently logs the user back in.
CREATE OR REPLACE FUNCTION public.lexa_consume_password_reset(
  p_token_hash text,
  p_password_hash text
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_user_id uuid;
BEGIN
  IF p_token_hash IS NULL OR p_token_hash !~ '^[0-9a-f]{64}$'
     OR p_password_hash IS NULL OR length(p_password_hash) < 40 OR length(p_password_hash) > 500
     OR left(p_password_hash, 1) <> '$' THEN
    RETURN false;
  END IF;

  SELECT t.user_id
    INTO v_user_id
    FROM public.user_security_tokens t
    JOIN public.users u ON u.id = t.user_id AND u.is_active = true
   WHERE t.token_hash = p_token_hash
     AND t.token_type = 'PASSWORD_RESET'
     AND t.used_at IS NULL
     AND t.expires_at > now()
   FOR UPDATE OF t, u;
  IF v_user_id IS NULL THEN
    RETURN false;
  END IF;

  UPDATE public.users
     SET password_hash = p_password_hash
   WHERE id = v_user_id AND is_active = true;
  IF NOT FOUND THEN
    UPDATE public.user_security_tokens
       SET used_at = now()
     WHERE user_id = v_user_id AND token_type = 'PASSWORD_RESET' AND used_at IS NULL;
    RETURN false;
  END IF;

  UPDATE public.user_security_tokens
     SET used_at = now()
   WHERE user_id = v_user_id AND token_type = 'PASSWORD_RESET' AND used_at IS NULL;

  UPDATE public.sessions
     SET revoked_at = COALESCE(revoked_at, now())
   WHERE user_id = v_user_id AND revoked_at IS NULL;

  RETURN true;
END
$$;

-- Invalidate a freshly issued token if the email provider cannot deliver the message.
CREATE OR REPLACE FUNCTION public.lexa_revoke_password_reset(p_token_hash text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_count integer;
BEGIN
  IF p_token_hash IS NULL OR p_token_hash !~ '^[0-9a-f]{64}$' THEN
    RETURN false;
  END IF;
  UPDATE public.user_security_tokens
     SET used_at = now()
   WHERE token_hash = p_token_hash
     AND token_type = 'PASSWORD_RESET'
     AND used_at IS NULL;
  GET DIAGNOSTICS v_count = ROW_COUNT;
  RETURN v_count > 0;
END
$$;

REVOKE ALL ON FUNCTION public.lexa_issue_password_reset(text, text, timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.lexa_consume_password_reset(text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.lexa_revoke_password_reset(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.lexa_issue_password_reset(text, text, timestamptz) TO lexa_app;
GRANT EXECUTE ON FUNCTION public.lexa_consume_password_reset(text, text) TO lexa_app;
GRANT EXECUTE ON FUNCTION public.lexa_revoke_password_reset(text) TO lexa_app;

INSERT INTO public.schema_migrations(version)
VALUES ('044_phase3_password_reset_security')
ON CONFLICT(version) DO NOTHING;
