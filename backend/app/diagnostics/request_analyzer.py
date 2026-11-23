"""Request diagnostics module.

Analyzes HTTP methods, required headers, Content-Type mismatches, malformed JSON,
unexpanded path parameters, query parameters, payload structures, and serialization bugs.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlparse

from backend.app.core.security import redact_text, redact_url
from backend.app.schemas.diagnostics import DiagnosticFinding, HTTPExchangeSnapshot

UNEXPANDED_PATH_PARAM_RE = re.compile(r"(\{[A-Za-z0-9_.-]+\}|:[A-Za-z_][A-Za-z0-9_]*)(?=/|$)")
SINGLE_QUOTED_DICT_RE = re.compile(r"^\s*\{'[A-Za-z0-9_]+'\s*:")


def analyze_request(
    *,
    url: str | None,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    query_params: dict[str, Any] | None = None,
    request_payload: Any | None = None,
    raw_request_text: str | None = None,
    exchange: HTTPExchangeSnapshot | None = None,
    allowed_methods: list[str] | None = None,
    required_headers: list[str] | None = None,
    required_query_params: list[str] | None = None,
) -> list[DiagnosticFinding]:
    """Run deterministic diagnostics on an outgoing HTTP request configuration."""
    findings: list[DiagnosticFinding] = []
    upper_method = (method or "GET").strip().upper()
    lower_headers = {k.lower(): v for k, v in (headers or {}).items()}
    resp_status = exchange.response_status if exchange else None
    resp_headers = {k.lower(): v for k, v in (exchange.response_headers or {}).items()} if exchange else {}

    # 1. Incorrect HTTP method
    if resp_status == 405 or (
        allowed_methods and upper_method not in {m.upper() for m in allowed_methods}
    ):
        server_allow = resp_headers.get("allow")
        evidence = [f"Request method used: {upper_method}"]
        if resp_status == 405:
            evidence.append("Server returned HTTP 405 Method Not Allowed.")
        if server_allow:
            evidence.append(f"Response 'Allow' header: {server_allow}")
        if allowed_methods:
            evidence.append(f"Specification allowed methods: {', '.join(allowed_methods)}")
        findings.append(
            DiagnosticFinding(
                diagnostic_id="REQ-001",
                category="request",
                severity="high",
                title="Incorrect or Disallowed HTTP Method",
                description=f"HTTP method '{upper_method}' is not supported by the target endpoint.",
                evidence=evidence,
                recommendation=f"Switch the request method to one of the supported methods ({server_allow or ', '.join(allowed_methods or ['POST', 'GET'])}).",
                confidence=0.99,
                status="confirmed",
            )
        )
    elif upper_method in ("GET", "HEAD") and (
        request_payload not in (None, "", {}, []) or (raw_request_text and raw_request_text.strip())
    ):
        findings.append(
            DiagnosticFinding(
                diagnostic_id="REQ-001",
                category="request",
                severity="medium",
                title=f"Request Body Sent With {upper_method} Method",
                description=f"A request payload was provided for a {upper_method} request. Many HTTP proxies, gateways, and servers ignore or reject bodies on {upper_method} requests.",
                evidence=[f"Method: {upper_method}", "Non-empty request payload attached."],
                recommendation="Move parameters to the URL query string for GET requests, or change the HTTP method to POST/PUT/PATCH.",
                confidence=0.92,
                status="confirmed",
            )
        )

    # 2. Missing required headers
    missing_hdrs: list[str] = []
    if required_headers:
        for req_h in required_headers:
            if req_h.lower() not in lower_headers:
                missing_hdrs.append(req_h)
    has_body = request_payload not in (None, "") or bool(raw_request_text and raw_request_text.strip())
    if has_body and "content-type" not in lower_headers:
        missing_hdrs.append("Content-Type")
    if missing_hdrs:
        findings.append(
            DiagnosticFinding(
                diagnostic_id="REQ-002",
                category="request",
                severity="high" if resp_status in (400, 415, 422) else "medium",
                title="Missing Required Request Header(s)",
                description=f"The request is missing required HTTP header(s): {', '.join(missing_hdrs)}.",
                evidence=[f"Missing headers: {', '.join(missing_hdrs)}"],
                recommendation=f"Include the missing header(s) ({', '.join(missing_hdrs)}) in the request configuration.",
                confidence=0.95,
                status="confirmed",
            )
        )

    # 3. Incorrect Content-Type
    content_type = lower_headers.get("content-type", "")
    if resp_status == 415:
        findings.append(
            DiagnosticFinding(
                diagnostic_id="REQ-003",
                category="request",
                severity="high",
                title="HTTP 415 Unsupported Media Type (Incorrect Content-Type)",
                description=f"The server rejected the payload media type ('{content_type or 'unspecified'}').",
                evidence=[
                    "Server returned HTTP 415 Unsupported Media Type.",
                    f"Request Content-Type: '{content_type or 'missing'}'",
                ],
                recommendation="Set 'Content-Type: application/json' (or the media type specified by the endpoint's OpenAPI contract).",
                confidence=0.99,
                status="confirmed",
            )
        )
    elif has_body and content_type and isinstance(request_payload, (dict, list)) and "json" not in content_type.lower():
        findings.append(
            DiagnosticFinding(
                diagnostic_id="REQ-003",
                category="request",
                severity="high",
                title="Content-Type Mismatch for Structured JSON Payload",
                description=f"A structured JSON payload is being sent with Content-Type '{content_type}'.",
                evidence=[
                    f"Content-Type header: {content_type}",
                    f"Payload type: {type(request_payload).__name__}",
                ],
                recommendation="Change the Content-Type header to 'application/json'.",
                confidence=0.93,
                status="confirmed",
            )
        )

    # 4. Invalid JSON & 8. Serialization Problems
    raw_to_check = raw_request_text
    if raw_to_check is None and isinstance(request_payload, str):
        raw_to_check = request_payload

    if raw_to_check and raw_to_check.strip():
        text_val = raw_to_check.strip()
        if "[object Object]" in text_val:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="REQ-008",
                    category="request",
                    severity="critical",
                    title="JavaScript '[object Object]' Serialization Bug",
                    description="The request payload contains literal '[object Object]', indicating a JavaScript object was coerced to a string without JSON.stringify().",
                    evidence=["Request body contains '[object Object]'."],
                    recommendation="Serialize the JavaScript object with JSON.stringify(payload) before passing it to fetch() or your HTTP client.",
                    confidence=0.99,
                    status="confirmed",
                )
            )
        elif SINGLE_QUOTED_DICT_RE.match(text_val):
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="REQ-008",
                    category="request",
                    severity="high",
                    title="Python Dict Stringification Instead of JSON Serialization",
                    description="The request body uses single-quoted keys (Python str(dict) format) instead of valid double-quoted JSON.",
                    evidence=[f"Payload prefix: {redact_text(text_val[:60])}"],
                    recommendation="Use json.dumps(payload) or pass json=payload in httpx/requests rather than data=str(payload).",
                    confidence=0.97,
                    status="confirmed",
                )
            )
        elif "json" in content_type.lower() or text_val.startswith(("{", "[")):
            try:
                parsed_json = json.loads(text_val)
                if isinstance(parsed_json, str) and parsed_json.strip().startswith(("{", "[")):
                    findings.append(
                        DiagnosticFinding(
                            diagnostic_id="REQ-008",
                            category="request",
                            severity="high",
                            title="Double-Encoded JSON String Payload",
                            description="The request body is a JSON-encoded string containing another JSON object, typically caused by calling JSON.stringify() or json.dumps() twice.",
                            evidence=["json.loads(body) produced a string beginning with '{' or '['."],
                            recommendation="Remove redundant JSON serialization when passing payloads to clients like Axios or httpx(json=...).",
                            confidence=0.96,
                            status="confirmed",
                        )
                    )
            except json.JSONDecodeError as exc:
                findings.append(
                    DiagnosticFinding(
                        diagnostic_id="REQ-004",
                        category="request",
                        severity="critical",
                        title="Malformed JSON in Request Payload",
                        description=f"The request body is not valid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}.",
                        evidence=[
                            f"JSONDecodeError: {exc.msg} (line {exc.lineno}, col {exc.colno})",
                        ],
                        recommendation="Fix syntax errors (trailing commas, unquoted keys, or unescaped quotes) in the JSON payload.",
                        confidence=1.0,
                        status="confirmed",
                    )
                )

    # 5. Missing parameters (unexpanded path templates or missing required query params)
    if url:
        parsed_url = urlparse(url)
        unexpanded = UNEXPANDED_PATH_PARAM_RE.findall(parsed_url.path)
        if unexpanded:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="REQ-005",
                    category="request",
                    severity="high",
                    title="Unexpanded Path Template Parameter in URL",
                    description=f"The URL path contains uninterpolated template placeholder(s): {', '.join(unexpanded)}.",
                    evidence=[
                        f"URL path: {redact_url(parsed_url.path)}",
                        f"Unexpanded placeholders: {', '.join(unexpanded)}",
                    ],
                    recommendation="Replace path template placeholders with concrete resource identifiers before issuing the request.",
                    confidence=0.98,
                    status="confirmed",
                )
            )

    combined_query: dict[str, Any] = {}
    if url:
        for k, v in parse_qsl(urlparse(url).query, keep_blank_values=True):
            combined_query[k] = v
    if query_params:
        combined_query.update(query_params)

    if required_query_params:
        missing_q = [q for q in required_query_params if q not in combined_query or combined_query[q] in (None, "")]
        if missing_q:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="REQ-005",
                    category="request",
                    severity="high",
                    title="Missing Required Query Parameter(s)",
                    description=f"Required query parameter(s) were omitted or empty: {', '.join(missing_q)}.",
                    evidence=[f"Missing query parameters: {', '.join(missing_q)}"],
                    recommendation=f"Provide non-empty values for query parameter(s): {', '.join(missing_q)}.",
                    confidence=0.96,
                    status="confirmed",
                )
            )

    # 6. Incorrect query parameters (e.g., 'undefined', 'null', 'NaN' serialized into URL)
    bad_query_entries = [
        f"{k}={v}"
        for k, v in combined_query.items()
        if str(v).strip() in ("undefined", "NaN", "[object Object]")
    ]
    if bad_query_entries:
        findings.append(
            DiagnosticFinding(
                diagnostic_id="REQ-006",
                category="request",
                severity="high",
                title="Invalid Serialized Literals in Query Parameters",
                description="One or more query parameters contain literal 'undefined', 'NaN', or '[object Object]' values.",
                evidence=[f"Suspicious query parameters: {', '.join(bad_query_entries)}"],
                recommendation="Validate state variables before constructing query strings so undefined or NaN values are omitted or defaulted.",
                confidence=0.97,
                status="confirmed",
            )
        )

    # 7. Invalid request payload on mutating methods
    if upper_method in ("POST", "PUT", "PATCH") and not has_body and resp_status in (400, 422):
        findings.append(
            DiagnosticFinding(
                diagnostic_id="REQ-007",
                category="request",
                severity="high",
                title=f"Empty Request Payload on {upper_method} Request",
                description=f"The {upper_method} request was sent without a body and the server responded with HTTP {resp_status}.",
                evidence=[
                    f"HTTP method: {upper_method}",
                    "Request payload: empty/None",
                    f"Response status: HTTP {resp_status}",
                ],
                recommendation=f"Provide the required JSON payload body for this {upper_method} endpoint.",
                confidence=0.93,
                status="probable",
            )
        )

    return findings
