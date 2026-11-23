#!/usr/bin/env python3
"""Standalone Agensi skill diagnostic runner for API Detective."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Add repository root to sys.path when running inside the repo checkout
REPO_ROOT = Path(__file__).resolve().parents[3]
if (REPO_ROOT / "backend").exists() and str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _run_with_engine(args: argparse.Namespace) -> dict[str, Any]:
    from backend.app.agent.orchestrator import AgentOrchestrator
    from backend.app.schemas.diagnostics import InvestigationRequest

    headers: dict[str, str] = {}
    for h in args.header or []:
        if ":" in h:
            k, v = h.split(":", 1)
            headers[k.strip()] = v.strip()

    payload_obj: Any = None
    if args.data:
        try:
            payload_obj = json.loads(args.data)
        except Exception:
            payload_obj = None

    req = InvestigationRequest(
        url=args.url,
        method=args.method.upper(),
        headers=headers,
        request_payload=payload_obj,
        raw_request_text=args.data,
        simulated_response_status=args.status,
        repository_path=args.repo,
        execute_live_request=bool(args.live and args.url and args.status is None),
        allow_localhost=args.allow_localhost,
    )
    orchestrator = AgentOrchestrator()
    report = orchestrator.run_investigation(req)
    return report.model_dump()


def _run_standalone_fallback(args: argparse.Namespace) -> dict[str, Any]:
    """Self-contained stdlib diagnostic fallback if run outside the full package."""
    findings: list[dict[str, Any]] = []
    headers: dict[str, str] = {}
    for h in args.header or []:
        if ":" in h:
            k, v = h.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    if args.status in (401, 403) and "authorization" not in headers and "x-api-key" not in headers:
        findings.append(
            {
                "diagnostic_id": "AUTH-001",
                "category": "authentication",
                "severity": "high",
                "title": "Missing Authorization Header",
                "description": "The request does not contain an authorization header.",
                "evidence": ["Authorization header was not present."],
                "recommendation": "Provide the required authentication credentials.",
                "confidence": 0.98,
                "status": "confirmed",
            }
        )
    if args.data:
        try:
            json.loads(args.data)
        except json.JSONDecodeError as exc:
            findings.append(
                {
                    "diagnostic_id": "REQ-004",
                    "category": "request",
                    "severity": "critical",
                    "title": "Malformed JSON in Request Payload",
                    "description": f"JSON syntax error: {exc.msg}",
                    "evidence": [str(exc)],
                    "recommendation": "Fix JSON syntax errors in the request payload.",
                    "confidence": 1.0,
                    "status": "confirmed",
                }
            )
    return {
        "investigation_id": "INV-STANDALONE",
        "title": f"{args.method.upper()} {args.url or args.repo or 'Diagnostic Run'}",
        "status": "completed",
        "target_url": args.url,
        "http_method": args.method.upper(),
        "findings": findings,
        "summary": f"Completed standalone diagnosis with {len(findings)} finding(s).",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="API Detective — Endpoint & Repository Diagnostic Script")
    parser.add_argument("--url", type=str, default=None, help="Target API endpoint URL")
    parser.add_argument("--method", type=str, default="GET", help="HTTP method")
    parser.add_argument("--header", action="append", default=[], help="HTTP header ('Key: Value')")
    parser.add_argument("--data", type=str, default=None, help="Raw JSON request payload string")
    parser.add_argument("--status", type=int, default=None, help="Observed or simulated HTTP response status")
    parser.add_argument("--repo", type=str, default=None, help="Optional local repository path to scan")
    parser.add_argument("--live", action="store_true", help="Execute live HTTP request")
    parser.add_argument("--allow-localhost", action="store_true", help="Permit localhost targets")
    parser.add_argument("--output", type=str, default=None, help="Optional path to write JSON report")
    args = parser.parse_args()

    try:
        result = _run_with_engine(args)
    except ImportError:
        result = _run_standalone_fallback(args)

    formatted = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(formatted, encoding="utf-8")
    else:
        print(formatted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
