"""Factuality verification: summary claims vs. source evidence.

Pipeline
1. Split the summary into claims (sentence level).
2. Retrieve the most relevant source passage(s) for each claim (IDF-weighted
   token containment with light prefix stemming; also tries 2-sentence windows).
3. Judge each claim:
   * rule   - deterministic checks for changed numbers, dates, entity
              substitution, negation flips, plus an overlap threshold.
   * llm    - an LLM judges each claim against the source (needs API key).
   * hybrid - LLM verdict, then rule checks may DOWNGRADE "supported" when a
              number/date in the claim does not exist anywhere in the source.
4. Output Supported / Contradicted / Unverifiable with evidence + explanation.

``confidence`` is always ``None`` unless a calibrated model provides it; neither
the rules nor the LLM prompt produce a calibrated probability. The rule engine
exposes ``evidence_score`` (lexical overlap 0-1) which is NOT a probability.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter

from app.services.providers import LLMClient, ProviderError
from app.services.prompts import VERIFY_SYSTEM
from app.services.text import (
    dates_unmatched, entity_keys, extract_dates, extract_entities, extract_numbers, fold,
    has_negation, numbers_unmatched, split_sentences, tokens,
)

LIMITATIONS = (
    "Automatic verification is an estimate, not a guarantee of correctness. Rule-based checks rely on lexical "
    "overlap and can miss paraphrases, implicit reasoning, spelled-out numbers (e.g. 'five') and entities that "
    "are not capitalised Latin names or in the built-in Hindi gazetteer. LLM judgements can be wrong or "
    "inconsistent. Treat 'Supported' as 'no problem detected', and review 'Contradicted'/'Unverifiable' items manually."
)
SUPPORT_THRESHOLD = 0.65
RELEVANCE_THRESHOLD = 0.45
STATUSES = {"supported", "contradicted", "unverifiable"}


def split_claims(summary: str) -> list[str]:
    claims: list[str] = []
    for s in split_sentences(summary):
        for part in re.split(r"[;；]", s):
            part = part.strip(" -•\t")
            if len(tokens(part)) >= 2:
                claims.append(part)
    return claims


def _stem(t: str) -> str:
    return t[:5] if len(t) >= 6 else t


class Retriever:
    def __init__(self, source: str):
        self.sents = split_sentences(source) or [source]
        self.sent_tokens = [set(tokens(s, drop_stop=True)) for s in self.sents]
        self.sent_stems = [{_stem(t) for t in ts} for ts in self.sent_tokens]
        n = len(self.sents)
        df = Counter(t for ts in self.sent_tokens for t in ts)
        self.idf = {t: math.log(1 + n / c) for t, c in df.items()}
        self.max_idf = math.log(1 + n) + 1

    def _score(self, claim_toks: list[str], toks: set[str], stems: set[str]) -> float:
        if not claim_toks:
            return 0.0
        tot = hit = 0.0
        for t in claim_toks:
            w = self.idf.get(t, self.max_idf)
            tot += w
            if t in toks or _stem(t) in stems:
                hit += w
        return hit / tot if tot else 0.0

    def best(self, claim: str, top: int = 3) -> list[tuple[int, int, float]]:
        """Return up to ``top`` (start, end_exclusive, score) windows sorted by score."""
        ctoks = tokens(claim, drop_stop=True)
        results = []
        for i in range(len(self.sents)):
            results.append((i, i + 1, self._score(ctoks, self.sent_tokens[i], self.sent_stems[i])))
            if i + 1 < len(self.sents):
                toks = self.sent_tokens[i] | self.sent_tokens[i + 1]
                stems = self.sent_stems[i] | self.sent_stems[i + 1]
                # small penalty so a single sentence wins ties against a window
                results.append((i, i + 2, self._score(ctoks, toks, stems) - 0.02))
        results.sort(key=lambda r: r[2], reverse=True)
        out, seen = [], set()
        for r in results:
            if (r[0], r[1]) not in seen:
                out.append(r)
                seen.add((r[0], r[1]))
            if len(out) >= top:
                break
        return out

    def text(self, start: int, end: int) -> str:
        return " ".join(self.sents[start:end])


def _source_facts(source: str) -> dict:
    dates, masked = extract_dates(source)
    return {"dates": dates, "nums": extract_numbers(masked), "ents": entity_keys(extract_entities(source)),
            "folded": fold(source).lower()}


def rule_verify_claim(claim: str, retr: Retriever, src: dict) -> dict:
    cands = retr.best(claim)
    start, end, score = cands[0]
    evidence = retr.text(start, end)
    checks: list[dict] = []
    contra: list[str] = []
    unver: list[str] = []

    cdates, cmasked = extract_dates(claim)
    cnums = extract_numbers(cmasked)
    edates, emasked = extract_dates(evidence)
    enums = extract_numbers(emasked)

    # dates -- compared to the evidence passage, but only flagged if absent from the WHOLE source
    bad_d = [d for d in dates_unmatched(cdates, edates) if d in dates_unmatched([d], src["dates"])]
    if cdates:
        checks.append({"name": "dates", "passed": not bad_d,
                       "detail": "all dates found in source" if not bad_d else
                       f"date(s) not in source: {', '.join(d['raw'] for d in bad_d)}"})
    if bad_d:
        (contra if edates else unver).append(
            f"date '{bad_d[0]['raw']}' does not match the source" + (f" (source says '{edates[0]['raw']}')" if edates else ""))

    bad_n = [n for n in numbers_unmatched(cnums, enums) if n in numbers_unmatched([n], src["nums"])]
    if cnums:
        checks.append({"name": "numbers", "passed": not bad_n,
                       "detail": "all numbers found in source" if not bad_n else
                       f"number(s) not in source: {', '.join(n['raw'] for n in bad_n)}"})
    if bad_n:
        (contra if enums else unver).append(
            f"number '{bad_n[0]['raw']}' does not match the source" + (f" (source says '{enums[0]['raw']}')" if enums else ""))

    cl_neg, ev_neg = has_negation(claim), has_negation(evidence)
    checks.append({"name": "negation", "passed": cl_neg == ev_neg,
                   "detail": "negation consistent" if cl_neg == ev_neg else
                   ("claim is negated but source passage is not" if cl_neg else "source passage is negated but claim is not")})
    if cl_neg != ev_neg:
        contra.append("negation differs between claim and source passage")

    cents = entity_keys(extract_entities(claim))
    missing = {e for e in cents if e not in src["folded"]}
    ev_ents = entity_keys(extract_entities(evidence))
    if cents:
        checks.append({"name": "entities", "passed": not missing,
                       "detail": "all entities found in source" if not missing else
                       f"entity not in source: {', '.join(sorted(missing))}"})
    if missing:
        swapped = ev_ents - cents
        (contra if (swapped and score >= 0.5) else unver).append(
            f"entity '{sorted(missing)[0]}' is not in the source" + (f" (source passage mentions '{sorted(swapped)[0]}')" if swapped and score >= 0.5 else ""))

    checks.append({"name": "overlap", "passed": score >= SUPPORT_THRESHOLD,
                   "detail": f"{score:.0%} of the claim's content terms appear in the best passage"})

    if score < RELEVANCE_THRESHOLD:
        status, expl = "unverifiable", "No source passage covers this claim well enough to judge it."
        evidence = evidence if score > 0.15 else ""
    elif contra:
        status, expl = "contradicted", "Conflicts with the source: " + "; ".join(contra) + "."
    elif unver:
        status, expl = "unverifiable", "Cannot be confirmed: " + "; ".join(unver) + "."
    elif score >= SUPPORT_THRESHOLD:
        status, expl = "supported", "The key terms, numbers, dates and polarity of the claim match the source passage."
    else:
        status, expl = "unverifiable", "The source passage only partially overlaps with the claim."
    return {"claim": claim, "status": status, "evidence": evidence, "evidence_index": start,
            "explanation": expl, "confidence": None, "evidence_score": round(score, 3),
            "checks": checks, "method": "rule"}


def _parse_json(raw: str) -> dict:
    t = raw.strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j < 0:
        raise ProviderError("The verifier model returned malformed output (no JSON found).", 502)
    try:
        return json.loads(t[i:j + 1])
    except json.JSONDecodeError:
        raise ProviderError("The verifier model returned malformed JSON.", 502)


def llm_verify_claims(client: LLMClient, source: str, claims: list[str], retr: Retriever) -> list[dict]:
    if len(source) <= 12000:
        src_block = f"SOURCE:\n{source}"
    else:
        idxs = sorted({k for c in claims for s, e, _ in retr.best(c) for k in range(s, e)})
        src_block = "SOURCE EXCERPTS (retrieved passages):\n" + "\n".join(retr.sents[i] for i in idxs)
    numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(claims))
    raw = client.complete(VERIFY_SYSTEM, f"{src_block}\n\nCLAIMS:\n{numbered}", max_tokens=min(4000, 300 + 200 * len(claims)))
    data = _parse_json(raw)
    by_id = {}
    for r in data.get("results", []):
        try:
            by_id[int(r.get("id"))] = r
        except (TypeError, ValueError):
            continue
    norm_src = re.sub(r"\s+", " ", fold(source)).lower()
    out = []
    for i, claim in enumerate(claims):
        r = by_id.get(i)
        if not r or str(r.get("status", "")).lower() not in STATUSES:
            raise ProviderError(f"The verifier model did not return a valid verdict for claim {i + 1}.", 502)
        ev = str(r.get("evidence", "")).strip()
        grounded = bool(ev) and re.sub(r"\s+", " ", fold(ev)).lower() in norm_src
        out.append({"claim": claim, "status": str(r["status"]).lower(), "evidence": ev if grounded else "",
                    "explanation": str(r.get("explanation", "")).strip() or "No explanation returned.",
                    "evidence_grounded": grounded, "confidence": None, "method": "llm"})
    return out


def aggregate(results: list[dict]) -> dict:
    n = len(results)
    c = Counter(r["status"] for r in results)
    rate = (lambda k: round(c[k] / n, 4)) if n else (lambda k: None)
    return {
        "n_claims": n, "supported": c["supported"], "contradicted": c["contradicted"],
        "unverifiable": c["unverifiable"],
        "support_rate": rate("supported"), "contradiction_rate": rate("contradicted"),
        "unverifiable_rate": rate("unverifiable"),
        "unsupported_rate": round((c["contradicted"] + c["unverifiable"]) / n, 4) if n else None,
        "formula": "support_rate = supported_claims / total_claims",
    }


METHOD_LABELS = {
    "rule": "Rule-based heuristic (offline; not an AI model)",
    "llm": "LLM judge",
    "hybrid": "Hybrid: LLM judge + rule checks",
}


def verify(source: str, summary: str, method: str, client: LLMClient | None) -> dict:
    """``method`` must already be resolved to rule | llm | hybrid."""
    return verify_claims(source, split_claims(summary), method, client)


def verify_claims(source: str, claims: list[str], method: str, client: LLMClient | None) -> dict:
    retr = Retriever(source)
    src = _source_facts(source)
    rule = [rule_verify_claim(c, retr, src) for c in claims]
    results = rule
    if method in ("llm", "hybrid"):
        assert client is not None
        llm = llm_verify_claims(client, source, claims, retr) if claims else []
        results = []
        for r, l in zip(rule, llm):
            item = dict(l)
            item["evidence_index"] = r["evidence_index"]
            item["evidence_score"] = r["evidence_score"]
            item["checks"] = r["checks"]
            if not item["evidence"]:
                item["evidence"] = r["evidence"]
            if method == "hybrid" and item["status"] == "supported":
                hard = [c for c in r["checks"] if c["name"] in ("numbers", "dates") and not c["passed"]]
                if hard:
                    item["status"] = r["status"] if r["status"] in ("contradicted", "unverifiable") else "unverifiable"
                    item["explanation"] += f" [Rule check overrode the LLM verdict: {hard[0]['detail']}.]"
                    item["disagreement"] = True
            item["method"] = method
            results.append(item)
    return {"method": method, "method_label": METHOD_LABELS[method], "claims": results,
            "metrics": aggregate(results), "limitations": LIMITATIONS,
            "is_ai_verification": method in ("llm", "hybrid"),
            "n_source_passages": len(retr.sents)}
