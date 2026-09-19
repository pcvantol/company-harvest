#!/bin/sh
set -eu
if [ "$#" -lt 1 ]; then printf 'Gebruik: run.sh VENV [ARGUMENTEN...]\n' >&2; exit 2; fi
VENV=$1; shift
"$VENV/bin/company-lookup" "$@"

