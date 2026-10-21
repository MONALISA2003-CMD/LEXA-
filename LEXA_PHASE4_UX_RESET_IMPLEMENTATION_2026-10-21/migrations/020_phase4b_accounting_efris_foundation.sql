BEGIN;

CREATE TABLE IF NOT EXISTS accounting_accounts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 code varchar(40) NOT NULL, name varchar(160) NOT NULL,
 account_type varchar(20) NOT NULL CHECK (account_type IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')),
 normal_balance varchar(10) NOT NULL CHECK (normal_balance IN ('DEBIT','CREDIT')),
 parent_account_id uuid NULL, currency_code varchar(3) NULL, system_key varchar(80) NULL,
 allow_posting boolean NOT NULL DEFAULT true,
 status varchar(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED')),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id), UNIQUE (tenant_id,code)
);
ALTER TABLE accounting_accounts ADD CONSTRAINT fk_account_parent_tenant FOREIGN KEY (tenant_id,parent_account_id) REFERENCES accounting_accounts(tenant_id,id) DEFERRABLE;

CREATE TABLE IF NOT EXISTS accounting_periods (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 period_name varchar(80) NOT NULL, start_date date NOT NULL, end_date date NOT NULL,
 status varchar(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED','LOCKED')),
 closed_at timestamptz NULL, closed_by uuid NULL REFERENCES users(id) ON DELETE SET NULL,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id), UNIQUE (tenant_id,start_date,end_date), CHECK (start_date<=end_date)
);

CREATE TABLE IF NOT EXISTS journal_entries (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 period_id uuid NOT NULL, entry_date date NOT NULL, source_type varchar(60) NOT NULL, source_id uuid NULL,
 entry_role varchar(60) NOT NULL DEFAULT 'PRIMARY', reference varchar(120) NULL, description text NOT NULL,
 currency_code varchar(3) NOT NULL,
 status varchar(20) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','POSTED','REVERSED')),
 reversal_of_id uuid NULL, posted_at timestamptz NULL, posted_by uuid NULL REFERENCES users(id) ON DELETE SET NULL,
 correlation_id uuid NULL, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id)
);
ALTER TABLE journal_entries ADD CONSTRAINT fk_journal_period_tenant FOREIGN KEY (tenant_id,period_id) REFERENCES accounting_periods(tenant_id,id) DEFERRABLE;
ALTER TABLE journal_entries ADD CONSTRAINT fk_journal_reversal_tenant FOREIGN KEY (tenant_id,reversal_of_id) REFERENCES journal_entries(tenant_id,id) DEFERRABLE;
CREATE UNIQUE INDEX IF NOT EXISTS uq_journal_primary_source ON journal_entries(tenant_id,source_type,source_id,entry_role) WHERE source_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS journal_lines (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 journal_entry_id uuid NOT NULL, line_no integer NOT NULL, account_id uuid NOT NULL, description text NULL,
 debit numeric(20,4) NOT NULL DEFAULT 0 CHECK (debit>=0), credit numeric(20,4) NOT NULL DEFAULT 0 CHECK (credit>=0),
 currency_code varchar(3) NOT NULL, party_id uuid NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id), UNIQUE (tenant_id,journal_entry_id,line_no), CHECK ((debit>0 AND credit=0) OR (credit>0 AND debit=0))
);
ALTER TABLE journal_lines ADD CONSTRAINT fk_journal_line_entry_tenant FOREIGN KEY (tenant_id,journal_entry_id) REFERENCES journal_entries(tenant_id,id) ON DELETE RESTRICT DEFERRABLE;
ALTER TABLE journal_lines ADD CONSTRAINT fk_journal_line_account_tenant FOREIGN KEY (tenant_id,account_id) REFERENCES accounting_accounts(tenant_id,id) DEFERRABLE;
ALTER TABLE journal_lines ADD CONSTRAINT fk_journal_line_party_tenant FOREIGN KEY (tenant_id,party_id) REFERENCES parties(tenant_id,id) DEFERRABLE;

CREATE TABLE IF NOT EXISTS accounting_mappings (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 mapping_key varchar(100) NOT NULL, account_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id), UNIQUE (tenant_id,mapping_key)
);
ALTER TABLE accounting_mappings ADD CONSTRAINT fk_accounting_mapping_account_tenant FOREIGN KEY (tenant_id,account_id) REFERENCES accounting_accounts(tenant_id,id) DEFERRABLE;

CREATE TABLE IF NOT EXISTS tax_rates (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 code varchar(50) NOT NULL, name varchar(160) NOT NULL, rate_percent numeric(9,4) NOT NULL CHECK (rate_percent>=0 AND rate_percent<=100),
 inclusive boolean NOT NULL DEFAULT false, effective_from date NOT NULL, effective_to date NULL,
 status varchar(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED')),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE (tenant_id,id), UNIQUE (tenant_id,code),
 CHECK (effective_to IS NULL OR effective_to>=effective_from)
);

CREATE TABLE IF NOT EXISTS tax_configurations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 name varchar(160) NOT NULL, tax_rate_id uuid NOT NULL, scope_type varchar(30) NOT NULL CHECK (scope_type IN ('DEFAULT','PRODUCT','CATEGORY')),
 scope_id uuid NULL, effective_from date NOT NULL, effective_to date NULL,
 status varchar(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED')),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE (tenant_id,id),
 CHECK ((scope_type='DEFAULT' AND scope_id IS NULL) OR (scope_type<>'DEFAULT' AND scope_id IS NOT NULL)), CHECK (effective_to IS NULL OR effective_to>=effective_from)
);
ALTER TABLE tax_configurations ADD CONSTRAINT fk_tax_config_rate_tenant FOREIGN KEY (tenant_id,tax_rate_id) REFERENCES tax_rates(tenant_id,id) DEFERRABLE;

CREATE TABLE IF NOT EXISTS expense_records (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 expense_date date NOT NULL, reference varchar(120) NOT NULL, description text NOT NULL, expense_account_id uuid NOT NULL,
 payment_channel_id uuid NULL, currency_code varchar(3) NOT NULL, subtotal numeric(20,4) NOT NULL CHECK (subtotal>=0),
 tax_amount numeric(20,4) NOT NULL DEFAULT 0 CHECK (tax_amount>=0), total numeric(20,4) NOT NULL CHECK (total>=0),
 status varchar(20) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','POSTED','VOIDED')),
 supplier_party_id uuid NULL, journal_entry_id uuid NULL, created_by uuid NULL REFERENCES users(id) ON DELETE SET NULL,
 posted_by uuid NULL REFERENCES users(id) ON DELETE SET NULL, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id), UNIQUE (tenant_id,reference), CHECK (total=subtotal+tax_amount)
);
ALTER TABLE expense_records ADD CONSTRAINT fk_expense_account_tenant FOREIGN KEY (tenant_id,expense_account_id) REFERENCES accounting_accounts(tenant_id,id) DEFERRABLE;
ALTER TABLE expense_records ADD CONSTRAINT fk_expense_payment_channel_tenant FOREIGN KEY (tenant_id,payment_channel_id) REFERENCES payment_channels(tenant_id,id) DEFERRABLE;
ALTER TABLE expense_records ADD CONSTRAINT fk_expense_supplier_tenant FOREIGN KEY (tenant_id,supplier_party_id) REFERENCES parties(tenant_id,id) DEFERRABLE;
ALTER TABLE expense_records ADD CONSTRAINT fk_expense_journal_tenant FOREIGN KEY (tenant_id,journal_entry_id) REFERENCES journal_entries(tenant_id,id) DEFERRABLE;

