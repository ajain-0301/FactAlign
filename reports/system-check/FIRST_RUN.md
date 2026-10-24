# Use the existing project environment

The environment used for this check is `/home/jaina/FactAlign/.venv`.
Do not create a second `backend/.venv` when the root `.venv` already exists.

To start the current Linux workspace after setup:

```bash
cd /home/jaina/FactAlign
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd /home/jaina/FactAlign/frontend
npm run dev
```

# First run on a laptop

These commands assume the project folder is named `FactAlign`. Replace only the example
project location with its actual location. Python 3.12 and Node.js 22 match the versions
used for the local connection check. The full verification workflow runs its embedding
and XLM-R models locally, so the first setup needs substantial downloads and sufficient RAM.

## Windows PowerShell — backend (terminal 1)

Install Python 3.12 and Node.js 22 before opening these terminals.

```powershell
cd "C:\path\to\FactAlign"
if (!(Test-Path .venv\Scripts\python.exe)) { py -3.12 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install "torch>=2.4,<3" --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r backend\requirements-nli.txt
if (!(Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
notepad backend\.env
```

Save these values in `backend/.env` (keep your actual key on the backend only):

```dotenv
GROQ_API_KEY=your_actual_groq_key
GROQ_MODEL=qwen/qwen3.8-27b
PROVIDER_MODE=auto
VERIFICATION_LOCAL_ONLY=true
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

`qwen/qwen3.8-27b` is the model configured in this project at the time of the check.
Use a model your Groq account can access. Keep all the other `.env.example` defaults.
Then cache the ML models and start the server:

```powershell
.\.venv\Scripts\python.exe backend\scripts\cache_verification_models.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

The cache command downloads model weights but does not call Groq. No PowerShell
activation or execution-policy change is needed with these commands.

## Windows PowerShell — frontend (terminal 2)

```powershell
cd "C:\path\to\FactAlign\frontend"
npm.cmd ci
if (!(Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm.cmd run dev
```

`.env.local` should contain `NEXT_PUBLIC_API_URL=http://localhost:8000`.
Open **http://localhost:3000**. API docs: **http://127.0.0.1:8000/docs**.
To check connectivity without spending Groq quota, open a third PowerShell terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Expect `status: ok` and `database: ok`. A configured key is not the same as a verified
Groq connection. **Settings → Test connection** sends a real Groq request. Summarization
in real mode and claim extraction also use quota; merely starting the servers or opening
health/settings does not. Select **Claim-level NLI** when ready to run that workflow.

## Later runs on Windows

Terminal 1:

```powershell
cd "C:\path\to\FactAlign"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd "C:\path\to\FactAlign\frontend"
npm.cmd run dev
```

Stop a server with `Ctrl+C` in its terminal. Do not repeat installation/model caching
unless dependencies or model IDs change. These commands use the root `.venv` directly.

## macOS/Linux equivalent

Terminal 1 (the CPU-specific PyTorch index command above is for Windows/Linux; on macOS
let requirements-nli.txt install the platform-appropriate PyTorch wheel):

```bash
cd /path/to/FactAlign
[ -x .venv/bin/python ] || python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
# Linux only; skip this command on macOS:
.venv/bin/python -m pip install 'torch>=2.4,<3' --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r backend/requirements.txt -r backend/requirements-nli.txt
[ -f backend/.env ] || cp backend/.env.example backend/.env
# Edit backend/.env with your editor; use the values above.
.venv/bin/python backend/scripts/cache_verification_models.py
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
cd /path/to/FactAlign/frontend
npm ci
[ -f .env.local ] || cp .env.example .env.local
npm run dev
```

## Optional tests (no Groq requests)

From the project root on Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

From `frontend`:

```powershell
npm run typecheck
npm test
```

Leave `RUN_LIVE_API_TESTS` unset for ordinary frontend tests. The connection check in
this report explicitly used an isolated demo backend with no key, so its live local
HTTP tests did not use Groq.

PyTorch CPU installation source: [official installation guide](https://pytorch.org/get-started/locally/).
