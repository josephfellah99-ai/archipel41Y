# PROMPT – ARCHIPEL41 · LOT 1 « FONDATIONS » (à copier tel quel dans Claude Code)

Tu interviens comme une équipe de développement senior (architecte logiciel, ingénieur full-stack Python/TypeScript,
ingénieur DevOps/sécurité, ingénieur QA, rédacteur technique) sur le logiciel **Archipel41**, déjà développé et
fonctionnel. Ta mission est de réaliser le **Lot 1 « Fondations »** décrit ci-dessous, de bout en bout, puis de
livrer le travail sur une branche avec une pull request. Ne t'arrête pas après une analyse : réalise, teste, documente.

---

## 1. Contexte : ce qui existe déjà

Dépôt GitHub : `josephfellah99-ai/archipel41Y` (branche `main` = code ; branche `installateur-windows` = installateur découpé).

Archipel41 est un logiciel de gestion d'agence d'architecture (3 à 10 personnes) : 11 modules (tableau de bord,
projets/chantiers, devis et comparateur intelligent, agenda, planning Gantt + météo, urbanisme, assistant IA RAG,
documents, clients/entreprises, finances, rapports).

Architecture (lis `README.md` et `docs/DOCUMENTATION_TECHNIQUE.pdf` avant toute modification) :

- `web/backend/app` : API **FastAPI** (Python 3.12), SQLAlchemy, Alembic (`database/migrations`), JWT, rôles
  admin / manager / member / viewer, isolation par agence, journal d'audit, concurrence optimiste (champ `version`).
- `web/frontend/src` : **React + TypeScript + Tailwind**, PWA, IndexedDB + file d'attente hors connexion (`lib/api.ts`).
- `ai/` : extraction documentaire (PDF, OCR Tesseract, XLSX, DOCX…), moteur de calcul déterministe des devis,
  comparateur, RAG, couche fournisseurs d'IA (Anthropic SDK officiel, API compatibles OpenAI, aucun).
- Deux déploiements du même code : **serveur central** (Docker : PostgreSQL 16 + PostGIS + pgvector, Caddy HTTPS)
  et **application Windows** (Electron 33 + Python Windows et Tesseract embarqués, SQLite local, installateur NSIS
  construit sous Linux sans Wine : `scripts/build/build_desktop.sh`).
- Synchronisation local-first poste ↔ serveur (`web/backend/app/services/sync.py`) avec conflits.
- Tests : `tests/backend` (65 tests, SQLite et PostgreSQL via `ARCHIPEL_TEST_DATABASE_URL`), `tests/sync`
  (intégration poste ↔ serveur), `tests/e2e/e2e.cjs` (26 vérifications Playwright, produit les captures des guides).
- Documentation : `docs/sources/*.py` → `docs/*.pdf` via `docs/sources/build_docs.py`.

Limites connues à traiter dans ce lot : l'installateur n'a **jamais été exécuté sur un vrai Windows** ; il n'est pas
signé ; aucun serveur n'est hébergé ; les connecteurs externes (météo, urbanisme, IA) n'ont été testés que sur des
réponses simulées.

---

## 2. Mission – Lot 1 « Fondations » (dans cet ordre)

### A. Valider et fiabiliser l'application Windows
1. Exécute le workflow `.github/workflows/windows-build-and-test.yml` (ou adapte-le) sur `windows-latest` :
   construction, installation silencieuse, démarrage du moteur embarqué, création d'agence, import d'un devis
   scanné avec OCR, désinstallation. Corrige tout ce qui échoue sur Windows (chemins, encodage, antivirus, port,
   Tesseract, fuseau horaire, droits).
2. Ajoute au workflow un test qui lance réellement `Archipel41.exe` (Playwright `_electron`) et vérifie que la
   fenêtre s'ouvre et que le moteur répond.
3. Publie automatiquement l'installateur et la version portable comme **fichiers joints d'une GitHub Release**
   à chaque tag `v*` (workflow `release.yml`), avec `SHA256SUMS.txt`.
4. Prépare la **signature de code** : le workflow signe si les secrets `CSC_LINK` / `CSC_KEY_PASSWORD` existent,
   sinon il continue sans signature et le signale. Documente l'achat du certificat.
5. Ajoute la **mise à jour automatique** (electron-updater, fournisseur GitHub Releases) : vérification au
   démarrage, notification « Nouvelle version disponible », installation à la demande de l'utilisateur.

### B. Serveur central hébergé en France
1. Durcis `docker-compose.yml` pour la production : utilisateurs non root, limites mémoire, journaux en rotation,
   volumes nommés, fichier `docker-compose.prod.yml` séparé, variables d'environnement documentées.
2. Écris un guide pas à pas (et un script `scripts/install/deploy_scaleway_ou_ovh.sh`) pour déployer sur un VPS
   hébergé en France (Scaleway, OVHcloud ou Infomaniak) : création du serveur, pare-feu (ports 22/80/443),
   nom de domaine, HTTPS automatique, premier administrateur.
3. Crée un **environnement de recette** (staging) séparé de la production (même compose, autre base, autre domaine).
4. **Sauvegardes automatiques hors site** : chaque nuit, `pg_dump` + fichiers, chiffrés (restic ou équivalent),
   envoyés vers un stockage objet compatible S3 chez un autre hébergeur ; rétention 7 jours / 4 semaines /
   12 mois ; script de **test de restauration** automatisé (restauration dans une base temporaire + contrôles).
