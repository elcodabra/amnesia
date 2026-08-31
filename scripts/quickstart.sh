#!/usr/bin/env bash
# One command from a fresh clone to a running Amnesia.
#
# Judges have limited patience and many submissions. This does every setup step
# in order, explains what it is doing, and refuses to continue quietly when
# something is missing.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

echo "==> Amnesia quickstart"
echo

# ------------------------------------------------------------------ python
if [ ! -d .venv ]; then
  echo "==> Creating virtualenv"
  python3 -m venv .venv
fi
echo "==> Installing dependencies"
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

# --------------------------------------------------------------------- env
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

if [ -z "${GOOGLE_API_KEY:-}" ] && [ "${GOOGLE_GENAI_USE_VERTEXAI:-}" != "true" ]; then
  echo
  echo "    No GOOGLE_API_KEY set."
  echo "    Amnesia will still run: ingestion, measured facts, stuck detection"
  echo "    and the card work with no model at all. For distillation and chat,"
  echo "    get a key at https://aistudio.google.com/apikey and:"
  echo
  echo "        echo 'GOOGLE_API_KEY=your_key' >> .env"
  echo
fi

# ------------------------------------------------------------------- check
echo "==> Checking what it can read on this machine"
.venv/bin/python scripts/demo_check.py || true

echo
echo "==> Starting on http://localhost:8080"
echo "    Click 'Run background pass' to watch it learn from your own sessions."
echo
exec .venv/bin/python -m uvicorn amnesia.web.app:app --host 0.0.0.0 --port "${PORT:-8080}"
