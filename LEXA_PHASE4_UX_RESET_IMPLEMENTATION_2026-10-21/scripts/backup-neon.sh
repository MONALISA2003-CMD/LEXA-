#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL_UNPOOLED:?DATABASE_URL_UNPOOLED must point to the direct Neon endpoint}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${LEXA_BACKUP_DIR:-$ROOT/backups}"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/lexa-neon-$STAMP.dump"

pg_dump "$DATABASE_URL_UNPOOLED" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file="$OUT"

printf 'LEXA Neon backup created: %s\n' "$OUT"
