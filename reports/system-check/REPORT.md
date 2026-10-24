# FactAlign basic check report

Checked using the existing `/home/jaina/FactAlign/.venv`. Generated 20 October 2026, 11:55 PM IST.

## Result

- Frontend/backend API connection: **passed**, including CORS, the compiled API URL, and six live local API-contract tests.
- Frontend Fact Checker page: **HTTP 200**, verification controls rendered. This was an HTTP/API-client check, not interactive browser automation.
- Backend tests: **109 passed**. Frontend tests against an isolated demo backend: **11 passed**, none skipped. TypeScript check passed.
- PDF: a synthetic three-page Hindi/English/Hinglish PDF was **accepted with exact Unicode text and page offsets preserved**; PDF-to-summary page metadata also passed.
- Local embedding/XLM-R models: **loaded successfully** in the project environment. Real verification endpoint returned HTTP 200 for all three languages.
- Groq requests used for this report: **3 of 3 approved**, with automatic retries disabled. Summaries were reused from the earlier Groq run, so none were regenerated.
- **Calibrated confidence is unavailable (`null`).** Scores below are uncalibrated model scores, not probabilities that a claim is factually correct.

## Basic factuality scores

Each original document contains **15 words**. The checked summaries are the previously generated **standard** summaries, including their original errors.

| Language | Claims | Supported | Contradicted | Unsupported | Uncertain | Support rate | Mean claim score /100 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hindi | 4 | 1 | 0 | 2 | 1 | 25% | 29.86 |
| English | 1 | 0 | 0 | 0 | 1 | 0% | 99.95 |
| Hinglish | 4 | 1 | 0 | 0 | 3 | 25% | 99.62 |

Mean claim score = mean of each claim’s maximum passage entailment × 100. Support rate = supported claims / all claims. Contradiction count is the Contradicted column; warnings are independent and can occur on Uncertain claims.

### What these results show

- Hindi’s June/30,000 recruitment claim has only **0.10/100 entailment**, **67.13% contradiction**, and a contradiction warning. Its final label is Uncertain because contradiction did not meet the 75% decision threshold. The number and missing-date checks also flag it.
- English has **99.95/100 entailment** but remains Uncertain because the conservative temporal check requests review of the summary’s explicit future wording against the source’s announcement. This is an overcautious guard result, not evidence that the English summary is false.
- Hinglish’s incorrect **saat (7)** versus source **das (10)** receives **98.81/100 entailment** from XLM-R. The independent number mismatch prevents a Supported label. This directly demonstrates why a high NLI score must not be presented as calibrated confidence.
- These are three smoke-check examples, not a human-labelled accuracy benchmark. Extraction phrasing, implicit tense, transliteration, and NLI number sensitivity still require review.

## Hindi

**Source (15 words):** सरकार ने सोमवार को दिल्ली में छात्रों के लिए दस विद्यालय खोलने की घोषणा की।

**Previously generated summary:** दिल्ली सरकार की ओर से सोमवार को दो बड़े सामाजिक कार्यों की घोषणा की गई, जिनमें 10 नए विद्यालय खोलना और जून तक 30,000 भर्तियां करना शामिल है।

| Atomic claim | Entailment | Contradiction | Neutral | Final label |
|---|---:|---:|---:|---|
| दिल्ली सरकार ने सोमवार को बड़े सामाजिक कार्यों की घोषणा की। | 19.29% | 0.06% | 80.65% | unsupported |
| दिल्ली सरकार द्वारा घोषित कार्य प्रचलित समय में दो बड़े सामाजिक कार्यों पर केंद्रित हैं। | 0.12% | 0.07% | 99.81% | unsupported |
| दिल्ली सरकार ने 10 नए विद्यालय खोलने की घोषणा की है। | 99.92% | 0.05% | 0.03% | supported |
| दिल्ली सरकार ने जून तक 30,000 भर्तियां करने की घोषणा की है। | 0.10% | 67.13% | 32.77% | uncertain |

**Checks requiring review:**

- दिल्ली सरकार द्वारा घोषित कार्य प्रचलित समय में दो बड़े सामाजिक कार्यों पर केंद्रित हैं। — numbers: mismatch.
- दिल्ली सरकार ने जून तक 30,000 भर्तियां करने की घोषणा की है। — numbers: mismatch, dates: missing.

The complete evidence passages, page references, similarity scores, NLI scores, summary quotes, and check details are in [live-scores.json](live-scores.json).

## English

**Source (15 words):** The government announced ten new schools for students in Delhi on Monday during its meeting.

**Previously generated summary:** Government announced that ten new schools will be established in Delhi for students.

