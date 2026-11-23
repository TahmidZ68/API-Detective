"""Repository-aware inspection tool for Python, JavaScript, and TypeScript integrations.

Operates through a controlled read-only inspection layer by default.
Enforces symlink and path-traversal protection, binary file filtering, and hardcoded secret detection.
Never transmits repository source code to external LLM providers without explicit user consent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from backend.app.core.exceptions import RepositoryAccessError
from backend.app.core.security import redact_text
from backend.app.schemas.diagnostics import (
    DiagnosticFinding,
    RepositoryAnalysisResult,
    RepositoryFinding,
)

IGNORED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        "dist",
        "build",
        ".next",
        ".vite",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "coverage",
    }
)

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".env": "env",
    ".yaml": "config",
    ".yml": "config",
    ".json": "config",
}

URL_PATTERN = re.compile(r"""['"](https?://[A-Za-z0-9._~:/?#\[\]@!$&()*+,;=%-]+)['"]""")
API_PATH_PATTERN = re.compile(
    r"""['"](/api/[A-Za-z0-9._~:/?#\[\]{}-]+|/v\d+/[A-Za-z0-9._~:/?#\[\]{}-]+)['"]"""
)

PY_ENV_PATTERN = re.compile(
    r"""(?:os\.environ\.get|os\.getenv|os\.environ\[)\s*\(?\s*['"]([A-Z0-9_]+)['"]"""
)
JS_ENV_PATTERN = re.compile(
    r"""(?:process\.env\.([A-Z0-9_]+)|import\.meta\.env\.([A-Z0-9_]+))"""
)

HARDCODED_SECRET_RE = re.compile(
    r"(?:\bsk-(?:proj-|live-|test-)?[A-Za-z0-9]{16,}\b|"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b|"
    r"\bAKIA[0-9A-Z]{16}\b|"
    r"\bAIza[0-9A-Za-z\-_]{30,}\b|"
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----)"
)


def _is_within_root(candidate: Path, root: Path) -> bool:
    """Return True if candidate's resolved real path is strictly inside root."""
    try:
        resolved = candidate.resolve()
        return resolved == root or root in resolved.parents
    except Exception:
        return False


def _is_binary_file(fpath: Path) -> bool:
    """Return True if the first 4096 bytes of fpath contain a null byte."""
    try:
        with fpath.open("rb") as bf:
            chunk = bf.read(4096)
        return b"\x00" in chunk
    except Exception:
        return True


