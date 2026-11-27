"""PROPOSITIONS D'ÉVOLUTION – ARCHIPEL41 (fonctionnalités, environnement, feuille de route)."""
import html
from pathlib import Path

from layout import Doc

E = {"Faible": '<span class="badge ok">Faible</span>', "Moyen": '<span class="badge mid">Moyen</span>', "Élevé": '<span class="badge ko">Élevé</span>'}
V = {"Forte": '<span class="badge ok">Forte</span>', "Moyenne": '<span class="badge mid">Moyenne</span>'}


def rows(items):
    return [[f"<b>{n}</b>", why, V[v], E[e]] for n, why, v, e in items]


def build() -> Doc:
    d = Doc("Propositions d'évolution d'Archipel41", "Nouvelles fonctionnalités, environnement technique et feuille de route.", "Propositions d'évolution")
    H = ["Proposition", "Bénéfice pour l'agence", "Valeur", "Effort"]
    W = [24, 54, 11, 11]

    d.part("Synthèse")
    d.p("Archipel41 1.0 couvre l'essentiel du quotidien d'une agence : projets et chantiers, analyse et comparaison des devis, agenda, planning et météo, "
        "urbanisme, assistant IA, documents, annuaire, finances et rapports. Ce document propose les évolutions les plus utiles, classées par priorité, "
        "ainsi que l'environnement technique (hébergement, sécurité, outils connectés, organisation) qui permettra de les déployer sereinement.")
    d.h3("Les trois priorités recommandées")
    d.steps("<b>Fiabiliser et déployer</b> : test sur un vrai Windows, signature et mise à jour automatique de l'installateur, serveur hébergé en France avec sauvegardes hors site.",
            "<b>Connecter l'outil au quotidien de l'agence</b> : synchronisation Outlook / Google Agenda, double authentification, connexion avec le compte Microsoft ou Google.",
            "<b>Capitaliser sur le comparateur de devis</b> : base de prix de l'agence, demande de précisions automatique aux entreprises, puis suivi des temps et facturation des honoraires.")
    d.note("Valeur : bénéfice attendu pour l'agence. Effort : charge de développement relative — <b>faible</b> (quelques jours), <b>moyen</b> (une à trois semaines), "
           "<b>élevé</b> (plus d'un mois). Les coûts sont indicatifs et hors taxes.", "Lecture des tableaux")

    d.part("Nouvelles fonctionnalités")
    d.sec("Fiabiliser et faciliter l'adoption")
    d.table(H, rows([
        ("Signature numérique de l'installateur", "Supprime l'alerte « Windows a protégé votre ordinateur ». Certificat de 200 à 400 € par an.", "Forte", "Faible"),
        ("Mise à jour automatique", "L'application détecte les nouvelles versions et s'installe en un clic.", "Forte", "Moyen"),
        ("Version web hébergée", "Un lien unique pour toute l'équipe, sur ordinateur, tablette et téléphone.", "Forte", "Moyen"),
        ("Assistant de prise en main", "Premier lancement guidé : créer un client, un projet, importer un devis.", "Moyenne", "Faible"),
    ]), W)
    d.sec("Gagner du temps au quotidien")
    d.table(H, rows([
        ("Synchronisation Outlook / Google Agenda", "Les rendez-vous apparaissent sur le téléphone et dans l'agenda habituel.", "Forte", "Moyen"),
        ("Envoi d'e-mails depuis l'application", "Comptes rendus, comparatifs et demandes aux entreprises envoyés en un clic avec modèles.", "Forte", "Moyen"),
        ("Demande de précisions automatique", "Le comparateur rédige pour chaque entreprise le courrier listant postes non renseignés, prix anormaux et anomalies.", "Forte", "Faible"),
        ("Comptes rendus de chantier sur tablette", "Photos géolocalisées, réserves annotées sur plan, signature, PDF envoyé automatiquement.", "Forte", "Élevé"),
        ("Dictée vocale", "Dicter un compte rendu ou une observation ; l'IA le met en forme.", "Moyenne", "Moyen"),
        ("Modèles de projets", "Projet type (maison, équipement public…) avec phases, lots et planning préparés.", "Moyenne", "Faible"),
    ]), W)
    d.sec("Devis, marchés et chantier")
    d.table(H, rows([
        ("Base de prix de l'agence", "Chaque devis validé enrichit une base de prix unitaires pour estimer et détecter les prix anormaux.", "Forte", "Moyen"),
        ("Estimation automatique", "Première estimation par lot dès l'esquisse, à partir des surfaces et de la base de prix.", "Forte", "Moyen"),
        ("Génération du DCE", "DPGF et CCTP de base produits à partir de modèles par lot.", "Moyenne", "Élevé"),
        ("Contrôle des situations de travaux", "Vérification des situations mensuelles, retenue de garantie, révision de prix.", "Forte", "Moyen"),
        ("Réception et levée des réserves", "Réserves par entreprise, photos, relances, procès-verbal signé (phase AOR).", "Forte", "Moyen"),
    ]), W)
    d.sec("Pilotage de l'agence")
    d.table(H, rows([
        ("Suivi des temps passés", "Heures par projet et par phase : rentabilité réelle de chaque mission.", "Forte", "Moyen"),
        ("Facturation des honoraires", "Factures par phase selon le contrat, relances, export comptable.", "Forte", "Moyen"),
        ("Tableau de bord de direction", "Chiffre d'affaires prévisionnel, rentabilité, charge de l'équipe à trois mois.", "Forte", "Moyen"),
        ("Espace client en ligne", "Le maître d'ouvrage consulte avancement, comptes rendus et documents qui le concernent.", "Moyenne", "Élevé"),
    ]), W)
    d.sec("Outils techniques de l'architecte")
    d.table(H, rows([
        ("Visionneuse de plans", "PDF, DWG, DXF et maquette IFC affichés et annotés dans l'application.", "Moyenne", "Élevé"),
        ("Carte interactive des projets", "Chantiers, parcelles cadastrales et zonage du PLU sur une carte.", "Moyenne", "Moyen"),
        ("Veille réglementaire", "Alerte lorsqu'un PLU concerné par un projet est modifié.", "Moyenne", "Moyen"),
        ("Contrôles RE2020 et accessibilité", "Listes de vérification guidées par type de bâtiment.", "Moyenne", "Moyen"),
    ]), W)

    d.part("Environnement technique")
    HE = ["Proposition", "Pourquoi", "Coût indicatif"]
    WE = [30, 50, 20]
    d.sec("Hébergement")
    d.table(HE, [
        ["<b>Serveur hébergé en France</b> (OVHcloud, Scaleway, Infomaniak)", "Toute l'équipe travaille sur les mêmes données, partout ; conformité RGPD.", "15 à 40 € / mois"],
        ["<b>Nom de domaine de l'agence</b>", "Adresse simple et sécurisée en HTTPS (ex. archipel41.votre-agence.fr).", "≈ 10 € / an"],
        ["<b>Environnement de recette</b>", "Tester les nouvelles versions sans risque pour les données réelles.", "Inclus"],
        ["<b>Supervision</b>", "Alerte e-mail si le serveur ne répond plus ou si le disque est plein.", "Gratuit"],
    ], WE)
    d.sec("Sécurité et sauvegardes")
    d.table(["Proposition", "Pourquoi"], [
        ["<b>Sauvegarde nocturne hors site, chiffrée</b>", "Panne, erreur ou rançongiciel : au pire une journée de travail perdue."],
        ["<b>Test de restauration trimestriel</b>", "Une sauvegarde jamais restaurée n'est pas une garantie."],
        ["<b>Double authentification</b>", "Comptes protégés même en cas de vol de mot de passe."],
        ["<b>Connexion Microsoft 365 / Google</b>", "Un seul mot de passe ; départ d'un collaborateur géré en un clic."],
        ["<b>Registre RGPD et conservation</b>", "Obligations légales : quelles données, combien de temps."],
    ], [32, 68])
    d.sec("Outils connectés")
    d.table(["Outil", "Apport"], [
        ["Outlook / Google Agenda", "Rendez-vous synchronisés sur tous les appareils."],
        ["Messagerie (Outlook, Gmail)", "Devis reçus par e-mail classés automatiquement dans le bon projet."],
        ["OneDrive, Google Drive, Dropbox", "Dossiers existants accessibles sans réimport."],
        ["Comptabilité (Pennylane, QuickBooks, Sage)", "Factures d'honoraires transmises sans ressaisie."],
        ["ArchiCAD, Revit, AutoCAD", "Surfaces et quantités de la maquette reprises pour les estimations."],
        ["Signature électronique (Yousign)", "Marchés, avenants et procès-verbaux signés à distance."],
        ["Chorus Pro", "Factures échangées avec les maîtres d'ouvrage publics."],
    ], [34, 66])
    d.sec("Organisation du développement")
    d.ul("<b>Dépôt GitHub</b> comme point central : code, historique, demandes d'amélioration et anomalies.",
         "<b>Issues GitHub</b> : chaque idée ou problème devient une fiche suivie.",
         "<b>Tests automatiques</b> à chaque modification (déjà présents dans le dépôt : 65 tests, synchronisation, 26 vérifications de bout en bout).",
         "<b>Version de démonstration en ligne</b> pour présenter l'outil sans installation.",
         "<b>Une version par mois</b> : des nouveautés régulières et maîtrisées.")
    d.sec("Environnement au sens écologique")
    d.table(["Proposition", "Bénéfice"], [
        ["Suivi carbone RE2020 par projet", "Indicateurs carbone et énergie suivis de l'esquisse à la livraison, alertes sur les seuils."],
        ["Base de matériaux biosourcés et de réemploi", "Alternatives proposées lors de l'analyse des devis."],
        ["Critère « impact carbone » dans le comparateur", "Choix des offres sur le prix, le délai et l'empreinte environnementale."],
        ["Hébergement sobre", "Serveur alimenté en énergie renouvelable."],
    ], [36, 64])

    d.part("Feuille de route proposée")
    d.table(["Lot", "Contenu", "Durée indicative"], [
        ["<b>Lot 1 – Fondations</b>", "Test Windows réel, release automatique, signature, mise à jour automatique ; serveur en France, recette, sauvegardes hors site, supervision ; double authentification, connexion Microsoft/Google ; synchronisation des agendas ; organisation GitHub.", "4 à 6 semaines"],
        ["<b>Lot 2 – Devis et marchés</b>", "Base de prix, estimation automatique, demande de précisions automatique, contrôle des situations, réception et réserves.", "4 à 6 semaines"],
        ["<b>Lot 3 – Pilotage de l'agence</b>", "Suivi des temps, facturation des honoraires, tableau de bord de direction, export comptable.", "4 semaines"],
        ["<b>Lot 4 – Terrain et clients</b>", "Comptes rendus sur tablette, dictée, e-mails, espace client, signature électronique.", "6 semaines"],
        ["<b>Lot 5 – Outils techniques</b>", "Visionneuse de plans et BIM, carte, veille PLU, RE2020, critère carbone.", "6 à 8 semaines"],
    ], [20, 62, 18])
    d.tip("Le lot 1 conditionne tous les autres : il garantit que l'application s'installe et se met à jour sans difficulté, que les données sont protégées "
          "et que l'équipe peut travailler à plusieurs. Le prompt complet pour le réaliser figure en annexe et dans le fichier "
          "<code>docs/PROMPT_LOT1_ARCHIPEL41.md</code>.", "Pourquoi commencer par le lot 1")

    d.part("Annexe – Prompt du lot 1")
    d.p("À copier tel quel dans Claude Code, ouvert sur le dépôt GitHub d'Archipel41.")
    d.pre((Path(__file__).resolve().parents[1] / "PROMPT_LOT1_ARCHIPEL41.md").read_text(encoding="utf-8"))
    return d
