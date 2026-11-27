"""GUIDE D'HÉBERGEMENT ET DE TEST D'ARCHIPEL41 – pas à pas, à partir des fichiers livrés."""
from layout import Doc

V = "1.2.0"


def build(server_verified: str = "") -> Doc:
    d = Doc("Héberger et tester Archipel41, pas à pas",
            "Du téléchargement des fichiers au serveur de l'agence en HTTPS : chaque étape, chaque commande, chaque vérification.",
            "Guide d'hébergement et de test")

    # ------------------------------------------------------------------ 1
    d.part("Les fichiers livrés")
    d.p("Archipel41 est livré sous forme de quelques archives ZIP. Vous n'avez pas besoin de toutes : choisissez selon ce que vous "
        "voulez faire (tableau ci-dessous).")
    d.table(["Archive", "Contenu", "Pour quoi faire ?"], [
        [f"<code>Archipel41-{V}-Windows-Installateur.zip</code>", f"<code>Archipel41-Setup-{V}-x64.exe</code>, empreintes <code>SHA256SUMS.txt</code>, guides PDF, <code>LISEZMOI.txt</code>",
         "Installer l'application sur un poste Windows (cas le plus courant)."],
        [f"<code>Archipel41-{V}-Windows-Portable.zip</code>", f"<code>Archipel41-Portable-{V}-x64.exe</code>, empreintes, guides PDF",
         "Essayer sans rien installer (clé USB, poste sans droits d'administration)."],
        [f"<code>Archipel41-{V}-source.zip</code>", "Code source complet, <code>docker-compose.yml</code>, <code>.env.example</code>, scripts d'installation, tests, documentation",
         "Héberger le serveur central de l'agence ; lancer la version web sur un ordinateur."],
        [f"<code>Archipel41-{V}-Documentation.zip</code>", "Tous les guides PDF (pratique, utilisation, installation, technique, ce guide)", "Lire, imprimer, transmettre au prestataire."],
        ["<code>A41_referentiel_agence_CONFIDENTIEL.zip</code>", "Audit documentaire, base de connaissance, modèles adaptés de l'agence",
         "Usage interne uniquement : ne jamais le publier ni l'envoyer à un tiers."],
    ], [30, 40, 30])
    d.warn("L'archive du référentiel de l'agence est confidentielle. Elle n'est pas publiée sur GitHub et ne doit pas être déposée "
           "sur le serveur public, ni dans un service en ligne, sans décision de l'agence.", "Confidentialité")
    d.sec("Trois façons de faire tourner Archipel41")
    d.table(["", "A. Poste Windows seul", "B. Version web locale", "C. Serveur central de l'agence"], [
        ["But", "Tester ou travailler seul", "Tester dans un navigateur, sur Linux, Mac ou Windows", "Travailler en équipe, depuis le bureau, le chantier ou un téléphone"],
        ["Il faut", "Windows 10/11 64 bits", "Python 3.12 et Node.js 22", "Un serveur Linux (VPS) avec Docker et un nom de domaine"],
        ["Données", "Sur le poste (SQLite)", "Sur l'ordinateur (SQLite)", "Base PostgreSQL centrale, copie locale sur chaque poste Windows"],
        ["Durée", "10 minutes", "15 minutes", "1 heure environ (hors propagation DNS)"],
    ], [13, 27, 27, 33])
    d.tip("Ordre conseillé : <b>A</b> pour découvrir l'application avec la démonstration, puis <b>C</b> quand l'agence décide de "
          "travailler à plusieurs. <b>B</b> sert surtout au prestataire informatique.", "Par où commencer ?")

    # ------------------------------------------------------------------ A
    d.part("A. Tester sur un poste Windows")
    d.sec("Télécharger et vérifier l'installateur")
    d.steps(f"Téléchargez <code>Archipel41-{V}-Windows-Installateur.zip</code>, puis faites un clic droit › <b>Extraire tout…</b>.",
            "Dans le dossier extrait, cliquez dans la barre d'adresse de l'Explorateur, tapez <code>powershell</code> puis Entrée : une fenêtre PowerShell s'ouvre dans ce dossier.",
            f"Tapez la commande ci-dessous et comparez le résultat avec la ligne <code>Archipel41-Setup-{V}-x64.exe</code> du fichier <code>SHA256SUMS.txt</code>.")
    d.pre(f"Get-FileHash .\\Archipel41-Setup-{V}-x64.exe -Algorithm SHA256")
    d.note("Les deux empreintes doivent être strictement identiques (la casse des lettres ne compte pas). Si elles diffèrent, "
           "le fichier est incomplet ou altéré : supprimez-le et téléchargez-le à nouveau.", "Pourquoi vérifier ?")
    d.sec("Installer")
    d.steps(f"Double-cliquez sur <code>Archipel41-Setup-{V}-x64.exe</code>.",
            "Si Windows affiche « <b>Windows a protégé votre ordinateur</b> » : cliquez sur <b>Informations complémentaires</b>, puis sur "
            "<b>Exécuter quand même</b>. Ce message apparaît parce que l'installateur n'est pas encore signé par un certificat d'éditeur.",
            "Suivez l'assistant (dossier proposé par défaut). Aucun droit d'administrateur n'est nécessaire.",
            "À la fin, laissez cochée la case de lancement et cliquez sur <b>Terminer</b>.")
    d.sec("Premier lancement : explorer la démonstration")
    d.steps("Un écran « Démarrage du moteur local… » s'affiche de 5 à 20 secondes la première fois.",
            "Sur l'écran d'accueil, cliquez sur <b>Explorer la démonstration</b>, choisissez un mot de passe pour les comptes fictifs, validez.",
            "Vous êtes connecté avec <code>demo@archipel41.demo</code>. Un bandeau orange rappelle que ce sont des données de démonstration : "
            "elles appartiennent à une agence fictive séparée et ne se mélangent jamais avec les vôtres.")
    d.sec("Liste de vérification (30 minutes)")
    d.p("Cochez chaque ligne. Si une vérification échoue, notez l'écran, l'heure et la référence <code>E-XXXXXX</code> éventuellement "
        "affichée : elle permet de retrouver l'erreur dans <b>Historique › Erreurs et diagnostic</b>.")
    d.table(["Module", "Ce qu'il faut faire", "Résultat attendu"], [
        ["Tableau de bord", "Ouvrir l'application", "Alertes, rendez-vous, tâches et budgets du jour s'affichent"],
        ["Projets", "Créer un projet (code, nom, maître d'ouvrage, budget « 1 250 000 »)", "Le projet apparaît ; le budget est lu à la française"],
        ["Projets › Lots", "Ajouter, renommer, réordonner deux lots", "Les lots suivent l'ordre choisi ; aucune liste imposée"],
        ["Comparateur", "Importer un devis PDF (même scanné) dans un lot", "Lignes extraites, total recalculé, lignes douteuses signalées « à vérifier »"],
        ["Comparatif", "Comparer deux devis validés du même lot", "Écarts ligne à ligne, remarques techniques, leviers d'optimisation"],
        ["Documents", "Choisir un dossier de l'arborescence, importer un PDF puis un Excel", "Aperçu, suggestion de classement « Classer ici / Ignorer », version 1"],
        ["Documents", "Importer à nouveau le même nom de fichier", "Une version 2 est créée ; la version 1 reste téléchargeable (rien n'est écrasé)"],
        ["Documents", "Ouvrir un document › Annoter, poser une zone", "L'annotation s'affiche ; le fichier original n'est pas modifié"],
        ["Terrain", "Rechercher une adresse, mesurer une surface, poser un repère", "Carte, mesure en m², repère annoté (connexion Internet requise)"],
        ["Planning", "Créer deux tâches liées", "La dépendance est respectée ; les décalages météo sont proposés, jamais imposés"],
        ["Agenda", "Créer deux rendez-vous qui se chevauchent", "Le conflit est signalé avant l'enregistrement"],
        ["Équipe", "Créer un collaborateur au rôle « Lecteur », se connecter avec", "Il consulte mais ne peut ni modifier ni ouvrir les paramètres"],
        ["Historique", "Ouvrir une ligne du journal", "Ancienne et nouvelle valeur, auteur, date ; contrôle d'intégrité « OK »"],
        ["Paramètres › Sauvegardes", "Sauvegarder maintenant, puis télécharger le ZIP", "Un fichier <code>.zip</code> est produit"],
        ["Aide", "Bouton « ? » en haut de chaque écran", "Fiche d'aide de l'écran ; lien vers le guide pratique"],
    ], [18, 44, 38])
    d.sec("Créer votre propre agence")
    d.p("Une fois la démonstration explorée, déconnectez-vous, puis sur l'écran d'accueil choisissez <b>Créer mon agence</b> : nom de "
        "l'agence, votre nom, votre e-mail et un mot de passe solide (12 caractères ou plus). Vous devenez administrateur.")
    d.sec("Vérification automatique (facultatif, pour le prestataire)")
    d.p("Le script <code>scripts/install/test_windows_install.ps1</code> (archive source) démarre le moteur installé sur un port de test, "
        "crée une agence temporaire, importe un devis scanné et vérifie l'OCR. Il n'utilise pas vos données.")
    d.pre("powershell -ExecutionPolicy Bypass -File .\\scripts\\install\\test_windows_install.ps1")
    d.warn("L'installateur a été construit et son contenu vérifié fichier par fichier, mais il n'a pas encore été exécuté sur un vrai "
           "poste Windows de l'agence. Ce premier test réel est précisément l'objet de ce chapitre : merci de signaler tout écart.",
           "Ce qui reste à confirmer")

    # ------------------------------------------------------------------ B
    d.part("B. Tester la version web sur un ordinateur")
    d.p("Utile pour le prestataire, ou pour essayer Archipel41 dans un navigateur sans serveur. Les données restent sur l'ordinateur (SQLite).")
    d.steps("Installez <b>Python 3.12</b> (python.org) et <b>Node.js 22</b> (nodejs.org).",
            f"Décompressez <code>Archipel41-{V}-source.zip</code> et ouvrez un terminal dans le dossier <code>Archipel41-{V}-source</code>.",
            "Lancez le script correspondant à votre système (ci-dessous). Le premier lancement installe les dépendances et construit l'interface : quelques minutes.",
            "Ouvrez <code>http://127.0.0.1:8041</code> dans le navigateur, puis suivez les étapes « Premier lancement » à « Créer votre propre agence » du chapitre A.",
            "Pour arrêter : <kbd>Ctrl</kbd> + <kbd>C</kbd> dans le terminal.")
    d.h3("Linux ou macOS")
    d.pre("bash scripts/install/run_local.sh")
    d.h3("Windows (PowerShell)")
    d.pre("powershell -ExecutionPolicy Bypass -File .\\scripts\\install\\run_local.ps1")
    d.note("Cette version locale n'est accessible que depuis l'ordinateur lui-même (adresse 127.0.0.1). Pour un usage en équipe, "
           "utilisez le serveur central du chapitre C, qui chiffre les échanges en HTTPS.", "Accès")

    # ------------------------------------------------------------------ C
    d.part("C. Héberger le serveur central de l'agence")
    d.p("Le serveur central fait tourner trois services Docker : la base <b>PostgreSQL 16</b> (avec PostGIS et pgvector), l'application "
        "<b>Archipel41</b>, et le proxy <b>Caddy</b> qui obtient et renouvelle automatiquement un certificat HTTPS Let's Encrypt.")
    if server_verified:
        d.note(server_verified, "Vérifié avant livraison")
    d.sec("Choisir un serveur et un nom de domaine")
    d.table(["Élément", "Recommandation"], [
        ["Serveur", "Un VPS Linux chez l'hébergeur de votre choix (OVHcloud, Scaleway, Infomaniak, Hetzner…) – de préférence situé en France ou dans l'UE"],
        ["Taille", "2 processeurs virtuels, 4 Go de mémoire, 40 Go de disque au minimum (prévoir plus selon le volume de documents)"],
        ["Système", "Ubuntu Server 24.04 LTS ou Debian 12"],
        ["Nom de domaine", "Un sous-domaine de l'agence, par ex. <code>archipel41.monagence.fr</code>"],
        ["Ports ouverts", "22 (administration SSH), 80 et 443 (HTTP/HTTPS). Aucun autre : la base de données n'est jamais exposée"],
    ], [22, 78])
    d.sec("Faire pointer le domaine vers le serveur")
    d.steps("Relevez l'adresse IP publique du serveur dans l'espace client de l'hébergeur (par ex. <code>203.0.113.10</code>).",
            "Chez le gestionnaire du nom de domaine, créez un enregistrement DNS de type <b>A</b> : nom <code>archipel41</code>, valeur = l'adresse IP du serveur.",
            "Attendez la propagation (de quelques minutes à quelques heures). Vérifiez depuis votre poste :")
    d.pre("nslookup archipel41.monagence.fr")
    d.warn("Le certificat HTTPS ne peut être délivré que si le domaine pointe déjà vers le serveur et que les ports 80 et 443 sont "
           "ouverts. Faites cette étape avant l'installation.", "Indispensable")
    d.sec("Se connecter au serveur et installer Docker")
    d.p("Depuis Windows 10/11, ouvrez PowerShell (SSH est inclus) ; sous macOS ou Linux, ouvrez un terminal :")
    d.pre("ssh root@203.0.113.10")
    d.p("Puis, sur le serveur, installez Docker avec le script officiel et vérifiez :")
    d.pre("curl -fsSL https://get.docker.com | sh\ndocker --version\ndocker compose version")
    d.sec("Déposer Archipel41 sur le serveur")
    d.p("Depuis votre poste (pas sur le serveur), envoyez l'archive source :")
    d.pre(f"scp Archipel41-{V}-source.zip root@203.0.113.10:/opt/")
    d.p("Puis, sur le serveur, décompressez-la dans un dossier au nom <b>fixe</b>, <code>/opt/archipel41</code> : "
        "Docker nomme les volumes de données d'après ce dossier, le garder simplifie les mises à jour.")
    d.pre(f"apt-get install -y unzip\ncd /opt && unzip Archipel41-{V}-source.zip\nmv Archipel41-{V}-source archipel41\ncd /opt/archipel41")
    d.sec("Lancer l'installation")
    d.pre("bash scripts/install/install_server.sh")
    d.steps("Le script crée le fichier de configuration <code>.env</code> avec un mot de passe de base de données et une clé de session "
            "<b>aléatoires</b> (jamais affichés).",
            "Il demande le <b>nom de domaine</b> : saisissez par ex. <code>archipel41.monagence.fr</code> puis Entrée.",
            "Il construit et démarre les trois services (de 5 à 15 minutes la première fois).",
            "Il affiche l'adresse à ouvrir : <code>https://archipel41.monagence.fr</code>.")
    d.note("Le fichier <code>.env</code> contient les secrets du serveur : il reste sur le serveur, n'est jamais envoyé par e-mail et "
           "n'est jamais publié. Les clés des services d'IA ne s'y inscrivent pas : elles se saisissent dans l'application "
           "(Paramètres › Intelligence artificielle) et sont chiffrées en base.", "Secrets")
    d.sec("Vérifier que tout fonctionne")
    d.pre("docker compose ps                 # trois services « running » (db « healthy »)\n"
          "docker compose logs -f app        # journal de l'application (Ctrl+C pour quitter)\n"
          "curl -s https://archipel41.monagence.fr/api/health")
    d.p("La dernière commande doit répondre <code>{\"status\":\"ok\", …, \"mode\":\"server\"}</code>.")
    d.sec("Créer l'agence et les comptes")
    d.steps("Ouvrez <code>https://archipel41.monagence.fr</code> : le cadenas du navigateur confirme le HTTPS.",
            "Choisissez <b>Créer mon agence</b> : vous devenez administrateur du serveur.",
            "Dans <b>Équipe › Nouveau collaborateur</b>, créez un compte par personne avec le rôle adapté "
            "(Administrateur, Gestionnaire, Collaborateur, Lecteur). Communiquez à chacun son e-mail et son mot de passe initial de vive voix.",
            "Pour un partenaire extérieur (BET, entreprise), utilisez une <b>invitation par code</b> à durée limitée : il n'accède qu'aux projets désignés, jamais aux paramètres.")
    d.sec("Raccorder chaque poste Windows")
    d.steps("Sur le poste, installez l'application (chapitre A : télécharger, vérifier, installer).",
            "Ouvrez <b>Paramètres › Synchronisation</b>.",
            "Saisissez l'adresse du serveur (<code>https://archipel41.monagence.fr</code>), votre e-mail et votre mot de passe du serveur.",
            "Cliquez sur <b>Raccorder ce poste</b>. Le poste adopte l'agence du serveur ; ses données locales existantes lui sont envoyées.",
            "Cliquez sur <b>Synchroniser maintenant</b> : l'état indique le nombre d'éléments envoyés et reçus.")
    d.tip("Testez la synchronisation à deux : créez un projet sur le poste 1, synchronisez, puis synchronisez le poste 2 – le projet y apparaît. "
          "Modifiez le même champ sur les deux postes hors connexion : le conflit est détecté et vous est présenté, jamais tranché au hasard.",
          "Test d'équipe")
    d.p("Les téléphones et les postes sans installation utilisent simplement le navigateur à la même adresse ; l'interface s'adapte à l'écran "
        "et peut être ajoutée à l'écran d'accueil (application web).")
    d.sec("Sauvegardes")
    d.p("Deux niveaux complémentaires, à mettre en place dès le premier jour :")
    d.ul("<b>Dans l'application</b> : <b>Paramètres › Sauvegardes › Sauvegarder maintenant</b> (administrateur) produit un ZIP "
         "(données + fichiers, avec empreintes). Téléchargez-le et conservez-le hors du serveur.",
         "<b>Sur le serveur</b> : une copie quotidienne de la base et des fichiers (commandes ci-dessous), à copier ensuite vers un "
         "stockage externe (autre serveur, NAS de l'agence, stockage objet de l'hébergeur).")
    d.pre("cd /opt/archipel41\n"
          "mkdir -p /opt/sauvegardes\n"
          "docker compose exec -T db sh -c 'pg_dump -U \"$POSTGRES_USER\" -Fc \"$POSTGRES_DB\"' \\\n"
          "  > /opt/sauvegardes/base-$(date +%F).dump\n"
          "docker compose exec -T app tar -C /data -czf - . > /opt/sauvegardes/fichiers-$(date +%F).tar.gz")
    d.p("Pour l'automatiser chaque nuit à 2 h, enregistrez ces lignes dans <code>/opt/sauvegarde_archipel41.sh</code>, puis "
        "<code>crontab -e</code> et ajoutez :")
    d.pre("0 2 * * * bash /opt/sauvegarde_archipel41.sh")
    d.warn("Une sauvegarde qui n'a jamais été restaurée n'est pas une sauvegarde. Une fois par trimestre, restaurez le ZIP de l'application "
           "sur un poste de test (Paramètres › Sauvegardes › Restaurer) et vérifiez quelques projets.", "Tester la restauration")
    d.sec("Mettre à jour")
    d.steps("Faites une sauvegarde (section « Sauvegardes »).",
            "Envoyez la nouvelle archive source sur le serveur (section « Déposer Archipel41 », commande <code>scp</code>).",
            "Sur le serveur, décompressez-la à part, puis recopiez-la sur le dossier existant. Le fichier <code>.env</code> "
            "(les secrets du serveur) n'est pas dans l'archive : il est conservé.",
            "Reconstruisez et redémarrez : les données restent dans les volumes Docker, les migrations de la base s'appliquent automatiquement.")
    d.pre("cd /opt && rm -rf maj && mkdir maj && cd maj && unzip -q ../Archipel41-X.Y.Z-source.zip\n"
          "cp -a Archipel41-X.Y.Z-source/. /opt/archipel41/\n"
          "cd /opt/archipel41 && docker compose up -d --build")
    d.warn("Ne lancez jamais <code>docker compose down -v</code> : l'option <code>-v</code> supprime les volumes, donc la base et les fichiers.",
           "Attention")

    # ------------------------------------------------------------------ D
    d.part("En cas de problème")
    d.table(["Symptôme", "Cause probable", "Solution"], [
        ["« Windows a protégé votre ordinateur »", "Installateur non signé", "Informations complémentaires › Exécuter quand même"],
        ["L'empreinte SHA-256 ne correspond pas", "Téléchargement incomplet", "Supprimer et télécharger à nouveau"],
        ["Le navigateur signale un certificat invalide", "Le domaine ne pointait pas vers le serveur lors du démarrage, ou ports 80/443 fermés",
         "Vérifier le DNS (<code>nslookup</code>) et le pare-feu de l'hébergeur, puis <code>docker compose restart proxy</code>"],
        ["<code>docker compose ps</code> : db non « healthy »", "Mémoire ou disque insuffisant", "<code>docker compose logs db</code> ; agrandir le serveur"],
        ["Erreur 429 « Too Many Requests » pendant l'installation", "Limite de téléchargement anonyme de Docker Hub atteinte",
         "Attendre une heure et relancer, ou <code>docker login</code> avec un compte Docker gratuit"],
        ["Le poste ne se raccorde pas", "Adresse sans <code>https://</code>, ou mauvais compte", "Saisir l'adresse complète ; tester l'adresse dans le navigateur du poste"],
        ["Mot de passe administrateur perdu", "—", "Serveur : <code>docker compose exec app python /app/scripts/install/reset_admin_password.py --email votre@adresse.fr</code> ; poste Windows : <code>reinitialiser_mot_de_passe.bat</code> (guide d'installation)"],
        ["Message avec une référence E-XXXXXX", "Erreur enregistrée", "Historique › Erreurs et diagnostic ; communiquer la référence au prestataire"],
    ], [30, 30, 40])
    d.sec("Ce qui demande encore une action de l'agence")
    d.ul("Premier test de l'installateur sur un vrai poste Windows (chapitre A).",
         "Synchronisation Outlook et Google Agenda : nécessite l'enregistrement d'une application OAuth au nom de l'agence (Microsoft Entra, Google Cloud). "
         "Sans cet enregistrement, l'agenda interne fonctionne, mais pas la connexion aux agendas externes.",
         "Signature de l'installateur par un certificat d'éditeur (supprime l'alerte SmartScreen) – facultatif, payant.",
         "Choix de l'hébergeur et du nom de domaine du serveur central.")
    return d
