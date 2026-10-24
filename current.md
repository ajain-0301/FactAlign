# FactAlign — current working status

Compiled on **21 October 2026 (IST)** from the completed checks recorded on **20 October 2026**. This is a record of verified behavior, not a claim that the servers are currently running or that every possible input works.

## Environment and overall status

- Existing Python environment: `/home/jaina/FactAlign/.venv` (Python 3.12).
- Frontend: Next.js, tested with Node.js 22.
- Provider: **Groq**, configured model `qwen/qwen3.8-27b`. The backend reads the key from `backend/.env`; it is not included in this report.
- Multilingual embeddings: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- NLI: `joeddav/xlm-roberta-large-xnli`, running locally on CPU with the native XLM-R SentencePiece tokenizer.
- ML dependencies and model weights are installed/cached for the existing environment. A fresh local model load succeeded and reproduced the recorded scores.
- Automated verification: **109 backend tests passed**, **11 frontend tests passed against a local demo backend**, and **TypeScript checking passed**.
- The temporary test servers were stopped after checking. Start the normal application with the commands below.

## Working features and evidence

| Feature | Verified status | Evidence / scope |
|---|---|---|
| Backend startup, health and SQLite | Working | Live HTTP health response: status/database OK; isolated test database |
| Frontend Fact Checker page | Working | HTTP 200 and verification controls rendered |
| Frontend/backend API connection | Working | Six frontend API-client contract tests against a real local backend; CORS and compiled API URL checked |
| Settings and provider status | Working | API contract/regression tests; key is hidden |
| Hindi, English and Hinglish input | Working on checked examples | Three 15-word sources, PDF extraction, and real claim-verification responses |
| Standard and factuality summarization | Working on checked paths | Local demo comparisons, regression tests, and earlier Groq-generated summaries; quality differs by strategy |
| Existing Rule, LLM and Hybrid methods | Preserved | Regression tests; earlier live Hybrid responses are recorded in `reports/language-check.json` |
| Groq atomic claim extraction | Operational | Three approved real extraction requests; exact summary quotes retained |
| Multilingual embedding retrieval | Operational | Up to three passages per claim; real model loaded and relevance scores returned |
| XLM-R NLI verification | Operational | Real entailment, contradiction and neutral scores returned through `/api/verify` |
| Independent structured checks | Operational, heuristic | Numbers, dates, entities/aliases, units, negation and temporal checks; number mismatches detected in the live run |
| Four-way claim classification | Working | Supported / Contradicted / Unsupported / Uncertain logic covered by tests; live examples produced Supported, Unsupported and Uncertain |
| Missing/conflicting evidence | Tested | Automated cases cover absent passages, neutral evidence and conflicting support/contradiction |
| Uncalibrated support scoring | Working | Maximum retrieved-passage entailment × 100; calibrated confidence stays null |
| Document aggregation | Working | Support rate, mean claim score and contradiction count returned |
| Claim/evidence frontend display | Tested | Rendering tests cover scores, page references, mismatches and conflict warnings; no interactive browser automation was performed |
| PDF upload and Unicode extraction | Working on synthetic fixture | Real three-page Hindi/English/Hinglish PDF accepted with exact extracted text |
| PDF page metadata | Working | Page numbers/offsets preserved through extraction and summarization |
| Tokenizer limits and long passages | Working | Real long-Hindi test preserves all text; oversized NLI pairs rejected before inference |
| TXT/DOCX uploads and invalid input | Tested | Backend regression tests cover uploads, file-size limits and validation errors |
| History, comparisons, metrics, evaluation and experiments | Tested | Existing backend tests and live frontend API-client contracts |

“Operational” means the path executed successfully; it does not mean the model's factual decisions are always correct. The detailed scores below show important limitations.

## Start the current installation

Use the existing root environment. No new virtual environment or repeated model download is needed for this workspace.

Backend, terminal 1:

