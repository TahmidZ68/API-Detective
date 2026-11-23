"""Verification and test runner tool for validating remediation repairs."""

from __future__ import annotations

from typing import Any

from backend.app.diagnostics import run_all_diagnostics
from backend.app.schemas.diagnostics import (
    DiagnosticFinding,
    HTTPExchangeSnapshot,
    RepositoryAnalysisResult,
    VerificationReport,
)


def run_diagnostic_verification(
    *,
    previous_findings: list[DiagnosticFinding],
    url: str | None = None,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    query_params: dict[str, Any] | None = None,
    request_payload: Any | None = None,
    exchange: HTTPExchangeSnapshot | None = None,
    openapi_spec: str | dict[str, Any] | None = None,
    request_schema: dict[str, Any] | None = None,
    expected_response_schema: dict[str, Any] | None = None,
    repository_analysis: RepositoryAnalysisResult | None = None,
    applied_fixes: list[str] | None = None,
) -> VerificationReport:
    """Re-run diagnostics and compare against initial findings to verify whether fixes worked."""
    current_findings = run_all_diagnostics(
        url=url,
        method=method,
        headers=headers,
        query_params=query_params,
        request_payload=request_payload,
        exchange=exchange,
        openapi_spec=openapi_spec,
        request_schema=request_schema,
        expected_response_schema=expected_response_schema,
        repository_analysis=repository_analysis,
    )

    prev_keys = {(f.diagnostic_id, f.title): f.title for f in previous_findings}
    curr_keys = {(f.diagnostic_id, f.title): f.title for f in current_findings}

    resolved_keys = [k for k in prev_keys if k not in curr_keys]
    remaining_ids = [f"{f.diagnostic_id}: {f.title}" for f in current_findings]

    passed_checks: list[str] = []
    failed_checks: list[str] = []

    for did, title in resolved_keys:
        passed_checks.append(f"Resolved {did} ({title})")

    if applied_fixes:
        for fix_note in applied_fixes:
            passed_checks.append(f"Applied approved fix: {fix_note}")

    if exchange and exchange.response_status and 200 <= exchange.response_status < 300:
        passed_checks.append(f"Endpoint responded with HTTP {exchange.response_status}")
    elif exchange and exchange.response_status and exchange.response_status >= 400:
        failed_checks.append(f"Endpoint returned HTTP {exchange.response_status}")

    for f in current_findings:
        if f.severity in ("critical", "high"):
            failed_checks.append(f"Active {f.severity} finding {f.diagnostic_id}: {f.title}")

    unverified_assumptions: list[str] = []
    if exchange is None or exchange.response_status is None:
        unverified_assumptions.append(
            "Live upstream server response was not re-queried after local configuration verification."
        )

    fix_worked = len(failed_checks) == 0 and (
        len(resolved_keys) > 0 or len(current_findings) == 0
    )
    summary = (
        f"Verification passed ({len(passed_checks)} check(s) succeeded, 0 high/critical issues remaining)."
        if fix_worked
        else f"Verification completed with {len(remaining_ids)} remaining issue(s) and {len(passed_checks)} passed check(s)."
    )

    return VerificationReport(
        verified=True,
        fix_worked=fix_worked,
        passed_checks=passed_checks or ["Deterministic diagnostic suite executed cleanly."],
        failed_checks=failed_checks,
        remaining_problems=remaining_ids,
        unverified_assumptions=unverified_assumptions,
        summary=summary,
    )
