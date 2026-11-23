# Deterministic Diagnostic Catalog (`CONN`, `AUTH`, `REQ`, `SCH`, `RES`, `INT`)

API Detective uses standardized finding schemas across six deterministic diagnostic domains.

## Finding Schema

```json
{
  "diagnostic_id": "AUTH-001",
  "category": "authentication",
  "severity": "high",
  "title": "Missing Authorization Header",
  "description": "The request does not contain an authorization header.",
  "evidence": ["Authorization header was not present."],
  "recommendation": "Provide the required authentication credentials.",
  "confidence": 0.98,
  "status": "confirmed"
}
```

- **Severity Levels**: `critical`, `high`, `medium`, `low`, `informational`
- **Finding Statuses**: `confirmed`, `probable`, `possible`, `unverified`

---

## Diagnostic ID Reference

| ID | Category | Title | Typical Trigger |
|----|----------|-------|-----------------|
| `CONN-001` | `connectivity` | DNS Resolution Failure | Hostname fails DNS lookup (`NXDOMAIN` / `gaierror`). |
| `CONN-002` | `connectivity` | TCP Connection Refused | Target port closed or service not listening (`ECONNREFUSED`). |
| `CONN-003` | `connectivity` | Request or Connection Timeout | TCP connect or read timeout exceeded. |
| `CONN-004` | `connectivity` | SSL/TLS Certificate Verification Failure | Expired, self-signed, or hostname-mismatched TLS certificate. |
| `CONN-005` | `connectivity` | Invalid URL Format | Missing scheme (`http`/`https`), missing host, or illegal whitespace. |
| `CONN-006` | `connectivity` | Redirect Problem | Redirect loop, `HTTPS -> HTTP` downgrade, or cross-host `Authorization` strip. |
| `CONN-007` | `connectivity` | CORS Configuration Conflict | `Access-Control-Allow-Origin: *` with credentials, or missing/mismatched origin header. |
| `CONN-008` | `connectivity` | Proxy or Gateway Issue | HTTP `407` or `502`/`504` with intermediary `Via` proxy headers. |
| `AUTH-001` | `authentication` | Missing Authorization Header | Request lacks `Authorization` or API key header on protected endpoint. |
| `AUTH-002` | `authentication` | Invalid or Placeholder Bearer Token | Empty token, placeholder literal (`YOUR_API_KEY`, `undefined`), or malformed JWT. |
| `AUTH-003` | `authentication` | Expired or Future JWT Token | JWT `exp` claim is in the past or `nbf` claim is in the future. |
| `AUTH-004` | `authentication` | Incorrect Authorization Header Format | Duplicate `Bearer Bearer`, missing scheme prefix, or invalid Base64 in `Basic`. |
| `AUTH-005` | `authentication` | OAuth 2.0 Configuration Error | Standard OAuth error (`invalid_client`, `invalid_grant`, `unsupported_grant_type`). |
| `AUTH-006` | `authentication` | Incorrect Token Placement | Credentials placed in URL query string instead of required HTTP header. |
| `AUTH-007` | `authentication` | Missing Required OAuth/JWT Scopes | Token `scope`/`scp` claims lack required endpoint scopes or `insufficient_scope`. |
| `AUTH-008` | `authentication` | HTTP 401 / 403 Response Analysis | Distinguishes unauthenticated (`401`) from insufficient permissions (`403`). |
| `REQ-001` | `request` | Incorrect or Disallowed HTTP Method | HTTP `405`, OpenAPI method mismatch, or body attached to `GET`/`HEAD`. |
| `REQ-002` | `request` | Missing Required Request Header | Missing `Content-Type` on payload or missing documented header parameter. |
| `REQ-003` | `request` | Incorrect Content-Type | HTTP `415` or sending structured JSON with non-JSON `Content-Type`. |
| `REQ-004` | `request` | Malformed JSON in Request Payload | Syntax error in raw JSON request body. |
| `REQ-005` | `request` | Missing Path or Query Parameter | Unexpanded `{id}` / `:id` template in URL path or missing required query parameter. |
| `REQ-006` | `request` | Invalid Serialized Query Parameter | Query string contains literal `undefined`, `NaN`, or `[object Object]`. |
| `REQ-007` | `request` | Empty Request Payload | Empty body sent on `POST`/`PUT`/`PATCH` resulting in `400`/`422`. |
| `REQ-008` | `request` | Payload Serialization Problem | Double-encoded JSON string, Python `str(dict)` single quotes, or `[object Object]`. |
| `SCH-001` | `schema` | Missing Required Schema Property | Required property omitted or null in request/response object. |
| `SCH-002` | `schema` | Unexpected Property | Undocumented field violates `additionalProperties: false`. |
| `SCH-003` | `schema` | Incorrect Data Type | Field value type does not match JSON Schema `type`. |
| `SCH-004` | `schema` | Enum Value Mismatch | Value is not in documented `enum` list. |
| `SCH-005` | `schema` | Request/Response Contract Mismatch | Actual response payload violates documented OpenAPI response schema. |
| `SCH-006` | `schema` | Deprecated API Operation | OpenAPI operation is marked `deprecated: true`. |
| `RES-001` | `response` | HTTP Status Code Error | Detailed diagnosis for `400`, `404`, `422`, or expected status mismatch. |
| `RES-002` | `response` | Malformed JSON in Response | Response declares `application/json` but fails JSON decoding. |
| `RES-003` | `response` | Application Error in HTTP 200 OK | `200 OK` payload contains `"success": false` or `"error"` envelope. |
| `RES-004` | `response` | Empty Response Body on HTTP 200 | Zero-byte body returned with `200 OK` instead of `204 No Content`. |
| `RES-005` | `response` | Server-Side 5xx Failure | HTTP `500`, `502`, `503`, or `504` upstream failure. |
| `RES-006` | `response` | Rate Limit Exceeded | HTTP `429` or `X-RateLimit-Remaining: 0`. |
| `RES-007` | `response` | Pagination Configuration Problem | Non-positive page index (`page=0`) or truncated collection without cursor. |
| `RES-008` | `response` | Unexpected Content-Type | Receiving `text/html` (login/error page) when `application/json` was requested. |
| `INT-001` | `integration` | Base URL Mismatch | Request origin differs from OpenAPI `servers` or configured base URL. |
| `INT-002` | `integration` | Environment Variable Mismatch | Referenced env var is unset, blank, or set to a placeholder in `.env`. |
| `INT-004` | `integration` | Undocumented Endpoint Path | Request path missing from OpenAPI spec (includes fuzzy match suggestions). |
| `INT-005` | `integration` | Inconsistent API Version Prefix | Mixed `/v1/` and `/v2/` prefixes across request, spec, and repository. |
| `INT-006` | `integration` | Field Casing Mismatch | Client sends `camelCase` keys while backend schema expects `snake_case` (or vice versa). |
| `INT-007` | `integration` | Unsafe SDK Configuration | Missing request timeout or disabled TLS verification (`verify=False`) in code. |
