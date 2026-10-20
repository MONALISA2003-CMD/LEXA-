"""Source-contract regression tests for Phase 3 organization mutation controls.

These checks are intentionally fast guardrails; isolated-database integration and
credentialed authorization tests remain separate release gates.
"""
import os
from pathlib import Path

ROOT = Path(os.environ.get("LEXA_ROOT", Path(__file__).resolve().parents[3]))
SOURCE = ROOT / "apps" / "api" / "app" / "routes" / "organization.py"


def test_profile_creation_and_update_are_tenant_scoped_and_audited():
    source = SOURCE.read_text(encoding="utf-8")
    assert '@router.post("/profile", response_model=BusinessProfileOut, status_code=201)' in source
    assert '@router.patch("/profile", response_model=BusinessProfileOut)' in source
    assert 'Depends(require_permission("organization.manage"))' in source
    assert 'select(BusinessProfile).where(BusinessProfile.tenant_id == tenant_id)' in source
    assert 'action="organization.profile.create"' in source
    assert 'action="organization.profile.update"' in source
    assert 'event_type="BusinessProfileCreated"' in source
    assert 'event_type="BusinessProfileUpdated"' in source


def test_profile_and_branch_writes_have_idempotency_and_cached_response_contracts():
    source = SOURCE.read_text(encoding="utf-8")
    assert 'operation_type="organization.profile.create"' in source
    assert 'operation_type="organization.profile.update"' in source
    assert 'operation_type="organization.branch.create"' in source
    assert 'operation_type="organization.branch.update"' in source
    assert 'def _require_replay(' in source
    assert "finish_idempotency(" in source


def test_branch_patch_and_create_are_scoped_to_selected_tenant():
    source = SOURCE.read_text(encoding="utf-8")
    assert '@router.post("/branches", response_model=BranchOut, status_code=201)' in source
    assert '@router.patch("/branches/{branch_id}", response_model=BranchOut)' in source
    assert 'select(Branch).where(Branch.id == branch_id, Branch.tenant_id == tenant_id)' in source
    assert 'action="organization.branch.create"' in source
    assert 'action="organization.branch.update"' in source
    assert 'event_type="BranchCreated"' in source
    assert 'event_type="BranchUpdated"' in source


def test_related_resource_ids_are_verified_against_same_tenant():
    source = SOURCE.read_text(encoding="utf-8")
    assert 'select(Branch.id).where(Branch.id == body.branch_id, Branch.tenant_id == tenant_id)' in source
    assert 'select(Warehouse.id).where(Warehouse.id == body.warehouse_id, Warehouse.tenant_id == tenant_id)' in source
    assert 'select(Branch.id).where(Branch.id == body.branch_id, Branch.tenant_id == tenant_id)' in source


def test_configuration_creates_are_audited_and_emit_outbox_events():
    source = SOURCE.read_text(encoding="utf-8")
    for event in (
        'BusinessProfileCreated', 'BusinessProfileUpdated', 'BranchCreated', 'BranchUpdated',
        'WarehouseCreated', 'LocationCreated', 'PosTerminalCreated',
    ):
        assert f'event_type="{event}"' in source
    for action in (
        'organization.profile.create', 'organization.profile.update', 'organization.branch.create',
        'organization.branch.update', 'organization.warehouse.create', 'organization.location.create',
        'organization.pos_terminal.create',
    ):
        assert f'action="{action}"' in source
