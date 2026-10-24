@echo off
echo Stopping FactAlign server windows...
taskkill /FI "WINDOWTITLE eq FactAlign Backend*" /T /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq FactAlign Frontend*" /T /F >nul 2>nul
echo Done.