CREATE TABLE IF NOT EXISTS efris_configurations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 enabled boolean NOT NULL DEFAULT false, integration_mode varchar(30) NOT NULL DEFAULT 'MANUAL' CHECK (integration_mode IN ('MANUAL','PENDING_INTEGRATION','SYSTEM_TO_SYSTEM')),
 registration_status varchar(30) NOT NULL DEFAULT 'NOT_REGISTERED' CHECK (registration_status IN ('NOT_REGISTERED','PENDING','ACTIVE','SUSPENDED')),
 tin varchar(40) NULL, legal_name varchar(200) NULL, effective_date date NULL,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE (tenant_id), UNIQUE (id,tenant_id)
);

CREATE TABLE IF NOT EXISTS fiscal_documents (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 source_type varchar(60) NOT NULL, source_id uuid NOT NULL, document_type varchar(30) NOT NULL CHECK (document_type IN ('INVOICE','RECEIPT','CREDIT_NOTE','DEBIT_NOTE')),
 currency_code varchar(3) NOT NULL, issue_date date NOT NULL,
 status varchar(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','PENDING','SUBMITTED','ACCEPTED','REJECTED','VOIDED')),
 document_number varchar(100) NULL, fdn varchar(40) NULL, verification_code varchar(160) NULL, qr_code text NULL, efris_reference varchar(160) NULL,
 response_code varchar(60) NULL, response_message text NULL, submitted_at timestamptz NULL, accepted_at timestamptz NULL, voided_at timestamptz NULL,
 last_error text NULL, metadata jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id), UNIQUE (tenant_id,source_type,source_id,document_type)
);

CREATE TABLE IF NOT EXISTS fiscalization_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 fiscal_document_id uuid NOT NULL, event_type varchar(40) NOT NULL CHECK (event_type IN ('CREATE','SUBMIT','RETRY','ACCEPT','REJECT','VOID')),
 status varchar(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','PROCESSING','SUCCEEDED','FAILED')),
 request_hash varchar(128) NULL, response_code varchar(60) NULL, response_message text NULL,
 attempts integer NOT NULL DEFAULT 0 CHECK (attempts>=0), next_attempt_at timestamptz NULL, processed_at timestamptz NULL, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (tenant_id,id)
);
ALTER TABLE fiscalization_events ADD CONSTRAINT fk_fiscal_event_document_tenant FOREIGN KEY (tenant_id,fiscal_document_id) REFERENCES fiscal_documents(tenant_id,id) ON DELETE RESTRICT DEFERRABLE;

CREATE TABLE IF NOT EXISTS inventory_valuation_snapshots (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, location_id uuid NULL,
 snapshot_at timestamptz NOT NULL DEFAULT now(), valuation_method varchar(40) NOT NULL DEFAULT 'WEIGHTED_AVERAGE',
 total_quantity numeric(20,4) NOT NULL DEFAULT 0, total_value numeric(20,4) NOT NULL DEFAULT 0, metadata jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (tenant_id,id)
);
ALTER TABLE inventory_valuation_snapshots ADD CONSTRAINT fk_valuation_location_tenant FOREIGN KEY (tenant_id,location_id) REFERENCES locations(tenant_id,id) DEFERRABLE;

ALTER TABLE payment_channels ADD COLUMN IF NOT EXISTS accounting_account_id uuid NULL;
ALTER TABLE payment_channels ADD CONSTRAINT fk_payment_channel_account_tenant FOREIGN KEY (tenant_id,accounting_account_id) REFERENCES accounting_accounts(tenant_id,id) DEFERRABLE;

