#!/usr/bin/env bash
# Sauvegarde complète du serveur central : base PostgreSQL (pg_dump) + fichiers des documents.
#   ./scripts/backup/backup_server.sh [dossier_destination]     (à planifier chaque nuit via cron)
set -euo pipefail
cd "$(dirname "$0")/../.."
DEST="${1:-./sauvegardes}"; mkdir -p "$DEST"
STAMP="$(date +%Y%m%d_%H%M%S)"
set -a; . ./.env; set +a
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$DEST/archipel41_db_$STAMP.dump"
docker compose exec -T app tar czf - -C /data files > "$DEST/archipel41_fichiers_$STAMP.tar.gz"
sha256sum "$DEST"/*_"$STAMP".* > "$DEST/archipel41_$STAMP.sha256"
find "$DEST" -name "archipel41_*" -mtime +30 -delete
echo "✓ Sauvegarde : $DEST/archipel41_db_$STAMP.dump + fichiers"
