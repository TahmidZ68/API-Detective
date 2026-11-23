"""Schema diagnostics module.

Validates request and response payloads against JSON Schema and OpenAPI 3.0/3.1/Swagger 2.0 contracts.
Detects missing required properties, unexpected properties, incorrect data types,
enum mismatches, contract mismatches, and API version incompatibilities.
"""

from __future__ import annotations

from typing import Any

from backend.app.core.exceptions import SpecificationParseError
from backend.app.schemas.diagnostics import DiagnosticFinding, HTTPExchangeSnapshot
from backend.app.tools.openapi_parser import (
    dereference_schema,
    extract_operation_contract,
    parse_spec_content,
)

JSON_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
    "null": (type(None),),
}


def _matches_json_type(value: Any, expected_type: str) -> bool:
    """Return True if a Python value matches the JSON Schema primitive or container type."""
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    allowed = JSON_TYPE_MAP.get(expected_type)
    if not allowed:
        return True
    return isinstance(value, allowed)


def validate_payload_against_schema(
    payload: Any,
    schema: dict[str, Any],
    *,
    context_label: str = "request",
    path_prefix: str = "$",
) -> list[DiagnosticFinding]:
    """Recursively validate a payload against a JSON Schema and return structured findings."""
    findings: list[DiagnosticFinding] = []
    if not isinstance(schema, dict) or not schema:
        return findings

    resolved = dereference_schema(schema, schema)

    # Handle allOf combinations
    if isinstance(resolved.get("allOf"), list):
        for sub_schema in resolved["allOf"]:
            if isinstance(sub_schema, dict):
                findings.extend(
                    validate_payload_against_schema(
                        payload, sub_schema, context_label=context_label, path_prefix=path_prefix
                    )
                )

    expected_type = resolved.get("type")
    nullable = bool(resolved.get("nullable", False))
    if payload is None and nullable:
        return findings

    if isinstance(expected_type, list):
        if not any(_matches_json_type(payload, str(t)) for t in expected_type):
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="SCH-003",
                    category="schema",
                    severity="high",
                    title=f"Incorrect Data Type at '{path_prefix}' ({context_label})",
                    description=f"Field '{path_prefix}' in {context_label} has type '{type(payload).__name__}', but schema requires one of {expected_type}.",
                    evidence=[
                        f"Location: {path_prefix}",
                        f"Expected type(s): {expected_type}",
                        f"Actual Python/JSON type: {type(payload).__name__}",
                    ],
                    recommendation=f"Convert '{path_prefix}' to type {expected_type}.",
                    confidence=0.99,
                    status="confirmed",
                )
            )
            return findings
    elif isinstance(expected_type, str):
        if not _matches_json_type(payload, expected_type):
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="SCH-003",
                    category="schema",
                    severity="high",
                    title=f"Incorrect Data Type at '{path_prefix}' ({context_label})",
                    description=f"Field '{path_prefix}' in {context_label} has type '{type(payload).__name__}', but schema expects '{expected_type}'.",
                    evidence=[
                        f"Location: {path_prefix}",
                        f"Expected type: {expected_type}",
                        f"Actual type: {type(payload).__name__}",
                    ],
                    recommendation=f"Ensure '{path_prefix}' is serialized as a valid JSON '{expected_type}'.",
                    confidence=0.99,
                    status="confirmed",
                )
            )
            return findings

    # Enum validation
    if "enum" in resolved and isinstance(resolved["enum"], list):
        allowed_enums = resolved["enum"]
        if payload not in allowed_enums:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="SCH-004",
                    category="schema",
                    severity="high",
                    title=f"Enum Value Mismatch at '{path_prefix}' ({context_label})",
                    description=f"Value '{payload}' at '{path_prefix}' is not one of the allowed enum values.",
                    evidence=[
                        f"Location: {path_prefix}",
                        f"Actual value: {payload!r}",
                        f"Allowed enum values: {allowed_enums}",
                    ],
                    recommendation=f"Use one of the documented enum values for '{path_prefix}': {allowed_enums}.",
                    confidence=0.99,
                    status="confirmed",
                )
            )

    # Object validation
    if isinstance(payload, dict):
        required_props = resolved.get("required")
        if isinstance(required_props, list):
            missing = [req for req in required_props if req not in payload or payload[req] is None]
            if missing:
                findings.append(
                    DiagnosticFinding(
                        diagnostic_id="SCH-001",
                        category="schema",
                        severity="high",
                        title=f"Missing Required Schema Property in {context_label.title()}",
                        description=f"Required property/properties {', '.join(repr(m) for m in missing)} missing at '{path_prefix}'.",
                        evidence=[
                            f"Object path: {path_prefix}",
                            f"Missing required properties: {', '.join(missing)}",
                            f"Provided keys: {sorted(payload.keys())}",
                        ],
                        recommendation=f"Include the required field(s) ({', '.join(missing)}) in the {context_label} payload.",
                        confidence=0.99,
                        status="confirmed",
                    )
                )

        raw_props = resolved.get("properties")
        properties: dict[str, Any] = raw_props if isinstance(raw_props, dict) else {}
        additional_props = resolved.get("additionalProperties", True)

        if properties:
            unexpected = [k for k in payload if k not in properties]
            if unexpected and additional_props is False:
                findings.append(
                    DiagnosticFinding(
                        diagnostic_id="SCH-002",
                        category="schema",
                        severity="medium",
                        title=f"Unexpected Property Rejected by Schema at '{path_prefix}'",
                        description=f"The {context_label} contains property/properties not permitted by 'additionalProperties: false': {', '.join(unexpected)}.",
                        evidence=[
                            f"Object path: {path_prefix}",
                            f"Unexpected keys: {', '.join(unexpected)}",
                            f"Allowed properties: {sorted(properties.keys())}",
                        ],
                        recommendation=f"Remove undocumented property/properties ({', '.join(unexpected)}) or check for field naming typos.",
                        confidence=0.97,
                        status="confirmed",
                    )
                )

        for prop_key, prop_schema in properties.items():
            if prop_key in payload and isinstance(prop_schema, dict):
                findings.extend(
                    validate_payload_against_schema(
                        payload[prop_key],
                        prop_schema,
                        context_label=context_label,
                        path_prefix=f"{path_prefix}.{prop_key}",
                    )
                )

    # Array validation
    elif isinstance(payload, list):
        item_schema = resolved.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(payload[:25]):
                findings.extend(
                    validate_payload_against_schema(
                        item,
                        item_schema,
                        context_label=context_label,
                        path_prefix=f"{path_prefix}[{idx}]",
                    )
                )

    return findings


