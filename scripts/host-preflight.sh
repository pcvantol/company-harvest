#!/bin/sh
set -eu
PYTHON_BIN="${PYTHON_BIN:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { printf 'Python 3.11–3.14 ontbreekt.\n' >&2; exit 2; }
"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if (3,11)<=sys.version_info[:2]<(3,15) else 2)'
printf 'Hostpreflight: Python %s op %s/%s beschikbaar.\n' "$($PYTHON_BIN -c 'import platform; print(platform.python_version())')" "$($PYTHON_BIN -c 'import platform; print(platform.system())')" "$($PYTHON_BIN -c 'import platform; print(platform.machine())')"

