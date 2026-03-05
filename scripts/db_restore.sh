#!/usr/bin/env bash
set -euo pipefail

if ! command -v pg_restore >/dev/null 2>&1; then
  echo "pg_restore не найден. Установите PostgreSQL client tools."
  exit 1
fi

DB_URL="${DATABASE_URL:-${1:-}}"
DUMP_FILE="${DUMP_FILE:-${2:-}}"

if [[ -z "$DB_URL" || -z "$DUMP_FILE" ]]; then
  echo "Usage: DATABASE_URL=postgresql://... DUMP_FILE=./backups/file.dump FORCE_RESTORE=true $0"
  exit 1
fi

if [[ ! -f "$DUMP_FILE" ]]; then
  echo "Файл дампа не найден: $DUMP_FILE"
  exit 1
fi

if [[ "${FORCE_RESTORE:-false}" != "true" ]]; then
  echo "Восстановление перезапишет данные. Повторите с FORCE_RESTORE=true"
  exit 1
fi

pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --dbname "$DB_URL" \
  "$DUMP_FILE"

echo "Restore completed from: $DUMP_FILE"
