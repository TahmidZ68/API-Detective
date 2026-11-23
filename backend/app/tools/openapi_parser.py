"""OpenAPI 3.0 / 3.1, Swagger 2.0, and JSON Schema parser and contract matcher."""

from __future__ import annotations

import copy
import json
import re
from typing import Any
from urllib.parse import urlparse

import yaml

from backend.app.core.exceptions import SpecificationParseError
from backend.app.schemas.diagnostics import SpecInspectResponse


def parse_spec_content(raw_spec: str | dict[str, Any]) -> dict[str, Any]:
    """Parse an OpenAPI/Swagger/JSON Schema specification from string (JSON/YAML) or dict."""
    if isinstance(raw_spec, dict):
        return copy.deepcopy(raw_spec)
    if not isinstance(raw_spec, str) or not raw_spec.strip():
        raise SpecificationParseError("Specification content is empty or not a string/object.")
    text = raw_spec.strip()
    try:
        if text.startswith("{"):
            parsed = json.loads(text)
        else:
            parsed = yaml.safe_load(text)
    except Exception as exc:
        raise SpecificationParseError(f"Failed to parse specification as JSON or YAML: {exc}") from exc

    if not isinstance(parsed, dict):
        raise SpecificationParseError("Parsed specification root must be a JSON/YAML object.")
    return parsed


def resolve_json_pointer(root: dict[str, Any], ref: str, visited: set[str] | None = None) -> dict[str, Any]:
    """Resolve local JSON Pointer references like '#/components/schemas/User'."""
    if not ref.startswith("#/"):
        return {}
    seen = visited or set()
    if ref in seen:
        return {}
    seen.add(ref)
    parts = [p.replace("~1", "/").replace("~0", "~") for p in ref[2:].split("/")]
    current: Any = root
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return {}
    if isinstance(current, dict):
        return dereference_schema(current, root, seen)
    return {}


