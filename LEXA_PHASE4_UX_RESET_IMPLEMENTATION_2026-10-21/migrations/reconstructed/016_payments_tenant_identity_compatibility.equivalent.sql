-- REPLAY-ONLY COMPATIBILITY DELTA — NOT AN ORIGINAL HISTORICAL MIGRATION.
-- Isolated replay of checked-in 016 fails without a unique composite key on payments(tenant_id,id).
-- The canonical Neon schema has uq_payments_tenant_id, while checked-in 012 does not create it.
-- Keep as a documented schema-delta repair; do not insert into original source paths.
CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_tenant_id ON public.payments(tenant_id,id);