```bash
cd /home/jaina/FactAlign
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Frontend, terminal 2:

```bash
cd /home/jaina/FactAlign/frontend
npm run dev
```

Open **http://localhost:3000**. Backend API docs: **http://127.0.0.1:8000/docs**.

A connectivity check that does not call Groq:

```bash
curl http://127.0.0.1:8000/api/health
```

For a **first-time laptop installation**, including Windows PowerShell and Linux/macOS commands, environment configuration, CPU dependencies and model caching, see [FIRST_RUN.md](reports/system-check/FIRST_RUN.md). That guide preserves an existing root `.venv` when available.

## API usage

- The completed real score report used **exactly 3 approved Groq requests**, with automatic retries disabled.
- No additional Groq calls were made to create this file.
- Starting the servers and reading health/settings do not call Groq.
- Real summarization, claim extraction and the Settings connection-test button consume quota. The new claim-level UI asks before extraction.
- Backend automated tests block live Groq clients. Ordinary frontend tests skip live-backend tests unless explicitly enabled.

## Limits and outstanding quality work

- **Calibrated factual confidence is not available.** The support scores below are uncalibrated NLI scores, not accuracy estimates or probabilities that claims are true.
- The live run exposed overcautious temporal reviews: an accurate English paraphrase was retained as Uncertain despite strong NLI entailment.
- XLM-R gave high entailment to an incorrect Hinglish number. The independent number check caught the mismatch and prevented a Supported label.
- Atomic extraction and structured entity/temporal checks remain imperfect. Summary quotes establish text provenance, not semantic correctness of every extracted claim.
- Cross-language inference was exercised on a Hindi-source/English-claim example; this is not broad multilingual accuracy validation.
- Three short examples are a smoke check, not a held-out, human-labelled benchmark. Calibration and reliable accuracy claims require such data.
- PDF acceptance was tested with a synthetic Unicode fixture, not an uploaded real-world document. Font/layout variations may affect extraction. Scanned PDFs need OCR, which is not implemented; encrypted PDFs are rejected.
- Interactive browser clicks, arbitrary PDFs, production deployment and performance under load were not validated in these checks.

## Fixes included during verification

- Oversized evidence passages prefer whitespace boundaries while retaining exact source offsets.
- XLM-R uses its native SentencePiece tokenizer. All ten scored premise/claim pairs matched the previous fast-tokenizer inputs.
- `protobuf` is declared in the optional ML requirements for tokenizer compatibility.
- Regression tests cover word-boundary preservation and tokenizer selection.

Files changed for these fixes: `backend/app/services/claim_verification.py`, `backend/app/services/nli_models.py`, `backend/requirements-nli.txt`, and `backend/tests/test_claim_verification.py`.

---

# Detailed verification results

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

The complete evidence passages, page references, similarity scores, NLI scores, summary quotes, and check details are in [live-scores.json](reports/system-check/live-scores.json).

## English

**Source (15 words):** The government announced ten new schools for students in Delhi on Monday during its meeting.

**Previously generated summary:** Government announced that ten new schools will be established in Delhi for students.

| Atomic claim | Entailment | Contradiction | Neutral | Final label |
|---|---:|---:|---:|---|
| The Government announced that ten new schools will be established in Delhi for students. | 99.95% | 0.03% | 0.03% | uncertain |

**Checks requiring review:**

- The Government announced that ten new schools will be established in Delhi for students. — temporal_relationships: review.

The complete evidence passages, page references, similarity scores, NLI scores, summary quotes, and check details are in [live-scores.json](reports/system-check/live-scores.json).

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

The complete evidence passages, page references, similarity scores, NLI scores, summary quotes, and check details are in [live-scores.json](reports/system-check/live-scores.json).

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

XLM-R’s fast tokenizer matched its native SentencePiece reference on six multilingual/numeric/negation fixtures and all **10 scored premise/claim pairs**, including cross-language verification. A generic Transformers fast-tokenizer warning was unrelated to XLM-R; the application now loads native SentencePiece directly. A fresh model load reproduced the recorded English scores within 0.000001. See [tokenizer-check.json](reports/system-check/tokenizer-check.json) and [current-runtime.json](reports/system-check/current-runtime.json).

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

Use the exact existing-environment and first-time Windows/Linux commands in [FIRST_RUN.md](reports/system-check/FIRST_RUN.md). The temporary check servers have been stopped. Normal URLs are frontend http://localhost:3000 and backend http://127.0.0.1:8000.

## Raw artifacts

- [Connection and PDF results](reports/system-check/report.json)
- [Real claim scores, evidence, mismatches, runtime versions](reports/system-check/live-scores.json)
- [Frontend API-client test output](reports/system-check/frontend-tests.log)
- [Tokenizer reference checks](reports/system-check/tokenizer-check.json)
- [Current model readiness](reports/system-check/current-runtime.json)

