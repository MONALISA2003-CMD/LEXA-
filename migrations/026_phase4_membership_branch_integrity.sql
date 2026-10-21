-- ACCEPTED REPLACEMENT — ORIGINAL HISTORICAL SOURCE LOST; NOT BYTE-IDENTICAL.
-- Accepted 2026-10-21 for reproducible clean replay after source-loss decision.
-- Do not describe this file as the exact SQL originally applied in production.
-- Full migration identity: 026_phase4_membership_branch_integrity.
CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_memberships_tenant_id ON tenant_memberships(tenant_id,id);
CREATE TABLE IF NOT EXISTS membership_branch_assignments (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 membership_id uuid NOT NULL REFERENCES tenant_memberships(id) ON DELETE CASCADE,
 branch_id uuid NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
 status varchar NOT NULL DEFAULT 'ACTIVE',
 created_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT mba_status_check CHECK(status IN ('ACTIVE','INACTIVE')),
 CONSTRAINT mba_membership_tenant_fk FOREIGN KEY(tenant_id,membership_id) REFERENCES tenant_memberships(tenant_id,id) ON DELETE CASCADE,
 CONSTRAINT mba_branch_tenant_fk FOREIGN KEY(tenant_id,branch_id) REFERENCES branches(tenant_id,id) ON DELETE CASCADE,
 UNIQUE(tenant_id,membership_id,branch_id)
);
CREATE INDEX IF NOT EXISTS idx_mba_tenant_branch ON membership_branch_assignments(tenant_id,branch_id,status);
CREATE INDEX IF NOT EXISTS idx_membership_branch_assignments_tenant ON membership_branch_assignments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_membership_branch_assignments_branch ON membership_branch_assignments(tenant_id,branch_id);
ALTER TABLE membership_branch_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE membership_branch_assignments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS membership_branch_assignments_tenant_isolation ON membership_branch_assignments;
CREATE POLICY membership_branch_assignments_tenant_isolation ON membership_branch_assignments
 USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid);
GRANT SELECT,INSERT,UPDATE,DELETE ON membership_branch_assignments TO lexa_app;
