"""Script/lexicon-based language identification and Code-Mixing Index (CMI).

Language labels: "hi" (Hindi), "en" (English), "hinglish" (Hindi-English code-mixed).

Token tags: Devanagari token -> "hi"; Latin token in a small romanised-Hindi
lexicon -> "hi"; any other Latin word -> "en"; numbers are language independent.
CMI = 100 * (1 - max(n_hi, n_en) / (n_hi + n_en))   (Das & Gambäck, 2014, without
"other" tokens). 0 = monolingual, up to 50 = evenly mixed.

Limitations: romanised-Hindi detection uses a short lexicon and will miss
unlisted words; Latin-script words shared by both languages are tagged "en".
"""
from __future__ import annotations

import re
from collections import Counter

ROMAN_HI = set(
    """hai hain hoon ho raha rahi rahe tha thi ka ki ke ko se mein par aur ya nahi nahin nhi kya kyun kyunki
    kaise kab kahan kaun yeh ye woh wo vo hum humne tum aap mera meri mere tera teri apna apni apne jab tab
    agar lekin magar sirf sab kuch bahut zyada abhi kal aaj saal log logon sarkar desh shehar wajah kaaran
    liye lie kiya kiye karna kar karke gaya gayi gaye hua hui hue hota hoti hote chahiye sakta sakti sakte
    bata batata matlab bhi toh isliye jaise jo""".split()
)
_TOK = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|[\u0900-\u097F]+")
_DEV = re.compile(r"[\u0900-\u097F]")


def tag_tokens(text: str) -> list[str]:
    tags = []
    for tok in _TOK.findall(text):
        if _DEV.search(tok):
            tags.append("hi_dev")
        elif tok.lower() in ROMAN_HI:
            tags.append("hi_rom")
        else:
            tags.append("en")
    return tags


def cmi(text: str) -> float:
    tags = tag_tokens(text)
    n_hi = sum(1 for t in tags if t.startswith("hi"))
    n_en = len(tags) - n_hi
    n = n_hi + n_en
    if n == 0:
        return 0.0
    return round(100.0 * (1 - max(n_hi, n_en) / n), 2)


def detect_language(text: str) -> str:
    tags = tag_tokens(text)
    c = Counter(tags)
    hi_dev, hi_rom, en = c["hi_dev"], c["hi_rom"], c["en"]
    total = hi_dev + hi_rom + en
    if total == 0:
        return "en"
    hi = hi_dev + hi_rom
    if hi / total < 0.10:
        return "en"
    if hi_rom > hi_dev:  # romanised Hindi => treated as Hinglish
        return "hinglish"
    if en / total >= 0.10:
        return "hinglish"
    return "hi"


LANGUAGE_NAMES = {"hi": "Hindi", "en": "English", "hinglish": "Hindi-English (code-mixed)", "auto": "Auto-detect"}
