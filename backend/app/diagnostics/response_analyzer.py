"""Response diagnostics module.

Analyzes HTTP status codes, malformed JSON responses, unexpected response structures,
empty responses, server-side 5xx errors, rate limiting (429 / Retry-After),
pagination problems, and unexpected Content-Type headers.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qsl, urlparse

from backend.app.core.security import redact_text
from backend.app.schemas.diagnostics import DiagnosticFinding, HTTPExchangeSnapshot


def analyze_response(
    *,
    url: str | None = None,
    method: str = "GET",
    request_headers: dict[str, str] | None = None,
    query_params: dict[str, Any] | None = None,
    exchange: HTTPExchangeSnapshot | None = None,
    expected_status: int | None = None,
) -> list[DiagnosticFinding]:
    """Run deterministic diagnostics on an HTTP response snapshot."""
    findings: list[DiagnosticFinding] = []
    if exchange is None or exchange.response_status is None:
        return findings

    status = exchange.response_status
    resp_headers = {k.lower(): v for k, v in (exchange.response_headers or {}).items()}
    req_headers = {k.lower(): v for k, v in (request_headers or exchange.request_headers or {}).items()}
    content_type = resp_headers.get("content-type", "")
    raw_text = exchange.raw_response_text
    resp_body = exchange.response_body

    # 1. HTTP Status Code Analysis (404, 400, 409, 422, expected status mismatch)
    if expected_status and status != expected_status:
        findings.append(
            DiagnosticFinding(
                diagnostic_id="RES-001",
                category="response",
                severity="high" if status >= 400 else "medium",
                title=f"Unexpected HTTP Status Code ({status} vs Expected {expected_status})",
                description=f"The endpoint returned HTTP {status}, whereas HTTP {expected_status} was expected.",
                evidence=[
                    f"Actual HTTP status: {status}",
                    f"Expected HTTP status: {expected_status}",
                ],
                recommendation="Inspect the response payload and status-specific findings to determine why the operation did not return the expected status code.",
                confidence=0.98,
                status="confirmed",
            )
        )

    if status == 404:
        findings.append(
            DiagnosticFinding(
                diagnostic_id="RES-001",
                category="response",
                severity="high",
                title="HTTP 404 Not Found",
                description="The requested endpoint path or resource identifier does not exist on the target server.",
                evidence=[
                    "HTTP status: 404 Not Found",
                    f"Target URL: {exchange.url}",
                ],
                recommendation="Verify the endpoint route path, API version prefix (e.g. /v1/), base URL, and resource ID.",
                confidence=0.98,
                status="confirmed",
            )
        )
    elif status in (400, 422):
        detail_preview = ""
        if isinstance(resp_body, dict):
            detail_preview = str(
                resp_body.get("detail")
                or resp_body.get("message")
                or resp_body.get("error")
                or resp_body.get("errors")
                or ""
            )
        findings.append(
            DiagnosticFinding(
                diagnostic_id="RES-001",
                category="response",
                severity="high",
                title=f"HTTP {status} Client Validation Error",
                description=f"The server rejected the request due to bad request syntax or validation failure (HTTP {status}).",
                evidence=[
                    f"HTTP status: {status}",
                    *([f"Server error detail: {redact_text(detail_preview[:240])}"] if detail_preview else []),
                ],
                recommendation="Review request payload fields, data types, required query parameters, and headers against the API schema.",
                confidence=0.97,
                status="confirmed",
            )
        )

    # 2. Rate Limiting (HTTP 429 or zero RateLimit-Remaining)
    retry_after = resp_headers.get("retry-after")
    ratelimit_rem = resp_headers.get("x-ratelimit-remaining") or resp_headers.get("ratelimit-remaining")
    if status == 429 or ratelimit_rem == "0":
        findings.append(
            DiagnosticFinding(
                diagnostic_id="RES-006",
                category="response",
                severity="high" if status == 429 else "medium",
                title="API Rate Limit Exceeded (HTTP 429)" if status == 429 else "Rate Limit Quota Exhausted",
                description="The client has exceeded the allowed request rate or quota window configured by the API provider.",
                evidence=[
                    f"HTTP status: {status}",
                    *([f"Retry-After header: {retry_after}"] if retry_after else []),
                    *([f"RateLimit-Remaining: {ratelimit_rem}"] if ratelimit_rem is not None else []),
                ],
                recommendation="Implement exponential backoff with jitter honoring the 'Retry-After' header, and cache frequent read requests.",
                confidence=0.99,
                status="confirmed",
            )
        )

    # 3. Server-Side Errors (5xx)
    if 500 <= status <= 599:
        findings.append(
            DiagnosticFinding(
                diagnostic_id="RES-005",
                category="response",
                severity="critical",
                title=f"HTTP {status} Server-Side Failure",
                description=f"The upstream server encountered an internal failure or gateway error (HTTP {status}).",
                evidence=[
                    f"HTTP status: {status}",
                    *(
                        [f"Response preview: {redact_text(str(raw_text or resp_body)[:200])}"]
                        if (raw_text or resp_body)
                        else []
                    ),
                ],
                recommendation="Check upstream server logs, database connectivity, or payload edge cases triggering an unhandled server exception. Retry idempotent requests with exponential backoff.",
                confidence=0.98,
                status="confirmed",
            )
        )

    # 4. Unexpected Content-Type
    accept_hdr = req_headers.get("accept", "application/json")
    if content_type:
        ct_lower = content_type.lower()
        if "application/json" in accept_hdr.lower() and "text/html" in ct_lower:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="RES-008",
                    category="response",
                    severity="high",
                    title="Unexpected HTML Response Instead of JSON",
                    description=f"The client expected JSON, but the server returned '{content_type}'. This commonly happens when hitting a frontend route, SSO login redirect page, or reverse-proxy HTML error page.",
                    evidence=[
                        f"Request Accept header: {accept_hdr}",
                        f"Response Content-Type: {content_type}",
                        f"HTTP status: {status}",
                    ],
                    recommendation="Verify the base URL points to the API server rather than the web frontend, and check whether an authentication proxy redirected the request to an HTML login page.",
                    confidence=0.97,
                    status="confirmed",
                )
            )
        elif "application/json" not in ct_lower and isinstance(raw_text, str) and raw_text.strip().startswith(("{", "[")):
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="RES-008",
                    category="response",
                    severity="medium",
                    title="JSON Body Served With Non-JSON Content-Type Header",
                    description=f"The response body appears to be JSON, but the Content-Type header is '{content_type}'. Strict HTTP clients may skip automatic JSON parsing.",
                    evidence=[
                        f"Response Content-Type: {content_type}",
                        f"Body prefix: {redact_text(raw_text.strip()[:40])}",
                    ],
                    recommendation="Configure the API endpoint to return 'Content-Type: application/json; charset=utf-8'.",
                    confidence=0.94,
                    status="confirmed",
                )
            )

    # 5. Malformed JSON in Response
    if isinstance(raw_text, str) and raw_text.strip():
        if "json" in content_type.lower():
            try:
                json.loads(raw_text)
            except json.JSONDecodeError as exc:
                findings.append(
                    DiagnosticFinding(
                        diagnostic_id="RES-002",
                        category="response",
                        severity="critical",
                        title="Malformed JSON in Server Response",
                        description=f"The response declared '{content_type}' but its body is not valid JSON ({exc.msg} at line {exc.lineno}, col {exc.colno}).",
                        evidence=[
                            f"Response Content-Type: {content_type}",
                            f"JSONDecodeError: {exc.msg} (line {exc.lineno}, col {exc.colno})",
                            f"Response preview: {redact_text(raw_text[:120])}",
                        ],
                        recommendation="Check for truncated chunked responses, reverse proxy error text appended to JSON, or corrupt serialization on the server.",
                        confidence=1.0,
                        status="confirmed",
                    )
                )

    # 6. Empty Responses
    is_empty_body = (raw_text is None or raw_text == "") and resp_body in (None, "")
    if is_empty_body and status == 200 and method.upper() not in ("HEAD", "OPTIONS"):
        findings.append(
            DiagnosticFinding(
                diagnostic_id="RES-004",
                category="response",
                severity="medium",
                title="Empty Response Body on HTTP 200 OK",
                description="The server returned HTTP 200 OK with an empty body. Clients calling response.json() on an empty 200 response will raise a JSON parse exception.",
                evidence=[
                    "HTTP status: 200 OK",
                    "Response body length: 0 bytes",
                ],
                recommendation="Return HTTP 204 No Content for intentionally empty responses, or return a valid JSON object (e.g. '{}') for HTTP 200.",
                confidence=0.95,
                status="confirmed",
            )
        )

    # 7. Unexpected Response Structure (e.g., error envelope inside HTTP 200 OK)
    if 200 <= status < 300 and isinstance(resp_body, dict):
        has_error_flag = (
            resp_body.get("success") is False
            or resp_body.get("ok") is False
            or (resp_body.get("error") not in (None, False, "", {}) and "data" not in resp_body)
            or (isinstance(resp_body.get("errors"), list) and len(resp_body["errors"]) > 0)
        )
        if has_error_flag:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="RES-003",
                    category="response",
                    severity="high",
                    title="Application Error Masked Behind HTTP 200 OK",
                    description="The server returned a 2xx success status code, but the JSON payload contains an explicit failure flag or error object.",
                    evidence=[
                        f"HTTP status: {status}",
                        f"Error keys detected in 2xx payload: {[k for k in ('success', 'ok', 'error', 'errors') if k in resp_body]}",
                    ],
                    recommendation="Inspect application-level 'error'/'errors'/'success' fields in the response body in addition to checking HTTP status codes.",
                    confidence=0.93,
                    status="confirmed",
                )
            )

    # 8. Pagination Problems
    combined_query: dict[str, Any] = {}
    if url:
        for k, v in parse_qsl(urlparse(url).query, keep_blank_values=True):
            combined_query[k.lower()] = v
    if query_params:
        for k, v in query_params.items():
            combined_query[k.lower()] = v

    page_val = combined_query.get("page")
    limit_val = combined_query.get("limit") or combined_query.get("per_page") or combined_query.get("page_size")
    if page_val is not None:
        try:
            if int(page_val) <= 0:
                findings.append(
                    DiagnosticFinding(
                        diagnostic_id="RES-007",
                        category="response",
                        severity="medium",
                        title="Invalid Non-Positive Page Number in Pagination Request",
                        description=f"Pagination query parameter 'page={page_val}' is less than or equal to 0, whereas most 1-indexed paginated APIs require page >= 1.",
                        evidence=[f"Query parameter: page={page_val}"],
                        recommendation="Use 1-based page indexing (page=1) or verify whether the API uses offset/cursor pagination.",
                        confidence=0.91,
                        status="probable",
                    )
                )
        except ValueError:
            pass

    if isinstance(resp_body, dict):
        items = resp_body.get("items") or resp_body.get("data") or resp_body.get("results")
        total = resp_body.get("total") or resp_body.get("total_count") or resp_body.get("count")
        next_cursor = resp_body.get("next") or resp_body.get("next_cursor") or resp_body.get("has_more")
        if (
            isinstance(items, list)
            and isinstance(total, int)
            and total > len(items) > 0
            and next_cursor is None
            and "link" not in resp_headers
            and not page_val
        ):
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="RES-007",
                    category="response",
                    severity="low",
                    title="Truncated Paginated Collection Without Next Cursor or Page Parameter",
                    description=f"The response returned {len(items)} items out of {total} total records, but no pagination parameters or next-page cursor were used.",
                    evidence=[
                        f"Items returned in page: {len(items)}",
                        f"Total records reported: {total}",
                        *([f"Limit parameter: {limit_val}"] if limit_val else []),
                    ],
                    recommendation="Iterate through pages using 'page'/'offset' or cursor parameters until all records are retrieved.",
                    confidence=0.86,
                    status="probable",
                )
            )

    return findings
