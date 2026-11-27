"""GUIDE D'INSTALLATION ET DE DÉMARRAGE D'ARCHIPEL41."""
from layout import Doc


def build() -> Doc:
    d = Doc("Guide d'installation et de démarrage d'Archipel41",
            "Installer, configurer, sauvegarder et mettre à jour Archipel41 – sans connaissance en programmation.", "Guide d'installation")

    d.part("Avant de commencer")
    d.p("Ce guide accompagne pas à pas l'installation d'Archipel41 sur un ordinateur Windows, sa configuration initiale "
        "et son entretien (sauvegardes, mises à jour, désinstallation). Il ne suppose aucune connaissance en informatique : "
        "chaque opération est décrite clic par clic.")
    d.note("Les captures d'écran de ce guide sont des captures réelles de l'interface d'Archipel41 version 1.0. "
           "L'interface est strictement identique dans l'application Windows et dans la version web. "
           "Les écrans propres à Windows (assistant d'installation, alerte SmartScreen) sont décrits en texte : ils dépendent "
           "de votre version de Windows et n'ont pas été capturés.", "À propos des illustrations")

    d.sec("Les fichiers livrés")
    d.p("Le dossier de livraison <b>ARCHIPEL41</b> contient :")
    d.table(["Fichier ou dossier", "Rôle", "Pour qui ?"], [
        ["<code>desktop/build/dist/Archipel41-Setup-1.2.0-x64.exe</code>", "Installateur Windows (≈ 150 Mo). C'est le fichier à utiliser dans la grande majorité des cas.", "Chaque poste de l'agence"],
        ["<code>desktop/build/dist/Archipel41-Portable-1.2.0-x64.exe</code>", "Version portable : se lance sans installation (clé USB, poste sans droits d'administration).", "Usage ponctuel"],
        ["<code>desktop/build/dist/SHA256SUMS.txt</code>", "Empreintes permettant de vérifier que les fichiers n'ont pas été altérés.", "Responsable informatique"],
        ["<code>docs/GUIDE_INSTALLATION_ARCHIPEL41.pdf</code>", "Le présent guide.", "Tous"],
        ["<code>docs/GUIDE_UTILISATION_ARCHIPEL41.pdf</code>", "Manuel d'utilisation, module par module.", "Tous"],
        ["<code>docs/DOCUMENTATION_TECHNIQUE.pdf</code>", "Architecture, API, sécurité, tests, construction.", "Prestataire informatique"],
        ["<code>docker-compose.yml</code>, <code>.env.example</code>", "Installation du serveur central partagé (optionnel).", "Prestataire informatique"],
        ["<code>web/</code>, <code>desktop/</code>, <code>ai/</code>, <code>database/</code>, <code>scripts/</code>, <code>tests/</code>", "Code source complet, scripts et tests.", "Prestataire informatique"],
    ], [42, 40, 18])

    d.sec("Les deux façons d'utiliser Archipel41")
    d.table(["", "Application Windows (poste seul)", "Avec un serveur central (travail en équipe)"], [
        ["Installation", "L'installateur suffit : aucune autre installation n'est nécessaire.", "Un serveur (ordinateur ou hébergement) fait tourner Archipel41 et PostgreSQL ; chaque poste installe l'application Windows ou utilise le navigateur."],
        ["Données", "Conservées sur le poste, dans votre profil Windows.", "Base centrale partagée + copie locale sur chaque poste Windows."],
        ["Hors connexion", "Toujours disponible.", "Chaque poste continue de fonctionner ; les modifications sont synchronisées au retour du réseau."],
        ["Partage entre collègues", "Non : le stockage local seul ne permet pas de partager des données entre appareils.", "Oui, avec détection et résolution des conflits."],
    ], [18, 41, 41])
    d.tip("Pour démarrer, installez simplement l'application Windows sur votre poste : vous pourrez raccorder plus tard ce poste à un "
          "serveur central ; vos données locales seront alors envoyées au serveur.", "Conseil")

    d.part("Prérequis informatiques")
    d.table(["Élément", "Minimum", "Recommandé"], [
        ["Système", "Windows 10 64 bits (version 1909 ou ultérieure)", "Windows 11 64 bits"],
        ["Processeur", "Double cœur 64 bits", "Quatre cœurs ou plus"],
        ["Mémoire vive", "4 Go", "8 Go ou plus"],
        ["Espace disque", "1 Go pour le logiciel + l'espace de vos documents", "10 Go libres"],
        ["Écran", "1366 × 768", "1920 × 1080"],
        ["Connexion Internet", "Facultative (fonctionnement hors ligne)", "Nécessaire pour la météo, l'urbanisme, l'IA en ligne et la synchronisation"],
        ["Droits", "Compte Windows standard (installation pour l'utilisateur courant)", "—"],
    ], [22, 39, 39])
    d.p("Aucun logiciel supplémentaire n'est requis : le moteur local (Python), la base de données (SQLite) et la reconnaissance de "
        "texte des documents scannés (OCR Tesseract, langues française et anglaise) sont inclus dans l'installateur.")
    d.note("Seul l'ancien format Word 97-2003 (<code>.doc</code>) nécessite LibreOffice (gratuit) pour être analysé. "
           "Sans LibreOffice, enregistrez ces fichiers au format <code>.docx</code> depuis Word avant de les importer.", "Format .doc")
    d.h3("Adresses Internet utilisées (pour votre pare-feu)")
    d.table(["Service", "Adresse", "Clé nécessaire ?"], [
        ["Prévisions météo", "api.open-meteo.com", "Non"],
        ["Géocodage des adresses", "api-adresse.data.gouv.fr", "Non"],
        ["Cadastre et Géoportail de l'Urbanisme", "apicarto.ign.fr", "Non"],
        ["Risques naturels et technologiques", "georisques.gouv.fr", "Non"],
        ["Légifrance (code de l'urbanisme)", "oauth.piste.gouv.fr, api.piste.gouv.fr", "Oui – identifiants PISTE gratuits"],
        ["IA Claude (facultatif)", "api.anthropic.com", "Oui – clé API"],
        ["IA Mistral / OpenAI (facultatif)", "api.mistral.ai / api.openai.com", "Oui – clé API"],
    ], [38, 40, 22])

    d.part("Télécharger et installer sur Windows")
    d.sec("Télécharger l'installateur")
    d.steps("Récupérez le fichier <b>Archipel41-Setup-1.2.0-x64.exe</b> (dossier <code>desktop/build/dist</code> de la livraison, ou lien transmis par votre prestataire).",
            "Enregistrez-le dans votre dossier <b>Téléchargements</b>.",
            "Facultatif mais recommandé : vérifiez son empreinte. Ouvrez PowerShell dans le dossier Téléchargements et tapez "
            "<code>Get-FileHash .\\Archipel41-Setup-1.2.0-x64.exe</code> ; le résultat doit être identique à la ligne correspondante de <code>SHA256SUMS.txt</code>.")
    d.sec("Lancer l'installation")
    d.steps("Double-cliquez sur <b>Archipel41-Setup-1.2.0-x64.exe</b>.",
            "Si Windows affiche « <b>Windows a protégé votre ordinateur</b> » (SmartScreen), cliquez sur <b>Informations complémentaires</b> puis sur <b>Exécuter quand même</b>. "
            "Ce message apparaît car l'installateur de cette version n'est pas signé numériquement (voir l'encadré ci-dessous).",
            "Lisez les conditions d'utilisation puis cliquez sur <b>J'accepte</b>.",
            "Si l'assistant le demande, choisissez <b>Pour moi uniquement</b> (recommandé : aucun droit d'administrateur nécessaire).",
            "Conservez le dossier d'installation proposé (<code>C:\\Users\\<i>vous</i>\\AppData\\Local\\Programs\\Archipel41</code>) ou choisissez-en un autre, puis cliquez sur <b>Installer</b>.",
            "Patientez une à deux minutes pendant la copie des fichiers.",
            "Laissez cochée la case <b>Lancer Archipel41</b> et cliquez sur <b>Fermer</b>.")
    d.warn("Pour éviter l'alerte SmartScreen, l'installateur doit être signé avec un certificat de signature de code (acheté auprès d'une "
           "autorité de certification). La procédure de signature est décrite dans la documentation technique. Votre antivirus peut aussi "
           "demander une confirmation la première fois que le moteur local (<code>python.exe</code>, dans le dossier d'Archipel41) démarre : autorisez-le.",
           "Installateur non signé")
    d.p("À l'issue de l'installation, vous trouvez :")
    d.ul("une icône <b>Archipel41</b> sur le Bureau ;",
         "une entrée <b>Archipel41</b> dans le menu Démarrer (tapez « Archipel » dans la recherche) ;",
         "une entrée <b>Archipel41</b> dans <b>Paramètres › Applications</b>, pour la désinstallation.")
    d.sec("Version portable")
    d.p("La version portable <b>Archipel41-Portable-1.2.0-x64.exe</b> se lance par un double-clic, sans installation. Son démarrage est un peu plus long "
        "(décompression à chaque lancement). Par défaut, ses données sont rangées dans votre profil Windows comme la version installée. "
        "Pour garder les données à côté de l'exécutable (sur une clé USB par exemple), créez un dossier nommé <code>Archipel41-data</code> dans le même dossier que l'exécutable.")

    d.part("Premier démarrage et configuration initiale")
    d.sec("Ouvrir Archipel41")
    d.steps("Double-cliquez sur l'icône <b>Archipel41</b> du Bureau.",
            "Un écran vert « Démarrage du moteur local… » s'affiche quelques secondes (de 5 à 20 secondes au premier lancement, le temps de créer la base de données).",
            "La fenêtre d'Archipel41 s'ouvre : c'est une application indépendante du navigateur.")
    d.img("01_premier_demarrage", "Premier démarrage : choix entre la création de votre agence et l'exploration de la démonstration.")
    d.sec("Créer l'agence et le compte administrateur")
    d.p("Le premier compte créé est <b>administrateur</b> : il peut créer les autres utilisateurs, régler les paramètres et gérer les sauvegardes.")
    d.steps("Restez sur l'onglet <b>Créer mon agence</b>.",
            "Saisissez le <b>nom de l'agence</b> (obligatoire), puis, si vous le souhaitez, son SIRET et son adresse.",
            "Saisissez le <b>nom</b> et l'<b>adresse e-mail</b> de l'administrateur : l'e-mail servira d'identifiant de connexion.",
            "Choisissez un <b>mot de passe</b> d'au moins 10 caractères mélangeant au moins trois types de caractères (minuscules, majuscules, chiffres, symboles), puis confirmez-le.",
            "Cliquez sur <b>Créer l'agence et me connecter</b>.")
    d.img("02_creation_agence", "Formulaire de création de l'agence et du compte administrateur.")
    d.warn("Notez votre mot de passe dans un gestionnaire de mots de passe. En cas d'oubli, un administrateur peut le réinitialiser "
           "(voir « Résolution des problèmes »). Ne communiquez jamais un mot de passe par e-mail.", "Mot de passe")
    d.p("Vous arrivez sur le <b>tableau de bord</b>, vide pour l'instant :")
    d.img("03_tableau_de_bord_vide", "Tableau de bord d'une agence nouvellement créée.")
    d.sec("Explorer la démonstration (facultatif)")
    d.p("Le bouton <b>Explorer la démonstration</b> (écran de bienvenue) ou l'appel <b>Créer l'espace de démonstration</b> créent une "
        "<b>agence fictive distincte</b> (« [DÉMO] Atelier Démo Architectes ») avec un projet complet : devis réels analysés, planning, rendez-vous, finances. "
        "Ses comptes sont <code>demo@archipel41.demo</code> (administrateur), <code>claire.martin@archipel41.demo</code> (cheffe de projet), "
        "<code>hugo.bernard@archipel41.demo</code> (collaborateur) et <code>lea.petit@archipel41.demo</code> (lecteur), avec le mot de passe que vous choisissez.")
    d.note("Les données de démonstration ne se mélangent jamais avec les vôtres : elles appartiennent à une autre agence, un bandeau orange "
           "« ESPACE DE DÉMONSTRATION » est affiché en permanence et chaque rapport porte la mention « DONNÉES DE DÉMONSTRATION ». "
           "La météo et l'urbanisme y fonctionnent en mode simulé, clairement signalé.", "Séparation des données")
    d.sec("Ajouter les collaborateurs")
    d.steps("Cliquez sur <b>Paramètres</b> (en bas à gauche) puis sur l'onglet <b>Utilisateurs et permissions</b>.",
            "Cliquez sur <b>+ Utilisateur</b>.",
            "Renseignez le nom, l'e-mail, le <b>rôle</b> et un mot de passe initial, puis <b>Enregistrer</b>.",
            "Communiquez oralement le mot de passe initial au collaborateur ; il pourra le changer dans <b>Paramètres › Mon compte</b>.")
    d.img("04_ajout_utilisateur", "Ajout d'un utilisateur avec le rôle « Chef de projet ».")
    d.table(["Rôle", "Peut…"], [
        ["Administrateur", "tout faire, y compris gérer les utilisateurs, les paramètres, les sauvegardes et le journal d'audit"],
        ["Chef de projet", "consulter, créer, modifier, supprimer et <b>valider</b> (devis, propositions d'ajustement du planning)"],
        ["Collaborateur", "consulter, créer et modifier (pas de suppression ni de validation)"],
        ["Lecture seule", "consulter uniquement"],
    ], [24, 76])

    d.part("Configuration des services")
    d.sec("Base de données")
    d.p("<b>Sur un poste Windows, il n'y a rien à configurer</b> : Archipel41 crée automatiquement sa base locale (SQLite) au premier démarrage, "
        "dans <code>%APPDATA%\\Archipel41\\data\\archipel41.db</code>. Les documents importés sont rangés dans <code>%APPDATA%\\Archipel41\\data\\files</code>. "
        "Le menu <b>Fichier › Ouvrir le dossier des données</b> de l'application ouvre ce dossier.")
    d.p("La base centrale partagée (PostgreSQL avec PostGIS et pgvector) concerne uniquement le <b>serveur central</b> ; son installation est décrite au chapitre 6.")
    d.sec("Intelligence artificielle")
    d.p("Archipel41 fonctionne <b>sans fournisseur d'IA</b> : extraction et comparaison des devis par moteur de règles, recherche documentaire locale, "
        "conclusions et synthèses automatiques. Un fournisseur d'IA ajoute la rédaction en langage naturel (conclusions argumentées, réponses de l'assistant, synthèses).")
    d.table(["Fournisseur", "Où obtenir la clé ?", "Données envoyées hors de l'agence ?"], [
        ["Anthropic – Claude (recommandé)", "console.anthropic.com › API Keys › Create Key (clé commençant par <code>sk-ant-</code>)", "Oui (fournisseur externe)"],
        ["Mistral AI (France)", "console.mistral.ai › API Keys", "Oui (fournisseur externe)"],
        ["OpenAI", "platform.openai.com › API keys", "Oui (fournisseur externe)"],
        ["Ollama (modèle local)", "Aucune clé : installez Ollama (ollama.com) sur un poste ou un serveur de l'agence", "Non"],
    ], [26, 50, 24])
    d.steps("Ouvrez <b>Paramètres › Intelligence artificielle</b> (compte administrateur).",
            "Choisissez le <b>fournisseur</b>. Pour Mistral, OpenAI ou Ollama, choisissez « Compatible OpenAI » puis le <b>préréglage</b> correspondant.",
            "Collez la <b>clé API</b> dans le champ prévu. Elle est chiffrée avant d'être enregistrée et n'est plus jamais affichée en clair.",
            "Réglez la <b>confidentialité</b> : par défaut, les extraits de documents non confidentiels peuvent être transmis ; les documents et projets marqués <b>confidentiels</b> ne sont jamais transmis à un fournisseur externe tant que vous ne cochez pas l'autorisation correspondante.",
            "Cliquez sur <b>Tester la connexion</b> : le message « Connexion réussie » confirme le réglage.")
    d.img("36_parametres_ia", "Paramètres de l'intelligence artificielle (exemple avec Anthropic – Claude).", maxh=150)
    d.warn("Les fournisseurs d'IA facturent leur service à l'usage. Consultez leurs conditions (conservation des données, hébergement, contrat de sous-traitance RGPD) "
           "avant d'autoriser l'envoi de documents confidentiels. Ne saisissez jamais une clé API ailleurs que dans cet écran.", "Coûts et confidentialité")
    d.sec("Météo")
    d.p("La météo des chantiers utilise <b>Open-Meteo</b> (données Météo-France et ECMWF) et la <b>Base Adresse Nationale</b> pour situer le chantier : "
        "<b>aucune clé n'est nécessaire</b>. Il suffit que l'adresse du chantier soit renseignée dans la fiche projet et que le poste ait accès à Internet.")
    d.steps("Ouvrez <b>Paramètres › Météo</b>.", "Laissez les adresses des services proposées par défaut.",
            "Cliquez sur <b>Tester la connexion</b> : chaque service doit afficher ✓.",
            "Le <b>mode démonstration</b> affiche des prévisions simulées, signalées comme telles : ne l'activez pas pour un usage réel.")
    d.img("37_parametres_meteo", "Paramètres de la météo.")
    d.sec("Services urbanistiques")
    d.p("La recherche de parcelles interroge l'<b>API Carto de l'IGN</b> (cadastre et Géoportail de l'Urbanisme), <b>Géorisques</b> et la <b>Base Adresse Nationale</b>, sans clé. "
        "La recherche d'articles du code de l'urbanisme sur <b>Légifrance</b> nécessite des identifiants gratuits de l'API PISTE :")
    d.steps("Créez un compte sur <b>piste.gouv.fr</b>.",
            "Dans « Applications », créez une application et abonnez-la à l'API <b>Légifrance</b> ; acceptez les conditions générales d'utilisation.",
            "Copiez l'<b>identifiant client</b> (client_id) et le <b>secret client</b> (client_secret) de l'application.",
            "Dans Archipel41, ouvrez <b>Paramètres › Urbanisme</b>, collez ces deux valeurs et cliquez sur <b>Enregistrer</b>.")
    d.img("38_parametres_urbanisme", "Paramètres des services urbanistiques.")

    d.part("Synchronisation et serveur central")
    d.sec("Principe")
    d.p("Chaque poste Windows dispose de sa propre base locale et fonctionne hors connexion. Pour travailler à plusieurs sur les mêmes projets, l'agence "
        "installe un <b>serveur central</b>. Les postes s'y synchronisent automatiquement (toutes les 5 minutes par défaut) dans les deux sens : "
        "envoi des modifications locales, réception des modifications des collègues, transfert des fichiers vérifié par empreinte SHA-256. "
        "Les navigateurs (ordinateur, tablette, smartphone) se connectent directement au serveur central ; hors connexion, ils conservent les pages déjà consultées "
        "et mettent les modifications en file d'attente.")
    d.p("Si un même élément est modifié à deux endroits entre deux synchronisations, Archipel41 <b>ne choisit jamais à votre place</b> : un conflit est créé "
        "et vous décidez de garder votre version ou celle du serveur (<b>Paramètres › Synchronisation</b>).")
    d.sec("Installer le serveur central")
    d.p("Cette opération est généralement confiée à votre prestataire informatique. Elle nécessite un ordinateur ou un serveur Linux (ou un hébergement) "
        "avec Docker, accessible par les postes de l'agence, et de préférence un nom de domaine.")
    d.steps("Copiez le dossier ARCHIPEL41 sur le serveur.",
            "Exécutez <code>./scripts/install/install_server.sh</code> : le script crée le fichier de configuration <code>.env</code> avec des mots de passe aléatoires, demande le nom de domaine, puis démarre la base PostgreSQL (PostGIS + pgvector), Archipel41 et un proxy HTTPS (certificat Let's Encrypt automatique).",
            "Ouvrez <code>https://<i>votre-domaine</i></code> dans un navigateur et créez l'agence et l'administrateur (chapitre 4).",
            "Créez les comptes des collaborateurs sur le serveur.")
    d.pre("cp .env.example .env      # puis modifier mots de passe et domaine\ndocker compose up -d --build")
    d.sec("Raccorder un poste Windows au serveur")
    d.steps("Sur le poste, ouvrez <b>Paramètres › Synchronisation</b> (compte administrateur du poste).",
            "Saisissez l'<b>adresse du serveur</b> (ex. <code>https://archipel41.monagence.fr</code>), l'<b>e-mail</b> et le <b>mot de passe</b> de votre compte sur le serveur, et l'intervalle de synchronisation.",
            "Cliquez sur <b>Raccorder ce poste</b>. Le poste adopte l'agence du serveur ; ses données locales existantes lui seront envoyées. Reconnectez-vous si l'application le demande.",
            "Cliquez sur <b>Synchroniser maintenant</b> : l'état indique le nombre d'éléments envoyés et reçus.")
    d.img("39_parametres_synchronisation", "Écran de synchronisation : état, raccordement, conflits et file d'attente hors connexion.", maxh=160)
    d.note("Le badge en haut de l'écran indique l'état : « En ligne », « Hors ligne » (avec le nombre de modifications en attente) ou « Synchronisé ». "
           "Un clic sur ce badge lance une synchronisation immédiate.", "Indicateur de connexion")

    d.part("Sauvegarde et restauration")
    d.sec("Créer une sauvegarde")
    d.steps("Ouvrez <b>Paramètres › Sauvegardes</b> (administrateur).",
            "Cliquez sur <b>Sauvegarder maintenant</b>.",
            "Enregistrez l'archive ZIP proposée sur un support externe (disque USB, NAS, espace de stockage de l'agence).")
    d.img("40_sauvegardes", "Création et liste des sauvegardes.")
    d.p("L'archive contient toutes les données de l'agence (projets, devis, agenda, finances, paramètres, historique), les fichiers des documents et un manifeste "
        "avec des empreintes SHA-256 qui permettent de détecter toute altération. Les dix dernières sauvegardes sont aussi conservées dans "
        "<code>%APPDATA%\\Archipel41\\data\\backups</code>.")
    d.tip("Sauvegardez au moins une fois par semaine sur un support externe, et toujours avant une mise à jour. "
          "Sur le serveur central, planifiez <code>scripts/backup/backup_server.sh</code> chaque nuit (sauvegarde PostgreSQL + fichiers, conservation 30 jours).", "Rythme recommandé")
    d.sec("Restaurer une sauvegarde")
    d.steps("Ouvrez <b>Paramètres › Sauvegardes</b>, rubrique <b>Restaurer une sauvegarde</b>.",
            "Cliquez sur <b>Choisir une archive…</b> et sélectionnez le fichier ZIP. Archipel41 vérifie son intégrité et affiche son contenu (agence, date, nombre d'enregistrements et de fichiers).",
            "Tapez <b>RESTAURER</b> dans le champ de confirmation, puis cliquez sur <b>Restaurer</b>.",
            "Reconnectez-vous lorsque l'application le demande.")
    d.img("41_restauration", "Vérification d'une archive avant restauration.")
    d.warn("La restauration remplace toutes les données actuelles de l'agence. Archipel41 crée automatiquement une sauvegarde de sécurité juste avant "
           "(fichier se terminant par « _avant_restauration.zip »). Une archive modifiée ou corrompue est refusée.")
    d.p("Sur le serveur central : <code>./scripts/restore/restore_server.sh &lt;fichier.dump&gt; &lt;fichiers.tar.gz&gt;</code>.")

    d.part("Mise à jour")
    d.steps("Effectuez une sauvegarde (chapitre 7).",
            "Fermez Archipel41.",
            "Lancez le nouvel installateur <b>Archipel41-Setup-<i>version</i>-x64.exe</b> et suivez les mêmes étapes que pour la première installation.",
            "Relancez Archipel41 : la base de données est mise à niveau automatiquement au démarrage. Vos données et paramètres sont conservés.")
    d.p("Serveur central : <code>docker compose up -d --build</code> après remplacement des fichiers ; les migrations de la base s'appliquent automatiquement.")
    d.note("Archipel41 ne se met pas à jour tout seul : chaque mise à jour est une décision de l'agence. La version installée est indiquée dans <b>Paramètres › Système</b>.")

    d.part("Résolution des problèmes courants")
    d.table(["Symptôme", "Cause probable", "Solution"], [
        ["« Windows a protégé votre ordinateur »", "Installateur non signé", "Informations complémentaires › Exécuter quand même (chapitre 3)."],
        ["Message « Impossible de démarrer le moteur local »", "Antivirus bloquant <code>python.exe</code>, dossier d'installation incomplet", "Autorisez Archipel41 dans l'antivirus ; réinstallez. Consultez le journal (Fichier › Ouvrir le dossier des journaux : <code>desktop.log</code>, <code>backend-console.log</code>, <code>archipel41.log</code>)."],
        ["Fenêtre blanche", "Affichage interrompu", "Menu <b>Affichage › Recharger</b> (Ctrl+R)."],
        ["« Identifiants incorrects »", "Erreur de saisie, majuscules", "Vérifiez la touche Verr. Maj. Après 5 échecs, la connexion est bloquée 5 minutes."],
        ["Mot de passe administrateur oublié", "—", "Fermez Archipel41, puis double-cliquez sur <code>resources\\backend\\scripts\\install\\reinitialiser_mot_de_passe.bat</code> (dans le dossier d'installation) et suivez les instructions."],
        ["Un devis scanné n'est pas lu", "Scan de mauvaise qualité", "Scannez en 300 ppp, bien droit ; à défaut, saisissez ou corrigez les lignes dans l'écran de vérification."],
        ["« Format Word 97-2003 (.doc) »", "LibreOffice absent", "Installez LibreOffice ou enregistrez le fichier en .docx."],
        ["« Service météo injoignable »", "Pas d'accès Internet ou pare-feu", "Vérifiez la connexion ; autorisez api.open-meteo.com et api-adresse.data.gouv.fr ; testez dans Paramètres › Météo."],
        ["Urbanisme : « Données indisponibles »", "Service public momentanément indisponible ou commune sans document numérisé", "Réessayez plus tard ; vérifiez sur le Géoportail de l'Urbanisme ; les informations manquantes sont toujours listées, jamais inventées."],
        ["« Clé API refusée »", "Clé erronée ou expirée", "Créez une nouvelle clé chez le fournisseur et saisissez-la dans Paramètres › Intelligence artificielle."],
        ["« Serveur injoignable » (synchronisation)", "Réseau ou serveur arrêté", "Continuez à travailler : les modifications sont conservées et envoyées au retour du réseau."],
        ["« Conflit de modification »", "Élément modifié par un collègue en même temps", "Rechargez la page ; pour la synchronisation, choisissez la version à conserver dans Paramètres › Synchronisation."],
    ], [26, 28, 46])

    d.part("Désinstallation")
    d.steps("Effectuez une dernière sauvegarde si vous souhaitez conserver vos données.",
            "Fermez Archipel41.",
            "Ouvrez <b>Paramètres Windows › Applications › Applications installées</b>, cherchez <b>Archipel41</b>, cliquez sur <b>…</b> puis <b>Désinstaller</b>.",
            "Une question vous est posée : « Souhaitez-vous également supprimer vos données Archipel41 ? ». Répondez <b>Non</b> pour les conserver (recommandé si vous réinstallez), <b>Oui</b> pour tout effacer.",
            "Les raccourcis du Bureau et du menu Démarrer sont supprimés.")
    d.note("Si vous avez répondu « Non », vos données restent dans <code>%APPDATA%\\Archipel41</code>. Vous pouvez supprimer ce dossier manuellement plus tard. "
           "La version portable se supprime simplement en effaçant le fichier exécutable (et le dossier <code>Archipel41-data</code> le cas échéant).")
    return d
