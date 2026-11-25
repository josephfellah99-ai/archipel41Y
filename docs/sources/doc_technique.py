"""DOCUMENTATION TECHNIQUE d'Archipel41 (résultats de tests lus dans les rapports d'exécution)."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from layout import Doc

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "tests" / "reports"


def junit(name: str):
    p = REPORTS / f"{name}.xml"
    if not p.exists():
        return None
    r = ET.parse(p).getroot()
    s = r if r.tag == "testsuite" else r.find("testsuite")
    t, f, e, sk = (int(s.get(k, 0)) for k in ("tests", "failures", "errors", "skipped"))
    return t, t - f - e - sk, f + e, sk, s.get("timestamp", "")[:16].replace("T", " ")


def build() -> Doc:
    d = Doc("Documentation technique – Archipel41", "Architecture, données, API, synchronisation, sécurité, tests et construction des livrables.", "Documentation technique")

    d.part("Vue d'ensemble")
    d.p("Archipel41 est composé d'un <b>moteur unique</b> (API FastAPI + moteurs documentaires et d'IA en Python) et d'une <b>interface unique</b> "
        "(React + TypeScript + Tailwind), déployés de deux façons qui partagent exactement le même code, les mêmes modèles de données et les mêmes règles métier :")
    d.table(["", "Serveur central (web)", "Application Windows"], [
        ["Moteur", "FastAPI (Python 3.12) dans Docker", "Le même moteur, avec Python 3.12 Windows embarqué, lancé par Electron sur 127.0.0.1 (port libre)"],
        ["Base", "PostgreSQL 16 + PostGIS 3.4 + pgvector", "SQLite (WAL) dans %APPDATA%\\Archipel41\\data"],
        ["Interface", "Servie par le moteur ; PWA (service worker, IndexedDB, file d'attente)", "Même interface dans une fenêtre Electron 33 (contextIsolation, sandbox)"],
        ["OCR", "Tesseract (paquet Debian, fra)", "Tesseract 5.4 Windows embarqué (fra, eng)"],
        ["Rôle", "Base centrale partagée, synchronisation", "Base locale par poste, synchronisation bidirectionnelle avec le serveur"],
    ], [14, 43, 43])
    d.h3("Justification des choix")
    d.ul("<b>Electron + moteur Python embarqué</b> plutôt qu'un simple raccourci web : l'application Windows fonctionne hors connexion avec toutes ses fonctions "
         "(OCR, extraction, comparateur, rapports), et le code métier n'est écrit qu'une fois.",
         "<b>SQLite sur le poste / PostgreSQL au serveur</b> via SQLAlchemy : un type <code>Embedding</code> utilise <code>vector</code> (pgvector) sous PostgreSQL et du JSON sous SQLite ; "
         "les géométries sont en GeoJSON, complétées sous PostgreSQL par une colonne PostGIS alimentée par déclencheur.",
         "<b>Calculs déterministes</b> (Decimal, arrondi demi-supérieur) séparés de l'IA, qui ne produit que du texte et des propositions.",
         "<b>Couche IA indépendante des fournisseurs</b> : Anthropic (SDK officiel), API compatibles OpenAI (Mistral, OpenAI, Azure, Ollama/LM Studio locaux), ou aucun fournisseur.")

    d.part("Arborescence du code")
    d.pre("""ARCHIPEL41/
