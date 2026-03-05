#!/usr/bin/env bash
set -euo pipefail

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "pg_dump не найден. Установите PostgreSQL client tools."
  exit 1
fi

DB_URL="${DATABASE_URL:-${1:-}}"
if [[ -z "$DB_URL" ]]; then
  echo "Usage: DATABASE_URL=postgresql://... [BACKUP_DIR=./backups] $0"
  exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
outfile="${BACKUP_DIR}/social_wishlist_${timestamp}.dump"

pg_dump \
  --format=custom \
  --compress=9 \
  --no-owner \
  --no-privileges \
  --file "$outfile" \
  "$DB_URL"

echo "Backup created: $outfile"
