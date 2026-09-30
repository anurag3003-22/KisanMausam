#!/usr/bin/env bash
# macOS / Linux one-command start: builds the site once, then serves site + API on http://127.0.0.1:8000
set -e
cd "$(dirname "$0")"
[ -d node_modules ] || npm install
[ -f dist/index.html ] || npm run build
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r server/requirements.txt
echo "Open http://127.0.0.1:8000"
exec .venv/bin/python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
