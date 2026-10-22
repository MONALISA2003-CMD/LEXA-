from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMERCE = ROOT / "app" / "routes" / "commerce.py"
RULES = ROOT / "app" / "commerce_rules.py"
WEB_COMMERCE = ROOT.parent.parent / "apps" / "web" / "app" / "commerce" / "page.tsx"
WEB_FINANCE = ROOT.parent.parent / "apps" / "web" / "app" / "accounting" / "page.tsx"


def test_payment_method_labels_block_credential_like_text_and_long_identifiers():
    source = COMMERCE.read_text(encoding="utf-8")
    rules = RULES.read_text(encoding="utf-8")
    channel = source.split("class ChannelCreate(Strict):", 1)[1].split("class ChannelDeactivate", 1)[0]
    assert "safe_payment_channel_label(self.name, self.provider)" in channel
    assert "_SECRET_TEXT.search(label)" in rules
    assert r"\d{8,}" in rules
    assert "Use a friendly name only" in rules


def test_payment_references_are_normalized_and_reject_explicit_secrets():
    source = COMMERCE.read_text(encoding="utf-8")
    rules = RULES.read_text(encoding="utf-8")
    assert "safe_payment_reference" in source
    helper = rules.split("def safe_payment_reference", 1)[1].split("def safe_payment_channel_label", 1)[0]
    assert "_SECRET_TEXT.search(reference)" in helper
    assert "Never enter a PIN, password or verification code" in helper
    allocations = source.split("class PaymentAllocationIn(Strict):", 1)[1].split("class SaleCreate", 1)[0]
    payment = source.split("class PaymentCreate(Strict):", 1)[1].split("class ActualIn", 1)[0]
    assert "@field_validator(\"reference\")" in allocations
    assert "safe_payment_reference(value)" in allocations
    assert "@field_validator(\"reference\")" in payment
    assert "safe_payment_reference(value)" in payment


def test_frontend_warns_never_to_enter_payment_credentials():
    commerce = WEB_COMMERCE.read_text(encoding="utf-8")
    finance = WEB_FINANCE.read_text(encoding="utf-8")
    assert "Never enter PINs, passwords or one-time codes" in commerce
    assert "never a PIN, password or one-time confirmation code" in finance
    assert "does not verify the payment" in commerce
