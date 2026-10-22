-- LEXA Phase 1 Business Kernel
-- Additive-only. Universal tenant-scoped primitives for multi-business support.
-- Target: LEXA project wispy-mud-75323042, branch br-soft-star-b1dj2m2w, database neondb.

CREATE TABLE IF NOT EXISTS parties (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  party_type varchar(30) NOT NULL DEFAULT 'PERSON',
  display_name varchar(250) NOT NULL,
  legal_name varchar(250),
  email varchar(320),
  phone varchar(50),
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  deleted_by uuid REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT parties_party_type_check CHECK (party_type IN ('PERSON','ORGANIZATION')),
  CONSTRAINT parties_status_check CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED')),
  CONSTRAINT parties_tenant_id_id_key UNIQUE (tenant_id, id)
);

CREATE INDEX IF NOT EXISTS idx_parties_tenant_name ON parties(tenant_id, display_name);
CREATE INDEX IF NOT EXISTS idx_parties_tenant_status ON parties(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_parties_tenant_email ON parties(tenant_id, email);

CREATE TABLE IF NOT EXISTS party_roles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  party_id uuid NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
  role_type varchar(40) NOT NULL,
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT party_roles_type_check CHECK (role_type IN ('CUSTOMER','SUPPLIER','EMPLOYEE','CONTACT','OTHER')),
  CONSTRAINT party_roles_status_check CHECK (status IN ('ACTIVE','INACTIVE')),
  CONSTRAINT party_roles_unique UNIQUE (tenant_id, party_id, role_type),
  CONSTRAINT party_roles_party_tenant_fk FOREIGN KEY (tenant_id, party_id) REFERENCES parties(tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_party_roles_tenant_role ON party_roles(tenant_id, role_type);

CREATE TABLE IF NOT EXISTS services (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name varchar(250) NOT NULL,
  code varchar(80) NOT NULL,
  description text,
  service_type varchar(80),
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT services_status_check CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED')),
  CONSTRAINT services_tenant_code_key UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS resources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  resource_type varchar(80) NOT NULL,
  name varchar(250) NOT NULL,
  code varchar(80) NOT NULL,
  capacity numeric(18,6),
  status varchar(30) NOT NULL DEFAULT 'AVAILABLE',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT resources_status_check CHECK (status IN ('AVAILABLE','BUSY','MAINTENANCE','INACTIVE')),
  CONSTRAINT resources_tenant_code_key UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS assets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  asset_type varchar(80) NOT NULL,
  name varchar(250) NOT NULL,
  code varchar(80) NOT NULL,
  serial_number varchar(120),
  resource_id uuid REFERENCES resources(id) ON DELETE SET NULL,
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT assets_status_check CHECK (status IN ('ACTIVE','INACTIVE','RETIRED')),
  CONSTRAINT assets_tenant_code_key UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  document_type varchar(80) NOT NULL,
  entity_type varchar(80),
  entity_id uuid,
  name varchar(250) NOT NULL,
  mime_type varchar(120),
  storage_key varchar(500),
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT documents_status_check CHECK (status IN ('ACTIVE','ARCHIVED','DELETED'))
);

CREATE INDEX IF NOT EXISTS idx_documents_entity ON documents(tenant_id, entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_documents_tenant_type ON documents(tenant_id, document_type);

CREATE TABLE IF NOT EXISTS business_transactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  transaction_type varchar(80) NOT NULL,
  reference varchar(120) NOT NULL,
  status varchar(40) NOT NULL DEFAULT 'DRAFT',
  party_id uuid REFERENCES parties(id) ON DELETE SET NULL,
  branch_id uuid REFERENCES branches(id) ON DELETE SET NULL,
  total_amount numeric(20,4),
  currency_code varchar(3),
  occurred_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT business_transactions_tenant_reference_key UNIQUE (tenant_id, reference),
  CONSTRAINT business_transactions_tenant_id_id_key UNIQUE (tenant_id, id),
  CONSTRAINT business_transactions_tenant_party_fk FOREIGN KEY (tenant_id, party_id) REFERENCES parties(tenant_id, id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_business_transactions_tenant_status ON business_transactions(tenant_id, status, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_business_transactions_party ON business_transactions(tenant_id, party_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS payments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  transaction_id uuid REFERENCES business_transactions(id) ON DELETE SET NULL,
  party_id uuid REFERENCES parties(id) ON DELETE SET NULL,
  amount numeric(20,4) NOT NULL,
  currency_code varchar(3) NOT NULL,
  method varchar(50) NOT NULL,
  status varchar(30) NOT NULL DEFAULT 'RECORDED',
  reference varchar(120),
  paid_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT payments_amount_positive CHECK (amount > 0),
  CONSTRAINT payments_tenant_transaction_fk FOREIGN KEY (tenant_id, transaction_id) REFERENCES business_transactions(tenant_id, id) ON DELETE SET NULL,
  CONSTRAINT payments_tenant_party_fk FOREIGN KEY (tenant_id, party_id) REFERENCES parties(tenant_id, id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_payments_tenant_paid_at ON payments(tenant_id, paid_at DESC);
CREATE INDEX IF NOT EXISTS idx_payments_transaction ON payments(tenant_id, transaction_id);

CREATE TABLE IF NOT EXISTS tasks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  title varchar(250) NOT NULL,
  description text,
  status varchar(30) NOT NULL DEFAULT 'OPEN',
  priority varchar(30) NOT NULL DEFAULT 'NORMAL',
  assigned_to_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  entity_type varchar(80),
  entity_id uuid,
  due_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT tasks_status_check CHECK (status IN ('OPEN','IN_PROGRESS','BLOCKED','COMPLETED','CANCELLED')),
  CONSTRAINT tasks_priority_check CHECK (priority IN ('LOW','NORMAL','HIGH','URGENT'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_tenant_status ON tasks(tenant_id, status, due_at);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(tenant_id, assigned_to_user_id, status);

CREATE TABLE IF NOT EXISTS business_cases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  case_type varchar(80) NOT NULL,
  title varchar(250) NOT NULL,
  status varchar(40) NOT NULL DEFAULT 'OPEN',
  priority varchar(30) NOT NULL DEFAULT 'NORMAL',
  party_id uuid REFERENCES parties(id) ON DELETE SET NULL,
  assigned_to_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  opened_at timestamptz NOT NULL DEFAULT now(),
  closed_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT cases_status_check CHECK (status IN ('OPEN','IN_PROGRESS','RESOLVED','CLOSED','CANCELLED')),
  CONSTRAINT cases_priority_check CHECK (priority IN ('LOW','NORMAL','HIGH','URGENT')),
  CONSTRAINT cases_tenant_party_fk FOREIGN KEY (tenant_id, party_id) REFERENCES parties(tenant_id, id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_cases_tenant_status ON business_cases(tenant_id, status, opened_at DESC);

CREATE TABLE IF NOT EXISTS business_projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name varchar(250) NOT NULL,
  code varchar(80) NOT NULL,
  status varchar(30) NOT NULL DEFAULT 'PLANNED',
  starts_at timestamptz,
  ends_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT projects_status_check CHECK (status IN ('PLANNED','ACTIVE','PAUSED','COMPLETED','CANCELLED')),
  CONSTRAINT projects_tenant_code_key UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS contracts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  contract_number varchar(120) NOT NULL,
  contract_type varchar(80) NOT NULL,
  title varchar(250) NOT NULL,
  status varchar(40) NOT NULL DEFAULT 'DRAFT',
  party_id uuid REFERENCES parties(id) ON DELETE SET NULL,
  starts_at timestamptz,
  ends_at timestamptz,
  terms jsonb NOT NULL DEFAULT '{}'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT contracts_status_check CHECK (status IN ('DRAFT','ACTIVE','EXPIRED','TERMINATED')),
  CONSTRAINT contracts_tenant_number_key UNIQUE (tenant_id, contract_number),
  CONSTRAINT contracts_tenant_party_fk FOREIGN KEY (tenant_id, party_id) REFERENCES parties(tenant_id, id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_contracts_tenant_status ON contracts(tenant_id, status, starts_at DESC);

ALTER TABLE parties ENABLE ROW LEVEL SECURITY;
ALTER TABLE parties FORCE ROW LEVEL SECURITY;
ALTER TABLE party_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE party_roles FORCE ROW LEVEL SECURITY;
ALTER TABLE services ENABLE ROW LEVEL SECURITY;
ALTER TABLE services FORCE ROW LEVEL SECURITY;
ALTER TABLE resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE resources FORCE ROW LEVEL SECURITY;
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets FORCE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
ALTER TABLE business_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_transactions FORCE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments FORCE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks FORCE ROW LEVEL SECURITY;
ALTER TABLE business_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_cases FORCE ROW LEVEL SECURITY;
ALTER TABLE business_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_projects FORCE ROW LEVEL SECURITY;
ALTER TABLE contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE contracts FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS parties_tenant_isolation ON parties;
CREATE POLICY parties_tenant_isolation ON parties
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS party_roles_tenant_isolation ON party_roles;
CREATE POLICY party_roles_tenant_isolation ON party_roles
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS services_tenant_isolation ON services;
CREATE POLICY services_tenant_isolation ON services
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS resources_tenant_isolation ON resources;
CREATE POLICY resources_tenant_isolation ON resources
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS assets_tenant_isolation ON assets;
CREATE POLICY assets_tenant_isolation ON assets
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS documents_tenant_isolation ON documents;
CREATE POLICY documents_tenant_isolation ON documents
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS business_transactions_tenant_isolation ON business_transactions;
CREATE POLICY business_transactions_tenant_isolation ON business_transactions
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS payments_tenant_isolation ON payments;
CREATE POLICY payments_tenant_isolation ON payments
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS tasks_tenant_isolation ON tasks;
CREATE POLICY tasks_tenant_isolation ON tasks
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS business_cases_tenant_isolation ON business_cases;
CREATE POLICY business_cases_tenant_isolation ON business_cases
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS business_projects_tenant_isolation ON business_projects;
CREATE POLICY business_projects_tenant_isolation ON business_projects
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS contracts_tenant_isolation ON contracts;
CREATE POLICY contracts_tenant_isolation ON contracts
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

INSERT INTO permissions (code, description) VALUES
 ('kernel.read', 'Read universal business kernel records'),
 ('kernel.manage', 'Create and manage universal business kernel records')
ON CONFLICT (code) DO NOTHING;

INSERT INTO schema_migrations (version)
VALUES ('012_phase1_business_kernel')
ON CONFLICT (version) DO NOTHING;
