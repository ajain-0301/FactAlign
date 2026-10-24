# FactAlign

**Factuality-aware summarization for Indic and code-mixed languages**  
CSET 346 — Natural Language Processing · Project assignment PJ_06

FactAlign summarizes Hindi, English and Hindi-English (Hinglish) text with two strategies — **standard** and **factuality-aware** — and then checks every claim of the summary against the source, labelling it **Supported / Contradicted / Unverifiable** with evidence. It records everything in a local database and reports the metrics the assignment asks for (precision, recall, F1, average summary length, compression ratio, inference time, plus ROUGE), including a **Hindi vs Hinglish code-mixing analysis**.

> **Claim-level NLI:** the optional [new workflow](#claim-level-factual-verification) adds atomic extraction, multilingual embeddings, local XLM-R, four-way decisions, and uncalibrated scores.

> **Read this first — what is real and what is demo**
>
> * **Demo mode** (default, no API key): summaries come from a *rule-based extractive* engine (it copies the best-scoring source sentences; it does not write text). Verification is a *rule-based heuristic*. Everything is labelled "Demo" in the UI. Demo numbers describe those baselines, **not an LLM**.
> * **Real AI mode** (needs `GROQ_API_KEY`): summaries are written by Groq-hosted models with the two prompts in `backend/app/services/prompts.py`; verification uses an LLM judge combined with rule checks.
> * **The real-AI path has only been tested with a mocked LLM** (the development environment had no API key). The first time you add a key, use *Settings → Test connection*, then try a short document.
> * The bundled benchmark is **synthetic, author-written and tiny** (9 documents, 36 labelled claims). It is a regression/demo set, **not** a research dataset. See [Known limitations](#known-limitations).

---

## 1. First-time setup and later runs

The project uses **one virtual environment at `FactAlign/.venv`**. Reuse it when it already exists; do not create `backend/.venv`. Python virtual environments and `node_modules` are platform-specific: install them locally rather than copying them between Windows and Linux/macOS.

**Prerequisites:** install [Python](https://www.python.org/downloads/) and [Node.js](https://nodejs.org/), then reopen your terminal. **Python 3.12 and Node.js 22** are the tested versions; the Windows launcher accepts Python 3.11+ and Node.js 18.18+. First-time dependency/model setup needs internet. Local XLM-R weights are large and need sufficient disk space and RAM.

### Windows — first time (recommended launcher)

Open PowerShell in the project folder, or replace the example path below:

```powershell
cd "C:\path\to\FactAlign"
.\start.bat --setup-nli
```

This performs the full setup for claim-level verification and starts both servers:

1. Reuses the root `.venv`, or creates it if absent. An existing non-Windows environment is left untouched and reported as incompatible.
2. Installs/checks `backend/requirements.txt` and preserves existing environment files. Missing `backend/.env` and `frontend/.env.local` are copied from their templates.
3. With **`--setup-nli`**, installs optional ML dependencies and caches the multilingual embedding and XLM-R models. It selects CPU PyTorch when PyTorch is not installed. **Model setup never calls Groq.** Large downloads may take time.
4. Uses `npm ci` with `frontend/package-lock.json` to install frontend dependencies.
5. Checks that ports **8000** and **3000** are free, starts the backend, waits for its health endpoint, starts the frontend, and opens the browser. Next.js may still need time to compile the first page.

For the basic app without local NLI dependencies/model downloads, use **`start.bat`** without the flag. Demo, uploads, history, Groq summaries and the older verification methods do not require local XLM-R.

Configure Groq in **`backend/.env`** when you want real AI mode:

```dotenv
GROQ_API_KEY=your_actual_groq_key
GROQ_MODEL=your_available_groq_model_id
PROVIDER_MODE=auto
VERIFICATION_LOCAL_ONLY=true
```

Replace both placeholders with your own key and an accessible model ID. Keep the other template settings. An existing configured `.env` is never overwritten. If you edit it after startup, run `stop.bat`, then `start.bat` again to reload it. Leaving the key empty keeps Auto in Demo mode.

Open **http://localhost:3000**. Backend health: **http://127.0.0.1:8000/api/health**; API docs: **http://127.0.0.1:8000/docs**. Select **Claim-level NLI** in the Fact Checker or summary verifier when you want local XLM-R verification.

### Windows — every later run

From the project folder:

```powershell
.\start.bat
```

Or double-click `start.bat`. Unchanged dependency fingerprints skip installation, and local models are not downloaded at startup. The first launcher use after a manual installation may check base dependencies and reinstall frontend dependencies once to establish these fingerprints. Changes to base requirements or the npm lockfile trigger their respective setup steps again.

Stop launcher-started servers with:

```powershell
.\stop.bat
```

The launcher helper records each server's parent PID, creation time and project identity under `backend/data/launcher/`. Stop validates those records and closes the corresponding process trees, including uvicorn/npm/Next.js children. It does not kill every Python/Node process or servers belonging to another project copy. It is safe to run when no managed servers are running.

For **manually started servers**, use **Ctrl+C** in each terminal. Also stop servers from an older launcher version manually once before using the updated launcher. If either port is occupied, startup stops with a message rather than starting a duplicate instance. If startup partially fails, inspect its server window and use `stop.bat` before retrying.

To add/reconfigure local NLI after a basic installation, or after optional ML requirements/model IDs change:

```powershell
.\stop.bat
.\start.bat --setup-nli
```

There is no need to repeat `--setup-nli` for ordinary later runs. The batch files use `backend/scripts/windows_launcher.ps1`; keep that helper with the project.

### Windows — manual first-time setup

These commands use the root environment directly and do not require activation or an execution-policy change. Skip creation if the Windows environment already exists.

```powershell
cd "C:\path\to\FactAlign"
if (!(Test-Path .venv\Scripts\python.exe)) { py -3.12 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if (!(Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
notepad backend\.env
```

For the **optional local claim-level NLI workflow**, also run:

```powershell
.\.venv\Scripts\python.exe -m pip install "torch>=2.4,<3" --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-nli.txt
.\.venv\Scripts\python.exe backend\scripts\cache_verification_models.py
```

Start the backend (terminal 1, project root):

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Set up/start the frontend (terminal 2):

```powershell
cd "C:\path\to\FactAlign\frontend"
npm.cmd ci
if (!(Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm.cmd run dev
```

For subsequent manual runs, use only the backend start command and `npm.cmd run dev` in their respective terminals. Stop each with Ctrl+C. `npm.cmd` avoids PowerShell's `npm.ps1` execution-policy issue.

### Linux/macOS — first time and later runs

From the project root, reuse an existing native `.venv`:

```bash
cd /path/to/FactAlign
[ -x .venv/bin/python ] || python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
[ -f backend/.env ] || cp backend/.env.example backend/.env
# Edit backend/.env with your Groq key and accessible model ID if using real mode.
```

Optional local NLI setup (once):

```bash
# Linux CPU-only setup; skip this line on macOS:
.venv/bin/python -m pip install 'torch>=2.4,<3' --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r backend/requirements-nli.txt
.venv/bin/python backend/scripts/cache_verification_models.py
```

Terminal 1 — backend, both first and later runs:

```bash
cd /path/to/FactAlign
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Terminal 2 — frontend first run:

```bash
cd /path/to/FactAlign/frontend
npm ci
[ -f .env.local ] || cp .env.example .env.local
npm run dev
```

For later frontend runs, just `cd /path/to/FactAlign/frontend` and `npm run dev`. Stop both servers with Ctrl+C. The `.bat` launchers are for Windows.

### Connection checks and API quota

Check the backend without consuming Groq quota:

```powershell
# Windows PowerShell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

```bash
# Linux/macOS
curl http://127.0.0.1:8000/api/health
```

Expect `status: ok` and `database: ok`. The frontend normally sends `/api` requests through Next.js, which proxies to `BACKEND_API_URL=http://127.0.0.1:8000` from `frontend/.env.local`. `NEXT_PUBLIC_API_URL` is an optional direct-backend override and requires matching backend CORS origins. Keep API keys out of frontend environment files.

**Starting/stopping servers, reading health/settings, and downloading local models do not call Groq.** Real summarization, LLM/Hybrid verification, claim extraction and **Settings → Test connection** consume quota. The launcher never tests the Groq connection automatically. A configured key alone does not prove it is valid.

| Feature | Internet | Groq key | Local model download |
|---|---|---|---|
| First dependency installation | yes | no | no |
| Demo summaries, rule verification, history and charts | no | no | no |
| Real summaries and LLM/Hybrid verification | yes | yes | no |
| PDF/DOCX extraction | no | no | no |
| Local NLI setup | yes, initially | no | yes, once per model/cache |
| Claim-level verification | yes for Groq claim extraction | yes | cached embeddings/XLM-R used locally |

`VERIFICATION_LOCAL_ONLY=true` prevents automatic model downloads during verification. Missing local models produce a setup error; use the explicit model-cache step above.

---

## 2. Features

| Page | What it does |
|---|---|
| **New Summary** | Large input (word/char counts), Hindi/English/Hinglish/auto language, Short/Medium/Long, **Standard / Factuality-aware / Compare both** (side-by-side results from two real backend calls, stacked on small screens), output-language choice, optional title and reference summary, sample documents, TXT/MD/PDF/DOCX upload with size/type validation. Output: summary, strategy, mode, detected language, inference time, word counts, compression, CMI, key facts, entities, dates, numbers, potentially unsupported claims, evidence passages, **Copy / Download TXT / Save to history / Run verification**. |
| **Overview** | Database-derived stats: total runs, average summary length / compression / inference time, claim-support rate, language distribution, strategy comparison charts, recent summaries and experiments. Designed empty state when there is no data (nothing fabricated). |
| **Fact Checker** | Paste any source + any summary; claim-by-claim verdict, evidence quote, explanation, rule checks, filter by status. Examples with planted errors in en/hi/Hinglish. |
| **Experiments** | Create (React Hook Form + Zod) → run → store config + results; choose language/strategies/length/model; built-in benchmark or your own documents; search and filter; detail view; select 2–4 to compare (table + chart); delete. |
| **Evaluation** | Filters (language, strategy, source, demo/real); metric tables and charts; **labelled benchmark** with verifier precision/recall/F1 + confusion matrix; **code-mixing analysis** (Hinglish − Hindi on parallel documents); formulas; CSV/JSON export. |
| **History** | Search; filter by date, language, strategy; detail view (source, summary, verification, ROUGE); delete with confirmation; CSV/JSON export. |
| **Settings** | Provider status (key configured? connection verified?), provider mode, model, defaults (strategy, length, languages, verifier, auto-save), setup steps, limits. |

Design: warm cream / charcoal / terracotta palette, serif headings, light + dark theme, collapsible sidebar, mobile drawer, skeleton loaders, keyboard focus rings and skip link. The logo is original.

---

## 3. Architecture

```
FactAlign/
├── start.bat / stop.bat           Windows launcher
├── sample_data/benchmark.json     synthetic 3-topic × (hi, hinglish, en) set + labelled claims (+ generator script)
├── backend/                       FastAPI · SQLAlchemy · SQLite
│   ├── app/
│   │   ├── main.py                app factory, CORS, error handlers
│   │   ├── api/                   routers: health, summarize, verify, history, experiments, evaluation, settings
│   │   ├── core/                  config (env), db (engine/session), errors
│   │   ├── models/                Run, Experiment, EvaluationRun, AppSetting
│   │   ├── schemas/               Pydantic request models + validation
│   │   ├── repositories/          DB access (runs, experiments, settings, evaluation runs)
│   │   └── services/
│   │       ├── text.py            tokenising, sentence split, numbers/dates/entities (Hindi-aware)
│   │       ├── language.py        language ID + Code-Mixing Index
│   │       ├── prompts.py         standard + factuality-aware + verifier prompts
│   │       ├── providers.py       LLM abstraction (Groq) + connection state
│   │       ├── summarizer.py      demo extractive engine, LLM engine, chunking/merge
│   │       ├── verification.py    claim split → retrieval → rule/LLM/hybrid judgement
│   │       ├── metrics.py         ROUGE, P/R/F1, compression, fact metrics, aggregation
│   │       ├── evaluation.py      metrics overview, labelled benchmark, exports
│   │       └── experiments.py     experiment runner
│   └── tests/                     65 pytest tests (mocked LLM; no paid calls)
└── frontend/                      Next.js 15 (App Router) · TypeScript · Tailwind · Recharts · Lucide
    ├── app/                       pages: /, /overview, /fact-checker, /experiments, /evaluation, /history, /settings
    ├── components/ui/             shadcn-style primitives (Radix + cva) written by hand
    ├── components/features/       summary card, verification view, charts, compare table
    ├── lib/                       typed API client, types, utils
    └── tests/                     vitest: utils + live API-contract tests
```

*shadcn/ui note:* the shadcn CLI could not be used offline, so the primitives follow shadcn's pattern (Radix + class-variance-authority + Tailwind) but are hand-written.

### Summarization
* **Standard** and **factuality-aware** are separate prompts (`prompts.py`). The factuality prompt requires: only source-supported facts; exact names/dates/numbers/relations; preserved negation and uncertainty; correct code-mixed handling; omit rather than guess; no invented details. By default the output keeps the source language and code-switching style; the user can request Hindi / English / Hinglish output.
* **Long documents** (> `CHUNK_CHARS`, default 6000): split on sentence boundaries (oversized sentences are hard-split — content is never dropped), each chunk summarized, then the partial summaries are merged with a dedicated merge prompt. Covered by a test that checks that text from the start, middle and end reaches the model.
* **Demo engine**: extractive. *Standard* ranks sentences by TF-IDF-style centrality with a lead bonus. *Factuality-aware* additionally rewards fact density (dates, numbers, entities) and penalises redundancy (MMR-like). It cannot translate (the UI says so).

### Factuality verification
1. Split the summary into claims (sentences, `;`).
2. Retrieve the best source passage (IDF-weighted token containment with light prefix stemming; single sentences and 2-sentence windows).
3. Judge:
   * **rule** — flags changed **numbers** (with unit scaling: `1.5 crore` = `15 million`; Devanagari digits = ASCII), changed **dates** (day/month/year, English and Hindi month names), **entity substitution**, **negation flips** (English + Hindi/Hinglish cues), and low overlap → *Unverifiable*.
   * **llm** — The Groq-hosted model judges each claim against the source and must quote evidence; quotes that are not literally in the source are discarded (`evidence_grounded: false`).
   * **hybrid** — LLM verdict, but a rule check may **downgrade** "supported" when a claim's number/date exists nowhere in the source.
4. Output per claim: `claim, status, evidence, explanation, checks, evidence_score`; `confidence` is **always `null`** because neither method yields a calibrated probability (`evidence_score` is a lexical match, not a probability). If evidence is insufficient the status is *Unverifiable*, never a guess.

Automatic verification is an estimate, not a guarantee (the UI repeats this wherever scores appear).

### Metrics (documented formulas)
| Metric | Definition | Needs |
|---|---|---|
| Compression ratio | `CR = summary_words / source_words` (share kept; lower = shorter). Factor = `1/CR` | — |
| Average summary length | mean word tokens of summaries | — |
| Inference time | wall-clock ms of the summarization call (network included in real mode; verification excluded) | — |
| Claim-support rate | `supported_claims / total_claims` over verified summaries | verification (automatic estimate) |
| Precision / Recall / F1 | `P=TP/(TP+FP)`, `R=TP/(TP+FN)`, `F1=2PR/(P+R)`. Reported per class and for the binary "unsupported detection" (positive = contradicted or unverifiable) | **labelled claims** (benchmark) |
| ROUGE-1/2/L F1 | unicode tokens, no stemming | **reference summary** |
| Fact precision (proxy) | share of summary numbers/dates/entities that occur in the source | — (proxy, not ground truth) |
| Fact recall vs reference | share of reference facts present in the summary | reference summary |
| Lexical similarity | cosine of term-frequency vectors — **not** embedding-based semantic similarity | — |
| CMI | `100·(1 − max(n_hi, n_en)/(n_hi+n_en))`; 0 = monolingual | — |

P/R/F1 are **never estimated without labels**; when labels/references are absent the UI shows "n/a / no references". The Evaluation page separates stored-run metrics from the labelled benchmark.

### Code-mixing analysis (assignment requirement)
The benchmark has three topics, each as **Hindi (Devanagari), Hinglish, English** with the same facts. *Run benchmark* computes per language and strategy: ROUGE, fact precision, claim support, compression, CMI, and the **Hinglish − Hindi difference per pair** (`code_mixing_gap`), plus verifier accuracy / macro-F1 by language. With 3 pairs this is illustrative, not statistically meaningful.

### Database
SQLite file at `backend/data/FactAlign.db` (created automatically). Tables: `runs` (source, summary, languages, model, strategy, timings, metrics, analysis, verification JSON), `experiments` (config + results), `evaluation_runs`, `app_settings`. The layer uses SQLAlchemy and generic `JSON` columns, so other databases should work via `DATABASE_URL` — **PostgreSQL has not been tested**.

---

## 4. API reference (base URL `http://localhost:8000`)

Interactive docs: `/docs`. Errors are `{"detail": "..."}` (422 validation, 413 too large, 415 bad file type, 404, 502/503/504 provider problems).

| Method & path | Purpose |
|---|---|
| `GET /api/health` | Liveness, DB status, effective mode (does **not** claim the provider is connected) |
| `GET /api/samples` | Sample documents and the assignment's example sentences |
| `POST /api/summarize` | `{text, title?, language, output_language, length, strategy, reference_summary?, save?}` → run |
| `POST /api/summarize/compare` | Runs both strategies; `{compare_id, results:[standard, factuality]}`. If either fails nothing is stored |
| `POST /api/extract` | Multipart upload (`.txt .md .pdf .docx`) → `{text, chars, words}` |
| `POST /api/verify` | `{source, summary, method: auto\|rule\|llm\|hybrid, run_id?}` → claims + metrics (stored on the run if `run_id`) |
| `GET /api/history` | `q, language, strategy, date_from, date_to, limit, offset` |
| `GET /api/history/export` | `format=csv\|json` + same filters |
| `GET /api/history/{id}` · `DELETE` · `POST /{id}/save` | Detail (source, summary, verification) / delete / mark saved |
| `POST /api/experiments` · `GET /api/experiments` · `GET/DELETE /api/experiments/{id}` | Create+run, list (`q, language, strategy, status`), detail, delete |
| `GET /api/evaluation/metrics` | `language, strategy, experiment_id, scope, mode` → aggregates, series, formulas, latest benchmark |
| `POST /api/evaluation/run` | Run the labelled benchmark `{strategies, length, language, verify_method}` |
| `GET /api/evaluation/runs` · `GET /api/evaluation/export` | Benchmark history · export `kind=runs\|benchmark`, `format=csv\|json` |
| `GET /api/settings` · `PUT /api/settings` | Status + preferences (never returns the key) · update preferences |
| `POST /api/settings/test-connection` | One tiny real provider call; sets "verified" only on success |

Endpoints added beyond your list: `/samples`, `/extract`, `/history/export`, `/history/{id}/save`, `/experiments/{id}`, `/evaluation/runs`, `/evaluation/export`, `PUT /settings`.

---

## 5. Tests

```powershell
# backend (65 tests, no network, no API key; LLM is mocked)
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q

# frontend
cd ..\frontend
npm run typecheck
npm run lint
npm run build
# live API-contract tests: start the backend first, then
npm test            # skips the integration tests automatically if the backend is down
```

Backend tests cover: health; validation (empty/whitespace/short/oversized/malformed/unknown enum); strategy selection and prompt content; demo Hindi / English / Hinglish; Devanagari digits; comparison (including no leftovers when one call fails); chunking without content loss; **changed numbers, changed dates, negation flips, entity substitution, unsupported claims**, Hindi and code-mixed verification; LLM and hybrid verification with a mocked judge (including malformed JSON and ungrounded evidence); history persistence/filter/export/delete/auto-save; uploads (txt, docx, type and size limits); metric formulas (ROUGE, P/R/F1, compression, confusion matrix); evaluation and experiment lifecycles; missing credentials; provider failures; connection-verified state; secret non-exposure.

---

## 6. Environment variables

**`backend/.env`** (template with comments: `backend/.env.example`)

| Variable | Default | Meaning |
|---|---|---|
| `GROQ_API_KEY` | *(empty)* | Empty = demo mode |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Default model (changeable in Settings) |
| `PROVIDER_MODE` | `auto` | `auto` / `demo` / `real` |
| `DATABASE_URL` | SQLite in `backend/data/` | Any SQLAlchemy URL |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Allowed browser origins |
| `LLM_TIMEOUT_SECONDS` | `90` | Per model request |
| `MAX_INPUT_CHARS` / `MAX_UPLOAD_MB` | `60000` / `5` | Input limits |
| `CHUNK_CHARS` | `6000` | Chunking threshold |

**`frontend/.env.local`**: `BACKEND_API_URL` (default `http://127.0.0.1:8000`) configures the Next.js `/api` proxy. Optionally set `NEXT_PUBLIC_API_URL` to call a public backend directly (requires CORS). Never put API keys here.

---

## 7. Deployment notes

* **There is no authentication.** Anyone who can reach the API can spend your API quota and read stored documents. Put it behind a login / VPN / reverse-proxy auth before exposing it publicly.
* Backend: `uvicorn app.main:app --host 0.0.0.0 --port 8000` behind a reverse proxy (HTTPS). Set `CORS_ORIGINS` to the exact frontend origin. Persist the `data/` folder (or use PostgreSQL via `DATABASE_URL` + `psycopg`; untested here).
* Frontend: set `BACKEND_API_URL` to the backend URL **before** `npm run build`, then `npm start` (or deploy to any Next.js host).
* Experiments and benchmark runs are synchronous HTTP requests; very large real-AI runs may hit proxy timeouts (a job queue would be the next step).

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| Red "Cannot reach the backend" banner | Backend window not running / crashed. Run `start.bat` or Option B; check <http://localhost:8000/api/health>. |
| `python` not found / old version | Install Python 3.11+ and tick *Add to PATH*; reopen the terminal. |
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope Process Bypass` then activate again. |
| Port 8000 or 3000 already in use | Close the other program, or `uvicorn ... --port 8001` and set `NEXT_PUBLIC_API_URL=http://localhost:8001` (+ restart frontend). |
| Real mode errors: "authentication failed" | Wrong/expired key in `backend\.env`; restart backend; re-run *Test connection*. |
| "Real AI mode is selected but GROQ_API_KEY is not configured" | Add the key, or set Provider mode to Auto/Demo in Settings. |
| `Model '…' was not found` | Pick a model your key can access in Settings, or set `GROQ_MODEL`. |
| Hindi shows as boxes | Use a current Windows/Edge/Chrome; fonts "Nirmala UI"/"Noto Sans Devanagari" are used. |
| CSV shows garbled Hindi in Excel | Use *Data → From Text/CSV* with UTF-8 (files already include a BOM, which normally works). |
| Reset all data | Stop the backend and delete `backend\data\FactAlign.db`. |
| Reinstall backend dependencies | Delete `.venv\.factalign-base.sha256` and run `start.bat`. For optional ML dependencies, use `start.bat --setup-nli`. |

---

## 9. Known limitations

* **Real-AI path untested against the live API** (no key during development); only mocked-LLM tests ran. Model IDs are configurable.
* **No browser/UI click-through was run** in the development environment; frontend verification = type-check, lint, production build, and API-contract tests of the real client against the live backend. Visual polish, dark mode and mobile layouts were not inspected on real devices.
* **`start.bat` was not executed on Windows** (developed on Linux). It uses standard commands; please report any issue.
* **Benchmark is synthetic and tiny** (9 docs / 36 claims, written by the project author, not independently annotated). The rule verifier was developed alongside these examples, so its 100 % score is a regression check, **not** evidence of general accuracy. In demo mode claim support is ~100 % by construction (extractive summaries copy source sentences).
* **Rule-based verification** cannot judge paraphrases, implicit reasoning, spelled-out numbers ("five"), or entities that are not capitalised Latin names / in the small Hindi gazetteer. LLM verification can also be wrong. Neither provides calibrated confidence.
* Entity detection for Devanagari names is heuristic (gazetteer + honorific patterns).
* Language ID is script + small romanised-Hindi lexicon (Hindi / English / Hinglish only; no other Indic languages). The assignment allows any two languages; this project uses Hindi and English (+ code-mixed).
* No embedding/NLI models are included (keeps installation light); "lexical similarity" is not semantic similarity.
* Scanned PDFs (images) are not supported (no OCR). No authentication, no background job queue.

## 10. Assignment deliverables

| Deliverable | Status |
|---|---|
| Source code (GitHub) | **This repository.** `.gitignore` excludes secrets, `node_modules`, venv and the database. |
| Research paper (IEEE, Word + PDF) | **Not included** — not part of this code build. |
| Presentation slides | **Not included.** |

For the paper, run the benchmark in Real AI mode, add your own held-out annotated data, and export CSV/JSON from the Evaluation page.

Groq requests are not retried automatically, to avoid extra requests against API limits.
Starting the backend and reading settings do not call Groq. The **Test connection**
button sends a real request and uses quota. Backend tests block live Groq clients
and use mocks instead.

## Claim-level factual verification

Select **Claim-level NLI** in the Fact Checker or a generated summary's verifier selector.
You can also choose it as the default verifier in Settings. Existing Auto, Rule, LLM,
and Hybrid methods retain their behavior; Auto still resolves to Hybrid in real mode.
The new method supports Hindi, English, Hinglish, and source/summary pairs in different
languages. Accuracy on these inputs, particularly romanized Hinglish, needs held-out
human-labelled evaluation; support is not a claim of measured accuracy.

Install the optional local model dependencies and explicitly cache the models once:

On Windows, use `start.bat --setup-nli` from the project root (stop existing servers first).
For a manually managed Linux/macOS installation, use the root environment:

```bash
cd /path/to/FactAlign
.venv/bin/python -m pip install -r backend/requirements.txt -r backend/requirements-nli.txt
.venv/bin/python backend/scripts/cache_verification_models.py
```

The cache command downloads large model files from Hugging Face and loads them locally;
provide sufficient disk space and memory for XLM-R large. It never calls Groq. Restart
the backend afterward. Model loading is lazy; ordinary demo/summarization startup is
unchanged. `VERIFICATION_LOCAL_ONLY=true` is the default, so missing models return HTTP
503 before a Groq extraction request is sent. Model IDs and decision thresholds are
configurable in `.env` (see `.env.example`).

The pipeline is:

1. **Atomic extraction:** one Groq request per summary, with automatic retries disabled.
   Each claim has an exact `summary_quote`. The prompt preserves names, quantities,
   dates, negation, tense, and modality. Malformed output or missing quotes fails
   explicitly. Quote validation checks provenance, not whether the LLM split every
   claim correctly. The UI asks before explicitly starting this method.
2. **Retrieval:** sentence passages retain exact source text and character offsets.
   Passages exceeding the embedding tokenizer budget are split without dropping text.
   Multilingual embeddings retrieve up to three passages per claim. Their cosine
   similarity is used **only for retrieval**, never as proof of factual support.
3. **NLI:** XLM-R processes each passage as the premise and the claim as the hypothesis.
   Softmax scores use the model's declared label mapping. Overlong NLI pairs fail
   instead of silently truncating evidence. Every passage reports entailment,
   contradiction, and neutral scores.
4. **Independent checks:** local rules compare numbers (including common Hindi/English/
   Hinglish number words), dates, scale/unit conversions, entity aliases, negation,
   and temporal cues against each passage. These are conservative checks, not complete
   multilingual entity linking or event reasoning. Unresolved aliases and discrepancies
   are exposed for review; a bag of matching document-wide facts cannot override NLI.
5. **Four decisions:** Supported requires dominant entailment and clear independent
   checks; Contradicted requires dominant NLI contradiction; all-neutral evidence is
   Unsupported; ambiguous evidence, structured discrepancies, or conflicting support
   and contradiction are Uncertain. Missing passages are explicitly Unsupported.
   The default dominant threshold is 0.75 with a 0.15 margin. A contradiction score
   of at least 0.5 emits a warning independently of the support score.
6. **Scores:** claim support score = maximum retrieved-passage entailment × 100.
   This is **uncalibrated**, not a probability of factual correctness. A high score
   can coexist with contradictory evidence. `confidence` remains `null`; calibration
   is intentionally unavailable until fitted and validated using disjoint,
   human-labelled calibration and evaluation data (including language subgroups).
7. **Report:** individual evidence, page/offset references, NLI scores, check mismatches,
   warnings and decisions; document support rate, mean claim score, and contradiction
   count. Conflicting/uncertain claims count in the support-rate denominator.

The default embedding model is
[`paraphrase-multilingual-MiniLM-L12-v2`](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2),
and the NLI model is
[`joeddav/xlm-roberta-large-xnli`](https://huggingface.co/joeddav/xlm-roberta-large-xnli).
Model-card multilingual coverage does not establish Hinglish or cross-language
verification accuracy for this application.

PDF uploads through either the summarizer or Fact Checker preserve physical, one-based
page numbers (including gaps for empty/scanned pages). TXT, Markdown, DOCX and pasted
text have no reliable page number and report `page: null`. Editing uploaded text
clears its page mapping. Saved summaries retain page mappings in their existing JSON
metadata, so no database migration is needed.

The existing endpoint accepts the new method and optional page references:

```json
{
  "source": "दिल्ली में दस विद्यालय खुले।",
  "summary": "Ten schools opened in Delhi.",
  "method": "claim_nli",
  "source_pages": [{"page": 1, "start": 0, "end": 28}]
}
```

Send this JSON to `POST /api/verify`. Offsets use Python Unicode character positions
and must cover the actual source; omit `source_pages` for pasted text. To attach the
result to history, pass `run_id` as before. `POST /api/extract` now additionally returns
`pages`, and summarization accepts `source_pages`. Page references are validated for
coverage and order. The sample offsets above must be adjusted if the source is edited.

Automated tests use fake Groq, embedding, and NLI responses: no Groq quota or model
downloads are required. They validate the pipeline, not pretrained model accuracy.
Frontend live-backend tests now require `RUN_LIVE_API_TESTS=1`; leave it unset for
ordinary offline tests so a running real-mode backend cannot consume quota.