CREATE INDEX IF NOT EXISTS idx_journal_entries_tenant_date ON journal_entries(tenant_id,entry_date,status);
CREATE INDEX IF NOT EXISTS idx_journal_lines_tenant_account ON journal_lines(tenant_id,account_id,journal_entry_id);
CREATE INDEX IF NOT EXISTS idx_tax_config_active_scope ON tax_configurations(tenant_id,scope_type,scope_id,effective_from);
CREATE INDEX IF NOT EXISTS idx_fiscal_documents_status ON fiscal_documents(tenant_id,status,issue_date);
CREATE INDEX IF NOT EXISTS idx_fiscalization_events_pending ON fiscalization_events(tenant_id,status,next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_expense_records_date ON expense_records(tenant_id,expense_date,status);
CREATE INDEX IF NOT EXISTS idx_inventory_valuation_snapshot ON inventory_valuation_snapshots(tenant_id,snapshot_at);

CREATE OR REPLACE FUNCTION ensure_accounting_period(p_tenant_id uuid,p_date date) RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_id uuid; v_start date; v_end date;
BEGIN v_start:=date_trunc('month',p_date)::date; v_end:=(date_trunc('month',p_date)+interval '1 month'-interval '1 day')::date;
SELECT id INTO v_id FROM accounting_periods WHERE tenant_id=p_tenant_id AND p_date BETWEEN start_date AND end_date ORDER BY start_date DESC LIMIT 1;
IF v_id IS NULL THEN INSERT INTO accounting_periods(tenant_id,period_name,start_date,end_date) VALUES(p_tenant_id,to_char(v_start,'YYYY-MM'),v_start,v_end) RETURNING id INTO v_id; END IF; RETURN v_id; END $fn$;

CREATE OR REPLACE FUNCTION ensure_system_account(p_tenant_id uuid,p_code varchar,p_name varchar,p_type varchar,p_normal varchar,p_system_key varchar,p_currency varchar DEFAULT NULL) RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_id uuid; BEGIN SELECT id INTO v_id FROM accounting_accounts WHERE tenant_id=p_tenant_id AND code=p_code; IF v_id IS NULL THEN INSERT INTO accounting_accounts(tenant_id,code,name,account_type,normal_balance,system_key,currency_code) VALUES(p_tenant_id,p_code,p_name,p_type,p_normal,p_system_key,p_currency) RETURNING id INTO v_id; END IF; RETURN v_id; END $fn$;

CREATE OR REPLACE FUNCTION accounting_mapping_account(p_tenant_id uuid,p_mapping_key varchar) RETURNS uuid LANGUAGE sql STABLE AS $fn$ SELECT account_id FROM accounting_mappings WHERE tenant_id=p_tenant_id AND mapping_key=p_mapping_key LIMIT 1 $fn$;

CREATE OR REPLACE FUNCTION seed_accounting_foundation(p_tenant_id uuid) RETURNS void LANGUAGE plpgsql AS $fn$
BEGIN
PERFORM ensure_system_account(p_tenant_id,'1000','Cash on Hand','ASSET','DEBIT','CASH');
PERFORM ensure_system_account(p_tenant_id,'1010','Mobile Money','ASSET','DEBIT','MOBILE_MONEY');
PERFORM ensure_system_account(p_tenant_id,'1020','Bank Accounts','ASSET','DEBIT','BANK');
PERFORM ensure_system_account(p_tenant_id,'1030','Card Receipts','ASSET','DEBIT','CARD');
PERFORM ensure_system_account(p_tenant_id,'1040','Cheque Receipts','ASSET','DEBIT','CHEQUE');
PERFORM ensure_system_account(p_tenant_id,'1100','Accounts Receivable','ASSET','DEBIT','ACCOUNTS_RECEIVABLE');
PERFORM ensure_system_account(p_tenant_id,'1200','Inventory','ASSET','DEBIT','INVENTORY');
PERFORM ensure_system_account(p_tenant_id,'1300','Input Tax Recoverable','ASSET','DEBIT','INPUT_TAX');
PERFORM ensure_system_account(p_tenant_id,'2000','Accounts Payable','LIABILITY','CREDIT','ACCOUNTS_PAYABLE');
PERFORM ensure_system_account(p_tenant_id,'2100','Output Tax Payable','LIABILITY','CREDIT','OUTPUT_TAX');
PERFORM ensure_system_account(p_tenant_id,'2200','Customer Deposits / Unallocated Receipts','LIABILITY','CREDIT','UNALLOCATED_RECEIPTS');
PERFORM ensure_system_account(p_tenant_id,'3000','Owner Equity','EQUITY','CREDIT','OWNER_EQUITY');
PERFORM ensure_system_account(p_tenant_id,'4000','Sales Revenue','REVENUE','CREDIT','SALES_REVENUE');
PERFORM ensure_system_account(p_tenant_id,'4100','Sales Returns','REVENUE','DEBIT','SALES_RETURNS');
PERFORM ensure_system_account(p_tenant_id,'5000','Cost of Goods Sold','EXPENSE','DEBIT','COGS');
PERFORM ensure_system_account(p_tenant_id,'6000','Operating Expenses','EXPENSE','DEBIT','OPERATING_EXPENSES');
INSERT INTO accounting_mappings(tenant_id,mapping_key,account_id) SELECT p_tenant_id,x.key,a.id FROM (VALUES ('PAYMENT_CHANNEL.CASH','1000'),('PAYMENT_CHANNEL.MOBILE_MONEY','1010'),('PAYMENT_CHANNEL.BANK','1020'),('PAYMENT_CHANNEL.CARD','1030'),('PAYMENT_CHANNEL.CHEQUE','1040'),('PAYMENT_CHANNEL.OTHER','1000')) x(key,code) JOIN accounting_accounts a ON a.tenant_id=p_tenant_id AND a.code=x.code ON CONFLICT (tenant_id,mapping_key) DO NOTHING;
INSERT INTO accounting_mappings(tenant_id,mapping_key,account_id) SELECT p_tenant_id,x.key,a.id FROM (VALUES ('ACCOUNTS_RECEIVABLE','1100'),('INVENTORY','1200'),('INPUT_TAX','1300'),('ACCOUNTS_PAYABLE','2000'),('OUTPUT_TAX','2100'),('UNALLOCATED_RECEIPTS','2200'),('OWNER_EQUITY','3000'),('SALES_REVENUE','4000'),('SALES_RETURNS','4100'),('COGS','5000'),('OPERATING_EXPENSES','6000')) x(key,code) JOIN accounting_accounts a ON a.tenant_id=p_tenant_id AND a.code=x.code ON CONFLICT (tenant_id,mapping_key) DO NOTHING;
PERFORM ensure_accounting_period(p_tenant_id,current_date); INSERT INTO efris_configurations(tenant_id) VALUES(p_tenant_id) ON CONFLICT(tenant_id) DO NOTHING;
END $fn$;

CREATE OR REPLACE FUNCTION post_journal_entry(p_entry_id uuid,p_user_id uuid) RETURNS void LANGUAGE plpgsql AS $fn$
DECLARE v_tenant uuid; v_status text; v_period uuid; v_debit numeric; v_credit numeric; v_lines int;
BEGIN SELECT tenant_id,status,period_id INTO v_tenant,v_status,v_period FROM journal_entries WHERE id=p_entry_id FOR UPDATE;
IF NOT FOUND THEN RAISE EXCEPTION 'Journal entry not found'; END IF; IF v_status<>'DRAFT' THEN RAISE EXCEPTION 'Only draft journal entries can be posted'; END IF;
IF EXISTS(SELECT 1 FROM accounting_periods WHERE id=v_period AND status<>'OPEN') THEN RAISE EXCEPTION 'Accounting period is not open'; END IF;
SELECT count(*),COALESCE(SUM(debit),0),COALESCE(SUM(credit),0) INTO v_lines,v_debit,v_credit FROM journal_lines WHERE tenant_id=v_tenant AND journal_entry_id=p_entry_id;
IF v_lines<2 THEN RAISE EXCEPTION 'A journal entry requires at least two lines'; END IF; IF round(v_debit,4)<>round(v_credit,4) THEN RAISE EXCEPTION 'Journal entry is not balanced: debit %, credit %',v_debit,v_credit; END IF;
IF EXISTS(SELECT 1 FROM journal_lines jl JOIN accounting_accounts a ON a.id=jl.account_id AND a.tenant_id=jl.tenant_id WHERE jl.tenant_id=v_tenant AND jl.journal_entry_id=p_entry_id AND (a.status<>'ACTIVE' OR NOT a.allow_posting)) THEN RAISE EXCEPTION 'Journal contains an inactive or non-posting account'; END IF;
UPDATE journal_entries SET status='POSTED',posted_at=now(),posted_by=p_user_id,updated_at=now() WHERE id=p_entry_id;
END $fn$;

CREATE OR REPLACE FUNCTION reverse_journal_entry(p_entry_id uuid,p_user_id uuid,p_date date DEFAULT current_date) RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_new uuid; v_tenant uuid; v_period uuid; v_currency varchar; v_status text;
BEGIN SELECT tenant_id,period_id,currency_code,status INTO v_tenant,v_period,v_currency,v_status FROM journal_entries WHERE id=p_entry_id FOR UPDATE;
IF NOT FOUND THEN RAISE EXCEPTION 'Journal entry not found'; END IF; IF v_status<>'POSTED' THEN RAISE EXCEPTION 'Only posted journal entries can be reversed'; END IF; IF EXISTS(SELECT 1 FROM journal_entries WHERE tenant_id=v_tenant AND reversal_of_id=p_entry_id) THEN RAISE EXCEPTION 'Journal entry has already been reversed'; END IF;
INSERT INTO journal_entries(tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,description,currency_code,reversal_of_id) SELECT v_tenant,ensure_accounting_period(v_tenant,p_date),p_date,'REVERSAL',p_entry_id,'REVERSAL',reference,'Reversal of '||COALESCE(reference,p_entry_id::text),v_currency,p_entry_id FROM journal_entries WHERE id=p_entry_id RETURNING id INTO v_new;
INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id) SELECT tenant_id,v_new,row_number() OVER (ORDER BY line_no),account_id,'Reversal: '||COALESCE(description,''),credit,debit,currency_code,party_id FROM journal_lines WHERE tenant_id=v_tenant AND journal_entry_id=p_entry_id;
UPDATE journal_entries SET status='REVERSED',updated_at=now() WHERE id=p_entry_id; PERFORM post_journal_entry(v_new,p_user_id); RETURN v_new;
END $fn$;

