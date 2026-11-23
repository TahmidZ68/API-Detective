"""Tests for FastAPI endpoints, Typer CLI commands, and Agensi skill scripts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from backend.app.main import app
from cli.api_detective.main import app as cli_app
from fastapi.testclient import TestClient
from typer.testing import CliRunner

runner = CliRunner()


def test_fastapi_endpoints() -> None:
    with TestClient(app) as client:
        # 1. Health check
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        # 2. Dashboard overview (uses real database baselines)
        overview = client.get("/api/v1/dashboard/overview")
        assert overview.status_code == 200
        ov_data = overview.json()
        assert ov_data["total_investigations"] >= 3
        assert len(ov_data["recent_investigations"]) >= 3

        # 3. Create new investigation
        create_resp = client.post(
            "/api/v1/investigations",
            json={
                "title": "Test 401 Investigation",
                "prompt": "Why is my API returning 401?",
                "url": "https://api.example.com/v1/profile",
                "method": "GET",
                "headers": {},
                "simulated_response_status": 401,
                "execute_live_request": False,
            },
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        inv_id = created["investigation_id"]
        assert any(f["diagnostic_id"] == "AUTH-001" for f in created["findings"])

        # 4. Get investigation & approve fix
        get_resp = client.get(f"/api/v1/investigations/{inv_id}")
        assert get_resp.status_code == 200
        fix_id = created["remediation_plan"][0]["fix_id"]

        approve_resp = client.post(
            f"/api/v1/investigations/{inv_id}/approve-fix",
            json={
                "fix_id": fix_id,
                "approved": True,
                "apply_changes": False,
                "run_verification": True,
            },
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["verification"]["verified"] is True

        # 5. Export report in JSON, Markdown, and HTML
        for fmt in ("json", "markdown", "html"):
            exp = client.get(f"/api/v1/investigations/{inv_id}/export?format={fmt}")
            assert exp.status_code == 200
            assert len(exp.text) > 50

        # 6. Standalone schema validation & spec inspection
        val_resp = client.post(
            "/api/v1/diagnostics/validate-schema",
            json={
                "schema_def": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}},
                "payload": {},
            },
        )
        assert val_resp.status_code == 200
        assert val_resp.json()["valid"] is False

        spec_resp = client.post(
            "/api/v1/diagnostics/inspect-spec",
            json={
                "content": {
                    "openapi": "3.0.3",
                    "info": {"title": "Demo", "version": "1.0"},
                    "paths": {"/ping": {"get": {"responses": {"200": {"description": "ok"}}}}},
                }
            },
        )
        assert spec_resp.status_code == 200
        assert spec_resp.json()["valid"] is True

        # 7. Settings get & update
        s_get = client.get("/api/v1/settings")
        assert s_get.status_code == 200
        s_put = client.put("/api/v1/settings", json={"agent_max_iterations": 8})
        assert s_put.status_code == 200
        assert s_put.json()["agent_max_iterations"] == 8


def test_cli_commands() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    # 1. diagnose command (JSON output)
    res_diag = runner.invoke(
        cli_app,
        [
            "diagnose",
            "--url",
            "https://api.example.com/v1/users",
            "--method",
            "GET",
            "--simulated-status",
            "401",
            "--no-live",
            "--format",
            "json",
        ],
    )
    assert res_diag.exit_code == 0
    diag_data = json.loads(res_diag.stdout)
    assert any(f["diagnostic_id"] == "AUTH-001" for f in diag_data["findings"])

    # 2. inspect command
    res_insp = runner.invoke(
        cli_app,
        ["inspect", "--file", str(repo_root / "examples" / "openapi.yaml"), "--format", "json"],
    )
    assert res_insp.exit_code == 0
    assert json.loads(res_insp.stdout)["valid"] is True

    # 3. validate command
    res_val = runner.invoke(
        cli_app,
        [
            "validate",
            "--schema",
            str(repo_root / "examples" / "schema.json"),
            "--payload",
            str(repo_root / "examples" / "request.json"),
            "--format",
            "json",
        ],
    )
    assert res_val.exit_code == 0
    assert json.loads(res_val.stdout)["valid"] is True

    # 4. investigate command on example repository
    res_inv = runner.invoke(
        cli_app,
        [
            "investigate",
            "--repo",
            str(repo_root / "examples" / "sample_repo"),
            "--format",
            "json",
        ],
    )
    assert res_inv.exit_code == 0
    inv_data = json.loads(res_inv.stdout)
    assert inv_data["repository_analysis"]["files_scanned"] >= 2

    # 5. config command
    res_cfg = runner.invoke(cli_app, ["config", "--format", "json"])
    assert res_cfg.exit_code == 0
    assert json.loads(res_cfg.stdout)["redact_secrets"] is True


def test_agensi_skill_scripts(tmp_path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    scripts_dir = repo_root / "skills" / "api-detective" / "scripts"
    out_json = tmp_path / "diag_out.json"
    out_md = tmp_path / "report.md"

    p1 = subprocess.run(
        [
            sys.executable,
            str(scripts_dir / "diagnose.py"),
            "--url",
            "https://api.example.com/v1/orders",
            "--method",
            "POST",
            "--status",
            "401",
            "--output",
            str(out_json),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert p1.returncode == 0
    assert out_json.exists()

    p2 = subprocess.run(
        [
            sys.executable,
            str(scripts_dir / "generate_report.py"),
            "--input",
            str(out_json),
            "--format",
            "markdown",
            "--output",
            str(out_md),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert p2.returncode == 0
    assert "AUTH-001" in out_md.read_text(encoding="utf-8")

    p3 = subprocess.run(
        [
            sys.executable,
            str(scripts_dir / "validate_schema.py"),
            "--schema",
            str(repo_root / "examples" / "schema.json"),
            "--payload",
            str(repo_root / "examples" / "request.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert p3.returncode == 0
    assert json.loads(p3.stdout)["valid"] is True
