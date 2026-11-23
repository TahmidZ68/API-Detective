"""Professional developer CLI for API Detective built with Typer and Rich."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
import yaml
from backend.app import __version__
from backend.app.core.config import get_settings, load_yaml_config, update_runtime_settings
from backend.app.core.exceptions import APIDetectiveError
from backend.app.database import SessionLocal, init_db
from backend.app.diagnostics.schema_validator import validate_payload_against_schema
from backend.app.schemas.diagnostics import (
    ApproveFixRequest,
    InvestigationReport,
    InvestigationRequest,
)
from backend.app.services.investigation_service import InvestigationService
from backend.app.services.report_exporter import (
    export_report_html,
    export_report_json,
    export_report_markdown,
)
from backend.app.tools.openapi_parser import inspect_openapi_spec, parse_spec_content
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="api-detective",
    help="API Detective — Open-Source Agentic API Debugging & Repair Toolkit (Investigate. Diagnose. Fix. Verify.)",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"API Detective v{__version__}")
        raise typer.Exit(code=0)


@app.callback()
def main_callback(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show the API Detective version and exit.",
    ),
) -> None:
    """API Detective CLI root callback."""


def _load_structured_file(path: Path) -> Any:
    if not path.exists():
        err_console.print(f"[bold red]Error:[/bold red] File not found: {path}")
        raise typer.Exit(code=2)
    text = path.read_text(encoding="utf-8")
    try:
        if path.suffix.lower() in (".yaml", ".yml"):
            return yaml.safe_load(text)
        return json.loads(text)
    except Exception:
        try:
            return yaml.safe_load(text)
        except Exception as exc:
            err_console.print(f"[bold red]Parse Error:[/bold red] Could not parse {path}: {exc}")
            raise typer.Exit(code=2) from exc


def _render_report_terminal(report: InvestigationReport) -> None:
    console.print(
        Panel(
            f"[bold cyan]Investigation ID:[/bold cyan] {report.investigation_id}\n"
            f"[bold cyan]Target:[/bold cyan] {report.http_method} {report.target_url or 'N/A'}\n"
            f"[bold cyan]Status:[/bold cyan] {report.status.upper()}\n"
            f"[bold cyan]Summary:[/bold cyan] {report.summary}",
            title="[bold white]API Detective Investigation Report[/bold white]",
            border_style="blue",
        )
    )

    if report.timeline:
        t_table = Table(title="Agent Execution Timeline", show_lines=False)
        t_table.add_column("#", style="dim", width=4)
        t_table.add_column("Phase", style="cyan")
        t_table.add_column("Tool", style="magenta")
        t_table.add_column("Summary")
        t_table.add_column("Time (ms)", justify="right", style="green")
        for s in report.timeline:
            t_table.add_row(
                str(s.step_number),
                s.phase,
                s.tool_name or "-",
                s.summary,
                f"{s.duration_ms:.2f}",
            )
        console.print(t_table)

    if report.findings:
        f_table = Table(title=f"Deterministic Diagnostic Findings ({len(report.findings)})", show_lines=True)
        f_table.add_column("ID", style="bold cyan", width=10)
        f_table.add_column("Severity", width=11)
        f_table.add_column("Category", width=15)
        f_table.add_column("Finding & Evidence")
        f_table.add_column("Recommendation", style="green")

        sev_color = {
            "critical": "bold red",
            "high": "red",
            "medium": "yellow",
            "low": "blue",
            "informational": "dim",
        }
        for f in report.findings:
            color = sev_color.get(f.severity, "white")
            ev_str = "\n".join(f"• {e}" for e in f.evidence[:3])
            f_table.add_row(
                f.diagnostic_id,
                f"[{color}]{f.severity.upper()}[/{color}]\n({int(f.confidence * 100)}%)",
                f.category,
                f"[bold]{f.title}[/bold]\n{f.description}\n[dim]{ev_str}[/dim]",
                f.recommendation,
            )
        console.print(f_table)
    else:
        console.print("[bold green]✓ No deterministic diagnostic defects detected.[/bold green]")

    if report.root_causes:
        rc_table = Table(title="Ranked Root-Cause Hypotheses")
        rc_table.add_column("Rank", width=6)
        rc_table.add_column("Hypothesis", style="bold")
        rc_table.add_column("Confidence", width=12)
        rc_table.add_column("Status", width=12)
        for rc in report.root_causes:
            rc_table.add_row(
                f"#{rc.rank}",
                f"{rc.title}\n[dim]{rc.explanation}[/dim]",
                f"{int(rc.confidence * 100)}%",
                rc.status,
            )
        console.print(rc_table)


@app.command("diagnose")
def diagnose_cmd(
    url: str = typer.Option(..., "--url", "-u", help="Target API endpoint URL"),
    method: str = typer.Option("GET", "--method", "-X", help="HTTP method (GET, POST, PUT, DELETE, etc.)"),
    header: list[str] | None = typer.Option(None, "--header", "-H", help="HTTP header in 'Key: Value' format"),
    data: str | None = typer.Option(None, "--data", "-d", help="JSON request body string or @filepath"),
    spec: Path | None = typer.Option(None, "--spec", "-s", help="Optional OpenAPI/Swagger file path"),
    simulated_status: int | None = typer.Option(None, "--simulated-status", help="Simulated HTTP response status for offline diagnosis"),
    allow_localhost: bool = typer.Option(False, "--allow-localhost", help="Permit diagnosing localhost targets"),
    no_live: bool = typer.Option(False, "--no-live", help="Skip live HTTP network call and analyze offline config"),
    output_format: str = typer.Option("text", "--format", "-f", help="Output format: text or json"),
    fail_on_issues: bool = typer.Option(False, "--fail-on-issues", help="Exit with code 1 if high/critical findings exist"),
) -> None:
    """Diagnose an API endpoint for connectivity, authentication, request, schema, and response issues."""
    headers_dict: dict[str, str] = {}
    for h in header or []:
        if ":" in h:
            k, v = h.split(":", 1)
            headers_dict[k.strip()] = v.strip()

    payload_obj: Any = None
    raw_text: str | None = None
    if data:
        if data.startswith("@"):
            fpath = Path(data[1:])
            if not fpath.exists():
                err_console.print(f"[bold red]Error:[/bold red] Payload file not found: {fpath}")
                raise typer.Exit(code=2)
            raw_text = fpath.read_text(encoding="utf-8")
        else:
            raw_text = data
        try:
            payload_obj = json.loads(raw_text)
        except Exception:
            payload_obj = None

    spec_obj: Any = None
    if spec:
        spec_obj = _load_structured_file(spec)

    req = InvestigationRequest(
        url=url,
        method=method.upper(),
        headers=headers_dict,
        request_payload=payload_obj,
        raw_request_text=raw_text,
        openapi_spec=spec_obj,
        simulated_response_status=simulated_status,
        execute_live_request=not no_live and simulated_status is None,
        allow_localhost=allow_localhost,
    )

    try:
        init_db()
        with SessionLocal() as db:
            svc = InvestigationService(db)
            report = svc.create_and_run_investigation(req)
    except APIDetectiveError as exc:
        if output_format.lower() == "json":
            typer.echo(json.dumps({"error": exc.code, "message": exc.message}, indent=2))
        else:
            err_console.print(f"[bold red][{exc.code}][/bold red] {exc.message}")
        raise typer.Exit(code=2) from exc

    if output_format.lower() == "json":
        typer.echo(export_report_json(report))
    else:
        _render_report_terminal(report)

    if fail_on_issues and any(f.severity in ("critical", "high") for f in report.findings):
        raise typer.Exit(code=1)


@app.command("inspect")
def inspect_cmd(
    file: Path = typer.Option(..., "--file", "-f", help="Path to OpenAPI 3.0/3.1 or Swagger YAML/JSON file"),
    output_format: str = typer.Option("text", "--format", help="Output format: text or json"),
) -> None:
    """Inspect and validate an OpenAPI or Swagger specification file."""
    if not file.exists():
        err_console.print(f"[bold red]Error:[/bold red] Specification file not found: {file}")
        raise typer.Exit(code=2)

    raw_text = file.read_text(encoding="utf-8")
    result = inspect_openapi_spec(raw_text)

    if output_format.lower() == "json":
        typer.echo(json.dumps(result.model_dump(), indent=2))
    else:
        status_badge = "[bold green]VALID[/bold green]" if result.valid else "[bold red]INVALID[/bold red]"
        console.print(
            Panel(
                f"[bold]Title:[/bold] {result.title}\n"
                f"[bold]Spec Version:[/bold] {result.spec_version}\n"
                f"[bold]Status:[/bold] {status_badge}\n"
                f"[bold]Base URLs:[/bold] {', '.join(result.base_urls) or 'None'}\n"
                f"[bold]Endpoints Count:[/bold] {len(result.endpoints)}\n"
                f"[bold]Security Schemes:[/bold] {len(result.security_schemes)}",
                title="[bold white]OpenAPI Specification Inspection[/bold white]",
                border_style="cyan",
            )
        )
        if result.endpoints:
            ep_table = Table(title="Documented Endpoints")
            ep_table.add_column("Method", style="bold cyan", width=10)
            ep_table.add_column("Path", style="white")
            ep_table.add_column("Summary")
            ep_table.add_column("Deprecated", width=12)
            for ep in result.endpoints:
                ep_table.add_row(
                    str(ep["method"]),
                    str(ep["path"]),
                    str(ep.get("summary", "")),
                    "Yes" if ep.get("deprecated") else "No",
                )
            console.print(ep_table)
        if result.errors:
            for err in result.errors:
                err_console.print(f"[bold red]Spec Error:[/bold red] {err}")

    if not result.valid:
        raise typer.Exit(code=1)


@app.command("validate")
def validate_cmd(
    schema: Path = typer.Option(..., "--schema", "-s", help="Path to JSON Schema or OpenAPI schema file"),
    payload: Path = typer.Option(..., "--payload", "-p", help="Path to JSON payload file"),
    output_format: str = typer.Option("text", "--format", help="Output format: text or json"),
) -> None:
    """Validate a JSON request or response payload against a JSON Schema file."""
    schema_obj = _load_structured_file(schema)
    payload_obj = _load_structured_file(payload)

    if not isinstance(schema_obj, dict):
        err_console.print("[bold red]Error:[/bold red] Schema file must contain a JSON/YAML object.")
        raise typer.Exit(code=2)

    findings = validate_payload_against_schema(payload_obj, schema_obj, context_label="payload")
    is_valid = len(findings) == 0

    if output_format.lower() == "json":
        typer.echo(
            json.dumps(
                {
                    "valid": is_valid,
                    "findings": [f.model_dump() for f in findings],
                },
                indent=2,
            )
        )
    else:
        if is_valid:
            console.print("[bold green]✓ Payload conforms to the provided JSON Schema.[/bold green]")
        else:
            console.print(f"[bold red]✗ Schema validation failed with {len(findings)} issue(s):[/bold red]")
            for f in findings:
                console.print(f"  • [bold cyan][{f.diagnostic_id}][/bold cyan] {f.title}: {f.description}")

    if not is_valid:
        raise typer.Exit(code=1)


@app.command("investigate")
def investigate_cmd(
    repo: Path | None = typer.Option(None, "--repo", "-r", help="Local repository path to inspect"),
    url: str | None = typer.Option(None, "--url", "-u", help="Optional target API URL"),
    method: str = typer.Option("GET", "--method", "-X", help="HTTP method"),
    prompt: str | None = typer.Option(None, "--prompt", "-p", help="Task description or error question"),
    spec: Path | None = typer.Option(None, "--spec", "-s", help="Optional OpenAPI spec file"),
    approve_fixes: bool = typer.Option(False, "--approve-fixes", help="Explicitly approve and verify generated repairs"),
    output_format: str = typer.Option("text", "--format", "-f", help="Output format: text or json"),
) -> None:
    """Run a full multi-step agentic investigation across a repository, endpoint, or specification."""
    spec_obj: Any = None
    if spec:
        spec_obj = parse_spec_content(spec.read_text(encoding="utf-8"))

    req = InvestigationRequest(
        prompt=prompt or (f"Investigate repository {repo}" if repo else "Investigate API integration"),
        url=url,
        method=method.upper(),
        repository_path=str(repo.resolve()) if repo else None,
        openapi_spec=spec_obj,
        execute_live_request=bool(url),
    )

    try:
        init_db()
        with SessionLocal() as db:
            svc = InvestigationService(db)
            report = svc.create_and_run_investigation(req)
            if approve_fixes and report.remediation_plan:
                for fix in list(report.remediation_plan):
                    report = svc.approve_and_apply_fix(
                        report.investigation_id,
                        ApproveFixRequest(
                            fix_id=fix.fix_id,
                            approved=True,
                            apply_changes=True,
                            run_verification=True,
                        ),
                    )
    except APIDetectiveError as exc:
        if output_format.lower() == "json":
            typer.echo(json.dumps({"error": exc.code, "message": exc.message}, indent=2))
        else:
            err_console.print(f"[bold red][{exc.code}][/bold red] {exc.message}")
        raise typer.Exit(code=2) from exc

    if output_format.lower() == "json":
        typer.echo(export_report_json(report))
    else:
        _render_report_terminal(report)
        if report.repository_analysis:
            ra = report.repository_analysis
            console.print(
                Panel(
                    f"[bold]Path:[/bold] {ra.repository_path}\n"
                    f"[bold]Files Scanned:[/bold] {ra.files_scanned}\n"
                    f"[bold]Languages:[/bold] {', '.join(ra.languages_detected) or 'None'}\n"
                    f"[bold]HTTP Clients:[/bold] {', '.join(ra.client_libraries_detected) or 'None'}\n"
                    f"[bold]Endpoints Discovered:[/bold] {', '.join(ra.endpoints_discovered[:8]) or 'None'}\n"
                    f"[bold]Env Vars Referenced:[/bold] {', '.join(ra.env_vars_referenced) or 'None'}",
                    title="[bold white]Repository Intelligence Summary[/bold white]",
                    border_style="magenta",
                )
            )


@app.command("report")
def report_cmd(
    investigation_id: str | None = typer.Option(None, "--id", help="Investigation ID (defaults to most recent)"),
    output_format: str = typer.Option("json", "--format", "-f", help="Report format: json, markdown, or html"),
    output_file: Path | None = typer.Option(None, "--output", "-o", help="Optional file path to save the exported report"),
) -> None:
    """Export an investigation report in JSON, Markdown, or standalone HTML format."""
    init_db()
    with SessionLocal() as db:
        svc = InvestigationService(db)
        svc.ensure_initial_diagnostic_baselines()
        if investigation_id:
            report = svc.get_investigation(investigation_id)
        else:
            recent = svc.list_investigations(limit=1)
            report = recent[0] if recent else None

    if not report:
        err_console.print("[bold red]Error:[/bold red] No investigation report found.")
        raise typer.Exit(code=2)

    fmt = output_format.lower()
    if fmt == "markdown":
        rendered = export_report_markdown(report)
    elif fmt == "html":
        rendered = export_report_html(report)
    else:
        rendered = export_report_json(report)

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(rendered, encoding="utf-8")
        console.print(f"[bold green]✓ Saved {fmt.upper()} report to {output_file}[/bold green]")
    else:
        typer.echo(rendered)


@app.command("config")
def config_cmd(
    file: Path | None = typer.Option(None, "--file", "-f", help="Load configuration overrides from a YAML file"),
    output_format: str = typer.Option("text", "--format", help="Output format: text or json"),
) -> None:
    """Display or load API Detective runtime configuration (with secrets masked)."""
    if file:
        loaded = load_yaml_config(file)
        update_runtime_settings(loaded)

    s = get_settings()
    safe_cfg = {
        "version": __version__,
        "app_env": s.app_env,
        "database_url": s.database_url,
        "block_private_networks": s.block_private_networks,
        "allow_localhost_targets": s.allow_localhost_targets,
        "http_timeout_seconds": s.http_timeout_seconds,
        "agent_max_iterations": s.agent_max_iterations,
        "redact_secrets": s.redact_secrets,
        "persist_request_bodies": s.persist_request_bodies,
        "llm_provider": s.llm_provider,
        "llm_model": s.llm_model,
        "llm_api_key_configured": bool(s.llm_api_key),
    }

    if output_format.lower() == "json":
        typer.echo(json.dumps(safe_cfg, indent=2))
    else:
        table = Table(title="API Detective Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        for k, v in safe_cfg.items():
            table.add_row(k, str(v))
        console.print(table)


if __name__ == "__main__":
    app()
