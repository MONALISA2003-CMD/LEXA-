-- REPLAY-ONLY COMPATIBILITY STEP, NOT A HISTORICAL MIGRATION.
-- Run after reconstructed 025 permissions and before reconstructed 026 branch-integrity source.
-- Migration 023 creates this table with composite tenant FKs but without the later id/status columns.
DO $$ BEGIN
  IF to_regclass('public.membership_branch_assignments') IS NULL THEN
    RAISE EXCEPTION '025a prerequisite missing; migration 023 must create membership_branch_assignments';
  END IF;
END $$;
ALTER TABLE public.membership_branch_assignments ADD COLUMN IF NOT EXISTS id uuid DEFAULT gen_random_uuid();
UPDATE public.membership_branch_assignments SET id=gen_random_uuid() WHERE id IS NULL;
ALTER TABLE public.membership_branch_assignments ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE public.membership_branch_assignments ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS lexa_phase2_uq_membership_branch_assignment_id ON public.membership_branch_assignments(id);
DO $$
DECLARE pk_name text; pk_def text;
BEGIN
  SELECT conname,pg_get_constraintdef(oid) INTO pk_name,pk_def
  FROM pg_constraint WHERE conrelid='public.membership_branch_assignments'::regclass AND contype='p';
  IF pk_name IS NOT NULL AND pk_def <> 'PRIMARY KEY (id)' THEN
    EXECUTE format('ALTER TABLE public.membership_branch_assignments DROP CONSTRAINT %I',pk_name);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.membership_branch_assignments'::regclass AND contype='p' AND pg_get_constraintdef(oid)='PRIMARY KEY (id)') THEN
    ALTER TABLE public.membership_branch_assignments ADD CONSTRAINT membership_branch_assignments_pkey PRIMARY KEY(id);
  END IF;
END $$;
-- The new primary key now guarantees uniqueness; discard the temporary unique index.
DROP INDEX IF EXISTS public.lexa_phase2_uq_membership_branch_assignment_id;
ALTER TABLE public.membership_branch_assignments ADD COLUMN IF NOT EXISTS status varchar(30) NOT NULL DEFAULT 'ACTIVE';
ALTER TABLE public.membership_branch_assignments ADD COLUMN IF NOT EXISTS assigned_by_user_id uuid REFERENCES public.users(id) ON DELETE SET NULL;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.membership_branch_assignments'::regclass AND conname='membership_branch_assignments_status_ck') THEN
    ALTER TABLE public.membership_branch_assignments ADD CONSTRAINT membership_branch_assignments_status_ck CHECK(status IN ('ACTIVE','INACTIVE')) NOT VALID;
  END IF;
END $$;
ALTER TABLE public.membership_branch_assignments VALIDATE CONSTRAINT membership_branch_assignments_status_ck;
CREATE INDEX IF NOT EXISTS idx_mba_tenant_branch ON public.membership_branch_assignments(tenant_id,branch_id,status);
INSERT INTO public.schema_migrations(version) VALUES ('025a_phase2_membership_branch_contract_reconciliation') ON CONFLICT(version) DO NOTHING;
