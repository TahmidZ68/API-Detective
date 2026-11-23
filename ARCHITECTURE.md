# API Detective System Architecture

API Detective is designed around a modular, deterministic-first architecture where the diagnostic engine, multi-step agent orchestrator, REST API, CLI, React web dashboard, and Agensi skill package operate with clear separation of concerns.

```mermaid
flowchart TD
    CLI["Typer & Rich CLI\n(cli/api_detective)"] --> Orchestrator["Agent Orchestrator\n(backend/app/agent/orchestrator.py)"]
    WebUI["React + TypeScript Dashboard\n(frontend/src)"] --> FastAPI["FastAPI REST Service\n(backend/app/main.py)"]
    Skill["Agensi Skill Scripts\n(skills/api-detective/scripts)"] --> Orchestrator
    FastAPI --> Service["Investigation Service\n(backend/app/services)"]
    Service --> Orchestrator
    Service --> DB[("SQLite / PostgreSQL\n(SQLAlchemy 2.x)")]

    Orchestrator --> Planner["Step 1-2: Context & Planner\n(planner.py)"]
    Orchestrator --> Investigator["Step 3: Bounded Tool Executor\n(investigator.py)"]
    Orchestrator --> RootCause["Step 4: Root-Cause Ranker\n(root_cause.py)"]
    Orchestrator --> FixGen["Step 5-6: Safe Fix & Diff Engine\n(fix_generator.py)"]
    Orchestrator --> Verifier["Step 7: Post-Fix Verifier\n(verifier.py)"]

    Investigator --> Tools["Tools Layer\n(http_client, openapi_parser, repository_inspector, log_analyzer)"]
    Investigator --> Diag["Deterministic Diagnostic Engine\n(connectivity, authentication, request, schema, response, integration)"]
    Orchestrator -. "Optional Redacted Synthesis" .-> LLM["LLM Provider Adapter\n(OpenAI / Gemini / Anthropic / Local)"]
```

## Layer Responsibilities

1. **Deterministic Diagnostic Engine (`backend/app/diagnostics/`)**:
   - Six pure, independently testable analyzers (`connectivity.py`, `authentication.py`, `request_analyzer.py`, `schema_validator.py`, `response_analyzer.py`, `integration_analyzer.py`).
   - Emits standardized `DiagnosticFinding` objects with `diagnostic_id`, `category`, `severity`, `confidence`, `status`, `evidence`, and `recommendation`.
2. **Tools Layer (`backend/app/tools/`)**:
   - `http_client.py`: SSRF-validated, redirect-checked HTTP execution with response size limits and automatic secret redaction.
   - `openapi_parser.py`: Parses OpenAPI 3.0/3.1, Swagger 2.0, and JSON Schema contracts, resolves local `$ref` pointers, and matches parameterized route templates.
   - `repository_inspector.py`: Read-only static scanner for Python (`httpx`, `requests`) and JavaScript/TypeScript (`axios`, `fetch`) codebases and `.env` configurations.
   - `log_analyzer.py` & `test_runner.py`: Extracts error signatures and executes Level 4 verification checks.
3. **Agent Engine (`backend/app/agent/`)**:
   - Implements the 7-step lifecycle (`Understand -> Plan -> Execute Tools -> Analyze Root Causes -> Generate Remediation Plan -> Apply Approved Changes -> Verify`) without depending on LangChain, LangGraph, or CrewAI.
4. **Security & Redaction Core (`backend/app/core/security.py`)**:
   - Enforces SSRF protections, DNS rebinding checks, secret masking, and prompt-injection isolation.
