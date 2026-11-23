"""Authentication diagnostics module.

Analyzes API keys, Bearer tokens, JWT expiration/claims (without exposing values),
Authorization header formats, OAuth errors, token placement, scopes, and 401/403 responses.
Never attempts to bypass authentication or discover credentials.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any
from urllib.parse import parse_qsl, urlparse

from backend.app.core.security import redact_headers, redact_text
from backend.app.schemas.diagnostics import DiagnosticFinding, HTTPExchangeSnapshot

PLACEHOLDER_TOKEN_VALUES = frozenset(
    {
        "your_api_key",
        "your-api-key",
        "your_token",
        "your-token",
        "<token>",
        "<api_key>",
        "undefined",
        "null",
        "none",
        "changeme",
        "todo",
        "xxx",
        "test",
    }
)


def _decode_jwt_metadata_safely(token: str) -> dict[str, Any] | None:
    """Safely inspect non-sensitive JWT header and claim metadata without exposing the token."""
    parts = token.strip().split(".")
    if len(parts) != 3:
        return None
    try:
        header_b64, payload_b64, _ = parts
        header_pad = header_b64 + "=" * (-len(header_b64) % 4)
        payload_pad = payload_b64 + "=" * (-len(payload_b64) % 4)
        header_data = json.loads(base64.urlsafe_b64decode(header_pad.encode("ascii")).decode("utf-8"))
        payload_data = json.loads(base64.urlsafe_b64decode(payload_pad.encode("ascii")).decode("utf-8"))
        if not isinstance(header_data, dict) or not isinstance(payload_data, dict):
            return None
        # Extract only safe structural metadata
        scopes: list[str] = []
        raw_scope = payload_data.get("scope") or payload_data.get("scp")
        if isinstance(raw_scope, str):
            scopes = [s for s in raw_scope.split() if s]
        elif isinstance(raw_scope, list):
            scopes = [str(s) for s in raw_scope]
        return {
            "alg": header_data.get("alg"),
            "typ": header_data.get("typ"),
            "exp": payload_data.get("exp"),
            "nbf": payload_data.get("nbf"),
            "iat": payload_data.get("iat"),
            "iss": payload_data.get("iss"),
            "aud": payload_data.get("aud"),
            "scopes": scopes,
            "claim_keys": sorted(payload_data.keys()),
        }
    except Exception:
        return None


def analyze_authentication(
    *,
    url: str | None = None,
    request_headers: dict[str, str] | None = None,
    query_params: dict[str, Any] | None = None,
    exchange: HTTPExchangeSnapshot | None = None,
    required_scopes: list[str] | None = None,
    expected_auth_scheme: str | None = None,
    expected_key_location: str | None = None,
    expected_key_name: str | None = None,
) -> list[DiagnosticFinding]:
    """Run deterministic authentication diagnostics without exposing secret values."""
    findings: list[DiagnosticFinding] = []
    raw_headers = request_headers or {}
    lower_headers = {k.lower(): v for k, v in raw_headers.items()}
    safe_headers = redact_headers(raw_headers)

    resp_status = exchange.response_status if exchange else None
    resp_headers = {k.lower(): v for k, v in (exchange.response_headers or {}).items()} if exchange else {}
    resp_body = exchange.response_body if exchange else None

    auth_header = lower_headers.get("authorization")
    api_key_headers = [
        k for k in lower_headers if k in ("x-api-key", "api-key", "apikey", "x-auth-token", "x-access-token")
    ]
    has_any_auth_header = bool(auth_header or api_key_headers)

    # Check query parameters for credentials (token placement)
    url_query_params: dict[str, str] = {}
    if url:
        for k, v in parse_qsl(urlparse(url).query, keep_blank_values=True):
            url_query_params[k.lower()] = v
    if query_params:
        for k, v in query_params.items():
            url_query_params[k.lower()] = str(v)

    auth_query_keys = [
        k
        for k in url_query_params
        if k in ("api_key", "apikey", "access_token", "token", "key", "auth_token", "client_secret")
    ]

    # 1. Missing API keys / Authorization header
    if not has_any_auth_header and not auth_query_keys:
        if resp_status in (401, 403) or expected_auth_scheme:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="AUTH-001",
                    category="authentication",
                    severity="high",
                    title="Missing Authorization Header",
                    description="The request does not contain an Authorization or API key header.",
                    evidence=[
                        "Authorization header was not present.",
                        *(
                            [f"Server responded with HTTP {resp_status}."]
                            if resp_status in (401, 403)
                            else []
                        ),
                        *(
                            [f"Endpoint specification requires authentication scheme: {expected_auth_scheme}."]
                            if expected_auth_scheme
                            else []
                        ),
                    ],
                    recommendation="Provide the required authentication credentials via the Authorization or X-API-Key header.",
                    confidence=0.98 if resp_status == 401 or expected_auth_scheme else 0.90,
                    status="confirmed",
                )
            )

    # 2. Incorrect token placement
    if auth_query_keys and (expected_key_location == "header" or not expected_key_location):
        findings.append(
            DiagnosticFinding(
                diagnostic_id="AUTH-006",
                category="authentication",
                severity="high" if resp_status in (401, 403) else "medium",
                title="Authentication Credential Placed in URL Query Parameter",
                description="Credentials were passed in the URL query string rather than request headers. Many APIs ignore query-string tokens, and URLs are often logged in plaintext by proxies.",
                evidence=[
                    f"Credential query parameter(s) detected: {', '.join(auth_query_keys)}",
                    *(
                        ["Authorization header is absent from request headers."]
                        if not has_any_auth_header
                        else []
                    ),
                ],
                recommendation="Move the API key or bearer token into the 'Authorization' or 'X-API-Key' HTTP request header.",
                confidence=0.94 if resp_status in (401, 403) else 0.85,
                status="confirmed" if expected_key_location == "header" else "probable",
            )
        )
    elif expected_key_location == "query" and expected_key_name and expected_key_name.lower() not in url_query_params:
        findings.append(
            DiagnosticFinding(
                diagnostic_id="AUTH-006",
                category="authentication",
                severity="high",
                title="Missing Required Authentication Query Parameter",
                description=f"The API specification requires credential parameter '{expected_key_name}' in the query string, but it was not found.",
                evidence=[f"Expected query parameter '{expected_key_name}' was absent."],
                recommendation=f"Pass '{expected_key_name}' in the query parameters as documented by the API contract.",
                confidence=0.95,
                status="confirmed",
            )
        )

    # 3. Inspect Authorization header format & Bearer token validity
    jwt_metadata: dict[str, Any] | None = None
    if auth_header is not None:
        stripped = auth_header.strip()
        if not stripped:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="AUTH-002",
                    category="authentication",
                    severity="high",
                    title="Empty Authorization Header",
                    description="The Authorization header is present in the request but contains an empty value.",
                    evidence=["Authorization header value is empty string."],
                    recommendation="Ensure the environment variable or token provider supplying the Authorization header is populated.",
                    confidence=0.99,
                    status="confirmed",
                )
            )
        elif stripped.lower().startswith("bearer bearer "):
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="AUTH-004",
                    category="authentication",
                    severity="high",
                    title="Duplicate 'Bearer' Prefix in Authorization Header",
                    description="The Authorization header contains a duplicated 'Bearer Bearer ...' prefix, which causes token verification failure.",
                    evidence=["Authorization header starts with 'Bearer Bearer '."],
                    recommendation="Ensure the token string does not already include the 'Bearer ' prefix before formatting the Authorization header.",
                    confidence=0.99,
                    status="confirmed",
                )
            )
        elif " " not in stripped:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="AUTH-004",
                    category="authentication",
                    severity="high",
                    title="Missing Scheme Prefix in Authorization Header",
                    description="The Authorization header contains a raw value without an authentication scheme prefix (such as 'Bearer' or 'Basic').",
                    evidence=[f"Redacted header structure: '{ redact_text(stripped[:10]) }...' lacks '<scheme> <credentials>' format."],
                    recommendation="Prefix the token with the expected scheme, e.g., 'Authorization: Bearer <token>'.",
                    confidence=0.95,
                    status="confirmed",
                )
            )
        else:
            scheme, token_val = stripped.split(" ", 1)
            scheme_lower = scheme.lower()
            token_clean = token_val.strip()

            if expected_auth_scheme and expected_auth_scheme.lower() not in (scheme_lower, "apikey"):
                findings.append(
                    DiagnosticFinding(
                        diagnostic_id="AUTH-004",
                        category="authentication",
                        severity="high",
                        title="Incorrect Authorization Scheme",
                        description=f"Request used '{scheme}' authentication scheme, but the endpoint expects '{expected_auth_scheme}'.",
                        evidence=[
                            f"Actual scheme: {scheme}",
                            f"Expected scheme: {expected_auth_scheme}",
                        ],
                        recommendation=f"Update the Authorization header to use the '{expected_auth_scheme}' scheme.",
                        confidence=0.96,
                        status="confirmed",
                    )
                )

            if scheme_lower == "bearer":
                if (
                    not token_clean
                    or token_clean.lower() in PLACEHOLDER_TOKEN_VALUES
                    or " " in token_clean
                    or len(token_clean) < 6
                ):
                    findings.append(
                        DiagnosticFinding(
                            diagnostic_id="AUTH-002",
                            category="authentication",
                            severity="high",
                            title="Invalid or Placeholder Bearer Token",
                            description="The Bearer token appears to be a placeholder, uninterpolated variable, empty string, or malformed value.",
                            evidence=[
                                f"Token length: {len(token_clean)} characters",
                                *(
                                    ["Token matches a common placeholder or uninitialized variable literal."]
                                    if token_clean.lower() in PLACEHOLDER_TOKEN_VALUES
                                    else []
                                ),
                                *(
                                    ["Token contains illegal whitespace characters."]
                                    if " " in token_clean
                                    else []
                                ),
                            ],
                            recommendation="Verify that your token environment variable is set and properly interpolated into the Authorization header.",
                            confidence=0.97,
                            status="confirmed",
                        )
                    )
                else:
                    # Check if token looks like a JWT (3 dot-separated parts or starts with eyJ)
                    if token_clean.count(".") == 2 or token_clean.startswith("eyJ"):
                        jwt_metadata = _decode_jwt_metadata_safely(token_clean)
                        if jwt_metadata is None:
                            findings.append(
                                DiagnosticFinding(
                                    diagnostic_id="AUTH-002",
                                    category="authentication",
                                    severity="high",
                                    title="Malformed JWT Bearer Token",
                                    description="The Bearer token resembles a JSON Web Token (JWT) but its header or payload could not be base64url-decoded as valid JSON.",
                                    evidence=["Token has JWT structure (eyJ...) but failed base64url JSON decoding."],
                                    recommendation="Ensure the full JWT string was copied without truncation or extra characters.",
                                    confidence=0.95,
                                    status="confirmed",
                                )
                            )
            elif scheme_lower == "basic":
                try:
                    decoded = base64.b64decode(token_clean, validate=True).decode("utf-8")
                    if ":" not in decoded:
                        raise ValueError("Missing colon separator")
                except Exception:
                    findings.append(
                        DiagnosticFinding(
                            diagnostic_id="AUTH-004",
                            category="authentication",
                            severity="high",
                            title="Malformed Basic Authentication Header",
                            description="Basic authentication value must be valid base64-encoded 'username:password'.",
                            evidence=["Authorization Basic payload is not valid base64 'username:password'."],
                            recommendation="Base64-encode 'username:password' before placing it in 'Authorization: Basic <encoded>'.",
                            confidence=0.97,
                            status="confirmed",
                        )
                    )

    # Check API key headers for placeholder values
    for key_hdr in api_key_headers:
        val = lower_headers.get(key_hdr, "").strip()
        if not val or val.lower() in PLACEHOLDER_TOKEN_VALUES:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="AUTH-002",
                    category="authentication",
                    severity="high",
                    title="Empty or Placeholder API Key Header",
                    description=f"The '{key_hdr}' header contains an empty or placeholder value.",
                    evidence=[f"Header '{key_hdr}' is empty or set to a placeholder string."],
                    recommendation=f"Set a valid API key value for the '{key_hdr}' header.",
                    confidence=0.98,
                    status="confirmed",
                )
            )

    # 4. JWT Expiration & Not-Before Inspection
    if jwt_metadata is not None:
        now_ts = int(time.time())
        exp = jwt_metadata.get("exp")
        nbf = jwt_metadata.get("nbf")
        if isinstance(exp, (int, float)) and exp < now_ts:
            expired_seconds = int(now_ts - exp)
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="AUTH-003",
                    category="authentication",
                    severity="high",
                    title="Expired JWT Bearer Token",
                    description=f"The JWT token's 'exp' claim ({int(exp)}) is in the past (expired {expired_seconds} seconds ago).",
                    evidence=[
                        f"JWT 'exp' claim timestamp: {int(exp)}",
                        f"Current UTC timestamp: {now_ts}",
                        f"JWT algorithm: {jwt_metadata.get('alg', 'unknown')}",
                    ],
                    recommendation="Refresh the access token using your refresh token flow or generate a new short-lived JWT.",
                    confidence=0.99,
                    status="confirmed",
                )
            )
        if isinstance(nbf, (int, float)) and nbf > now_ts + 30:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="AUTH-003",
                    category="authentication",
                    severity="medium",
                    title="JWT Token Not Yet Valid (nbf Claim in Future)",
                    description=f"The JWT token's 'nbf' (not-before) claim ({int(nbf)}) is in the future.",
                    evidence=[
                        f"JWT 'nbf' claim timestamp: {int(nbf)}",
                        f"Current UTC timestamp: {now_ts}",
                    ],
                    recommendation="Check for system clock skew between the token issuer and client machine.",
                    confidence=0.95,
                    status="confirmed",
                )
            )

    # 5. Missing Required Scopes
    www_auth = resp_headers.get("www-authenticate", "")
    needed_scopes = list(required_scopes or [])
    if jwt_metadata is not None and needed_scopes:
        token_scopes = set(jwt_metadata.get("scopes") or [])
        missing_scopes = [s for s in needed_scopes if s not in token_scopes]
        if missing_scopes:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="AUTH-007",
                    category="authentication",
                    severity="high",
                    title="Missing Required OAuth/JWT Scopes",
                    description="The inspected JWT claims do not include all scopes required by this endpoint.",
                    evidence=[
                        f"Token scopes present: {sorted(token_scopes) or ['none']}",
                        f"Missing required scopes: {missing_scopes}",
                    ],
                    recommendation=f"Request the missing scope(s) ({', '.join(missing_scopes)}) during token issuance.",
                    confidence=0.96,
                    status="confirmed",
                )
            )
    elif "insufficient_scope" in www_auth.lower():
        findings.append(
            DiagnosticFinding(
                diagnostic_id="AUTH-007",
                category="authentication",
                severity="high",
                title="Insufficient OAuth Scope Reported by Server",
                description="The server's WWW-Authenticate header explicitly indicates 'insufficient_scope'.",
                evidence=[f"WWW-Authenticate: {redact_text(www_auth)}"],
                recommendation="Re-authenticate or provision a token that grants the scope listed in WWW-Authenticate.",
                confidence=0.98,
                status="confirmed",
            )
        )

    # 6. OAuth Configuration Problems in Response
    if isinstance(resp_body, dict):
        oauth_err = str(resp_body.get("error", "")).lower()
        oauth_desc = str(resp_body.get("error_description", ""))
        if oauth_err in (
            "invalid_client",
            "invalid_grant",
            "unauthorized_client",
            "unsupported_grant_type",
            "invalid_scope",
            "invalid_token",
        ):
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="AUTH-005",
                    category="authentication",
                    severity="high",
                    title=f"OAuth 2.0 Error: {oauth_err}",
                    description=f"The server returned standard OAuth 2.0 error code '{oauth_err}'. {redact_text(oauth_desc)}".strip(),
                    evidence=[
                        f"OAuth error code: {oauth_err}",
                        *([f"Description: {redact_text(oauth_desc)}"] if oauth_desc else []),
                    ],
                    recommendation="Verify OAuth client_id, client_secret, redirect_uri, grant_type, and token endpoint configuration.",
                    confidence=0.98,
                    status="confirmed",
                )
            )

    # 7. HTTP 401 and 403 Response Analysis
    if resp_status == 401:
        findings.append(
            DiagnosticFinding(
                diagnostic_id="AUTH-008",
                category="authentication",
                severity="high",
                title="HTTP 401 Unauthorized Response",
                description="The endpoint rejected the request due to missing, invalid, or expired authentication credentials.",
                evidence=[
                    "Response status: 401 Unauthorized",
                    f"Request headers sent (redacted): {json.dumps(safe_headers)}",
                    *([f"WWW-Authenticate: {redact_text(www_auth)}"] if www_auth else []),
                ],
                recommendation="Check previous AUTH findings for missing headers, expired JWT claims, or invalid API keys, and confirm the token belongs to the target environment.",
                confidence=0.99,
                status="confirmed",
            )
        )
    elif resp_status == 403:
        findings.append(
            DiagnosticFinding(
                diagnostic_id="AUTH-008",
                category="authentication",
                severity="high",
                title="HTTP 403 Forbidden Response (Authorization / Permission Denied)",
                description="The server understood the request but refused to authorize it. Unlike 401, 403 usually indicates insufficient role permissions, missing scopes, IP allowlist restrictions, or WAF blocking.",
                evidence=[
                    "Response status: 403 Forbidden",
                    f"Authentication present in request: {has_any_auth_header}",
                    *([f"WWW-Authenticate: {redact_text(www_auth)}"] if www_auth else []),
                ],
                recommendation="Verify the authenticated account/service-principal has permissions for this resource, check required OAuth scopes, and verify IP/WAF allowlists.",
                confidence=0.96,
                status="confirmed",
            )
        )

    return findings
