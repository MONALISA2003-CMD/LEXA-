"""Unit-level mutation tests for Phase 3 organization configuration routes.

These use a small fake SQLAlchemy session to exercise handler logic without a
live database. They do not replace isolated-Postgres integration or RLS tests.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/test")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-for-phase3-organization")

ROOT = Path(__file__).resolve().parents[3]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.catalog_rules import CatalogValidation  # noqa: E402
from app.routes import organization as org  # noqa: E402


class FakeDB:
    def __init__(self, scalar_results=None):
        self.scalar_results = list(scalar_results or [])
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.refreshed = []

    def scalar(self, _statement):
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    def add(self, row):
        self.added.append(row)

    def flush(self):
        for row in self.added:
            if hasattr(row, "id") and getattr(row, "id", None) is None:
                row.id = uuid4()
            if hasattr(row, "status") and getattr(row, "status", None) is None:
                row.status = "ACTIVE"

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, row):
        self.refreshed.append(row)


def setup_mutation_spies(monkeypatch):
    actor_id, tenant_id, session_id = uuid4(), uuid4(), uuid4()
    idem = SimpleNamespace(response_status=None, response_body=None, resource_id=None)
    audit, events, finishes, idem_calls = [], [], [], []

    def begin(db, **kwargs):
        idem_calls.append(kwargs)
        return idem, None

    def finish(db, row, **kwargs):
        finishes.append(kwargs)
        row.response_status = kwargs["status_code"]
        row.response_body = kwargs["response_body"]
        row.resource_id = kwargs["resource_id"]

    monkeypatch.setattr(org, "_begin_idempotency", begin)
    monkeypatch.setattr(org, "finish_idempotency", finish)
    monkeypatch.setattr(org, "write_audit", lambda db, **kwargs: audit.append(kwargs))
    monkeypatch.setattr(org, "emit_event", lambda db, **kwargs: events.append(kwargs))
    return (actor_id, tenant_id, session_id), audit, events, finishes, idem_calls


def test_business_profile_input_normalizes_names_country_and_currency():
    body = org.BusinessProfileIn(
        legal_name="  Example Limited  ",
        display_name=" Example Shop ",
        country_code="ug",
        currency_code="ugx",
    )
    assert body.legal_name == "Example Limited"
    assert body.display_name == "Example Shop"
    assert body.country_code == "UG"
    assert body.currency_code == "UGX"


def test_create_profile_is_idempotent_audited_and_emits_event(monkeypatch):
    ctx, audit, events, finishes, idem_calls = setup_mutation_spies(monkeypatch)
    db = FakeDB(scalar_results=[None])
    body = org.BusinessProfileIn(legal_name="Example Limited", display_name="Example", country_code="UG", currency_code="UGX")

    result = org.create_profile(body, idempotency_key="profile-create-1", ctx=(db, *ctx))

    assert result.tenant_id == ctx[1]
    assert result.legal_name == "Example Limited"
    assert db.commits == 1
    assert idem_calls[0]["operation_type"] == "organization.profile.create"
    assert audit[0]["action"] == "organization.profile.create"
    assert events[0]["event_type"] == "BusinessProfileCreated"
    assert finishes[0]["status_code"] == 201
    assert UUID(finishes[0]["response_body"]["id"]) == result.id


def test_update_profile_only_changes_supplied_fields_and_is_audited(monkeypatch):
    ctx, audit, events, finishes, idem_calls = setup_mutation_spies(monkeypatch)
    profile = org.BusinessProfile(
        id=uuid4(), tenant_id=ctx[1], legal_name="Example Limited", display_name="Old Name",
        country_code="UG", currency_code="UGX",
    )
    db = FakeDB(scalar_results=[profile])
    result = org.update_profile(org.BusinessProfilePatch(display_name=" New Name "), idempotency_key="profile-update-1", ctx=(db, *ctx))

    assert result.display_name == "New Name"
    assert result.legal_name == "Example Limited"
    assert idem_calls[0]["operation_type"] == "organization.profile.update"
    assert audit[0]["action"] == "organization.profile.update"
    assert events[0]["event_type"] == "BusinessProfileUpdated"
    assert events[0]["payload"]["changed_fields"] == ["display_name"]
    assert finishes[0]["status_code"] == 200
    assert db.commits == 1


def test_create_branch_is_scoped_to_context_and_emits_audit_event(monkeypatch):
    ctx, audit, events, finishes, idem_calls = setup_mutation_spies(monkeypatch)
    db = FakeDB()
    result = org.create_branch(org.BranchIn(name="Main Branch", code=" main "), idempotency_key="branch-create-1", ctx=(db, *ctx))

    assert result.tenant_id == ctx[1]
    assert result.code == "MAIN"
    assert result.status == "ACTIVE"
    assert idem_calls[0]["operation_type"] == "organization.branch.create"
    assert audit[0]["action"] == "organization.branch.create"
    assert events[0]["event_type"] == "BranchCreated"
    assert finishes[0]["status_code"] == 201


def test_branch_update_does_not_return_a_branch_outside_the_selected_tenant(monkeypatch):
    ctx, _audit, _events, _finishes, _idem_calls = setup_mutation_spies(monkeypatch)
    foreign_branch_id = uuid4()
    db = FakeDB(scalar_results=[None])

    with pytest.raises(HTTPException) as exc:
        org.update_branch(foreign_branch_id, org.BranchPatch(name="Changed"), idempotency_key="branch-update-1", ctx=(db, *ctx))

    assert exc.value.status_code == 404
    assert db.commits == 0
    assert db.rollbacks == 1


def test_idempotency_conflict_maps_to_http_409(monkeypatch):
    def reject(*_args, **_kwargs):
        raise CatalogValidation("Idempotency-Key was already used with a different request")

    monkeypatch.setattr(org, "begin_idempotency", reject)
    with pytest.raises(HTTPException) as exc:
        org._begin_idempotency(FakeDB(), tenant_id=uuid4(), operation_type="organization.branch.create", key="same-key", payload={"name": "Different"})
    assert exc.value.status_code == 409


def test_empty_patch_is_rejected_before_database_mutation(monkeypatch):
    ctx, _audit, _events, _finishes, _idem_calls = setup_mutation_spies(monkeypatch)
    db = FakeDB()
    with pytest.raises(HTTPException) as exc:
        org.update_profile(org.BusinessProfilePatch(), idempotency_key="profile-update-empty", ctx=(db, *ctx))
    assert exc.value.status_code == 422
    assert db.commits == 0


def test_profile_retry_replays_saved_response_without_creating_duplicate(monkeypatch):
    ctx, _audit, _events, _finishes, _idem_calls = setup_mutation_spies(monkeypatch)
    saved_id = uuid4()
    saved = {
        "id": str(saved_id), "tenant_id": str(ctx[1]), "legal_name": "Example Limited",
        "display_name": "Example", "country_code": "UG", "currency_code": "UGX",
    }
    monkeypatch.setattr(org, "_begin_idempotency", lambda *args, **kwargs: (SimpleNamespace(), (201, saved)))
    db = FakeDB()
    body = org.BusinessProfileIn(legal_name="Example Limited", display_name="Example", country_code="UG", currency_code="UGX")

    result = org.create_profile(body, idempotency_key="profile-create-retry", ctx=(db, *ctx))

    assert result.id == saved_id
    assert not db.added
    assert db.commits == 0
    assert db.rollbacks == 1


def test_branch_update_success_is_audited_and_idempotent(monkeypatch):
    ctx, audit, events, finishes, idem_calls = setup_mutation_spies(monkeypatch)
    branch = org.Branch(id=uuid4(), tenant_id=ctx[1], name="Main", code="MAIN", status="ACTIVE")
    db = FakeDB(scalar_results=[branch])

    result = org.update_branch(branch.id, org.BranchPatch(name="Front Shop", code="front"), idempotency_key="branch-update-good", ctx=(db, *ctx))

    assert result.name == "Front Shop"
    assert result.code == "FRONT"
    assert idem_calls[0]["operation_type"] == "organization.branch.update"
    assert audit[0]["action"] == "organization.branch.update"
    assert events[0]["event_type"] == "BranchUpdated"
    assert finishes[0]["status_code"] == 200
    assert db.commits == 1


def test_warehouse_create_rejects_branch_not_found_in_current_tenant(monkeypatch):
    ctx, _audit, _events, _finishes, _idem_calls = setup_mutation_spies(monkeypatch)
    db = FakeDB(scalar_results=[None])
    foreign_branch_id = uuid4()
    body = org.WarehouseIn(name="Remote stock", code="REMOTE", branch_id=foreign_branch_id)

    with pytest.raises(HTTPException) as exc:
        org.create_warehouse(body, idempotency_key="warehouse-cross-tenant", ctx=(db, *ctx))

    assert exc.value.status_code == 400
    assert db.commits == 0
    assert db.rollbacks == 1


def test_warehouse_location_and_pos_inputs_normalize_codes_and_names():
    warehouse = org.WarehouseIn(name="  Main Warehouse ", code=" main ")
    location = org.LocationIn(name=" Front Shelf ", code=" a1 ", warehouse_id=uuid4())
    terminal = org.PosIn(name=" Front Till ", code=" till-1 ", branch_id=uuid4())

    assert (warehouse.name, warehouse.code) == ("Main Warehouse", "MAIN")
    assert (location.name, location.code) == ("Front Shelf", "A1")
    assert (terminal.name, terminal.code) == ("Front Till", "TILL-1")
