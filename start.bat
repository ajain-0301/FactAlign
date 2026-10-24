@echo off
setlocal EnableExtensions
title FactAlign launcher
cd /d "%~dp0"

echo.
echo ==========================================
echo   FactAlign - local launcher
echo ==========================================
echo.

rem ---------- 1. prerequisites ----------
where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js was not found.
  echo         Install the LTS version from https://nodejs.org , then run start.bat again.
  goto :fail
)
node -e "process.exit(parseInt(process.versions.node,10)>=18?0:1)"
if errorlevel 1 (
  echo [ERROR] Node.js 18 or newer is required. Install the current LTS from https://nodejs.org
  goto :fail
)
where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm was not found. Reinstall Node.js from https://nodejs.org
  goto :fail
)

set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo [ERROR] Python was not found.
  echo         Install Python 3.11 or newer from https://www.python.org/downloads/
  echo         and tick "Add python.exe to PATH" during setup.
  goto :fail
)
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
  echo [ERROR] Python 3.11 or newer is required. Your version:
  %PY% --version
  goto :fail
)

rem ---------- 2. backend setup (never overwrites existing files) ----------
if not exist "backend\.venv\Scripts\python.exe" (
  echo [1/4] Creating Python virtual environment...
  %PY% -m venv backend\.venv
  if errorlevel 1 goto :fail
)
if not exist "backend\.venv\.deps-installed" (
  echo [2/4] Installing backend dependencies (needs internet, first run only)...
  "backend\.venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
  "backend\.venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
  if errorlevel 1 goto :fail
  echo done> "backend\.venv\.deps-installed"
) else (
  echo [2/4] Backend dependencies already installed.
)
if not exist "backend\.env" (
  copy "backend\.env.example" "backend\.env" >nul
  echo       Created backend\.env from the template. Add GROQ_API_KEY there to enable real AI mode.
)

rem ---------- 3. frontend setup ----------
if not exist "frontend\node_modules" (
  echo [3/4] Installing frontend dependencies (needs internet, takes a few minutes, first run only)...
  pushd frontend
  call npm install --no-audit --no-fund
  if errorlevel 1 (
    popd
    goto :fail
  )
  popd
) else (
  echo [3/4] Frontend dependencies already installed.
)
if not exist "frontend\.env.local" copy "frontend\.env.example" "frontend\.env.local" >nul

rem ---------- 4. start both servers in their own windows ----------
echo [4/4] Starting servers...
start "FactAlign Backend" /D "%~dp0backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
start "FactAlign Frontend" /D "%~dp0frontend" cmd /k "npm run dev"

echo.
echo   Backend  : http://localhost:8000   (API docs: http://localhost:8000/docs)
echo   Frontend : http://localhost:3000
echo.
echo   The first page load can take 10-30 seconds while Next.js compiles.
echo   Opening your browser in a few seconds. Close the two server windows to stop FactAlign.
timeout /t 10 /nobreak >nul
start "" "http://localhost:3000"
endlocal
exit /b 0

:fail
echo.
echo Setup did not finish. Read the message above, fix it, and run start.bat again.
pause
endlocal
exit /b 1
