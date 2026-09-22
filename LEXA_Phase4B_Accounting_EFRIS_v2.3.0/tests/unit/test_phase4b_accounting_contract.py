from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "apps/api/app/routes/finance.py"
MAIN = ROOT / "apps/api/app/main.py"
MIG = ROOT / "migrations/020_phase4b_accounting_efris_foundation.sql"
WEB_API = ROOT / "apps/web/lib/api.ts"
ACCOUNTING = ROOT / "apps/web/app/accounting/page.tsx"
COMPLIANCE = ROOT / "apps/web/app/compliance/page.tsx"
CSS = ROOT / "apps/web/app/globals.css"


def test_phase4b_backend_route_and_core_contracts_exist():
    s = API.read_text()
    assert 'router = APIRouter(prefix="/accounting"' in s
    assert 'compliance = APIRouter(prefix="/compliance"' in s
    for marker in [
        '/accounts', '/periods', '/trial-balance', '/income-statement', '/balance-sheet',
        '/journal-entries', '/expenses', '/efris/config', '/fiscal-documents', '/fiscalize'
    ]:
        assert marker in s
    assert 'post_sale_journal' in s
    assert 'post_payment_journal' in s
    assert 'post_expense_journal' in s


def test_phase4b_main_includes_routes():
    s = MAIN.read_text()
    assert 'finance' in s
    assert 'finance.router' in s
    assert 'finance.compliance' in s


def test_phase4b_migration_has_authoritative_accounting_and_efris_contract():
    s = MIG.read_text()
    for table in [
        'accounting_accounts', 'accounting_periods', 'journal_entries', 'journal_lines',
        'accounting_mappings', 'tax_rates', 'tax_configurations', 'expense_records',
        'efris_configurations', 'fiscal_documents', 'fiscalization_events', 'inventory_valuation_snapshots'
    ]:
        assert f'CREATE TABLE IF NOT EXISTS {table}' in s
    assert '020_phase4b_accounting_efris_foundation' in s
    assert "OUTPUT_TAX" in s and "INPUT_TAX" in s
    assert 'Posted journal entry facts are immutable' in s
    assert 'create_fiscal_document_for_sale' in s


def test_phase4b_frontend_contract_and_mobile_sidebar_fix():
    api = WEB_API.read_text()
    for fn in ['getAccountingAccounts', 'getAccountingPeriods', 'getTrialBalance', 'getIncomeStatement', 'getBalanceSheet', 'getExpenses', 'getEfrisConfig', 'getFiscalDocuments']:
        assert f'export function {fn}' in api
    assert ACCOUNTING.exists()
    assert COMPLIANCE.exists()
    css = CSS.read_text()
    assert '.lexa-sidebar-mark' in css
    assert 'object-fit:contain' in css
