#!/bin/sh
set -eu
if [ "$#" -lt 2 ]; then printf 'Gebruik: install.sh WHEEL VENV [--sha256 HASH] [--offline WHEELHOUSE] [--browser] [--dry-run] [--log FILE]\n' >&2; exit 2; fi
WHEEL=$1; VENV=$2; shift 2
EXPECTED=; WHEELHOUSE=; BROWSER=0; DRY_RUN=0; LOG=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --sha256) EXPECTED=$2; shift 2 ;;
    --offline) WHEELHOUSE=$2; shift 2 ;;
    --browser) BROWSER=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --log) LOG=$2; shift 2 ;;
    *) printf 'Onbekende optie: %s\n' "$1" >&2; exit 2 ;;
  esac
done
[ -f "$WHEEL" ] || { printf 'Wheel ontbreekt: %s\n' "$WHEEL" >&2; exit 3; }
[ -z "$EXPECTED" ] || [ "$(shasum -a 256 "$WHEEL" | awk '{print $1}')" = "$EXPECTED" ] || { printf 'Wheelchecksum wijkt af.\n' >&2; exit 4; }
PYTHON_BIN="${PYTHON_BIN:-python3.14}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { printf 'Python 3.14 ontbreekt.\n' >&2; exit 2; }
"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3,14) else 2)' || { printf 'Python 3.14 is vereist.\n' >&2; exit 2; }
[ -z "$LOG" ] || { mkdir -p "$(dirname "$LOG")"; exec >>"$LOG" 2>&1; }
[ "$DRY_RUN" -eq 0 ] || { printf 'Dry-run geslaagd: wheel, checksum en opties zijn geldig.\n'; exit 0; }
[ ! -e "$VENV" ] || { printf 'Installatiemap bestaat al: %s\n' "$VENV" >&2; exit 3; }
CREATED=0
cleanup() { code=$?; if [ "$code" -ne 0 ] && [ "$CREATED" -eq 1 ]; then rm -rf "$VENV"; fi; exit "$code"; }
trap cleanup EXIT INT TERM
"$PYTHON_BIN" -m venv "$VENV"
CREATED=1
if [ -n "$WHEELHOUSE" ]; then "$VENV/bin/python" -m pip install --no-index --find-links "$WHEELHOUSE" "$WHEEL"; else "$VENV/bin/python" -m pip install "$WHEEL"; fi
if [ "$BROWSER" -eq 1 ]; then "$VENV/bin/python" -m playwright install chromium; fi
"$VENV/bin/company-harvest" --version
trap - EXIT INT TERM
