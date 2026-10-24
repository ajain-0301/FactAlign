from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import __version__
from app.core import db as dbm
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.services import samples, settings_service

router = APIRouter(prefix="/api")


@router.get("/health")
def health(db: Session = Depends(dbm.get_session), settings: Settings = Depends(get_settings)):
    try:
        dbm.ping()
        db_state = "ok"
    except Exception:  # noqa: BLE001
        db_state = "error"
    try:
        mode = settings_service.resolve(db, settings).mode
    except AppError:
        mode = "unavailable"
    except Exception:  # noqa: BLE001
        mode = "unavailable"
    if db_state != "ok":
        raise HTTPException(503, detail="Database unavailable")
    return {"status": "ok", "version": __version__, "database": db_state, "mode": mode,
            "time": datetime.now(timezone.utc).isoformat()}


@router.get("/samples")
def get_samples():
    b = samples.load_benchmark()
    return {"dataset": b.get("dataset"), "note": b.get("note"),
            "items": [{k: i[k] for k in ("id", "pair_id", "language", "title", "source", "reference_summary")} for i in b["items"]],
            "assignment_examples": b.get("assignment_examples", [])}
