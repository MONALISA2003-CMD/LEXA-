"""Unit and contract tests for safe, low-overhead performance observability."""
from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.performance import elapsed_ms, format_server_timing, is_slow_request, slow_request_threshold_ms  # noqa: E402


def test_elapsed_duration_is_rounded_non_negative_and_finite():
    assert elapsed_ms(1.0, 1.012345) == 12.35
    assert elapsed_ms(2.0, 1.0) == 0.0
    assert elapsed_ms(1.0, float("inf")) == 0.0


def test_server_timing_header_is_safe_and_uses_api_metric_name():
    assert format_server_timing(14.237) == "api;dur=14.24"
    assert format_server_timing(-1) == "api;dur=0.00"
    assert format_server_timing(float("nan")) == "api;dur=0.00"


def test_slow_request_threshold_is_bounded_and_invalid_values_fall_back(monkeypatch):
    monkeypatch.setenv("LEXA_SLOW_REQUEST_MS", "750")
    assert slow_request_threshold_ms() == 750
    monkeypatch.setenv("LEXA_SLOW_REQUEST_MS", "1")
    assert slow_request_threshold_ms() == 100
    monkeypatch.setenv("LEXA_SLOW_REQUEST_MS", "99999")
    assert slow_request_threshold_ms() == 10_000
    monkeypatch.setenv("LEXA_SLOW_REQUEST_MS", "not-a-number")
    assert slow_request_threshold_ms() == 500


def test_slow_request_decision_respects_threshold_and_ignores_non_finite_values():
    assert is_slow_request(500, threshold_ms=500)
    assert not is_slow_request(499.99, threshold_ms=500)
    assert not is_slow_request(float("nan"), threshold_ms=500)


def test_api_middleware_adds_timing_without_logging_request_contents():
    source = (API_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert "started_at = time.perf_counter()" in source
    assert 'response.headers["Server-Timing"] = format_server_timing(duration_ms)' in source
    assert '"slow_request request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f"' in source
    assert '"request_failed_5xx request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f"' in source
    assert '"path": request.url.path' in source
    # Scope the privacy assertion to the timing/logging middleware. The separate
    # manual-only EFRIS guard must read its own config payload to reject any
    # attempt to activate provider submission, but that payload is not logged.
    request_id_middleware = source.split("async def request_id_middleware", 1)[1].split("\n\n@app.middleware", 1)[0]
    assert "request.url.query" not in request_id_middleware
    assert "request.body" not in request_id_middleware


def test_web_proxy_preserves_server_timing_for_success_and_upstream_5xx():
    proxy = (REPO_ROOT / "apps" / "web" / "app" / "api" / "lexa" / "[...path]" / "route.ts").read_text(encoding="utf-8")
    assert 'response.headers.get("server-timing")' in proxy
    assert 'out.headers.set("server-timing", serverTiming)' in proxy
    assert 'headers.set("Server-Timing", errorServerTiming)' in proxy


def test_performance_helpers_have_no_application_database_or_network_imports():
    source = (API_ROOT / "app" / "performance.py").read_text(encoding="utf-8")
    assert "import math" in source
    assert "import os" in source
    for forbidden in ("sqlalchemy", "psycopg", "redis", "httpx", "requests"):
        assert forbidden not in source.lower()


def test_compose_stack_keeps_api_web_and_queue_worker_as_distinct_services():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "  api:" in compose
    assert "  web:" in compose
    assert "  analytics-worker:" in compose
    assert "ANALYTICS_REFRESH_WORKER_ENABLED: \"false\"" in compose
    assert '"python", "-m", "app.workers.analytics_outbox"' in compose
    assert "service_healthy" in compose


def test_kubernetes_template_scales_api_conservatively_and_separates_worker():
    deploy = (REPO_ROOT / "deploy" / "kubernetes" / "base")
    api_manifest = (deploy / "api.yaml").read_text(encoding="utf-8")
    worker_manifest = (deploy / "analytics-worker.yaml").read_text(encoding="utf-8")
    web_manifest = (deploy / "web.yaml").read_text(encoding="utf-8")
    config = (deploy / "configmap.yaml").read_text(encoding="utf-8")
    assert "  replicas: 2" in api_manifest
    assert "  maxReplicas: 4" in api_manifest
    assert "readinessProbe:" in api_manifest and "path: /ready" in api_manifest
    assert "ANALYTICS_REFRESH_WORKER_ENABLED: \"false\"" in config
    assert 'command: ["python", "-m", "app.workers.analytics_outbox"]' in worker_manifest
    assert "  replicas: 1" in worker_manifest
    assert "/app/.next/cache" in web_manifest
    assert "REPLACE_WITH_RELEASE_TAG" in api_manifest and "REPLACE_WITH_RELEASE_TAG" in web_manifest


def test_container_images_use_current_app_directories_and_non_root_runtime():
    api_dockerfile = (REPO_ROOT / "apps" / "api" / "Dockerfile").read_text(encoding="utf-8")
    web_dockerfile = (REPO_ROOT / "apps" / "web" / "Dockerfile").read_text(encoding="utf-8")
    assert "python:3.13-slim" in api_dockerfile
    assert "USER 10001:10001" in api_dockerfile
    assert "node:24-alpine" in web_dockerfile
    assert "USER node" in web_dockerfile
    assert "npm run build" in web_dockerfile
