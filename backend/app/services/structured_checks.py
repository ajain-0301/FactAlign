"""Conservative independent checks; incomplete extraction never proves support.

Rules are scoped to one evidence passage, not a bag of facts from the document.
Unknown transliterations and event roles require review rather than contradiction.
"""
import re

from app.services.text import (fold, tokens, extract_dates, extract_numbers, dates_unmatched,
                               extract_entities, has_negation)

_GROUPS = [
    ('zero', 'शून्य', 'shunya'), ('one', 'एक', 'ek'), ('two', 'दो', 'do'),
    ('three', 'तीन', 'teen'), ('four', 'चार', 'chaar'), ('five', 'पांच', 'पाँच', 'paanch'),
    ('six', 'छह', 'chhe'), ('seven', 'सात', 'saat'), ('eight', 'आठ', 'aath'),
    ('nine', 'नौ', 'nau'), ('ten', 'दस', 'das'), ('eleven', 'ग्यारह', 'gyarah'),
    ('twelve', 'बारह', 'barah'), ('thirteen', 'तेरह', 'terah'), ('fourteen', 'चौदह', 'chaudah'),
    ('fifteen', 'पंद्रह', 'pandrah'), ('sixteen', 'सोलह', 'solah'), ('seventeen', 'सत्रह', 'satrah'),
    ('eighteen', 'अठारह', 'atharah'), ('nineteen', 'उन्नीस', 'unnis'), ('twenty', 'बीस', 'bees'),
]
_WORD_NUMBERS = {fold(word): str(i) for i, group in enumerate(_GROUPS) for word in group}
# These are aliases, not a comprehensive named-entity recognizer.
_ALIASES = {'दिल्ली': 'delhi', 'मुंबई': 'mumbai', 'भारत': 'india', 'इसरो': 'isro',
            'करोड': 'crore', 'करोड़': 'crore', 'karod': 'crore', 'karor': 'crore',
            'हजार': 'thousand', 'hazar': 'thousand', 'लाख': 'lakh'}
_UNITS = {'km': ('distance', 1000), 'kilometers': ('distance', 1000), 'किलोमीटर': ('distance', 1000),
          'm': ('distance', 1), 'meters': ('distance', 1), 'मीटर': ('distance', 1),
          'kg': ('mass', 1000), 'किलोग्राम': ('mass', 1000), 'g': ('mass', 1),
          'grams': ('mass', 1), 'ग्राम': ('mass', 1),
          'rupees': ('inr', 1), 'रुपये': ('inr', 1), 'रुपए': ('inr', 1), 'rs': ('inr', 1),
          'dollars': ('usd', 1), 'डॉलर': ('usd', 1), '%': ('percent', 1),
          'percent': ('percent', 1), 'प्रतिशत': ('percent', 1)}


def normalize(text: str) -> str:
    text = fold(text).lower()
    # Avoid interpreting English auxiliary 'do' as the Hinglish number two.
    words = {k: v for k, v in _WORD_NUMBERS.items() if k != 'do'}
    text = re.sub(r'\bdo(?=\s+(?:schools?|students?|people|log|crore|lakh|vidyalaya)\b)', '2', text)
    for word, value in {**_ALIASES, **words}.items():
        text = re.sub(r'(?<![\w\u0900-\u097f])' + re.escape(fold(word)) + r'(?![\w\u0900-\u097f])', value, text)
    return text


def facts(text: str):
    normalized = normalize(text)
    dates, masked = extract_dates(normalized)
    return normalized, dates, extract_numbers(masked)


_QUANTITY_RE = re.compile(r'\d+(?:[.,]\d+)*\s*(?:(?:crore|lakh|million|billion|thousand)\s*)?(?:%|[\w\u0900-\u097f]+)?')


def quantities(text: str):
    result = []
    # extract_numbers handles scale normalization; bind following units separately.
    for m in _QUANTITY_RE.finditer(text):
        part = m.group()
        nums = extract_numbers(part)
        unit = next((_UNITS[t] for t in reversed(tokens(part)) if t in _UNITS), None)
        if '%' in part:
            unit = ('percent', 1)
        if nums and unit:
            result.append((float(nums[0]['value']) * unit[1], unit[0]))
    return result


def untyped_numbers(text: str):
    # Unit conversions are checked separately; they must not hide a changed bare count.
    text = _QUANTITY_RE.sub(lambda m: ' ' * len(m.group()) if quantities(m.group()) else m.group(), text)
    _, masked = extract_dates(text)
    return extract_numbers(masked)


def temporal(text: str) -> set[str]:
    ts = set(tokens(text))
    out = set()
    for label, cues in {
        'before': {'before', 'पहले', 'pehle'}, 'after': {'after', 'बाद', 'baad'},
        'future': {'will', 'होगा', 'होगी', 'hoga', 'hogi', 'karega'},
        'past': {'was', 'were', 'था', 'थी', 'थे', 'tha', 'thi', 'completed'},
    }.items():
        if ts & cues:
            out.add(label)
    return out


def check_claim(claim: str, evidence: str) -> list[dict]:
    ct, cd, cn = facts(claim)
    et, ed, en = facts(evidence)
    checks = []
    def add(name, outcome, detail):
        checks.append({'name': name, 'passed': outcome == 'match', 'outcome': outcome, 'detail': detail})
    # Quantities are compared after unit scaling, before bare numbers.
    cq, eq = quantities(ct), quantities(et)
    cn, en = untyped_numbers(ct), untyped_numbers(et)
    for name, c, e, same in (
        ('numbers', cn, en, lambda: all(any(n['value'] == v['value'] for v in en) for n in cn)),
        ('dates', cd, ed, lambda: not dates_unmatched(cd, ed)),
        ('units', cq, eq, lambda: all(q in eq for q in cq)),
    ):
        outcome = 'not_applicable' if not c else 'missing' if not e else 'match' if same() else 'mismatch'
        add(name, outcome, f'Claim: {c}; passage: {e}')
    known_entities = {'delhi', 'mumbai', 'india', 'isro'}
    ce = {normalize(e) for e in extract_entities(claim)} | (set(tokens(ct)) & known_entities)
    ee = {normalize(e) for e in extract_entities(evidence)} | (set(tokens(et)) & known_entities)
    missing = {e for e in ce if e not in et and e not in ee}
    add('entities', 'review' if missing else 'match' if ce else 'not_applicable',
        'Unresolved entity aliases: ' + ', '.join(sorted(missing)) if missing else 'No entity discrepancy detected; extraction is heuristic.')
    negation_mismatch = has_negation(claim) != has_negation(evidence)
    add('negation', 'mismatch' if negation_mismatch else 'match', 'Negation differs.' if negation_mismatch else 'Negation cues agree.')
    ctime, etime = temporal(ct), temporal(et)
    opposite = any(a in ctime and b in etime or b in ctime and a in etime
                   for a, b in [('before', 'after'), ('future', 'past')])
    add('temporal_relationships', 'mismatch' if opposite else 'review' if ctime - etime else 'match' if ctime else 'not_applicable',
        f'Claim cues: {sorted(ctime)}; passage cues: {sorted(etime)}. Event-role binding requires review.')
    return checks
