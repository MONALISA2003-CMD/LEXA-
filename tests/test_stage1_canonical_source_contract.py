from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_stage1_package_has_one_canonical_application_tree():
    assert (ROOT / "apps/web/package.json").is_file()
    assert (ROOT / "apps/api/app/main.py").is_file()
    assert (ROOT / "migrations/040_phase8_finance_workflows.sql").is_file()
    assert (ROOT / "migrations/041_commerce_integrity_scaling.sql").is_file()
    assert (ROOT / "migrations/042_team_chat_foundation.sql").is_file()
    assert (ROOT / "migrations/043_phase5_journal_currency_guard.sql").is_file()
    assert not (ROOT / "LEXA/apps/web/package.json").exists()
    assert not (ROOT / "LEXA/apps/api/app/main.py").exists()


def test_stage1_package_removes_the_duplicate_wrapper_after_overlay():
    # DELETE.txt and .lexa-delete are package-only control manifests. The ZIP
    # extractor consumes them while applying an overlay instead of committing
    # them into the checkout, so verify the tracked cleanup behavior directly.
    workflow = (ROOT / ".github/workflows/lexa-zip-extract.yml").read_text()
    assert "MANIFEST_NAMES = {'DELETE.txt', '.lexa-delete'}" in workflow
    assert "delete_entries.append(candidate.as_posix())" in workflow
    assert "for entry_text in delete_entries:" in workflow
    assert "shutil.rmtree(target)" in workflow


def test_stage1_includes_the_zip_normalization_workflow_patch():
    current = (ROOT / ".github/workflows/lexa-zip-extract.yml").read_text()
    distributable = (ROOT / "docs/stage1/lexa-zip-extract.yml").read_text()
    assert current == distributable
    assert "detect_wrapper" in current
    assert "multiple possible LEXA source roots" in current
    assert "Protected deletion blocked" in current


def test_stage1_uses_liveness_health_check_not_full_readiness():
    render = (ROOT / "render.yaml").read_text()
    assert "healthCheckPath: /health" in render
    assert "REQUIRED_APP_MIGRATIONS" in (ROOT / "apps/api/app/health.py").read_text()
