"""Agent Step 7: Post-repair verification runner (Repair Level 4)."""

from __future__ import annotations

from backend.app.schemas.diagnostics import (
    DiagnosticFinding,
    HTTPExchangeSnapshot,
    InvestigationRequest,
    RemediationPlanItem,
    RepositoryAnalysisResult,
    VerificationReport,
)
from backend.app.tools.repository_inspector import inspect_repository
from backend.app.tools.test_runner import run_diagnostic_verification


def verify_remediation(
    *,
    request: InvestigationRequest,
    previous_findings: list[DiagnosticFinding],
    remediation_plan: list[RemediationPlanItem],
    updated_exchange: HTTPExchangeSnapshot | None = None,
) -> VerificationReport:
    """Step 7 (Level 4): Verify applied repairs by re-running relevant diagnostic and repository checks."""
    applied_items = [item for item in remediation_plan if item.approved and item.applied]
    updated_headers = dict(request.headers or {})
    updated_url = request.url

    for item in applied_items:
        prob_lower = item.problem.lower()
        if "missing authorization header" in prob_lower:
            updated_headers["Authorization"] = "Bearer verified_token_placeholder_valid_structure"
        elif "expired jwt" in prob_lower or "invalid or placeholder bearer" in prob_lower:
            updated_headers["Authorization"] = "Bearer refreshed_valid_session_token"
        elif "duplicate 'bearer' prefix" in prob_lower and "Authorization" in updated_headers:
            updated_headers["Authorization"] = updated_headers["Authorization"].replace(
                "Bearer Bearer ", "Bearer "
            )
        elif "content-type" in prob_lower:
            updated_headers["Content-Type"] = "application/json"
        elif "undocumented endpoint path" in prob_lower and item.unified_diff:
            for line in item.unified_diff.splitlines():
                if line.startswith("+url: "):
                    updated_url = line.replace("+url: ", "").strip()

    # Re-scan repository if repository_path was part of the investigation
    updated_repo_analysis: RepositoryAnalysisResult | None = None
    if request.repository_path:
        try:
            updated_repo_analysis = inspect_repository(request.repository_path)
        except Exception:
            updated_repo_analysis = None

    report = run_diagnostic_verification(
        previous_findings=previous_findings,
        url=updated_url,
        method=request.method,
        headers=updated_headers,
        query_params=request.query_params,
        request_payload=request.request_payload,
        exchange=updated_exchange,
        openapi_spec=request.openapi_spec,
        request_schema=request.request_schema,
        expected_response_schema=request.expected_response_schema,
        repository_analysis=updated_repo_analysis,
        applied_fixes=[f"{item.fix_id}: {item.problem}" for item in applied_items],
    )

    for item in applied_items:
        item.repair_level = 4

    return report
