"""Strict, tenant-aware contracts shared by LEXA's intelligence components.

Contracts describe evidence and proposed decisions; they do not execute business
transactions. Money and quantities use strings to avoid JSON floating-point loss.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TaskType(StrEnum):
    BUSINESS_INSIGHT = "business_insight"
    REPLENISHMENT = "replenishment"
    CLASSIFY = "classify"
    EXTRACT = "extract"
    EXPLAIN = "explain"
    SUMMARIZE = "summarize"
    ANALYZE = "analyze"
    FORECAST = "forecast"
    RECONCILE = "reconcile"
    DAILY_BRIEF = "daily_brief"


class DataSensitivity(StrEnum):
    PUBLIC_SYNTHETIC = "public_synthetic"
    AGGREGATED_BUSINESS = "aggregated_business"
    CONFIDENTIAL_BUSINESS = "confidential_business"
    PERSONAL_DATA = "personal_data"
    SENSITIVE_PERSONAL_DATA = "sensitive_personal_data"


class InsightSeverity(StrEnum):
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    INFORMATIONAL = "informational"
    ATTENTION = "attention"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class InsightAvailability(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class InsightLifecycle(StrEnum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class EngineType(StrEnum):
    DETERMINISTIC = "deterministic"
    PYTHON = "python"
    EXTERNAL_LLM = "external_llm"
    NONE = "none"


class ProviderId(StrEnum):
    GEMINI = "gemini"
    GROQ = "groq"
    CEREBRAS = "cerebras"
    OPENROUTER = "openrouter"
    HUGGINGFACE = "huggingface"
    OPENAI = "openai"


class SourceType(StrEnum):
    SALE = "sale"
    SALE_RETURN = "sale_return"
    PAYMENT = "payment"
    INVENTORY_SNAPSHOT = "inventory_snapshot"
    INVENTORY_MOVEMENT = "inventory_movement"
    PRODUCT = "product"
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    PURCHASE_ORDER = "purchase_order"
    SUPPLIER_BILL = "supplier_bill"
    EXPENSE = "expense"
    JOURNAL_ENTRY = "journal_entry"
    RECEIPT = "receipt"
    DOCUMENT = "document"
    ANALYTICS_PROJECTION = "analytics_projection"
    RULE = "rule"


class TenantScope(StrictModel):
    """Server-derived request scope; clients must never be trusted to provide it."""

    tenant_id: UUID
    user_id: UUID
    branch_id: UUID | None = None


class SourceReference(StrictModel):
    """A pointer to a tenant-scoped LEXA record, never a copy of the record."""

    source_type: SourceType
    record_id: UUID
    branch_id: UUID | None = None


class MetricValue(StrictModel):
    label: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=80, description="Decimal encoded as text")
    unit: str = Field(min_length=1, max_length=40)
    currency_code: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    comparison_value: str | None = Field(default=None, max_length=80)
    comparison_label: str | None = Field(default=None, max_length=120)

    @field_validator("value", "comparison_value")
    @classmethod
    def validate_decimal_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Metric values must be finite decimal strings") from exc
        if not parsed.is_finite():
            raise ValueError("Metric values must be finite decimal strings")
        return format(parsed, "f")


class EvidenceReference(StrictModel):
    source: SourceReference
    label: str = Field(min_length=1, max_length=120)
    as_of: datetime | None = None
    fact_keys: list[str] = Field(default_factory=list, max_length=30)


class RecommendedAction(StrictModel):
    """A suggestion only; phase 1 cannot execute it."""

    action_code: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    target: SourceReference | None = None
    requires_human_approval: bool = True
    executable_in_phase1: bool = False

    @model_validator(mode="after")
    def prohibit_phase_one_execution(self) -> "RecommendedAction":
        if self.executable_in_phase1:
            raise ValueError("Phase 1 recommendations are never executable")
        if not self.requires_human_approval:
            raise ValueError("Recommended actions must require human approval")
        return self


class InsightContract(StrictModel):
    """A machine-readable, evidence-backed business insight envelope."""

    insight_id: UUID
    tenant_id: UUID
    branch_id: UUID | None = None
    insight_type: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")
    availability: InsightAvailability
    lifecycle_status: InsightLifecycle = InsightLifecycle.NEW
    severity: InsightSeverity = InsightSeverity.UNKNOWN
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=2400)
    metrics: list[MetricValue] = Field(default_factory=list, max_length=30)
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=50)
    methodology: str = Field(min_length=1, max_length=1600)
    limitations: list[str] = Field(default_factory=list, max_length=30)
    as_of: datetime | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_version: str = Field(min_length=1, max_length=100)
    trace_id: UUID | None = None
    recommended_action: RecommendedAction | None = None

    @model_validator(mode="after")
    def require_evidence_when_available(self) -> "InsightContract":
        if self.availability == InsightAvailability.AVAILABLE and not self.evidence:
            raise ValueError("Available insights must include at least one evidence reference")
        if self.availability == InsightAvailability.UNAVAILABLE and self.metrics:
            raise ValueError("Unavailable insights cannot present current metric values")
        return self


class RoutingRequest(StrictModel):
    """Internal routing input; data references, not raw records or prompts."""

    task: TaskType
    sensitivity: DataSensitivity
    provider_preference: ProviderId | None = None
    source: SourceReference | None = None
    includes_business_summary: bool = False
    # Set only by trusted server-side screening code, never from an HTTP payload.
    input_safety_checked: bool = False
    purpose_code: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")


class RouterDecision(StrictModel):
    policy_version: str
    task: TaskType
    allowed: bool
    engine: EngineType
    reason_code: str
    sensitivity: DataSensitivity
    selected_provider: ProviderId | None = None
    fallback_provider: ProviderId | None = None
    automatic_fallbacks: bool = False
    external_data_transfer: bool = False
    is_executable: bool = False

    @model_validator(mode="after")
    def validate_external_route(self) -> "RouterDecision":
        if self.fallback_provider is not None or self.automatic_fallbacks:
            raise ValueError("LEXA policy never configures automatic provider fallback")
        if self.engine == EngineType.EXTERNAL_LLM and self.allowed:
            if self.selected_provider is None or not self.external_data_transfer:
                raise ValueError("An approved external route must identify the provider and transfer boundary")
        if not self.allowed and self.is_executable:
            raise ValueError("A blocked route cannot be executable")
        return self


class EventType(StrEnum):
    SALE_COMPLETED = "sales.sale_completed.v1"
    RETURN_COMPLETED = "sales.return_completed.v1"
    PAYMENT_RECORDED = "payments.payment_recorded.v1"
    INVENTORY_MOVEMENT_RECORDED = "inventory.movement_recorded.v1"
    PURCHASE_ORDER_RECEIVED = "purchasing.order_received.v1"
    SUPPLIER_BILL_RECORDED = "purchasing.supplier_bill_recorded.v1"
    EXPENSE_RECORDED = "finance.expense_recorded.v1"
    JOURNAL_POSTED = "finance.journal_posted.v1"
    DOCUMENT_RECEIVED = "documents.document_received.v1"
    ANALYTICS_REFRESHED = "analytics.projection_refreshed.v1"


class EventMetadata(StrictModel):
    """Allow-listed, non-free-text event metadata. No names, emails or document text."""

    business_date: date | None = None
    currency_code: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    record_count: int | None = Field(default=None, ge=0, le=10_000_000)
    document_type: str | None = Field(default=None, max_length=60, pattern=r"^[A-Z][A-Z0-9_]*$")
    source_status: str | None = Field(default=None, max_length=40, pattern=r"^[A-Z][A-Z0-9_]*$")


class IntelligenceEvent(StrictModel):
    """Normalized event envelope for future outbox consumers; not a domain write API."""

    event_id: UUID
    schema_version: int = Field(default=1, ge=1, le=1)
    event_type: EventType
    tenant_id: UUID
    branch_id: UUID | None = None
    aggregate_type: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    aggregate_id: UUID
    occurred_at: datetime
    actor_user_id: UUID | None = None
    metadata: EventMetadata = Field(default_factory=EventMetadata)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Event timestamps must be timezone-aware")
        return value


class IntelligenceJobReference(StrictModel):
    """Reference-only job input; binary documents/prompts stay out of the queue row."""

    task: TaskType
    source: SourceReference | None = None
    business_date: date | None = None
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