def dereference_schema(
    schema: dict[str, Any],
    root: dict[str, Any],
    visited: set[str] | None = None,
) -> dict[str, Any]:
    """Recursively dereference local '$ref' pointers in a JSON Schema dictionary."""
    if not isinstance(schema, dict):
        return {}
    seen = set(visited or set())
    if "$ref" in schema and isinstance(schema["$ref"], str):
        resolved = resolve_json_pointer(root, schema["$ref"], seen)
        merged = copy.deepcopy(resolved)
        for k, v in schema.items():
            if k != "$ref":
                merged[k] = v
        return merged

    result: dict[str, Any] = {}
    for k, v in schema.items():
        if k == "properties" and isinstance(v, dict):
            result[k] = {
                prop_name: dereference_schema(prop_val, root, seen)
                if isinstance(prop_val, dict)
                else prop_val
                for prop_name, prop_val in v.items()
            }
        elif k == "items" and isinstance(v, dict):
            result[k] = dereference_schema(v, root, seen)
        elif k in ("allOf", "anyOf", "oneOf") and isinstance(v, list):
            result[k] = [
                dereference_schema(item, root, seen) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            result[k] = v
    return result


def inspect_openapi_spec(raw_spec: str | dict[str, Any]) -> SpecInspectResponse:
    """Validate and extract metadata, base URLs, endpoints, and security schemes from OpenAPI/Swagger."""
    try:
        spec = parse_spec_content(raw_spec)
    except SpecificationParseError as exc:
        return SpecInspectResponse(
            valid=False,
            spec_version="unknown",
            title="Invalid Specification",
            errors=[exc.message],
        )

    errors: list[str] = []
    openapi_ver = str(spec.get("openapi") or spec.get("swagger") or "")
    if not openapi_ver:
        if "$schema" in spec or "type" in spec or "properties" in spec:
            return SpecInspectResponse(
                valid=True,
                spec_version="json-schema",
                title=str(spec.get("title", "JSON Schema Definition")),
                base_urls=[],
                endpoints=[],
                security_schemes=[],
                errors=[],
            )
        errors.append("Missing 'openapi' (3.0/3.1) or 'swagger' (2.0) version field.")

    raw_info = spec.get("info")
    info: dict[str, Any] = raw_info if isinstance(raw_info, dict) else {}
    title = str(info.get("title", "Untitled API"))

    base_urls: list[str] = []
    if isinstance(spec.get("servers"), list):
        for srv in spec["servers"]:
            if isinstance(srv, dict) and srv.get("url"):
                base_urls.append(str(srv["url"]))
    elif spec.get("host"):
        raw_schemes = spec.get("schemes")
        schemes: list[Any] = raw_schemes if isinstance(raw_schemes, list) else ["https"]
        base_path = str(spec.get("basePath", ""))
        for sch in schemes:
            base_urls.append(f"{sch}://{spec['host']}{base_path}")

    security_schemes: list[dict[str, Any]] = []
    raw_comp = spec.get("components")
    components: dict[str, Any] = raw_comp if isinstance(raw_comp, dict) else {}
    raw_sec = components.get("securitySchemes") or spec.get("securityDefinitions") or {}
    if isinstance(raw_sec, dict):
        for name, sec_def in raw_sec.items():
            if isinstance(sec_def, dict):
                security_schemes.append(
                    {
                        "name": name,
                        "type": sec_def.get("type", "unknown"),
                        "scheme": sec_def.get("scheme"),
                        "in": sec_def.get("in"),
                        "parameter_name": sec_def.get("name"),
                    }
                )

    paths = spec.get("paths")
    endpoints: list[dict[str, Any]] = []
    if not isinstance(paths, dict):
        errors.append("Specification is missing a valid 'paths' object.")
    else:
        http_verbs = {"get", "post", "put", "patch", "delete", "options", "head"}
        for path_str, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for verb, op in path_item.items():
                if verb.lower() not in http_verbs or not isinstance(op, dict):
                    continue
                endpoints.append(
                    {
                        "path": path_str,
                        "method": verb.upper(),
                        "summary": op.get("summary") or op.get("operationId") or "",
                        "deprecated": bool(op.get("deprecated", False)),
                    }
                )

    return SpecInspectResponse(
        valid=len(errors) == 0,
        spec_version=openapi_ver or "unknown",
        title=title,
        base_urls=base_urls,
        endpoints=endpoints,
        security_schemes=security_schemes,
        errors=errors,
    )


def _path_template_matches(template_path: str, actual_path: str) -> bool:
    """Return True if an OpenAPI path template like '/users/{id}' matches '/users/42'."""
    norm_t = "/" + template_path.strip("/")
    norm_a = "/" + actual_path.strip("/")
    if norm_t == norm_a:
        return True
    pattern = re.sub(r"\{[^/]+\}", r"[^/]+", norm_t)
    return bool(re.fullmatch(pattern, norm_a))


def extract_operation_contract(
    raw_spec: str | dict[str, Any],
    url: str,
    method: str,
) -> dict[str, Any]:
    """Extract the documented contract for a target URL and HTTP method from an OpenAPI spec."""
    spec = parse_spec_content(raw_spec)
    parsed_url = urlparse(url)
    actual_path = parsed_url.path or "/"
    upper_method = method.strip().upper()

    # Determine base urls and strip base path prefix if present
    inspect_res = inspect_openapi_spec(spec)
    relative_path = actual_path
    for base_u in inspect_res.base_urls:
        base_parsed = urlparse(base_u)
        if base_parsed.path and base_parsed.path != "/" and actual_path.startswith(base_parsed.path):
            relative_path = "/" + actual_path[len(base_parsed.path) :].lstrip("/")
            break

    raw_paths = spec.get("paths")
    paths: dict[str, Any] = raw_paths if isinstance(raw_paths, dict) else {}
    matched_template: str | None = None
    matched_path_item: dict[str, Any] | None = None
    version_stripped_path = re.sub(r"^/(?:api/)?v\d+(?:\.\d+)?(?=/|$)", "", actual_path) or "/"

    for path_str, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        if (
            _path_template_matches(path_str, relative_path)
            or _path_template_matches(path_str, actual_path)
            or _path_template_matches(path_str, version_stripped_path)
        ):
            matched_template = path_str
            matched_path_item = path_item
            break

    contract: dict[str, Any] = {
        "spec_title": inspect_res.title,
        "spec_version": inspect_res.spec_version,
        "base_urls": inspect_res.base_urls,
        "all_paths": list(paths.keys()),
        "path_matched": matched_template is not None,
        "matched_path_template": matched_template,
        "allowed_methods": [],
        "operation_found": False,
        "deprecated": False,
        "required_headers": [],
        "required_query_params": [],
        "query_param_schemas": {},
        "auth_required": False,
        "expected_auth_scheme": None,
        "expected_key_location": None,
        "expected_key_name": None,
        "required_scopes": [],
        "request_schema": None,
        "response_schemas": {},
    }

    if not matched_path_item:
        return contract

    http_verbs = {"get", "post", "put", "patch", "delete", "options", "head"}
    allowed = [v.upper() for v in matched_path_item if v.lower() in http_verbs]
    contract["allowed_methods"] = allowed

    op = matched_path_item.get(upper_method.lower())
    if not isinstance(op, dict):
        return contract

    contract["operation_found"] = True
    contract["deprecated"] = bool(op.get("deprecated", False))

    # Parameters (path-level + operation-level)
    all_params: list[dict[str, Any]] = []
    for p_list in (matched_path_item.get("parameters"), op.get("parameters")):
        if isinstance(p_list, list):
            for p in p_list:
                if isinstance(p, dict):
                    resolved_p = dereference_schema(p, spec)
                    all_params.append(resolved_p)

    for p in all_params:
        p_in = str(p.get("in", "")).lower()
        p_name = str(p.get("name", ""))
        p_req = bool(p.get("required", False))
        raw_ps = p.get("schema")
        p_schema: dict[str, Any] = raw_ps if isinstance(raw_ps, dict) else p
        if p_in == "header" and p_req and p_name:
            contract["required_headers"].append(p_name)
        elif p_in == "query" and p_name:
            if p_req:
                contract["required_query_params"].append(p_name)
            contract["query_param_schemas"][p_name] = dereference_schema(p_schema, spec)
        elif p_in == "body" and isinstance(p.get("schema"), dict):
            # Swagger 2.0 body parameter
            contract["request_schema"] = dereference_schema(p["schema"], spec)

    # OpenAPI 3.x requestBody
    req_body = op.get("requestBody")
    if isinstance(req_body, dict):
        req_body = dereference_schema(req_body, spec)
        raw_content = req_body.get("content")
        content: dict[str, Any] = raw_content if isinstance(raw_content, dict) else {}
        for media_type, media_obj in content.items():
            if "json" in media_type.lower() and isinstance(media_obj, dict):
                raw_s = media_obj.get("schema")
                if isinstance(raw_s, dict):
                    contract["request_schema"] = dereference_schema(raw_s, spec)
                    break

    # Responses
    raw_responses = op.get("responses")
    responses: dict[str, Any] = raw_responses if isinstance(raw_responses, dict) else {}
    for status_key, resp_obj in responses.items():
        if not isinstance(resp_obj, dict):
            continue
        resp_obj = dereference_schema(resp_obj, spec)
        raw_rcontent = resp_obj.get("content")
        content = raw_rcontent if isinstance(raw_rcontent, dict) else {}
        for media_type, media_obj in content.items():
            if "json" in media_type.lower() and isinstance(media_obj, dict):
                raw_s = media_obj.get("schema")
                if isinstance(raw_s, dict):
                    contract["response_schemas"][str(status_key)] = dereference_schema(raw_s, spec)
                    break
        # Swagger 2.0 response schema
        if str(status_key) not in contract["response_schemas"] and isinstance(resp_obj.get("schema"), dict):
            contract["response_schemas"][str(status_key)] = dereference_schema(resp_obj["schema"], spec)

    # Security requirements
    sec_reqs = op.get("security") if "security" in op else spec.get("security")
    raw_comps = spec.get("components")
    components: dict[str, Any] = raw_comps if isinstance(raw_comps, dict) else {}
    sec_defs = components.get("securitySchemes") or spec.get("securityDefinitions") or {}

    if isinstance(sec_reqs, list) and len(sec_reqs) > 0:
        for req_item in sec_reqs:
            if not isinstance(req_item, dict):
                continue
            for scheme_name, scopes in req_item.items():
                contract["auth_required"] = True
                if isinstance(scopes, list):
                    contract["required_scopes"].extend(str(s) for s in scopes)
                scheme_def = sec_defs.get(scheme_name) if isinstance(sec_defs, dict) else None
                if isinstance(scheme_def, dict):
                    s_type = str(scheme_def.get("type", "")).lower()
                    if s_type == "http":
                        contract["expected_auth_scheme"] = str(scheme_def.get("scheme", "Bearer"))
                        contract["expected_key_location"] = "header"
                    elif s_type == "apikey":
                        contract["expected_auth_scheme"] = "apiKey"
                        contract["expected_key_location"] = str(scheme_def.get("in", "header"))
                        contract["expected_key_name"] = str(scheme_def.get("name", "X-API-Key"))
                    elif s_type in ("oauth2", "openidconnect"):
                        contract["expected_auth_scheme"] = "Bearer"
                        contract["expected_key_location"] = "header"

    return contract
