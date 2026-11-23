#!/usr/bin/env python3
"""Standalone Agensi skill schema validation script for API Detective."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if (REPO_ROOT / "backend").exists() and str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _validate_fallback(payload: Any, schema: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for req in schema.get("required", []):
            if req not in payload or payload[req] is None:
                findings.append(
                    {
                        "diagnostic_id": "SCH-001",
                        "category": "schema",
                        "severity": "high",
                        "title": "Missing Required Schema Property",
                        "description": f"Required property '{req}' is missing.",
                        "evidence": [f"Missing key: {req}"],
                        "recommendation": f"Add '{req}' to the payload.",
                        "confidence": 0.99,
                        "status": "confirmed",
                    }
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a JSON payload against a JSON Schema.")
    parser.add_argument("--schema", required=True, help="Path to JSON Schema file")
    parser.add_argument("--payload", required=True, help="Path to JSON payload file")
    args = parser.parse_args()

    schema_path = Path(args.schema)
    payload_path = Path(args.payload)
    if not schema_path.exists() or not payload_path.exists():
        print(json.dumps({"valid": False, "error": "Schema or payload file not found."}), file=sys.stderr)
        return 2

    schema_obj = json.loads(schema_path.read_text(encoding="utf-8"))
    payload_obj = json.loads(payload_path.read_text(encoding="utf-8"))

    try:
        from backend.app.diagnostics.schema_validator import validate_payload_against_schema

        findings_models = validate_payload_against_schema(payload_obj, schema_obj)
        findings = [f.model_dump() for f in findings_models]
    except ImportError:
        findings = _validate_fallback(payload_obj, schema_obj)

    valid = len(findings) == 0
    print(json.dumps({"valid": valid, "findings": findings}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
