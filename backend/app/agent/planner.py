"""Agent Step 1 & Step 2: Task understanding and dynamic investigation planner."""

from __future__ import annotations

from typing import Any

from backend.app.schemas.diagnostics import InvestigationPlanStep, InvestigationRequest


def extract_task_context(request: InvestigationRequest) -> dict[str, Any]:
    """Step 1: Parse the investigation request and natural-language prompt to extract context."""
    prompt = (request.prompt or "").strip()
    lower_prompt = prompt.lower()

    inferred_focus: list[str] = []
    if any(k in lower_prompt for k in ("401", "403", "auth", "token", "jwt", "key", "bearer", "oauth")):
        inferred_focus.append("authentication")
    if any(k in lower_prompt for k in ("schema", "openapi", "swagger", "422", "400", "payload", "type", "required")):
        inferred_focus.append("schema")
    if any(k in lower_prompt for k in ("timeout", "dns", "ssl", "tls", "cert", "refused", "cors", "redirect")):
        inferred_focus.append("connectivity")
    if any(k in lower_prompt for k in ("500", "502", "503", "429", "rate", "html", "json", "empty", "response")):
        inferred_focus.append("response")
    if any(k in lower_prompt for k in ("repo", "code", "env", "frontend", "backend", "version", "404")):
        inferred_focus.append("integration")

    title = request.title
    if not title:
        if request.url:
            title = f"{request.method.upper()} {request.url}"
        elif prompt:
            title = prompt[:80]
        elif request.repository_path:
            title = f"Repository Investigation: {request.repository_path}"
        else:
            title = "API Diagnostic Investigation"

    return {
        "title": title,
        "prompt": prompt,
        "inferred_focus": inferred_focus or ["general"],
        "has_url": bool(request.url and request.url.strip()),
        "has_openapi_spec": request.openapi_spec is not None,
        "has_schemas": bool(request.request_schema or request.expected_response_schema),
        "has_repository": bool(request.repository_path and request.repository_path.strip()),
        "has_error_log": bool(request.error_message and request.error_message.strip()),
        "has_simulated_response": request.simulated_response_status is not None,
    }


def build_investigation_plan(
    request: InvestigationRequest,
    context: dict[str, Any],
) -> list[InvestigationPlanStep]:
    """Step 2: Select and order the diagnostic tools relevant to the problem context."""
    plan: list[InvestigationPlanStep] = []
    idx = 1

    if context["has_error_log"]:
        plan.append(
            InvestigationPlanStep(
                step_index=idx,
                tool_name="log_analyzer",
                rationale="Extract HTTP status codes, exception signatures, and file references from error output.",
            )
        )
        idx += 1

    if context["has_openapi_spec"]:
        plan.append(
            InvestigationPlanStep(
                step_index=idx,
                tool_name="openapi_parser",
                rationale="Parse OpenAPI/Swagger specification to extract endpoint contract, security schemes, and schemas.",
            )
        )
        idx += 1

    if context["has_url"] and request.execute_live_request and not context["has_simulated_response"]:
        plan.append(
            InvestigationPlanStep(
                step_index=idx,
                tool_name="http_client",
                rationale=f"Execute SSRF-protected {request.method.upper()} request against target endpoint and capture timing/headers/payload.",
            )
        )
        idx += 1

    if context["has_url"] or context["has_error_log"]:
        plan.append(
            InvestigationPlanStep(
                step_index=idx,
                tool_name="connectivity_diagnostics",
                rationale="Inspect URL validity, DNS resolution, TLS handshake, redirect chains, CORS headers, and proxy behavior.",
            )
        )
        idx += 1

    plan.append(
        InvestigationPlanStep(
            step_index=idx,
            tool_name="authentication_diagnostics",
            rationale="Inspect Authorization headers, API key placement, JWT claim metadata/expiration, OAuth errors, and 401/403 status.",
        )
    )
    idx += 1

    plan.append(
        InvestigationPlanStep(
            step_index=idx,
            tool_name="request_diagnostics",
            rationale="Validate HTTP method, required headers, Content-Type, JSON syntax, path/query parameters, and serialization.",
        )
    )
    idx += 1

    if context["has_openapi_spec"] or context["has_schemas"] or request.request_payload is not None:
        plan.append(
            InvestigationPlanStep(
                step_index=idx,
                tool_name="schema_diagnostics",
                rationale="Validate request and response payloads against JSON Schema and OpenAPI contract requirements.",
            )
        )
        idx += 1

    plan.append(
        InvestigationPlanStep(
            step_index=idx,
            tool_name="response_diagnostics",
            rationale="Analyze response status code, JSON well-formedness, Content-Type headers, rate limits, and pagination.",
        )
    )
    idx += 1

    if context["has_repository"]:
        plan.append(
            InvestigationPlanStep(
                step_index=idx,
                tool_name="repository_inspector",
                rationale="Scan repository in read-only mode for API client calls, endpoints, environment variables, and SDK settings.",
            )
        )
        idx += 1

    plan.append(
        InvestigationPlanStep(
            step_index=idx,
            tool_name="integration_diagnostics",
            rationale="Cross-check base URLs, endpoint paths, API versions, field casing, and environment variable consistency.",
        )
    )

    return plan
