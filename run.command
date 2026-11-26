#!/usr/bin/env bash
# Works on macOS and Linux. Double-click run.command on macOS, or run:  ./run.sh
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python) || { echo "Python 3.10+ is required: https://www.python.org/downloads/"; exit 1; }
if [ ! -d .venv ]; then
  echo "First run: setting things up, this takes a minute..."
  "$PY" -m venv .venv && .venv/bin/python -m pip install -q --upgrade pip && .venv/bin/python -m pip install -q -r requirements.txt || { echo "Setup failed - check your internet"; exit 1; }
fi
mkdir -p ~/.streamlit
[ -f ~/.streamlit/credentials.toml ] || printf '[general]\nemail = ""\n' > ~/.streamlit/credentials.toml
.venv/bin/python -m streamlit run app.py
