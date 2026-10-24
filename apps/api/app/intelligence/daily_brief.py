"""Rules-first, evidence-backed daily brief composition for LEXA Phase 2.

This module is pure: it does not access a database, call an AI provider, or mutate
business records. It ranks the existing deterministic insight payload returned by
LEXA's canonical analytics insight calculator.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence

RULE_VERSION = "lexa-daily-brief-v1"

# Stable tie-break order makes identical source inputs produce identical ordering.
_ID_ORDER = {
    "stock-risk": 0,
    "working-capital-balances": 1,
    "sales-movement": 2,
    "gross-margin-movement": 3,
}
_SEVERITY_RANK = {
    "critical": 5,
    "attention": 4,
    "unknown": 3,
    "informational": 2,
    "positive": 1,
    "neutral": 0,
}
_ACTIONS = {
    "stock-risk": ("Review stock availability", "/inventory"),
    "working-capital-balances": ("Review customer and supplier balances", "/accounting"),
    "sales-movement": ("Review sales reports", "/reports"),
    "gross-margin-movement": ("Review product margin and cost records", "/reports"),
}


def _safe_href(value: Any, fallback: str) -> str:
    """Only expose same-app relative links; never allow source text to set an origin."""
    if not isinstance(value, str):
        return fallback
    path = value.strip()
    if not path.startswith("/") or path.startswith("//") or "://" in path or "\\" in path:
        return fallback
    return path[:240]


def _evidence(insight: Mapping[str, Any], fallback_href: str) -> dict[str, Any]:
    source = insight.get("source") if isinstance(insight.get("source"), Mapping) else {}
    source_label = insight.get("evidence") if isinstance(insight.get("evidence"), Mapping) else {}
    href = _safe_href(source_label.get("href"), fallback_href)
    tables = source.get("tables", [])
    if not isinstance(tables, list):
        tables = []
    safe_tables = [str(table)[:100] for table in tables[:12] if isinstance(table, str)]
    return {
        "label": str(source_label.get("label") or "Open source report")[:120],
        "href": href,
        "source_tables": safe_tables,
        "record_count": max(0, int(source.get("record_count") or 0)),
        "as_of_date": str(source.get("as_of_date")) if source.get("as_of_date") is not None else None,
        "refreshed_at": str(source.get("refreshed_at")) if source.get("refreshed_at") is not None else None,
    }


def _metric_payload(insight: Mapping[str, Any], *, status: str) -> dict[str, Any]:
    # The existing deterministic builders suppress metrics on stale/unavailable
    # records. Keep that invariant here even if a future source regresses.
    if status in {"stale", "unavailable"}:
        return {"metric": None, "comparison": None, "details": None, "examples": []}
    metric = insight.get("metric")
    comparison = insight.get("comparison")
    details = insight.get("details")
    examples = insight.get("examples")
    return {
        "metric": dict(metric) if isinstance(metric, Mapping) else None,
        "comparison": dict(comparison) if isinstance(comparison, Mapping) else None,
        "details": dict(details) if isinstance(details, Mapping) else None,
        "examples": [dict(item) for item in examples[:3] if isinstance(item, Mapping)] if isinstance(examples, list) else [],
    }


def build_daily_brief(
    *,
    insights_payload: Mapping[str, Any],
    as_of_date: date,
    currency_code: str,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Compose a deterministic daily brief from canonical saved-data insights.

    It does not infer missing records as zero, add values across currencies, infer
    causes, or execute any suggested action. Unknown future insight types remain
    visible in the informational section instead of being silently discarded.
    """
    currency = str(currency_code).strip().upper()
    if len(currency) != 3 or not currency.isalpha() or not currency.isascii():
        raise ValueError("currency_code must be a three-letter ISO-style code")
    raw_insights = insights_payload.get("insights")
    if not isinstance(raw_insights, Sequence) or isinstance(raw_insights, (str, bytes)):
        raise ValueError("insights_payload must contain an insights array")

    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in raw_insights:
        if not isinstance(raw, Mapping):
            raise ValueError("each insight must be an object")
        insight_id = str(raw.get("id") or "").strip()
        title = str(raw.get("title") or "").strip()
        summary = str(raw.get("summary") or "").strip()
        status = str(raw.get("status") or "unavailable").strip().lower()
        severity = str(raw.get("severity") or "unknown").strip().lower()
        if not insight_id or not title or not summary:
            raise ValueError("each insight must include id, title and summary")
        if insight_id in seen_ids:
            raise ValueError(f"duplicate insight id: {insight_id}")
        seen_ids.add(insight_id)

        default_action, default_href = _ACTIONS.get(insight_id, ("Review source records", "/analytics/insights"))
        evidence = _evidence(raw, default_href)
        item = {
            "rule_id": f"{RULE_VERSION}:{insight_id}",
            "source_insight_id": insight_id,
            "category": insight_id,
            "title": title[:160],
            "summary": summary[:2400],
            "status": status,
            "severity": severity if severity in _SEVERITY_RANK else "unknown",
            "priority_rank": _SEVERITY_RANK.get(severity, _SEVERITY_RANK["unknown"]),
            "action_label": default_action,
            "action_href": default_href,
            "evidence": evidence,
            "limitations": [str(x)[:500] for x in raw.get("limitations", [])[:10]] if isinstance(raw.get("limitations"), list) else [],
            **_metric_payload(raw, status=status),
        }
        items.append(item)

    if len(items) > 20:
        raise ValueError("daily brief input exceeds the supported insight limit")

    # Only current, rule-flagged findings enter action_items. Stale and unavailable
    # sources are explicitly routed to data_quality, not presented as current risk.
    action_items = [
        item for item in items
        if item["status"] == "available" and item["severity"] in {"critical", "attention"}
    ]
    action_items.sort(key=lambda item: (-item["priority_rank"], _ID_ORDER.get(item["source_insight_id"], 99), item["source_insight_id"]))

    data_quality = [item for item in items if item["status"] in {"stale", "unavailable"}]
    data_quality.sort(key=lambda item: (_ID_ORDER.get(item["source_insight_id"], 99), item["source_insight_id"]))

    information_items = [
        item for item in items
        if item not in action_items and item not in data_quality
    ]
    information_items.sort(key=lambda item: (-item["priority_rank"], _ID_ORDER.get(item["source_insight_id"], 99), item["source_insight_id"]))

    urgent_count = sum(item["severity"] == "critical" for item in action_items)
    if urgent_count:
        headline = f"{urgent_count} critical business issue(s) need prompt review."
        brief_status = "partial" if data_quality else "attention"
    elif action_items:
        headline = f"{len(action_items)} business area(s) need review today."
        brief_status = "partial" if data_quality else "attention"
    elif data_quality:
        headline = "Some source data is stale or unavailable; check data quality before relying on the full brief."
        brief_status = "partial"
    elif any(item["severity"] == "positive" for item in information_items):
        headline = "No urgent rule-based alerts; at least one indicator improved."
        brief_status = "available"
    elif items:
        headline = "No urgent rule-based alerts were raised from the available saved data."
        brief_status = "available"
    else:
        headline = "No business insight rows were returned; this is not evidence of zero activity."
        brief_status = "unavailable"

    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")

    # Large detail payloads are bounded; source insights remain available in their
    # reports. Do not leak tenant IDs, source row dumps, or arbitrary source text.
    def compact(item: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: item[key]
            for key in (
                "rule_id", "source_insight_id", "category", "title", "summary",
                "status", "severity", "action_label", "action_href", "evidence",
                "metric", "comparison", "details", "examples", "limitations",
            )
            if key in item
        }

    insight_period = insights_payload.get("period") if isinstance(insights_payload.get("period"), Mapping) else {}
    return {
        "schema_version": "phase2.daily_brief.v1",
        "rule_version": RULE_VERSION,
        "generated_at": generated.astimezone(timezone.utc).isoformat(),
        "as_of_date": as_of_date.isoformat(),
        "currency_code": currency,
        "period": {
            "from_date": str(insight_period.get("from_date") or as_of_date.isoformat()),
            "to_date": str(insight_period.get("to_date") or as_of_date.isoformat()),
            "comparison_period": dict(insights_payload.get("comparison_period") or {}),
        },
        "scope": str(insights_payload.get("scope") or "authorized_workspace_scope"),
        "headline": headline,
        "status": brief_status,
        "counts": {
            "insights_considered": len(items),
            "action_items": len(action_items),
            "information_items": len(information_items),
            "data_quality_items": len(data_quality),
        },
        "action_items": [compact(item) for item in action_items[:8]],
        "information_items": [compact(item) for item in information_items[:8]],
        "data_quality": [compact(item) for item in data_quality[:8]],
        "last_successful_refresh_at": insights_payload.get("last_successful_refresh_at"),
        "advisory_only": True,
        "external_ai_used": False,
        "business_writes_performed": False,
        "limitations": [
            "Priority is deterministic and based on the saved insight severity; it is not a prediction of future loss.",
            "A missing or stale projection is not interpreted as zero activity.",
            "Recommendations are review prompts only; the daily brief cannot create orders, post journals, edit stock or initiate payments.",
        ],
    }
