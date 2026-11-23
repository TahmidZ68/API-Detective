"""Standardized Pydantic v2 schemas for API Detective."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

DiagnosticCategory = Literal[
    "connectivity",
    "authentication",
    "request",
    "schema",
    "response",
    "integration",
]

DiagnosticSeverity = Literal[
    "critical",
    "high",
    "medium",
    "low",
    "informational",
]

FindingStatus = Literal[
    "confirmed",
    "probable",
    "possible",
    "unverified",
]


class DiagnosticFinding(BaseModel):
    """Standardized diagnostic finding produced by deterministic diagnostic modules."""

    diagnostic_id: str = Field(..., description="Unique diagnostic code, e.g. AUTH-001")
    category: DiagnosticCategory
    severity: DiagnosticSeverity
    title: str
    description: str
    evidence: list[str] = Field(default_factory=list)
    recommendation: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    status: FindingStatus
    metadata: dict[str, Any] = Field(default_factory=dict)


class HTTPExchangeSnapshot(BaseModel):
    """Redacted snapshot of an HTTP request and response exchange."""

    method: str = "GET"
    url: str
    request_headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, Any] = Field(default_factory=dict)
    request_body: Any | None = None
    response_status: int | None = None
    response_headers: dict[str, str] = Field(default_factory=dict)
    response_body: Any | None = None
    raw_response_text: str | None = None
    elapsed_ms: float | None = None
    redirect_chain: list[str] = Field(default_factory=list)
    error_type: str | None = None
    error_message: str | None = None
    tls_verified: bool = True
    dns_resolved_ips: list[str] = Field(default_factory=list)


class InvestigationPlanStep(BaseModel):
    """A single planned action in an investigation plan."""

    step_index: int
    tool_name: str
    rationale: str
    completed: bool = False


class InvestigationStepRecord(BaseModel):
    """Audit log entry for a completed investigation phase or tool execution."""

    step_number: int
    phase: Literal[
        "understand",
        "plan",
        "execute_tool",
        "analyze",
        "remediate",
        "apply_fix",
        "verify",
    ]
    tool_name: str | None = None
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class RootCauseHypothesis(BaseModel):
    """Ranked root-cause finding backed by deterministic and repository evidence."""

    hypothesis_id: str = Field(default_factory=lambda: f"RC-{uuid4().hex[:6].upper()}")
    rank: int
    title: str
    category: DiagnosticCategory
    confidence: float = Field(..., ge=0.0, le=1.0)
    status: FindingStatus
    explanation: str
    supporting_evidence: list[str] = Field(default_factory=list)
    related_diagnostic_ids: list[str] = Field(default_factory=list)


class RemediationPlanItem(BaseModel):
    """Actionable fix proposal with evidence, risk assessment, and optional patch."""

    fix_id: str = Field(default_factory=lambda: f"FIX-{uuid4().hex[:6].upper()}")
    problem: str
    evidence: list[str] = Field(default_factory=list)
    root_cause: str
    recommended_solution: str
    affected_files: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "low"
    repair_level: int = Field(default=1, ge=1, le=4)
    unified_diff: str | None = None
    requires_approval: bool = True
    approved: bool = False
    applied: bool = False
    verification_procedure: str


class VerificationReport(BaseModel):
    """Outcome of running verification diagnostics and tests after a fix."""

    verified: bool
    fix_worked: bool
    passed_checks: list[str] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    remaining_problems: list[str] = Field(default_factory=list)
    unverified_assumptions: list[str] = Field(default_factory=list)
    summary: str


class RepositoryFinding(BaseModel):
    """A single integration finding discovered during repository code analysis."""

    file_path: str
    line_number: int
    language: Literal["python", "javascript", "typescript", "env", "config"]
    client_library: str
    pattern_type: Literal[
        "endpoint",
        "request_construction",
        "env_reference",
        "auth_config",
        "response_parsing",
        "config_mismatch",
    ]
    snippet: str
    note: str


class RepositoryAnalysisResult(BaseModel):
    """Summary of repository inspection for API integration logic."""

    repository_path: str
    files_scanned: int
    languages_detected: list[str] = Field(default_factory=list)
    client_libraries_detected: list[str] = Field(default_factory=list)
    endpoints_discovered: list[str] = Field(default_factory=list)
    env_vars_referenced: list[str] = Field(default_factory=list)
    findings: list[RepositoryFinding] = Field(default_factory=list)
    diagnostic_findings: list[DiagnosticFinding] = Field(default_factory=list)


class InvestigationRequest(BaseModel):
    """Input payload for initiating an API Detective investigation."""

    title: str | None = None
    prompt: str | None = Field(
        default=None,
        description="Natural language task description, e.g. 'Why is my API returning 401?'",
    )
    url: str | None = None
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, Any] = Field(default_factory=dict)
    request_payload: Any | None = None
    raw_request_text: str | None = None
    expected_status: int | None = None
    simulated_response_status: int | None = None
    simulated_response_headers: dict[str, str] = Field(default_factory=dict)
    simulated_response_body: Any | None = None
    error_message: str | None = None
    openapi_spec: dict[str, Any] | str | None = None
    expected_response_schema: dict[str, Any] | None = None
    request_schema: dict[str, Any] | None = None
    repository_path: str | None = None
    environment_vars: dict[str, str] = Field(default_factory=dict)
    expected_base_url: str | None = None
    required_scopes: list[str] = Field(default_factory=list)
    execute_live_request: bool = True
    allow_localhost: bool = False


class InvestigationReport(BaseModel):
    """Complete structured report of an API Detective investigation."""

    investigation_id: str = Field(default_factory=lambda: f"INV-{uuid4().hex[:8].upper()}")
    title: str
    prompt: str | None = None
    status: Literal["running", "completed", "resolved", "failed", "cancelled"] = "completed"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    target_url: str | None = None
    http_method: str = "GET"
    plan: list[InvestigationPlanStep] = Field(default_factory=list)
    timeline: list[InvestigationStepRecord] = Field(default_factory=list)
    http_exchange: HTTPExchangeSnapshot | None = None
    findings: list[DiagnosticFinding] = Field(default_factory=list)
    root_causes: list[RootCauseHypothesis] = Field(default_factory=list)
    remediation_plan: list[RemediationPlanItem] = Field(default_factory=list)
    repository_analysis: RepositoryAnalysisResult | None = None
    verification: VerificationReport | None = None
    llm_assisted: bool = False
    llm_provider_used: str = "none"
    summary: str = ""


class ApproveFixRequest(BaseModel):
    """Payload to approve and optionally apply a proposed remediation fix."""

    fix_id: str
    approved: bool = True
    apply_changes: bool = True
    run_verification: bool = True


class SchemaValidationRequest(BaseModel):
    """Payload to validate a JSON payload against a JSON Schema or OpenAPI definition."""

    schema_def: dict[str, Any]
    payload: Any


class SchemaValidationResponse(BaseModel):
    """Response from standalone schema validation."""

    valid: bool
    findings: list[DiagnosticFinding] = Field(default_factory=list)


class SpecInspectRequest(BaseModel):
    """Payload to inspect an OpenAPI / Swagger specification."""

    content: str | dict[str, Any]


class SpecInspectResponse(BaseModel):
    """Parsed summary of an OpenAPI / Swagger specification."""

    valid: bool
    spec_version: str
    title: str
    base_urls: list[str] = Field(default_factory=list)
    endpoints: list[dict[str, Any]] = Field(default_factory=list)
    security_schemes: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DashboardOverviewStats(BaseModel):
    """Real backend metrics for the web dashboard overview."""

    total_investigations: int
    successful_diagnoses: int
    open_issues: int
    resolved_issues: int
    category_distribution: dict[str, int] = Field(default_factory=dict)
    severity_distribution: dict[str, int] = Field(default_factory=dict)
    recent_investigations: list[InvestigationReport] = Field(default_factory=list)
    recent_activity: list[InvestigationStepRecord] = Field(default_factory=list)


class AgentSettingsPayload(BaseModel):
    """Runtime settings update payload from the Agent Settings UI."""

    llm_provider: Literal["none", "openai", "gemini", "anthropic", "local"] | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    agent_max_iterations: int | None = Field(default=None, ge=1, le=20)
    http_timeout_seconds: float | None = Field(default=None, ge=1.0, le=120.0)
    block_private_networks: bool | None = None
    allow_localhost_targets: bool | None = None
    allow_repo_transmission_to_llm: bool | None = None
    require_approval_for_file_edits: bool | None = None
    redact_secrets: bool | None = None
    persist_request_bodies: bool | None = None


class AgentSettingsResponse(BaseModel):
    """Current agent and security settings (with API key masked)."""

    llm_provider: str
    llm_model: str
    llm_api_key_configured: bool
    llm_base_url: str
    agent_max_iterations: int
    http_timeout_seconds: float
    block_private_networks: bool
    allow_localhost_targets: bool
    allow_repo_transmission_to_llm: bool
    require_approval_for_file_edits: bool
    redact_secrets: bool
    persist_request_bodies: bool
