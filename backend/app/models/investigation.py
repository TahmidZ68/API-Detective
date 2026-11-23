"""ORM model for persisted API Detective investigations."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from backend.app.database import Base


class InvestigationRecord(Base):
    """Stores structured investigation reports with secrets redacted."""

    __tablename__ = "investigations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    investigation_id = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="completed")
    target_url = Column(String(1024), nullable=True)
    http_method = Column(String(16), nullable=False, default="GET")
    findings_count = Column(Integer, nullable=False, default=0)
    highest_severity = Column(String(32), nullable=False, default="informational")
    report_json = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
