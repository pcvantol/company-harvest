#!/bin/sh
set -eu
if [ "$#" -lt 2 ]; then printf 'Gebruik: run-preflight.sh VENV RUN_DIR\n' >&2; exit 2; fi
"$1/bin/company-harvest" run preflight --run-dir "$2"

