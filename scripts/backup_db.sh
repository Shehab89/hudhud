#!/usr/bin/env bash
# Dump the database to backups/<timestamp>.dump (custom format, compressed) and keep the
# newest $KEEP dumps. Usage: DATABASE_URL=... scripts/backup_db.sh
# The dump contains user e-mails and API-key hashes: store it privately.
set -euo pipefail
: "${DATABASE_URL:?set DATABASE_URL}"
KEEP="${KEEP:-14}"
DIR="${BACKUP_DIR:-backups}"
mkdir -p "$DIR"
url="${DATABASE_URL/postgresql+psycopg:/postgresql:}"
out="$DIR/observatory-$(date -u +%Y%m%dT%H%M%SZ).dump"
pg_dump --format=custom --no-owner --no-privileges --file "$out" "$url"
echo "wrote $out ($(du -h "$out" | cut -f1))"
ls -1t "$DIR"/observatory-*.dump | tail -n +"$((KEEP + 1))" | xargs -r rm --
