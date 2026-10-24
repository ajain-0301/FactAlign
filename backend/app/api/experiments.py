from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import db as dbm
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.repositories import misc
from app.schemas import ExperimentCreate
from app.services import settings_service
from app.services.experiments import experiment_out, run_experiment

router = APIRouter(prefix="/api/experiments")


@router.post("")
def create(req: ExperimentCreate, db: Session = Depends(dbm.get_session), settings: Settings = Depends(get_settings)):
    eff = settings_service.resolve(db, settings, model_override=req.model)
    exp = run_experiment(db, settings, eff, req)
    return experiment_out(exp, db)


@router.get("")
def list_experiments(q: str | None = None, language: str | None = None, strategy: str | None = None,
                     status: str | None = None, db: Session = Depends(dbm.get_session)):
    rows = misc.list_experiments(db, q, language, strategy, status)
    return {"total": len(rows), "items": [experiment_out(e) for e in rows]}


@router.get("/{exp_id}")
def get_experiment(exp_id: int, db: Session = Depends(dbm.get_session)):
    exp = misc.get_experiment(db, exp_id)
    if not exp:
        raise AppError(f"Experiment {exp_id} not found.", 404)
    return experiment_out(exp, db)


@router.delete("/{exp_id}")
def delete_experiment(exp_id: int, db: Session = Depends(dbm.get_session)):
    if not misc.delete_experiment(db, exp_id):
        raise AppError(f"Experiment {exp_id} not found.", 404)
    return {"deleted": exp_id}
