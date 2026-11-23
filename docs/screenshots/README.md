# Application Screenshots (`docs/screenshots/`)

Per the API Detective release integrity policy, **no fabricated or synthetic mockup images are committed as fake application screenshots**.

## Capturing Live Screenshots Locally

Start the backend and frontend services locally:

```bash
# Terminal 1: Start FastAPI backend
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Start Vite frontend
cd frontend
npm run dev
```

Capture the five standard 1440×900 dark-mode screenshots from `http://localhost:5173`:

1. `overview-dashboard.png` — Route `/` (Diagnostic Overview with live SQLite telemetry and category distribution chart).
2. `investigation-workspace.png` — Route `/workspace` (7-step agent timeline, ranked root-cause hypotheses, and unified diff repair modal).
3. `diagnostic-findings.png` — Route `/workspace` scrolled to the Deterministic Diagnostic Findings and Level 4 Verification banner.
4. `request-inspector.png` — Route `/inspector` (Side-by-side HTTP headers and payloads with `***REDACTED***` secret masking).
5. `cli-output.png` — Terminal capture of `api-detective diagnose --url https://api.orders.example.com/v1/orders --method POST --simulated-status 401 --no-live`.

A real verbatim text capture of the CLI output from `v0.1.0-alpha.2` is preserved in [`cli_output.txt`](cli_output.txt).
