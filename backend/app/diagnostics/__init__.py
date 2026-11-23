"""Unified deterministic diagnostic engine entry point."""

from __future__ import annotations

from typing import Any

from backend.app.diagnostics.authentication import analyze_authentication
from backend.app.diagnostics.connectivity import analyze_connectivity
from backend.app.diagnostics.integration_analyzer import analyze_integration
from backend.app.diagnostics.request_analyzer import analyze_request
from backend.app.diagnostics.response_analyzer import analyze_response
from backend.app.diagnostics.schema_validator import (
    analyze_schema,
    validate_payload_against_schema,
)
from backend.app.schemas.diagnostics import (
    DiagnosticFinding,
    HTTPExchangeSnapshot,
    RepositoryAnalysisResult,
)
from backend.app.tools.openapi_parser import extract_operation_contract, parse_spec_content


def run_all_diagnostics(
    *,
    url: str | None = None,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    query_params: dict[str, Any] | None = None,
    request_payload: Any | None = None,
    raw_request_text: str | None = None,
    exchange: HTTPExchangeSnapshot | None = None,
    error_message: str | None = None,
    openapi_spec: str | dict[str, Any] | None = None,
    request_schema: dict[str, Any] | None = None,
    expected_response_schema: dict[str, Any] | None = None,
    expected_status: int | None = None,
    expected_base_url: str | None = None,
    required_scopes: list[str] | None = None,
    environment_vars: dict[str, str] | None = None,
    repository_analysis: RepositoryAnalysisResult | None = None,
) -> list[DiagnosticFinding]:
    """Run all six deterministic diagnostic analyzers and return deduplicated findings."""
    contract: dict[str, Any] = {}
    if openapi_spec is not None and url:
        try:
            spec_dict = parse_spec_content(openapi_spec)
            contract = extract_operation_contract(spec_dict, url, method)
        except Exception:
            contract = {}

    all_findings: list[DiagnosticFinding] = []

    if url is not None or error_message is not None or exchange is not None or repository_analysis is None:
        all_findings.extend(
            analyze_connectivity(
                url=url,
                method=method,
                request_headers=headers,
                exchange=exchange,
                error_message=error_message,
            )
        )

    combined_scopes = list(required_scopes or [])
    if contract.get("required_scopes"):
        for s in contract["required_scopes"]:
            if s not in combined_scopes:
                combined_scopes.append(s)

    all_findings.extend(
        analyze_authentication(
            url=url,
            request_headers=headers,
            query_params=query_params,
            exchange=exchange,
            required_scopes=combined_scopes or None,
            expected_auth_scheme=contract.get("expected_auth_scheme"),
            expected_key_location=contract.get("expected_key_location"),
            expected_key_name=contract.get("expected_key_name"),
        )
    )

    all_findings.extend(
        analyze_request(
            url=url,
            method=method,
            headers=headers,
            query_params=query_params,
            request_payload=request_payload,
            raw_request_text=raw_request_text,
            exchange=exchange,
            allowed_methods=contract.get("allowed_methods") or None,
            required_headers=contract.get("required_headers") or None,
            required_query_params=contract.get("required_query_params") or None,
        )
    )

    all_findings.extend(
        analyze_schema(
            url=url,
            method=method,
            request_payload=request_payload,
            exchange=exchange,
            openapi_spec=openapi_spec,
            request_schema=request_schema,
            expected_response_schema=expected_response_schema,
        )
    )

    all_findings.extend(
        analyze_response(
            url=url,
            method=method,
            request_headers=headers,
            query_params=query_params,
            exchange=exchange,
            expected_status=expected_status,
        )
    )

    all_findings.extend(
        analyze_integration(
            url=url,
            method=method,
            request_payload=request_payload,
            exchange=exchange,
            openapi_spec=openapi_spec,
            expected_base_url=expected_base_url,
            environment_vars=environment_vars,
            repository_analysis=repository_analysis,
        )
    )

    # Deduplicate by (diagnostic_id, title) preserving order
    seen: set[tuple[str, str]] = set()
    unique: list[DiagnosticFinding] = []
    for f in all_findings:
        key = (f.diagnostic_id, f.title)
        if key not in seen:
            seen.add(key)
            unique.append(f)

    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}
    unique.sort(key=lambda item: (severity_rank.get(item.severity, 5), -item.confidence))
    return unique


__all__ = [
    "analyze_authentication",
    "analyze_connectivity",
    "analyze_integration",
    "analyze_request",
    "analyze_response",
    "analyze_schema",
    "run_all_diagnostics",
    "validate_payload_against_schema",
]
