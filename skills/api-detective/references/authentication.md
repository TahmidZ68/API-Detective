# Authentication Diagnostics & Safe Token Inspection

API Detective diagnoses authentication and authorization failures without exposing secret values or attempting credential discovery.

## 1. Safe JWT Claim Inspection (`AUTH-003`, `AUTH-007`)
When an `Authorization: Bearer <token>` header contains a three-part JWT (`header.payload.signature`), API Detective base64url-decodes the header and payload **in memory** and extracts only non-sensitive metadata:
- `alg` and `typ`
- `exp` (expiration UTC timestamp) and `nbf` (not-before UTC timestamp)
- `scope` / `scp` list
- Claim key names (e.g., `["aud", "exp", "iat", "iss", "scope", "sub"]`)

The raw token string is immediately redacted as `Bearer ***REDACTED***` in all logs, evidence lists, and persisted reports.

## 2. Common Header Formatting Defects (`AUTH-002`, `AUTH-004`)
- **Duplicate Scheme Prefix**: `Authorization: Bearer Bearer eyJ...` occurs when an environment variable already includes `Bearer ` and the client code prepends `Bearer ` again.
- **Uninterpolated Placeholders**: `Bearer undefined`, `Bearer null`, `Bearer YOUR_API_KEY`, or `Bearer <token>` indicates an uninitialized frontend state or missing `.env` variable.
- **Missing Scheme Prefix**: Sending a raw token (`Authorization: eyJ...`) when the server requires `Authorization: Bearer eyJ...`.

## 3. Distinguishing HTTP 401 vs HTTP 403 (`AUTH-008`)
- **HTTP 401 Unauthorized**: The caller's identity could not be verified (missing header, expired token, wrong signing key, or wrong environment).
- **HTTP 403 Forbidden**: The caller is authenticated, but lacks permission for the operation (missing OAuth scope `AUTH-007`, insufficient RBAC role, IP allowlist restriction, or WAF rule).