├── web/backend/app/          API FastAPI : main.py, config.py, db.py, models.py, schemas.py, security.py, crud.py
│   ├── routers/              auth, documents, quotes, agenda, planning, urbanisme, assistant, insights, reports, system, entities
│   └── services/             ai, documents, storage, settings_store, crypto, weather, urbanisme, exports, backup, sync
├── web/frontend/src/         React + TypeScript : lib/ (api.ts local-first, app.tsx), components/, pages/ (11 modules + paramètres)
├── ai/document_analysis/     extract.py (PDF/OCR/XLSX/XLS/CSV/DOCX/DOC/ZIP), numbers.py, quote_parser.py, calc.py, comparator.py, specs.py
├── ai/rag/engine.py          découpage, embeddings locaux, recherche hybride
├── ai/llm/providers.py       fournisseurs d'IA ;  ai/prompts/  consignes versionnées
├── database/                 alembic.ini, migrations/ (0001 schéma, 0002 PostGIS/plein texte), seeds/ (démo), Dockerfile
├── desktop/electron/         main.js, preload.js, splash.html, afterPack.js, package.json (electron-builder)
├── desktop/installer/        icône, licence, installer.nsh ;  desktop/build/  python-win, tesseract-win, backend, dist/
├── scripts/                  build/, install/, backup/, restore/
├── tests/                    backend/ (pytest), sync/ (intégration serveur ↔ poste), e2e/ (Playwright)
└── docker-compose.yml, .env.example, README.md, CHANGELOG.md""")

    d.part("Modèle de données")
    d.p("Toutes les entités métier héritent d'un socle commun : identifiant UUID (généré côté client ou serveur), <code>agency_id</code> (isolation), "
        "<code>version</code> (concurrence optimiste), <code>deleted</code> (suppression logique propagée), <code>created_at / updated_at / updated_by</code>, "
        "et, en mode bureau, <code>dirty / base_version</code> (état de synchronisation).")
    d.table(["Domaine", "Tables"], [
        ["Agence et comptes", "agencies, users, settings (clés API chiffrées Fernet), audit_logs"],
        ["Projets", "projects (phases JSON ESQ→AOR, équipe, terrain), lots, incidents"],
        ["Planning", "tasks (dépendances, activité, référence), proposals (ajustements à valider)"],
        ["Agenda", "events (participants, rappel, compte rendu, documents)"],
        ["Documents", "documents, document_versions (stockage par empreinte SHA-256), document_chunks (index RAG, non synchronisé)"],
        ["Devis", "quotes, quote_lines, dpgf_items, cctp_requirements, comparisons"],
        ["Finances", "budget_lines, finance_entries"],
        ["Urbanisme, IA, rapports", "parcel_analyses (+ geom PostGIS), conversations, reports"],
        ["Synchronisation", "change_log (journal des modifications / curseur), sync_conflicts"],
    ], [24, 76])

    d.part("API REST")
    d.p("L'API est documentée automatiquement (OpenAPI) : <code>/api/docs</code> (Swagger) et <code>/api/redoc</code>. Authentification par jeton JWT (HS256, 12 h) "
        "dans l'en-tête <code>Authorization: Bearer</code>. Principales routes :")
    d.table(["Route", "Rôle"], [
        ["POST /api/setup · POST /api/auth/login · GET /api/auth/me", "Configuration initiale, connexion, profil et permissions"],
        ["/api/projects, /lots, /incidents, /tasks, /clients, /companies, /budget-lines, /finance-entries, /dpgf-items", "CRUD générique (liste filtrée, lecture, création idempotente X-Client-Id, mise à jour avec version, suppression logique, /history)"],
        ["POST /api/quotes/import · PUT /api/quotes/{id}/lines · POST /api/quotes/{id}/validate · /reextract", "Import multi-fichiers, corrections, validation, ré-extraction (règles ou IA)"],
        ["POST /api/dpgf/import · POST /api/cctp/import · POST /api/comparisons · GET /api/comparisons/{id}/export", "Références, comparaison, exports XLSX/PDF/DOCX/CSV"],
        ["/api/documents (upload, versions, download, pages, page/{n}, text, search, export, reindex)", "Bibliothèque documentaire et recherche RAG"],
        ["/api/events (+ /check, /reminders, /summarize)", "Agenda, conflits, rappels, synthèse des comptes rendus"],
        ["/api/projects/{id}/schedule · /weather · /weather/proposals · /api/proposals/{id}/accept|reject", "Planning, météo, propositions à valider"],
        ["/api/urbanisme/analyses (+ /plu) · /api/urbanisme/legifrance", "Analyse de site et du règlement, Légifrance"],
        ["/api/assistant/ask · /api/conversations · /api/search", "Assistant RAG et recherche transversale"],
        ["/api/dashboard (+ /weather, /daily-summary) · /api/projects/{id}/finances · /api/reports", "Tableau de bord, finances, rapports"],
        ["/api/settings/{clé} · /api/backups · /api/restore · /api/audit · /api/system/info", "Administration"],
        ["/api/sync/push · /pull · /files/{id} (serveur) · /api/sync/configure · /run · /status · /conflicts (poste)", "Synchronisation"],
    ], [52, 48])

    d.part("Moteur documentaire et comparateur")
    d.sec("Extraction")
    d.ul("PDF natif : pdfplumber (texte et tableaux) ; page sans texte → rendu 300 ppp et OCR Tesseract (fra, psm 6).",
         "Images : redressement EXIF, agrandissement, OCR. XLSX/XLS : openpyxl/xlrd (en mémoire). CSV : détection d'encodage et de séparateur. DOCX : paragraphes et tableaux (cellules fusionnées). DOC : conversion LibreOffice si présent.",
         "ZIP : dépliage récursif (2 niveaux), protection contre les chemins malveillants et les archives démesurées. CAO/BIM : stockage et versions sans extraction.")
    d.sec("Analyse des devis (règles)")
    d.ul("Tableaux : reconnaissance des colonnes par en-têtes ; lignes sans montant → sections ou mentions (compris, non compris, PM).",
         "Texte : découpage de la fin de ligne en (quantité, unité, PU, montant) avec énumération des regroupements de milliers « 14 295,00 » et choix de la combinaison où qté × PU = montant.",
         "Nettoyage OCR (traits de grille, O/0, L/1, « ou »/u). Statut par mots-clés : <i>exclu</i> uniquement sur mention expresse.",
         "En-tête et pied : entreprise, SIRET, référence, date, validité, délai (converti en jours), totaux HT/TVA/TTC, conditions de paiement, exclusions, réserves, variantes.")
    d.sec("Calculs")
    d.p("<code>ai/document_analysis/calc.py</code> : Decimal, arrondi demi-supérieur au centime, TVA par taux (20 ; 10 ; 5,5 ; 2,1 ; 0), contrôle ligne par ligne (tolérance 0,02 €) "
        "et des totaux déclarés (tolérance 1 €), doublons, montants négatifs, options, variantes et lignes à vérifier exclues du total.")
    d.sec("Comparaison")
    d.p("Référence : DPGF du lot, sinon l'offre la plus détaillée. Appariement par similarité (Jaccard, couverture, SequenceMatcher, abréviations, bonus de code ; "
        "seuils 0,52 et 0,40), puis statuts, écarts à la médiane (30 % inhabituel, 50 % fort), montant à périmètre comparable, classement pondéré et contrôle CCTP "
        "(ouvrage cité, spécifications techniques). Conclusion rédigée par le moteur de règles, et facultativement par l'IA à partir des seuls faits calculés.")
    d.sec("RAG")
    d.p("Passages d'environ 750 caractères, ouverts à chaque intitulé (article, zone, lot) et préfixés par le contexte (« [ZONE UB] »). Embeddings locaux hors ligne "
        "(hachage de termes et bigrammes, 768 dimensions) ou embeddings du fournisseur. Sous PostgreSQL, présélection en base par <code>embedding &lt;=&gt; vecteur</code> (pgvector) "
        "et <code>to_tsvector('french')</code> (index GIN), puis classement hybride. Les rapports générés sont pondérés à 0,6 pour privilégier les pièces sources.")

    d.part("Synchronisation local-first")
    d.ul("Chaque modification incrémente <code>version</code>, est journalisée dans <code>change_log</code> et, sur un poste, marque la ligne <code>dirty</code>.",
         "PUSH : le serveur accepte si sa version = <code>base_version</code> du poste, sinon renvoie un conflit avec sa version des données.",
         "PULL : curseur sur <code>change_log.seq</code> ; les lignes en conflit ouvert ne sont jamais écrasées.",
         "Fichiers : transfert séparé, vérification SHA-256. Index RAG reconstruit localement.",
         "Raccordement : l'agence locale adopte l'identifiant de l'agence serveur ; comptes de même e-mail fusionnés.",
         "Navigateur : cache IndexedDB des lectures, file d'attente des écritures (rejeu idempotent par X-Client-Id), conflits 409 présentés à l'utilisateur.")

    d.part("Sécurité")
    d.table(["Exigence", "Mise en œuvre"], [
        ["Authentification", "Mots de passe PBKDF2-SHA256 (390 000 itérations, sel aléatoire), politique (10 caractères, 3 types), blocage 5 min après 5 échecs, JWT signé lié à l'agence"],
        ["Rôles", "admin / chef de projet / collaborateur / lecture seule ; matrice read, write, delete, validate, admin"],
        ["Isolation", "Filtrage systématique par agence ; projets confidentiels limités à l'équipe"],
        ["Documents", "Liste blanche d'extensions, contrôle de signature PDF, refus des exécutables, noms neutralisés, stockage hors racine web, téléchargement avec CSP sandbox"],
        ["Communications", "HTTPS par le proxy Caddy (Let's Encrypt) ; poste : boucle locale 127.0.0.1 uniquement"],
        ["Secrets", "Aucune clé dans le code ; clés API chiffrées au repos (Fernet), jamais renvoyées en clair ; SECRET_KEY générée"],
        ["IA", "Envoi externe désactivable ; contenus confidentiels exclus sauf autorisation explicite ; modèles locaux non considérés comme externes"],
        ["En-têtes", "nosniff, X-Frame-Options, Referrer-Policy, Permissions-Policy, CSP, HSTS en HTTPS, Cache-Control no-store sur l'API"],
        ["Traçabilité", "Journal d'audit, historique des modifications champ par champ"],
        ["Sauvegardes", "Archives avec manifeste et SHA-256, sauvegarde de sécurité avant restauration"],
    ], [20, 80])

    d.part("Tests et résultats")
    rows = []
    labels = [("pytest_sqlite", "Unitaires + intégration API + sécurité", "SQLite"), ("pytest_postgres", "Unitaires + intégration API + sécurité", "PostgreSQL 16 + PostGIS + pgvector"),
              ("sync_sqlite", "Synchronisation poste ↔ serveur (processus séparés)", "Serveur SQLite"), ("sync_postgres", "Synchronisation poste ↔ serveur (processus séparés)", "Serveur PostgreSQL")]
    for key, label, base in labels:
        r = junit(key)
        rows.append([label, base, f"{r[1]} / {r[0]}" if r else "non exécuté", f"{r[2]}" if r else "—", r[4] if r else "—"])
    e2e = ROOT / "tests" / "e2e" / "e2e-results.json"
    if e2e.exists():
        j = json.loads(e2e.read_text())
        ok = sum(1 for x in j["results"] if x["ok"])
        rows.append(["Bout en bout (Playwright/Chromium) : parcours complet, hors connexion, responsive", "Serveur SQLite", f"{ok} / {len(j['results'])}", str(len(j["results"]) - ok), j["date"][:16].replace("T", " ")])
    d.table(["Campagne", "Base", "Réussis / total", "Échecs", "Exécution (UTC)"], rows, [40, 20, 14, 8, 18])
    d.p("Détail des tests unitaires : nombres français, arrondis, TVA multi-taux, anomalies, extraction des cinq formats de devis de démonstration (dont OCR), "
        "ZIP malveillant, DPGF, CCTP, PLU (dont thème absent signalé), statuts du comparateur (non renseigné ≠ non inclus, non comparable, écart fort), RAG.")
    d.p("Tests de sécurité : authentification exigée sur toutes les routes, jetons falsifiés/expirés/d'une autre agence, compte désactivé, injections SQL, "
        "limitation des tentatives, fichiers exécutables et faux PDF, traversée de chemins, en-têtes, SVG piégé, hachage, droits du rôle lecture seule, absence de secrets dans le code, journal d'audit.")
    if e2e.exists():
        d.table(["Vérification de bout en bout", "Résultat"], [[x["name"], '<span class="badge ok">OK</span>' if x["ok"] else f'<span class="badge ko">ÉCHEC</span> {x["detail"]}'] for x in j["results"]], [80, 20])
    d.sec("Ce qui n'a pas pu être testé dans l'environnement de construction")
    d.ul("<b>Exécution réelle sous Windows 10/11</b> : l'installateur a été construit et vérifié structurellement (contenu, icône, métadonnées, script NSIS, Python et Tesseract en binaires Windows x64), "
         "et la même application Electron a été exécutée de bout en bout sous Linux ; mais aucun Windows n'était disponible (et Wine ne fonctionne pas dans ce conteneur). "
         "Le workflow <code>.github/workflows/windows-build-and-test.yml</code> et le script <code>scripts/install/test_windows_install.ps1</code> réalisent ce test sur un vrai Windows.",
         "<b>Services publics en ligne</b> (Open-Meteo, BAN, API Carto IGN, Géorisques, Légifrance) et <b>fournisseurs d'IA</b> : réseau sortant bloqué dans l'environnement de construction ; "
         "connecteurs testés sur réponses simulées conformes aux formats documentés. À valider avec « Tester la connexion » dans les paramètres.",
         "<b>Signature de code</b> de l'installateur : nécessite un certificat de l'agence.")

    d.part("Construction des livrables")
    d.table(["Commande", "Résultat"], [
        ["<code>cd web/frontend && npm ci && npm run build</code>", "Interface compilée (web/frontend/dist) avec service worker PWA"],
        ["<code>./scripts/install/run_local.sh</code>", "Version web locale sur http://127.0.0.1:8041 (SQLite)"],
        ["<code>docker compose up -d --build</code>", "Serveur central : PostgreSQL/PostGIS/pgvector + Archipel41 + HTTPS"],
        ["<code>./scripts/build/build_desktop.sh</code>", "Python Windows + Tesseract Windows + moteur assemblé + installateur NSIS et version portable (desktop/build/dist)"],
        ["<code>cd tests && ../.venv/bin/python -m pytest backend</code>", "Tests unitaires, API et sécurité (ARCHIPEL_TEST_DATABASE_URL pour PostgreSQL)"],
        ["<code>cd tests && ../.venv/bin/python -m pytest sync</code>", "Test d'intégration de la synchronisation"],
        ["<code>node tests/e2e/e2e.cjs --shots docs/screenshots</code>", "Tests de bout en bout et captures des guides"],
        ["<code>.venv/bin/python docs/sources/build_docs.py</code>", "Génération des trois PDF"],
    ], [50, 50])
    d.sec("Construction sans Wine")
    d.p("L'icône et les métadonnées de l'exécutable sont écrites par <code>resedit</code> (afterPack.js) ; le désinstalleur est extrait par l'outil JavaScript "
        "d'electron-builder (<code>UninstallerReader</code>), activé sous Linux par <code>scripts/build/patch_electron_builder.cjs</code> (variable A41_NO_WINE=1).")
    d.sec("Signature de code (recommandée)")
    d.p("Avec un certificat de signature de code (fichier .pfx), définissez <code>CSC_LINK</code> et <code>CSC_KEY_PASSWORD</code> puis construisez sous Windows "
        "(<code>npx electron-builder --win</code>), ou signez a posteriori avec <code>signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256</code>.")

    d.part("Limites connues et évolutions")
    d.ul("Dépendances de planning de type fin → début uniquement ; pas de calcul de marges libres et totales.",
         "Agenda non synchronisé avec Outlook / Google Agenda ; notifications affichées lorsque l'application est ouverte.",
         "Pas de visualisation des fichiers CAO/BIM (DWG, IFC…) ; ils sont stockés et versionnés.",
         "Extraction des devis aux mises en page très atypiques : correction manuelle ou extraction par IA.",
         "Pas de mise à jour automatique de l'application Windows (installation manuelle du nouvel installateur).",
         "Le contrôle CCTP porte sur la mention des exigences, pas sur la conformité technique.")
    return d
