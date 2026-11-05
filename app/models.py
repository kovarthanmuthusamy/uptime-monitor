"""ORM models: the sites being monitored and the history of their checks."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Monitor(Base):
    """A website registered for monitoring."""

    __tablename__ = "monitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    checks: Mapped[list[Check]] = relationship(
        back_populates="monitor", cascade="all, delete-orphan"
    )


class Check(Base):
    """One probe of a monitor: up or down, with latency and error detail."""

    __tablename__ = "checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    monitor_id: Mapped[int] = mapped_column(
        ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    is_up: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)

    monitor: Mapped[Monitor] = relationship(back_populates="checks")
