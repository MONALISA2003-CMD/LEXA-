from app.workspace_domain import setup_progress


def test_workspace_setup_steps_use_everyday_business_language():
    result = setup_progress(profile_exists=False, branch_count=0, warehouse_count=0, location_count=0)
    assert [step["label"] for step in result["steps"]] == [
        "Business details",
        "Main branch",
        "Stock room",
        "Where stock is kept",
        "Payment method",
        "Money tracking",
    ]
    assert result["complete"] is False
    assert result["required_steps"] == 6
    assert result["completed_required_steps"] == 0


def test_workspace_setup_is_complete_only_when_payment_and_finance_defaults_exist():
    result = setup_progress(
        profile_exists=True,
        branch_count=1,
        warehouse_count=1,
        location_count=1,
        payment_method_count=1,
        accounting_account_count=16,
        accounting_mapping_count=17,
    )
    assert result["complete"] is True
    assert result["completed_required_steps"] == result["required_steps"] == 6
