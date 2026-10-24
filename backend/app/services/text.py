"""Text utilities for Hindi / English / Hinglish: folding, tokenising, sentence
splitting, and extraction of numbers, dates and entities.

Design notes
- Devanagari combining marks (matras) are *not* matched by ``\\w`` in Python, so
  tokenisation uses explicit Unicode ranges.
- ``fold`` removes nukta and zero-width joiners and maps Devanagari digits to
  ASCII so that e.g. ``१५`` == ``15`` and ``ज़`` == ``ज``.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_DEV = "\u0900-\u097F"
_WORD_CHARS = r"\w\u0900-\u0963\u0966-\u097F"
TOKEN_RE = re.compile(rf"\d+(?:[.,]\d+)*|[{_WORD_CHARS}]+")
_L = rf"(?<![{_WORD_CHARS}])"
_R = rf"(?![{_WORD_CHARS}])"


def fold(text: str) -> str:
    t = unicodedata.normalize("NFD", text)
    t = t.replace("\u093c", "").replace("\u200c", "").replace("\u200d", "")
    return unicodedata.normalize("NFC", t).translate(_DEV_DIGITS)


STOPWORDS = set(
    """the a an of to in on at is are was were be been being and or for with by that this these those it
    as from which has have had will would can could their its they he she we you i not but if than then so
    also into over under about after before during between there here
    है हैं था थी थे का की के को में से पर और ने यह वह एक भी तो कि जो हो रहा रही रहे लिए करने ही इस उस कर
    गया गई गए जा सकता सकती सकते होता होती होते इन उन या कुछ तक बहुत
    hai hain hoon ho raha rahi rahe tha thi ka ki ke ko se mein par aur ne ye yeh woh wo vo ek bhi jo
    liye kar karke gaya gayi gaye hua hui hue hota hoti hote kya""".split()
)
STOPWORDS = {fold(w) for w in STOPWORDS}

NEGATION = {
    fold(w)
    for w in "not no never none neither nor cannot without nahi nahin nhi bina mat नहीं नही बिना मत कभीनहीं".split()
}
_NT_RE = re.compile(r"n['’]t\b", re.I)


def tokens(text: str, drop_stop: bool = False) -> list[str]:
    toks = [t.lower() for t in TOKEN_RE.findall(fold(text))]
    if drop_stop:
        toks = [t for t in toks if t not in STOPWORDS]
    return toks


def word_count(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def has_negation(text: str) -> bool:
    if _NT_RE.search(text):
        return True
    return any(t in NEGATION for t in tokens(text))


_ABBR = {"dr", "mr", "mrs", "ms", "prof", "st", "no", "vs", "etc", "rs", "jr", "sr", "inc", "ltd"}
_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|(?<=[।॥])\s*|\n+")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SPLIT_RE.split(text) if p and p.strip()]
    merged: list[str] = []
    for p in parts:
        if merged:
            prev = merged[-1]
            last = prev.rstrip(".").split()[-1].lower() if prev.split() else ""
            if prev.endswith(".") and (last in _ABBR or (len(last) == 1 and last.isalpha())):
                merged[-1] = prev + " " + p
                continue
        merged.append(p)
    return merged


# --------------------------------------------------------------------------- numbers & dates
_MONTHS_RAW = {
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "जनवरी": 1, "फ़रवरी": 2, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4, "मई": 5, "जून": 6, "जुलाई": 7,
    "अगस्त": 8, "सितंबर": 9, "सितम्बर": 9, "अक्टूबर": 10, "नवंबर": 11, "नवम्बर": 11,
    "दिसंबर": 12, "दिसम्बर": 12,
}
_SHORT_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
                 "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12}
MONTHS = {fold(k): v for k, v in _MONTHS_RAW.items()}
MONTHS_ALL = {**MONTHS, **_SHORT_MONTHS}


def _alt(d: dict) -> str:
    return "|".join(re.escape(k) for k in sorted(d, key=len, reverse=True))


_M_ALL = _alt(MONTHS_ALL)
_M_FULL = _alt({**MONTHS, "may": 5})
_YEAR = r"(?:19|20)\d{2}"
_DATE_PATTERNS = [
    ("dmy", re.compile(rf"{_L}(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_M_ALL})\.?(?:,?\s*({_YEAR}))?{_R}", re.I)),
    ("mdy", re.compile(rf"{_L}({_M_ALL})\.?\s+(\d{{1,2}})(?!\d)(?:st|nd|rd|th)?(?:,?\s*({_YEAR}))?{_R}", re.I)),
    ("my", re.compile(rf"{_L}({_M_ALL})\.?,?\s*({_YEAR}){_R}", re.I)),
    ("iso", re.compile(rf"{_L}({_YEAR})-(\d{{2}})-(\d{{2}}){_R}")),
    ("num", re.compile(rf"{_L}(\d{{1,2}})[/-](\d{{1,2}})[/-]((?:19|20)?\d{{2}}){_R}")),
    ("m", re.compile(rf"{_L}({_M_FULL}){_R}", re.I)),
    ("y", re.compile(rf"{_L}({_YEAR}){_R}")),
]


def _canon(day, month, year) -> str:
    return f"{year or '----'}-{('%02d' % month) if month else '--'}-{('%02d' % day) if day else '--'}"


def extract_dates(text: str) -> tuple[list[dict], str]:
    """Return (dates, text_with_dates_masked)."""
    work = fold(text)
    out: list[dict] = []
    for kind, pat in _DATE_PATTERNS:
        def repl(m: re.Match, kind=kind) -> str:
            g = m.groups()
            day = month = year = None
            try:
                if kind == "dmy":
                    day, month, year = int(g[0]), MONTHS_ALL[g[1].lower()], g[2]
                elif kind == "mdy":
                    month, day, year = MONTHS_ALL[g[0].lower()], int(g[1]), g[2]
                elif kind == "my":
                    month, year = MONTHS_ALL[g[0].lower()], g[1]
                elif kind == "iso":
                    year, month, day = g[0], int(g[1]), int(g[2])
                elif kind == "num":
                    day, month, year = int(g[0]), int(g[1]), g[2]
                    if len(year) == 2:
                        year = "20" + year
                elif kind == "m":
                    month = MONTHS_ALL[g[0].lower()]
                elif kind == "y":
                    year = g[0]
            except (KeyError, ValueError):
                return m.group(0)
            if day is not None and not 1 <= day <= 31:
                return m.group(0)
            if month is not None and not 1 <= month <= 12:
                return m.group(0)
            out.append({"raw": m.group(0).strip(), "day": day, "month": month,
                        "year": int(year) if year else None, "key": _canon(day, month, int(year) if year else None)})
            return " " * len(m.group(0))

        work = pat.sub(repl, work)
    return out, work


_SCALE = {"crore": Decimal(10) ** 7, "करोड": Decimal(10) ** 7, "lakh": Decimal(10) ** 5, "लाख": Decimal(10) ** 5,
          "million": Decimal(10) ** 6, "billion": Decimal(10) ** 9, "अरब": Decimal(10) ** 9, "thousand": Decimal(10) ** 3,
          "हजार": Decimal(10) ** 3, "k": Decimal(10) ** 3}
_UNITS = {"%": "%", "percent": "%", "per cent": "%", "प्रतिशत": "%", "km": "km", "°c": "°c",
          "डिग्री": "°c", "degrees": "°c", "degree": "°c"}
_UNIT_ALT = "|".join(re.escape(u) for u in sorted({*_SCALE, *_UNITS}, key=len, reverse=True))
_NUM_RE = re.compile(rf"(?<![\w.]){'(\\d+(?:[.,]\\d+)*)'}\s*({_UNIT_ALT})?(?![{_WORD_CHARS}])", re.I)


def extract_numbers(masked_text: str) -> list[dict]:
    """masked_text must already be folded with dates masked (see extract_dates)."""
    out = []
    for m in _NUM_RE.finditer(masked_text):
        raw_num = m.group(1).replace(",", "")
        unit_raw = (m.group(2) or "").lower()
        try:
            val = Decimal(raw_num)
        except InvalidOperation:
            continue
        unit = ""
        if unit_raw in _SCALE:
            val *= _SCALE[unit_raw]
        elif unit_raw in _UNITS:
            unit = _UNITS[unit_raw]
        norm = format(val.normalize(), "f")
        out.append({"raw": m.group(0).strip(), "value": norm, "unit": unit})
    return out


def numbers_unmatched(claim_nums: list[dict], ev_nums: list[dict]) -> list[dict]:
    bad = []
    for c in claim_nums:
        ok = any(c["value"] == e["value"] and (c["unit"] == e["unit"] or not c["unit"] or not e["unit"])
                 for e in ev_nums)
        if not ok:
            bad.append(c)
    return bad


def dates_unmatched(claim_dates: list[dict], ev_dates: list[dict]) -> list[dict]:
    bad = []
    for c in claim_dates:
        ok = False
        for e in ev_dates:
            if all(c[k] is None or c[k] == e[k] for k in ("day", "month", "year")):
                ok = True
                break
        if not ok:
            bad.append(c)
    return bad


# --------------------------------------------------------------------------- entities
GAZETTEER = [
    "भारत", "दिल्ली", "मुंबई", "कोलकाता", "चेन्नई", "बेंगलुरु", "हैदराबाद", "पुणे", "जयपुर", "लखनऊ", "पटना",
    "भोपाल", "उत्तर प्रदेश", "महाराष्ट्र", "बिहार", "गुजरात", "राजस्थान", "पंजाब", "हरियाणा", "केरल",
    "तमिलनाडु", "कर्नाटक", "चीन", "अमेरिका", "पाकिस्तान", "रूस", "जापान", "नेपाल", "इसरो", "संयुक्त राष्ट्र",
    "सुप्रीम कोर्ट", "रिज़र्व बैंक", "नासा", "गूगल", "माइक्रोसॉफ्ट",
]
_GAZ_FOLDED = [(fold(g), g) for g in sorted(GAZETTEER, key=len, reverse=True)]
_HONORIFIC = re.compile(
    rf"(?:श्री|श्रीमती|डॉ|डॉक्टर|प्रधानमंत्री|मुख्यमंत्री|अध्यक्ष|मंत्री)\.?\s+([{_DEV}]+(?:\s+[{_DEV}]+)?)"
)
_CAP_RE = re.compile(r"(?<![\w])[A-Z][\w&'’\-]*(?:\s+(?:(?:of|the|and|for)\s+)?[A-Z][\w&'’\-]*)*")
_NOT_ENTITY = {"the", "a", "an", "in", "on", "at", "this", "these", "that", "it", "i", "we", "he", "she",
               "they", "but", "and", "as", "for", "if", "however", "also", "according", "while", "when",
               "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"} | set(MONTHS_ALL)


def extract_entities(text: str) -> list[str]:
    found: dict[str, None] = {}
    mid_words: set[str] = set()
    cands: list[tuple[str, bool]] = []
    for sent in split_sentences(text):
        for m in _CAP_RE.finditer(sent):
            span = m.group(0).strip()
            words = span.split()
            while words and words[0].lower() in {"the", "a", "an"}:
                words = words[1:]
            if not words:
                continue
            span = " ".join(words)
            at_start = m.start() == 0
            if not at_start:
                mid_words.add(span.lower())
            cands.append((span, at_start))
    for span, at_start in cands:
        low = span.lower()
        single = " " not in span
        if low in _NOT_ENTITY:
            continue
        if single and at_start and not (span.isupper() and len(span) > 1) and low not in mid_words:
            continue
        found.setdefault(span)
    folded = fold(text)
    for fg, orig in _GAZ_FOLDED:
        if re.search(rf"{_L}{re.escape(fg)}{_R}", folded):
            found.setdefault(orig)
    for m in _HONORIFIC.finditer(folded):
        words = [w for w in m.group(1).split() if w not in STOPWORDS][:2]
        if words:
            found.setdefault(" ".join(words))
    return list(found)


def entity_keys(entities: list[str]) -> set[str]:
    return {fold(e).lower() for e in entities}


def fact_density(sentence: str) -> float:
    dates, masked = extract_dates(sentence)
    nums = extract_numbers(masked)
    ents = extract_entities(sentence)
    n = max(word_count(sentence), 1)
    return (2 * len(dates) + 2 * len(nums) + len(ents)) / n ** 0.5


def analyze(text: str) -> dict:
    dates, masked = extract_dates(text)
    nums = extract_numbers(masked)
    ents = extract_entities(text)
    sents = split_sentences(text)
    scored = sorted(((fact_density(s), i) for i, s in enumerate(sents)), reverse=True)
    top = sorted(i for sc, i in scored[: min(5, len(sents))] if sc > 0)
    return {
        "key_facts": [sents[i] for i in top],
        "entities": ents,
        "dates": [d["raw"] for d in dates],
        "numbers": [n["raw"] for n in nums],
    }
