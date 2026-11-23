"""Comprehensive unit tests for all six deterministic diagnostic modules."""

from __future__ import annotations

import base64
import json
import time

from backend.app.diagnostics.authentication import analyze_authentication
from backend.app.diagnostics.connectivity import analyze_connectivity
from backend.app.diagnostics.integration_analyzer import analyze_integration
from backend.app.diagnostics.request_analyzer import analyze_request
from backend.app.diagnostics.response_analyzer import analyze_response
from backend.app.diagnostics.schema_validator import (
    analyze_schema,
    validate_payload_against_schema,
)
from backend.app.schemas.diagnostics import HTTPExchangeSnapshot
from backend.app.tools.repository_inspector import inspect_repository


def _make_jwt(payload: dict) -> str:
    hdr = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    pld = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{hdr}.{pld}.signature_stub"


def test_connectivity_diagnostics() -> None:
    # 1. Invalid URL
    f_url = analyze_connectivity(url="ftp://bad url")
    assert any(f.diagnostic_id == "CONN-005" for f in f_url)

    # 2. DNS failure
    f_dns = analyze_connectivity(
        url="https://nonexistent.invalid/v1",
        error_message="[Errno 11001] getaddrinfo failed",
    )
    assert any(f.diagnostic_id == "CONN-001" for f in f_dns)

    # 3. Connection refused
    f_ref = analyze_connectivity(
        url="https://api.example.com/v1",
        error_message="Connection refused (ECONNREFUSED)",
    )
    assert any(f.diagnostic_id == "CONN-002" for f in f_ref)

    # 4. Timeout
    f_to = analyze_connectivity(
        url="https://api.example.com/v1",
        error_message="ReadTimeout: timed out waiting for response",
    )
    assert any(f.diagnostic_id == "CONN-003" for f in f_to)

    # 5. SSL/TLS issue
    f_ssl = analyze_connectivity(
        url="https://api.example.com/v1",
        error_message="SSL: CERTIFICATE_VERIFY_FAILED self-signed certificate",
    )
    assert any(f.diagnostic_id == "CONN-004" for f in f_ssl)

    # 6. Redirect downgrade & CORS wildcard conflict & Proxy 407
    ex = HTTPExchangeSnapshot(
        method="GET",
        url="http://api.example.com/v1",
        response_status=407,
        response_headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
            "Via": "1.1 corp-proxy",
        },
        redirect_chain=["https://api.example.com/v1"],
    )
    f_red = analyze_connectivity(
        url="https://api.example.com/v1",
        request_headers={"Origin": "https://app.example.com"},
        exchange=ex,
    )
    ids = {f.diagnostic_id for f in f_red}
    assert "CONN-006" in ids
    assert "CONN-007" in ids
    assert "CONN-008" in ids


def test_authentication_diagnostics() -> None:
    # 1. Missing auth on 401
    ex_401 = HTTPExchangeSnapshot(
        method="GET",
        url="https://api.example.com/v1/users",
        response_status=401,
    )
    f_missing = analyze_authentication(exchange=ex_401)
    assert any(f.diagnostic_id == "AUTH-001" for f in f_missing)
    assert any(f.diagnostic_id == "AUTH-008" for f in f_missing)

    # 2. Expired JWT & missing scope
    expired_token = _make_jwt({"sub": "u1", "exp": int(time.time()) - 3600, "scope": "read:users"})
    f_jwt = analyze_authentication(
        request_headers={"Authorization": f"Bearer {expired_token}"},
        required_scopes=["read:users", "write:users"],
        exchange=ex_401,
    )
    jwt_ids = {f.diagnostic_id for f in f_jwt}
    assert "AUTH-003" in jwt_ids
    assert "AUTH-007" in jwt_ids
    # Confirm raw token is never exposed in evidence
    for finding in f_jwt:
        for ev in finding.evidence:
            assert expired_token not in ev

    # 3. Duplicate Bearer prefix & token in query string & OAuth error
    ex_oauth = HTTPExchangeSnapshot(
        method="POST",
        url="https://api.example.com/oauth/token?api_key=secret123",
        response_status=401,
        response_body={"error": "invalid_grant", "error_description": "Authorization code expired"},
    )
    f_dup = analyze_authentication(
        url="https://api.example.com/oauth/token?api_key=secret123",
        request_headers={"Authorization": "Bearer Bearer my_token_value"},
        exchange=ex_oauth,
    )
    dup_ids = {f.diagnostic_id for f in f_dup}
    assert "AUTH-004" in dup_ids
    assert "AUTH-005" in dup_ids
    assert "AUTH-006" in dup_ids


def test_request_diagnostics() -> None:
    ex_405 = HTTPExchangeSnapshot(
        method="DELETE",
        url="https://api.example.com/v1/users/{id}",
        response_status=405,
        response_headers={"Allow": "GET, POST"},
    )
    findings = analyze_request(
        url="https://api.example.com/v1/users/{id}",
        method="DELETE",
        headers={"Content-Type": "text/plain"},
        query_params={"filter": "undefined"},
        request_payload={"a": 1},
        raw_request_text="{bad json",
        exchange=ex_405,
        allowed_methods=["GET", "POST"],
        required_headers=["X-Request-ID"],
        required_query_params=["tenant_id"],
    )
    ids = {f.diagnostic_id for f in findings}
    assert "REQ-001" in ids
    assert "REQ-002" in ids
    assert "REQ-003" in ids
    assert "REQ-004" in ids
    assert "REQ-005" in ids
    assert "REQ-006" in ids

    # Serialization bug: [object Object]
    f_ser = analyze_request(
        url="https://api.example.com/v1/items",
        method="POST",
        raw_request_text="[object Object]",
    )
    assert any(f.diagnostic_id == "REQ-008" for f in f_ser)


