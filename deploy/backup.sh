#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$(readlink -f -- "$0")")"
umask 077
exec 9>./backups/.backup.lock
flock -n 9 || exit 0
archive="/backups/civia-$(date -u +%Y%m%dT%H%M%SZ).enc"
docker compose --env-file compose.env run --rm backup backup --output "$archive" --media-root /media
docker compose --env-file compose.env run --rm backup restore-test --archive "$archive"
