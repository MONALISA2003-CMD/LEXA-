from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("workspace_domain", ROOT / "overrides/apps/api/app/workspace_domain.py")
workspace_domain = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(workspace_domain)


def test_setup_progress_returns_first_incomplete_step_and_resume_path():
    result = workspace_domain.setup_progress(profile_exists=True, branch_count=1, warehouse_count=0, location_count=0)
    assert result["status"] == "IN_PROGRESS"
    assert result["resume_path"] == "/administration"
    assert result["completed_required_steps"] == 2
    assert result["required_steps"] == 4
    assert [s["key"] for s in result["steps"] if not s["complete"]] == ["warehouse", "location"]


def test_setup_progress_is_complete_only_when_every_required_resource_exists():
    result = workspace_domain.setup_progress(profile_exists=True, branch_count=1, warehouse_count=1, location_count=1)
    assert result["complete"] is True
    assert result["status"] == "COMPLETE"
    assert result["resume_path"] == "/"


def test_setup_progress_does_not_use_a_client_supplied_completion_flag():
    # Only persisted-resource facts are inputs to the pure function.
    result = workspace_domain.setup_progress(profile_exists=False, branch_count=20, warehouse_count=20, location_count=20)
    assert result["complete"] is False
    assert result["resume_path"] == "/administration"


def test_invitation_tokens_are_stored_as_one_way_sha256_digests():
    digest = workspace_domain.invitation_token_digest("a-very-long-random-token-for-test-only")
    assert len(digest) == 64
    assert digest != "a-very-long-random-token-for-test-only"
    assert digest == workspace_domain.invitation_token_digest("a-very-long-random-token-for-test-only")
    assert digest != workspace_domain.invitation_token_digest("a-different-random-token-for-test-only")


def test_invitation_expiry_boundary_is_closed():
    now = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
    assert workspace_domain.invitation_is_expired(now, now)
    assert not workspace_domain.invitation_is_expired(now + timedelta(seconds=1), now)
    assert workspace_domain.invitation_is_expired(now - timedelta(seconds=1), now)


def test_naive_invitation_expiry_is_treated_as_utc():
    now = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
    assert workspace_domain.invitation_is_expired(datetime(2026, 10, 20, 8), now)


def test_branch_ids_are_deduplicated_without_mutating_values():
    assert workspace_domain.normalize_branch_ids(["b", "a", "b", "c"]) == ["b", "a", "c"]
