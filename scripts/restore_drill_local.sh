#!/usr/bin/env bash
set -euo pipefail

if ! command -v psql >/dev/null 2>&1; then
  echo "psql не найден. Установите PostgreSQL client tools."
  exit 1
fi

PGHOST="${PGHOST:-127.0.0.1}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGPASSWORD="${PGPASSWORD:-postgres}"
export PGPASSWORD

suffix="$(date -u +%Y%m%d%H%M%S)"
src_db="swl_restore_src_${suffix}"
dst_db="swl_restore_dst_${suffix}"
tmpdir="$(mktemp -d)"

cleanup() {
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS ${src_db};" >/dev/null 2>&1 || true
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS ${dst_db};" >/dev/null 2>&1 || true
  rm -rf "$tmpdir"
}
trap cleanup EXIT

psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 \
  -c "CREATE DATABASE ${src_db};" >/dev/null
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 \
  -c "CREATE DATABASE ${dst_db};" >/dev/null

psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$src_db" -v ON_ERROR_STOP=1 <<'SQL' >/dev/null
CREATE TABLE restore_probe (
  id SERIAL PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT INTO restore_probe (value) VALUES ('alpha'), ('beta');
SQL

src_url="postgresql://${PGUSER}:${PGPASSWORD}@${PGHOST}:${PGPORT}/${src_db}"
dst_url="postgresql://${PGUSER}:${PGPASSWORD}@${PGHOST}:${PGPORT}/${dst_db}"

BACKUP_DIR="$tmpdir" DATABASE_URL="$src_url" ./scripts/db_backup.sh >/dev/null
dump_file="$(ls -1 "$tmpdir"/social_wishlist_*.dump | head -n1)"
if [[ -z "${dump_file:-}" ]]; then
  echo "Не удалось найти файл backup после db_backup.sh"
  exit 1
fi

DATABASE_URL="$dst_url" DUMP_FILE="$dump_file" FORCE_RESTORE=true ./scripts/db_restore.sh >/dev/null

count="$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$dst_db" -Atc "SELECT COUNT(*) FROM restore_probe;")"
if [[ "$count" != "2" ]]; then
  echo "Restore drill failed: expected 2 rows, got ${count}"
  exit 1
fi

echo "Restore drill completed successfully."
