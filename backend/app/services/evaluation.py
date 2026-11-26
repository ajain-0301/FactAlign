"""Evaluation: aggregate stored runs, run the labelled benchmark, export.

Honesty rules implemented here
* ROUGE only uses runs that have a reference summary.
* Precision / recall / F1 are computed only from labelled data (labelled claims
  for the verifier). Nothing is estimated when no labels exist.
* Every result carries the mode (demo vs real) so demo numbers are never
  mistaken for LLM numbers.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import EvaluationRun, Run
from app.repositories import misc, runs as runs_repo
from app.services import engine, metrics, samples
from app.services.settings_service import Effective

LABELS = ["supported", "contradicted", "unverifiable"]


def _scope(runs: list[Run], scope: str, mode: str | None) -> list[Run]:
    if scope == "workspace":
        runs = [r for r in runs if r.experiment_id is None and r.evaluation_run_id is None]
    elif scope == "experiments":
        runs = [r for r in runs if r.experiment_id is not None]
    elif scope == "evaluation":
        runs = [r for r in runs if r.evaluation_run_id is not None]
    if mode:
        runs = [r for r in runs if r.mode == mode]
    return runs


def metrics_overview(db: Session, language: str | None = None, strategy: str | None = None,
                     experiment_id: int | None = None, scope: str = "all", mode: str | None = None) -> dict:
    runs = _scope(runs_repo.all_runs(db, language=language, strategy=strategy, experiment_id=experiment_id), scope, mode)
    runs = [r for r in runs if r.language_detected != "english"] 
    everything = runs_repo.all_runs(db)
    groups_s: dict[str, list[Run]] = defaultdict(list)
    groups_l: dict[str, list[Run]] = defaultdict(list)
    groups_sl: dict[tuple, list[Run]] = defaultdict(list)
    for r in runs:
        groups_s[r.strategy].append(r)
        groups_l[r.language_detected].append(r)
        groups_sl[(r.strategy, r.language_detected)].append(r)
    series = []
    for r in runs[-200:]:
        vm = (r.verification or {}).get("metrics") or {}
        rg = metrics.rouge(r.summary, r.reference_summary)["rougeL"] if r.reference_summary else None
        series.append({"run_id": r.id, "created_at": r.created_at.isoformat() + "Z", "strategy": r.strategy,
                       "language": r.language_detected, "mode": r.mode, "summary_words": r.summary_words,
                       "compression_ratio": r.compression_ratio, "inference_ms": r.inference_ms,
                       "claim_support_rate": vm.get("support_rate"), "rougeL_f1": rg["f1"] if rg else None,"rougeL_precision": rg["precision"] if rg else None, "rougeL_recall": rg["recall"] if rg else None, "cmi": r.cmi})
    ev = misc.latest_eval(db)
    evaluations = db.scalars(select(EvaluationRun)).all()
    rule_counts = []
    for evaluation in evaluations:
        verifier = (evaluation.results or {}).get("verifier") or {}
        unsupported = (verifier.get("overall") or {}).get("unsupported_detection")
        if verifier.get("method") == "rule" and unsupported and all(
            isinstance(unsupported.get(key), int) for key in ("tp", "fp", "fn")
        ):
            rule_counts.append(unsupported)
    if rule_counts:
        aggregated = metrics.prf_from_counts(
            sum(result["tp"] for result in rule_counts),
            sum(result["fp"] for result in rule_counts),
            sum(result["fn"] for result in rule_counts),
        )
        rule_verifier_metrics = {
            key: aggregated[key] for key in ("precision", "recall")
        }
    else:
        rule_verifier_metrics = None

    lang_counts = Counter(r.language_detected for r in runs)
    total = sum(lang_counts.values())  
    return {
        "totals": metrics.aggregate_runs(runs),
        "counts": {
            "all": len(everything),
            "workspace": sum(1 for r in everything if r.experiment_id is None and r.evaluation_run_id is None),
            "experiments": sum(1 for r in everything if r.experiment_id is not None),
            "evaluation": sum(1 for r in everything if r.evaluation_run_id is not None),
            "demo": sum(1 for r in everything if r.mode == "demo"),
            "real": sum(1 for r in everything if r.mode == "real"),
        },
        "by_strategy": {k: metrics.aggregate_runs(v) for k, v in groups_s.items()},
        "by_language": {k: metrics.aggregate_runs(v) for k, v in groups_l.items()},
        "by_strategy_language": [{"strategy": s, "language": l, **metrics.aggregate_runs(v)} for (s, l), v in groups_sl.items()],
        "language_distribution": {k: round(v / total * 100, 1) for k, v in lang_counts.items()} if total else {},
        "series": series,
        "latest_evaluation": _eval_out(ev) if ev else None,
        "rule_verifier_metrics": rule_verifier_metrics,
        "formulas": metrics.FORMULAS,
        "notes": [
            "Claim-support rate is an automatic estimate from the verifier, not human ground truth.",
            "ROUGE is computed only for runs that have a reference summary.",
            "Precision/recall/F1 appear only in the labelled-benchmark evaluation (see 'Run evaluation').",
            "Demo-mode runs use a rule-based extractive engine; do not read them as LLM performance.",
        ],
    }


def _eval_out(ev: EvaluationRun) -> dict:
    return {"id": ev.id, "created_at": ev.created_at.isoformat() + "Z", "mode": ev.mode, "model": ev.model,
            "dataset": ev.dataset, "config": ev.config, "results": ev.results}


def _prf_class(conf: dict, label: str) -> dict:
    tp = conf[label][label]
    fp = sum(conf[o][label] for o in conf if o != label)
    fn = sum(conf[label][o] for o in conf if o != label)
    return metrics.prf_from_counts(tp, fp, fn)


def _verifier_eval(rows: list[tuple[str, str]]) -> dict:
    """rows: (gold, predicted). Needs gold labels - computed only from labelled claims."""
    labels = list(dict.fromkeys([*LABELS, *(label for row in rows for label in row)]))
    conf = {g: {p: 0 for p in labels} for g in labels}
    for g, p in rows:
        conf[g][p] += 1
    n = len(rows)
    per = {l: _prf_class(conf, l) for l in labels}
    f1s = [per[l]["f1"] for l in labels if per[l]["f1"] is not None]
    # binary: positive class = "unsupported" (contradicted or unverifiable)
    tp = sum(1 for g, p in rows if g != "supported" and p != "supported")
    fp = sum(1 for g, p in rows if g == "supported" and p != "supported")
    fn = sum(1 for g, p in rows if g != "supported" and p == "supported")
    return {
        "n_labeled_claims": n, "confusion": conf, "per_class": per,
        "accuracy": round(sum(conf[l][l] for l in labels) / n, 4) if n else None,
        "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else None,
        "unsupported_detection": metrics.prf_from_counts(tp, fp, fn),
    }


def run_evaluation(db: Session, settings: Settings, eff: Effective, strategies: list[str], length: str,
                   language: str, verify_method: str) -> EvaluationRun:
    its = samples.items(language)
    bench = samples.load_benchmark()
    client = engine.get_client(settings, eff)
    vmethod = engine.resolve_verifier(verify_method, eff)
    ev = misc.add_eval(db, EvaluationRun(mode=eff.mode, model=eff.model if eff.mode == "real" else "rule-based extractive",
                                         dataset=bench.get("dataset", "?"),
                                         config={"strategies": strategies, "length": length, "language": language,
                                                 "verify_method": vmethod, "n_documents": len(its)}))
    rows = []
    for it in its:
        for st in strategies:
            run = engine.make_run(db, settings, eff, text=it["source"], title=it["title"], language=it["language"],
                                  output_language="same", length=length, strategy=st,
                                  reference_summary=it["reference_summary"], saved=False,
                                  evaluation_run_id=ev.id, client=client)
            verif = engine.verify_text(settings, eff, it["source"], run.summary, vmethod, client=client)
            engine.attach_verification(db, run, verif)
            rm = engine.run_metrics(run)
            rows.append({
                "item_id": it["id"], "pair_id": it["pair_id"], "language": it["language"], "strategy": st,
                "run_id": run.id, "summary_words": run.summary_words, "compression_ratio": run.compression_ratio,
                "inference_ms": run.inference_ms, "cmi": run.cmi,
                "rouge1_f1": rm["rouge"]["rouge1"]["f1"], "rouge2_f1": rm["rouge"]["rouge2"]["f1"],
                "rougeL_f1": rm["rouge"]["rougeL"]["f1"],
                "fact_precision": rm["fact"]["fact_precision"], "fact_recall_ref": rm["fact"]["fact_recall_ref"],
                "claim_support_rate": verif["metrics"]["support_rate"], "n_claims": verif["metrics"]["n_claims"],
            })
    # verifier accuracy on labelled claims
    gold_pred: list[tuple[str, str]] = []
    by_lang: dict[str, list[tuple[str, str]]] = defaultdict(list)
    labeled_items = samples.labeled_items()
    for it in labeled_items:
        claims = [c["claim"] for c in it["labeled_claims"]]
        v = engine.verify_text(settings, eff, it["source"], "", vmethod, claims=claims, client=client)
        for c, r in zip(it["labeled_claims"], v["claims"]):
            gold_pred.append((c["label"], r["status"]))
            by_lang[it["language"]].append((c["label"], r["status"]))
    n_labeled_claims = len(gold_pred)

    def _avg(xs): return metrics.avg(xs)

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["strategy"], r["language"])].append(r)
    by_sl = [{"strategy": s, "language": l, "n": len(v),
              "avg_summary_words": _avg([x["summary_words"] for x in v]),
              "avg_compression_ratio": _avg([x["compression_ratio"] for x in v]),
              "avg_inference_ms": _avg([x["inference_ms"] for x in v]),
              "rouge1_f1": _avg([x["rouge1_f1"] for x in v]), "rouge2_f1": _avg([x["rouge2_f1"] for x in v]),
              "rougeL_f1": _avg([x["rougeL_f1"] for x in v]),
              "fact_precision": _avg([x["fact_precision"] for x in v]),
              "fact_recall_ref": _avg([x["fact_recall_ref"] for x in v]),
              "claim_support_rate": _avg([x["claim_support_rate"] for x in v]),
              "avg_cmi": _avg([x["cmi"] for x in v])} for (s, l), v in groups.items()]

    gap = []
    keys = ["rougeL_f1", "claim_support_rate", "fact_precision", "compression_ratio", "summary_words"]
    for st in strategies:
        pairs = []
        for pid in sorted({r["pair_id"] for r in rows}):
            a = next((r for r in rows if r["pair_id"] == pid and r["strategy"] == st and r["language"] == "hi"), None)
            b = next((r for r in rows if r["pair_id"] == pid and r["strategy"] == st and r["language"] == "hinglish"), None)
            if a and b:
                pairs.append({"pair_id": pid, "hi": {k: a[k] for k in keys}, "hinglish": {k: b[k] for k in keys},
                              "delta": {k: (None if a[k] is None or b[k] is None else round(b[k] - a[k], 4)) for k in keys}})
        if pairs:
            gap.append({"strategy": st, "n_pairs": len(pairs), "pairs": pairs,
                        "mean_delta": {k: _avg([p["delta"][k] for p in pairs]) for k in keys}})

    ev.results = {
        "items": rows, "by_strategy_language": by_sl,
        "verifier": {"method": vmethod, "overall": _verifier_eval(gold_pred),
                     "by_language": {l: _verifier_eval(v) for l, v in by_lang.items()}},
        "code_mixing_gap": gap,
        "notes": [
            bench.get("note", ""),
            "Mean delta = Hinglish minus Hindi on parallel documents (same facts). Negative ROUGE/support deltas "
            "mean the code-mixed version scored lower.",
            ("Demo mode: summaries come from a rule-based EXTRACTIVE engine and verification is rule-based; these "
             "numbers describe those baselines, not an LLM." if eff.mode == "demo" else
             f"Real mode: summaries generated by {eff.model}; verification method = {vmethod}."),
            f"Verifier precision/recall/F1 use {n_labeled_claims} author-written claims from the separate synthetic "
            "demo set, not XL-Sum labels. These results are a regression check, NOT evidence of general accuracy. "
            "Use your own held-out, human-annotated claims for real conclusions.",
            "Demo-mode summaries are copied source sentences, so claim support of ~100% is expected and uninformative. "
            "The factuality comparison is only meaningful with real LLM summaries." if eff.mode == "demo" else
            "Claim support is an automatic estimate from the configured verifier.",
        ],
    }
    return _commit(db, ev)


def _commit(db: Session, ev: EvaluationRun) -> EvaluationRun:
    db.commit()
    db.refresh(ev)
    return ev


def export_rows(db: Session, **f) -> list[dict]:
    out = []
    for r in _scope(runs_repo.all_runs(db, language=f.get("language"), strategy=f.get("strategy"),
                                       experiment_id=f.get("experiment_id")), f.get("scope", "all"), f.get("mode")):
        vm = (r.verification or {}).get("metrics") or {}
        rg = metrics.rouge(r.summary, r.reference_summary) if r.reference_summary else None
        out.append({
            "run_id": r.id, "created_at": r.created_at.isoformat() + "Z", "mode": r.mode, "model": r.model,
            "strategy": r.strategy, "language": r.language_detected, "length": r.length,
            "source_words": r.source_words, "summary_words": r.summary_words,
            "compression_ratio": r.compression_ratio, "inference_ms": r.inference_ms, "cmi": r.cmi,
            "claims": vm.get("n_claims"), "claim_support_rate": vm.get("support_rate"),
            "rouge1_f1": rg["rouge1"]["f1"] if rg else None, "rouge2_f1": rg["rouge2"]["f1"] if rg else None,
            "rougeL_f1": rg["rougeL"]["f1"] if rg else None, "rougeL_precision": rg["rougeL"]["precision"] if rg else None, "rougeL_recall": rg["rougeL"]["recall"] if rg else None,
        })
    return out