CREATE OR REPLACE FUNCTION protect_posted_journal_entry() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
IF TG_OP='DELETE' THEN IF OLD.status IN ('POSTED','REVERSED') THEN RAISE EXCEPTION 'Posted or reversed journal entries are immutable'; END IF; RETURN OLD; END IF;
IF OLD.status='POSTED' AND (NEW.tenant_id<>OLD.tenant_id OR NEW.period_id<>OLD.period_id OR NEW.entry_date<>OLD.entry_date OR NEW.source_type<>OLD.source_type OR NEW.source_id IS DISTINCT FROM OLD.source_id OR NEW.entry_role<>OLD.entry_role OR NEW.reference IS DISTINCT FROM OLD.reference OR NEW.description<>OLD.description OR NEW.currency_code<>OLD.currency_code) THEN RAISE EXCEPTION 'Posted journal entry facts are immutable'; END IF;
IF OLD.status='POSTED' AND NEW.status NOT IN ('POSTED','REVERSED') THEN RAISE EXCEPTION 'Posted journal entry cannot return to draft'; END IF; IF OLD.status='REVERSED' AND NEW.status<>'REVERSED' THEN RAISE EXCEPTION 'Reversed journal entry cannot be reactivated'; END IF; RETURN NEW; END $fn$;

CREATE OR REPLACE FUNCTION protect_posted_journal_line() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE v_status text; v_tenant uuid; v_entry uuid; BEGIN v_tenant:=COALESCE(NEW.tenant_id,OLD.tenant_id); v_entry:=COALESCE(NEW.journal_entry_id,OLD.journal_entry_id); SELECT status INTO v_status FROM journal_entries WHERE tenant_id=v_tenant AND id=v_entry; IF v_status IN ('POSTED','REVERSED') THEN RAISE EXCEPTION 'Lines on posted or reversed journal entries are immutable'; END IF; IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $fn$;

CREATE OR REPLACE FUNCTION resolve_payment_account(p_payment_id uuid) RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_tenant uuid; v_channel uuid; v_type text; v_account uuid; BEGIN SELECT tenant_id,payment_channel_id INTO v_tenant,v_channel FROM payments WHERE id=p_payment_id; IF v_channel IS NULL THEN RETURN accounting_mapping_account(v_tenant,'UNALLOCATED_RECEIPTS'); END IF; SELECT accounting_account_id,channel_type INTO v_account,v_type FROM payment_channels WHERE tenant_id=v_tenant AND id=v_channel; IF v_account IS NOT NULL THEN RETURN v_account; END IF; RETURN accounting_mapping_account(v_tenant,'PAYMENT_CHANNEL.'||v_type); END $fn$;

