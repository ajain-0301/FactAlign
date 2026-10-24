from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.common import csv_response, json_response
from app.core import db as dbm
from app.core.errors import AppError
from app.repositories import runs as runs_repo
from app.services import engine

router = APIRouter(prefix="/api/history")


def _filters(q, language, strategy, date_from, date_to):
    return dict(q=q or None, language=language or None, strategy=strategy or None, date_from=date_from,
                date_to=date_to, saved_only=True)


@router.get("")
def list_history(q: str | None = None, language: str | None = None, strategy: str | None = None,
                 date_from: date | None = None, date_to: date | None = None,
                 limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                 db: Session = Depends(dbm.get_session)):
    rows, total = runs_repo.list_runs(db, limit=limit, offset=offset, **_filters(q, language, strategy, date_from, date_to))
    return {"total": total, "limit": limit, "offset": offset, "items": [engine.run_out(r, full=False) for r in rows]}


@router.get("/export")
def export_history(format: str = Query("json", pattern="^(json|csv)$"), q: str | None = None,
                   language: str | None = None, strategy: str | None = None,
                   date_from: date | None = None, date_to: date | None = None,
                   db: Session = Depends(dbm.get_session)):
    runs = runs_repo.all_runs(db, **_filters(q, language, strategy, date_from, date_to))
    if format == "csv":
        rows = [{"id": r.id, "created_at": r.created_at.isoformat(), "title": r.title or "", "language": r.language_detected,
                 "strategy": r.strategy, "mode": r.mode, "model": r.model, "length": r.length,
                 "source_words": r.source_words, "summary_words": r.summary_words,
                 "compression_ratio": r.compression_ratio, "inference_ms": r.inference_ms,
                 "claim_support_rate": ((r.verification or {}).get("metrics") or {}).get("support_rate"),
                 "summary": r.summary, "source": r.source_text} for r in runs]
        return csv_response(rows, "FactAlign_history.csv")
    return json_response([engine.run_out(r) for r in runs], "FactAlign_history.json")


@router.get("/{run_id}")
def get_run(run_id: int, db: Session = Depends(dbm.get_session)):
    run = runs_repo.get(db, run_id)
    if not run:
        raise AppError(f"Run {run_id} not found.", 404)
    return engine.run_out(run)


@router.post("/{run_id}/save")
def save_run(run_id: int, db: Session = Depends(dbm.get_session)):
    run = runs_repo.get(db, run_id)
    if not run:
        raise AppError(f"Run {run_id} not found.", 404)
    run.saved = True
    db.commit()
    return engine.run_out(run)


@router.delete("/{run_id}")
def delete_run(run_id: int, db: Session = Depends(dbm.get_session)):
    if not runs_repo.delete(db, run_id):
        raise AppError(f"Run {run_id} not found.", 404)
    return {"deleted": run_id}
