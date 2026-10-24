from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import db as dbm
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.repositories import runs as runs_repo
from app.schemas import VerifyRequest
from app.services import engine, settings_service

router = APIRouter(prefix="/api")


@router.post("/verify")
def verify(req: VerifyRequest, db: Session = Depends(dbm.get_session), settings: Settings = Depends(get_settings)):
    eff = settings_service.resolve(db, settings)
    run = None
    if req.run_id is not None:
        run = runs_repo.get(db, req.run_id)
        if not run:
            raise AppError(f"Run {req.run_id} not found.", 404)
    if len(req.source) > settings.max_input_chars or len(req.summary) > settings.max_input_chars:
        raise AppError("Source or summary exceeds the configured input limit.", 413)
    pages = [p.model_dump() for p in req.source_pages] if req.source_pages is not None else None
    if pages is None and run and req.source == run.source_text:
        pages = (run.extra or {}).get("source_pages")
    if pages is not None:
        cursor = 0
        for p in pages:
            if p['start'] < cursor or p['end'] <= p['start'] or p['end'] > len(req.source) or req.source[cursor:p['start']].strip():
                raise AppError("Page references must cover the source in nonoverlapping offset order.", 422)
            cursor = p['end']
        if req.source[cursor:].strip():
            raise AppError("Page references must cover the entire source.", 422)
    out = engine.verify_text(settings, eff, req.source, req.summary, req.method, source_pages=pages)
    if run:
        engine.attach_verification(db, run, out)
    return {**out, "run_id": run.id if run else None}
