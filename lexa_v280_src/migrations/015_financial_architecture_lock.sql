-- LEXA Financial Architecture Lock v1.0.0
-- Additive, tenant-safe architecture contract. No business rows are deleted or rewritten.

INSERT INTO business_capabilities (tenant_id, code, name, enabled, status, version, configuration)
SELECT
  t.id,
  'FINANCIAL_ARCHITECTURE',
  'Financial Architecture Foundation',
  true,
  'ACTIVE',
  1,
  '{"architecture_version":"1.0.0","status":"LOCKED","payment_model":"MANUAL_FIRST_INTEGRATION_OPTIONAL","deterministic_source_of_truth":true}'::jsonb
FROM tenants t
ON CONFLICT (tenant_id, code) DO UPDATE
  SET name = EXCLUDED.name,
      enabled = true,
      status = 'ACTIVE',
      version = EXCLUDED.version,
      configuration = business_capabilities.configuration || EXCLUDED.configuration,
      updated_at = now();

INSERT INTO business_configurations (tenant_id, config_key, value_json, value_type, version)
SELECT
  t.id,
  c.config_key,
  c.value_json,
  c.value_type,
  1
FROM tenants t
CROSS JOIN (
  VALUES
    ('financial.architecture.version', '"1.0.0"'::jsonb, 'STRING'),
    ('financial.architecture.status', '"LOCKED"'::jsonb, 'STRING'),
    ('financial.payment.model', '"MANUAL_FIRST_INTEGRATION_OPTIONAL"'::jsonb, 'STRING'),
    ('financial.payment.credentials_required', 'false'::jsonb, 'BOOLEAN'),
    ('financial.payment.terminology', '{"method":"Payment Method","channel":"Payment Channel"}'::jsonb, 'JSON'),
    ('financial.domain.chain', '["PRODUCTS_INVENTORY","SALES","PAYMENTS_RECEIVABLES","ACCOUNTING","RECONCILIATION","BUSINESS_INTELLIGENCE"]'::jsonb, 'JSON'),
    ('financial.source_of_truth', '"TRANSACTIONAL_CORE"'::jsonb, 'STRING'),
    ('financial.calculation_engine', '"DETERMINISTIC"'::jsonb, 'STRING'),
    ('financial.ai.boundary', '{"may_explain":true,"may_investigate":true,"may_recommend":true,"may_override_financial_truth":false}'::jsonb, 'JSON'),
    ('financial.credit.model', '"RECEIVABLE_NOT_PAYMENT_CHANNEL"'::jsonb, 'STRING'),
    ('financial.reconciliation.model', '"EXPECTED_VS_ACTUAL"'::jsonb, 'STRING'),
    ('financial.compliance.efris_separate', 'true'::jsonb, 'BOOLEAN'),
    ('financial.payment_channel.forbidden_fields', '["account_number","phone_number","pin","password","api_key","api_secret","access_token","refresh_token","otp","card_number","cvv"]'::jsonb, 'JSON')
) AS c(config_key, value_json, value_type)
ON CONFLICT (tenant_id, config_key) DO UPDATE
  SET value_json = EXCLUDED.value_json,
      value_type = EXCLUDED.value_type,
      version = EXCLUDED.version,
      updated_at = now();

INSERT INTO transaction_types (tenant_id, code, name, category, initial_status, statuses, transitions, active, configuration)
SELECT
  t.id,
  f.code,
  f.name,
  'FINANCE',
  f.initial_status,
  f.statuses::jsonb,
  f.transitions::jsonb,
  true,
  f.configuration::jsonb
