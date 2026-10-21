from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_collected_today_comes_from_recorded_payments_for_business_date():
    source = (ROOT / "app" / "routes" / "commerce.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "dashboard")
    body = ast.get_source_segment(source, function) or ""

    assert "SELECT currency_code FROM public.business_profiles WHERE tenant_id=:tenant_id" in body
    assert "FROM public.payments AS p" in body
    assert "p.status='RECORDED'" in body
    assert "p.business_date=:business_date" in body
    assert "p.currency_code=:currency_code" in body
    assert "SUM(s.amount_paid),0) collected" not in body
    assert "COALESCE(s.completed_at, s.created_at)" in body
    assert '"currency_code": currency_code' in body


def test_collected_today_is_a_separate_measure_from_sale_total():
    source = (ROOT / "app" / "routes" / "commerce.py").read_text(encoding="utf-8")
    assert "COALESCE(SUM(s.total),0) sales" in source
    assert "COALESCE(SUM(s.amount_due),0) credit" in source
    # Collection must include independently recorded receivable payments, not
    # merely the amount initially paid when the sales record was completed.
    assert "SELECT SUM(p.amount)" in source
