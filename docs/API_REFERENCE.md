# API Detective REST API Reference

Base URL: `http://localhost:8000/api/v1`

---

## 1. System Health

### `GET /api/v1/health`
Returns service readiness, version, and optional LLM provider status.

```json
{
  "status": "ok",
  "service": "api-detective",
  "version": "0.1.0-alpha.2",
  "llm_provider": "none",
  "deterministic_engine": "ready"
}
```

---

## 2. Dashboard Telemetry

### `GET /api/v1/dashboard/overview`
Returns live aggregated diagnostic metrics from persisted SQLite/PostgreSQL investigation records:
- `total_investigations`
- `successful_diagnoses`
- `open_issues`
- `resolved_issues`
- `category_distribution` (`connectivity`, `authentication`, `request`, `schema`, `response`, `integration`)
- `severity_distribution` (`critical`, `high`, `medium`, `low`, `informational`)
- `recent_investigations`
- `recent_activity`

---

## 3. Investigations & Remediation

### `POST /api/v1/investigations`
Launches a 7-step investigation and returns the full `InvestigationReport` (`HTTP 201`).

**Request Payload (`InvestigationRequest`):**
```json
{
  "title": "POST /v1/orders returning 401",
  "prompt": "Why is my API returning 401?",
  "url": "https://api.orders.example.com/v1/orders",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer <TOKEN>",
    "Content-Type": "application/json"
  },
  "query_params": {},
  "request_payload": {
    "customer_id": "cust_402",
    "amount": 99.5,
    "currency": "USD"
  },
  "openapi_spec": null,
  "request_schema": null,
  "expected_response_schema": null,
  "repository_path": null,
  "execute_live_request": true,
  "allow_localhost": false
}
```

### `GET /api/v1/investigations`
Lists recent persisted investigation reports (`?limit=50`).

### `GET /api/v1/investigations/{investigation_id}`
Retrieves a single `InvestigationReport` by ID.

### `POST /api/v1/investigations/{investigation_id}/approve-fix`
Approves a proposed `RemediationPlanItem` (`Level 3`) and triggers `Level 4` verification diagnostics.

```json
{
  "fix_id": "FIX-001",
  "approved": true,
  "apply_changes": true,
  "run_verification": true
}
```

### `GET /api/v1/investigations/{investigation_id}/export?format=json|markdown|html`
Exports a secret-redacted diagnostic report in `json`, `markdown`, or standalone `html`.

---

## 4. Standalone Diagnostic Endpoints

- `POST /api/v1/diagnostics/validate-schema`: Validates a JSON payload against a JSON Schema (`SchemaValidationRequest` -> `SchemaValidationResponse`).
- `POST /api/v1/diagnostics/inspect-spec`: Parses and validates an OpenAPI 3.0/3.1 or Swagger 2.0 specification (`SpecInspectRequest` -> `SpecInspectResponse`).
- `POST /api/v1/diagnostics/inspect-repository`: Performs a read-only scan of a local repository path (`{"repository_path": "./my-repo"}` -> `RepositoryAnalysisResult`).

---

## 5. Runtime Agent Settings

- `GET /api/v1/settings`: Returns current runtime configuration (`AgentSettingsResponse`) with API keys masked.
- `PUT /api/v1/settings`: Updates LLM provider, model, iteration limits, timeout, SSRF, and privacy flags (`AgentSettingsPayload`).
