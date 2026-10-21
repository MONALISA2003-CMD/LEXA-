-- ACCEPTED REPLACEMENT — ORIGINAL HISTORICAL SOURCE LOST; NOT BYTE-IDENTICAL.
-- Accepted 2026-10-21 for reproducible clean replay after source-loss decision.
-- Do not describe this file as the exact SQL originally applied in production.
-- Full migration identity: 025_phase4_purchasing_permissions.
INSERT INTO permissions(code,description) VALUES
 ('purchasing.read','View suppliers and purchasing state'),
 ('purchasing.manage','Create and manage supplier and purchasing records'),
 ('purchasing.approve','Approve purchase orders and purchasing returns'),
 ('purchasing.receive','Receive purchase orders into inventory'),
 ('purchasing.returns.manage','Manage purchase returns')
ON CONFLICT(code) DO NOTHING;
INSERT INTO role_permissions(role_id,permission_id)
 SELECT r.id,p.id FROM roles r JOIN permissions p ON p.code LIKE 'purchasing.%'
 WHERE r.name IN ('Owner','Administrator','Manager') ON CONFLICT DO NOTHING;
INSERT INTO role_permissions(role_id,permission_id)
 SELECT r.id,p.id FROM roles r JOIN permissions p ON p.code IN ('purchasing.read','purchasing.receive')
 WHERE r.name='Inventory' ON CONFLICT DO NOTHING;
INSERT INTO role_permissions(role_id,permission_id)
 SELECT r.id,p.id FROM roles r JOIN permissions p ON p.code='purchasing.read'
 WHERE r.name IN ('Finance / Accounting','Read-only') ON CONFLICT DO NOTHING;
