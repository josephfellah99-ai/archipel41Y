#!/usr/bin/env bash
# Restauration du serveur central à partir d'une sauvegarde de backup_server.sh.
#   ./scripts/restore/restore_server.sh sauvegardes/archipel41_db_AAAAMMJJ_HHMMSS.dump sauvegardes/archipel41_fichiers_AAAAMMJJ_HHMMSS.tar.gz
set -euo pipefail
cd "$(dirname "$0")/../.."
DUMP="$1"; FILES="$2"
read -rp "La base actuelle sera REMPLACÉE. Tapez RESTAURER pour continuer : " OK
[ "$OK" = "RESTAURER" ] || exit 1
set -a; . ./.env; set +a
./scripts/backup/backup_server.sh ./sauvegardes/avant_restauration
docker compose stop app
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists < "$DUMP"
docker compose start app
docker compose exec -T app sh -c "rm -rf /data/files && tar xzf - -C /data" < "$FILES"
echo "✓ Restauration terminée."
