#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB="$ROOT/apps/web"

if [[ ! -f "$WEB/package.json" || ! -d "$WEB/app" ]]; then
  echo "Error: expected the LEXA web package under apps/web; refusing cleanup." >&2
  exit 1
fi

# These routes are documented as internal technical infrastructure, not user-facing UI.
# Their backend/database functionality is not removed by this script.
for route in business-engine kernel; do
  path="$WEB/app/$route"
  if [[ -e "$path" || -L "$path" ]]; then
    rm -rf -- "$path"
    echo "Removed obsolete frontend route: apps/web/app/$route"
  fi
done

# TypeScript build info is generated cache and should not be version-controlled.
if [[ -f "$WEB/tsconfig.tsbuildinfo" ]]; then
  rm -f -- "$WEB/tsconfig.tsbuildinfo"
  echo "Removed generated TypeScript cache: apps/web/tsconfig.tsbuildinfo"
fi

echo "Frontend source cleanup complete. No backend routes, migrations, or business data were changed."
