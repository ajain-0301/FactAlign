"""Summarization engines: a deterministic extractive DEMO engine and an LLM engine.

Both expose ``summarize(...) -> SummaryResult``. The demo engine is NOT an AI
model: it ranks and copies source sentences, and every result is labelled so.
"""
from __future__ import annotations

import math
import time
from collections import Counter
from dataclasses import dataclass, field

from app.services import prompts
from app.services.providers import LLMClient, ProviderError
from app.services.text import extract_dates, fact_density, split_sentences, tokens, word_count


@dataclass
class SummaryResult:
    summary: str
    inference_ms: float
    mode: str  # demo | real
    provider: str
    model: str
    extra: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- demo (extractive)
_TARGETS = {"short": (1, 2, 0.15), "medium": (2, 4, 0.30), "long": (3, 7, 0.50)}


def _n_select(n_sent: int, length: str) -> int:
    lo, hi, frac = _TARGETS[length]
    return max(1, min(n_sent, max(lo, min(hi, round(frac * n_sent)))))


def demo_summarize(text: str, strategy: str, length: str) -> tuple[str, dict]:
    sents = split_sentences(text)
    if not sents:
        return "", {}
    k = _n_select(len(sents), length)
    toks = [tokens(s, drop_stop=True) for s in sents]
    tf = Counter(t for ts in toks for t in ts)
    df = Counter(t for ts in toks for t in set(ts))
    n = len(sents)
    base = []
    for i, ts in enumerate(toks):
        if not ts:
            base.append(0.0)
            continue
        centrality = sum(tf[t] * (1 + math.log(1 + n / df[t])) for t in ts) / (len(ts) ** 0.5)
        lead = 1.5 if i == 0 else (1.15 if i < 3 else 1.0)
        base.append(centrality * lead)
    mx = max(base) or 1.0
    base = [b / mx for b in base]
    facts = [fact_density(s) for s in sents]
    fmx = max(facts) or 1.0
    facts = [f / fmx for f in facts]

    chosen: list[int] = []
    covered: set[str] = set()
    for _ in range(k):
        best, best_score = None, -1.0
        for i in range(n):
            if i in chosen:
                continue
            score = base[i]
            if strategy == "factuality":
                # prioritise sentences dense in dates/numbers/entities, and penalise redundancy (MMR-like)
                score = 0.55 * base[i] + 0.45 * facts[i]
                if toks[i]:
                    overlap = len(covered & set(toks[i])) / len(set(toks[i]))
                    score -= 0.25 * overlap
            if score > best_score:
                best, best_score = i, score
        chosen.append(best)  # type: ignore[arg-type]
        covered |= set(toks[best])  # type: ignore[index]
    chosen.sort()
    summary = " ".join(sents[i] for i in chosen)
    note = (
        "Extractive demo engine: copies the highest-scoring source sentences. "
        + ("Factuality-aware variant additionally prioritises sentences with dates, numbers and entities and "
           "reduces redundancy." if strategy == "factuality" else "Standard variant ranks by centrality and lead position.")
    )
    return summary, {"selected_sentences": [i + 1 for i in chosen], "engine_note": note}


# --------------------------------------------------------------------------- chunking
def chunk_text(text: str, max_chars: int) -> list[str]:
    sents = split_sentences(text) or [text]
    chunks: list[str] = []
    cur = ""
    for s in sents:
        while len(s) > max_chars:  # hard split a pathological sentence, never drop content
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(s[:max_chars])
            s = s[max_chars:]
        if cur and len(cur) + len(s) + 1 > max_chars:
            chunks.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return chunks


# --------------------------------------------------------------------------- LLM
def llm_summarize(client: LLMClient, text: str, strategy: str, length: str, output_language: str,
                  chunk_chars: int) -> tuple[str, dict]:
    extra: dict = {"chunks": 1}
    if len(text) <= chunk_chars:
        system = prompts.build_summary_system(strategy, length, output_language)
        return client.complete(system, text, max_tokens=900).strip(), extra
    chunks = chunk_text(text, chunk_chars)
    extra["chunks"] = len(chunks)
    partial_system = prompts.build_summary_system(strategy, "medium", output_language, prompts.CHUNK_NOTE)
    partials = [client.complete(partial_system, c, max_tokens=700).strip() for c in chunks]
    merge_system = prompts.build_summary_system(strategy, length, output_language, prompts.MERGE_NOTE)
    merged = "\n\n".join(f"[Part {i + 1}] {p}" for i, p in enumerate(partials))
    return client.complete(merge_system, merged, max_tokens=900).strip(), extra


def run_summary(*, mode: str, client: LLMClient | None, text: str, strategy: str, length: str,
                output_language: str, detected_language: str, chunk_chars: int, model: str) -> SummaryResult:
    t0 = time.perf_counter()
    if mode == "demo":
        summary, extra = demo_summarize(text, strategy, length)
        warnings = []
        if output_language not in ("same", detected_language):
            warnings.append("Demo mode cannot translate; the summary stays in the source language.")
        extra["warnings"] = warnings
        ms = (time.perf_counter() - t0) * 1000
        return SummaryResult(summary, round(ms, 2), "demo", "demo-extractive", "rule-based extractive", extra)
    assert client is not None
    summary, extra = llm_summarize(client, text, strategy, length, output_language, chunk_chars)
    if not summary:
        raise ProviderError("The model returned an empty summary.", 502)
    ms = (time.perf_counter() - t0) * 1000
    return SummaryResult(summary, round(ms, 2), "real", client.name, client.model, extra)