5. **Supervision** : point de santé enrichi (`/api/health` : base, disque, dernière sauvegarde), alerte par e-mail
   en cas d'échec de sauvegarde ou de disque plein, instructions UptimeRobot.

### C. Sécurité des comptes
1. **Double authentification TOTP** (application d'authentification), activable par l'utilisateur, imposable
   par l'administrateur, avec codes de secours.
2. **Connexion avec Microsoft 365 et Google** (OpenID Connect), configurable dans Paramètres, en plus du mot de passe.
3. Politique de conservation des données (RGPD) : écran de paramétrage et purge des éléments supprimés
   au-delà d'une durée choisie ; export des données d'un client sur demande.

### D. Synchronisation des agendas
1. Synchronisation **bidirectionnelle** des rendez-vous avec **Microsoft Outlook / Exchange Online (Microsoft Graph)**
   et **Google Agenda (Google Calendar API)**, par utilisateur (OAuth), avec gestion des conflits et des suppressions.
2. Flux **ICS** en lecture seule par utilisateur (alternative simple, compatible avec tous les agendas).
3. Les identifiants OAuth (client ID / secret) se configurent dans Paramètres, chiffrés comme les clés API
   existantes ; aucun secret dans le code.

### E. Organisation du projet sur GitHub
1. Modèles d'issues (bug, amélioration) et de pull request, `CONTRIBUTING.md` en français, conventions de
   branches et de messages de commit, numérotation sémantique des versions.
2. Workflow d'intégration continue sur chaque pull request : tests backend (SQLite + PostgreSQL en service),
   test de synchronisation, vérification TypeScript, construction de l'interface, tests de bout en bout.
3. `CHANGELOG.md` tenu à jour ; tag `v1.1.0` à la fin du lot.

---

## 3. Règles impératives

- **Ne casse rien** : les 65 tests backend, le test de synchronisation et les 26 vérifications de bout en bout doivent
  rester verts. Ajoute des tests pour chaque nouvelle fonctionnalité (unitaires, intégration, sécurité).
- **Aucun secret** (clé API, mot de passe, certificat, client secret) dans le code, les commits ou les journaux.
- Interface et documentation **en français impeccable**, cohérentes avec la charte (vert forêt #253A33, vert sauge
  #718578, beige minéral #E8E3D8, ivoire #F8F7F2).
- Les fonctions existantes restent utilisables **hors connexion** et **sans fournisseur d'IA**.
- **Honnêteté** : n'annonce jamais comme opérationnel ce qui n'a pas été réellement exécuté et vérifié. Si un élément
  dépend d'un compte, d'un certificat ou d'un service que tu n'as pas, développe-le, prévois son écran de
  configuration, teste-le sur des réponses simulées, et indique précisément ce qui reste à faire.
- Mets à jour les guides PDF (`docs/sources/*.py`, puis `docs/sources/build_docs.py`) avec de **vraies captures** des
  nouveaux écrans (`node tests/e2e/e2e.cjs --shots docs/screenshots`).
- Travaille sur une branche `lot1-fondations` et ouvre une **pull request** vers `main` avec un descriptif clair.

## 4. Informations à me demander si nécessaire (une seule fois, regroupées)

- Hébergeur choisi (Scaleway, OVHcloud, Infomaniak) et accès au serveur.
- Nom de domaine de l'agence.
- Comptes administrateur Microsoft 365 et/ou Google Workspace pour créer les applications OAuth.
- Certificat de signature de code (fichier .pfx et mot de passe), s'il a été acheté.
- Stockage objet pour les sauvegardes hors site (fournisseur, compartiment).
En attendant mes réponses, avance sur tout ce qui n'en dépend pas.

## 5. Livrables attendus et critères d'acceptation

| Livrable | Critère d'acceptation |
|---|---|
| Installateur testé sur Windows | Le workflow Windows est vert : installation, lancement de la fenêtre, OCR, désinstallation |
| Release GitHub automatique | Un tag `v1.1.0` produit une Release avec Setup, Portable et SHA256SUMS |
| Mise à jour automatique | Une version 1.1.0 installée détecte une version 1.1.1 de test et propose la mise à jour |
| Serveur de production + recette | Guide et scripts permettant un déploiement complet en moins d'une heure |
| Sauvegardes hors site | Sauvegarde nocturne chiffrée + test de restauration automatisé qui réussit |
| Supervision | Alerte reçue en cas d'échec de sauvegarde simulé |
| Double authentification | Activation, connexion avec code, codes de secours, imposition par l'administrateur (tests inclus) |
| Connexion Microsoft / Google | Fonctionne avec des identifiants de test ; écran de configuration |
| Synchronisation des agendas | Création, modification, suppression répercutées dans les deux sens (tests sur API simulées) ; flux ICS |
| Organisation GitHub | Modèles, CONTRIBUTING, CI sur pull request verte |
| Documentation | Guides PDF mis à jour avec captures réelles ; CHANGELOG |

Termine par un **tableau récapitulatif** : terminé et testé / terminé mais à configurer / non réalisé (avec la raison).
