from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "app" / "routes" / "team_chat.py"
MIGRATION = ROOT.parent.parent / "migrations" / "042_team_chat_foundation.sql"
MAIN = ROOT / "app" / "main.py"


def test_team_chat_is_registered_and_permission_gated():
    source = ROUTE.read_text()
    main = MAIN.read_text()
    assert "app.include_router(team_chat.router, prefix=\"/api/v1\")" in main
    assert 'Depends(require_permission("team_chat.read"))' in source
    assert 'Depends(require_permission("team_chat.send"))' in source
    assert 'Depends(require_permission("team_chat.manage"))' not in source or "team_chat.manage" in MIGRATION.read_text()


def test_messages_are_bounded_idempotent_audited_and_emit_metadata_only_events():
    source = ROUTE.read_text()
    assert "max_length=4000" in source
    assert "begin_idempotency" in source and "finish_idempotency" in source
    assert 'action="team_chat.message.sent"' in source
    assert 'event_type="TEAM_MESSAGE_SENT"' in source
    event_payload = source.split('event_type="TEAM_MESSAGE_SENT"', 1)[1].split('finish_idempotency', 1)[0]
    assert '"message_id"' in event_payload and '"body"' not in event_payload
    assert "ensure_branch_access" in source


def test_chat_schema_forces_tenant_rls_and_branch_scope_for_all_chat_tables():
    sql = MIGRATION.read_text()
    for table in ("team_conversations", "team_messages", "team_conversation_reads"):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in sql
    assert "public.lexa_can_access_branch(branch_id)" in sql
    assert "team_messages_conversation_tenant_fk" in sql
    assert "team_conversation_reads_user_scope" in sql
    assert "GRANT SELECT, INSERT ON team_messages TO lexa_app" in sql
    assert "team_chat.read" in sql and "team_chat.send" in sql and "team_chat.manage" in sql
