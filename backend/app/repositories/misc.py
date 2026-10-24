from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppSetting, EvaluationRun, Experiment


# ---- app settings (preferences)
def get_setting(db: Session, key: str) -> dict:
    row = db.get(AppSetting, key)
    return dict(row.value) if row else {}


def put_setting(db: Session, key: str, value: dict) -> dict:
    row = db.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    db.commit()
    return value


# ---- experiments
def add_experiment(db: Session, exp: Experiment) -> Experiment:
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def save_experiment(db: Session, exp: Experiment) -> Experiment:
    db.commit()
    db.refresh(exp)
    return exp


def get_experiment(db: Session, exp_id: int) -> Experiment | None:
    return db.get(Experiment, exp_id)


def delete_experiment(db: Session, exp_id: int) -> bool:
    from app.models import Run

    exp = db.get(Experiment, exp_id)
    if not exp:
        return False
    for r in db.scalars(select(Run).where(Run.experiment_id == exp_id)).all():
        db.delete(r)
    db.delete(exp)
    db.commit()
    return True


def list_experiments(db: Session, q: str | None = None, language: str | None = None,
                     strategy: str | None = None, status: str | None = None) -> list[Experiment]:
    rows = db.scalars(select(Experiment).order_by(Experiment.created_at.desc(), Experiment.id.desc())).all()
    out = []
    for e in rows:
        if q and q.lower() not in f"{e.name} {e.description or ''}".lower():
            continue
        if language and e.language != language:
            continue
        if strategy and strategy not in (e.strategies or []):
            continue
        if status and e.status != status:
            continue
        out.append(e)
    return out


# ---- evaluation runs
def add_eval(db: Session, ev: EvaluationRun) -> EvaluationRun:
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def latest_eval(db: Session) -> EvaluationRun | None:
    return db.scalars(select(EvaluationRun).order_by(EvaluationRun.created_at.desc(), EvaluationRun.id.desc()).limit(1)).first()


def list_evals(db: Session, limit: int = 20) -> list[EvaluationRun]:
    return list(db.scalars(select(EvaluationRun).order_by(EvaluationRun.created_at.desc(), EvaluationRun.id.desc()).limit(limit)).all())
