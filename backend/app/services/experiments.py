from __future__ import annotations

import time
from collections import defaultdict

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models import Experiment, Run
from app.repositories import misc, runs as runs_repo
from app.schemas import ExperimentCreate
from app.services import engine, metrics, samples
from app.services.providers import ProviderError
from app.services.settings_service import Effective


def experiment_out(exp: Experiment, with_runs: Session | None = None) -> dict:
    d = {"id": exp.id, "created_at": exp.created_at.isoformat() + "Z", "name": exp.name,
         "description": exp.description, "status": exp.status, "error": exp.error, "mode": exp.mode,
         "model": exp.model, "language": exp.language, "strategies": exp.strategies, "length": exp.length,
         "config": exp.config, "results": exp.results, "duration_ms": exp.duration_ms}
    if with_runs is not None:
        rows, _ = runs_repo.list_runs(with_runs, limit=500, experiment_id=exp.id)
        d["runs"] = [engine.run_out(r, full=False) | {"source_text_chars": len(r.source_text)} for r in reversed(rows)]
    return d


def run_experiment(db: Session, settings: Settings, eff: Effective, req: ExperimentCreate) -> Experiment:
    if req.dataset == "sample":
        docs = [{"title": i["title"], "text": i["source"], "language": i["language"],
                 "reference_summary": i["reference_summary"]} for i in samples.items(req.language)]
    else:
        docs = [d.model_dump() for d in req.documents]
        if req.language != "all":
            for d in docs:
                if d["language"] == "auto":
                    d["language"] = req.language
    if not docs:
        raise AppError("No documents to run. Add documents, or pick a language that has sample documents.", 422)
    exp = misc.add_experiment(db, Experiment(
        name=req.name, description=req.description, mode=eff.mode,
        model=eff.model if eff.mode == "real" else "rule-based extractive", language=req.language,
        strategies=list(req.strategies), length=req.length,
        config={"dataset": req.dataset, "n_documents": len(docs), "verify": req.verify,
                "model_requested": req.model, "chunk_chars": settings.chunk_chars},
        status="running"))
    t0 = time.perf_counter()
    try:
        client = engine.get_client(settings, eff)
        for d in docs:
            for st in req.strategies:
                run = engine.make_run(db, settings, eff, text=d["text"], title=d.get("title"),
                                      language=d.get("language", "auto"), output_language="same",
                                      length=req.length, strategy=st, reference_summary=d.get("reference_summary"),
                                      saved=False, experiment_id=exp.id, client=client)
                if req.verify:
                    v = engine.verify_text(settings, eff, d["text"], run.summary, "auto", client=client)
                    engine.attach_verification(db, run, v)
        exp.status = "completed"
    except (ProviderError, AppError) as e:
        exp.status = "failed"
        exp.error = e.message
    finally:
        exp.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        runs = runs_repo.all_runs(db, experiment_id=exp.id)
        by: dict[str, list[Run]] = defaultdict(list)
        for r in runs:
            by[r.strategy].append(r)
        exp.results = {"by_strategy": {k: metrics.aggregate_runs(v) for k, v in by.items()},
                       "overall": metrics.aggregate_runs(runs), "n_runs": len(runs),
                       "planned_runs": len(docs) * len(req.strategies)}
        db.commit()
        db.refresh(exp)
    return exp