CREATE OR REPLACE FUNCTION post_sale_journal(p_sale_id uuid,p_user_id uuid) RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_tenant uuid; v_period uuid; v_currency varchar; v_total numeric; v_tax numeric; v_net numeric; v_party uuid; v_existing uuid; v_entry uuid;
BEGIN SELECT tenant_id,currency_code,total,tax_total,customer_party_id INTO v_tenant,v_currency,v_total,v_tax,v_party FROM sales WHERE id=p_sale_id FOR UPDATE; IF NOT FOUND THEN RAISE EXCEPTION 'Sale not found'; END IF;
SELECT id INTO v_existing FROM journal_entries WHERE tenant_id=v_tenant AND source_type='SALE' AND source_id=p_sale_id AND entry_role='SALE_RECOGNITION'; IF v_existing IS NOT NULL THEN RETURN v_existing; END IF;
v_period:=ensure_accounting_period(v_tenant,current_date); v_net:=GREATEST(v_total-v_tax,0);
INSERT INTO journal_entries(tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,description,currency_code) VALUES(v_tenant,v_period,current_date,'SALE',p_sale_id,'SALE_RECOGNITION','SALE:'||p_sale_id::text,'Sale revenue recognition',v_currency) RETURNING id INTO v_entry;
INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id) VALUES(v_tenant,v_entry,1,accounting_mapping_account(v_tenant,'ACCOUNTS_RECEIVABLE'),'Customer receivable',v_total,0,v_currency,v_party);
IF v_net>0 THEN INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code) VALUES(v_tenant,v_entry,2,accounting_mapping_account(v_tenant,'SALES_REVENUE'),'Net sales revenue',0,v_net,v_currency); END IF;
IF v_tax>0 THEN INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code) VALUES(v_tenant,v_entry,3,accounting_mapping_account(v_tenant,'OUTPUT_TAX'),'Output tax',0,v_tax,v_currency); END IF;
PERFORM post_journal_entry(v_entry,p_user_id); RETURN v_entry; END $fn$;

CREATE OR REPLACE FUNCTION post_payment_journal(p_payment_id uuid,p_user_id uuid) RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_tenant uuid; v_currency varchar; v_amount numeric; v_party uuid; v_account uuid; v_existing uuid; v_entry uuid; v_period uuid; v_allocated numeric;
BEGIN SELECT tenant_id,currency_code,amount,party_id INTO v_tenant,v_currency,v_amount,v_party FROM payments WHERE id=p_payment_id AND status='RECORDED' FOR UPDATE; IF NOT FOUND THEN RAISE EXCEPTION 'Recorded payment not found'; END IF;
SELECT id INTO v_existing FROM journal_entries WHERE tenant_id=v_tenant AND source_type='PAYMENT' AND source_id=p_payment_id AND entry_role='PAYMENT_RECEIPT'; IF v_existing IS NOT NULL THEN RETURN v_existing; END IF;
v_account:=resolve_payment_account(p_payment_id); v_allocated:=COALESCE((SELECT SUM(amount) FROM payment_allocations WHERE tenant_id=v_tenant AND payment_id=p_payment_id AND status='RECORDED'),0); IF v_allocated>v_amount THEN RAISE EXCEPTION 'Payment allocations exceed payment amount'; END IF;
v_period:=ensure_accounting_period(v_tenant,current_date); INSERT INTO journal_entries(tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,description,currency_code) VALUES(v_tenant,v_period,current_date,'PAYMENT',p_payment_id,'PAYMENT_RECEIPT','PAYMENT:'||p_payment_id::text,'Payment received',v_currency) RETURNING id INTO v_entry;
INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id) VALUES(v_tenant,v_entry,1,v_account,'Cash or settlement channel',v_amount,0,v_currency,v_party);
IF v_allocated>0 THEN INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id) VALUES(v_tenant,v_entry,2,accounting_mapping_account(v_tenant,'ACCOUNTS_RECEIVABLE'),'Settlement of customer receivable',0,v_allocated,v_currency,v_party); END IF;
IF v_amount-v_allocated>0 THEN INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id) VALUES(v_tenant,v_entry,3,accounting_mapping_account(v_tenant,'UNALLOCATED_RECEIPTS'),'Unallocated customer receipt',0,v_amount-v_allocated,v_currency,v_party); END IF;
PERFORM post_journal_entry(v_entry,p_user_id); RETURN v_entry; END $fn$;

CREATE OR REPLACE FUNCTION post_sale_cogs_journal(p_sale_id uuid,p_user_id uuid) RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_tenant uuid; v_period uuid; v_currency varchar; v_cogs numeric; v_existing uuid; v_entry uuid;
BEGIN SELECT tenant_id,currency_code INTO v_tenant,v_currency FROM sales WHERE id=p_sale_id; IF NOT FOUND THEN RAISE EXCEPTION 'Sale not found'; END IF; SELECT id INTO v_existing FROM journal_entries WHERE tenant_id=v_tenant AND source_type='SALE' AND source_id=p_sale_id AND entry_role='COGS'; IF v_existing IS NOT NULL THEN RETURN v_existing; END IF; SELECT COALESCE(SUM(CASE WHEN quantity_delta<0 THEN ABS(total_cost) ELSE 0 END),0) INTO v_cogs FROM inventory_transactions WHERE tenant_id=v_tenant AND reference_type='SALE' AND reference_id=p_sale_id; IF v_cogs<=0 THEN RETURN NULL; END IF; v_period:=ensure_accounting_period(v_tenant,current_date); INSERT INTO journal_entries(tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,description,currency_code) VALUES(v_tenant,v_period,current_date,'SALE',p_sale_id,'COGS','SALE:'||p_sale_id::text,'Cost of goods sold',v_currency) RETURNING id INTO v_entry; INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code) VALUES(v_tenant,v_entry,1,accounting_mapping_account(v_tenant,'COGS'),'Cost of goods sold',v_cogs,0,v_currency),(v_tenant,v_entry,2,accounting_mapping_account(v_tenant,'INVENTORY'),'Inventory reduction',0,v_cogs,v_currency); PERFORM post_journal_entry(v_entry,p_user_id); RETURN v_entry; END $fn$;

