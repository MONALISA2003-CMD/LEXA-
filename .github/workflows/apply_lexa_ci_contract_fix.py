#!/usr/bin/env python3
"""Apply the verified LEXA CI contract-test corrections to a repository checkout.

Run from any directory:
  python /path/to/apply_lexa_ci_contract_fix.py /path/to/LEXA-

The script is deliberately fail-closed: every expected old assertion must occur
exactly once before any files are written.
"""
from pathlib import Path
import sys

PATCHES = {
    "apps/web/tests/phase1-ux-contract.test.mjs": [
        ('assert.match(navigation, /Business settings/);',
         'assert.match(navigation, /Business details/);'),
    ],
    "apps/web/tests/phase3-document-intelligence.test.mjs": [
        ('assert.match(page, /Guidance that fits your business/);',
         'assert.match(page, /Guidance for your business/);'),
        ('assert.match(page, /AI responses are temporarily paused/);',
         'assert.match(page, /The assistant isn’t available right now/);'),
        ('assert.match(page, /Your question will not be sent to a provider/);',
         'assert.match(page, /will not generate or pretend to generate an answer while the assistant is unavailable/);'),
        ('assert.match(page, /executionAvailable &&/);',
         r'assert.doesNotMatch(page, /fetch\(|<textarea|executionAvailable &&/);'),
        ('assert.match(page, /Information that needs a refresh/);',
         'assert.match(page, /Information to check or update/);'),
        ('assert.match(page, /Missing data is never presented as zero/);',
         'assert.match(page, /Missing information is never treated as zero/);'),
    ],
    "apps/web/tests/phase4-demand-forecast.test.mjs": [
        (r'assert.match(nav, /\["\/demand-forecast", "Demand forecast", "chart"\]/);',
         r'assert.match(nav, /\["\/demand-forecast", "Sales forecast", "chart"\]/);'),
        ('assert.match(nav, /Product demand forecast/);',
         'assert.match(nav, /Expected demand and sales forecast/);'),
    ],
    "apps/web/tests/phase8-foundation-polish.test.mjs": [
        ('for (const label of ["Home", "Sales", "Stock", "Products", "Customers", "Purchases", "Finance", "Reports"])',
         'for (const label of ["Home", "Sales", "Stock", "Products", "Customers", "Purchases", "Money & records", "Reports"])'),
    ],
    "apps/web/tests/visible-product-contract.test.mjs": [
        ('assert.match(navigation, /Business settings/);',
         'assert.match(navigation, /Business details/);'),
    ],
    "apps/api/tests/test_intelligence_phase3.py": [
        ('    assert "executionAvailable &&" in ai_ui\n'
         '    assert "Your question will not be sent to a provider" in ai_ui',
         '    assert "The assistant isn’t available right now." in ai_ui\n'
         '    assert "will not generate or pretend to generate an answer while the assistant is unavailable" in ai_ui\n'
         '    assert "fetch(" not in ai_ui\n'
         '    assert "<textarea" not in ai_ui'),
    ],
}

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python apply_lexa_ci_contract_fix.py /path/to/LEXA-")
    root = Path(sys.argv[1]).resolve()
    prepared = {}
    for rel, replacements in PATCHES.items():
        path = root / rel
        if not path.is_file():
            raise SystemExit(f"ABORT: expected file is missing: {rel}")
        original = path.read_text(encoding="utf-8")
        updated = original
        for old, new in replacements:
            count = updated.count(old)
            if count != 1:
                raise SystemExit(
                    f"ABORT: {rel}: expected one occurrence, found {count}: {old[:100]!r}"
                )
            updated = updated.replace(old, new, 1)
        prepared[path] = updated

    # Only write after every target file and every old assertion has validated.
    for path, content in prepared.items():
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"UPDATED {path.relative_to(root)}")
    print(f"PASS: updated {len(prepared)} files; no application UI or runtime code changed.")
    print("Next: run apps/web `npm test`, `npm run typecheck`, `npm run build`,")
    print("and apps/api `python -m pytest tests -q`.")

if __name__ == "__main__":
    main()
