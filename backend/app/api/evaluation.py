from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.common import csv_response, json_response
from app.core import db as dbm
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.repositories import misc
from app.schemas import EvaluationRunRequest
from app.services import evaluation as ev
from app.services import settings_service

router = APIRouter(prefix="/api/evaluation")


@router.get("/metrics")
def get_metrics(language: str | None = None, strategy: str | None = None, experiment_id: int | None = None,
                scope: str = Query("all", pattern="^(all|workspace|experiments|evaluation)$"),
                mode: str | None = Query(None, pattern="^(demo|real)$"), db: Session = Depends(dbm.get_session)):
    return ev.metrics_overview(db, language or None, strategy or None, experiment_id, scope, mode)


@router.post("/run")
def run(req: EvaluationRunRequest, db: Session = Depends(dbm.get_session), settings: Settings = Depends(get_settings)):
    eff = settings_service.resolve(db, settings)
    row = ev.run_evaluation(db, settings, eff, list(req.strategies), req.length, req.language, req.verify_method)
    return ev._eval_out(row)


@router.get("/runs")
def list_runs(db: Session = Depends(dbm.get_session)):
    return {"items": [ev._eval_out(e) for e in misc.list_evals(db)]}


@router.get("/export")
def export(kind: str = Query("runs", pattern="^(runs|benchmark)$"), format: str = Query("csv", pattern="^(csv|json)$"),
           language: str | None = None, strategy: str | None = None,
           scope: str = Query("all", pattern="^(all|workspace|experiments|evaluation)$"),
           mode: str | None = Query(None, pattern="^(demo|real)$"), db: Session = Depends(dbm.get_session)):
    if kind == "runs":
        rows = ev.export_rows(db, language=language or None, strategy=strategy or None, scope=scope, mode=mode)
        return csv_response(rows, "FactAlign_runs.csv") if format == "csv" else json_response(rows, "FactAlign_runs.json")
    latest = misc.latest_eval(db)
    if not latest:
        raise AppError("No benchmark evaluation has been run yet.", 404)
    if format == "json":
        return json_response(ev._eval_out(latest), f"FactAlign_benchmark_{latest.id}.json")
    return csv_response(latest.results["items"], f"FactAlign_benchmark_{latest.id}.csv")
