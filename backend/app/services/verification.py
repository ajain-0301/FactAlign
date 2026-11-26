"""Factuality verification: summary claims vs. source evidence.

Pipeline
1. Split the summary into claims (sentence level).
2. The rule path splits compound claims into atomic clauses and retrieves
   several relevant source passages for each clause (IDF-weighted token
   containment with light prefix stemming; also tries 2-sentence windows).
3. Judge each claim or atomic clause:
   * rule   - local XLM-R NLI plus deterministic checks for changed numbers/dates,
              normalized entities, clause-scoped negation, conflicting passages, and overlap.
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

from app.core.errors import AppError
from app.services.providers import LLMClient, ProviderError
from app.services.prompts import VERIFY_SYSTEM
from app.services.text import (
    dates_unmatched, entity_keys, extract_dates, extract_entities, extract_numbers,
    fold, has_negation, numbers_unmatched, split_sentences, tokens,
)

LIMITATIONS = (
    "Automatic verification is an estimate, not a guarantee of correctness. The offline rule path combines "
    "lexical checks with local XLM-R NLI. Lexical checks rely on overlap and conservative surface-pattern clause splitting; "
    "number-word and transliteration coverage is finite, and entity extraction may miss Hindi names without a title "
    "or names outside the built-in aliases and gazetteer. LLM judgements can be wrong or "
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


def _validate_embedding_batch(vectors, expected_count: int) -> list[list[float]]:
    try:
        normalized = [[float(value) for value in vector] for vector in vectors]
    except (TypeError, ValueError) as exc:
        raise AppError("Local embedding model returned invalid vectors.", 503) from exc
    if (
        len(normalized) != expected_count
        or not normalized
        or not normalized[0]
        or any(len(vector) != len(normalized[0]) for vector in normalized)
        or any(not math.isfinite(value) for vector in normalized for value in vector)
    ):
        raise AppError("Local embedding model returned invalid vectors.", 503)
    return normalized


def _cosine_vectors(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise AppError("Local embedding model returned incompatible vectors.", 503)
    denominator = math.sqrt(sum(value * value for value in left) * sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


_NEGATION_ALIASES = {
    "nahi": "nahi", "nahin": "nahi", "nhi": "nahi", "nahiin": "nahi",
    "नही": "नहीं", "नहीं": "नहीं",
}
_ROMAN_HINDI_ALIASES = {
    **_NEGATION_ALIASES,
    "hain": "hai", "hae": "hai",
    "karna": "kar", "karta": "kar", "karti": "kar", "karte": "kar",
    "karo": "kar", "kare": "kar", "krna": "kar", "krta": "kar", "krti": "kar",
    "kiya": "kiya", "kiye": "kiya",
    "karega": "karega", "karegi": "karega", "karenge": "karega",
    "rahi": "raha", "rahe": "raha",
    "hogi": "hoga", "honge": "hoga",
    "gayi": "gaya", "gaye": "gaya",
    "banaayi": "banaya", "banayi": "banaya", "banayee": "banaya", "banaya": "banaya",
    "banaye": "banaya", "lagaya": "lagaya", "lagaye": "lagaya", "lagayi": "lagaya",
    "lagai": "lagaya", "diya": "diya", "diye": "diya",
    "hui": "hua", "hue": "hua", "huye": "hua",
    "crores": "crore", "karod": "crore", "karore": "crore", "krore": "crore",
    "lacs": "lakh", "lac": "lakh",
    "rupaye": "rupee", "rupay": "rupee", "rupees": "rupee",
    "dilli": "delhi", "newdelhi": "delhi", "bombay": "mumbai", "bambai": "mumbai",
    "bangalore": "bengaluru", "bangaluru": "bengaluru",
    "calcutta": "kolkata",
    "bharat": "india",
}
_DEVANAGARI_ALIASES = {
    "हैं": "है", "थी": "था", "थे": "था",
    "किए": "किया",
    "बनाए": "बनाया", "बनाई": "बनाया",
    "लगाए": "लगाया", "लगाई": "लगाया",
    "गई": "गया", "गए": "गया",
    "होगी": "होगा", "होंगे": "होगा",
    "करोड": "crore", "करोड़": "crore", "करोड़": "crore",
    "लाख": "lakh",
    "दिल्ली": "delhi", "मुंबई": "mumbai", "बंबई": "mumbai",
    "बेंगलुरु": "bengaluru", "बैंगलोर": "bengaluru",
    "कोलकाता": "kolkata", "कलकत्ता": "kolkata",
    "भारत": "india",
    "विश्व बैंक": "world bank", "रिजर्व बैंक": "reserve bank",
}
_ENTITY_ALIASES = {
    "delhi": "delhi", "new delhi": "delhi", "dilli": "delhi", "दिल्ली": "delhi",
    "mumbai": "mumbai", "bombay": "mumbai", "bambai": "mumbai", "मुंबई": "mumbai", "बंबई": "mumbai",
    "bengaluru": "bengaluru", "bangalore": "bengaluru", "बेंगलुरु": "bengaluru", "बैंगलोर": "bengaluru",
    "kolkata": "kolkata", "calcutta": "kolkata", "कोलकाता": "kolkata", "कलकत्ता": "kolkata",
    "india": "india", "bharat": "india", "भारत": "india",
    "world bank": "world bank", "विश्व बैंक": "world bank",
    "reserve bank of india": "reserve bank of india", "rbi": "reserve bank of india",
    "रिजर्व बैंक ऑफ इंडिया": "reserve bank of india", "रिजर्व बैंक": "reserve bank of india",
}
_HINDI_PERSON_RE = re.compile(
    r"(?:श्री(?:मती|मान)?|डॉ\.?|डॉक्टर|प्रधानमंत्री|मुख्यमंत्री|राष्ट्रपति|मंत्री|सांसद)"
    r"\s+([\u0900-\u097f]+(?:\s+[\u0900-\u097f]+){0,2})"
)
_HINDI_ORG_RE = re.compile(
    r"([\u0900-\u097fA-Za-z][\u0900-\u097fA-Za-z0-9&.'’\-]*"
    r"(?:\s+[\u0900-\u097fA-Za-z][\u0900-\u097fA-Za-z0-9&.'’\-]*){0,3}\s+"
    r"(?:बैंक|निगम|मंत्रालय|विश्वविद्यालय|संस्थान|आयोग|प्राधिकरण|सरकार))"
)
_NEGATION_TOKENS = {
    "not", "no", "never", "none", "neither", "nor", "cannot", "without",
    "nahi", "na", "mat", "bina", "नहीं", "मत", "बिना",
}


def _extract_entities(text: str) -> list[str]:
    found = list(extract_entities(text))
    found.extend(match.group(1).strip() for match in _HINDI_PERSON_RE.finditer(text))
    found.extend(match.group(1).strip() for match in _HINDI_ORG_RE.finditer(text))
    return list(dict.fromkeys(entity for entity in found if entity))


_DEV_CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh",
    "ष": "sh", "स": "s", "ह": "h",
}
_DEV_VOWELS = {
    "अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u",
    "ऋ": "ri", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
}
_DEV_MATRAS = {
    "ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u",
    "ृ": "ri", "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
}


def _romanize_devanagari(text: str) -> str:
    folded = fold(text)
    output = []
    inherent_vowel = False
    for char in folded:
        if char in _DEV_CONSONANTS:
            output.append(_DEV_CONSONANTS[char] + "a")
            inherent_vowel = True
        elif char in _DEV_MATRAS:
            if inherent_vowel:
                output[-1] = output[-1][:-1] + _DEV_MATRAS[char]
            else:
                output.append(_DEV_MATRAS[char])
            inherent_vowel = False
        elif char == "्":
            if inherent_vowel:
                output[-1] = output[-1][:-1]
            inherent_vowel = False
        elif char in _DEV_VOWELS:
            output.append(_DEV_VOWELS[char])
            inherent_vowel = False
        elif char in {"ं", "ँ"}:
            output.append("n")
            inherent_vowel = False
        elif char.isspace():
            if inherent_vowel and output:
                output[-1] = output[-1][:-1]
            output.append(" ")
            inherent_vowel = False
    if inherent_vowel and output:
        output[-1] = output[-1][:-1]
    return " ".join("".join(output).split())


def _simplify_transliteration(text: str) -> str:
    value = fold(text).lower().replace("w", "v")
    for pair, single in (("aa", "a"), ("ee", "i"), ("ii", "i"), ("oo", "u"), ("uu", "u")):
        value = value.replace(pair, single)
    return re.sub(r"av\b", "ao", value)


def _canonical_token(token: str) -> str:
    value = fold(token).lower()
    value = _ROMAN_HINDI_ALIASES.get(value, value)
    value = _DEVANAGARI_ALIASES.get(value, value)
    return value


def _canonical_entity_key(entity: str) -> str:
    key = " ".join(fold(token).lower() for token in tokens(entity))
    if key in _ENTITY_ALIASES:
        return _ENTITY_ALIASES[key]
    normalized_keys = entity_keys([entity])
    if normalized_keys:
        normalized_key = next(iter(normalized_keys))
        if normalized_key in _ENTITY_ALIASES:
            return _ENTITY_ALIASES[normalized_key]
        key = normalized_key
    key = " ".join(_canonical_token(token) for token in tokens(entity))
    if key in _ENTITY_ALIASES:
        return _ENTITY_ALIASES[key]
    romanized = _romanize_devanagari(key) if re.search(r"[\u0900-\u097f]", key) else key
    return _simplify_transliteration(romanized)


def _normalized_tokens(text: str, drop_stop: bool = False) -> list[str]:
    entities = _extract_entities(text)
    entity_words = {word for entity in entities for word in tokens(entity)}
    remaining = [word for word in tokens(text) if word not in entity_words]
    normalized = [_canonical_token(word) for word in remaining]
    normalized.extend(
        word for entity in entities
        for word in tokens(_canonical_entity_key(entity))
    )
    if not drop_stop:
        return normalized
    filtered = [_canonical_token(word) for word in tokens(" ".join(normalized), drop_stop=True)]
    for word in normalized:
        if word in _NEGATION_TOKENS and word not in filtered:
            filtered.append(word)
    return filtered


def _normalized_query(text: str) -> str:
    return " ".join(_canonical_token(token) for token in tokens(text))


_NUMBER_WORD_VALUES: dict[str, int] = {}
for _value, _words in {
    0: ("zero", "शून्य", "sunya"),
    1: ("one", "एक", "ek"),
    2: ("two", "दो", "do"),
    3: ("three", "तीन", "teen", "tin"),
    4: ("four", "चार", "char", "chaar"),
    5: ("five", "पांच", "पाँच", "panch", "paanch"),
    6: ("six", "छह", "छः", "chhe", "chhah"),
    7: ("seven", "सात", "saat", "sat"),
    8: ("eight", "आठ", "aath", "ath"),
    9: ("nine", "नौ", "nau"),
    10: ("ten", "दस", "das"),
    11: ("eleven", "ग्यारह", "gyarah"),
    12: ("twelve", "बारह", "barah"),
    13: ("thirteen", "तेरह", "terah"),
    14: ("fourteen", "चौदह", "chaudah"),
    15: ("fifteen", "पंद्रह", "pandrah"),
    16: ("sixteen", "सोलह", "solah"),
    17: ("seventeen", "सत्रह", "satrah"),
    18: ("eighteen", "अठारह", "atharah"),
    19: ("nineteen", "उन्नीस", "unnis"),
    20: ("twenty", "बीस", "bees"),
    21: ("इक्कीस", "ikkis"),
    22: ("बाईस", "baais", "bais"),
    30: ("thirty", "तीस", "tees"),
    40: ("forty", "चालीस", "chalis", "chalees"),
    50: ("fifty", "पचास", "pachas", "pachaas"),
    60: ("sixty", "साठ", "saath"),
    70: ("seventy", "सत्तर", "sattar"),
    80: ("eighty", "अस्सी", "assi"),
    90: ("ninety", "नब्बे", "nabbe"),
}.items():
    for _word in _words:
        _NUMBER_WORD_VALUES[fold(_word).lower()] = _value
_NUMBER_SCALES = {
    "hundred": 100, "सौ": 100,
    "thousand": 1_000, "हजार": 1_000,
    "lakh": 100_000, "lac": 100_000, "लाख": 100_000,
    "million": 1_000_000,
    "crore": 10_000_000, "crores": 10_000_000, "karod": 10_000_000,
    "karore": 10_000_000, "krore": 10_000_000, "करोड": 10_000_000,
    "billion": 1_000_000_000,
}
_NUMBER_WORD_VALUES.update({key: value for key, value in _NUMBER_SCALES.items()})
_MONTH_ALIASES = {
    "janvari": "January", "janvary": "January", "जनवरी": "January",
    "farvari": "February", "february": "February", "फरवरी": "February",
    "maarch": "March", "march": "March", "मार्च": "March",
    "aprail": "April", "अप्रैल": "April", "mei": "May", "मई": "May",
    "jun": "June", "जून": "June", "julai": "July", "जुलाई": "July",
    "agast": "August", "अगस्त": "August", "sitambar": "September", "सितंबर": "September",
    "aktubar": "October", "अक्टूबर": "October", "navambar": "November", "नवंबर": "November",
    "disambar": "December", "दिसंबर": "December",
}
_NUMBER_CONTEXT_RE = re.compile(
    r"(?<![\w.])\d+(?:[.,]\d+)*(?:\s*(?:crores?|karod|karore|krore|करोड|"
    r"lakhs?|lacs?|लाख|millions?|billions?|thousand|हजार|k|%|percent|प्रतिशत|km|degrees?|डिग्री))?(?![\w])",
    re.I,
)


def _number_words_to_digits(text: str) -> str:
    word_matches = list(re.finditer(r"[\w\u0900-\u097f]+", text))
    spans: list[tuple[int, int, int]] = []
    start = end = -1
    phrase: list[str] = []
    previous_word = ""

    def flush() -> None:
        nonlocal start, end, phrase, previous_word
        if not phrase:
            return
        total = current = 0
        for item in phrase:
            value = _NUMBER_WORD_VALUES[fold(item).lower()]
            if value == 100:
                current = max(current, 1) * value
            elif value >= 1_000:
                total += max(current, 1) * value
                current = 0
            elif value >= 20 and value % 10 == 0:
                current += value
            else:
                current += value
        spans.append((start, end, total + current))
        start = end = -1
        phrase = []
        previous_word = ""

    for match in word_matches:
        raw = match.group()
        word = fold(raw).lower()
        recognized = word in _NUMBER_WORD_VALUES
        bridge = word in {"and", "और"} and previous_word in {
            "hundred", "सौ", "thousand", "हजार",
        }
        gap = text[end:match.start()] if end >= 0 else ""
        if recognized and (not phrase or not gap.strip(" -")):
            if not phrase:
                start = match.start()
            phrase.append(raw)
            end = match.end()
            previous_word = word
        elif bridge and phrase and not gap.strip(" -"):
            end = match.end()
            previous_word = word
        else:
            flush()
            if recognized:
                start, end, phrase, previous_word = match.start(), match.end(), [raw], word
    flush()
    for start, end, value in reversed(spans):
        text = f"{text[:start]}{value}{text[end:]}"
    return text


def _normalize_month_words(text: str) -> str:
    for alias, month in _MONTH_ALIASES.items():
        text = re.sub(rf"(?<!\w){re.escape(alias)}(?!\w)", month, text, flags=re.I)
    return text


def _multilingual_facts(text: str) -> tuple[list[dict], list[dict]]:
    normalized = _number_words_to_digits(_normalize_month_words(text))
    dates, date_masked = extract_dates(normalized)
    numbers = extract_numbers(date_masked)
    return dates, numbers


def _fact_context_tokens(text: str) -> list[str]:
    normalized = _number_words_to_digits(_normalize_month_words(text))
    _, masked = extract_dates(normalized)
    masked = _NUMBER_CONTEXT_RE.sub(" ", masked)
    for entity in sorted(_extract_entities(masked), key=len, reverse=True):
        masked = re.sub(re.escape(entity), " ", masked, flags=re.I)
    return _normalized_tokens(masked, drop_stop=True)


def _entity_keys(text: str) -> set[str]:
    return {_canonical_entity_key(entity) for entity in _extract_entities(text)}


def _fact_context_score(claim: str, evidence: str, retr: "Retriever") -> float:
    claim_tokens = _fact_context_tokens(claim)
    evidence_tokens = set(_fact_context_tokens(evidence))
    return retr._score(claim_tokens, evidence_tokens, {_stem(token) for token in evidence_tokens})


class Retriever:
    def __init__(self, source: str):
        self.sents = split_sentences(source) or [source]
        self.sent_tokens = [set(_normalized_tokens(s, drop_stop=True)) for s in self.sents]
        self.sent_stems = [{_stem(t) for t in ts} for ts in self.sent_tokens]
        self._semantic_vectors: dict[tuple[int, int], list[float]] | None = None
        n = len(self.sents)
        df = Counter(t for ts in self.sent_tokens for t in ts)
        self.idf = {t: math.log(1 + n / c) for t, c in df.items()}
        self.max_idf = math.log(1 + n) + 1
        self.offsets = []
        pos = 0
        for s in self.sents:
            i = source.find(s, pos)
            if i < 0:
                self.offsets.append(None)
            else:
                self.offsets.append((i, i + len(s)))
                pos = i + len(s)

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
        ctoks = _normalized_tokens(claim, drop_stop=True)
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

    def semantic_scores(self, claim: str, models) -> dict[tuple[int, int], float]:
        if not models.fits(claim):
            raise AppError("A claim exceeds the local embedding context window; shorten the claim.", 422)
        if self._semantic_vectors is None:
            spans = [(i, i + 1) for i in range(len(self.sents))]
            spans.extend((i, i + 2) for i in range(len(self.sents) - 1))
            texts = {}
            for start, end in spans:
                passage = self.text(start, end)
                if not passage.strip():
                    continue
                if not models.fits(passage):
                    if end == start + 1:
                        raise AppError(
                            "A source sentence exceeds the local embedding context window; shorten the source.",
                            422,
                        )
                    continue
                texts[(start, end)] = passage

            self._semantic_vectors = {}
            ordered_spans = list(texts)
            for batch_start in range(0, len(ordered_spans), 32):
                batch_spans = ordered_spans[batch_start:batch_start + 32]
                vectors = _validate_embedding_batch(
                    models.encode([texts[span] for span in batch_spans]),
                    len(batch_spans),
                )
                self._semantic_vectors.update(zip(batch_spans, vectors))

        claim_vector = _validate_embedding_batch(models.encode([claim]), 1)[0]
        return {
            span: _cosine_vectors(claim_vector, vector)
            for span, vector in self._semantic_vectors.items()
        }

    def text(self, start: int, end: int) -> str:
        return " ".join(self.sents[start:end])


_CONTEXT_SPLIT_RE = re.compile(
    r"[;；]+|\s+(?:but|however|although|whereas|while|yet|and|or|लेकिन|मगर|बल्कि|किन्तु|परंतु|परन्तु|और|तथा|या|"
    r"lekin|magar|jabki|aur)\s+",
    re.I,
)
_ATOMIC_SPLIT_RE = re.compile(
    r"(?P<semicolon>[;；]+)|\s+(?P<connector>and|but|although|whereas|while|yet|however|लेकिन|मगर|बल्कि|किन्तु|परंतु|परन्तु|और|तथा|जबकि|aur|lekin|magar|jabki)\s+",
    re.I,
)
_CLAUSE_AUXILIARIES = {
    "am", "is", "are", "was", "were", "be", "been", "being", "has", "have", "had",
    "do", "does", "did", "will", "would", "can", "could", "may", "might", "must",
    "shall", "should", "है", "हैं", "था", "थी", "थे", "होगा", "होगी", "होंगे",
    "hai", "tha", "thi", "hoga", "hogi", "honge", "raha", "rahi", "rahe",
}
_IRREGULAR_VERBS = {
    "announced", "approved", "became", "began", "built", "bought", "brought", "came",
    "changed", "chose", "cut", "did", "drew", "drove", "fell", "fed", "felt", "found",
    "funded", "gave", "got", "grew", "held", "kept", "knew", "led", "left", "lost",
    "made", "met", "paid", "put", "ran", "read", "rose", "said", "saw", "sent", "set",
    "sold", "spent", "stood", "took", "told", "won", "wrote",
}
_PRESENT_VERBS = {
    "adds", "announces", "approves", "builds", "closes", "costs", "creates", "cuts",
    "contains", "covers", "decreases", "delivers", "employs", "establishes", "features",
    "funds", "grows", "has", "helps", "includes", "increases", "leads", "makes", "offers",
    "opens", "operates", "owns", "pays", "produces", "provides", "reaches", "reduces",
    "reports", "requires", "runs", "says", "sells", "sends", "serves", "shows", "spends",
    "spans", "starts", "supports", "takes", "uses", "works",
}
_BASE_VERBS = {
    "add", "announce", "approve", "become", "begin", "build", "buy", "bring",
    "change", "choose", "close", "cost", "create", "cut", "decrease", "deliver",
    "employ", "establish", "feature", "fund", "grow", "help", "include", "increase",
    "lead", "make", "offer", "open", "operate", "own", "pay", "produce", "provide",
    "reach", "reduce", "report", "require", "run", "say", "sell", "send", "serve",
    "show", "spend", "span", "start", "support", "take", "use", "work", "install",
    "allocate", "complete", "enroll", "enrol", "launch", "approve",
}
_HINDI_VERB_FORMS = {
    "किया", "किए", "बनाया", "बनाए", "बनाई", "लगाया", "लगाए", "लगाई", "घटाया",
    "घटाए", "बढ़ाया", "बढ़ाए", "दिया", "दिए", "रखा", "रखे", "गया", "गई", "गए",
    "करेगा", "करेगी", "करेंगे", "करेगे", "होगा", "होगी", "होंगे",
    "हुआ", "हुई", "हुए", "रहा", "रही", "रहे", "करता", "करती", "करते",
    "बढ़ेगा", "बढ़ेगी", "बढ़ेंगे", "घटेगा", "घटेगी", "घटेंगे",
}
_HINDI_VERB_ENDINGS = (
    "ाएगा", "ाएगी", "ाएंगे", "ाए", "ाई", "िया", "िए", "ेगा", "ेगी", "ेगे",
    "ेंगे", "ेंगी", "ता", "ती", "ते", "या", "यी", "एगा", "एगी", "एंगे", "हुआ", "हुई", "हुए",
)
_ATOMIC_SUBJECT_LEADS = {"the", "a", "an", "this", "that", "these", "those"}
_ATOMIC_ADVERBS = {"also", "then"}
_ATOMIC_SUBJECTS = _ATOMIC_SUBJECT_LEADS | {
    "it", "they", "he", "she", "we", "you", "i", "मैं", "हम", "वे", "यह", "वह",
}
_ATOMIC_NON_SUBJECT_LEADS = {
    "also", "then", "quickly", "rapidly", "later", "finally", "subsequently",
    "in", "on", "at", "after", "before", "during", "by", "with", "for", "from",
    "not", "never", "no", "only", "because", "therefore", "नहीं", "मत", "nahi", "nahin", "nhi",
    "aur", "lekin", "magar", "jabki",
}


def _context_clauses(text: str) -> list[str]:
    clauses = []
    for sentence in split_sentences(text):
        clauses.extend(part.strip() for part in _CONTEXT_SPLIT_RE.split(sentence) if part.strip())
    return clauses or [text]


def _is_verb_form(word: str) -> bool:
    word = _canonical_token(word)
    return (
        word in _IRREGULAR_VERBS or word in _PRESENT_VERBS or word in _BASE_VERBS or word in _HINDI_VERB_FORMS
        or (len(word) >= 5 and word.endswith(("ed", "ing")))
        or any(word.endswith(ending) for ending in _HINDI_VERB_ENDINGS)
        or word.endswith((
            "karega", "karenge", "kiya", "banaya", "lagaya", "gaya", "hoga",
            "yega", "yegi", "yenge", "raha", "karta", "karte",
        ))
        or word in {"kar", "ho", "ja", "ban", "lag", "de", "le"}
    )


def _has_predicate(text: str) -> bool:
    words = tokens(text)
    entity_words = {
        word
        for entity in _extract_entities(text)
        for word in tokens(entity)
    }
    return any(word in _CLAUSE_AUXILIARIES for word in words) or any(
        word not in entity_words and _is_verb_form(word) for word in words
    )


def _starts_with_predicate(text: str) -> bool:
    words = tokens(text)
    while words and words[0] in _ATOMIC_ADVERBS:
        words.pop(0)
    if not words or words[0] in _ATOMIC_SUBJECTS:
        return False
    return words[0] in _CLAUSE_AUXILIARIES or _is_verb_form(words[0])


def _subject_prefix(claim: str) -> str | None:
    words = list(re.finditer(r"[\w\u0900-\u097f]+", claim))
    entity_words = set()
    for entity in _extract_entities(claim):
        entity_words.update(tokens(entity))
    has_devanagari = bool(re.search(r"[\u0900-\u0963\u0970-\u097f]", claim))
    if has_devanagari:
        hindi_postpositions = {"ने", "में", "पर", "को", "से", "द्वारा", "तक"}
        for match in words[1:]:
            word = match.group(0).lower()
            if word in hindi_postpositions or re.fullmatch(r"\d+", word):
                prefix = claim[:match.end() if word in hindi_postpositions else match.start()].strip(" ,")
                if prefix:
                    return prefix
    for index, match in enumerate(words):
        word = match.group(0).lower()
        if word in _CLAUSE_AUXILIARIES or (
            index > 0 and word not in entity_words and _is_verb_form(word)
        ):
            prefix = claim[:match.start()].strip(" ,")
            if prefix:
                prefix_tokens = tokens(prefix)
                if prefix_tokens and prefix_tokens[0] in _ATOMIC_NON_SUBJECT_LEADS:
                    return None
                return prefix
    if not words:
        return None
    return None


def _numeric_frame_prefix(text: str) -> str | None:
    if extract_dates(text)[0]:
        return None
    numbers = list(re.finditer(r"(?<![\w])[\d०-९][\d०-९,./-]*", text))
    number_start = numbers[-1].start() if numbers else None
    if number_start is None:
        word_numbers = [
            match.start()
            for match in re.finditer(r"[\w\u0900-\u097f]+", text)
            if fold(match.group()).lower() in _NUMBER_WORD_VALUES
        ]
        if not word_numbers:
            return None
        number_start = word_numbers[0]
    prefix = text[:number_start].strip(" ,")
    return prefix or None


def _coordinated_tail_prefix(text: str) -> str | None:
    folded = fold(text).lower()
    matching_entities = [
        entity for entity in _extract_entities(text)
        if folded.endswith(fold(entity).lower())
    ]
    if matching_entities:
        entity = max(matching_entities, key=len)
        start = folded.rfind(fold(entity).lower())
        return text[:start].rstrip()
    return None


def _shared_auxiliary_frame(claim: str, subject: str | None) -> str:
    if not subject:
        return ""
    remainder = claim[len(subject):].strip()
    frame = []
    for word in tokens(remainder):
        if word in _CLAUSE_AUXILIARIES or word in _NEGATION_TOKENS:
            frame.append(word)
        else:
            break
    return " ".join(frame)


def _atomic_components(claim: str) -> list[str]:
    """Split clear coordinated predicates, carrying the original subject to fragments."""
    if (
        re.search(r"\bnot\s+only\b.*\bbut\s+also\b", claim, re.I)
        or re.search(r"(?:न\s+केवल|na\s+sirf).*?(?:बल्कि|balki)", claim, re.I)
    ):
        return [claim]
    matches = list(_ATOMIC_SPLIT_RE.finditer(claim))
    if not matches:
        return [claim]

    components: list[str] = []
    current = claim[:matches[0].start()].strip()
    for index, match in enumerate(matches):
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(claim)
        following = claim[match.end():next_start].strip()
        current_has_predicate = _has_predicate(current)
        following_has_predicate = _has_predicate(following)
        starts_with_predicate = _starts_with_predicate(following)
        subject = _subject_prefix(current) if starts_with_predicate else None
        shared_frame = _shared_auxiliary_frame(current, subject)
        object_prefix = None
        starts_with_number = bool(re.match(r"^[\d०-९]", following))
        if current_has_predicate and starts_with_number:
            object_prefix = _numeric_frame_prefix(current)
        if current_has_predicate and not following_has_predicate:
            starts_with_entity = bool(_extract_entities(following))
            if following and starts_with_entity and object_prefix is None:
                object_prefix = _coordinated_tail_prefix(current)
        following_tokens = tokens(following)
        first_predicate = following_tokens[0] if following_tokens else ""
        while first_predicate in _ATOMIC_ADVERBS and len(following_tokens) > 1:
            following_tokens.pop(0)
            first_predicate = following_tokens[0]
        first_match = re.search(r"[\w\u0900-\u097f]+", following)
        first_word = first_match.group(0) if first_match else ""
        has_hindi_subject_marker = bool(
            re.search(r"(?:\s|^)(?:ने|में|पर|को|से|द्वारा|ne|mein|par|ko|se)(?:\s|$)", following, re.I)
        )
        explicit_subject = bool(
            following_tokens
            and not starts_with_predicate
            and first_predicate not in _ATOMIC_NON_SUBJECT_LEADS
            and (
                first_predicate in _ATOMIC_SUBJECTS
                or has_hindi_subject_marker
                or bool(_extract_entities(following))
                or (
                    not re.search(r"[\u0900-\u097f]", following)
                    and bool(_subject_prefix(following))
                    and first_word not in _ATOMIC_NON_SUBJECT_LEADS
                )
                or (
                    bool(re.search(r"[\u0900-\u097f]", following))
                    and bool(_numeric_frame_prefix(following))
                    and not starts_with_number
                )
            )
        )
        inherited_predicate = bool(
            subject
            and starts_with_predicate
        )
        independent_predicates = current_has_predicate and following_has_predicate and (
            explicit_subject or inherited_predicate
        )
        split_semicolon = (
            bool(match.group("semicolon"))
            and current_has_predicate
            and following_has_predicate
            and (explicit_subject or inherited_predicate)
        )
        if split_semicolon or independent_predicates or object_prefix is not None:
            if current:
                components.append(current)
            if object_prefix is not None:
                following = f"{object_prefix} {following}"
            elif starts_with_predicate and subject:
                following = " ".join(part for part in (subject, shared_frame, following) if part)
            current = following
        else:
            separator = match.group("semicolon") or match.group("connector")
            current = f"{current} {separator} {following}".strip()
    if current:
        components.append(current)
    return components or [claim]


def _negation_match(claim: str, evidence: str, retr: Retriever) -> bool | None:
    """Compare polarity only between claim clauses and their best-matching evidence clauses."""
    evidence_data = []
    for clause in _context_clauses(evidence):
        ev_tokens = _normalized_tokens(clause, drop_stop=True)
        evidence_data.append((clause, set(ev_tokens), {_stem(t) for t in ev_tokens}))
    outcomes: list[bool | None] = []
    for claim_clause in _context_clauses(claim):
        claim_toks = _normalized_tokens(claim_clause, drop_stop=True)
        if not claim_toks:
            continue
        claim_negated = has_negation(claim_clause)
        scored = [
            (retr._score(claim_toks, ev_toks, ev_stems), has_negation(clause))
            for clause, ev_toks, ev_stems in evidence_data
        ]
        best_score = max((score for score, _ in scored), default=0.0)
        if best_score < SUPPORT_THRESHOLD:
            outcomes.append(None)
            continue
        best_polarities = {
            claim_negated == polarity
            for score, polarity in scored
            if score >= best_score - 1e-9
        }
        outcomes.append(best_polarities.pop() if len(best_polarities) == 1 else None)
    if False in outcomes:
        return False
    if not outcomes or None in outcomes:
        return None
    return True


def _source_facts(source: str) -> dict:
    return {"entities": _entity_keys(source)}


def _rule_candidates(
    claim: str,
    retr: Retriever,
    semantic_model=None,
    context_claim: str | None = None,
) -> list[tuple[int, int, float, float]]:
    component_queries = list(dict.fromkeys(
        query
        for clause in _context_clauses(claim)
        for query in (clause, _normalized_query(clause))
        if query.strip()
    ))
    discovery_queries = list(component_queries)
    if context_claim and context_claim.strip() != claim.strip():
        discovery_queries.extend((context_claim, _normalized_query(context_claim)))
    discovery_queries = list(dict.fromkeys(query for query in discovery_queries if query.strip()))

    spans: set[tuple[int, int]] = set()
    component_semantic: dict[tuple[int, int], float] = {}
    for query in discovery_queries:
        ranked = retr.best(query, top=3 if semantic_model else 5)
        spans.update((start, end) for start, end, _ in ranked)
        spans.update(
            (index, index + 1)
            for start, end, _ in ranked
            for index in range(start, end)
        )
        if semantic_model is None:
            continue
        is_component_query = query in component_queries
        if not is_component_query and not semantic_model.fits(query):
            continue
        scores = retr.semantic_scores(query, semantic_model)
        if is_component_query:
            component_semantic.update({
                span: max(component_semantic.get(span, 0.0), score)
                for span, score in scores.items()
            })
        spans.update(
            span for span, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:3]
        )

    lexical_scores: dict[tuple[int, int], float] = {}
    for start, end in spans:
        window_tokens = set().union(*retr.sent_tokens[start:end])
        window_stems = set().union(*retr.sent_stems[start:end])
        lexical_scores[(start, end)] = max(
            (
                retr._score(_normalized_tokens(query, drop_stop=True), window_tokens, window_stems)
                for query in component_queries
            ),
            default=0.0,
        )

    ranked_spans = sorted(
        spans,
        key=lambda span: max(lexical_scores.get(span, 0.0), component_semantic.get(span, 0.0)),
        reverse=True,
    )[:6]
    return [
        (
            start,
            end,
            lexical_scores.get((start, end), 0.0),
            component_semantic.get((start, end), 0.0),
        )
        for start, end in ranked_spans
    ]


def _candidate_is_relevant(candidate: tuple[int, int, float, float]) -> bool:
    return candidate[2] >= RELEVANCE_THRESHOLD or candidate[3] >= RELEVANCE_THRESHOLD


def _verify_rule_passage(
    claim: str,
    retr: Retriever,
    src: dict,
    candidate: tuple[int, int, float, float],
) -> dict:
    start, end, score = candidate[:3]
    evidence = retr.text(start, end)
    if not _candidate_is_relevant(candidate):
        return {
            "claim": claim,
            "status": "unverifiable",
            "evidence": "",
            "evidence_index": start,
            "explanation": "No source passage is sufficiently relevant to judge this claim.",
            "confidence": None,
            "evidence_score": round(score, 3),
            "relevance_score": round(max(score, candidate[3]), 3),
            "evidence_end": end,
            "checks": [{
                "name": "relevance",
                "passed": False,
                "detail": "lexical and semantic relevance scores are below threshold",
            }],
            "method": "rule",
        }

    checks: list[dict] = []
    contra: list[str] = []
    unver: list[str] = []

    cdates, cnums = _multilingual_facts(claim)
    edates, enums = _multilingual_facts(evidence)
    cents = _entity_keys(claim)
    ev_ents = _entity_keys(evidence)
    contextual_match = _fact_context_score(claim, evidence, retr)
    entity_context_compatible = not cents or not ev_ents or bool(cents & ev_ents)

    # Keep factual checks local to the selected evidence; unrelated source mentions must not mask a mismatch.
    bad_d = dates_unmatched(cdates, edates)
    date_conflict = bool(
        bad_d and edates and contextual_match >= SUPPORT_THRESHOLD and entity_context_compatible
    )
    if cdates:
        checks.append({"name": "dates", "passed": not bad_d,
                       "detail": "all dates found in evidence" if not bad_d else
                       f"date(s) not matched in evidence: {', '.join(d['raw'] for d in bad_d)}",
                       "conflict": date_conflict})
    if bad_d:
        (contra if date_conflict else unver).append(
            f"date '{bad_d[0]['raw']}' does not match the evidence"
            + (f" (evidence says '{edates[0]['raw']}')" if edates else ""))

    bad_n = numbers_unmatched(cnums, enums)
    number_conflict = bool(
        bad_n and enums and contextual_match >= SUPPORT_THRESHOLD and entity_context_compatible
    )
    if cnums:
        checks.append({"name": "numbers", "passed": not bad_n,
                       "detail": "all numbers found in evidence" if not bad_n else
                       f"number(s) not matched in evidence: {', '.join(n['raw'] for n in bad_n)}",
                       "conflict": number_conflict})
    if bad_n:
        (contra if number_conflict else unver).append(
            f"number '{bad_n[0]['raw']}' does not match the evidence"
            + (f" (evidence says '{enums[0]['raw']}')" if enums else ""))

    negation_match = _negation_match(claim, evidence, retr)
    negation_detail = {
        True: "claim and matching evidence clauses have consistent polarity",
        False: "claim and matching evidence clauses have opposite polarity",
        None: "could not align claim polarity with a relevant evidence clause",
    }[negation_match]
    checks.append({"name": "negation", "passed": negation_match is True, "detail": negation_detail})
    if negation_match is False:
        contra.append("negation differs between the claim and matching evidence")
    elif negation_match is None:
        unver.append("negation could not be aligned to a relevant evidence clause")

    missing = cents - ev_ents
    missing_source = cents - src["entities"]
    conflicting_missing = sorted(missing & missing_source)
    entity_conflict = bool(
        conflicting_missing and ev_ents - cents and contextual_match >= SUPPORT_THRESHOLD
    )
    if cents:
        checks.append({
            "name": "entities",
            "passed": not missing,
            "detail": "all extracted entities found in evidence" if not missing else
            f"entity not found in this passage: {', '.join(sorted(missing))}",
            "conflict": entity_conflict,
        })
    if missing:
        swapped = ev_ents - cents
        entity = conflicting_missing[0] if entity_conflict else sorted(missing)[0]
        if entity_conflict:
            contra.append(
                f"entity '{entity}' conflicts with '{sorted(swapped)[0]}' in matching evidence"
            )
        elif entity in missing_source:
            unver.append(f"entity '{entity}' could not be confirmed in the source")
        else:
            unver.append(f"entity '{entity}' is absent from this passage but appears elsewhere in the source")

    checks.append({"name": "overlap", "passed": score >= SUPPORT_THRESHOLD,
                   "detail": f"{score:.0%} of the claim's content terms appear in the best passage"})

    if contra:
        status, expl = "contradicted", "Conflicts with the source: " + "; ".join(contra) + "."
    elif unver:
        status, expl = "unverifiable", "Cannot be confirmed: " + "; ".join(unver) + "."
    elif score >= SUPPORT_THRESHOLD:
        status, expl = "supported", "The key terms, numbers, dates and polarity of the claim match the source passage."
    else:
        status, expl = "unverifiable", "The source passage only partially overlaps with the claim."
    return {"claim": claim, "status": status, "evidence": evidence, "evidence_index": start,
            "explanation": expl, "confidence": None, "evidence_score": round(score, 3),
            "relevance_score": round(max(score, candidate[3]), 3),"evidence_end": end,
            "checks": checks, "method": "rule"}


def _validate_nli_scores(scores) -> dict[str, float]:
    if not isinstance(scores, dict) or set(scores) != {"entailment", "contradiction", "neutral"}:
        raise AppError("XLM-R NLI model returned invalid scores.", 503)
    try:
        validated = {label: float(value) for label, value in scores.items()}
    except (TypeError, ValueError) as exc:
        raise AppError("XLM-R NLI model returned invalid scores.", 503) from exc
    if any(not math.isfinite(value) or value < 0 or value > 1 for value in validated.values()) or (
        abs(sum(validated.values()) - 1) > 0.01
    ):
        raise AppError("XLM-R NLI model returned invalid scores.", 503)
    return validated


def _nli_status(scores: dict[str, float], threshold: float, margin: float) -> str:
    entailment = scores["entailment"]
    contradiction = scores["contradiction"]
    neutral = scores["neutral"]
    if entailment >= threshold and entailment - max(contradiction, neutral) >= margin:
        return "supported"
    if contradiction >= threshold and contradiction - max(entailment, neutral) >= margin:
        return "contradicted"
    return "unverifiable"


def _guardrail_failures(result: dict) -> list[dict]:
    return [
        check for check in result["checks"]
        if (
            check["name"] in {"numbers", "dates", "entities"} and not check["passed"]
        ) or (
            check["name"] == "negation"
            and not check["passed"]
            and "opposite polarity" in check["detail"]
        )
    ]


def _nli_contradiction_is_usable(result: dict) -> bool:
    failed_facts = [
        check for check in result["checks"]
        if check["name"] in {"numbers", "dates", "entities"} and not check["passed"]
    ]
    if not failed_facts:
        return True
    explicit_conflict = any(check.get("conflict", False) for check in failed_facts) or any(
        check["name"] == "negation"
        and not check["passed"]
        and "opposite polarity" in check["detail"]
        for check in result["checks"]
    )
    return explicit_conflict


def _apply_local_nli(
    claim: str,
    assessments: list[dict],
    candidates: list[tuple[int, int, float, float]],
    nli_model,
    threshold: float,
    margin: float,
) -> dict:
    evaluated = []
    for result, candidate in zip(assessments, candidates):
        scores = _validate_nli_scores(nli_model.score(result["evidence"], claim)) if result["evidence"] else None
        verdict = _nli_status(scores, threshold, margin) if scores else "unverifiable"
        evaluated.append({
            "result": result,
            "scores": scores,
            "status": verdict,
            "similarity": max(candidate[2], candidate[3]),
        })

    supports = [item for item in evaluated if item["status"] == "supported"]
    contradictions = [
        item for item in evaluated
        if item["status"] == "contradicted" and _nli_contradiction_is_usable(item["result"])
    ]
    rule_contradictions = [
        item for item in evaluated if item["result"]["status"] == "contradicted"
    ]
    same_passage_rule_conflicts = [
        item for item in rule_contradictions
        if any(item is support for support in supports)
    ]
    other_rule_contradictions = [
        item for item in rule_contradictions if item not in same_passage_rule_conflicts
    ]
    conflicts = bool((supports and contradictions) or (supports and other_rule_contradictions))
    same_passage_conflict = bool(same_passage_rule_conflicts) and not conflicts
    if conflicts:
        status = "unverifiable"
        selected = [
            max(supports, key=lambda item: item["scores"]["entailment"]),
            max(
                contradictions or rule_contradictions,
                key=lambda item: (
                    item["scores"]["contradiction"] if item["scores"] else 0.0,
                    item["similarity"],
                ),
            ),
        ]
        primary = max(selected, key=lambda item: item["similarity"])
    elif same_passage_conflict:
        status = "contradicted"
        primary = max(
            [item for item in supports if item in rule_contradictions],
            key=lambda item: item["similarity"],
        )
        selected = [primary]
    elif contradictions:
        status = "contradicted"
        primary = max(contradictions, key=lambda item: item["scores"]["contradiction"])
        selected = [primary]
    elif rule_contradictions:
        status = "contradicted"
        primary = max(rule_contradictions, key=lambda item: item["similarity"])
        selected = [primary]
    elif supports:
        clean_supports = [item for item in supports if not _guardrail_failures(item["result"])]
        if clean_supports:
            status = "supported"
            primary = max(clean_supports, key=lambda item: item["scores"]["entailment"])
        else:
            status = "unverifiable"
            primary = max(supports, key=lambda item: item["scores"]["entailment"])
        selected = [primary]
    else:
        status = "unverifiable"
        primary = max(evaluated, key=lambda item: item["similarity"])
        selected = [primary]

    primary_result = primary["result"]
    result = dict(primary_result)
    evidence = list(dict.fromkeys(
        item["result"]["evidence"] for item in selected if item["result"]["evidence"]
    ))
    result["evidence"] = "\n".join(evidence)
    result["status"] = status
    result["nli_scores"] = primary["scores"]

    if conflicts:
        if contradictions:
            explanation = "Retrieved passages conflict: semantic evidence contains both strong support and contradiction."
            nli_detail = "XLM-R found conflicting support and contradiction across retrieved passages."
        else:
            explanation = (
                "Retrieved passages conflict: one supports the claim while another contains an explicit factual conflict."
            )
            nli_detail = "XLM-R support conflicts with a deterministic factual contradiction in another passage."
    elif same_passage_conflict:
        explanation = (
            "Deterministic factual safeguards found an explicit conflict in the selected evidence "
            "despite XLM-R entailment."
        )
        nli_detail = "XLM-R found entailment, but an explicit factual conflict overrode the verdict."
    elif status == "supported":
        explanation = "XLM-R NLI supports the claim, and deterministic factual safeguards passed."
        nli_detail = "XLM-R found dominant entailment for the selected evidence passage."
    elif contradictions:
        explanation = "XLM-R NLI found dominant contradiction in the retrieved evidence."
        if primary_result["status"] == "contradicted":
            explanation += f" Deterministic checks: {primary_result['explanation']}"
        nli_detail = "XLM-R found dominant contradiction for the selected evidence passage."
    elif rule_contradictions:
        explanation = f"Deterministic checks found an explicit factual conflict: {primary_result['explanation']}"
        nli_detail = "XLM-R was inconclusive; explicit factual safeguards found a conflict."
    elif supports:
        failures = _guardrail_failures(primary_result)
        details = "; ".join(check["detail"] for check in failures)
        explanation = f"XLM-R supports the passage, but deterministic checks need review: {details}."
        nli_detail = "XLM-R found entailment, but deterministic safeguards prevented a Supported verdict."
    else:
        explanation = "XLM-R NLI was inconclusive for the best semantic evidence passage."
        nli_detail = "No retrieved passage met the configured entailment or contradiction thresholds."

    if primary["scores"]:
        scores = primary["scores"]
        nli_detail += (
            f" Scores: entailment {scores['entailment']:.3f}, contradiction "
            f"{scores['contradiction']:.3f}, neutral {scores['neutral']:.3f}."
        )
    result["explanation"] = explanation
    result["checks"] = list(primary_result["checks"])
    result["checks"].append({
        "name": "nli",
        "passed": primary["status"] == "supported" and not conflicts,
        "detail": nli_detail,
    })
    result["nli_scores"] = primary["scores"]
    passage_records = []
    seen_passages = set()
    for item in sorted(evaluated, key=lambda candidate: candidate["similarity"], reverse=True):
        passage = item["result"]["evidence"]
        if not passage:
            continue
        passage_key = " ".join(_normalized_tokens(passage, drop_stop=False))
        if passage_key in seen_passages:
            continue
        seen_passages.add(passage_key)
        passage_records.append({
            "evidence_index": item["result"]["evidence_index"],
            "passage": passage,
            "retrieval_score": round(item["similarity"], 3),
            "nli_scores": item["scores"],
            "status": item["status"],
            "checks": item["result"]["checks"],
            "evidence_end": item["result"]["evidence_end"],
        })
    result["evidence_passages"] = passage_records
    return result


def _verify_atomic_component(
    claim: str,
    retr: Retriever,
    src: dict,
    nli_model=None,
    nli_threshold: float = 0.75,
    nli_margin: float = 0.15,
    context_claim: str | None = None,
) -> dict:
    candidates = _rule_candidates(claim, retr, nli_model, context_claim)
    assessments = [
        _verify_rule_passage(claim, retr, src, candidate)
        for candidate in candidates
    ]
    if nli_model:
        return _apply_local_nli(claim, assessments, candidates, nli_model, nli_threshold, nli_margin)

    relevant = [
        result for result in assessments
        if result.get("relevance_score", result["evidence_score"]) >= RELEVANCE_THRESHOLD
    ]
    if not relevant:
        return max(assessments, key=lambda result: result.get("relevance_score", 0.0))

    supported = [result for result in relevant if result["status"] == "supported"]
    contradicted = [result for result in relevant if result["status"] == "contradicted"]
    if supported and contradicted:
        result = max(
            supported + contradicted,
            key=lambda item: item.get("relevance_score", item["evidence_score"]),
        )
        result["status"] = "unverifiable"
        result["explanation"] = (
            "Retrieved passages conflict: some support the claim while others contradict it."
        )
    elif supported:
        result = max(supported, key=lambda result: result.get("relevance_score", result["evidence_score"]))
    elif contradicted:
        result = max(contradicted, key=lambda result: result.get("relevance_score", result["evidence_score"]))
    else:
        result = max(relevant, key=lambda result: result.get("relevance_score", result["evidence_score"]))
    return result


def _atomic_result_details(claim: str, result: dict) -> dict:
    evidence_passages = result.get("evidence_passages")
    if evidence_passages is None:
        evidence_passages = (
            [{
                "evidence_index": result.get("evidence_index"),
                "passage": result["evidence"],
                "retrieval_score": result.get("relevance_score", result["evidence_score"]),
                "nli_scores": None,
                "status": result["status"],
                "checks": result["checks"],
                "evidence_end": result.get("evidence_end"),
            }]
            if result.get("evidence") else []
        )
    return {
        "claim": claim,
        "status": result["status"],
        "evidence": result.get("evidence", ""),
        "nli_scores": result.get("nli_scores"),
        "checks": result.get("checks", []),
        "explanation": result.get("explanation", ""),
        "evidence_passages": evidence_passages,
    }


def rule_verify_claim(
    claim: str,
    retr: Retriever,
    src: dict,
    nli_model=None,
    nli_threshold: float = 0.75,
    nli_margin: float = 0.15,
) -> dict:
    components = _atomic_components(claim)
    if len(components) == 1:
        result = _verify_atomic_component(
            claim, retr, src, nli_model, nli_threshold, nli_margin, context_claim=claim,
        )
        result["atomic_results"] = [_atomic_result_details(claim, result)]
        return result

    results = [
        _verify_atomic_component(
            component, retr, src, nli_model, nli_threshold, nli_margin, context_claim=claim,
        )
        for component in components
    ]
    if any(result["status"] == "contradicted" for result in results):
        status = "contradicted"
    elif any(result["status"] == "unverifiable" for result in results):
        status = "unverifiable"
    else:
        status = "supported"

    final_results = [result for result in results if result["status"] == status]
    if status == "supported":
        primary = min(final_results, key=lambda result: result["evidence_score"])
    else:
        primary = max(final_results, key=lambda result: result["evidence_score"])

    evidence_parts = []
    for result in [primary, *results]:
        if result["evidence"] and result["evidence"] not in evidence_parts:
            evidence_parts.append(result["evidence"])
    checks = [
        {
            **check,
            "detail": f"Component {index + 1}: {check['detail']}",
        }
        for index, result in enumerate(results)
        for check in result["checks"]
    ]
    explanations = [
        f"Component {index + 1} ({component}): {result['status'].title()}. {result['explanation']}"
        for index, (component, result) in enumerate(zip(components, results))
    ]
    return {
        **primary,
        "claim": claim,
        "status": status,
        "evidence": "\n".join(evidence_parts),
        "explanation": " ".join(explanations),
        "evidence_score": round(min(result["evidence_score"] for result in results), 3),
        "checks": checks,
        "atomic_results": results,
        "evidence_passages": [
            passage
            for atomic in results
            for passage in atomic.get("evidence_passages", [])
        ],
        "nli_scores": primary.get("nli_scores"),
    }

def _api_passages(r: dict, retr: Retriever, source_pages: list[dict] | None) -> list[dict]:
    atoms = r.get("atomic_results") or []
    out = []
    for a in atoms:
        component = a["claim"] if len(atoms) > 1 else None
        for p in a.get("evidence_passages", []):
            s = p["evidence_index"]
            e = p.get("evidence_end") or s + 1
            first, last = retr.offsets[s], retr.offsets[e - 1]
            start, end = (first[0], last[1]) if first and last else (None, None)
            page = None
            if start is not None and source_pages:
                page = next((sp["page"] for sp in source_pages if sp["start"] <= start < sp["end"]), None)
            out.append({
                "passage_id": len(out),
                "text": p["passage"],
                "page": page,
                "start": start,
                "end": end,
                "retrieval_similarity": p["retrieval_score"],
                "nli": p["nli_scores"],
                "component": component,
                "checks": [
                    {"name": c["name"], "passed": c["passed"], "detail": c["detail"]}
                    for c in p["checks"]
                ],
            })
    return out

def _parse_json(raw: str) -> dict:
    t = raw.strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j < 0:
        raise ProviderError("The verifier model returned malformed output (no JSON found).", 502)
    try:
        data = json.loads(t[i:j + 1])
    except json.JSONDecodeError as exc:
        raise ProviderError("The verifier model returned malformed JSON.", 502) from exc
    if not isinstance(data, dict):
        raise ProviderError("The verifier model returned malformed JSON: expected a JSON object.", 502)
    return data


def llm_verify_claims(client: LLMClient, source: str, claims: list[str], retr: Retriever) -> list[dict]:
    if len(source) <= 12000:
        src_block = f"SOURCE:\n{source}"
    else:
        idxs = sorted({k for c in claims for s, e, _ in retr.best(c) for k in range(s, e)})
        src_block = "SOURCE EXCERPTS (retrieved passages):\n" + "\n".join(retr.sents[i] for i in idxs)
    numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(claims))
    user = f"{src_block}\n\nCLAIMS:\n{numbered}"
    max_tokens = min(4000, 300 + 200 * len(claims))
    raw = client.complete(VERIFY_SYSTEM, user, max_tokens=max_tokens)
    try:
        data = _parse_json(raw)
    except ProviderError:
        retry_system = (
            VERIFY_SYSTEM
            + "\nYour previous response was not valid JSON. Return one complete JSON object only, "
            "with no markdown or surrounding text."
        )
        raw = client.complete(retry_system, user, max_tokens=max_tokens)
        try:
            data = _parse_json(raw)
        except ProviderError as retry_exc:
            raise ProviderError(
                "The verifier model returned malformed JSON after one retry. Please retry verification.",
                502,
            ) from retry_exc
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
    "rule": "Rule-based checks + local XLM-R NLI (offline)",
    "llm": "LLM judge",
    "hybrid": "Hybrid: LLM judge + rule checks",
}


def verify(source: str, summary: str, method: str, client: LLMClient | None) -> dict:
    """``method`` must already be resolved to rule | llm | hybrid."""
    return verify_claims(source, split_claims(summary), method, client)


def verify_claims(source: str, claims: list[str], method: str, client: LLMClient | None, source_pages=None) -> dict:
    retr = Retriever(source)
    src = _source_facts(source)
    nli_model = None
    nli_threshold = 0.75
    nli_margin = 0.15
    if method == "rule" and claims:
        from app.core.config import get_settings
        from app.services.nli_models import get_models

        settings = get_settings()
        nli_model = get_models(settings.embedding_model, settings.nli_model, local_only=True)
        nli_threshold = settings.nli_decision_threshold
        nli_margin = settings.nli_decision_margin
    rule = [
        rule_verify_claim(c, retr, src, nli_model, nli_threshold, nli_margin)
        for c in claims
    ]
    if method == "rule":
        for r in rule:
            r["evidence_passages"] = _api_passages(r, retr, source_pages)
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
            item["nli_scores"] = None
            item["atomic_results"] = r.get("atomic_results", [])
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
            "is_ai_verification": method in ("rule", "llm", "hybrid"),
            "n_source_passages": len(retr.sents)}
