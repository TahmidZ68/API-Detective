"""End-to-end integration test suite against a local mock API environment with 12 scenarios.

Verifies that API Detective accurately diagnoses:
1. Valid API endpoint.
2. Missing authorization.
3. Invalid API token.
4. Malformed JSON.
5. Missing required fields.
6. Incorrect data types.
7. HTTP 404.
8. HTTP 429.
9. HTTP 500.
10. Connection timeout.
11. Invalid response schema.
12. Incorrect content type.
"""

from __future__ import annotations

import httpx
from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.schemas.diagnostics import InvestigationRequest

MOCK_OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "Mock Integration API", "version": "1.0.0"},
    "servers": [{"url": "https://mock.api.example.com/v1"}],
    "paths": {
        "/users": {
            "get": {
                "security": [{"BearerAuth": []}],
                "responses": {
                    "200": {
                        "description": "User list",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["users", "count"],
                                    "properties": {
                                        "users": {"type": "array"},
                                        "count": {"type": "integer"},
                                    },
                                }
                            }
                        },
                    }
                },
            },
            "post": {
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["username", "email", "age"],
                                "properties": {
                                    "username": {"type": "string"},
                                    "email": {"type": "string"},
                                    "age": {"type": "integer"},
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Created",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["id", "username"],
                                    "properties": {
                                        "id": {"type": "string"},
                                        "username": {"type": "string"},
                                    },
                                }
                            }
                        },
                    }
                },
            },
        }
    },
    "components": {
        "securitySchemes": {
            "BearerAuth": {"type": "http", "scheme": "bearer"},
        }
    },
}


def _mock_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    scenario = request.headers.get("X-Mock-Scenario", "")

    if scenario == "timeout" or path.endswith("/timeout"):
        raise httpx.ReadTimeout("Simulated upstream read timeout", request=request)

    if path == "/v1/unknown-endpoint":
        return httpx.Response(404, json={"error": "Not Found"})

    if scenario == "rate-limit":
        return httpx.Response(
            429,
            headers={"Retry-After": "60", "X-RateLimit-Remaining": "0"},
            json={"error": "Too Many Requests"},
        )

    if scenario == "server-error":
        return httpx.Response(500, json={"error": "Internal Server Error - database pool exhausted"})

    if scenario == "invalid-response-schema":
        return httpx.Response(200, json={"users": "corrupted_non_array_value"})

    if scenario == "wrong-content-type":
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            text="<!DOCTYPE html><html><body>Gateway Login Page</body></html>",
        )

    auth = request.headers.get("Authorization", "")
    if not auth:
        return httpx.Response(401, json={"error": "Missing Authorization header"})
    if "YOUR_API_KEY" in auth or "invalid" in auth:
        return httpx.Response(401, json={"error": "Invalid bearer token"})

    if request.method == "POST":
        ct = request.headers.get("Content-Type", "")
        if "application/json" not in ct:
            return httpx.Response(415, json={"error": "Unsupported Media Type"})
        raw = request.content.decode("utf-8", errors="replace")
        import json

        try:
            body = json.loads(raw)
        except Exception:
            return httpx.Response(400, json={"error": "Malformed JSON payload"})
        if not isinstance(body, dict) or "email" not in body:
            return httpx.Response(422, json={"error": "Missing required field 'email'"})
        if not isinstance(body.get("age"), int):
            return httpx.Response(422, json={"error": "Field 'age' must be integer"})
        return httpx.Response(201, json={"id": "usr_1", "username": body["username"]})

    return httpx.Response(200, json={"users": [{"id": "usr_1"}], "count": 1})


def _orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator(http_transport=httpx.MockTransport(_mock_handler))


def test_scenario_01_valid_api_endpoint() -> None:
    report = _orchestrator().run_investigation(
        InvestigationRequest(
            url="https://mock.api.example.com/v1/users",
            method="GET",
            headers={"Authorization": "Bearer valid_prod_token_998877", "Accept": "application/json"},
            openapi_spec=MOCK_OPENAPI_SPEC,
        )
    )
    assert report.http_exchange is not None
    assert report.http_exchange.response_status == 200
    assert len(report.findings) == 0


def test_scenario_02_missing_authorization() -> None:
    report = _orchestrator().run_investigation(
        InvestigationRequest(
            url="https://mock.api.example.com/v1/users",
            method="GET",
            headers={"Accept": "application/json"},
            openapi_spec=MOCK_OPENAPI_SPEC,
        )
    )
    ids = {f.diagnostic_id for f in report.findings}
    assert "AUTH-001" in ids
    assert report.root_causes[0].category == "authentication"