| Atomic claim | Entailment | Contradiction | Neutral | Final label |
|---|---:|---:|---:|---|
| The Government announced that ten new schools will be established in Delhi for students. | 99.95% | 0.03% | 0.03% | uncertain |

**Checks requiring review:**

- The Government announced that ten new schools will be established in Delhi for students. — temporal_relationships: review.

The complete evidence passages, page references, similarity scores, NLI scores, summary quotes, and check details are in [live-scores.json](live-scores.json).

## Hinglish

**Source (15 words):** Government ne Monday ko Delhi mein students ke liye das schools kholne ka announcement kiya.

**Previously generated summary:** Government ne Monday ko Delhi mein students ke liye saat schools kholne ka announcement kiya.

| Atomic claim | Entailment | Contradiction | Neutral | Final label |
|---|---:|---:|---:|---|
| Government ne Monday ko announcement kiya. | 99.95% | 0.03% | 0.02% | supported |
| Announcement ki jagah Delhi thi. | 99.89% | 0.05% | 0.06% | uncertain |
| Announcement students ke liye tha. | 99.81% | 0.05% | 0.14% | uncertain |
| Announcement mein saat schools kholne ka tha. | 98.81% | 1.07% | 0.12% | uncertain |

**Checks requiring review:**

- Announcement ki jagah Delhi thi. — temporal_relationships: review.
- Announcement students ke liye tha. — temporal_relationships: review.
- Announcement mein saat schools kholne ka tha. — numbers: mismatch, temporal_relationships: review.

The complete evidence passages, page references, similarity scores, NLI scores, summary quotes, and check details are in [live-scores.json](live-scores.json).

## PDF and tokenizer checks

| Check | Result |
|---|---|
| Three-page multilingual PDF upload | HTTP 200; all three pages extracted |
| Extracted Unicode source text | Exact match with fixture input |
| Word/text token count | 45 words and 45 text tokens; expected tokens preserved |
| Page references and offsets | Pages 1, 2, 3 retained; each offset slices the exact page text |
| PDF-to-summary upload path | HTTP 200; page metadata preserved |
| Corrupt PDF | HTTP 422, rejected |
| Blank/image-only PDF with no selectable text | HTTP 422; OCR is not included |
| Encrypted PDF | HTTP 422, rejected |
| Long Hindi passage | 3,605 characters → 4 passages; all text preserved; maximum 104 embedding tokens, below 128 |
| Overlong NLI input | HTTP-style 422 error before inference; no silent truncation |

Neural tokenizer counts include special tokens, so they differ from word counts:

| PDF page language | Words | Embedding tokens | XLM-R tokens | Embedding limit |
|---|---:|---:|---:|---:|
| Hindi | 15 | 19 | 19 | 128 |
| English | 15 | 18 | 18 | 128 |
| Hinglish | 15 | 21 | 21 | 128 |

XLM-R’s fast tokenizer matched its native SentencePiece reference on six multilingual/numeric/negation fixtures and all **10 scored premise/claim pairs**, including cross-language verification. A generic Transformers fast-tokenizer warning was unrelated to XLM-R; the application now loads native SentencePiece directly. A fresh model load reproduced the recorded English scores within 0.000001. See [tokenizer-check.json](tokenizer-check.json) and [current-runtime.json](current-runtime.json).

The PDF fixture exercises Unicode extraction and references; it does not establish reliability for every PDF font/layout. No user-supplied real-world PDF was available. Scanned pages require OCR, which is not implemented.

## Cross-language check

The Hindi source was compared with the already extracted English claim using local models only, with **no additional Groq request**. Entailment was **99.67/100**; the final label was Uncertain because of the same conservative temporal review.

## Changes made while checking

- `backend/app/services/claim_verification.py`: oversized passages now prefer whitespace boundaries, preserving words and exact source offsets.
- `backend/app/services/nli_models.py`: use the native XLM-R SentencePiece tokenizer.
- `backend/requirements-nli.txt`: include protobuf for tokenizer/model compatibility.
- `backend/tests/test_claim_verification.py`: word-boundary regression and tokenizer selection checks.
- The existing root `.venv` received missing ML dependencies. Cached model weights are registered for ordinary local-only backend use. The Groq key was not printed or changed.

## Run commands

Use the exact existing-environment and first-time Windows/Linux commands in [FIRST_RUN.md](FIRST_RUN.md). The temporary check servers have been stopped. Normal URLs are frontend http://localhost:3000 and backend http://127.0.0.1:8000.

## Raw artifacts

- [Connection and PDF results](report.json)
- [Real claim scores, evidence, mismatches, runtime versions](live-scores.json)
- [Frontend API-client test output](frontend-tests.log)
- [Tokenizer reference checks](tokenizer-check.json)
- [Current model readiness](current-runtime.json)
