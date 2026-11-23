"""Integration diagnostics module.

Analyzes base URL mismatches, environment variable configuration errors,
missing configuration, endpoint path typos against OpenAPI specs,
inconsistent API versions, frontend/backend casing mismatches, and SDK misconfigurations.
"""

from __future__ import annotations

import difflib
import re
from typing import Any
from urllib.parse import urlparse

from backend.app.core.security import redact_url
from backend.app.schemas.diagnostics import (
    DiagnosticFinding,
    HTTPExchangeSnapshot,
    RepositoryAnalysisResult,
)
from backend.app.tools.openapi_parser import extract_operation_contract, parse_spec_content

VERSION_SEGMENT_RE = re.compile(r"/(v\d+(?:\.\d+)?)(?=/|$)", re.IGNORECASE)


def _detect_casing_style(keys: list[str]) -> str:
    snake = sum(1 for k in keys if "_" in k and k == k.lower())
    camel = sum(1 for k in keys if "_" not in k and any(c.isupper() for c in k[1:]))
    if snake > 0 and camel == 0:
        return "snake_case"
    if camel > 0 and snake == 0:
        return "camelCase"
    return "mixed"


def analyze_integration(
    *,
    url: str | None = None,
    method: str = "GET",
    request_payload: Any | None = None,
    exchange: HTTPExchangeSnapshot | None = None,
    openapi_spec: str | dict[str, Any] | None = None,
    expected_base_url: str | None = None,
    environment_vars: dict[str, str] | None = None,
    repository_analysis: RepositoryAnalysisResult | None = None,
) -> list[DiagnosticFinding]:
    """Run deterministic integration diagnostics combining HTTP, spec, env, and repo evidence."""
    findings: list[DiagnosticFinding] = []
    env_map = environment_vars or {}

    contract: dict[str, Any] | None = None
    if openapi_spec is not None and url:
        try:
            spec_dict = parse_spec_content(openapi_spec)
            contract = extract_operation_contract(spec_dict, url, method)
        except Exception:
            contract = None

    # 1. Incorrect Base URLs
    known_base_urls: list[str] = []
    if expected_base_url:
        known_base_urls.append(expected_base_url.rstrip("/"))
    if contract and contract.get("base_urls"):
        known_base_urls.extend(u.rstrip("/") for u in contract["base_urls"])

    if url and known_base_urls:
        target_parsed = urlparse(url)
        target_origin = f"{target_parsed.scheme}://{target_parsed.netloc}"
        matches_any_base = any(url.startswith(b) for b in known_base_urls)
        if not matches_any_base:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="INT-001",
                    category="integration",
                    severity="high",
                    title="Target Base URL Does Not Match Documented Server Base URL",
                    description=f"Request URL '{redact_url(url)}' does not match any configured or documented base URL.",
                    evidence=[
                        f"Request origin/URL: {redact_url(target_origin)}",
                        f"Expected base URL(s): {', '.join(known_base_urls)}",
                    ],
                    recommendation=f"Update the client base URL configuration to match '{known_base_urls[0]}'.",
                    confidence=0.94,
                    status="confirmed",
                )
            )

    # 2. Incorrect Endpoint Paths (404 or unmatched OpenAPI path with close similarity)
    if url and contract and not contract["path_matched"] and contract.get("all_paths"):
        actual_path = urlparse(url).path or "/"
        all_paths: list[str] = contract["all_paths"]
        close_matches = difflib.get_close_matches(actual_path, all_paths, n=2, cutoff=0.55)
        findings.append(
            DiagnosticFinding(
                diagnostic_id="INT-004",
                category="integration",
                severity="high",
                title="Undocumented Endpoint Path in API Request",
                description=f"Path '{actual_path}' does not exist in the OpenAPI specification."
                + (f" Did you mean '{close_matches[0]}'?" if close_matches else ""),
                evidence=[
                    f"Requested path: {actual_path}",
                    *(
                        [f"Closest documented path(s): {', '.join(close_matches)}"]
                        if close_matches
                        else [f"Documented paths ({len(all_paths)}): {', '.join(all_paths[:6])}"]
                    ),
                ],
                recommendation=(
                    f"Update the endpoint path from '{actual_path}' to '{close_matches[0]}'."
                    if close_matches
                    else "Align the request path with one of the paths defined in the OpenAPI contract."
                ),
                confidence=0.96,
                status="confirmed",
            )
        )

    # 3. Environment Variable Mismatches & Missing Configuration
    if env_map:
        empty_vars = [k for k, v in env_map.items() if v is None or str(v).strip() == ""]
        placeholder_vars = [
            k
            for k, v in env_map.items()
            if str(v).strip().lower() in ("changeme", "your_api_key", "todo", "undefined", "null", "xxx")
        ]
        if empty_vars or placeholder_vars:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="INT-002",
                    category="integration",
                    severity="high",
                    title="Unset or Placeholder Environment Variable(s)",
                    description="One or more integration environment variables are blank or contain placeholder values.",
                    evidence=[
                        *([f"Empty environment variables: {', '.join(empty_vars)}"] if empty_vars else []),
                        *(
                            [f"Placeholder environment variables: {', '.join(placeholder_vars)}"]
                            if placeholder_vars
                            else []
                        ),
                    ],
                    recommendation="Populate the missing environment variables in your .env file or runtime secret manager.",
                    confidence=0.97,
                    status="confirmed",
                )
            )

    # 4. Inconsistent API Versions
    versions_found: set[str] = set()
    if url:
        for m in VERSION_SEGMENT_RE.findall(urlparse(url).path):
            versions_found.add(m.lower())
    if contract and contract.get("base_urls"):
        for b_url in contract["base_urls"]:
            for m in VERSION_SEGMENT_RE.findall(urlparse(b_url).path):
                versions_found.add(m.lower())
    if repository_analysis:
        for ep in repository_analysis.endpoints_discovered:
            for m in VERSION_SEGMENT_RE.findall(ep):
                versions_found.add(m.lower())

    if len(versions_found) > 1:
        findings.append(
            DiagnosticFinding(
                diagnostic_id="INT-005",
                category="integration",
                severity="medium",
                title="Inconsistent API Version Prefixes Detected",
                description=f"Multiple API version prefixes ({', '.join(sorted(versions_found))}) were detected across the request, specification, or repository.",
                evidence=[f"Version prefixes observed: {', '.join(sorted(versions_found))}"],
                recommendation="Standardize all API client endpoints on a single consistent version prefix.",
                confidence=0.90,
                status="probable",
            )
        )

    # 5. Frontend / Backend Casing & Contract Integration Mismatches
    if isinstance(request_payload, dict) and contract and isinstance(contract.get("request_schema"), dict):
        schema_props = contract["request_schema"].get("properties")
        if isinstance(schema_props, dict) and schema_props and request_payload:
            req_style = _detect_casing_style(list(request_payload.keys()))
            spec_style = _detect_casing_style(list(schema_props.keys()))
            if req_style != "mixed" and spec_style != "mixed" and req_style != spec_style:
                findings.append(
                    DiagnosticFinding(
                        diagnostic_id="INT-006",
                        category="integration",
                        severity="high",
                        title=f"Frontend/Backend Field Casing Mismatch ({req_style} vs {spec_style})",
                        description=f"The request payload uses {req_style} keys, whereas the backend schema expects {spec_style} keys.",
                        evidence=[
                            f"Request payload keys ({req_style}): {sorted(request_payload.keys())}",
                            f"Backend schema keys ({spec_style}): {sorted(schema_props.keys())}",
                        ],
                        recommendation=f"Transform payload keys from {req_style} to {spec_style} before serializing the request.",
                        confidence=0.95,
                        status="confirmed",
                    )
                )

    # 6. Include repository-level diagnostic findings (e.g. INT-003, INT-007)
    if repository_analysis and repository_analysis.diagnostic_findings:
        findings.extend(repository_analysis.diagnostic_findings)

    return findings
