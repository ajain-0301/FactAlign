"""Orchestration: summarize -> analyse -> persist; verify; (de)serialise runs."""
from __future__ import annotations

import time
import uuid

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models import Run
from app.repositories import runs as runs_repo
from app.services import language as lang
from app.services import metrics, verification
from app.services.providers import LLMClient, build_llm
from app.services.settings_service import Effective
from app.services.summarizer import run_summary
from app.services.text import analyze, word_count


def new_compare_id() -> str:
    return uuid.uuid4().hex[:16]


def get_client(settings: Settings, eff: Effective) -> LLMClient | None:
    return build_llm(settings, eff.model) if eff.mode == "real" else None


def make_run(db: Session, settings: Settings, eff: Effective, *, text: str, title: str | None,
             language: str, output_language: str, length: str, strategy: str,
             reference_summary: str | None = None, saved: bool = True, compare_id: str | None = None,
             experiment_id: int | None = None, evaluation_run_id: int | None = None,
             client: LLMClient | None = None, source_pages: list[dict] | None = None) -> Run:
    if len(text) > settings.max_input_chars:
        raise AppError(f"Document is too long ({len(text):,} characters). The limit is {settings.max_input_chars:,}.", 413)
    detected = lang.detect_language(text)
    used = detected if language == "auto" else language
    if eff.mode == "real" and client is None:
        client = get_client(settings, eff)
    res = run_summary(mode=eff.mode, client=client, text=text, strategy=strategy, length=length,
                      output_language=output_language, detected_language=used,
                      chunk_chars=settings.chunk_chars, model=eff.model)
    sw, mw = word_count(text), word_count(res.summary)
    res.extra["auto_detected_language"] = detected
    if source_pages:
        res.extra["source_pages"] = source_pages
    run = Run(
        title=(title or None), source_text=text, reference_summary=reference_summary or None,
        language_requested=language, language_detected=used, output_language=output_language,
        length=length, strategy=strategy, mode=res.mode, provider=res.provider, model=res.model,
        summary=res.summary, inference_ms=res.inference_ms, source_words=sw, summary_words=mw,
        compression_ratio=metrics.compression_ratio(sw, mw), cmi=lang.cmi(text),
        compare_id=compare_id, experiment_id=experiment_id, evaluation_run_id=evaluation_run_id,
        saved=saved, analysis=analyze(text), extra=res.extra,
    )
    return runs_repo.add(db, run)


def resolve_verifier(method: str, eff: Effective) -> str:
    m = method if method != "auto" else eff.prefs.get("verifier", "auto")
    if m == "auto":
        m = "hybrid" if eff.mode == "real" else "rule"
    return m


def verify_text(settings: Settings, eff: Effective, source: str, summary: str, method: str = "auto",
                claims: list[str] | None = None, client: LLMClient | None = None, source_pages: list[dict] | None = None) -> dict:
    m = resolve_verifier(method, eff)
    if m == "claim_nli":
        from app.services.claim_verification import verify as verify_atomic
        from app.services.nli_models import get_models
        models = get_models(settings.embedding_model, settings.nli_model, settings.verification_local_only)
        client = client or build_llm(settings, eff.model)
        t0 = time.perf_counter()
        out = verify_atomic(source, summary, client, models, settings, source_pages, claims)
        out.update(verify_ms=round((time.perf_counter() - t0) * 1000, 2), mode="real", model=client.model)
        return out
    if m in ("llm", "hybrid") and client is None:
        client = build_llm(settings, eff.model)
    t0 = time.perf_counter()
    if claims is not None:
        out = verification.verify_claims(source, claims, m, client)
    else:
        out = verification.verify(source, summary, m, client)
    out["verify_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    out["mode"] = "real" if m in ("llm", "hybrid") else "demo"
    out["model"] = client.model if client and m != "rule" else None
    return out


def attach_verification(db: Session, run: Run, verif: dict) -> Run:
    run.verification = verif
    db.commit()
    db.refresh(run)
    return run


def run_out(run: Run, full: bool = True) -> dict:
    d = {
        "id": run.id, "created_at": run.created_at.isoformat() + "Z", "title": run.title,
        "language_requested": run.language_requested, "language_detected": run.language_detected,
        "output_language": run.output_language, "length": run.length, "strategy": run.strategy,
        "mode": run.mode, "provider": run.provider, "model": run.model, "summary": run.summary,
        "inference_ms": run.inference_ms, "source_words": run.source_words,
        "summary_words": run.summary_words, "compression_ratio": run.compression_ratio,
        "compression_factor": round(run.source_words / run.summary_words, 2) if run.summary_words else None,
        "cmi": run.cmi, "compare_id": run.compare_id, "experiment_id": run.experiment_id,
        "evaluation_run_id": run.evaluation_run_id, "saved": run.saved,
        "verification_metrics": (run.verification or {}).get("metrics"),
        "verification_method": (run.verification or {}).get("method"),
    }
    if not full:
        d["source_preview"] = run.source_text[:180]
        return d
    sa = analyze(run.summary)
    d.update({
        "source_text": run.source_text, "reference_summary": run.reference_summary,
        "analysis": run.analysis, "summary_facts": {k: sa[k] for k in ("entities", "dates", "numbers")},
        "verification": run.verification, "extra": run.extra,
        "metrics": run_metrics(run),
    })
    return d


def run_metrics(run: Run) -> dict:
    m: dict = {
        "fact": metrics.fact_metrics(run.summary, run.source_text, run.reference_summary),
        "lexical_similarity_to_source": metrics.lexical_cosine(run.source_text, run.summary),
    }
    if run.reference_summary:
        m["rouge"] = metrics.rouge(run.summary, run.reference_summary)
    return m
