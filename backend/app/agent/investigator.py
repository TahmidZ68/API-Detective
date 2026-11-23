"""Agent Step 3:Bounded tool execution investigator."""

from __future__ import annotations

import time
from typing import Any

import httpx

from backend.app.core.config import get_settings
from backend.app.core.exceptions import ToolExecutionTimeoutError
from backend.app.core.security import redact_headers, redact_object, redact_text, redact_url
from backend.app.diagnostics.authentication import analyze_authentication
from backend.app.diagnostics.connectivity import analyze_connectivity
from backend.app.diagnostics.integration_analyzer import analyze_integration
from backend.app.diagnostics.request_analyzer import analyze_request
from backend.app.diagnostics.response_analyzer import analyze_response
from backend.app.diagnostics.schema_validator import analyze_schema
from backend.app.schemas.diagnostics import (
    DiagnosticFinding,
    HTTPExchangeSnapshot,
    InvestigationPlanStep,
    InvestigationRequest,
    InvestigationStepRecord,
    RepositoryAnalysisResult,
)
from backend.app.tools.http_client import execute_diagnostic_request
from backend.app.tools.log_analyzer import analyze_error_log
from backend.app.tools.openapi_parser import extract_operation_contract, parse_spec_content
from backend.app.tools.repository_inspector import inspect_repository


