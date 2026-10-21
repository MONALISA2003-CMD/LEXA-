-- REPLAY-ONLY COMPATIBILITY STEP, NOT A HISTORICAL MIGRATION.
-- Run after 005_inventory_foundation and before 006_phase1_security_reliability ONLY in a clean isolated replay.
-- The available 004 source creates a catalog outbox shape; 006 expects a newer transactional-outbox contract.
-- This file is intentionally under migrations/reconstructed and must not be used as a production hotfix.
DO $$
DECLARE correlation_type text;
BEGIN
  IF to_regclass('public.outbox_events') IS NULL THEN RAISE EXCEPTION '005a prerequisite missing; apply the replay-equivalent 004 first'; END IF;
  SELECT data_type INTO correlation_type FROM information_schema.columns WHERE table_schema='public' AND table_name='outbox_events' AND column_name='correlation_id';
  IF correlation_type IS NOT NULL AND correlation_type <> 'uuid' THEN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='outbox_events' AND column_name='correlation_id_legacy') THEN
      RAISE EXCEPTION 'outbox_events has both a non-UUID correlation_id and correlation_id_legacy; manual review required';
    END IF;
    ALTER TABLE public.outbox_events RENAME COLUMN correlation_id TO correlation_id_legacy;
  END IF;
END $$;
ALTER TABLE public.outbox_events ADD COLUMN IF NOT EXISTS recorded_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE public.outbox_events ADD COLUMN IF NOT EXISTS actor_id uuid REFERENCES public.users(id) ON DELETE SET NULL;
ALTER TABLE public.outbox_events ADD COLUMN IF NOT EXISTS correlation_id uuid;
ALTER TABLE public.outbox_events ADD COLUMN IF NOT EXISTS causation_id uuid;
ALTER TABLE public.outbox_events ADD COLUMN IF NOT EXISTS idempotency_key varchar(200);
ALTER TABLE public.outbox_events ADD COLUMN IF NOT EXISTS status varchar(30) NOT NULL DEFAULT 'PENDING';
ALTER TABLE public.outbox_events ADD COLUMN IF NOT EXISTS attempt_count integer NOT NULL DEFAULT 0;
ALTER TABLE public.outbox_events ADD COLUMN IF NOT EXISTS available_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE public.outbox_events ADD COLUMN IF NOT EXISTS processed_at timestamptz;
ALTER TABLE public.outbox_events ADD COLUMN IF NOT EXISTS last_error text;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='outbox_events' AND column_name='actor_user_id') THEN
    UPDATE public.outbox_events SET actor_id=actor_user_id WHERE actor_id IS NULL;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='outbox_events' AND column_name='created_at') THEN
    UPDATE public.outbox_events SET recorded_at=created_at WHERE recorded_at>created_at;
    UPDATE public.outbox_events SET available_at=created_at WHERE available_at>created_at;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='outbox_events' AND column_name='published_at') THEN
    UPDATE public.outbox_events SET status='PUBLISHED', processed_at=COALESCE(processed_at,published_at) WHERE published_at IS NOT NULL AND status='PENDING';
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='outbox_events' AND column_name='correlation_id_legacy') THEN
    UPDATE public.outbox_events SET correlation_id=correlation_id_legacy::uuid
    WHERE correlation_id IS NULL AND correlation_id_legacy ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';
  END IF;
END $$;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.outbox_events'::regclass AND conname='outbox_events_status_check') THEN
    ALTER TABLE public.outbox_events ADD CONSTRAINT outbox_events_status_check CHECK(status IN ('PENDING','PROCESSING','PUBLISHED','FAILED','DEAD_LETTER')) NOT VALID;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.outbox_events'::regclass AND conname='outbox_events_attempt_check') THEN
    ALTER TABLE public.outbox_events ADD CONSTRAINT outbox_events_attempt_check CHECK(attempt_count>=0) NOT VALID;
  END IF;
END $$;
ALTER TABLE public.outbox_events VALIDATE CONSTRAINT outbox_events_status_check;
ALTER TABLE public.outbox_events VALIDATE CONSTRAINT outbox_events_attempt_check;
CREATE INDEX IF NOT EXISTS lexa_phase0_outbox_status_available_idx ON public.outbox_events(status,available_at);
CREATE TABLE IF NOT EXISTS public.schema_migrations(version varchar(100) PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
INSERT INTO public.schema_migrations(version) VALUES ('005a_phase0_outbox_contract_reconciliation') ON CONFLICT(version) DO NOTHING;
