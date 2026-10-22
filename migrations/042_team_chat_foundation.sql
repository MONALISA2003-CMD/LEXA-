-- LEXA team chat foundation. Append-only messages, tenant/branch scoped, no AI or external provider dependency.
BEGIN;

CREATE TABLE IF NOT EXISTS team_conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  branch_id uuid NULL,
  title varchar(160) NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 160),
  context_type varchar(32) NULL CHECK (context_type IS NULL OR context_type IN ('SALE','CUSTOMER','PURCHASE_ORDER','PRODUCT','INVENTORY')),
  context_id uuid NULL,
  created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  last_message_at timestamptz NULL,
  UNIQUE (tenant_id, id),
  CONSTRAINT team_conversations_branch_tenant_fk FOREIGN KEY (tenant_id, branch_id) REFERENCES branches(tenant_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS team_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL,
  sender_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  body varchar(4000) NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 4000),
  created_at timestamptz NOT NULL DEFAULT now(),
  edited_at timestamptz NULL,
  UNIQUE (tenant_id, conversation_id, id),
  CONSTRAINT team_messages_conversation_tenant_fk FOREIGN KEY (tenant_id, conversation_id) REFERENCES team_conversations(tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS team_conversation_reads (
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL,
  reader_user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  last_read_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, conversation_id, reader_user_id),
  CONSTRAINT team_conversation_reads_conversation_tenant_fk FOREIGN KEY (tenant_id, conversation_id) REFERENCES team_conversations(tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_team_conversations_tenant_recent ON team_conversations(tenant_id, last_message_at DESC NULLS LAST, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_team_conversations_tenant_branch_recent ON team_conversations(tenant_id, branch_id, last_message_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_team_messages_conversation_recent ON team_messages(tenant_id, conversation_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_team_messages_sender_recent ON team_messages(tenant_id, sender_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_team_reads_user_recent ON team_conversation_reads(tenant_id, reader_user_id, last_read_at DESC);

ALTER TABLE team_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_conversations FORCE ROW LEVEL SECURITY;
ALTER TABLE team_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_messages FORCE ROW LEVEL SECURITY;
ALTER TABLE team_conversation_reads ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_conversation_reads FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS team_conversations_tenant_branch_scope ON team_conversations;
CREATE POLICY team_conversations_tenant_branch_scope ON team_conversations
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
         AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id)))
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
              AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id)));

DROP POLICY IF EXISTS team_messages_conversation_scope ON team_messages;
CREATE POLICY team_messages_conversation_scope ON team_messages
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
         AND EXISTS (SELECT 1 FROM team_conversations c WHERE c.tenant_id=team_messages.tenant_id AND c.id=team_messages.conversation_id))
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
              AND EXISTS (SELECT 1 FROM team_conversations c WHERE c.tenant_id=team_messages.tenant_id AND c.id=team_messages.conversation_id));

DROP POLICY IF EXISTS team_conversation_reads_user_scope ON team_conversation_reads;
CREATE POLICY team_conversation_reads_user_scope ON team_conversation_reads
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
         AND reader_user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
         AND EXISTS (SELECT 1 FROM team_conversations c WHERE c.tenant_id=team_conversation_reads.tenant_id AND c.id=team_conversation_reads.conversation_id))
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
              AND reader_user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
              AND EXISTS (SELECT 1 FROM team_conversations c WHERE c.tenant_id=team_conversation_reads.tenant_id AND c.id=team_conversation_reads.conversation_id));

GRANT SELECT, INSERT, UPDATE ON team_conversations TO lexa_app;
GRANT SELECT, INSERT ON team_messages TO lexa_app;
GRANT SELECT, INSERT, UPDATE ON team_conversation_reads TO lexa_app;

INSERT INTO permissions(code, description) VALUES
 ('team_chat.read', 'Read branch-scoped internal team conversations'),
 ('team_chat.send', 'Create conversations and send internal team messages'),
 ('team_chat.manage', 'Manage team conversation settings')
ON CONFLICT(code) DO NOTHING;

INSERT INTO role_permissions(role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code='team_chat.read'
WHERE r.name IN ('Owner','Administrator','Manager','Finance / Accounting','Sales','Inventory','Staff / Operator','Read-only','Admin','Accountant','Auditor')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions(role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code='team_chat.send'
WHERE r.name IN ('Owner','Administrator','Manager','Finance / Accounting','Sales','Inventory','Staff / Operator','Admin','Accountant')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions(role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code='team_chat.manage'
WHERE r.name IN ('Owner','Administrator','Manager','Admin')
ON CONFLICT DO NOTHING;

INSERT INTO schema_migrations(version) VALUES ('042_team_chat_foundation') ON CONFLICT (version) DO NOTHING;
COMMIT;
