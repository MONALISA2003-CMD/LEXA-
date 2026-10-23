from app.workspace_domain import setup_progress


def test_workspace_setup_steps_use_everyday_business_language():
    result = setup_progress(profile_exists=False, currency_configured=False, branch_count=0, warehouse_count=0, location_count=0)
    required = [step for step in result["steps"] if step["required"]]
    assert [step["label"] for step in required] == [
        "Business details",
        "Business currency",
        "Main branch",
        "Stock room",
        "Where stock is kept",
        "Payment method in your currency",
        "Money tracking",
    ]
    assert result["complete"] is False
    assert result["required_steps"] == 7
    assert result["completed_required_steps"] == 0
    assert any(step["key"] == "tax_configuration" and not step["required"] for step in result["steps"])
    assert any(step["key"] == "team_access" and not step["required"] for step in result["steps"])


def test_currency_and_payment_channel_must_be_ready_before_setup_is_complete():
    base = dict(profile_exists=True, branch_count=1, warehouse_count=1, location_count=1,
                payment_method_count=1, accounting_account_count=16, accounting_mapping_count=17)
    missing_currency = setup_progress(**base, currency_configured=False)
    assert missing_currency["complete"] is False
    assert next(step for step in missing_currency["steps"] if step["key"] == "business_currency")["complete"] is False

    missing_local_channel = setup_progress(**{**base, "payment_method_count": 0}, currency_configured=True)
    assert missing_local_channel["complete"] is False
    assert next(step for step in missing_local_channel["steps"] if step["key"] == "payment_method")["complete"] is False


def test_workspace_setup_is_complete_only_when_all_required_config_exists():
    result = setup_progress(
        profile_exists=True,
        currency_configured=True,
        branch_count=1,
        warehouse_count=1,
        location_count=1,
        payment_method_count=1,
        accounting_account_count=16,
        accounting_mapping_count=17,
        tax_configuration_ready=False,
        team_access_ready=False,
    )
    assert result["complete"] is True
    assert result["completed_required_steps"] == result["required_steps"] == 7
    # Tax and team access remain visible, recommended checks rather than a blocker.
    assert all(not step["required"] for step in result["steps"] if step["key"] in {"tax_configuration", "team_access"})
