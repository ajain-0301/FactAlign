from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Run


def add(db: Session, run: Run) -> Run:
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get(db: Session, run_id: int) -> Run | None:
    return db.get(Run, run_id)


def delete(db: Session, run_id: int) -> bool:
    run = db.get(Run, run_id)
    if not run:
        return False
    db.delete(run)
    db.commit()
    return True


def _filters(stmt, q=None, language=None, strategy=None, date_from: date | None = None,
             date_to: date | None = None, saved_only: bool = False, experiment_id: int | None = None,
             evaluation_run_id: int | None = None):
    if saved_only:
        stmt = stmt.where(Run.saved.is_(True))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Run.title.ilike(like), Run.source_text.ilike(like), Run.summary.ilike(like)))
    if language:
        stmt = stmt.where(Run.language_detected == language)
    if strategy:
        stmt = stmt.where(Run.strategy == strategy)
    if date_from:
        stmt = stmt.where(Run.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        stmt = stmt.where(Run.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    if experiment_id is not None:
        stmt = stmt.where(Run.experiment_id == experiment_id)
    if evaluation_run_id is not None:
        stmt = stmt.where(Run.evaluation_run_id == evaluation_run_id)
    return stmt


def list_runs(db: Session, limit: int = 50, offset: int = 0, **f) -> tuple[list[Run], int]:
    base = _filters(select(Run), **f)
    total = db.scalar(_filters(select(func.count(Run.id)), **f)) or 0
    rows = db.scalars(base.order_by(Run.created_at.desc(), Run.id.desc()).limit(limit).offset(offset)).all()
    return list(rows), int(total)


def all_runs(db: Session, **f) -> list[Run]:
    return list(db.scalars(_filters(select(Run), **f).order_by(Run.created_at.asc(), Run.id.asc())).all())
