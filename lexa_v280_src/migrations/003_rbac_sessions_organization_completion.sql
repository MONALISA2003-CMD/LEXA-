-- LEXA Phase 1, Slice 3: authorization, sessions/devices, locations and POS completion.
-- Additive and non-destructive. No reset, delete, or reseed of business data.

CREATE TABLE IF NOT EXISTS devices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  device_key varchar(200) NOT NULL,
  name varchar(200),
  platform varchar(50),
  last_seen_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, device_key)
);

CREATE TABLE IF NOT EXISTS sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  device_id uuid REFERENCES devices(id) ON DELETE SET NULL,
  refresh_token_hash text NOT NULL,
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_used_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_devices_tenant ON devices(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sessions_tenant_user ON sessions(tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

ALTER TABLE devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY devices_tenant_isolation ON devices
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY sessions_tenant_isolation ON sessions
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- Composite tenant FKs prevent accidental cross-tenant references even when IDs are valid.
CREATE UNIQUE INDEX IF NOT EXISTS uq_branches_tenant_id ON branches(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_warehouses_tenant_id ON warehouses(tenant_id, id);
ALTER TABLE warehouses DROP CONSTRAINT IF EXISTS fk_warehouses_branch_tenant;
ALTER TABLE warehouses ADD CONSTRAINT fk_warehouses_branch_tenant
  FOREIGN KEY (tenant_id, branch_id) REFERENCES branches(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_locations_tenant_id ON locations(tenant_id, id);
ALTER TABLE locations DROP CONSTRAINT IF EXISTS fk_locations_warehouse_tenant;
ALTER TABLE locations ADD CONSTRAINT fk_locations_warehouse_tenant
  FOREIGN KEY (tenant_id, warehouse_id) REFERENCES warehouses(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE pos_terminals DROP CONSTRAINT IF EXISTS fk_pos_terminals_branch_tenant;
ALTER TABLE pos_terminals ADD CONSTRAINT fk_pos_terminals_branch_tenant
  FOREIGN KEY (tenant_id, branch_id) REFERENCES branches(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_roles_tenant_id ON roles(tenant_id, id);
ALTER TABLE membership_roles DROP CONSTRAINT IF EXISTS fk_membership_roles_role_tenant;
ALTER TABLE membership_roles ADD CONSTRAINT fk_membership_roles_role_tenant
  FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE;
