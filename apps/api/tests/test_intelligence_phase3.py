from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.intelligence import document_extraction as extraction

SAMPLE = """SUPPLIER: Nile Office Supplies Ltd
INVOICE NUMBER: NS-2026-1045
INVOICE DATE: 24/10/2026
SUBTOTAL: UGX 100,000
VAT Amount: UGX 18,000
Grand Total: UGX 118,000
TIN: 1234567890
"""


def test_parse_document_fields_extracts_labeled_values_with_evidence():
    result = extraction.parse_document_fields(SAMPLE, "SUPPLIER_INVOICE")
    assert result["schema_version"] == "phase3.document_candidate.v1"
    assert result["fields"]["supplier_name"]["value"] == "Nile Office Supplies Ltd"
    assert result["fields"]["invoice_number"]["value"] == "NS-2026-1045"
    assert result["fields"]["invoice_date"]["value"] == "2026-10-24"
    assert result["fields"]["subtotal"]["value"] == "100000.00"
    assert result["fields"]["tax_amount"]["value"] == "18000.00"
    assert result["fields"]["total"]["value"] == "118000.00"
    assert result["fields"]["tax_id"]["value"] == "1234567890"
    assert result["fields"]["currency_code"]["value"] == "UGX"
    assert result["fields"]["total"]["evidence"] == "Grand Total: UGX 118,000"
    assert result["warnings"]
    assert any("not created or posted" in warning for warning in result["warnings"])


def test_uganda_day_month_year_dates_are_normalized_and_invalid_dates_rejected():
    assert extraction._normalize_date("03/04/2026") == "2026-04-03"
    assert extraction._normalize_date("31/02/2026") is None
    assert extraction._normalize_date("24 Oct 2026") == "2026-10-24"


def test_no_text_yields_unavailable_candidates_not_fabricated_values():
    result = extraction.parse_document_fields("  \x00 \n", "EXPENSE_RECEIPT")
    assert result["text_character_count"] == 0
    assert all(field["value"] is None for field in result["fields"].values())
    assert any("No readable text" in warning for warning in result["warnings"])


def test_unknown_document_type_rejected():
    with pytest.raises(ValueError, match="Unsupported document type"):
        extraction.parse_document_fields(SAMPLE, "BANK_LOGIN")


@pytest.mark.parametrize("mime", ["text/plain", "application/octet-stream", "application/x-msdownload"])
def test_unsupported_mime_types_rejected_before_extraction(mime):
    with pytest.raises(ValueError, match="Unsupported file type"):
        extraction.extract_document(b"x", mime, "OTHER")


def test_empty_and_over_limit_files_are_rejected():
    with pytest.raises(ValueError, match="empty or exceeds"):
        extraction.extract_document(b"", "image/png", "OTHER")
    with pytest.raises(ValueError, match="empty or exceeds"):
        extraction.extract_document(b"x" * (extraction.MAX_FILE_BYTES + 1), "image/png", "OTHER")


def test_file_signature_must_match_declared_mime_before_native_parser_runs(monkeypatch):
    def unexpected_run(*args, **kwargs):
        raise AssertionError("native parser must not run for mismatched content")

    monkeypatch.setattr(extraction, "_run", unexpected_run)
    with pytest.raises(ValueError, match="do not match"):
        extraction.extract_document(b"not really a PDF", "application/pdf", "OTHER")
    with pytest.raises(ValueError, match="do not match"):
        extraction.extract_document(b"not really an image", "image/png", "OTHER")


def test_pdf_text_layer_uses_local_bounded_subprocess_and_returns_candidates(monkeypatch):
    seen = []

    def fake_run(command, *, input_bytes=None, timeout=8):
        seen.append((command, timeout))
        assert command[0] == "pdftotext"
        assert command[-1] == "-"
        assert timeout <= 10
        return subprocess.CompletedProcess(command, 0, SAMPLE.encode(), b"")

    monkeypatch.setattr(extraction, "_run", fake_run)
    result = extraction.extract_document(b"%PDF-synthetic", "application/pdf", "SUPPLIER_INVOICE")
    assert result["extraction_method"] == "PDF_TEXT_LAYER"
    assert result["extraction_status"] == "SUCCEEDED"
    assert result["candidate_fields"]["fields"]["total"]["value"] == "118000.00"
    assert len(seen) == 1


def test_pdf_without_text_falls_back_to_local_ocr_then_manual_review(monkeypatch):
    def fake_run(command, *, input_bytes=None, timeout=8):
        if command[0] == "pdftotext":
            return subprocess.CompletedProcess(command, 0, b"", b"")
        if command[0] == "pdftoppm":
            return subprocess.CompletedProcess(command, 1, b"", b"renderer unavailable")
        raise AssertionError(f"Unexpected subprocess: {command[0]}")

    monkeypatch.setattr(extraction, "_run", fake_run)
    result = extraction.extract_document(b"%PDF-synthetic", "application/pdf", "OTHER")
    assert result["extraction_method"] == "UNAVAILABLE"
    assert result["extraction_status"] == "UNAVAILABLE"
    assert result["extracted_text"] == ""
    assert all(v["value"] is None for v in result["candidate_fields"]["fields"].values())


