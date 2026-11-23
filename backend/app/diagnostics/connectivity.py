"""Connectivity diagnostics module (DNS, TCP, TLS, URLs, redirects, CORS, proxy)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from backend.app.core.security import redact_text, redact_url
from backend.app.schemas.diagnostics import DiagnosticFinding, HTTPExchangeSnapshot


def analyze_connectivity(
    *,
    url: str | None,
    method: str = "GET",
    request_headers: dict[str, str] | None = None,
    exchange: HTTPExchangeSnapshot | None = None,
    error_message: str | None = None,
) -> list[DiagnosticFinding]:
    """Run deterministic connectivity diagnostics on an HTTP target and exchange."""
    findings: list[DiagnosticFinding] = []
    req_headers = {k.lower(): v for k, v in (request_headers or {}).items()}
    combined_error = " ".join(
        filter(
            None,
            [
                error_message or "",
                (exchange.error_message if exchange else "") or "",
                (exchange.error_type if exchange else "") or "",
            ],
        )
    )
    lower_error = combined_error.lower()

    # 1. URL validity check
    if not url or not url.strip():
        findings.append(
            DiagnosticFinding(
                diagnostic_id="CONN-005",
                category="connectivity",
                severity="critical",
                title="Missing or Empty Target URL",
                description="No target URL was provided for the API request.",
                evidence=["Target URL field is empty or null."],
                recommendation="Provide a valid HTTP or HTTPS endpoint URL (e.g. https://api.example.com/v1/resource).",
                confidence=1.0,
                status="confirmed",
            )
        )
        return findings

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc or " " in url.strip():
        findings.append(
            DiagnosticFinding(
                diagnostic_id="CONN-005",
                category="connectivity",
                severity="critical",
                title="Invalid URL Format",
                description=f"The URL '{redact_url(url)}' is malformed or uses an unsupported protocol scheme.",
                evidence=[
                    f"Parsed scheme: '{parsed.scheme or 'none'}'",
                    f"Parsed host: '{parsed.netloc or 'none'}'",
                ],
                recommendation="Ensure the URL begins with 'https://' or 'http://' and contains a valid hostname without spaces.",
                confidence=0.99,
                status="confirmed",
            )
        )

    # 2. DNS resolution failures
    if any(
        marker in lower_error
        for marker in (
            "getaddrinfo failed",
            "name or service not known",
            "nodename nor servname provided",
            "temporary failure in name resolution",
            "nxdomain",
            "dns",
            "no address associated with hostname",
        )
    ):
        findings.append(
            DiagnosticFinding(
                diagnostic_id="CONN-001",
                category="connectivity",
                severity="critical",
                title="DNS Resolution Failure",
                description=f"Unable to resolve hostname '{parsed.hostname or url}' to an IP address.",
                evidence=[redact_text(combined_error.strip())],
                recommendation="Verify the domain spelling, check local DNS/VPN settings, and confirm the host exists in the target environment.",
                confidence=0.97,
                status="confirmed",
            )
        )

    # 3. Connection refused
    if any(
        marker in lower_error
        for marker in ("connection refused", "econnrefused", "actively refused", "winerror 10061")
    ):
        findings.append(
            DiagnosticFinding(
                diagnostic_id="CONN-002",
                category="connectivity",
                severity="critical",
                title="TCP Connection Refused",
                description="The target host actively refused the TCP connection on the requested port.",
                evidence=[
                    f"Target host: {parsed.netloc}",
                    redact_text(combined_error.strip()),
                ],
                recommendation="Ensure the target API server process is running, listening on the expected interface and port, and not blocked by a local firewall.",
                confidence=0.98,
                status="confirmed",
            )
        )

    # 4. Connection / Read Timeouts
    if any(
        marker in lower_error
        for marker in (
            "timed out",
            "timeout",
            "connecttimeout",
            "readtimeout",
            "pooltimeout",
            "etimedout",
        )
    ):
        findings.append(
            DiagnosticFinding(
                diagnostic_id="CONN-003",
                category="connectivity",
                severity="high",
                title="Request or Connection Timeout",
                description="The API request timed out while establishing a connection or waiting for response bytes.",
                evidence=[redact_text(combined_error.strip())],
                recommendation="Check network reachability, firewall security groups, upstream server latency, or increase client timeout configuration.",
                confidence=0.96,
                status="confirmed",
            )
        )

    # 5. SSL / TLS Certificate Issues
    if any(
        marker in lower_error
        for marker in (
            "ssl",
            "certificate_verify_failed",
            "cert",
            "tls",
            "handshake failure",
            "hostname mismatch",
            "self-signed",
            "expired certificate",
        )
    ):
        findings.append(
            DiagnosticFinding(
                diagnostic_id="CONN-004",
                category="connectivity",
                severity="critical",
                title="SSL/TLS Certificate Verification Failure",
                description="The TLS handshake failed due to an untrusted, expired, or mismatched server certificate.",
                evidence=[redact_text(combined_error.strip())],
                recommendation="Renew or reissue the server TLS certificate, ensure the full certificate chain is served, and verify system CA bundle configuration. Do not disable SSL verification in production.",
                confidence=0.97,
                status="confirmed",
            )
        )

    # 6. Redirect Problems
    if exchange and exchange.redirect_chain:
        chain = exchange.redirect_chain
        if len(chain) > 3 or "too many redirects" in lower_error:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="CONN-006",
                    category="connectivity",
                    severity="high",
                    title="Excessive Redirects or Redirect Loop",
                    description=f"The request encountered {len(chain)} redirects before terminating.",
                    evidence=[f"Redirect chain ({len(chain)} hops): " + " -> ".join(redact_url(u) for u in chain)],
                    recommendation="Inspect server redirect rules and canonical trailing-slash configuration to eliminate redirect chains.",
                    confidence=0.94,
                    status="confirmed",
                )
            )
        # Check HTTPS -> HTTP downgrade or cross-host redirect with Authorization header
        first_parsed = urlparse(chain[0])
        last_parsed = urlparse(exchange.url)
        if first_parsed.scheme == "https" and last_parsed.scheme == "http":
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="CONN-006",
                    category="connectivity",
                    severity="high",
                    title="Insecure HTTPS-to-HTTP Redirect Downgrade",
                    description="An HTTPS endpoint redirected to an unencrypted HTTP URL, which risks credential exposure or dropped headers.",
                    evidence=[f"Initial: {redact_url(chain[0])}", f"Final: {redact_url(exchange.url)}"],
                    recommendation="Configure the upstream reverse proxy or load balancer to redirect exclusively to HTTPS URLs.",
                    confidence=0.96,
                    status="confirmed",
                )
            )
        elif (
            first_parsed.netloc != last_parsed.netloc
            and "authorization" in req_headers
            and exchange.response_status == 401
        ):
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="CONN-006",
                    category="connectivity",
                    severity="high",
                    title="Authorization Header Stripped Across Cross-Origin Redirect",
                    description="HTTP clients automatically strip the Authorization header when following redirects to a different hostname, causing a 401 response.",
                    evidence=[
                        f"Initial host: {first_parsed.netloc}",
                        f"Redirected host: {last_parsed.netloc}",
                        "Final status: HTTP 401",
                    ],
                    recommendation="Call the final canonical hostname directly instead of relying on a cross-domain redirect.",
                    confidence=0.93,
                    status="probable",
                )
            )
    elif "too many redirects" in lower_error or "redirect" in lower_error:
        findings.append(
            DiagnosticFinding(
                diagnostic_id="CONN-006",
                category="connectivity",
                severity="high",
                title="Redirect Failure Detected",
                description="The HTTP client terminated due to a redirect loop or redirect policy violation.",
                evidence=[redact_text(combined_error.strip())],
                recommendation="Call the canonical target URL directly and verify server redirect configuration.",
                confidence=0.92,
                status="confirmed",
            )
        )

    # 7. CORS Configuration Diagnostics
    if exchange:
        resp_headers = {k.lower(): v for k, v in (exchange.response_headers or {}).items()}
        origin = req_headers.get("origin")
        acao = resp_headers.get("access-control-allow-origin")
        acac = resp_headers.get("access-control-allow-credentials", "").lower()

        if acao == "*" and acac == "true":
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="CONN-007",
                    category="connectivity",
                    severity="high",
                    title="Invalid CORS Wildcard Origin With Credentials",
                    description="The server returned 'Access-Control-Allow-Origin: *' alongside 'Access-Control-Allow-Credentials: true', which browsers reject.",
                    evidence=[
                        "Access-Control-Allow-Origin: *",
                        "Access-Control-Allow-Credentials: true",
                    ],
                    recommendation="Echo the specific allowed Origin header instead of '*' when credentials are enabled.",
                    confidence=0.99,
                    status="confirmed",
                )
            )
        elif origin and not acao:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="CONN-007",
                    category="connectivity",
                    severity="medium",
                    title="Missing CORS Access-Control-Allow-Origin Header",
                    description=f"Request included Origin '{origin}', but the response omitted 'Access-Control-Allow-Origin'. Browser clients will block the response.",
                    evidence=[
                        f"Request Origin: {origin}",
                        "Response Access-Control-Allow-Origin header: absent",
                    ],
                    recommendation="Configure CORS middleware on the API server to permit the frontend origin.",
                    confidence=0.90,
                    status="confirmed",
                )
            )
        elif origin and acao and acao not in ("*", origin):
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="CONN-007",
                    category="connectivity",
                    severity="high",
                    title="CORS Origin Mismatch",
                    description=f"The request Origin '{origin}' does not match the server's 'Access-Control-Allow-Origin: {acao}'.",
                    evidence=[
                        f"Request Origin: {origin}",
                        f"Access-Control-Allow-Origin: {acao}",
                    ],
                    recommendation=f"Add '{origin}' to the backend CORS allowlist.",
                    confidence=0.98,
                    status="confirmed",
                )
            )
    if "cors" in lower_error or "access-control-allow-origin" in lower_error:
        if not any(f.diagnostic_id == "CONN-007" for f in findings):
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="CONN-007",
                    category="connectivity",
                    severity="high",
                    title="CORS Policy Rejection Reported",
                    description="The client error indicates a Cross-Origin Resource Sharing (CORS) block.",
                    evidence=[redact_text(combined_error.strip())],
                    recommendation="Ensure the backend handles OPTIONS preflight requests and returns matching Access-Control-Allow-Origin and Access-Control-Allow-Headers.",
                    confidence=0.91,
                    status="probable",
                )
            )

    # 8. Proxy-related Issues
    resp_status = exchange.response_status if exchange else None
    resp_headers_lower: dict[str, Any] = (
        {k.lower(): v for k, v in (exchange.response_headers or {}).items()} if exchange else {}
    )
    if (
        resp_status == 407
        or "proxy" in lower_error
        or (resp_status in (502, 504) and ("via" in resp_headers_lower or "server" in resp_headers_lower))
    ):
        evidence_list = []
        if resp_status:
            evidence_list.append(f"HTTP Status: {resp_status}")
        if "via" in resp_headers_lower:
            evidence_list.append(f"Via header: {resp_headers_lower['via']}")
        if combined_error.strip():
            evidence_list.append(redact_text(combined_error.strip()))
        findings.append(
            DiagnosticFinding(
                diagnostic_id="CONN-008",
                category="connectivity",
                severity="high" if resp_status == 407 or "proxy" in lower_error else "medium",
                title="Proxy or Gateway Connectivity Issue",
                description="Evidence indicates an intermediary HTTP proxy or reverse gateway rejected or failed to forward the request.",
                evidence=evidence_list or ["Intermediary proxy error detected."],
                recommendation="Check HTTP_PROXY/HTTPS_PROXY environment variables, proxy credentials (HTTP 407), or upstream gateway target health (HTTP 502/504).",
                confidence=0.92 if resp_status == 407 or "proxy" in lower_error else 0.78,
                status="confirmed" if resp_status == 407 or "proxy" in lower_error else "probable",
            )
        )

    return findings
