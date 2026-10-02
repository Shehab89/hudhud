#!/usr/bin/env bash
# Restore a dump made by backup_db.sh into an EMPTY database (pgvector must be available).
# Usage: DATABASE_URL=... scripts/restore_db.sh backups/observatory-....dump
set -euo pipefail
: "${DATABASE_URL:?set DATABASE_URL}"
dump="${1:?path to .dump file}"
url="${DATABASE_URL/postgresql+psycopg:/postgresql:}"
pg_restore --no-owner --no-privileges --exit-on-error --dbname "$url" "$dump"
echo "restored $dump; run 'observatory migrate' if the code is newer than the dump"