CREATE OR REPLACE FUNCTION resolve_tax_rate(p_tenant_id uuid,p_product_id uuid,p_category_id uuid,p_date date) RETURNS TABLE(tax_rate_id uuid,code varchar,rate_percent numeric,inclusive boolean) LANGUAGE sql STABLE AS $fn$ SELECT tr.id,tr.code,tr.rate_percent,tr.inclusive FROM tax_configurations tc JOIN tax_rates tr ON tr.tenant_id=tc.tenant_id AND tr.id=tc.tax_rate_id WHERE tc.tenant_id=p_tenant_id AND tc.status='ACTIVE' AND tr.status='ACTIVE' AND p_date BETWEEN tc.effective_from AND COALESCE(tc.effective_to,'9999-12-31') AND p_date BETWEEN tr.effective_from AND COALESCE(tr.effective_to,'9999-12-31') AND ((tc.scope_type='PRODUCT' AND tc.scope_id=p_product_id) OR (tc.scope_type='CATEGORY' AND tc.scope_id=p_category_id) OR (tc.scope_type='DEFAULT')) ORDER BY CASE tc.scope_type WHEN 'PRODUCT' THEN 1 WHEN 'CATEGORY' THEN 2 ELSE 3 END,tc.effective_from DESC LIMIT 1 $fn$;

CREATE OR REPLACE FUNCTION create_fiscal_document_for_sale(p_sale_id uuid,p_document_type varchar DEFAULT 'INVOICE') RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_tenant uuid; v_currency varchar; v_enabled boolean; v_status text; v_id uuid; BEGIN SELECT tenant_id,currency_code INTO v_tenant,v_currency FROM sales WHERE id=p_sale_id; IF NOT FOUND THEN RAISE EXCEPTION 'Sale not found'; END IF; SELECT enabled,registration_status INTO v_enabled,v_status FROM efris_configurations WHERE tenant_id=v_tenant; IF NOT COALESCE(v_enabled,false) OR v_status<>'ACTIVE' THEN RAISE EXCEPTION 'EFRIS is not active for this business'; END IF; SELECT id INTO v_id FROM fiscal_documents WHERE tenant_id=v_tenant AND source_type='SALE' AND source_id=p_sale_id AND document_type=p_document_type; IF v_id IS NOT NULL THEN RETURN v_id; END IF; INSERT INTO fiscal_documents(tenant_id,source_type,source_id,document_type,currency_code,issue_date,status) VALUES(v_tenant,'SALE',p_sale_id,p_document_type,v_currency,current_date,'PENDING') RETURNING id INTO v_id; INSERT INTO fiscalization_events(tenant_id,fiscal_document_id,event_type,status) VALUES(v_tenant,v_id,'SUBMIT','PENDING'); RETURN v_id; END $fn$;

CREATE OR REPLACE FUNCTION close_accounting_period(p_period_id uuid,p_user_id uuid) RETURNS void LANGUAGE plpgsql AS $fn$
DECLARE v_tenant uuid; v_status text; BEGIN SELECT tenant_id,status INTO v_tenant,v_status FROM accounting_periods WHERE id=p_period_id FOR UPDATE; IF NOT FOUND THEN RAISE EXCEPTION 'Accounting period not found'; END IF; IF v_status<>'OPEN' THEN RAISE EXCEPTION 'Accounting period is not open'; END IF; IF EXISTS(SELECT 1 FROM journal_entries WHERE tenant_id=v_tenant AND period_id=p_period_id AND status='DRAFT') THEN RAISE EXCEPTION 'Cannot close a period with draft journal entries'; END IF; UPDATE accounting_periods SET status='CLOSED',closed_at=now(),closed_by=p_user_id,updated_at=now() WHERE id=p_period_id; END $fn$;

CREATE OR REPLACE FUNCTION trial_balance(p_tenant_id uuid,p_from date,p_to date) RETURNS TABLE(account_id uuid,code varchar,name varchar,account_type varchar,debits numeric,credits numeric,net_balance numeric) LANGUAGE sql STABLE AS $fn$
WITH posted AS (SELECT jl.account_id,SUM(jl.debit) debits,SUM(jl.credit) credits FROM journal_lines jl JOIN journal_entries je ON je.tenant_id=jl.tenant_id AND je.id=jl.journal_entry_id WHERE jl.tenant_id=p_tenant_id AND je.status='POSTED' AND je.entry_date BETWEEN p_from AND p_to GROUP BY jl.account_id)
SELECT a.id,a.code,a.name,a.account_type,COALESCE(p.debits,0),COALESCE(p.credits,0),CASE WHEN a.normal_balance='DEBIT' THEN COALESCE(p.debits,0)-COALESCE(p.credits,0) ELSE COALESCE(p.credits,0)-COALESCE(p.debits,0) END FROM accounting_accounts a LEFT JOIN posted p ON p.account_id=a.id WHERE a.tenant_id=p_tenant_id ORDER BY a.code $fn$;

CREATE OR REPLACE FUNCTION income_statement(p_tenant_id uuid,p_from date,p_to date) RETURNS TABLE(account_id uuid,code varchar,name varchar,account_type varchar,amount numeric) LANGUAGE sql STABLE AS $fn$ SELECT a.id,a.code,a.name,a.account_type,CASE WHEN a.account_type='REVENUE' THEN SUM(jl.credit-jl.debit) ELSE SUM(jl.debit-jl.credit) END FROM accounting_accounts a JOIN journal_lines jl ON jl.tenant_id=a.tenant_id AND jl.account_id=a.id JOIN journal_entries je ON je.tenant_id=jl.tenant_id AND je.id=jl.journal_entry_id WHERE a.tenant_id=p_tenant_id AND je.status='POSTED' AND je.entry_date BETWEEN p_from AND p_to AND a.account_type IN ('REVENUE','EXPENSE') GROUP BY a.id,a.code,a.name,a.account_type ORDER BY a.code $fn$;
CREATE OR REPLACE FUNCTION balance_sheet(p_tenant_id uuid,p_to date) RETURNS TABLE(account_id uuid,code varchar,name varchar,account_type varchar,amount numeric) LANGUAGE sql STABLE AS $fn$ SELECT a.id,a.code,a.name,a.account_type,CASE WHEN a.account_type='ASSET' THEN SUM(jl.debit-jl.credit) ELSE SUM(jl.credit-jl.debit) END FROM accounting_accounts a JOIN journal_lines jl ON jl.tenant_id=a.tenant_id AND jl.account_id=a.id JOIN journal_entries je ON je.tenant_id=jl.tenant_id AND je.id=jl.journal_entry_id WHERE a.tenant_id=p_tenant_id AND je.status='POSTED' AND je.entry_date<=p_to AND a.account_type IN ('ASSET','LIABILITY','EQUITY') GROUP BY a.id,a.code,a.name,a.account_type ORDER BY a.code $fn$;

