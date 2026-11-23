---
name: api-detective
description: >-
  Investigate, diagnose, plan, fix, and verify API integration failures across
  connectivity, authentication, request construction, OpenAPI/JSON Schema contracts,
  HTTP responses, and repository source code. Produces deterministic, secret-redacted
  diagnostic reports and reviewable unified diffs without requiring external LLM API keys.
---

# API Detective — Agentic API Debugging & Repair Toolkit (`v0.1.0-alpha.2`)

**Investigate. Diagnose. Fix. Verify.**

API Detective is an open-source, deterministic-first API debugging and repair toolkit that diagnoses why API integrations fail, ranks root-cause hypotheses with verifiable evidence, generates reviewable patches, and verifies approved fixes.

---

## Mandatory Operating Rules

1. **Evidence-Based Diagnosis Only**: Never fabricate diagnostic findings, tool outputs, or root causes. Distinguish **confirmed** findings (backed by HTTP headers, status codes, JWT metadata, or schema validation errors) from **probable** or **possible** hypotheses.
2. **Strict Secret Protection**: Redact all API keys, Bearer tokens, Basic credentials, cookies, and sensitive query parameters (`***REDACTED***`) in every command output, log, and report. Never attempt to bypass authentication or discover credentials.
3. **SSRF & Network Safety**: Do not send probes to cloud metadata endpoints (`169.254.169.254`), link-local addresses, or unauthorized private internal networks. Only target `localhost` when the user explicitly requests local server debugging (`--allow-localhost`).
4. **Explicit Permission Before Modifying Code**: Always operate in read-only inspection mode first. Generate a unified diff (`Level 2`) and request explicit developer approval before modifying any repository file (`Level 3`) or running post-fix verification (`Level 4`). Never disable SSL verification (`verify=False`), weaken authentication, or alter production credentials.

---

## 10-Step Agent Investigation Workflow

Follow these ten steps whenever a user asks you to troubleshoot an API error, inspect an OpenAPI contract, validate a payload, or debug an integration in a repository:

### Step 1 — Understand the User's API Problem
Identify the failure symptom (e.g., `HTTP 401 Unauthorized`, `HTTP 422 Unprocessable Entity`, `CORS error`, `Malformed JSON`, `Timeout`, or unexpected response fields).

### Step 2 — Collect Relevant Diagnostic Information
Gather the available artifacts from the user or repository:
- Target endpoint URL and HTTP method (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`).
- Request headers, query parameters, and request payload.
- Observed response status code, response headers, response body, or error logs.
- OpenAPI (`3.0`/`3.1`), Swagger (`2.0`), or JSON Schema specification files.
- Local repository path (Python `httpx`/`requests`, JavaScript/TypeScript `axios`/`fetch`).

### Step 3 — Select Appropriate Diagnostic Operations
Choose the deterministic script(s) matching the collected evidence:
- `scripts/diagnose.py` for endpoint connectivity, authentication, request, response, or repository analysis.
- `scripts/validate_schema.py` for OpenAPI or JSON Schema payload validation.
- `scripts/generate_report.py` for compiling JSON, Markdown, or standalone HTML diagnostic reports.

### Step 4 — Execute Available Tools
Run the standalone scripts from the skill directory (or invoke `api-detective` CLI when installed):

```bash
# 1. Diagnose an endpoint or simulated failure
python scripts/diagnose.py \
  --url "https://api.example.com/v1/orders" \
  --method POST \
  --header "Authorization: Bearer <TOKEN>" \
  --header "Content-Type: application/json" \
  --data '{"customer_id": "c_1", "amount": "invalid"}' \
  --status 401

# 2. Validate a request or response payload against a JSON Schema
python scripts/validate_schema.py \
  --schema path/to/schema.json \
  --payload path/to/payload.json

# 3. Generate a formatted Markdown, JSON, or HTML diagnostic report
python scripts/generate_report.py \
  --input diagnosis_output.json \
  --format markdown \
  --output api_detective_report.md
```

### Step 5 — Analyze Findings
Consult the reference guides in `references/` to interpret the diagnostic codes:
- [references/diagnostics.md](references/diagnostics.md) — Complete catalog of `CONN-*`, `AUTH-*`, `REQ-*`, `SCH-*`, `RES-*`, and `INT-*` codes.
- [references/authentication.md](references/authentication.md) — Safe JWT claim inspection, OAuth error codes, and 401 vs 403 triage.
- [references/schemas.md](references/schemas.md) — OpenAPI 3.0/3.1, Swagger 2.0, and JSON Schema contract validation rules.
- [references/troubleshooting.md](references/troubleshooting.md) — Step-by-step remediation playbooks for common integration failures.
- [references/security.md](references/security.md) — Secret redaction, SSRF guards, and safe code repair boundaries.

### Step 6 — Identify Likely Root Causes
Rank the root-cause hypotheses by confidence and status (`confirmed`, `probable`, `possible`). Separate primary root causes (e.g., `AUTH-003 Expired JWT Bearer Token` or `SCH-001 Missing Required Schema Property`) from downstream symptoms (`AUTH-008 HTTP 401` or `RES-001 HTTP 422`).

### Step 7 — Propose Actionable Fixes
For each root cause, present a structured remediation plan containing:
- **Problem & Root Cause**
- **Supporting Evidence** (redacted headers, status codes, schema paths, or `file:line` references)
- **Recommended Solution** & **Risk Level** (`low`, `medium`, `high`)
- **Reviewable Unified Diff** (`Level 2`)
- **Verification Procedure**

### Step 8 — Request Permission Before Modifying Code
Ask the user for explicit approval before applying any file patch (`Level 3`) or executing state-changing requests.

### Step 9 — Verify Fixes When Possible
After the user approves and applies a fix, re-run `scripts/diagnose.py` or `scripts/validate_schema.py` (`Level 4`) to confirm that previous high/critical findings are resolved and no regressions remain.

### Step 10 — Present a Structured Final Report
Summarize the investigation timeline, confirmed root causes, applied or proposed patches, and verification status, and provide the path to any generated `.json`, `.md`, or `.html` report artifact.