def test_schema_validation_diagnostics() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["customer_id", "amount", "currency"],
        "properties": {
            "customer_id": {"type": "string"},
            "amount": {"type": "number"},
            "currency": {"type": "string", "enum": ["USD", "EUR"]},
        },
    }
    bad_payload = {
        "amount": "not_a_number",
        "currency": "JPY",
        "extra_field": True,
    }
    findings = validate_payload_against_schema(bad_payload, schema)
    ids = {f.diagnostic_id for f in findings}
    assert "SCH-001" in ids  # missing customer_id
    assert "SCH-002" in ids  # unexpected extra_field
    assert "SCH-003" in ids  # amount wrong type
    assert "SCH-004" in ids  # currency enum mismatch

    # Response contract mismatch via analyze_schema
    ex = HTTPExchangeSnapshot(
        method="GET",
        url="https://api.orders.example.com/v1/orders",
        response_status=200,
        response_body={"items": "not_an_array"},
    )
    resp_findings = analyze_schema(
        url="https://api.orders.example.com/v1/orders",
        method="GET",
        exchange=ex,
        expected_response_schema={
            "type": "object",
            "required": ["items", "total"],
            "properties": {"items": {"type": "array"}, "total": {"type": "integer"}},
        },
    )
    assert any(f.diagnostic_id == "SCH-005" for f in resp_findings)


def test_response_diagnostics() -> None:
    # 429 rate limit
    ex_429 = HTTPExchangeSnapshot(
        method="GET",
        url="https://api.example.com/v1/items",
        response_status=429,
        response_headers={"Retry-After": "15", "Content-Type": "application/json"},
    )
    f_429 = analyze_response(exchange=ex_429, expected_status=200)
    assert any(f.diagnostic_id == "RES-006" for f in f_429)
    assert any(f.diagnostic_id == "RES-001" for f in f_429)

    # Malformed JSON on 200
    ex_bad_json = HTTPExchangeSnapshot(
        method="GET",
        url="https://api.example.com/v1/items",
        response_status=200,
        response_headers={"Content-Type": "application/json"},
        raw_response_text='{"incomplete": ',
    )
    f_bad = analyze_response(exchange=ex_bad_json)
    assert any(f.diagnostic_id == "RES-002" for f in f_bad)

    # Unexpected HTML & application error in 200 & pagination
    ex_html = HTTPExchangeSnapshot(
        method="GET",
        url="https://api.example.com/v1/items?page=0",
        response_status=200,
        response_headers={"Content-Type": "text/html"},
        response_body={"success": False, "error": "Failed"},
    )
    f_html = analyze_response(
        url="https://api.example.com/v1/items?page=0",
        request_headers={"Accept": "application/json"},
        exchange=ex_html,
    )
    html_ids = {f.diagnostic_id for f in f_html}
    assert "RES-008" in html_ids
    assert "RES-003" in html_ids
    assert "RES-007" in html_ids


def test_integration_and_repository_diagnostics(tmp_path) -> None:
    # Create a temporary repository with Python and TS files
    (tmp_path / ".env").write_text("API_KEY=YOUR_API_KEY\n", encoding="utf-8")
    (tmp_path / "service.py").write_text(
        'import os, requests\n'
        'KEY = os.getenv("MISSING_SECRET")\n'
        'def call():\n'
        '    return requests.get("https://api.example.com/v1/orders", verify=False)\n',
        encoding="utf-8",
    )
    repo_res = inspect_repository(tmp_path)
    assert repo_res.files_scanned >= 2
    assert "python" in repo_res.languages_detected
    assert "requests" in repo_res.client_libraries_detected

    openapi = {
        "openapi": "3.0.0",
        "info": {"title": "Test", "version": "1.0"},
        "servers": [{"url": "https://api.example.com/v2"}],
        "paths": {
            "/orders": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"customer_id": {"type": "string"}},
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }

    int_findings = analyze_integration(
        url="https://wrong-host.example.com/v1/ordrs",
        method="POST",
        request_payload={"customerId": "c1"},
        openapi_spec=openapi,
        environment_vars={"API_KEY": ""},
        repository_analysis=repo_res,
    )
    int_ids = {f.diagnostic_id for f in int_findings}
    assert "INT-001" in int_ids  # base URL mismatch
    assert "INT-002" in int_ids  # empty env var
    assert "INT-004" in int_ids  # undocumented path /ordrs vs /orders
    assert "INT-005" in int_ids  # v1 vs v2 version mismatch
    assert "INT-007" in int_ids  # verify=False / missing timeout

    casing_findings = analyze_integration(
        url="https://api.example.com/v2/orders",
        method="POST",
        request_payload={"customerId": "c1"},
        openapi_spec=openapi,
    )
    assert any(f.diagnostic_id == "INT-006" for f in casing_findings)
