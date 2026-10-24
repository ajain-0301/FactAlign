"""Metric implementations with documented formulas (see README -> Metrics)."""
from __future__ import annotations

import math
from collections import Counter
from statistics import mean, median

from app.services.text import (
    entity_keys, extract_dates, extract_entities, extract_numbers, fold, tokens, word_count,
)


def compression_ratio(source_words: int, summary_words: int) -> float:
    """CR = summary_words / source_words  (fraction of the source that is kept; lower = more compression)."""
    return round(summary_words / source_words, 4) if source_words else 0.0


def _ngrams(toks: list[str], n: int) -> Counter:
    return Counter(tuple(toks[i:i + n]) for i in range(len(toks) - n + 1))


def _prf(overlap: float, pred: float, ref: float) -> dict:
    p = overlap / pred if pred else 0.0
    r = overlap / ref if ref else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4)}


def _lcs(a: list[str], b: list[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


def rouge(candidate: str, reference: str) -> dict:
    """ROUGE-1/2/L on folded, lower-cased unicode tokens (no stemming). Needs a human reference summary."""
    c, r = tokens(candidate), tokens(reference)
    out = {}
    for n in (1, 2):
        cn, rn = _ngrams(c, n), _ngrams(r, n)
        ov = sum((cn & rn).values())
        out[f"rouge{n}"] = _prf(ov, sum(cn.values()), sum(rn.values()))
    out["rougeL"] = _prf(_lcs(c, r), len(c), len(r))
    return out


def prf_from_counts(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p is not None and r is not None and p + r else (0.0 if p is not None and r is not None else None)
    rd = lambda x: None if x is None else round(x, 4)  # noqa: E731
    return {"precision": rd(p), "recall": rd(r), "f1": rd(f), "tp": tp, "fp": fp, "fn": fn}


def _facts(text: str) -> dict:
    dates, masked = extract_dates(text)
    nums = extract_numbers(masked)
    return {
        "num": {n["value"] for n in nums},
        "date": {d["key"] for d in dates},
        "ent": entity_keys(extract_entities(text)),
        "folded": fold(text).lower(),
    }


def fact_metrics(summary: str, source: str, reference: str | None = None) -> dict:
    """Automatic fact-preservation PROXIES (not human ground truth).

    fact_precision   = |facts(summary) found in source| / |facts(summary)|
    source_coverage  = |facts(summary) found in source| / |facts(source)|
    fact_recall_ref  = |facts(reference) found in summary| / |facts(reference)|   (needs a reference summary)
    where facts = numbers, dates and named entities extracted automatically.
    """
    s, src = _facts(summary), _facts(source)
    s_items = [("num", x) for x in s["num"]] + [("date", x) for x in s["date"]] + [("ent", x) for x in s["ent"]]

    def in_src(kind: str, x: str) -> bool:
        return (x in src[kind]) if kind != "ent" else (x in src["folded"])

    supported = [it for it in s_items if in_src(*it)]
    unsupported = [it[1] for it in s_items if not in_src(*it)]
    src_total = len(src["num"]) + len(src["date"]) + len(src["ent"])
    out = {
        "n_summary_facts": len(s_items),
        "n_source_facts": src_total,
        "fact_precision": round(len(supported) / len(s_items), 4) if s_items else None,
        "source_coverage": round(len(supported) / src_total, 4) if src_total else None,
        "unsupported_facts": unsupported,
        "fact_recall_ref": None,
    }
    if reference:
        r = _facts(reference)
        r_items = [("num", x) for x in r["num"]] + [("date", x) for x in r["date"]] + [("ent", x) for x in r["ent"]]
        if r_items:
            def in_sum(kind: str, x: str) -> bool:
                return (x in s[kind]) if kind != "ent" else (x in s["folded"])
            out["fact_recall_ref"] = round(sum(1 for it in r_items if in_sum(*it)) / len(r_items), 4)
    return out


def lexical_cosine(a: str, b: str) -> float:
    """Cosine similarity between term-frequency vectors of content tokens (lexical, NOT semantic)."""
    ca, cb = Counter(tokens(a, True)), Counter(tokens(b, True))
    num = sum(ca[t] * cb[t] for t in ca)
    den = math.sqrt(sum(v * v for v in ca.values())) * math.sqrt(sum(v * v for v in cb.values()))
    return round(num / den, 4) if den else 0.0


def avg(xs: list[float | None]) -> float | None:
    v = [x for x in xs if x is not None]
    return round(mean(v), 4) if v else None


def med(xs: list[float]) -> float | None:
    return round(median(xs), 4) if xs else None


# ---------------------------------------------------------------- aggregation over stored runs
def aggregate_runs(runs: list) -> dict:
    """Aggregate Run rows. Only uses data that exists (reference/verification are optional)."""
    n = len(runs)
    if not n:
        return {"n_runs": 0}
    claims = sum((r.verification or {}).get("metrics", {}).get("n_claims", 0) for r in runs)
    supported = sum((r.verification or {}).get("metrics", {}).get("supported", 0) for r in runs)
    contra = sum((r.verification or {}).get("metrics", {}).get("contradicted", 0) for r in runs)
    verified_runs = sum(1 for r in runs if r.verification)
    rouge_vals = [rouge(r.summary, r.reference_summary) for r in runs if r.reference_summary]
    return {
        "n_runs": n,
        "avg_source_words": avg([r.source_words for r in runs]),
        "avg_summary_words": avg([r.summary_words for r in runs]),
        "avg_compression_ratio": avg([r.compression_ratio for r in runs]),
        "avg_inference_ms": avg([r.inference_ms for r in runs]),
        "median_inference_ms": med([r.inference_ms for r in runs]),
        "avg_cmi": avg([r.cmi for r in runs]),
        "n_verified_runs": verified_runs,
        "n_claims": claims,
        "claim_support_rate": round(supported / claims, 4) if claims else None,
        "claim_contradiction_rate": round(contra / claims, 4) if claims else None,
        "n_with_reference": len(rouge_vals),
        "rouge1_f1": avg([x["rouge1"]["f1"] for x in rouge_vals]),
        "rouge2_f1": avg([x["rouge2"]["f1"] for x in rouge_vals]),
        "rougeL_f1": avg([x["rougeL"]["f1"] for x in rouge_vals]),
    }


FORMULAS = {
    "compression_ratio": "CR = summary_words / source_words (share of the source kept; lower = shorter). Compression factor = 1 / CR.",
    "avg_summary_length": "Mean number of word tokens in generated summaries.",
    "inference_time": "Wall-clock milliseconds for the summarization call (includes network time in real mode; excludes verification).",
    "claim_support_rate": "supported_claims / total_claims, over summaries that were verified. An automatic estimate, not ground truth.",
    "precision_recall_f1": "P = TP/(TP+FP), R = TP/(TP+FN), F1 = 2PR/(P+R). Only reported when labelled data exists (labelled claims for the verifier; reference summaries for fact recall).",
    "rouge": "ROUGE-1/2/L F1 against a human reference summary, on unicode word tokens without stemming.",
    "fact_precision": "Automatic proxy: share of numbers/dates/entities in the summary that also occur in the source.",
    "cmi": "Code-Mixing Index = 100 * (1 - max(n_hi, n_en) / (n_hi + n_en)); 0 = monolingual.",
    "lexical_similarity": "Cosine similarity of term-frequency vectors (lexical overlap, NOT embedding-based semantic similarity).",
}
