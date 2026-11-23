"""Safe HTTP client with SSRF validation, redirect re-validation, size caps, and secret redaction."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urljoin

import httpx

from backend.app.core.config import get_settings
from backend.app.core.exceptions import SSRFProtectionError
from backend.app.core.security import (
    _is_forbidden_ip,
    redact_headers,
    redact_object,
    redact_text,
    redact_url,
    validate_url_ssrf,
)
from backend.app.schemas.diagnostics import HTTPExchangeSnapshot


def _verify_connected_peer_ip(
    response: httpx.Response,
    *,
    block_private: bool,
    allow_localhost: bool,
) -> str | None:
    """Verify the actual connected socket peer IP (IPv4 or IPv6) at connection time to mitigate DNS TOCTOU rebinding."""
    stream = response.extensions.get("network_stream")
    if stream is None:
        return None

    peername: Any = None
    if hasattr(stream, "get_extra_info"):
        try:
            peername = stream.get_extra_info("peername")
            if peername is None:
                raw_sock = stream.get_extra_info("socket")
                if raw_sock is not None and hasattr(raw_sock, "getpeername"):
                    peername = raw_sock.getpeername()
        except Exception:
            peername = None

    # Supports both IPv4 2-tuples (host, port) and IPv6 4-tuples (host, port, flowinfo, scope_id)
    if isinstance(peername, tuple) and len(peername) >= 2 and isinstance(peername[0], str):
        peer_ip = peername[0]
        forbidden, reason = _is_forbidden_ip(
            peer_ip,
            block_private=block_private,
            allow_localhost=allow_localhost,
        )
        if forbidden:
            raise SSRFProtectionError(
                f"Connection-time peer IP '{peer_ip}' violated SSRF policy ({reason}). Possible DNS rebinding blocked.",
                details={"peer_ip": peer_ip},
            )
        return peer_ip
    return None


def execute_diagnostic_request(
    *,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    query_params: dict[str, Any] | None = None,
    request_payload: Any | None = None,
    raw_request_text: str | None = None,
    allow_localhost: bool | None = None,
    block_private_networks: bool | None = None,
    timeout_seconds: float | None = None,
    transport: httpx.BaseTransport | None = None,
) -> HTTPExchangeSnapshot:
    """Execute a bounded, SSRF-protected HTTP request and return a redacted snapshot."""
    settings = get_settings()
    effective_allow_localhost = (
        settings.allow_localhost_targets if allow_localhost is None else allow_localhost
    )
    effective_block_private = (
        settings.block_private_networks
        if block_private_networks is None
        else block_private_networks
    )
    timeout = timeout_seconds or settings.http_timeout_seconds
    max_redirects = settings.max_redirects
    max_bytes = settings.max_response_bytes

    req_headers = dict(headers or {})
    req_params = dict(query_params or {})
    upper_method = (method or "GET").strip().upper()

    # Validate initial URL against SSRF policy
    validate_url_ssrf(
        url,
        block_private_networks=effective_block_private,
        allow_localhost_targets=effective_allow_localhost,
        resolve_dns=transport is None,
    )

    redirect_chain: list[str] = []
    resolved_peer_ips: list[str] = []
    current_url = url.strip()
    start_time = time.perf_counter()

    try:
        # Disable keepalive connection pooling across diagnostic probes so each hop undergoes fresh DNS & peer validation
        limits = httpx.Limits(max_keepalive_connections=0, max_connections=10)
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            verify=True,
            limits=limits,
            transport=transport,
        ) as client:
            response: httpx.Response | None = None
            for hop in range(max_redirects + 1):
                req_kwargs: dict[str, Any] = {
                    "method": upper_method,
                    "url": current_url,
                    "headers": req_headers,
                }
                if hop == 0 and req_params:
                    req_kwargs["params"] = req_params

                if hop == 0:
                    if raw_request_text is not None:
                        req_kwargs["content"] = raw_request_text.encode("utf-8")
                    elif isinstance(request_payload, (dict, list)):
                        if not any(k.lower() == "content-type" for k in req_headers):
                            req_headers["Content-Type"] = "application/json"
                        req_kwargs["content"] = json.dumps(request_payload).encode("utf-8")
                    elif isinstance(request_payload, str):
                        req_kwargs["content"] = request_payload.encode("utf-8")

                response = client.request(**req_kwargs)
                peer_ip = _verify_connected_peer_ip(
                    response,
                    block_private=effective_block_private,
                    allow_localhost=effective_allow_localhost,
                )
                if peer_ip and peer_ip not in resolved_peer_ips:
                    resolved_peer_ips.append(peer_ip)

                if response.is_redirect and "location" in response.headers:
                    redirect_chain.append(current_url)
                    if hop >= max_redirects:
                        elapsed = round((time.perf_counter() - start_time) * 1000, 2)
                        return HTTPExchangeSnapshot(
                            method=upper_method,
                            url=redact_url(current_url),
                            request_headers=redact_headers(req_headers),
                            query_params=redact_object(req_params),
                            request_body=redact_object(request_payload)
                            if settings.persist_request_bodies
                            else None,
                            response_status=response.status_code,
                            response_headers=redact_headers(dict(response.headers)),
                            elapsed_ms=elapsed,
                            redirect_chain=[redact_url(u) for u in redirect_chain],
                            error_type="TooManyRedirects",
                            error_message=f"Exceeded maximum allowed redirects ({max_redirects}).",
                        )

                    next_url = urljoin(current_url, response.headers["location"])
                    # Validate redirect target against SSRF before following
                    validate_url_ssrf(
                        next_url,
                        block_private_networks=effective_block_private,
                        allow_localhost_targets=effective_allow_localhost,
                        resolve_dns=transport is None,
                    )
                    # Strip sensitive auth headers on cross-origin redirect OR HTTPS-to-HTTP downgrade
                    next_parsed = httpx.URL(next_url)
                    curr_parsed = httpx.URL(current_url)
                    is_cross_origin = (
                        next_parsed.host != curr_parsed.host
                        or next_parsed.port != curr_parsed.port
                    )
                    is_scheme_downgrade = (
                        curr_parsed.scheme == "https" and next_parsed.scheme == "http"
                    )
                    if is_cross_origin or is_scheme_downgrade:
                        req_headers = {
                            k: v
                            for k, v in req_headers.items()
                            if k.lower()
                            not in ("authorization", "proxy-authorization", "cookie", "x-api-key")
                        }
                    current_url = next_url
                    if response.status_code in (301, 302, 303) and upper_method not in ("GET", "HEAD"):
                        upper_method = "GET"
                    continue
                break

            elapsed = round((time.perf_counter() - start_time) * 1000, 2)
            assert response is not None
            raw_bytes = response.content[:max_bytes]
            raw_text = raw_bytes.decode(response.encoding or "utf-8", errors="replace")

            parsed_body: Any = None
            if raw_text.strip():
                try:
                    parsed_body = redact_object(json.loads(raw_text))
                except Exception:
                    parsed_body = redact_text(raw_text[:4000])

            return HTTPExchangeSnapshot(
                method=(method or "GET").strip().upper(),
                url=redact_url(str(response.url)),
                request_headers=redact_headers(headers or {}),
                query_params=redact_object(req_params),
                request_body=redact_object(request_payload)
                if settings.persist_request_bodies
                else None,
                response_status=response.status_code,
                response_headers=redact_headers(dict(response.headers)),
                response_body=parsed_body,
                raw_response_text=redact_text(raw_text[:4000]),
                elapsed_ms=elapsed,
                redirect_chain=[redact_url(u) for u in redirect_chain],
                dns_resolved_ips=resolved_peer_ips,
            )

    except SSRFProtectionError:
        raise
    except Exception as exc:
        elapsed = round((time.perf_counter() - start_time) * 1000, 2)
        return HTTPExchangeSnapshot(
            method=upper_method,
            url=redact_url(current_url),
            request_headers=redact_headers(headers or {}),
            query_params=redact_object(req_params),
            request_body=redact_object(request_payload)
            if settings.persist_request_bodies
            else None,
            response_status=None,
            response_headers={},
            response_body=None,
            elapsed_ms=elapsed,
            redirect_chain=[redact_url(u) for u in redirect_chain],
            error_type=type(exc).__name__,
            error_message=redact_text(str(exc)),
        )
