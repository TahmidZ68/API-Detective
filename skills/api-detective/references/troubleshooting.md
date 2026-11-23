# Troubleshooting Playbooks

## Scenario 1: Frontend Receives HTML Instead of JSON (`RES-008`)
- **Symptoms**: Client throws `SyntaxError: Unexpected token '<', "<!DOCTYPE "... is not valid JSON`.
- **Root Causes**:
  1. Target URL points to the frontend SPA host instead of the backend API base URL (`INT-001`).
  2. An authentication proxy redirected an unauthenticated API request to an HTML SSO login page.
  3. Reverse proxy (Nginx/Cloudflare) returned a default HTML 502/504/404 page.
- **Fix**: Check `Response Content-Type` and `Redirect Chain` in the Request Inspector, align the base URL with the OpenAPI `servers` list, and pass valid authentication headers.

## Scenario 2: Cross-Origin Redirect Drops Authorization Header (`CONN-006`, `AUTH-008`)
- **Symptoms**: Request includes a valid `Authorization: Bearer <token>` header in code, but the server responds with `HTTP 401 Unauthorized`.
- **Root Cause**: The request hits `https://example.com/api/v1/users` which redirects (`301`/`302`) to `https://api.example.com/v1/users`. Standard HTTP clients strip the `Authorization` header on cross-host redirects to prevent credential leakage.
- **Fix**: Configure the client base URL to call the canonical host (`https://api.example.com`) directly.

## Scenario 3: JavaScript or Python Serialization Bugs (`REQ-008`, `REQ-004`)
- **Symptoms**: Server returns `HTTP 400 Bad Request` or `HTTP 422 Unprocessable Entity` even though payload fields look right in code.
- **Root Causes**:
  - Passing a JS object directly to `fetch({ body: obj })` without `JSON.stringify(obj)` serializes `"[object Object]"`.
  - Calling `JSON.stringify()` on a payload passed to `axios.post()` double-encodes the JSON string.
  - Passing `data=str(payload)` in Python `requests`/`httpx` sends single-quoted Python dictionary syntax (`{'a': 1}`) instead of valid double-quoted JSON.