CREATE OR REPLACE FUNCTION protect_fiscal_document() RETURNS trigger LANGUAGE plpgsql AS $fn$ BEGIN IF TG_OP='DELETE' THEN IF OLD.status IN ('ACCEPTED','VOIDED') THEN RAISE EXCEPTION 'Accepted or voided fiscal documents are immutable'; END IF; RETURN OLD; END IF; IF OLD.status='ACCEPTED' AND (NEW.tenant_id<>OLD.tenant_id OR NEW.source_type<>OLD.source_type OR NEW.source_id<>OLD.source_id OR NEW.document_type<>OLD.document_type OR NEW.currency_code<>OLD.currency_code OR NEW.document_number IS DISTINCT FROM OLD.document_number OR NEW.fdn IS DISTINCT FROM OLD.fdn OR NEW.verification_code IS DISTINCT FROM OLD.verification_code OR NEW.qr_code IS DISTINCT FROM OLD.qr_code) THEN RAISE EXCEPTION 'Accepted fiscal document facts are immutable'; END IF; IF OLD.status='VOIDED' AND NEW.status<>'VOIDED' THEN RAISE EXCEPTION 'Voided fiscal document cannot be reactivated'; END IF; RETURN NEW; END $fn$;

ALTER TABLE accounting_accounts ENABLE ROW LEVEL SECURITY; ALTER TABLE accounting_accounts FORCE ROW LEVEL SECURITY; DROP POLICY IF EXISTS accounting_accounts_tenant_isolation ON accounting_accounts; CREATE POLICY accounting_accounts_tenant_isolation ON accounting_accounts USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));
ALTER TABLE accounting_periods ENABLE ROW LEVEL SECURITY; ALTER TABLE accounting_periods FORCE ROW LEVEL SECURITY; DROP POLICY IF EXISTS accounting_periods_tenant_isolation ON accounting_periods; CREATE POLICY accounting_periods_tenant_isolation ON accounting_periods USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));
ALTER TABLE journal_entries ENABLE ROW LEVEL SECURITY; ALTER TABLE journal_entries FORCE ROW LEVEL SECURITY; DROP POLICY IF EXISTS journal_entries_tenant_isolation ON journal_entries; CREATE POLICY journal_entries_tenant_isolation ON journal_entries USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));
ALTER TABLE journal_lines ENABLE ROW LEVEL SECURITY; ALTER TABLE journal_lines FORCE ROW LEVEL SECURITY; DROP POLICY IF EXISTS journal_lines_tenant_isolation ON journal_lines; CREATE POLICY journal_lines_tenant_isolation ON journal_lines USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));
ALTER TABLE accounting_mappings ENABLE ROW LEVEL SECURITY; ALTER TABLE accounting_mappings FORCE ROW LEVEL SECURITY; DROP POLICY IF EXISTS accounting_mappings_tenant_isolation ON accounting_mappings; CREATE POLICY accounting_mappings_tenant_isolation ON accounting_mappings USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));
ALTER TABLE tax_rates ENABLE ROW LEVEL SECURITY; ALTER TABLE tax_rates FORCE ROW LEVEL SECURITY; DROP POLICY IF EXISTS tax_rates_tenant_isolation ON tax_rates; CREATE POLICY tax_rates_tenant_isolation ON tax_rates USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));
ALTER TABLE tax_configurations ENABLE ROW LEVEL SECURITY; ALTER TABLE tax_configurations FORCE ROW LEVEL SECURITY; DROP POLICY IF EXISTS tax_configurations_tenant_isolation ON tax_configurations; CREATE POLICY tax_configurations_tenant_isolation ON tax_configurations USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));
ALTER TABLE expense_records ENABLE ROW LEVEL SECURITY; ALTER TABLE expense_records FORCE ROW LEVEL SECURITY; DROP POLICY IF EXISTS expense_records_tenant_isolation ON expense_records; CREATE POLICY expense_records_tenant_isolation ON expense_records USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));
ALTER TABLE efris_configurations ENABLE ROW LEVEL SECURITY; ALTER TABLE efris_configurations FORCE ROW LEVEL SECURITY; DROP POLICY IF EXISTS efris_configurations_tenant_isolation ON efris_configurations; CREATE POLICY efris_configurations_tenant_isolation ON efris_configurations USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));
ALTER TABLE fiscal_documents ENABLE ROW LEVEL SECURITY; ALTER TABLE fiscal_documents FORCE ROW LEVEL SECURITY; DROP POLICY IF EXISTS fiscal_documents_tenant_isolation ON fiscal_documents; CREATE POLICY fiscal_documents_tenant_isolation ON fiscal_documents USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));
ALTER TABLE fiscalization_events ENABLE ROW LEVEL SECURITY; ALTER TABLE fiscalization_events FORCE ROW LEVEL SECURITY; DROP POLICY IF EXISTS fiscalization_events_tenant_isolation ON fiscalization_events; CREATE POLICY fiscalization_events_tenant_isolation ON fiscalization_events USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));
ALTER TABLE inventory_valuation_snapshots ENABLE ROW LEVEL SECURITY; ALTER TABLE inventory_valuation_snapshots FORCE ROW LEVEL SECURITY; DROP POLICY IF EXISTS inventory_valuation_snapshots_tenant_isolation ON inventory_valuation_snapshots; CREATE POLICY inventory_valuation_snapshots_tenant_isolation ON inventory_valuation_snapshots USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));


