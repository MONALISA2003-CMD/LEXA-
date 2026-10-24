#!/usr/bin/env python3
"""Apply LEXA's approved, customer-facing business-English wording to the frontend.

This intentionally changes visible copy only. It does not rename code symbols,
change API contracts, modify business rules, alter permissions, or touch the database.
It is idempotent and reports every file and phrase it changes.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

# Pairs are literal customer-facing phrases, not identifiers or data contracts.
# A phrase may already have been updated by an earlier accepted overlay; in that
# case it is left alone. The same phrase is intentionally used consistently.
RULES: dict[str, list[tuple[str, str]]] = {
    "apps/web/app/ai-assistant/page.tsx": [
        ("Guidance for your business.", "Guidance that fits your business."),
        ("The assistant isn’t available right now.", "The business assistant isn’t available right now."),
        ("TEMPORARILY UNAVAILABLE", "NOT AVAILABLE RIGHT NOW"),
        ("LEXA · BUSINESS SUPPORT", "LEXA · BUSINESS GUIDANCE"),
        ("BUSINESS SUPPORT", "BUSINESS GUIDANCE"),
        ("6 useful places", "6 useful areas"),
        ("A clear place to start when you need to make sense of sales, stock, customers or day-to-day spending.", "A clear place to start when you need help understanding sales, stock, customers or daily spending."),
        ("This page will not prepare an answer or change your business records.", "The assistant will not answer questions or change your business records while it is unavailable."),
        ("will not prepare an answer or change your business records", "will not answer questions or change your business records while it is unavailable"),
        ("Check the record before retrying", "Check the record before trying again"),
        ("You can still use the tools below to review your business information. This page will not generate or pretend to generate an answer while the assistant is unavailable.", "You can still use the business tools below to check your records and decide what to do next. The business assistant will not answer questions or change your business records while it is unavailable."),
        ("BUSINESS SUPPORT", "BUSINESS GUIDANCE"),
        ("LEXA · BUSINESS SUPPORT", "LEXA · BUSINESS GUIDANCE"),
        ("TOOLS YOU CAN USE NOW", "BUSINESS TOOLS YOU CAN USE NOW"),
        ("Review recent sales and see how your business is performing.", "Check recent sales and payments to see how your business is doing."),
        ("See what is available and which products may need attention.", "Check what is in stock and which products may need restocking."),
        ("Review business totals and compare activity over time.", "Compare sales, costs and other business figures over time."),
        ("Review suppliers, orders and deliveries before making a decision.", "Check supplier orders and deliveries before deciding what to buy."),
        ("Review customer records, payments and amounts still due.", "Check customer details, payments and any money customers still owe."),
        ("Review invoices, receipts and other documents before using their details.", "Check invoices and receipts before using the details they contain."),
        ("Keep passwords, payment credentials and private customer details out of messages or notes. Check important figures against the original business records before acting.", "Keep passwords and private customer details safe. Check important amounts against the original records before making a decision."),
    ],
    "apps/web/app/page.tsx": [
        ("TODAY'S WORK", "TODAY'S PRIORITIES"),
        ("Other business signals", "Other changes to review"),
        ("Business indicators", "Business overview"),
        ("No records found", "No records found for this period"),
        ("Your business is unavailable", "Your business information is not available right now"),
    ],
    "apps/web/app/accounting/page.tsx": [
        ('POSTED: "Included in records"', 'POSTED: "Recorded"'),
        ('VOIDED: "Cancelled before recording"', 'VOIDED: "Cancelled before it was recorded"'),
        ('RECONCILIATION_PENDING: "Amounts still needed"', 'RECONCILIATION_PENDING: "Waiting for amounts to be checked"'),
        ('VARIANCE_DETECTED: "Difference to review"', 'VARIANCE_DETECTED: "Difference to check"'),
        ('UNDER_REVIEW: "Being reviewed"', 'UNDER_REVIEW: "Under review"'),
        ("End-of-day check", "End-of-day payment check"),
        ("Your business currency is not set", "Your business currency has not been set"),
        ("Amounts still needed", "Waiting for amounts to be checked"),
        ("Reconciliation variance", "Difference between recorded and actual amounts"),
        ("reconciliation variance", "difference between recorded and actual amounts"),
    ],
    "apps/web/app/administration/page.tsx": [
        ('title="Business settings"', 'title="Business details"'),
        ('eyebrow="WORKSPACE SETTINGS"', 'eyebrow="BUSINESS DETAILS"'),
        ('"Currency code"', '"Business currency"'),
        ('"Country code"', '"Country"'),
        ('"Warehouse name"', '"Storage area name"'),
        ("Configure the business profile, branches, warehouses and stock locations for the selected workspace.", "Update your business details, branches, storage areas and stock locations here."),
        ('"Loading settings"', '"Loading business details"'),
        ('"Some settings unavailable"', '"Some business details unavailable"'),
        ('"Workspace settings loaded"', '"Business details loaded"'),
        ("No branches were returned for this workspace.", "No branches are set up for this business yet."),
        ("Some business settings could not be loaded.", "Some business details could not be loaded."),
        ("Stock location created.", "Stock location added."),
        ("selected workspace", "selected business"),
        ("workspace settings", "business details"),
        ("Configure the business profile", "Update your business details"),
    ],
    "apps/web/app/administration/members/page.tsx": [
        ('>Roles<', '>Access levels<'),
        ('>Permissions<', '>What team members can do<'),
        ('>Workspace members<', '>Business team members<'),
        ('"Role name"', '"Access level name"'),
        ("Membership status could not be changed.", "This team member's access could not be changed."),
        ("Role permissions could not be saved.", "The changes to what this role can do could not be saved."),
        ("Role assignments could not be saved.", "Team access changes could not be saved."),
        ("Branch assignments could not be saved.", "Branch access changes could not be saved."),
        ("Team access could not be loaded.", "Team members and their access could not be loaded."),
        ("Assign only the permissions this role needs.", "Give this role only the access it needs."),
        ("Create role", "Add access level"),
        ("Role description", "What this access level is for"),
        ("Manage roles and permissions", "Choose what each team member can do"),
        ("Permissions", "What they can do"),
        ("Workspace members", "Business team members"),
    ],
    "apps/web/app/commerce/page.tsx": [
        ('VARIANCE_DETECTED: "Difference to review"', 'VARIANCE_DETECTED: "Difference to check"'),
        ('PARTIALLY_PAID: "Partly paid"', 'PARTIALLY_PAID: "Part-paid"'),
        ("Business currency could not be confirmed.", "LEXA could not confirm your business currency."),
        ("End-of-day check", "End-of-day payment check"),
        ("Customer balances", "Customer balances and amounts due"),
        ("Past sales", "Past sales and payments"),
    ],
    "apps/web/app/compliance/page.tsx": [
        ('title="Tax and compliance"', 'title="Tax and receipts"'),
        ('"EFRIS setup"', '"URA EFRIS tax invoicing setup"'),
        ("EFRIS details saved. Registration status still depends on a verified URA workflow.", "EFRIS details saved. This does not confirm that URA registration or tax invoicing is active."),
        ("No official fiscal documents have been recorded yet", "No official tax documents have been recorded yet"),
        ("Official fiscal documents", "Official tax documents"),
        ("Fiscal documents", "Official tax documents"),
        ("fiscal document", "official tax document"),
        ("fiscal documents", "official tax documents"),
        ("Tax rate end date cannot be before its start date.", "The tax rate end date must be on or after its start date."),
        ("Tax rule end date cannot be before its start date.", "The tax rule end date must be on or after its start date."),
    ],
    "apps/web/app/customers/page.tsx": [
        ("This customer's sales history could not be loaded.", "LEXA could not load this customer's past sales."),
        ("Customer balances could not be loaded.", "Amounts customers still owe could not be loaded."),
        ("Customer details could not be loaded.", "Customer information could not be loaded."),
        ("Sales history", "Past sales"),
        ("Business trends and insights", "Business insights"),
        ("credit limit", "maximum amount this customer can owe"),
    ],
    "apps/web/app/daily-brief/page.tsx": [
        ("BUSINESS INDICATORS", "BUSINESS UPDATES"),
        ("INFORMATION QUALITY", "INFORMATION TO CHECK"),
        ("Information to check or update", "Information to check"),
        ("Other useful signals", "Other useful business updates"),
        ("SEVEN-DAY VIEW", "LAST 7 DAYS"),
        ("Checks completed", "Checks made"),
        ("This overview is based on the business records available to LEXA.", "This overview uses the business records LEXA could check."),
        ("These are prompts for your team to review—not automated transactions.", "These are suggestions to review. They do not make changes to your records."),
        ("No outdated or unavailable information was reported.", "No missing or out-of-date information was found in the records checked."),
        ("Missing information is never treated as zero.", "Missing information is not counted as zero."),
    ],
    "apps/web/app/demand-forecast/page.tsx": [
        ('title="Demand forecast"', 'title="Sales forecast"'),
        ("A transparent weekday-seasonal baseline, checked against a rolling 14-day holdout of historical sales.", "An estimate based on recent sales patterns, checked against recent recorded sales."),
        ("Daily forecast and historical range", "Daily sales estimate and past range"),
        ("Business writes performed: no", "No stock or purchase records are changed"),
        ("Mean absolute error", "Average forecast error"),
        ("rolling-origin holdout", "check against recent sales"),
        ("rolling-origin", "recent-sales check"),
        ("rolling 14-day holdout", "check against recent sales"),
        ("Historical same-weekday range", "Past range for the same day of the week"),
        ("Forecast units", "Estimated units to sell"),
        ("History verified", "Sales history checked"),
        ("Eligible variants", "Products with enough sales history"),
        ("LEXA · PREDICTIVE INTELLIGENCE", "LEXA · SALES PLANNING"),
        ("Predictive intelligence", "Sales planning"),
        ("14-DAY BASELINE", "14-DAY SALES ESTIMATE"),
        ("Product demand forecasts", "Estimated product sales"),
        ("Items not forecast", "Products without a reliable estimate"),
        ("DATA QUALITY", "INFORMATION TO CHECK"),
        ("Planning evidence only", "For planning only"),
        ("WAPE", "Forecast error compared with actual sales"),
        ("Forecast stock demand", "Estimate what you may need to restock"),
        ("The historical range is not a calibrated confidence interval.", "The past sales range is only a guide, not a guarantee."),
        ("This forecast", "This sales estimate"),
        ("demand forecast", "sales estimate"),
        ("Demand forecast", "Sales forecast"),
    ],
    "apps/web/app/documents/page.tsx": [
        ('eyebrow="LEXA intelligence"', 'eyebrow="BUSINESS DOCUMENTS"'),
        ("No value was extracted. Enter it after checking the original document.", "No detail was found. Check the original document before entering it."),
        ("No supporting text was detected. Check the original document.", "LEXA could not find supporting text for this detail. Check the original document."),
        ("Read from:", "Found in the document:"),
        ("Candidate fields", "Details found in the document"),
        ("Extraction method", "How the document was read"),
        ("Document extraction", "Reading document details"),
        ("branch-scoped store", "business branch records"),
        ("This file is already saved in this branch. The existing review was opened.", "This file is already saved for this branch. The existing review is open."),
        ("Document saved. Check each extracted field against the original before confirming.", "Document saved. Check every detail against the original before confirming."),
        ("No supporting text was detected", "No supporting words were found"),
    ],
    "apps/web/app/intelligence/page.tsx": [
        ("Data quality", "Information to check"),
        ("Business intelligence", "Business insights"),
        ("PREDICTIVE INTELLIGENCE", "BUSINESS INSIGHTS"),
        ("Business intelligence", "Business insights"),
        ("Business indicators", "Business updates"),
        ("Supported now: sales movement, gross margin, stock risk, current receivables and supplier balances. Answers use local rules and saved metrics; this question is not sent to an AI provider.", "You can ask about changes in sales, gross margin, stock risks, amounts customers owe and amounts you owe suppliers. Answers use saved business figures. Your question is not sent to an outside service."),
        ("Answer unavailable", "We could not check the answer"),
        ("LEXA could not verify the saved insight data just now.", "LEXA could not check the saved business figures just now."),
        ("information freshness", "when the information was last updated"),
        ("deterministic", "based on clear business rules"),
        ("Data quality", "Information to check"),
    ],
    "apps/web/app/inventory/page.tsx": [
        ('"Stock Health": "Stock checks"', '"Stock Health": "Stock checks"'),
        ('"Stock Age": "Age of stock"', '"Stock Age": "How long stock has been stored"'),
        ('"Stock Age": "Stock age"', '"Stock Age": "How long stock has been stored"'),
        ('"Ledger": "Stock history"', '"Ledger": "Stock history"'),
        ('"Replenishment": "Restock suggestions"', '"Replenishment": "Restock suggestions"'),
        ("No net demand in lookback", "No sales after returns in this period"),
        ("AT_OR_BELOW_CONFIGURED_MINIMUM: " + '"At or below minimum"', "AT_OR_BELOW_CONFIGURED_MINIMUM: " + '"At or below the minimum level"'),
        ("Inventory unavailable", "Stock information is not available right now"),
        ("Unable to load inventory.", "LEXA could not load stock information. Check your connection and try again."),
        ("stock ledger", "stock history"),
        ("inventory ageing", "how long stock has been in storage"),
    ],
    "apps/web/app/products/page.tsx": [
        ('>Catalog<', '>Products<'),
        ('"Catalog"', '"Products"'),
        ('>Variants<', '>Product options<'),
        ('>SKU<', '>Product code<'),
        ("pack sizes, product codes, barcodes and prices", "product options, product codes, barcodes and prices"),
        ("Unable to load the product products.", "LEXA could not load products. Check your connection and try again."),
        ("Products reference data could not be loaded.", "Product lists could not be loaded. Try again."),
        ("Could not create the product.", "The product could not be added. Check the details and try again."),
        ("Could not save this pack size or option.", "This product option could not be saved. Check the details and try again."),
        ("Could not update this pack size or option.", "This product option could not be updated. Try again."),
        ("Could not create the barcode.", "The barcode could not be added. Check the details and try again."),
        ("Could not create the price list.", "The price list could not be added. Check the details and try again."),
        ("Could not create the price.", "The price could not be added. Check the details and try again."),
    ],
    "apps/web/app/purchasing/page.tsx": [
        ('"VARIANCE": "Needs review"', '"VARIANCE": "Difference to check"'),
        ('VARIANCE: "Needs review"', 'VARIANCE: "Difference to check"'),
        ('"NOT_LINKED": "No delivery linked"', '"NOT_LINKED": "No delivery recorded"'),
        ('"Supplier return credit"', '"Credit for returned goods"'),
        ('"Supplier balance change"', '"Supplier balance update"'),
        ("Supplier balances", "Supplier balances and amounts due"),
        ("Bills & payments", "Supplier bills and payments"),
        ('"Receiving"', '"Record deliveries"'),
        ("Overdue", "Past due date"),
        ("Supplier bill corrected", "Supplier bill correction recorded"),
        ("Supplier payment corrected", "Supplier payment correction recorded"),
    ],
    "apps/web/app/reports/page.tsx": [
        ("Data quality", "Information to check"),
        ("Report panel", "report section"),
        ("report panel", "report section"),
        ("This report could not be loaded. Check your access or try again.", "This report could not be loaded. Check that you have access, then try again."),
        ("Reports could not be refreshed for these dates. Try again.", "The reports for these dates could not be updated. Try again."),
        ("Receipts after refunds and expenses", "Money received after refunds and expenses"),
        ("Business performance metrics", "Business performance figures"),
        ("Stock value by location", "Value of stock at each location"),
        ("Customer balance", "Customer amounts due"),
        ("Supplier balance", "Supplier amounts due"),
    ],
    "apps/web/app/settings/page.tsx": [
        ("Manage business settings", "Manage your business details"),
        ("These details help LEXA present your business consistently across sales, stock and reports.", "These details help LEXA show your business name and currency correctly in sales, stock and reports."),
        ("Business setup", "Finish business setup"),
        ("Review your branches, stock locations and required setup.", "Check your branches, stock locations and any details still needed."),
        ("Your business details could not be loaded.", "LEXA could not load your business details."),
        ("Your details were not saved.", "Your business details were not saved."),
    ],
    "apps/web/app/settings/security/page.tsx": [
        ("active sessions connected to your current business workspace", "devices and browsers currently signed in to your business"),
        ("No active sessions found", "No other sign-ins were found"),
        ("That session could not be revoked.", "That sign-in could not be ended."),
        ("Revoke session", "Sign out this device"),
        ("Active sessions", "Devices signed in"),
    ],
    "apps/web/app/team-chat/page.tsx": [
        ("Start your first team thread", "Start your first team conversation"),
        ("Team conversations could not be loaded.", "Team conversations could not be loaded. Refresh to try again."),
        ("The conversation could not be created.", "The conversation could not be started. Check the details and try again."),
        ("The message was not confirmed.", "LEXA could not confirm that the message was sent."),
        ("LEXA · COLLABORATION", "LEXA · TEAM CHAT"),
    ],
    "apps/web/app/onboarding/page.tsx": [
        ("Check your business details, stock location, payment method and basic money records", "Check your business details, stock location, payment method and money records"),
        ("Setup progress could not be verified.", "LEXA could not check your setup progress. Try again."),
        ("We couldn't finish setting up your business.", "Your business setup could not be completed. Check the details and try again."),
        ("Set up missing details", "Add the details that are still needed"),
        ("Checking your business setup…", "Checking that your business is ready…"),
    ],
    "apps/web/app/login/page.tsx": [
        ("This account is not linked to an active business. Ask the business owner for help.", "This account is not linked to an active business. Ask the business owner to help you."),
        ("We could not sign you in. Check your details and try again.", "We couldn't sign you in. Check your email and password, then try again."),
        ("Choose which business to open.", "Choose which business you want to open."),
    ],
    "apps/web/app/register/page.tsx": [
        ("Starting operating location", "First business location"),
        ("Branch, warehouse and stock location are created together with your business.", "Your first branch and stock location will be set up with your business."),
        ("You can update these details later", "You can change these details later"),
        ("Your sales and stock records start empty", "Your sales and stock records will start empty"),
        ("Keep access details private. LEXA staff will never ask for your password.", "Keep your sign-in details private. LEXA staff will never ask for your password."),
    ],
    "apps/web/app/invite/page.tsx": [
        ("This invitation link is missing its token. Ask the workspace owner to issue a new link.", "This invitation link is incomplete. Ask the business owner to send a new link."),
        ("The invitation could not be accepted.", "LEXA could not accept this invitation. Check the link and try again."),
        ("Back to sign in", "Return to sign in"),
        ("workspace owner", "business owner"),
    ],
    "apps/web/app/forgot-password/page.tsx": [
        ("Password reset email is temporarily unavailable. Please contact LEXA support or your business administrator.", "Password reset email is not available right now. Contact your business owner or LEXA support for help."),
        ("We couldn't submit the request. Please try again.", "We couldn't send the request. Please try again."),
    ],
    "apps/web/app/reset-password/page.tsx": [
        ("Could not reset password", "Password not changed"),
        ("This reset link is missing or has expired.", "This password reset link is missing or has expired."),
        ("Your password could not be reset.", "Your password was not changed."),
        ("Open the most recent reset link from your email, or request a new one below.", "Open the latest password reset link in your email, or request a new one below."),
    ],
    "apps/web/app/workspace/page.tsx": [
        ("Choose a workspace", "Choose a business"),
        ("Switch workspace", "Switch business"),
        ("Your workspaces", "Your businesses"),
        ("workspace owner", "business owner"),
        ("Could not load your workspaces.", "LEXA could not load the businesses linked to your account."),
        ("LEXA could not switch workspaces.", "LEXA could not switch to that business. Try again."),
        ("No business is available yet", "No business is linked to your account yet"),
        ("Loading your businesses…", "Loading your businesses…"),
    ],
    "apps/web/components/app-shell.tsx": [
        ('<b>Business settings</b>', '<b>Business details</b>'),
        ('aria-label="Open business settings"', 'aria-label="Open business details"'),
        ('aria-label={open ? "Close business settings" : "Open business settings"}', 'aria-label={open ? "Close business details" : "Open business details"}'),
        ("Checking that everything is ready", "Checking that your business is ready"),
        ("Could not check business status", "Could not check your business status"),
        ("Could not open your business", "Could not open your business information"),
        ("current business workspace", "current business"),
        ("workspace permissions", "team access"),
        ("workspace-wide", "across the business"),
        ("Let's get your business ready", "Let's get your business ready"),
    ],
    "apps/web/components/ui.tsx": [
        ('title: "Loading your data"', 'title: "Loading your business information"'),
        ('description: "We are checking the latest information from LEXA."', 'description: "We are checking your latest business information."'),
        ('title: "Nothing here yet"', 'title: "No records yet"'),
        ('description: "When a record is created, it will appear here."', 'description: "Records will appear here after you add them."'),
        ('title: "We could not load this data"', 'title: "We could not load this information"'),
        ('title: "You do not have access"', 'title: "You cannot open this area"'),
        ('description: "Ask the business owner or manager to check your access for this task."', 'description: "Ask the business owner or manager to give you access to this task."'),
        ('title: "LEXA is temporarily unavailable"', 'title: "LEXA is not available right now"'),
        ('description: "Check your connection and retry. We will not treat missing data as zero."', 'description: "Check your internet connection and try again. Missing information will not be shown as zero."'),
    ],
    "apps/web/lib/navigation.mjs": [
        ('["/demand-forecast", "Demand forecast", "chart"]', '["/demand-forecast", "Sales forecast", "chart"]'),
        ('["Expected demand and sales forecast", "/demand-forecast"]', '["Sales estimates and restock planning", "/demand-forecast"]'),
        ('["Business trends and insights", "/intelligence"]', '["Business insights", "/intelligence"]'),
        ('"Business settings"', '"Business details"'),
        ('"Expected demand and sales forecast"', '"Sales estimates and restock planning"'),
        ('"Predictive intelligence"', '"Sales planning"'),
        ('"inventory", "warehouse", "transfer", "count", "adjustment", "low stock"', '"stock", "storage", "transfer", "count", "adjustment", "low stock"'),
    ],
    "apps/web/lib/api.ts": [
        ("We couldn't find that item. It may have been removed or may not be available to your business.", "We couldn't find that item. It may have been removed or may not be available to your business."),
        ("LEXA couldn't complete the request right now. Your change may not have been saved. Check the record before retrying.", "LEXA couldn't complete that action right now. Your change may not have been saved. Check the record before trying again."),
        ("We couldn't complete that action. Review the information and try again.", "We couldn't complete that action. Check the details and try again."),
        ("We couldn't connect to LEXA right now. Check your connection and try again.", "We couldn't connect to LEXA right now. Check your internet connection and try again."),
    ],
    "apps/web/lib/daily-brief-api.ts": [
        ("Check your business details and try again.", "Check your business details and try again."),
        ("saved rows", "saved records"),
    ],
    "apps/web/lib/demand-forecast-api.ts": [
        ("Choose a forecast window from 7 to 28 days.", "Choose an estimate period between 7 and 28 days."),
        ("LEXA could not verify the demand forecast. Check analytics freshness and try again.", "LEXA could not prepare a sales estimate. Check that recent sales records are up to date, then try again."),
        ("forecast window", "estimate period"),
        ("analytics freshness", "whether recent sales records are up to date"),
    ],
    "apps/web/lib/document-intelligence-api.ts": [
        ("LEXA could not read this document. Check the file and try again.", "LEXA could not read this document. Check that the file is clear and try again."),
        ("This document could not be saved yet. Refresh the list and try again.", "This document has not been saved. Refresh the list and try again."),
        ("One or more details cannot be reviewed here. Check the document and try again.", "One or more details cannot be checked here. Compare them with the original document and try again."),
        ("Choose a PDF, JPG, PNG or WebP file.", "Choose a PDF, JPG or PNG image."),
    ],
    "apps/web/tests/phase1-ux-contract.test.mjs": [
        ("/Business settings/", "/Business details/"),
        ("/Checking that everything is ready/", "/Checking that your business is ready/"),
        ("/No official fiscal documents have been recorded yet/", "/No official tax documents have been recorded yet/"),
    ],
    "apps/web/tests/phase8-foundation-polish.test.mjs": [
        ('"Finance"', '"Money & records"'),
        ("/Checking that everything is ready/", "/Checking that your business is ready/"),
        ("/Set up missing details/", "/Add the details that are still needed/"),
        ('"Demand forecast"', '"Sales forecast"'),
    ],
    "apps/web/tests/visible-product-contract.test.mjs": [
        ("/Business settings/", "/Business details/"),
        ("/TODAY'S WORK/", "/TODAY'S PRIORITIES/"),
        ("/Variants/", "/product options/i"),
    ],
    "apps/web/tests/phase4-demand-forecast.test.mjs": [
        (r'\["/demand-forecast", "Demand forecast", "chart"\]', r'\["/demand-forecast", "Sales forecast", "chart"\]'),
        ("/Planning evidence only/", "/For planning only/"),
        ("assert.match(page, /rolling-origin/);", "assert.doesNotMatch(page, /rolling-origin/);"),
        ("/WAPE/", "/Forecast error compared with actual sales/"),
        ("/Expected demand and sales forecast/", "/Sales estimates and restock planning/"),
        ("/Business writes performed: no/", "/No stock or purchase records are changed/"),
        ("Planning evidence only", "For planning only"),
        ("WAPE", "Forecast error compared with actual sales"),
    ],
    "apps/web/tests/phase3-document-intelligence.test.mjs": [
        ("/Information that needs a refresh/", "/Information to check/"),
        ("/Information to check or update/", "/Information to check/"),
        ("/Missing information is never treated as zero/", "/Missing information is not counted as zero/"),
        ("/AI responses are temporarily paused/", "/The business assistant isn’t available right now/"),
        ("/Your question will not be sent to a provider/", "/will not answer questions or change your business records while it is unavailable/"),
        ("/executionAvailable &&/", "/will not answer questions or change your business records while it is unavailable/"),
        ("/will not prepare an answer or change your business records/", "/will not answer questions or change your business records while it is unavailable/"),
    ],
    "apps/web/tests/lexa-language-overhaul.test.mjs": [
        ("Guidance for your business", "Guidance that fits your business"),
        ("/The assistant isn’t available right now/", "/The business assistant isn’t available right now/"),
        ("/will not prepare an answer or change your business records/", "/will not answer questions or change your business records while it is unavailable/"),
        ("/demand-forecast", "/demand-forecast"),
    ],
    "apps/api/tests/test_intelligence_phase3.py": [
        ('    assert "executionAvailable &&" in ai_ui\n    assert "Your question will not be sent to a provider" in ai_ui', '    assert "The business assistant isn’t available right now." in ai_ui\n    assert "will not answer questions or change your business records while it is unavailable" in ai_ui\n    assert "fetch(" not in ai_ui\n    assert "<textarea" not in ai_ui'),
        ('    assert "will not prepare an answer or change your business records" in assistant_ui', '    assert "will not answer questions or change your business records while it is unavailable" in assistant_ui'),
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes; without this option, only preview")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    changed_files: list[str] = []
    changed_phrases = 0
    missing_files: list[str] = []
    for rel, pairs in RULES.items():
        path = args.root / rel
        if not path.is_file():
            missing_files.append(rel)
            continue
        before = path.read_text(encoding="utf-8")
        after = before
        count = 0
        for old, new in pairs:
            occurrences = after.count(old)
            if occurrences:
                after = after.replace(old, new)
                count += occurrences
        if after != before:
            changed_files.append(rel)
            changed_phrases += count
            if args.apply:
                path.write_text(after, encoding="utf-8", newline="\n")
            print(f"{'UPDATED' if args.apply else 'WOULD UPDATE'} {rel}: {count} wording change(s)")
    # Keep existing language contracts aligned with the approved copy across every test.
    # This pass is deliberately limited to tests and only updates literal visible wording.
    test_root = args.root / "apps/web/tests"
    test_pairs = [
        ("TODAY'S WORK", "TODAY'S PRIORITIES"),
        ('"Demand forecast"', '"Sales forecast"'),
        ("Expected demand and sales forecast", "Sales estimates and restock planning"),
        ('"Receiving"', '"Record deliveries"'),
        ("/Receiving/", "/Record deliveries/"),
        ('"Bills & payments"', '"Supplier bills and payments"'),
        ("End-of-day check", "End-of-day payment check"),
        ("Sales history", "Past sales"),
        ("Business trends and insights", "Business insights"),
        ("/Variants/", "/product options/i"),
        ("Planning evidence only", "For planning only"),
        ("Information to check or update", "Information to check"),
        ("Missing information is never treated as zero", "Missing information is not counted as zero"),
        ("No official fiscal documents have been recorded yet", "No official tax documents have been recorded yet"),
        ("Checking that everything is ready", "Checking that your business is ready"),
        ("Set up missing details", "Add the details that are still needed"),
        ("Business writes performed: no", "No stock or purchase records are changed"),
        ("will not prepare an answer or change your business records", "will not answer questions or change your business records while it is unavailable"),
        ("Check the record before retrying", "Check the record before trying again"),
    ]
    if test_root.is_dir():
        for test_path in sorted(test_root.glob("*.test.mjs")):
            before = test_path.read_text(encoding="utf-8")
            after = before
            count = 0
            for old, new in test_pairs:
                n = after.count(old)
                if n:
                    after = after.replace(old, new)
                    count += n
            if after != before:
                rel = str(test_path.relative_to(args.root))
                if rel not in changed_files:
                    changed_files.append(rel)
                changed_phrases += count
                if args.apply:
                    test_path.write_text(after, encoding="utf-8", newline="\n")
                print(f"{'UPDATED' if args.apply else 'WOULD UPDATE'} {rel}: {count} test wording expectation(s)")

    print(f"\n{'Applied' if args.apply else 'Preview'}: {changed_phrases} wording changes across {len(changed_files)} files.")
    if missing_files:
        print(f"Files not present in this checkout: {len(missing_files)} (showing up to 12)")
        for name in missing_files[:12]:
            print(f"  - {name}")
    if args.apply and len(changed_files) < 8:
        print("ERROR: too few source files changed; this may not be the expected LEXA main checkout.", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
