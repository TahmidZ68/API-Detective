# API Detective

**Investigate. Diagnose. Fix. Verify.**

API Detective is an open-source developer tool that investigates API integration failures, identifies probable root causes, recommends corrective actions, and verifies approved fixes.

[![Release: v0.1.0-alpha.2](https://img.shields.io/badge/release-v0.1.0--alpha.2-blue.svg)](CHANGELOG.md)
[![Status: Public Alpha](https://img.shields.io/badge/status-Public_Alpha_(Experimental)-amber.svg)](docs/RELEASE_READINESS.md)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB.svg)](pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688.svg)](backend/app/main.py)
[![React + TypeScript](https://img.shields.io/badge/Frontend-React_18_%2B_TypeScript-61DAFB.svg)](frontend/package.json)

---

## Table of Contents

1. [Project Status](#1-project-status)
2. [Key Features](#2-key-features)
3. [How It Works](#3-how-it-works)
4. [Screenshots & Visual Previews](#4-screenshots--visual-previews)
5. [Architecture](#5-architecture)
6. [Installation (Windows, macOS, Linux)](#6-installation-windows-macos-linux)
7. [Quick Start](#7-quick-start)
8. [CLI Examples](#8-cli-examples)
9. [Agent Usage & 7-Step Lifecycle](#9-agent-usage--7-step-lifecycle)
10. [Diagnostic Examples](#10-diagnostic-examples)
11. [Configuration](#11-configuration)
12. [Security Model](#12-security-model)
13. [Docker Deployment](#13-docker-deployment)
14. [Agensi Skill Installation](#14-agensi-skill-installation)
15. [Supported Diagnostics Catalog](#15-supported-diagnostics-catalog)
16. [Benchmark Results](#16-benchmark-results)
17. [Roadmap](#17-roadmap)
18. [Contributing](#18-contributing)
19. [License](#19-license)

---

## 1. Project Status

> **Public Alpha — Experimental Software (`v0.1.0-alpha.2`)**
>
> API Detective is under active open-source development. The deterministic diagnostic engine, 7-step agent orchestrator, CLI, React web dashboard, and Agensi skill package are functional and verified against a [25-scenario benchmark suite](docs/BENCHMARK_RESULTS.md), [security audit](docs/SECURITY_AUDIT.md), and [agent reliability audit](docs/AGENT_RELIABILITY.md).

---

## 2. Key Features

- **43-Check Deterministic Diagnostic Engine (No LLM Key Required)**: Operates 100% locally without requiring an external AI provider key.
- **7-Step Autonomous Investigation Agent**: Dynamically plans tool execution, correlates HTTP, OpenAPI, and repository evidence, and ranks competing root-cause hypotheses by confidence.
- **OpenAPI 3.0 / 3.1, Swagger 2.0 & JSON Schema Contract Intelligence**: Resolves local `$ref` pointers, matches parameterized URL templates (`/users/{id}`), and detects missing properties, type mismatches, enum violations, and response contract drift.
- **Repository-Aware Debugging**: Read-only static analyzer for Python (`requests`, `httpx`), JavaScript, TypeScript (`axios`, `fetch`), and `.env` files with symlink-escape and binary-file protection.
- **4-Level Controlled Repair & Rollback System**: Generates reviewable unified diffs (`Level 2`), enforces explicit developer approval (`Level 3`) with transactional backup and rollback, blocks unsafe edits (`verify=False`), and runs post-fix verification (`Level 4`).
- **Defense-in-Depth Security**: Recursive secret redaction (`***REDACTED***`), safe in-memory JWT metadata inspection, SSRF protection (blocking cloud metadata, IPv6-mapped IPv4, decimal/octal/hex IPs, and private networks), and redirect credential stripping.

---

## 3. How It Works

```text
[Symptom / Endpoint / OpenAPI Spec / Repository]
                       │
        ┌──────────────▼──────────────┐
        │  Step 1: Understand Context │
        └──────────────┬──────────────┘
        ┌──────────────▼──────────────┐
        │  Step 2: Build Tool Plan    │
        └──────────────┬──────────────┘
        ┌──────────────▼──────────────┐
        │  Step 3: Execute Tools      │ ──► Connectivity, Auth, Request,
        └──────────────┬──────────────┘     Schema, Response, Repo Inspector
        ┌──────────────▼──────────────┐
        │  Step 4: Rank Root Causes   │ ──► Separates root causes from symptoms
        └──────────────┬──────────────┘
        ┌──────────────▼──────────────┐
        │  Step 5: Generate Diffs     │ ──► Level 1 Explanation + Level 2 Unified Diff
        └──────────────┬──────────────┘
        ┌──────────────▼──────────────┐
        │  Step 6: Approved Repair    │ ──► Level 3 Patch Application (with Rollback)
        └──────────────┬──────────────┘
        ┌──────────────▼──────────────┐
        │  Step 7: Verify Outcome     │ ──► Level 4 Re-Inspection & Diagnostic Check
        └─────────────────────────────┘
```

---

## 4. Screenshots & Visual Previews

> **Screenshot Status (`v0.1.0-alpha.2`)**: In accordance with our no-fake-mockup policy, browser PNG captures (`overview-dashboard.png`, `investigation-workspace.png`, `diagnostic-findings.png`, `request-inspector.png`, `cli-output.png`) are documented as pending live capture in [`docs/screenshots/README.md`](docs/screenshots/README.md), while a real verbatim CLI capture is stored in [`docs/screenshots/cli_output.txt`](docs/screenshots/cli_output.txt).

| View | Route / Command | Key Elements |
|------|-----------------|--------------|
| **Overview Dashboard** | `http://localhost:5173/` | Persisted investigation counters, category bar chart, severity distribution, and live agent tool execution log. |
| **Investigation Workspace** | `http://localhost:5173/workspace` | 7-step agent timeline, ranked root-cause hypotheses, deterministic findings, unified diff viewer, and repair confirmation modal. |
| **Request Inspector** | `http://localhost:5173/inspector` | Side-by-side HTTP headers, query params, and payloads with `***REDACTED***` secret masking. |
| **Diagnostic Reports** | `http://localhost:5173/reports` | Interactive preview, copy, and download in `JSON`, `Markdown`, and standalone `HTML`. |
| **CLI Terminal Output** | `api-detective diagnose ...` | Rich-formatted terminal tables ([`docs/screenshots/cli_output.txt`](docs/screenshots/cli_output.txt)). |

---

## 5. Architecture

```text
api-detective/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes (/investigations, /diagnostics, /settings, /dashboard)
│   │   ├── core/           # Settings, SSRF & secret redaction security, structured logging
│   │   ├── diagnostics/    # 6 deterministic analyzers (CONN, AUTH, REQ, SCH, RES, INT)
│   │   ├── agent/          # 7-step orchestrator, planner, investigator, root_cause, fix_generator, verifier
│   │   ├── tools/          # http_client, openapi_parser, repository_inspector, log_analyzer, test_runner
│   │   ├── providers/      # Optional LLM provider adapter (OpenAI, Gemini, Anthropic, Local)
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── services/       # Investigation persistence & JSON/Markdown/HTML report exporters
│   │   └── schemas/        # Pydantic v2 data schemas
│   ├── migrations/         # Alembic database migrations
│   └── tests/              # Unit, security, API, and CLI tests
├── frontend/               # React 18 + TypeScript + Vite + Tailwind CSS + TanStack Query + Recharts
├── cli/api_detective/      # Typer & Rich CLI
├── skills/api-detective/   # Agensi Skill Package (SKILL.md, references/, scripts/)
├── examples/               # Sample OpenAPI spec, JSON Schema, payloads, and sample_repo
├── docs/                   # Architecture, API reference, security audit, agent reliability, benchmark results
└── tests/                  # 12-scenario integration suite & 25-scenario benchmark suite
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the complete system diagram.

---

## 6. Installation (Windows, macOS, Linux)

### Prerequisites
- **Python 3.12+**
- **Node.js 20+** and **npm 10+**

### 1. Clone & Set Up Python Virtual Environment

**Linux / macOS:**
```bash
git clone https://github.com/TahmidZ68/API-Detective.git
cd API-Detective
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/TahmidZ68/API-Detective.git
Set-Location API-Detective
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install
```

---

## 7. Quick Start

### Start the Backend API Server
```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

### Start the Web Dashboard
```bash
cd frontend
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 8. CLI Examples

```bash
# Check installed version
api-detective --version

# 1. Diagnose an endpoint offline or live
api-detective diagnose \
  --url https://api.orders.example.com/v1/orders \
  --method POST \
  --header "Authorization: Bearer Bearer token_example" \
  --data @examples/request.json \
  --spec examples/openapi.yaml \
  --simulated-status 401 \
  --no-live

# 2. Inspect and validate an OpenAPI 3.0/3.1 or Swagger 2.0 specification
api-detective inspect --file examples/openapi.yaml

# 3. Validate a JSON payload against a JSON Schema (exits 0 if valid, 1 if invalid)
api-detective validate \
  --schema examples/schema.json \
  --payload examples/request.json

# 4. Run a repository-aware investigation across Python/JS/TS source files
api-detective investigate --repo ./examples/sample_repo

# 5. Export the latest report as JSON, Markdown, or standalone HTML
api-detective report --format json
api-detective report --format markdown --output diagnostic_report.md
api-detective report --format html --output diagnostic_report.html

# 6. View runtime configuration (secrets masked)
api-detective config
```

---

## 9. Agent Usage & 7-Step Lifecycle

You can invoke the 7-step `AgentOrchestrator` directly from Python, the REST API (`POST /api/v1/investigations`), or the CLI (`api-detective investigate`):

```python
from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.schemas.diagnostics import InvestigationRequest

orchestrator = AgentOrchestrator()
report = orchestrator.run_investigation(
    InvestigationRequest(
        prompt="Why is my POST /v1/orders request failing with 401 and schema errors?",
        url="https://api.orders.example.com/v1/orders",
        method="POST",
        headers={"Authorization": "Bearer YOUR_API_KEY"},
        request_payload={"customer_id": "cust_1", "amount": "not_a_number"},
        simulated_response_status=401,
        execute_live_request=False,
    )
)

print("Top Root Cause:", report.root_causes[0].title, report.root_causes[0].confidence)
print("Proposed Diff:\n", report.remediation_plan[0].unified_diff)
```

See [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) and [docs/AGENT_RELIABILITY.md](docs/AGENT_RELIABILITY.md).

---

## 10. Diagnostic Examples

Every finding conforms to a strict schema distinguishing confirmed facts from hypotheses:

```json
{
  "diagnostic_id": "AUTH-003",
  "category": "authentication",
  "severity": "high",
  "title": "Expired JWT Bearer Token",
  "description": "The JWT token's 'exp' claim (1732370000) is in the past (expired 7200 seconds ago).",
  "evidence": [
    "JWT 'exp' claim timestamp: 1732370000",
    "Current UTC timestamp: 1732377200",
    "JWT algorithm: HS256"
  ],
  "recommendation": "Refresh the access token using your refresh token flow or generate a new short-lived JWT.",
  "confidence": 0.99,
  "status": "confirmed"
}
```

---

## 11. Configuration

Copy [`.env.example`](.env.example) to `.env` to customize settings:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:///./api_detective.db` | SQLAlchemy database URL (SQLite or PostgreSQL). |
| `BLOCK_PRIVATE_NETWORKS` | `true` | Block RFC 1918, IPv6 private, CGNAT, and link-local ranges. |
| `ALLOW_LOCALHOST_TARGETS` | `false` | Permit diagnosing `localhost` / `127.0.0.1` / `::1`. |
| `REDACT_SECRETS` | `true` | Mask tokens, keys, passwords, and PEM keys as `***REDACTED***`. |
| `PERSIST_REQUEST_BODIES` | `false` | Avoid persisting raw request bodies in database history. |
| `AGENT_MAX_ITERATIONS` | `6` | Maximum bounded tool-execution iterations per investigation. |
| `REQUIRE_APPROVAL_FOR_FILE_EDITS` | `true` | Require explicit developer approval before Level 3 file edits. |
| `LLM_PROVIDER` | `none` | Optional LLM synthesis (`none`, `openai`, `gemini`, `anthropic`, `local`). |

---

## 12. Security Model

- **SSRF & DNS Rebinding Protection**: Unconditionally blocks cloud metadata (`169.254.169.254`, `100.100.100.200`, `fd00:ec2::254`, `metadata.google.internal`), unwraps IPv6-mapped IPv4 (`::ffff:127.0.0.1`), blocks decimal/octal/hex IP encodings, and re-validates every redirect hop.
- **Credential Stripping on Redirects**: Automatically strips `Authorization`, `Proxy-Authorization`, `Cookie`, and `X-API-Key` headers on cross-origin redirects and `HTTPS -> HTTP` downgrade redirects.
- **Repository & Repair Safety**: Rejects symlinks and binary files during repository scans, backs up files before Level 3 edits with rollback support, and blocks unsafe patches (`verify=False`).

See [SECURITY.md](SECURITY.md) and [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md).

---

## 13. Docker Deployment

```bash
cp .env.example .env
docker compose up --build -d
```

- **Web Dashboard**: `http://localhost:5173`
- **Backend API & Health Check**: `http://localhost:8000/api/v1/health`

See [docs/SELF_HOSTING.md](docs/SELF_HOSTING.md) for production PostgreSQL and container hardening guides.

---

## 14. Agensi Skill Installation

API Detective includes a standalone Agensi skill package in [`skills/api-detective/`](skills/api-detective/SKILL.md) and a validated distributable archive at [`API-Detective-Agensi-Skill.zip`](API-Detective-Agensi-Skill.zip).

- Contains `SKILL.md`, 5 domain reference guides (`references/*.md`), and 3 standalone scripts (`scripts/diagnose.py`, `scripts/validate_schema.py`, `scripts/generate_report.py`) that operate even when extracted outside the main repository.

---

## 15. Supported Diagnostics Catalog

| ID Range | Category | Checks Included |
|----------|----------|-----------------|
| `CONN-001`..`008` | **Connectivity** | DNS resolution failure, TCP connection refused, request timeout, SSL/TLS verification failure, invalid URL format, redirect loops/downgrades/auth-stripping, CORS wildcard/origin mismatch, proxy 407/502/504 errors. |
| `AUTH-001`..`008` | **Authentication** | Missing Authorization header, placeholder/malformed Bearer token, expired/future JWT claims (`exp`/`nbf`), duplicate `Bearer Bearer` / malformed `Basic` header, OAuth 2.0 error codes, query-string credential leaks, missing scopes, HTTP 401 vs 403 triage. |
| `REQ-001`..`008` | **Request** | Disallowed HTTP method (405 / body on GET), missing required headers, Content-Type mismatch (415), malformed JSON syntax, unexpanded `{id}` path parameters, invalid query literals (`undefined`/`NaN`), empty POST/PUT payload, `[object Object]` / double-encoded JSON serialization bugs. |
| `SCH-001`..`006` | **Schema** | Missing required properties, unexpected `additionalProperties: false` fields, data type mismatches, enum violations, OpenAPI response contract mismatches, deprecated operations. |
| `RES-001`..`008` | **Response** | HTTP status mismatch (400/404/422), malformed response JSON, application errors inside HTTP 200 OK, empty 200 body, 5xx server failure, HTTP 429 rate limiting (`Retry-After`), pagination truncation, unexpected `text/html` response. |
| `INT-001`..`007` | **Integration** | Base URL mismatch, unset/placeholder `.env` variables, undocumented endpoint path with fuzzy matching, inconsistent `/v1/` vs `/v2/` prefixes, `camelCase` vs `snake_case` mismatch, unsafe SDK configuration (`verify=False`, missing timeout, hardcoded secrets). |

---

## 16. Benchmark Results

Evaluated against 25 real-world API failure scenarios and multi-language synthetic repositories ([`docs/BENCHMARK_RESULTS.md`](docs/BENCHMARK_RESULTS.md)):
- **Diagnostic Engine Detection**: `25 / 25 (100.0%)`
- **Agent Primary Root-Cause Ranking**: `25 / 25 (100.0%)`
- **False Positives / False Negatives**: `0 / 0`

---

## 17. Roadmap

See [ROADMAP.md](ROADMAP.md) for upcoming `v0.2.0` features (GraphQL & gRPC diagnostics, HAR/cURL import, multi-file AST refactoring).

---

## 18. Contributing

We welcome community contributions! Please review [CONTRIBUTING.md](CONTRIBUTING.md) and our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

## 19. License

Distributed under the **Apache License 2.0**. See [LICENSE](LICENSE) for full text.