CREATE OR REPLACE FUNCTION post_expense_journal(p_expense_id uuid,p_user_id uuid) RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_tenant uuid; v_currency varchar; v_subtotal numeric; v_tax numeric; v_total numeric; v_expense_account uuid; v_channel_account uuid; v_entry uuid; v_existing uuid; v_period uuid; v_party uuid;
BEGIN
SELECT tenant_id,currency_code,subtotal,tax_amount,total,expense_account_id,supplier_party_id INTO v_tenant,v_currency,v_subtotal,v_tax,v_total,v_expense_account,v_party FROM expense_records WHERE id=p_expense_id AND status='DRAFT' FOR UPDATE;
IF NOT FOUND THEN RAISE EXCEPTION 'Draft expense not found'; END IF;
SELECT id INTO v_existing FROM journal_entries WHERE tenant_id=v_tenant AND source_type='EXPENSE' AND source_id=p_expense_id AND entry_role='EXPENSE'; IF v_existing IS NOT NULL THEN RETURN v_existing; END IF;
v_period:=ensure_accounting_period(v_tenant,current_date);
INSERT INTO journal_entries(tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,description,currency_code) SELECT v_tenant,v_period,expense_date,'EXPENSE',p_expense_id,'EXPENSE',reference,description,v_currency FROM expense_records WHERE id=p_expense_id RETURNING id INTO v_entry;
INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id) VALUES(v_tenant,v_entry,1,v_expense_account,'Expense',v_subtotal,0,v_currency,v_party);
IF v_tax>0 THEN INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id) VALUES(v_tenant,v_entry,2,accounting_mapping_account(v_tenant,'INPUT_TAX'),'Input tax',v_tax,0,v_currency,v_party); END IF;
IF EXISTS(SELECT 1 FROM expense_records WHERE id=p_expense_id AND payment_channel_id IS NOT NULL) THEN SELECT accounting_account_id INTO v_channel_account FROM payment_channels pc JOIN expense_records er ON er.tenant_id=pc.tenant_id AND er.payment_channel_id=pc.id WHERE er.id=p_expense_id; IF v_channel_account IS NULL THEN SELECT accounting_mapping_account(v_tenant,'PAYMENT_CHANNEL.'||pc.channel_type) INTO v_channel_account FROM payment_channels pc JOIN expense_records er ON er.tenant_id=pc.tenant_id AND er.payment_channel_id=pc.id WHERE er.id=p_expense_id; END IF; END IF;
INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id) VALUES(v_tenant,v_entry,4,COALESCE(v_channel_account,accounting_mapping_account(v_tenant,'ACCOUNTS_PAYABLE')),'Expense payment/payable',0,v_total,v_currency,v_party);
PERFORM post_journal_entry(v_entry,p_user_id); UPDATE expense_records SET status='POSTED',journal_entry_id=v_entry,posted_by=p_user_id,updated_at=now() WHERE id=p_expense_id; RETURN v_entry;
END $fn$;

DROP TRIGGER IF EXISTS trg_protect_posted_journal_entry ON journal_entries; CREATE TRIGGER trg_protect_posted_journal_entry BEFORE UPDATE OR DELETE ON journal_entries FOR EACH ROW EXECUTE FUNCTION protect_posted_journal_entry();
DROP TRIGGER IF EXISTS trg_protect_posted_journal_line ON journal_lines; CREATE TRIGGER trg_protect_posted_journal_line BEFORE UPDATE OR DELETE ON journal_lines FOR EACH ROW EXECUTE FUNCTION protect_posted_journal_line();
DROP TRIGGER IF EXISTS trg_protect_fiscal_document ON fiscal_documents; CREATE TRIGGER trg_protect_fiscal_document BEFORE UPDATE OR DELETE ON fiscal_documents FOR EACH ROW EXECUTE FUNCTION protect_fiscal_document();

INSERT INTO permissions(code,description) VALUES
('accounting.read','View accounting data and reports'),('accounting.manage','Manage chart of accounts and accounting setup'),('accounting.post','Post accounting entries'),('accounting.reverse','Reverse posted accounting entries'),('periods.manage','Open and close accounting periods'),('tax.read','View tax configuration'),('tax.manage','Manage tax rates and configurations'),('expenses.read','View expenses'),('expenses.manage','Create and manage expenses'),('efris.read','View EFRIS/fiscal documents'),('efris.manage','Manage EFRIS configuration and fiscal documents'),('efris.submit','Submit or retry fiscalization events') ON CONFLICT(code) DO NOTHING;
SELECT seed_accounting_foundation(id) FROM tenants;
INSERT INTO accounting_mappings(tenant_id,mapping_key,account_id) SELECT t.id,x.key,a.id FROM tenants t CROSS JOIN (VALUES ('ACCOUNTS_RECEIVABLE','1100'),('INVENTORY','1200'),('INPUT_TAX','1300'),('ACCOUNTS_PAYABLE','2000'),('OUTPUT_TAX','2100'),('UNALLOCATED_RECEIPTS','2200'),('OWNER_EQUITY','3000'),('SALES_REVENUE','4000'),('SALES_RETURNS','4100'),('COGS','5000'),('OPERATING_EXPENSES','6000'),('PAYMENT_CHANNEL.CASH','1000'),('PAYMENT_CHANNEL.MOBILE_MONEY','1010'),('PAYMENT_CHANNEL.BANK','1020'),('PAYMENT_CHANNEL.CARD','1030'),('PAYMENT_CHANNEL.CHEQUE','1040'),('PAYMENT_CHANNEL.OTHER','1000')) x(key,code) JOIN accounting_accounts a ON a.tenant_id=t.id AND a.code=x.code ON CONFLICT(tenant_id,mapping_key) DO NOTHING;
INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r JOIN permissions p ON p.code IN ('accounting.read','accounting.manage','accounting.post','accounting.reverse','periods.manage','tax.read','tax.manage','expenses.read','expenses.manage','efris.read','efris.manage','efris.submit') WHERE r.name IN ('Owner','Accountant','Admin') ON CONFLICT DO NOTHING;
INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r JOIN permissions p ON p.code IN ('accounting.read','tax.read','expenses.read','efris.read') WHERE r.name IN ('Manager','Auditor') ON CONFLICT DO NOTHING;
INSERT INTO business_configurations(tenant_id,config_key,value_json,value_type,version) SELECT id,'accounting.foundation.version','"4.0-B"','STRING',1 FROM tenants ON CONFLICT DO NOTHING;
INSERT INTO business_configurations(tenant_id,config_key,value_json,value_type,version) SELECT id,'accounting.calculation.engine','"DETERMINISTIC"','STRING',1 FROM tenants ON CONFLICT DO NOTHING;
INSERT INTO business_configurations(tenant_id,config_key,value_json,value_type,version) SELECT id,'efris.compliance.separate','true','BOOLEAN',1 FROM tenants ON CONFLICT DO NOTHING;
INSERT INTO schema_migrations(version) VALUES ('020_phase4b_accounting_efris_foundation') ON CONFLICT(version) DO NOTHING;
COMMIT;
