from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Run(Base):
    """One summarization run (one strategy applied to one document)."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source_text: Mapped[str] = mapped_column(Text)
    reference_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    language_requested: Mapped[str] = mapped_column(String(20), default="auto")
    language_detected: Mapped[str] = mapped_column(String(20), index=True)
    output_language: Mapped[str] = mapped_column(String(20), default="same")
    length: Mapped[str] = mapped_column(String(10))
    strategy: Mapped[str] = mapped_column(String(20), index=True)
    mode: Mapped[str] = mapped_column(String(10))  # demo | real
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(Text)
    inference_ms: Mapped[float] = mapped_column(Float)
    source_words: Mapped[int] = mapped_column(Integer)
    summary_words: Mapped[int] = mapped_column(Integer)
    compression_ratio: Mapped[float] = mapped_column(Float)
    cmi: Mapped[float] = mapped_column(Float, default=0.0)
    compare_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    experiment_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    evaluation_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    saved: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    verification: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="completed")  # completed | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(10), default="demo")
    model: Mapped[str] = mapped_column(String(100), default="")
    language: Mapped[str] = mapped_column(String(20), default="all")
    strategies: Mapped[list] = mapped_column(JSON, default=list)
    length: Mapped[str] = mapped_column(String(10), default="medium")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    results: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    mode: Mapped[str] = mapped_column(String(10))
    model: Mapped[str] = mapped_column(String(100))
    dataset: Mapped[str] = mapped_column(String(100))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    results: Mapped[dict] = mapped_column(JSON, default=dict)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