FROM tenants t
CROSS JOIN (
  VALUES
    ('SALE','Sale','DRAFT','["DRAFT","COMPLETED","VOIDED","CANCELLED"]','{"DRAFT":["COMPLETED","CANCELLED"],"COMPLETED":["VOIDED"],"VOIDED":[],"CANCELLED":[]}','{"architecture_version":"1.0.0","domain":"SALES","canonical":true}'),
    ('SALE_RETURN','Sale Return','DRAFT','["DRAFT","COMPLETED","CANCELLED"]','{"DRAFT":["COMPLETED","CANCELLED"],"COMPLETED":[],"CANCELLED":[]}','{"architecture_version":"1.0.0","domain":"SALES","canonical":true}'),
    ('PAYMENT','Payment','RECORDED','["RECORDED","VOIDED","REVERSED"]','{"RECORDED":["VOIDED","REVERSED"],"VOIDED":[],"REVERSED":[]}','{"architecture_version":"1.0.0","domain":"PAYMENTS_RECEIVABLES","canonical":true}'),
    ('PAYMENT_ALLOCATION','Payment Allocation','RECORDED','["RECORDED","REVERSED"]','{"RECORDED":["REVERSED"],"REVERSED":[]}','{"architecture_version":"1.0.0","domain":"PAYMENTS_RECEIVABLES","canonical":true}'),
    ('RECEIVABLE','Receivable','OPEN','["OPEN","PARTIALLY_PAID","PAID","WRITTEN_OFF","CANCELLED"]','{"OPEN":["PARTIALLY_PAID","PAID","WRITTEN_OFF","CANCELLED"],"PARTIALLY_PAID":["PAID","WRITTEN_OFF","CANCELLED"],"PAID":[],"WRITTEN_OFF":[],"CANCELLED":[]}','{"architecture_version":"1.0.0","domain":"PAYMENTS_RECEIVABLES","canonical":true}'),
    ('REFUND','Refund','RECORDED','["RECORDED","VOIDED","REVERSED"]','{"RECORDED":["VOIDED","REVERSED"],"VOIDED":[],"REVERSED":[]}','{"architecture_version":"1.0.0","domain":"PAYMENTS_RECEIVABLES","canonical":true}'),
    ('RECONCILIATION','Reconciliation','OPEN','["OPEN","VARIANCE_DETECTED","UNDER_REVIEW","RESOLVED","ACKNOWLEDGED","CLOSED"]','{"OPEN":["VARIANCE_DETECTED","CLOSED"],"VARIANCE_DETECTED":["UNDER_REVIEW","RESOLVED","ACKNOWLEDGED"],"UNDER_REVIEW":["RESOLVED","ACKNOWLEDGED"],"RESOLVED":["CLOSED"],"ACKNOWLEDGED":["CLOSED"],"CLOSED":[]}','{"architecture_version":"1.0.0","domain":"RECONCILIATION","canonical":true}'),
    ('SETTLEMENT','Settlement','DRAFT','["DRAFT","POSTED","RECONCILED","CANCELLED"]','{"DRAFT":["POSTED","CANCELLED"],"POSTED":["RECONCILED","CANCELLED"]}','{"architecture_version":"1.0.0","domain":"RECONCILIATION","canonical":true}')
) AS f(code, name, initial_status, statuses, transitions, configuration)
ON CONFLICT (tenant_id, code) DO UPDATE
  SET category = EXCLUDED.category,
      active = EXCLUDED.active,
      configuration = transaction_types.configuration || EXCLUDED.configuration,
      updated_at = now();

INSERT INTO permissions (code, description) VALUES
  ('sales.read','Read sales'),
  ('sales.manage','Create and manage sales'),
  ('sales.complete','Complete a sale'),
  ('sales.return','Process a sale return'),
  ('sales.void','Void a completed sale'),
  ('payments.read','Read recorded payments'),
  ('payments.manage','Record and manage payments'),
  ('payments.allocate','Allocate payments to receivables or sales'),
  ('receivables.read','Read receivables'),
  ('receivables.manage','Manage receivables'),
  ('reconciliation.read','Read reconciliation data'),
  ('reconciliation.manage','Start and manage reconciliations'),
  ('reconciliation.resolve','Resolve or acknowledge reconciliation variances'),
  ('reconciliation.close','Close a reconciled business day'),
  ('accounting.read','Read accounting information'),
  ('accounting.manage','Manage accounting configuration and records'),
  ('accounting.post','Post accounting entries'),
  ('accounting.reverse','Reverse accounting entries'),
  ('financial.configure','Configure payment channels and financial settings')
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'Owner'
  AND p.code IN (
    'sales.read','sales.manage','sales.complete','sales.return','sales.void',
    'payments.read','payments.manage','payments.allocate',
    'receivables.read','receivables.manage',
    'reconciliation.read','reconciliation.manage','reconciliation.resolve','reconciliation.close',
    'accounting.read','accounting.manage','accounting.post','accounting.reverse',
    'financial.configure'
  )
ON CONFLICT DO NOTHING;

INSERT INTO schema_migrations(version)
VALUES ('015_financial_architecture_lock')
ON CONFLICT (version) DO NOTHING;
