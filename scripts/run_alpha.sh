#!/usr/bin/env bash
#
# ROLE OS Alpha -- one-command launcher.
#
# Creates/activates a local virtualenv, installs the dashboard's
# dependencies, seeds the Alpha demo data (idempotent -- safe to run every
# time), and starts the dashboard. Visit http://127.0.0.1:8000/ once it
# says "Uvicorn running".
#
# Usage:
#   ./scripts/run_alpha.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export ROLE_OS_DB_PATH="$REPO_ROOT/samples/role_os_sample/00_SYSTEM/role_os.db"
export ROLE_OS_PROJECTS_DB_PATH="$REPO_ROOT/var/role_os_alpha/role_os_projects.db"
export ROLE_OS_ADVISOR_DB_PATH="$REPO_ROOT/var/role_os_alpha/role_os_advisor.db"

if [ ! -d "$REPO_ROOT/.venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$REPO_ROOT/.venv"
fi

# shellcheck disable=SC1091
source "$REPO_ROOT/.venv/bin/activate"

echo "Installing dependencies..."
pip install -q -r "$REPO_ROOT/dashboard/requirements.txt"

echo "Seeding Alpha demo data (skips automatically if already seeded)..."
python3 "$REPO_ROOT/scripts/seed_alpha_demo.py"

echo ""
echo "Starting ROLE OS Alpha at http://127.0.0.1:8000/"
echo ""
cd "$REPO_ROOT/dashboard"
exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