class ToolExecutor:
    """Executes real diagnostic tools within bounded iteration and timeout constraints."""

    def __init__(
        self,
        *,
        max_iterations: int | None = None,
        tool_timeout_seconds: float | None = None,
        http_transport: httpx.BaseTransport | None = None,
    ):
        settings = get_settings()
        self.max_iterations = max_iterations or settings.agent_max_iterations
        self.tool_timeout_seconds = tool_timeout_seconds or settings.agent_tool_timeout_seconds
        self.http_transport = http_transport

    def execute_plan(
        self,
        request: InvestigationRequest,
        plan: list[InvestigationPlanStep],
        *,
        start_step_number: int = 3,
    ) -> dict[str, Any]:
        """Run planned tools sequentially and collect real evidence and audit records."""
        findings: list[DiagnosticFinding] = []
        timeline: list[InvestigationStepRecord] = []
        contract: dict[str, Any] = {}
        log_analysis: dict[str, Any] = {}
        repository_analysis: RepositoryAnalysisResult | None = None
        exchange: HTTPExchangeSnapshot | None = None

        # Build simulated exchange if caller provided simulated response metadata
        if request.simulated_response_status is not None:
            raw_sim_text: str | None = None
            parsed_sim_body: Any = request.simulated_response_body
            if isinstance(request.simulated_response_body, str):
                raw_sim_text = request.simulated_response_body
                try:
                    import json

                    parsed_sim_body = json.loads(raw_sim_text)
                except Exception:
                    parsed_sim_body = raw_sim_text
            exchange = HTTPExchangeSnapshot(
                method=request.method.upper(),
                url=redact_url(request.url or "https://simulated.local/endpoint"),
                request_headers=redact_headers(request.headers),
                query_params=redact_object(request.query_params),
                request_body=redact_object(request.request_payload),
                response_status=request.simulated_response_status,
                response_headers=redact_headers(request.simulated_response_headers),
                response_body=redact_object(parsed_sim_body),
                raw_response_text=redact_text(raw_sim_text) if raw_sim_text is not None else None,
                elapsed_ms=0.0,
            )

        step_num = start_step_number
        # Strictly enforce bounded iterations while preventing duplicate tool calls
        max_tool_steps = max(1, self.max_iterations * 2)
        executed_signatures: set[tuple[str, str | None, str]] = set()

        for idx, plan_step in enumerate(plan):
            if idx >= max_tool_steps:
                break

            sig = (plan_step.tool_name, request.url, request.method.upper())
            if sig in executed_signatures:
                continue
            executed_signatures.add(sig)

            t0 = time.perf_counter()
            tool = plan_step.tool_name
            step_findings: list[DiagnosticFinding] = []
            details: dict[str, Any] = {}

            if tool == "log_analyzer":
                log_analysis = analyze_error_log(request.error_message)
                details = {
                    "status_codes_detected": log_analysis.get("status_codes", []),
                    "keywords": log_analysis.get("keywords", []),
                    "source_locations": log_analysis.get("source_locations", []),
                }

            elif tool == "openapi_parser" and request.openapi_spec is not None:
                try:
                    spec_dict = parse_spec_content(request.openapi_spec)
                    if request.url:
                        contract = extract_operation_contract(spec_dict, request.url, request.method)
                        details = {
                            "spec_title": contract.get("spec_title"),
                            "path_matched": contract.get("path_matched"),
                            "matched_path_template": contract.get("matched_path_template"),
                            "operation_found": contract.get("operation_found"),
                            "auth_required": contract.get("auth_required"),
                        }
                    else:
                        details = {"spec_parsed": True}
                except Exception as exc:
                    details = {"parse_error": str(exc)}

            elif tool == "http_client" and request.url:
                exchange = execute_diagnostic_request(
                    url=request.url,
                    method=request.method,
                    headers=request.headers,
                    query_params=request.query_params,
                    request_payload=request.request_payload,
                    raw_request_text=request.raw_request_text,
                    allow_localhost=request.allow_localhost,
                    timeout_seconds=min(
                        self.tool_timeout_seconds, get_settings().http_timeout_seconds
                    ),
                    transport=self.http_transport,
                )
                details = {
                    "response_status": exchange.response_status,
                    "elapsed_ms": exchange.elapsed_ms,
                    "error_type": exchange.error_type,
                }

            elif tool == "connectivity_diagnostics":
                step_findings = analyze_connectivity(
                    url=request.url,
                    method=request.method,
                    request_headers=request.headers,
                    exchange=exchange,
                    error_message=request.error_message,
                )
                details = {"findings_detected": [f.diagnostic_id for f in step_findings]}

            elif tool == "authentication_diagnostics":
                combined_scopes = list(request.required_scopes or [])
                for s in contract.get("required_scopes", []):
                    if s not in combined_scopes:
                        combined_scopes.append(s)
                step_findings = analyze_authentication(
                    url=request.url,
                    request_headers=request.headers,
                    query_params=request.query_params,
                    exchange=exchange,
                    required_scopes=combined_scopes or None,
                    expected_auth_scheme=contract.get("expected_auth_scheme"),
                    expected_key_location=contract.get("expected_key_location"),
                    expected_key_name=contract.get("expected_key_name"),
                )
                details = {"findings_detected": [f.diagnostic_id for f in step_findings]}

            elif tool == "request_diagnostics":
                step_findings = analyze_request(
                    url=request.url,
                    method=request.method,
                    headers=request.headers,
                    query_params=request.query_params,
                    request_payload=request.request_payload,
                    raw_request_text=request.raw_request_text,
                    exchange=exchange,
                    allowed_methods=contract.get("allowed_methods") or None,
                    required_headers=contract.get("required_headers") or None,
                    required_query_params=contract.get("required_query_params") or None,
                )
                details = {"findings_detected": [f.diagnostic_id for f in step_findings]}

            elif tool == "schema_diagnostics":
                step_findings = analyze_schema(
                    url=request.url,
                    method=request.method,
                    request_payload=request.request_payload,
                    exchange=exchange,
                    openapi_spec=request.openapi_spec,
                    request_schema=request.request_schema,
                    expected_response_schema=request.expected_response_schema,
                )
                details = {"findings_detected": [f.diagnostic_id for f in step_findings]}

            elif tool == "response_diagnostics":
                step_findings = analyze_response(
                    url=request.url,
                    method=request.method,
                    request_headers=request.headers,
                    query_params=request.query_params,
                    exchange=exchange,
                    expected_status=request.expected_status,
                )
                details = {"findings_detected": [f.diagnostic_id for f in step_findings]}

            elif tool == "repository_inspector" and request.repository_path:
                repository_analysis = inspect_repository(request.repository_path)
                details = {
                    "files_scanned": repository_analysis.files_scanned,
                    "languages": repository_analysis.languages_detected,
                    "clients": repository_analysis.client_libraries_detected,
                    "endpoints_found": len(repository_analysis.endpoints_discovered),
                }

            elif tool == "integration_diagnostics":
                step_findings = analyze_integration(
                    url=request.url,
                    method=request.method,
                    request_payload=request.request_payload,
                    exchange=exchange,
                    openapi_spec=request.openapi_spec,
                    expected_base_url=request.expected_base_url,
                    environment_vars=request.environment_vars,
                    repository_analysis=repository_analysis,
                )
                details = {"findings_detected": [f.diagnostic_id for f in step_findings]}

            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            if elapsed_ms > self.tool_timeout_seconds * 1000:
                raise ToolExecutionTimeoutError(
                    f"Tool '{tool}' exceeded timeout of {self.tool_timeout_seconds}s."
                )

            plan_step.completed = True
            findings.extend(step_findings)
            timeline.append(
                InvestigationStepRecord(
                    step_number=step_num,
                    phase="execute_tool",
                    tool_name=tool,
                    summary=(
                        f"Executed {tool} ({len(step_findings)} finding(s) produced)"
                        if step_findings
                        else f"Executed {tool} cleanly"
                    ),
                    details=details,
                    duration_ms=elapsed_ms,
                )
            )
            step_num += 1

        # Deduplicate and rank findings
        seen: set[tuple[str, str]] = set()
        deduped: list[DiagnosticFinding] = []
        for f in findings:
            key = (f.diagnostic_id, f.title)
            if key not in seen:
                seen.add(key)
                deduped.append(f)

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}
        deduped.sort(key=lambda item: (severity_order.get(item.severity, 5), -item.confidence))

        return {
            "findings": deduped,
            "timeline": timeline,
            "exchange": exchange,
            "contract": contract,
            "repository_analysis": repository_analysis,
            "log_analysis": log_analysis,
        }
