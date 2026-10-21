from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FINANCE = ROOT / "apps/api/app/routes/finance.py"

def test_optional_journal_status_filter_is_added_only_when_supplied():
    source = FINANCE.read_text()
    start = source.index('def journal_entries(')
    end = source.index('@router.get("/journal-entries/{entry_id}")', start)
    block = source[start:end]
    assert 'FROM journal_entries WHERE tenant_id=:t' in block
    assert 'if status is not None:' in block
    assert 'query += " AND status=:s"' in block
    assert 'params["s"] = status' in block
    assert '(:s IS NULL OR status=:s)' not in block

def test_optional_fiscal_document_status_filter_is_added_only_when_supplied():
    source = FINANCE.read_text()
    start = source.index('def fiscal_documents(')
    end = source.index('@compliance.post("/sales/{sale_id}/fiscalize")', start)
    block = source[start:end]
    assert 'FROM fiscal_documents WHERE tenant_id=:t' in block
    assert 'if status is not None:' in block
    assert 'query += " AND status=:s"' in block
    assert 'params["s"] = status' in block
    assert '(:s IS NULL OR status=:s)' not in block
