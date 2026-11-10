@echo off
REM Run the production Waitress process on loopback behind a TLS reverse proxy.
setlocal
cd /d "%~dp0.."

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
if "%ITAM_PORT%"=="" set ITAM_PORT=8000
set ITAM_BIND=127.0.0.1

if not exist ".env" (
  echo [ITAM] ERROR: .env is missing. Copy deploy\.env.example to .env and configure it.
  exit /b 1
)

set PYTHON=python
if exist ".venv\Scripts\python.exe" set PYTHON=.venv\Scripts\python.exe

%PYTHON% -c "import waitress" >nul 2>&1
if errorlevel 1 (
  echo [ITAM] ERROR: Waitress is required. Install requirements.txt; refusing to run Django development server.
  exit /b 1
)

echo [ITAM] Running Django checks...
%PYTHON% manage.py check
if errorlevel 1 exit /b 1

echo [ITAM] Starting Waitress on %ITAM_BIND%:%ITAM_PORT% ...
%PYTHON% -m waitress --listen=%ITAM_BIND%:%ITAM_PORT% --threads=8 --channel-timeout=120 config.wsgi:application
endlocal
