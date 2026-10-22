from app.workspace_domain import setup_progress


def test_workspace_setup_steps_use_everyday_business_language():
    result = setup_progress(profile_exists=False, branch_count=0, warehouse_count=0, location_count=0)
    assert [step["label"] for step in result["steps"]] == [
        "Business details",
        "Main branch",
        "Stock room",
        "Where stock is kept",
    ]
    assert result["complete"] is False
    assert result["completed_required_steps"] == 0
