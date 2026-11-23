"""FastAPI entry point for API Detective backend service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app import __version__
from backend.app.api.routes import diagnostics, investigations, settings
from backend.app.core.config import get_settings
from backend.app.core.exceptions import APIDetectiveError
from backend.app.core.logging import configure_logging, get_logger
from backend.app.core.security import redact_text
from backend.app.database import SessionLocal, init_db
from backend.app.services.investigation_service import InvestigationService

logger = get_logger("api_detective.main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    cfg = get_settings()
    configure_logging(cfg.log_level)
    init_db()
    with SessionLocal() as db:
        svc = InvestigationService(db)
        svc.ensure_initial_diagnostic_baselines()
    logger.info("api_detective_started", version=__version__, env=cfg.app_env)
    yield


app = FastAPI(
    title="API Detective",
    description="Open-Source Agentic API Debugging & Repair Toolkit",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(APIDetectiveError)
async def handle_api_detective_error(_request: Request, exc: APIDetectiveError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "code": exc.code,
            "message": redact_text(exc.message),
            "details": exc.details,
        },
    )


@app.get("/api/v1/health", tags=["system"])
def health_check() -> dict[str, object]:
    cfg = get_settings()
    return {
        "status": "ok",
        "service": "api-detective",
        "version": __version__,
        "llm_provider": cfg.llm_provider,
        "deterministic_engine": "ready",
    }


app.include_router(investigations.router, prefix="/api/v1")
app.include_router(diagnostics.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")

# Optional single-port SPA serving when frontend production bundle is built
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if (_FRONTEND_DIST / "index.html").exists():
    if (_FRONTEND_DIST / "assets").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
            name="frontend-assets",
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str) -> FileResponse:
        candidate = (_FRONTEND_DIST / full_path).resolve()
        if (
            full_path
            and candidate.is_file()
            and _FRONTEND_DIST.resolve() in candidate.parents
        ):
            return FileResponse(str(candidate))
        return FileResponse(str(_FRONTEND_DIST / "index.html"))
