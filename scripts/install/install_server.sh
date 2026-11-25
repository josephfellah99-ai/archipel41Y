#!/usr/bin/env bash
# Installation du serveur central Archipel41 (Linux avec Docker).
set -euo pipefail
cd "$(dirname "$0")/../.."
command -v docker >/dev/null || { echo "Docker est requis : https://docs.docker.com/engine/install/"; exit 1; }
if [ ! -f .env ]; then
  cp .env.example .env
  PW="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sed -i "s#changez-moi-mot-de-passe-long-et-aleatoire#${PW}#g; s#^ARCHIPEL_SECRET_KEY=.*#ARCHIPEL_SECRET_KEY=${KEY}#" .env
  echo "→ Fichier .env créé avec un mot de passe de base de données aléatoire."
  read -rp "Nom de domaine du serveur (ex. archipel41.monagence.fr) : " DOMAIN
  sed -i "s#^ARCHIPEL_DOMAIN=.*#ARCHIPEL_DOMAIN=${DOMAIN}#" .env
fi
docker compose up -d --build
echo "✓ Archipel41 démarre. Ouvrez https://$(grep ^ARCHIPEL_DOMAIN .env | cut -d= -f2) pour créer l'agence."
