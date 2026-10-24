@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title FactAlign launcher

set "SETUP_NLI=0"
if not "%~2"=="" goto :usage
if /i "%~1"=="--setup-nli" set "SETUP_NLI=1"
if not "%~1"=="" if /i not "%~1"=="--setup-nli" goto :usage

echo.
echo FactAlign - local launcher
echo Uses the root .venv. Startup does not call Groq.
echo.

where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Windows PowerShell is required by the launcher.
  goto :fail
)
where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Install Node.js 22, then reopen this terminal.
  goto :fail
)
node -e "const [a,b]=process.versions.node.split('.').map(Number);process.exit(a>18 || (a===18 && b>=18)?0:1)"
if errorlevel 1 (
  echo [ERROR] Node.js 18.18 or newer is required. Node.js 22 is tested.
  goto :fail
)
where npm.cmd >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm.cmd is missing. Reinstall Node.js.
  goto :fail
)

if not exist "backend\scripts\windows_launcher.ps1" (
  echo [ERROR] Missing backend\scripts\windows_launcher.ps1.
  goto :fail
)

powershell.exe -NoProfile -Command "$busy=@([Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object { $_.Port -in 8000,3000 }); if ($busy.Count) { Write-Host '[ERROR] Port 8000 or 3000 is already in use. Run stop.bat for this project, or close the application using that port.'; exit 1 }"
if errorlevel 1 goto :fail

rem Reuse the existing root environment; never create backend\.venv.
if exist ".venv\Scripts\python.exe" goto :venv_ready
if exist ".venv\" (
  echo [ERROR] The root .venv has no Windows Python executable.
  echo Virtual environments cannot be copied between Linux/macOS and Windows.
  echo Move that environment aside and create a Windows .venv locally.
  goto :fail
)
set "PY_BOOTSTRAP="
where py >nul 2>nul
if not errorlevel 1 set "PY_BOOTSTRAP=py -3"
if defined PY_BOOTSTRAP goto :create_venv
where python >nul 2>nul
if not errorlevel 1 set "PY_BOOTSTRAP=python"
if not defined PY_BOOTSTRAP (
  echo [ERROR] Install Python 3.12 and enable its PATH option.
  goto :fail
)
:create_venv
%PY_BOOTSTRAP% -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
  echo [ERROR] Python 3.11 or newer is required. Python 3.12 is tested.
  goto :fail
)
echo Creating root .venv...
%PY_BOOTSTRAP% -m venv .venv
if errorlevel 1 goto :fail
:venv_ready
set "PROJECT_PY=%CD%\.venv\Scripts\python.exe"
"%PROJECT_PY%" -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 goto :fail

rem Hash the requirements so changed dependencies trigger setup on a later run.
"%PROJECT_PY%" -c "import hashlib,pathlib,sys; p=pathlib.Path('backend/requirements.txt'); m=pathlib.Path('.venv/.factalign-base.sha256'); sys.exit(0 if m.exists() and m.read_text().strip()==hashlib.sha256(p.read_bytes()).hexdigest() else 1)"
if errorlevel 1 goto :install_base
"%PROJECT_PY%" -c "import fastapi,uvicorn,sqlalchemy,pydantic_settings,groq,pypdf,docx,multipart" >nul 2>nul
if not errorlevel 1 goto :base_ready
:install_base
echo Installing/checking backend dependencies...
"%PROJECT_PY%" -m pip install -r backend\requirements.txt
if errorlevel 1 goto :fail
"%PROJECT_PY%" -c "import hashlib,pathlib; pathlib.Path('.venv/.factalign-base.sha256').write_text(hashlib.sha256(pathlib.Path('backend/requirements.txt').read_bytes()).hexdigest())"
if errorlevel 1 goto :fail
:base_ready
if exist "backend\.env" goto :backend_env_ready
copy "backend\.env.example" "backend\.env" >nul
if errorlevel 1 goto :fail
echo Created backend\.env. Add your Groq key/model there when ready.
:backend_env_ready

if "%SETUP_NLI%"=="0" goto :frontend_setup
echo Installing/checking optional local verification dependencies...
"%PROJECT_PY%" -c "import torch" >nul 2>nul
if not errorlevel 1 goto :install_nli
"%PROJECT_PY%" -m pip install "torch>=2.4,<3" --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto :fail
:install_nli
"%PROJECT_PY%" -m pip install -r backend\requirements-nli.txt
if errorlevel 1 goto :fail
echo Caching multilingual embedding and XLM-R models. Large downloads may take time.
echo This setup step never calls Groq.
"%PROJECT_PY%" backend\scripts\cache_verification_models.py
if errorlevel 1 goto :fail

:frontend_setup
rem npm ci uses the checked-in lockfile. Reinstall only when it changes or tools are missing.
"%PROJECT_PY%" -c "import hashlib,pathlib,sys; p=pathlib.Path('frontend/package-lock.json'); m=pathlib.Path('frontend/node_modules/.factalign-lock.sha256'); sys.exit(0 if m.exists() and pathlib.Path('frontend/node_modules/next/dist/bin/next').exists() and m.read_text().strip()==hashlib.sha256(p.read_bytes()).hexdigest() else 1)"
if not errorlevel 1 goto :frontend_ready
echo Installing frontend dependencies from package-lock.json...
pushd frontend
call npm.cmd ci --no-audit --no-fund
if errorlevel 1 (
  popd
  goto :fail
)
popd
"%PROJECT_PY%" -c "import hashlib,pathlib; pathlib.Path('frontend/node_modules/.factalign-lock.sha256').write_text(hashlib.sha256(pathlib.Path('frontend/package-lock.json').read_bytes()).hexdigest())"
if errorlevel 1 goto :fail
:frontend_ready
if exist "frontend\.env.local" goto :launch
copy "frontend\.env.example" "frontend\.env.local" >nul
if errorlevel 1 goto :fail

:launch
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "backend\scripts\windows_launcher.ps1" StartBackend
if errorlevel 1 goto :launch_failed
rem Check health only; never send a paid connection-test or model request.
powershell.exe -NoProfile -Command "$ready=$false; for ($i=0; $i -lt 30; $i++) { try { $r=Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; if ($r.status -eq 'ok') { $ready=$true; break } } catch {}; Start-Sleep -Seconds 1 }; if (-not $ready) { Write-Host '[ERROR] Backend did not become healthy. Read its server window.'; exit 1 }"
if errorlevel 1 goto :launch_failed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "backend\scripts\windows_launcher.ps1" StartFrontend
if errorlevel 1 goto :launch_failed
echo.
echo Backend:  http://127.0.0.1:8000
echo API docs: http://127.0.0.1:8000/docs
echo Frontend: http://localhost:3000
echo The frontend may need time to compile on its first page load.
echo Use stop.bat from this project folder to stop these server windows.
start "" "http://localhost:3000"
endlocal
exit /b 0

:launch_failed
echo Run stop.bat to close any partially started server windows.
goto :fail
:usage
echo Usage: start.bat [--setup-nli]
echo   start.bat               Start; install base dependencies on first use.
echo   start.bat --setup-nli   Also install/cache local claim-level verification models.
endlocal
exit /b 2
:fail
echo.
echo Startup did not finish. Fix the error above and run start.bat again.
pause
endlocal
exit /b 1
