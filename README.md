# ARCHIPEL41

Assistant numérique intelligent pour agences d'architecture : projets et chantiers, devis et comparateur, agenda,
planning et météo, urbanisme, assistant IA (RAG), documents, clients et entreprises, finances et rapports.

Un seul moteur (FastAPI) et une seule interface (React/TypeScript/Tailwind), livrés de deux façons :

| Livrable | Emplacement |
|---|---|
| Installateur Windows 10/11 x64 | `desktop/build/dist/Archipel41-Setup-1.0.0-x64.exe` |
| Version portable Windows | `desktop/build/dist/Archipel41-Portable-1.0.0-x64.exe` |
| Empreintes SHA-256 | `desktop/build/dist/SHA256SUMS.txt` |
| Guide d'installation | `docs/GUIDE_INSTALLATION_ARCHIPEL41.pdf` |
| Guide utilisateur | `docs/GUIDE_UTILISATION_ARCHIPEL41.pdf` |
| Documentation technique | `docs/DOCUMENTATION_TECHNIQUE.pdf` |
| Serveur central (web) | `docker-compose.yml`, `.env.example` |

## Démarrage rapide

**Poste Windows** : lancer l'installateur, puis l'icône *Archipel41* du Bureau (voir le guide d'installation).

**Version web locale** (Linux/macOS) :
```bash
./scripts/install/run_local.sh        # http://127.0.0.1:8041
```
Windows (PowerShell) : `scripts\install\run_local.ps1`.

**Serveur central** (PostgreSQL 16 + PostGIS + pgvector, HTTPS) :
```bash
./scripts/install/install_server.sh   # ou : cp .env.example .env && docker compose up -d --build
```

Documentation de l'API : `/api/docs` (OpenAPI).

## Clés API

Aucune clé n'est stockée dans le code ni dans `.env`. Les clés se saisissent dans l'application
(**Paramètres › Intelligence artificielle** : Anthropic, Mistral, OpenAI, ou Ollama local sans clé ;
**Paramètres › Urbanisme** : identifiants Légifrance/PISTE). Elles sont chiffrées en base et jamais réaffichées.
Météo (Open-Meteo, BAN), cadastre / Géoportail de l'Urbanisme (API Carto IGN) et Géorisques ne demandent pas de clé.

## Sauvegarde et restauration

- Application : **Paramètres › Sauvegardes** (archive ZIP avec manifeste et SHA-256 ; restauration avec confirmation et sauvegarde de sécurité préalable).
- Serveur : `scripts/backup/backup_server.sh` (pg_dump + fichiers) et `scripts/restore/restore_server.sh`.

## Construction et tests

```bash
./scripts/build/build_desktop.sh                       # installateur + portable (sans Wine)
cd tests && ../.venv/bin/python -m pytest backend      # 65 tests (SQLite ; ARCHIPEL_TEST_DATABASE_URL pour PostgreSQL)
cd tests && ../.venv/bin/python -m pytest sync         # synchronisation poste ↔ serveur
node tests/e2e/e2e.cjs --shots docs/screenshots        # 26 vérifications de bout en bout
.venv/bin/python docs/sources/build_docs.py            # régénère les PDF
```
Test sur un vrai Windows : `.github/workflows/windows-build-and-test.yml` ou `scripts/install/test_windows_install.ps1`.

## Arborescence

```
web/frontend  web/backend  desktop/{electron,installer,build}  database/{migrations,seeds}
ai/{document_analysis,rag,llm,prompts}  docs/  scripts/{install,backup,restore,build}  tests/
```

Démonstration : écran de bienvenue › *Explorer la démonstration* (agence fictive séparée, comptes `*@archipel41.demo`).
