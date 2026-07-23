@echo off
REM ROLE OS Alpha -- one-command launcher (Windows).
REM
REM Creates/activates a local virtual environment, installs the dashboard's
REM dependencies, seeds the Alpha demo data (idempotent -- safe to run every
REM time), and starts the dashboard. Visit http://127.0.0.1:8000/ once it
REM says "Uvicorn running".
REM
REM Usage:
REM   scripts\run_alpha.bat

setlocal
set "REPO_ROOT=%~dp0.."
cd /d "%REPO_ROOT%"

set "ROLE_OS_DB_PATH=%REPO_ROOT%\samples\role_os_sample\00_SYSTEM\role_os.db"
set "ROLE_OS_PROJECTS_DB_PATH=%REPO_ROOT%\var\role_os_alpha\role_os_projects.db"
set "ROLE_OS_ADVISOR_DB_PATH=%REPO_ROOT%\var\role_os_alpha\role_os_advisor.db"

if not exist "%REPO_ROOT%\.venv" (
  echo Creating virtual environment...
  python -m venv "%REPO_ROOT%\.venv"
)

call "%REPO_ROOT%\.venv\Scripts\activate.bat"

echo Installing dependencies...
pip install -q -r "%REPO_ROOT%\dashboard\requirements.txt"

echo Seeding Alpha demo data (skips automatically if already seeded)...
python "%REPO_ROOT%\scripts\seed_alpha_demo.py"

echo.
echo Starting ROLE OS Alpha at http://127.0.0.1:8000/
echo.
cd /d "%REPO_ROOT%\dashboard"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