def analyze_schema(
    *,
    url: str | None = None,
    method: str = "GET",
    request_payload: Any | None = None,
    exchange: HTTPExchangeSnapshot | None = None,
    openapi_spec: str | dict[str, Any] | None = None,
    request_schema: dict[str, Any] | None = None,
    expected_response_schema: dict[str, Any] | None = None,
) -> list[DiagnosticFinding]:
    """Run schema and OpenAPI contract diagnostics on request and response payloads."""
    findings: list[DiagnosticFinding] = []
    contract: dict[str, Any] | None = None

    if openapi_spec is not None:
        try:
            spec_dict = parse_spec_content(openapi_spec)
            if url:
                contract = extract_operation_contract(spec_dict, url, method)
                if contract["deprecated"]:
                    findings.append(
                        DiagnosticFinding(
                            diagnostic_id="SCH-006",
                            category="schema",
                            severity="medium",
                            title="Deprecated API Endpoint Operation",
                            description=f"Operation '{method.upper()} {contract['matched_path_template']}' is marked as deprecated in the OpenAPI specification.",
                            evidence=[
                                f"Operation: {method.upper()} {contract['matched_path_template']}",
                                "OpenAPI flag: deprecated=true",
                            ],
                            recommendation="Migrate to the replacement endpoint version documented in the API specification.",
                            confidence=0.96,
                            status="confirmed",
                        )
                    )
        except SpecificationParseError as exc:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="SCH-005",
                    category="schema",
                    severity="high",
                    title="Invalid OpenAPI or JSON Schema Specification",
                    description=exc.message,
                    evidence=[exc.message],
                    recommendation="Fix syntax or structural errors in the provided OpenAPI/Swagger specification.",
                    confidence=1.0,
                    status="confirmed",
                )
            )

    # Validate request payload against explicit request_schema or OpenAPI operation request_schema
    active_req_schema = request_schema or (contract.get("request_schema") if contract else None)
    if active_req_schema and request_payload is not None and not isinstance(request_payload, str):
        findings.extend(
            validate_payload_against_schema(
                request_payload, active_req_schema, context_label="request", path_prefix="$"
            )
        )

    # Validate response payload against expected_response_schema or OpenAPI operation response_schemas
    resp_body = exchange.response_body if exchange else None
    resp_status = exchange.response_status if exchange else None

    active_resp_schema = expected_response_schema
    if not active_resp_schema and contract and contract.get("response_schemas"):
        resp_schemas = contract["response_schemas"]
        if resp_status and str(resp_status) in resp_schemas:
            active_resp_schema = resp_schemas[str(resp_status)]
        elif "200" in resp_schemas and (resp_status is None or 200 <= resp_status < 300):
            active_resp_schema = resp_schemas["200"]
        elif "default" in resp_schemas:
            active_resp_schema = resp_schemas["default"]

    if active_resp_schema and resp_body is not None and not isinstance(resp_body, str):
        resp_findings = validate_payload_against_schema(
            resp_body, active_resp_schema, context_label="response", path_prefix="$"
        )
        for rf in resp_findings:
            findings.append(
                DiagnosticFinding(
                    diagnostic_id="SCH-005",
                    category="schema",
                    severity=rf.severity,
                    title=f"Response Contract Mismatch: {rf.title}",
                    description=rf.description,
                    evidence=rf.evidence,
                    recommendation="Align the client response parser or backend serializer with the documented response schema.",
                    confidence=rf.confidence,
                    status=rf.status,
                )
            )

    return findings