def test_text_and_candidate_output_are_bounded():
    result = extraction.parse_document_fields("Invoice number: INV-1\n" + ("x" * 20000), "OTHER")
    assert result["text_character_count"] <= extraction.MAX_TEXT_CHARS
    for field in result["fields"].values():
        if field["evidence"] is not None:
            assert len(field["evidence"]) <= 220


def test_phase3_migration_is_tenant_branch_scoped_and_has_review_history():
    repo_root = Path(__file__).resolve().parents[3]
    migration = (repo_root / "migrations/046_intelligence_documents.sql").read_text(encoding="utf-8")
    assert "ALTER TABLE public.intelligence_documents FORCE ROW LEVEL SECURITY" in migration
    assert "ALTER TABLE public.intelligence_document_reviews FORCE ROW LEVEL SECURITY" in migration
    assert "public.lexa_can_access_branch(branch_id)" in migration
    assert "UNIQUE (tenant_id, branch_id, content_sha256)" in migration
    assert "GRANT SELECT, INSERT ON TABLE public.intelligence_document_reviews TO lexa_app" in migration
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.intelligence_documents TO lexa_app" not in migration
    assert "046_intelligence_documents" in migration


def test_phase3_api_ui_and_policy_keep_review_separate_from_business_writes():
    api_root = Path(__file__).resolve().parents[1]
    repo_root = Path(__file__).resolve().parents[3]
    document_routes = (api_root / "app/intelligence/document_routes.py").read_text(encoding="utf-8")
    main = (api_root / "app/main.py").read_text(encoding="utf-8")
    ui = (repo_root / "apps/web/app/documents/page.tsx").read_text(encoding="utf-8")
    ai_ui = (repo_root / "apps/web/app/ai-assistant/page.tsx").read_text(encoding="utf-8")
    ai_client = (repo_root / "apps/web/lib/ai-assistant-api.ts").read_text(encoding="utf-8")
    assert "intelligence.documents.intake" in document_routes
    assert "intelligence.documents.review" in document_routes
    assert "transaction_created\"] = False" in document_routes
    assert 'app.include_router(intelligence_documents_router, prefix="/api/v1")' in main
    dockerfile = (repo_root / "apps/api/Dockerfile").read_text(encoding="utf-8")
    assert "poppler-utils" in dockerfile and "tesseract-ocr" in dockerfile
    assert "AI_POLICY_GATE_REQUIRED" in main
    assert "No business transaction was created" in ui
    # The replacement chat must stay interactive while all external execution
    # remains server-side and subject to the central intelligence policy.
    assert "Your LEXA business assistant" in ai_ui
    assert "Private to your signed-in workspace" in ai_ui
    assert "Your business question" in ai_ui
    assert "MarkdownAnswer" in ai_ui
    assert "askLexaAssistant" in ai_ui
    assert "/api/lexa/api/v1/ai/assistant" in ai_client
    assert "Authorization: `Bearer ${token}`" in ai_client
    assert "include_business_summary: false" in ai_client
    assert "tenant_id" not in ai_client and "user_id" not in ai_client
    assert "fetch(" not in ai_ui
    assert not any(provider_url in ai_ui + ai_client for provider_url in (
        "api.openai.com", "generativelanguage.googleapis.com", "api.groq.com"
    ))
    assert "NEXT_PUBLIC_" not in ai_ui + ai_client


def test_replay_manifest_appends_candidate_migrations_in_order_without_production_opt_in():
    repo_root = Path(__file__).resolve().parents[3]
    manifest_path = repo_root / "migrations/reconstructed/clean_replay_order.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = [step["path"] for step in manifest["steps"]]
    assert paths[-2:] == [
        "migrations/045_intelligence_foundation.sql",
        "migrations/046_intelligence_documents.sql",
    ]
    assert manifest["do_not_execute_in_production"] is True
    assert "disposable PostgreSQL" in manifest["replay_only_notice"]


def test_document_route_is_registered_and_external_ai_stays_default_denied():
    repo_root = Path(__file__).resolve().parents[3]
    routes = (repo_root / "apps/api/app/intelligence/routes.py").read_text(encoding="utf-8")
    policy = (repo_root / "apps/api/app/intelligence/policy.py").read_text(encoding="utf-8")
    main = (repo_root / "apps/api/app/main.py").read_text(encoding="utf-8")
    assert '@router.post("/intake")' in (repo_root / "apps/api/app/intelligence/document_routes.py").read_text(encoding="utf-8")
    assert '@router.get("/daily-brief")' in routes
    assert "external_providers_enabled: bool = False" in policy
    assert "pdf_text" in routes and "pdftotext" in routes and "tesseract" in routes
    assert "AI_POLICY_GATE_REQUIRED" in main
    assert 'app.include_router(intelligence_router, prefix="/api/v1")' in main
    assert 'app.include_router(intelligence_documents_router, prefix="/api/v1")' in main
    dockerfile = (repo_root / "apps/api/Dockerfile").read_text(encoding="utf-8")
    assert "poppler-utils" in dockerfile and "tesseract-ocr" in dockerfile
