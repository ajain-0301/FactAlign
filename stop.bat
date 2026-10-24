@echo off
setlocal EnableExtensions
cd /d "%~dp0"
where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Windows PowerShell is required. Use Ctrl+C in the server terminals.
  endlocal
  exit /b 1
)
if not exist "backend\scripts\windows_launcher.ps1" (
  echo [ERROR] Missing launcher helper. Use Ctrl+C in the server terminals.
  endlocal
  exit /b 1
)
echo Stopping launcher-owned FactAlign servers for this project...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "backend\scripts\windows_launcher.ps1" Stop
set "RESULT=%ERRORLEVEL%"
echo Manually started servers must be stopped with Ctrl+C in their terminals.
endlocal & exit /b %RESULT%
