"""Local-only, bounded OCR and deterministic field extraction for LEXA documents.

No external model or network is used. Extracted values are candidates, never facts
until a human confirms them against the original document.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 12_000
MAX_RENDERED_PDF_PAGES = 3
ALLOWED_MIME_TYPES = frozenset({"application/pdf", "image/jpeg", "image/png", "image/webp"})
DOCUMENT_TYPES = frozenset({"SUPPLIER_INVOICE", "EXPENSE_RECEIPT", "CUSTOMER_INVOICE", "PURCHASE_ORDER", "OTHER"})
FIELD_LABELS: dict[str, tuple[str, ...]] = {
    "supplier_name": ("supplier", "vendor", "seller", "issued by"),
    "customer_name": ("customer", "bill to", "buyer", "client"),
    "invoice_number": ("invoice number", "invoice no", "invoice #", "tax invoice no", "document number"),
    "receipt_number": ("receipt number", "receipt no", "receipt #", "receipt reference"),
    "purchase_order_number": ("purchase order number", "purchase order no", "po number", "po no"),
    "invoice_date": ("invoice date", "date issued", "date of issue", "receipt date"),
    "due_date": ("due date", "payment due"),
    "subtotal": ("subtotal", "sub-total", "net amount", "amount before tax"),
    "tax_amount": ("vat amount", "tax amount", "vat", "total vat"),
    "total": ("grand total", "total due", "amount due", "invoice total", "total payable", "total"),
    "tax_id": ("tax identification number", "tin", "tax id"),
}
_DATE_RE = re.compile(r"(?<!\d)(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})(?!\d)")
_AMOUNT_RE = re.compile(r"(?<![A-Za-z0-9])(?:UGX|USD|KES|TZS|RWF|EUR|GBP)?\s*([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,4})?)(?!\d)", re.IGNORECASE)
_CURRENCY_RE = re.compile(r"\b(UGX|USD|KES|TZS|RWF|EUR|GBP)\b", re.IGNORECASE)
_TIN_RE = re.compile(r"\b(?:TIN|TAX\s*(?:ID|IDENTIFICATION\s*NUMBER))\s*[:#-]?\s*([A-Z0-9-]{6,24})\b", re.IGNORECASE)


def _clean_text(value: str) -> str:
    value = value.replace("\x00", " ")
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()[:MAX_TEXT_CHARS]


def _normalize_date(value: str) -> str | None:
    value = value.strip()
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if match:
        y, m, d = map(int, match.groups())
    else:
        match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", value)
        if match:
            # Uganda-oriented interpretation: day/month/year, not US month/day/year.
            d, m, y = map(int, match.groups())
            if y < 100:
                y += 2000 if y < 70 else 1900
        else:
            match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})", value)
            if not match:
                return None
            d, month_name, y = match.groups()
            month_index = {name.lower(): i for i, name in enumerate(
                ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1
            )}
            m = month_index.get(month_name[:3].lower(), 0)
            d, y = int(d), int(y)
    try:
        from datetime import date
        return date(y, m, d).isoformat()
    except (ValueError, TypeError):
        return None


def _field(value: str | None, confidence: float, evidence: str | None) -> dict[str, Any]:
    return {"value": value, "confidence": confidence if value is not None else 0.0, "evidence": evidence[:220] if evidence else None}


def parse_document_fields(text: str, document_type: str) -> dict[str, Any]:
    """Extract only labelled, reviewable candidate fields from supplied text."""
    doc_type = str(document_type).strip().upper()
    if doc_type not in DOCUMENT_TYPES:
        raise ValueError("Unsupported document type")
    clean = _clean_text(text)
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    fields: dict[str, dict[str, Any]] = {}

    for key, aliases in FIELD_LABELS.items():
        selected: tuple[str, str] | None = None
        # Match the longest explicit label first. Require a label boundary to avoid
        # interpreting unrelated words (e.g. 'Total' inside 'Subtotal') as a match.
        aliases_ordered = sorted(aliases, key=len, reverse=True)
        for line in lines:
            for alias in aliases_ordered:
                pattern = rf"(?i)(?<![A-Za-z]){re.escape(alias)}(?![A-Za-z])\s*(?:[:#=\-])?\s*(.*)$"
                match = re.search(pattern, line)
                if not match:
                    continue
                if key == "total" and re.search(r"(?i)sub\s*-?\s*total", line):
                    continue
                raw = match.group(1).strip(" :-#=")
                if key in {"invoice_date", "due_date"}:
                    date_match = _DATE_RE.search(raw) or _DATE_RE.search(line)
                    normalized = _normalize_date(date_match.group(1)) if date_match else None
                    if normalized:
                        selected = (normalized, line)
                elif key in {"subtotal", "tax_amount", "total"}:
                    amount_match = _AMOUNT_RE.search(raw)
                    # The value may follow a currency marker before the label or
                    # appear after a label with no colon (e.g. 'VAT 18,000').
                    if not amount_match:
                        amount_match = _AMOUNT_RE.search(line[match.end():])
                    if amount_match:
                        number = amount_match.group(1).replace(",", "")
                        try:
                            from decimal import Decimal
                            normalized = format(Decimal(number).quantize(Decimal("0.01")), "f")
                            if Decimal(normalized) >= 0:
                                selected = (normalized, line)
                        except Exception:
                            pass
                elif key == "tax_id":
                    tin_match = _TIN_RE.search(line)
                    if tin_match:
                        selected = (tin_match.group(1).strip(), line)
                elif raw:
                    # Remove trailing unrelated OCR noise without inventing text.
                    normalized = re.split(r"\s{2,}|\s\|\s", raw, maxsplit=1)[0].strip()[:180]
                    if normalized and normalized.lower() not in {"n/a", "na", "none", "-"}:
                        selected = (normalized, line)
                if selected:
                    break
            if selected:
                break
        fields[key] = _field(selected[0], 0.92, selected[1]) if selected else _field(None, 0.0, None)

    currency_match = _CURRENCY_RE.search(clean)
    fields["currency_code"] = _field(currency_match.group(1).upper(), 0.95, currency_match.group(0)) if currency_match else _field(None, 0.0, None)
    warnings = [
        "Every extracted value is a candidate. Check it against the original document before confirming.",
        "Supplier and customer names are not linked to LEXA parties automatically.",
        "LEXA has not created or posted an invoice, expense, payment, purchase order, or journal entry.",
    ]
    if not clean:
        warnings.insert(0, "No readable text was extracted. Enter details manually after reviewing the original file.")
    return {
        "schema_version": "phase3.document_candidate.v1",
        "document_type": doc_type,
        "fields": fields,
        "warnings": warnings,
        "text_character_count": len(clean),
    }


def _run(command: list[str], *, input_bytes: bytes | None = None, timeout: int = 8) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
        shell=False,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
    )


def _ocr_image(path: Path) -> tuple[str, str]:
    result = _run(["tesseract", str(path), "stdout", "-l", "eng", "--psm", "6"], timeout=8)
    if result.returncode != 0:
        return "", "UNAVAILABLE"
    return _clean_text(result.stdout.decode("utf-8", "replace")), "TESSERACT_OCR"


def _validate_file_signature(content: bytes, mime: str) -> None:
    """Reject mismatched MIME headers before handing bytes to native parsers."""
    valid = False
    if mime == "application/pdf":
        valid = content.lstrip().startswith(b"%PDF-")
    elif mime == "image/jpeg":
        valid = content.startswith(b"\xff\xd8\xff")
    elif mime == "image/png":
        valid = content.startswith(b"\x89PNG\r\n\x1a\n")
    elif mime == "image/webp":
        valid = len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    if not valid:
        raise ValueError("The file contents do not match the selected file type")


def extract_document(content: bytes, content_type: str, document_type: str) -> dict[str, Any]:
    """Run bounded local PDF text extraction/OCR and return candidate metadata.

    Missing OCR binaries, unreadable files, or timeouts degrade to manual review; an
    upload remains stored and is never represented as a verified business record.
    """
    mime = content_type.split(";", 1)[0].strip().lower()
    if mime not in ALLOWED_MIME_TYPES:
        raise ValueError("Unsupported file type")
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValueError("File is empty or exceeds the configured size limit")
    if str(document_type).strip().upper() not in DOCUMENT_TYPES:
        raise ValueError("Unsupported document type")
    _validate_file_signature(content, mime)
    output_text = ""
    method = "UNAVAILABLE"
    timed_out = False
    try:
        with tempfile.TemporaryDirectory(prefix="lexa-doc-") as temp:
            root = Path(temp)
            if mime == "application/pdf":
                pdf_path = root / "document.pdf"
                pdf_path.write_bytes(content)
                try:
                    text_result = _run(["pdftotext", "-layout", str(pdf_path), "-"], timeout=8)
                    if text_result.returncode == 0:
                        output_text = _clean_text(text_result.stdout.decode("utf-8", "replace"))
                        if output_text:
                            method = "PDF_TEXT_LAYER"
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    timed_out = True
                if not output_text:
                    try:
                        prefix = root / "page"
                        rendered = _run(["pdftoppm", "-f", "1", "-l", str(MAX_RENDERED_PDF_PAGES), "-r", "120", "-png", str(pdf_path), str(prefix)], timeout=10)
                        if rendered.returncode == 0:
                            pieces: list[str] = []
                            for page in sorted(root.glob("page-*.png"))[:MAX_RENDERED_PDF_PAGES]:
                                text_piece, _ = _ocr_image(page)
                                if text_piece:
                                    pieces.append(text_piece)
                            output_text = _clean_text("\n".join(pieces))
                            if output_text:
                                method = "PDF_RENDERED_OCR"
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        timed_out = True
            else:
                suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[mime]
                image_path = root / ("document" + suffix)
                image_path.write_bytes(content)
                try:
                    output_text, method = _ocr_image(image_path)
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    timed_out = True
                    output_text, method = "", "UNAVAILABLE"
    except OSError:
        output_text, method = "", "UNAVAILABLE"

    candidate = parse_document_fields(output_text, document_type)
    extraction_status = "SUCCEEDED" if output_text else ("UNAVAILABLE" if method == "UNAVAILABLE" else "PARTIAL")
    if timed_out and not output_text:
        candidate["warnings"].insert(0, "Local text extraction reached its time limit. Review the document manually.")
    return {
        "extracted_text": output_text,
        "candidate_fields": candidate,
        "extraction_method": method,
        "extraction_status": extraction_status,
    }
