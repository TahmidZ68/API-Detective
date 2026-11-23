"""FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.services.investigation_service import InvestigationService


def get_investigation_service(db: Session = Depends(get_db)) -> InvestigationService:
    """Provide an InvestigationService bound to the request database session."""
    return InvestigationService(db)