def test_scenario_03_invalid_api_token() -> None:
    report = _orchestrator().run_investigation(
        InvestigationRequest(
            url="https://mock.api.example.com/v1/users",
            method="GET",
            headers={"Authorization": "Bearer YOUR_API_KEY"},
            openapi_spec=MOCK_OPENAPI_SPEC,
        )
    )
    ids = {f.diagnostic_id for f in report.findings}
    assert "AUTH-002" in ids


def test_scenario_04_malformed_json() -> None:
    report = _orchestrator().run_investigation(
        InvestigationRequest(
            url="https://mock.api.example.com/v1/users",
            method="POST",
            headers={
                "Authorization": "Bearer valid_prod_token_998877",
                "Content-Type": "application/json",
            },
            raw_request_text='{"username": "ada", "email": ',
            openapi_spec=MOCK_OPENAPI_SPEC,
        )
    )
    ids = {f.diagnostic_id for f in report.findings}
    assert "REQ-004" in ids


def test_scenario_05_missing_required_fields() -> None:
    report = _orchestrator().run_investigation(
        InvestigationRequest(
            url="https://mock.api.example.com/v1/users",
            method="POST",
            headers={
                "Authorization": "Bearer valid_prod_token_998877",
                "Content-Type": "application/json",
            },
            request_payload={"username": "ada", "age": 30},
            openapi_spec=MOCK_OPENAPI_SPEC,
        )
    )
    ids = {f.diagnostic_id for f in report.findings}
    assert "SCH-001" in ids


def test_scenario_06_incorrect_data_types() -> None:
    report = _orchestrator().run_investigation(
        InvestigationRequest(
            url="https://mock.api.example.com/v1/users",
            method="POST",
            headers={
                "Authorization": "Bearer valid_prod_token_998877",
                "Content-Type": "application/json",
            },
            request_payload={"username": "ada", "email": "ada@example.com", "age": "thirty"},
            openapi_spec=MOCK_OPENAPI_SPEC,
        )
    )
    ids = {f.diagnostic_id for f in report.findings}
    assert "SCH-003" in ids


def test_scenario_07_http_404() -> None:
    report = _orchestrator().run_investigation(
        InvestigationRequest(
            url="https://mock.api.example.com/v1/unknown-endpoint",
            method="GET",
            headers={"Authorization": "Bearer valid_prod_token_998877"},
            openapi_spec=MOCK_OPENAPI_SPEC,
        )
    )
    ids = {f.diagnostic_id for f in report.findings}
    assert "RES-001" in ids
    assert "INT-004" in ids


def test_scenario_08_http_429() -> None:
    report = _orchestrator().run_investigation(
        InvestigationRequest(
            url="https://mock.api.example.com/v1/users",
            method="GET",
            headers={
                "Authorization": "Bearer valid_prod_token_998877",
                "X-Mock-Scenario": "rate-limit",
            },
        )
    )
    ids = {f.diagnostic_id for f in report.findings}
    assert "RES-006" in ids


def test_scenario_09_http_500() -> None:
    report = _orchestrator().run_investigation(
        InvestigationRequest(
            url="https://mock.api.example.com/v1/users",
            method="GET",
            headers={
                "Authorization": "Bearer valid_prod_token_998877",
                "X-Mock-Scenario": "server-error",
            },
        )
    )
    ids = {f.diagnostic_id for f in report.findings}
    assert "RES-005" in ids


def test_scenario_10_connection_timeout() -> None:
    report = _orchestrator().run_investigation(
        InvestigationRequest(
            url="https://mock.api.example.com/v1/timeout",
            method="GET",
            headers={
                "Authorization": "Bearer valid_prod_token_998877",
                "X-Mock-Scenario": "timeout",
            },
        )
    )
    ids = {f.diagnostic_id for f in report.findings}
    assert "CONN-003" in ids


def test_scenario_11_invalid_response_schema() -> None:
    report = _orchestrator().run_investigation(
        InvestigationRequest(
            url="https://mock.api.example.com/v1/users",
            method="GET",
            headers={
                "Authorization": "Bearer valid_prod_token_998877",
                "X-Mock-Scenario": "invalid-response-schema",
            },
            openapi_spec=MOCK_OPENAPI_SPEC,
        )
    )
    ids = {f.diagnostic_id for f in report.findings}
    assert "SCH-005" in ids


def test_scenario_12_incorrect_content_type() -> None:
    report = _orchestrator().run_investigation(
        InvestigationRequest(
            url="https://mock.api.example.com/v1/users",
            method="GET",
            headers={
                "Authorization": "Bearer valid_prod_token_998877",
                "Accept": "application/json",
                "X-Mock-Scenario": "wrong-content-type",
            },
        )
    )
    ids = {f.diagnostic_id for f in report.findings}
    assert "RES-008" in ids