def inspect_repository(
    repo_path: str | Path,
    *,
    max_files: int = 300,
    max_file_bytes: int = 512 * 1024,
) -> RepositoryAnalysisResult:
    """Scan a local repository in read-only mode to map API clients, endpoints, env vars, and bugs."""
    raw_path = Path(repo_path)
    if not raw_path.exists() or not raw_path.is_dir():
        raise RepositoryAccessError(
            f"Repository path '{repo_path}' does not exist or is not a directory."
        )
    root = raw_path.resolve()

    files_scanned = 0
    languages_detected: set[str] = set()
    clients_detected: set[str] = set()
    endpoints_discovered: set[str] = set()
    env_vars_referenced: set[str] = set()
    defined_env_vars: dict[str, str] = {}
    findings: list[RepositoryFinding] = []
    diagnostic_findings: list[DiagnosticFinding] = []

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Prune ignored directories and any symlinked directories
        safe_dirs: list[str] = []
        for d in dirnames:
            if d in IGNORED_DIRS:
                continue
            d_path = Path(dirpath) / d
            if d_path.is_symlink() or not _is_within_root(d_path, root):
                continue
            safe_dirs.append(d)
        dirnames[:] = safe_dirs

        for fname in sorted(filenames):
            if files_scanned >= max_files:
                break
            fpath = Path(dirpath) / fname

            # Reject symlinks and any path resolving outside the repository root
            if fpath.is_symlink() or not _is_within_root(fpath, root):
                continue

            rel_path = fpath.resolve().relative_to(root).as_posix()

            ext = fpath.suffix.lower()
            if fname.startswith(".env"):
                lang = "env"
            elif ext in SUPPORTED_EXTENSIONS:
                lang = SUPPORTED_EXTENSIONS[ext]
            else:
                continue

            try:
                stat_res = fpath.stat()
                if stat_res.st_size > max_file_bytes:
                    continue
                if _is_binary_file(fpath):
                    continue
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            files_scanned += 1
            if lang in ("python", "javascript", "typescript"):
                languages_detected.add(lang)

            lines = content.splitlines()

            # Parse .env files for defined keys (without storing raw secrets)
            if lang == "env":
                for idx, line in enumerate(lines, start=1):
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#") or "=" not in stripped:
                        continue
                    k, v = stripped.split("=", 1)
                    key_clean = k.strip()
                    val_clean = v.strip().strip("'\"")
                    defined_env_vars[key_clean] = val_clean
                    if not val_clean or val_clean.lower() in (
                        "changeme",
                        "your_api_key",
                        "todo",
                        "xxx",
                    ):
                        findings.append(
                            RepositoryFinding(
                                file_path=rel_path,
                                line_number=idx,
                                language="env",
                                client_library="dotenv",
                                pattern_type="config_mismatch",
                                snippet=f"{key_clean}={redact_text(val_clean) or '<EMPTY>'}",
                                note=f"Environment variable '{key_clean}' is empty or set to a placeholder.",
                            )
                        )
                continue

            if lang not in ("python", "javascript", "typescript"):
                continue

            # Detect client libraries in file
            file_client = "stdlib"
            if lang == "python":
                if "httpx" in content:
                    file_client = "httpx"
                    clients_detected.add("httpx")
                elif "requests" in content:
                    file_client = "requests"
                    clients_detected.add("requests")
                elif "aiohttp" in content:
                    file_client = "aiohttp"
                    clients_detected.add("aiohttp")
            else:
                if "axios" in content:
                    file_client = "axios"
                    clients_detected.add("axios")
                elif "fetch(" in content or "window.fetch" in content:
                    file_client = "fetch"
                    clients_detected.add("fetch")
                elif "http.request" in content or "https.request" in content:
                    file_client = "node-http"
                    clients_detected.add("node-http")

            for idx, line in enumerate(lines, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith(("#", "//")):
                    continue

                # 0. Hardcoded secret detection (redacted)
                if HARDCODED_SECRET_RE.search(line):
                    findings.append(
                        RepositoryFinding(
                            file_path=rel_path,
                            line_number=idx,
                            language=lang,  # type: ignore[arg-type]
                            client_library=file_client,
                            pattern_type="auth_config",
                            snippet=redact_text(stripped[:160]),
                            note="Hardcoded API key or private key literal detected in source code.",
                        )
                    )
                    diagnostic_findings.append(
                        DiagnosticFinding(
                            diagnostic_id="INT-007",
                            category="integration",
                            severity="critical",
                            title=f"Hardcoded Secret Credential in Source File ({rel_path}:{idx})",
                            description=f"File '{rel_path}' at line {idx} contains a hardcoded API key or private key literal.",
                            evidence=[f"{rel_path}:{idx} -> {redact_text(stripped[:120])}"],
                            recommendation="Move credentials out of source files into environment variables or a secret manager, and rotate the exposed credential.",
                            confidence=0.98,
                            status="confirmed",
                            metadata={"file_path": rel_path, "line_number": idx},
                        )
                    )

                # 1. URLs & API endpoints
                for url_match in URL_PATTERN.findall(line):
                    endpoints_discovered.add(url_match)
                    findings.append(
                        RepositoryFinding(
                            file_path=rel_path,
                            line_number=idx,
                            language=lang,  # type: ignore[arg-type]
                            client_library=file_client,
                            pattern_type="endpoint",
                            snippet=redact_text(stripped[:160]),
                            note=f"Discovered hardcoded endpoint URL: {redact_text(url_match)}",
                        )
                    )
                for path_match in API_PATH_PATTERN.findall(line):
                    endpoints_discovered.add(path_match)
                    findings.append(
                        RepositoryFinding(
                            file_path=rel_path,
                            line_number=idx,
                            language=lang,  # type: ignore[arg-type]
                            client_library=file_client,
                            pattern_type="endpoint",
                            snippet=redact_text(stripped[:160]),
                            note=f"Discovered API route path: {path_match}",
                        )
                    )

                # 2. Environment variable references
                for env_m in PY_ENV_PATTERN.findall(line):
                    env_vars_referenced.add(env_m)
                    findings.append(
                        RepositoryFinding(
                            file_path=rel_path,
                            line_number=idx,
                            language=lang,  # type: ignore[arg-type]
                            client_library=file_client,
                            pattern_type="env_reference",
                            snippet=redact_text(stripped[:160]),
                            note=f"References environment variable '{env_m}'.",
                        )
                    )
                for js_m1, js_m2 in JS_ENV_PATTERN.findall(line):
                    env_name = js_m1 or js_m2
                    if env_name:
                        env_vars_referenced.add(env_name)
                        findings.append(
                            RepositoryFinding(
                                file_path=rel_path,
                                line_number=idx,
                                language=lang,  # type: ignore[arg-type]
                                client_library=file_client,
                                pattern_type="env_reference",
                                snippet=redact_text(stripped[:160]),
                                note=f"References environment variable '{env_name}'.",
                            )
                        )

                # 3. Request construction
                if any(
                    call in line
                    for call in (
                        "requests.get(",
                        "requests.post(",
                        "requests.put(",
                        "requests.delete(",
                        "httpx.get(",
                        "httpx.post(",
                        "client.get(",
                        "client.post(",
                        "axios.get(",
                        "axios.post(",
                        "fetch(",
                    )
                ):
                    findings.append(
                        RepositoryFinding(
                            file_path=rel_path,
                            line_number=idx,
                            language=lang,  # type: ignore[arg-type]
                            client_library=file_client,
                            pattern_type="request_construction",
                            snippet=redact_text(stripped[:160]),
                            note=f"HTTP client request invocation using {file_client}.",
                        )
                    )
                    if lang == "python" and "requests." in line and "timeout" not in content:
                        diagnostic_findings.append(
                            DiagnosticFinding(
                                diagnostic_id="INT-007",
                                category="integration",
                                severity="medium",
                                title=f"Missing Timeout in Python 'requests' Call ({rel_path}:{idx})",
                                description=f"File '{rel_path}' at line {idx} invokes 'requests' without an explicit timeout parameter, which can hang workers indefinitely.",
                                evidence=[f"{rel_path}:{idx} -> {redact_text(stripped[:120])}"],
                                recommendation="Add an explicit timeout parameter (e.g., timeout=10) to all requests.* calls.",
                                confidence=0.91,
                                status="confirmed",
                                metadata={"file_path": rel_path, "line_number": idx},
                            )
                        )

                # 4. Insecure SSL disablement
                if "verify=False" in line or "rejectUnauthorized: false" in line:
                    findings.append(
                        RepositoryFinding(
                            file_path=rel_path,
                            line_number=idx,
                            language=lang,  # type: ignore[arg-type]
                            client_library=file_client,
                            pattern_type="config_mismatch",
                            snippet=redact_text(stripped[:160]),
                            note="TLS certificate verification is explicitly disabled in code.",
                        )
                    )
                    diagnostic_findings.append(
                        DiagnosticFinding(
                            diagnostic_id="INT-007",
                            category="integration",
                            severity="high",
                            title=f"TLS Certificate Verification Disabled in Code ({rel_path}:{idx})",
                            description=f"Source file '{rel_path}:{idx}' disables SSL/TLS verification, exposing API traffic to man-in-the-middle attacks.",
                            evidence=[f"{rel_path}:{idx} -> {redact_text(stripped[:120])}"],
                            recommendation="Enable TLS verification (verify=True / rejectUnauthorized: true) and configure a valid CA certificate bundle.",
                            confidence=0.98,
                            status="confirmed",
                            metadata={"file_path": rel_path, "line_number": idx},
                        )
                    )

                # 5. Auth configuration patterns
                if any(
                    tok in line.lower()
                    for tok in ("authorization", "x-api-key", "bearer ", "api_key")
                ):
                    findings.append(
                        RepositoryFinding(
                            file_path=rel_path,
                            line_number=idx,
                            language=lang,  # type: ignore[arg-type]
                            client_library=file_client,
                            pattern_type="auth_config",
                            snippet=redact_text(stripped[:160]),
                            note="Authentication header or credential wiring.",
                        )
                    )
                    if "Bearer Bearer " in line:
                        diagnostic_findings.append(
                            DiagnosticFinding(
                                diagnostic_id="AUTH-004",
                                category="authentication",
                                severity="high",
                                title=f"Duplicate 'Bearer' Prefix in Source File ({rel_path}:{idx})",
                                description=f"File '{rel_path}:{idx}' constructs an Authorization header with duplicated 'Bearer Bearer ' prefix.",
                                evidence=[f"{rel_path}:{idx} -> {redact_text(stripped[:120])}"],
                                recommendation="Use a single 'Bearer ' prefix when constructing the Authorization header.",
                                confidence=0.98,
                                status="confirmed",
                                metadata={"file_path": rel_path, "line_number": idx},
                            )
                        )

                # 6. Response parsing logic
                if any(
                    tok in line
                    for tok in (".json()", "JSON.parse(", "raise_for_status()", "response.status")
                ):
                    findings.append(
                        RepositoryFinding(
                            file_path=rel_path,
                            line_number=idx,
                            language=lang,  # type: ignore[arg-type]
                            client_library=file_client,
                            pattern_type="response_parsing",
                            snippet=redact_text(stripped[:160]),
                            note="HTTP response parsing or status check logic.",
                        )
                    )

    # Cross-check referenced env vars against defined .env keys
    if defined_env_vars and env_vars_referenced:
        missing_in_env = sorted(k for k in env_vars_referenced if k not in defined_env_vars)
        if missing_in_env:
            diagnostic_findings.append(
                DiagnosticFinding(
                    diagnostic_id="INT-002",
                    category="integration",
                    severity="high",
                    title="Environment Variables Referenced in Code Missing From .env",
                    description=f"Code references environment variable(s) {', '.join(missing_in_env)}, which are not defined in the repository's .env file.",
                    evidence=[
                        f"Referenced in code: {sorted(env_vars_referenced)}",
                        f"Missing from .env: {missing_in_env}",
                    ],
                    recommendation=f"Add {', '.join(missing_in_env)} to your environment configuration.",
                    confidence=0.93,
                    status="probable",
                )
            )

    return RepositoryAnalysisResult(
        repository_path=str(root),
        files_scanned=files_scanned,
        languages_detected=sorted(languages_detected),
        client_libraries_detected=sorted(clients_detected),
        endpoints_discovered=sorted(endpoints_discovered),
        env_vars_referenced=sorted(env_vars_referenced),
        findings=findings,
        diagnostic_findings=diagnostic_findings,
    )
