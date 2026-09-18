#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CURRENT=$(git -C "$ROOT" config --local --get core.hooksPath || true)
if [ -n "$CURRENT" ] && [ "$CURRENT" != ".githooks" ]; then
  printf 'Bestaande hooksPath blijft behouden: %s\n' "$CURRENT" >&2
  exit 3
fi
git -C "$ROOT" config --local core.hooksPath .githooks
printf 'Lokale hooks geactiveerd zonder bestaande custom hooks te overschrijven.\n'
