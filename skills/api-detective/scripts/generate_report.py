#!/usr/bin/env python3
"""Standalone Agensi skill report generator for API Detective (JSON, Markdown, HTML)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if (REPO_ROOT / "backend").exists() and str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Format an API Detective JSON report into Markdown, HTML, or JSON.")
    parser.add_argument("--input", required=True, help="Path to input investigation JSON file")
    parser.add_argument("--format", choices=["json", "markdown", "html"], default="markdown", help="Target format")
    parser.add_argument("--output", default=None, help="Optional output file path")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"Error: Input file not found: {in_path}", file=sys.stderr)
        return 2

    raw_data = json.loads(in_path.read_text(encoding="utf-8"))

    try:
        from backend.app.schemas.diagnostics import InvestigationReport
        from backend.app.services.report_exporter import (
            export_report_html,
            export_report_json,
            export_report_markdown,
        )

        report = InvestigationReport(**raw_data)
        if args.format == "markdown":
            rendered = export_report_markdown(report)
        elif args.format == "html":
            rendered = export_report_html(report)
        else:
            rendered = export_report_json(report)
    except ImportError:
        if args.format == "json":
            rendered = json.dumps(raw_data, indent=2)
        else:
            lines = [
                f"# API Detective Report — {raw_data.get('investigation_id', 'INV')}",
                "",
                f"**Summary:** {raw_data.get('summary', '')}",
                "",
                "## Findings",
            ]
            for f in raw_data.get("findings", []):
                lines.append(f"- **[{f.get('diagnostic_id')}] {f.get('title')}** ({f.get('severity')}): {f.get('recommendation')}")
            rendered = "\n".join(lines) + "\n"

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
