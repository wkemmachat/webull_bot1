#!/usr/bin/env bash
# Start TH Strategy Bot on your Mac:  ./run.sh   (then open http://127.0.0.1:8000)
set -e
cd "$(dirname "$0")"

# Find the newest Python 3.9+ (Homebrew, python.org installer, pyenv, or the Mac's own /usr/bin/python3)
PY=""
for c in python3.13 python3.12 python3.11 python3.10 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3 \
         /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
         "$HOME/.pyenv/shims/python3" python3 /usr/bin/python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.9 or newer is needed."
  echo "  Easiest: run  xcode-select --install  (Apple's command line tools include Python 3.9),"
  echo "  or install Python 3.12 from https://www.python.org/downloads/macos/"
  exit 1
fi

# A .venv made by an older/removed Python is rebuilt
if [ -d .venv ] && ! ./.venv/bin/python -c 'import sys' >/dev/null 2>&1; then rm -rf .venv; fi
if [ ! -d .venv ]; then
  echo "Creating .venv with $("$PY" --version 2>&1) ($PY) …"
  "$PY" -m venv .venv
fi
./.venv/bin/python -m pip install -q --upgrade pip
echo "Installing packages (first time takes a minute) …"
./.venv/bin/python -m pip install -q -r requirements-dev.txt
[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example"; }
mkdir -p data
PORT="${PORT:-8000}"
echo "TH Strategy Bot → http://127.0.0.1:$PORT   (Ctrl+C to stop)"
exec ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --workers 1
