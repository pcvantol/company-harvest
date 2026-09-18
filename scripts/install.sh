#!/bin/sh
set -eu
if [ "$#" -lt 2 ]; then printf 'Gebruik: install.sh WHEEL VENV [--offline WHEELHOUSE] [--browser]\n' >&2; exit 2; fi
WHEEL=$1; VENV=$2; shift 2
[ ! -e "$VENV" ] || { printf 'Installatiemap bestaat al: %s\n' "$VENV" >&2; exit 3; }
python3 -m venv "$VENV"
if [ "${1:-}" = "--offline" ]; then WHEELHOUSE=$2; shift 2; "$VENV/bin/python" -m pip install --no-index --find-links "$WHEELHOUSE" "$WHEEL"; else "$VENV/bin/python" -m pip install "$WHEEL"; fi
if [ "${1:-}" = "--browser" ]; then "$VENV/bin/python" -m playwright install chromium; fi
"$VENV/bin/company-harvest" --version

