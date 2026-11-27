"""GUIDE UTILISATEUR – ARCHIPEL41 – GESTION INTELLIGENTE D'UNE AGENCE D'ARCHITECTURE."""
from layout import Doc


def ol(*items):
    return '<ol class="steps">' + "".join(f"<li>{i}</li>" for i in items) + "</ol>"


def ul(*items):
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def build() -> Doc:
    d = Doc("Guide utilisateur – Archipel41", "Gestion intelligente d'une agence d'architecture – manuel pratique, module par module.", "Guide utilisateur")

    # ===================================================================== philosophie
    d.part("Philosophie générale")
    d.p("Archipel41 réunit dans un même outil ce qui, dans une agence, est souvent dispersé entre tableurs, dossiers partagés, agendas et courriels : "
        "les projets et chantiers, les devis des entreprises, les pièces écrites, l'agenda, le planning, l'urbanisme, les finances et les rapports.")
    d.p("Trois principes guident le logiciel :")
    d.ul("<b>L'architecte décide.</b> Archipel41 extrait, calcule, compare et propose ; aucune information extraite n'est validée, aucun planning n'est modifié "
         "et aucune conclusion n'est retenue sans action d'un utilisateur habilité.",
         "<b>Les chiffres sont exacts et traçables.</b> Tous les montants, totaux et taux de TVA sont recalculés par un moteur déterministe (arrondi au centime), "
         "jamais par l'intelligence artificielle. Chaque modification est historisée.",
         "<b>Rien n'est inventé.</b> Une information absente (article de règlement, caractéristique d'un terrain, prestation d'un devis) est signalée comme telle. "
         "L'assistant cite ses sources ; une prestation absente d'un devis n'est jamais confondue avec une prestation expressément exclue.")
    d.p("Archipel41 fonctionne <b>sans intelligence artificielle externe</b> (moteurs de règles et recherche documentaire locale). Lorsqu'un fournisseur d'IA est "
        "configuré, il ajoute la rédaction en langage naturel, dans le respect des règles de confidentialité définies par l'administrateur.")
    d.note("Les captures d'écran de ce manuel sont des captures réelles d'Archipel41. Les exemples utilisent des données fictives : le projet « Maison Martin » "
           "créé pas à pas, et l'espace de démonstration « [DÉMO] Atelier Démo Architectes » (bandeau orange en haut de l'écran).", "Illustrations")

    d.part("Organisation de l'interface")
    d.img("44_tableau_de_bord", "Vue générale : barre latérale des modules, barre supérieure, contenu (espace de démonstration).")
    d.table(["Zone", "Contenu"], [
        ["Barre latérale (gauche)", "Les 11 modules numérotés de 01 à 11, puis <b>Paramètres</b> et votre compte (bouton de déconnexion). Sur tablette et smartphone, elle s'ouvre avec le bouton ☰."],
        ["Sélecteur de projet (haut)", "Choisit le <b>projet actif</b> : les modules Devis, Planning, Finances, Documents, Assistant… s'y rapportent automatiquement."],
        ["Recherche (haut)", "Recherche transversale dans tous les projets, clients, entreprises, devis, tâches, rendez-vous, documents et dans le <b>contenu</b> des documents."],
        ["Badge de connexion", "« En ligne », « Hors ligne » (avec le nombre de modifications en attente) ou « Synchronisé ». Cliquez dessus pour synchroniser."],
        ["Cloche", "Rappels des prochains rendez-vous (une notification Windows s'affiche aussi à l'heure du rappel)."],
        ["Lune / soleil", "Bascule entre mode clair et mode sombre."],
        ["Bouton Assistant", "Ouvre l'assistant IA dans un panneau latéral, depuis n'importe quel écran, dans le contexte du projet actif."],
    ], [26, 74])
    d.img("49_mode_sombre", "Le même tableau de bord en mode sombre.")
    d.h3("Gestes communs à tous les écrans")
    d.ul("Les boutons verts foncés réalisent l'action principale (Enregistrer, Créer, Valider).",
         "Un clic sur une ligne de tableau ouvre l'élément ; les fenêtres se ferment avec <kbd>Échap</kbd>.",
         "Les montants sont exprimés en euros hors taxes (HT), sauf mention TTC.",
         "Si un collègue a modifié le même élément entre-temps, Archipel41 refuse d'écraser son travail et recharge la version à jour (« Conflit de modification »).")

    # ===================================================================== exemple global
    d.part("Exemple suivi dans ce manuel")
    d.p("Camille Durand, architecte et administratrice de l'« Atelier Exemple Architectes », reçoit M. et Mme Martin pour l'extension de leur maison à Nantes. "
        "Nous allons, dans l'ordre : créer le client et les entreprises, créer le projet et son lot gros œuvre, importer trois devis (dont un scanné), "
        "les corriger, les comparer à la DPGF et au CCTP, obtenir une conclusion, planifier le rendez-vous de présentation, préparer le planning, "
        "consulter la météo, analyser la parcelle, interroger l'assistant, enregistrer le marché et générer les rapports.")

    # ===================================================================== modules
    d.part("Module 01 – Tableau de bord")
    d.module(
        "Donner, dès l'ouverture, une vue synthétique de l'activité de l'agence et des points qui demandent une action.",
        "Le matin, en une minute, savoir quels rendez-vous ont lieu, quelles tâches sont en retard, quels devis attendent une vérification et quels budgets dérivent.",
        "Aucune saisie spécifique : le tableau de bord agrège les données des autres modules.",
        ol("Ouvrez <b>Tableau de bord</b> (module 01).",
           "Filtrez si besoin par <b>période</b> (7, 30 ou 90 jours), par <b>projet</b> et par <b>collaborateur</b>.",
           "Lisez la <b>Synthèse du jour</b> (rédigée par l'IA si un fournisseur est configuré, sinon par le moteur de règles) ; cliquez sur <b>Actualiser</b> pour la recalculer.",
           "Traitez les <b>alertes</b> en commençant par les points rouges (priorité haute).",
           "Cliquez sur un projet, un devis ou un rendez-vous pour l'ouvrir."),
        "Dans l'espace de démonstration, le tableau de bord signale le dépassement de 11,5 % du lot charpente, une situation de travaux échue, trois tâches en retard, "
        "les anomalies de calcul d'un devis et un incident « venue d'eau en fond de fouille ».",
        ul("indicateurs : projets actifs, chantiers en cours, devis à vérifier, rendez-vous, tâches prioritaires, alertes ;",
           "listes : alertes, projets avec avancement, budgets (budget actualisé, engagé, facturé, écart), météo des chantiers sur trois jours, prochains rendez-vous, tâches prioritaires, devis en attente, activité récente de l'équipe."),
        ul("Commencez la journée par le tableau de bord et traitez les alertes « haute ».", "Renseignez l'adresse des chantiers pour afficher leur météo."),
        "La météo n'apparaît que pour les projets au statut « Chantier » dont l'adresse a pu être localisée, et nécessite une connexion Internet.")
    d.img("44_tableau_de_bord", "Tableau de bord filtré sur le projet de démonstration.")

    d.part("Module 02 – Projets et chantiers")
    d.module(
        "Centraliser toutes les informations d'une opération : maître d'ouvrage, équipe, phases de la mission, terrain, lots, entreprises, échéances, incidents, documents, avancement.",
        "Disposer d'une fiche unique et à jour, partagée par toute l'équipe, de l'esquisse à la réception.",
        ul("code et nom du projet (obligatoires) ;", "maître d'ouvrage (créé au préalable dans le module 09) ;",
           "adresse du chantier, surface, budget travaux, dates, taux d'honoraires ;", "lots et entreprises attributaires ;", "collaborateurs affectés."),
        "<h3>Créer un projet</h3>" + ol(
            "Ouvrez <b>Projets et chantiers</b> puis cliquez sur <b>Nouveau projet</b>.",
            "Saisissez le <b>code</b> (ex. 26-014) et le <b>nom</b>, choisissez le <b>maître d'ouvrage</b>, puis l'adresse, la surface et le budget.",
            "Cochez <b>Projet confidentiel</b> si l'opération ne doit être visible que de son équipe (et jamais transmise à une IA externe sans autorisation).",
            "Cliquez sur <b>Créer le projet</b> : la fiche s'ouvre, avec les dix phases ESQ, APS, APD, PC, PRO, DCE, ACT, EXE/VISA, DET et AOR.") +
        "<h3>Compléter la fiche</h3>" + ol(
            "Onglet <b>Phases</b> : désactivez les phases hors mission, renseignez dates, statut et avancement, cochez la phase en cours, puis <b>Enregistrer</b>.",
            "Onglet <b>Lots</b> : <b>Ajouter un lot</b> (numéro, désignation, budget, entreprise attributaire, montant du marché, avancement).",
            "Onglet <b>Terrain</b> : références cadastrales, zone du PLU, nature du sol, réseaux, accès ; le bouton <b>Analyser la parcelle</b> ouvre le module Urbanisme.",
            "Onglet <b>Équipe</b> : ajoutez les collaborateurs et leur rôle sur le projet.",
            "Onglet <b>Incidents</b> : <b>Signaler</b> un incident (date, gravité, description, statut, résolution).",
            "Onglet <b>Documents</b> : tous les documents rattachés au projet."),
        "Camille crée le projet « 26-014 – Maison Martin – extension et rénovation » (145 m², budget 95 000 € HT), puis le lot 02 « Gros œuvre » avec un budget de 36 000 € HT.",
        "Une fiche projet complète ; le projet apparaît dans le sélecteur de projet, sur le tableau de bord et dans tous les modules.",
        ul("Choisissez des codes courts et uniques (année-numéro).", "Tenez à jour la phase en cours et l'avancement : ils alimentent le tableau de bord.",
           "Signalez les incidents le jour même, avec photos dans Documents."),
        "La suppression d'un projet est réservée aux chefs de projet et administrateurs ; elle est logique (l'historique et les sauvegardes conservent le projet).")
    d.img("09_nouveau_projet", "Création du projet « Maison Martin ».")
    d.img("10_fiche_projet", "Fiche projet : indicateurs, onglets et formulaire.")
    d.img("11_phases_projet", "Phases de la mission, configurables selon le contrat.")
    d.img("12_lots_projet", "Lots du projet et entreprises attributaires.")
    d.img("45_liste_projets", "Liste des projets de l'espace de démonstration (filtres par statut et recherche).")

    d.part("Module 03 – Devis et comparateur intelligent")
    d.p("C'est le cœur d'Archipel41. Le module lit les devis dans tous les formats courants, en extrait les données, contrôle les calculs, les compare "
        "entre eux et à la DPGF et au CCTP, puis produit un tableau comparatif et une conclusion argumentée.")
    d.module(
        "Transformer des devis hétérogènes (PDF, scans, Excel, Word, archives ZIP) en données structurées, fiables et comparables.",
        "Gagner des heures de ressaisie lors de l'analyse des offres (phase ACT), fiabiliser les contrôles et objectiver le choix des entreprises.",
        ul("les devis : PDF natifs, PDF scannés, JPG, PNG, XLS, XLSX, CSV, DOC, DOCX ou une archive ZIP les regroupant ;",
           "le lot concerné ;", "idéalement la <b>DPGF</b> du lot (Excel, CSV ou PDF) et le <b>CCTP</b> (PDF ou Word)."),
        "<h3>Importer des devis</h3>" + ol(
            "Sélectionnez le projet actif, ouvrez <b>Devis et comparateur</b>, onglet <b>Devis</b>.",
            "Choisissez le <b>lot concerné</b> et la <b>méthode d'extraction</b> : <i>Moteur de règles (local)</i>, ou <i>Assistant IA</i> si un fournisseur est configuré.",
            "Déposez un ou plusieurs fichiers dans la zone « Déposer un ou plusieurs devis » (ou cliquez pour les choisir).",
            "Patientez quelques secondes par fichier (un PDF scanné passe par la reconnaissance de caractères – OCR).",
            "Le compte rendu indique, pour chaque fichier, la méthode, le nombre de lignes, le total HT recalculé, l'usage de l'OCR et les anomalies.") +
        "<h3>Importer la DPGF et le CCTP</h3>" + ol(
            "Onglet <b>DPGF et CCTP</b>, avec le lot sélectionné en haut à droite.",
            "Déposez la DPGF : les lignes (n°, désignation, unité, quantité, prix estimé, référence CCTP) sont reconnues.",
            "Déposez le CCTP : les articles et les exigences techniques (classe de béton, classe d'exposition, DTU, normes, épaisseurs…) sont repérés.") +
        "<h3>Consulter et corriger les données extraites</h3>" + ol(
            "Dans la liste, cliquez sur le nom d'une entreprise pour ouvrir l'écran de vérification.",
            "Comparez avec le document source affiché à droite (bouton <b>Masquer / Afficher le document</b>).",
            "Consultez le bloc <b>Totaux et contrôle des calculs</b> (recalculé par le moteur / déclaré par l'entreprise / écart) et la liste des <b>anomalies</b>.",
            "Corrigez directement les cellules (désignation, quantité, unité, prix unitaire, montant, TVA, <b>statut</b>) ; les lignes surlignées ont une fiabilité d'extraction inférieure à 70 % ; survolez une ligne pour voir le texte source.",
            "Corrigez si besoin l'entreprise (ou cliquez sur « créer la fiche »), les délais, la validité, les conditions de paiement, les exclusions, les réserves et les variantes.",
            "Cliquez sur <b>Enregistrer les corrections</b> : les totaux et la TVA sont recalculés.",
            "Un gestionnaire ou un administrateur clique sur <b>Valider</b>.") +
        "<h3>Comparer plusieurs offres</h3>" + ol(
            "Onglet <b>Devis</b> : cochez au moins deux devis du même lot.",
            "Cochez éventuellement <b>Conclusion rédigée par l'IA</b>, puis cliquez sur <b>Comparer</b>.",
            "Le comparatif s'ouvre : classement multicritère, tableau comparatif, conclusion, contrôle CCTP et conditions des offres.",
            "Filtrez le tableau (écarts, postes non renseignés ou exclus, à vérifier) et affichez les prix unitaires si nécessaire.",
            "Exportez en <b>Excel</b>, <b>CSV</b> ou <b>Word</b>, ou générez le <b>Rapport PDF</b> (classé automatiquement dans les documents du projet)."),
        "Camille importe trois devis du lot 02 : Bâti Ouest (PDF avec tableau), Durand & Fils (PDF texte) et Le Goff (PDF <b>scanné</b>). "
        "Archipel41 détecte chez Bâti Ouest une erreur de calcul (42 m² × 81,00 € = 3 402,00 € et non 3 412,00 €) qui fausse les totaux de 10 € HT. "
        "Camille corrige la ligne et valide le devis. Le comparatif montre que Durand & Fils est le moins-disant (28 432 € HT) mais "
        "n'a pas chiffré l'enduit hydrofuge (« non renseigné »), exclut expressément l'évacuation des gravats (« non inclus »), propose un drain en option, "
        "affiche un prix anormalement bas pour le béton de propreté (−57 % par rapport à la médiane) et émet une réserve sur l'étude de sol. "
        "Son montant à périmètre comparable est estimé à 30 992 € HT.",
        ul("lignes structurées : désignation, quantité, unité, prix unitaire, montant HT, TVA, statut ;",
           "totaux recalculés par taux de TVA, comparés aux totaux déclarés ; options et variantes isolées ;",
           "anomalies : erreurs de calcul, totaux incohérents, taux de TVA inhabituels, doublons, montants négatifs, lignes à vérifier ;",
           "comparaison ligne à ligne avec la DPGF : statut de chaque poste, écart à la médiane, prix le plus bas mis en évidence ;",
           "classement transparent (prix 50 %, complétude 25 %, risques 15 %, délai 10 %) et conclusion argumentée ;",
           "contrôle des exigences du CCTP non citées par chaque offre."),
        ul("Importez toujours la DPGF avant de comparer : elle fournit la référence des quantités et des unités.",
           "Vérifiez chaque devis (surtout les scans) avant validation ; la validation est un acte engageant.",
           "Faites préciser par écrit aux entreprises les postes « non renseignés » : inclus sans plus-value, oubli ou exclusion ?",
           "Demandez la justification des prix anormalement bas (risque d'offre sous-évaluée)."),
        ul("La qualité de l'OCR dépend du scan (300 ppp, document droit et net) ; les lignes lues par OCR doivent être relues.",
           "Les mises en page très inhabituelles peuvent nécessiter une saisie manuelle ou l'extraction par IA.",
           "Le contrôle CCTP vérifie la <i>mention</i> des exigences dans les offres, pas la conformité technique réelle des ouvrages.",
           "Le classement est une aide à la décision : il ne tient pas compte des références, de la capacité ou de l'assurance des entreprises."))
    d.h3("Les sept statuts du comparateur")
    d.table(["Statut", "Signification"], [
        ['<span class="badge ok">Inclus</span>', "Le poste est chiffré (ou mentionné « compris ») dans l'offre."],
        ['<span class="badge ko">Non inclus</span>', "L'entreprise <b>exclut expressément</b> le poste (« non compris », « hors lot », « à la charge du maître d'ouvrage », liste d'exclusions)."],
        ['<span class="badge mid">Non renseigné</span>', "Le poste est <b>absent</b> de l'offre, sans mention d'exclusion. À faire préciser : ce n'est pas une exclusion."],
        ['<span class="badge" style="background:#DDE5F0;color:#46678C">Optionnel</span>', "Proposé en option, non compris dans le total."],
        ['<span class="badge" style="background:#E6DDF0;color:#7C5FA8">Variante</span>', "Proposé en variante, non compris dans le total."],
        ['<span class="badge" style="background:#E4E4E4;color:#666">Non comparable</span>', "Unité incompatible avec la référence (ex. m² au lieu de ml)."],
        ['<span class="badge mid">À vérifier</span>', "Correspondance incertaine entre libellés, ou ligne signalée à vérifier (PM, à définir…)."],
    ], [22, 78])
    d.img("13_import_devis", "Import des devis : choix du lot et de la méthode d'extraction.")
    d.img("14_devis_importes", "Compte rendu d'import (dont un PDF scanné lu par OCR) et liste des devis du projet.")
    d.img("15_dpgf_cctp", "DPGF et CCTP importés : référence du comparateur.")
    d.img("16_revue_devis", "Vérification d'un devis : contrôle des calculs, anomalies et document source en regard.")
    d.img("17_correction_ligne", "Correction d'un montant erroné directement dans le tableau des lignes.")
    d.img("18_devis_valide", "Après correction : plus d'erreur de calcul, devis validé.")
    d.img("19_selection_comparaison", "Sélection des devis à comparer.")
    d.img("20_comparatif_tableau", "Comparatif : classement des offres et tableau ligne à ligne avec statuts et écarts.")
    d.img("21_comparatif_filtre", "Filtre « Non renseignés / exclus » : les divergences de périmètre en un coup d'œil.")
    d.img("22_comparatif_conclusion", "Conclusion argumentée produite à partir des faits calculés.", maxh=170)
    d.img("23_comparatif_cctp", "Contrôle des exigences du CCTP dans chaque offre.")

    d.part("Module 04 – Agenda et rendez-vous")
    d.module(
        "Planifier les rendez-vous clients, réunions d'entreprises, visites de chantier et réunions internes, avec participants, rappels, comptes rendus et documents.",
        "Éviter les doubles réservations, ne plus oublier un rendez-vous et retrouver chaque compte rendu dans le projet concerné.",
        ul("objet, type, date et heures, lieu ;", "participants de l'agence et externes ;", "projet concerné, rappel, ordre du jour, documents associés."),
        ol("Ouvrez <b>Agenda</b> ; choisissez la vue <b>jour</b>, <b>semaine</b> ou <b>mois</b> et naviguez avec les flèches ou <b>Aujourd'hui</b>.",
           "Cliquez sur <b>+ Rendez-vous</b> (ou double-cliquez sur un créneau).",
           "Renseignez l'objet, le type, le projet, les horaires, le lieu et le rappel ; sélectionnez les participants de l'agence et ajoutez les participants externes.",
           "Si un participant est déjà pris sur ce créneau, l'encadré <b>Conflit d'agenda détecté</b> l'indique : modifiez l'horaire ou enregistrez en connaissance de cause.",
           "Cliquez sur <b>Enregistrer</b>.",
           "Après la réunion, rouvrez le rendez-vous, rédigez le <b>compte rendu</b>, cliquez sur <b>Résumer le compte rendu</b> (décisions et actions), puis sur <b>Compte rendu PDF</b>."),
        "Camille programme la présentation du comparatif aux Martin le lendemain à 10 h. En ajoutant une visite de chantier à 10 h 30 le même jour, Archipel41 signale le conflit.",
        ul("calendrier jour / semaine / mois, coloré par type ;", "conflits signalés (icône ⚠ sur les rendez-vous concernés) ;",
           "rappels : notification Windows ou du navigateur et cloche de la barre supérieure ;", "compte rendu synthétisé et rapport PDF/Word."),
        ul("Rattachez chaque rendez-vous à son projet : il apparaît dans la fiche projet et alimente l'assistant.", "Rédigez le compte rendu le jour même avec actions, responsables et échéances."),
        ul("Les notifications de rappel s'affichent lorsque l'application (ou l'onglet du navigateur) est ouverte.",
           "Synchronisation avec Outlook ou Google Agenda : Paramètres › Agendas (application déclarée chez Microsoft ou Google requise ; votre mot de passe n'est jamais enregistré)."))
    d.img("24_nouveau_rendez_vous", "Création d'un rendez-vous client.")
    d.img("25_conflit_agenda", "Détection d'un conflit d'agenda.")
    d.img("26_agenda_semaine", "Vue semaine.")
    d.img("27_agenda_mois", "Vue mois.")

    d.part("Module 05 – Planning et météo")
    d.module(
        "Planifier le chantier dans un diagramme de Gantt interactif et anticiper les intempéries selon la nature des travaux prévus.",
        "Visualiser l'enchaînement des travaux, repérer les retards et le chemin critique, et décaler à temps les tâches sensibles à la météo (coulage de béton, couverture, enduits…).",
        ul("tâches : nom, date de début, durée en jours (0 = jalon), dépendances, responsable, entreprise, lot, avancement ;",
           "<b>type d'activité</b> de chaque tâche (béton, couverture, façade…) pour l'analyse météo ;", "adresse du chantier (fiche projet) pour la météo."),
        "<h3>Planifier</h3>" + ol(
            "Ouvrez <b>Planning et météo</b> avec le projet actif, puis <b>+ Tâche</b>.",
            "Renseignez la tâche, sa durée, son type d'activité et ses <b>dépendances</b> (fin → début).",
            "Dans le Gantt, <b>glissez</b> une barre pour la déplacer, tirez son <b>bord droit</b> pour changer sa durée ; double-cliquez pour l'ouvrir.",
            "Cliquez sur <b>Figer la référence</b> pour conserver le planning initial (barres grises) et mesurer les glissements.",
            "Si une dépendance n'est pas respectée, cliquez sur <b>Proposer un recalage</b>.") +
        "<h3>Consulter la météo et ajuster</h3>" + ol(
            "Onglet <b>Météo et propositions</b> : prévisions sur 14 jours ; les jours à risque pour une tâche prévue sont surlignés.",
            "Lisez l'<b>analyse des activités prévues</b> : pour chaque tâche exposée, les jours défavorables, les risques et la recommandation.",
            "Cliquez sur <b>Proposer des ajustements</b> : des propositions sont créées.",
            "Un gestionnaire <b>accepte</b> (la tâche et ses successeurs sont décalés) ou <b>refuse</b> chaque proposition. Aucune modification n'est appliquée sans validation."),
        "Dans l'espace de démonstration (météo simulée), le dallage béton est prévu pendant trois jours de pluie supérieure à 5 mm (risque de délavage du béton frais) "
        "et la maçonnerie comporte un jour de gel. Faute de fenêtre favorable dans l'horizon de prévision, Archipel41 recommande de prévoir des protections et de réévaluer à J-2 ; "
        "deux propositions sont soumises à la cheffe de projet. Lorsqu'une fenêtre favorable existe, la proposition consiste à décaler la tâche à cette date : "
        "si elle est acceptée, la tâche et ses successeurs sont recalés automatiquement.",
        ul("Gantt avec jalons, dépendances, chemin critique (contour rouge), retards (orange), date du jour, planning de référence ;",
           "avancement attendu comparé à l'avancement réel ;", "propositions d'ajustement traçables (acceptées ou refusées, par qui, quand)."),
        ul("Mettez à jour l'avancement chaque semaine.", "Renseignez le type d'activité de chaque tâche extérieure.",
           "Confrontez les seuils météo aux prescriptions du CCTP, des fiches techniques et des DTU."),
        ul("Les prévisions sont fiables à quelques jours ; au-delà, elles sont indicatives.", "Les seuils de l'analyse sont génériques et indicatifs.",
           "Les dépendances gérées sont de type fin → début."))
    d.img("28_nouvelle_tache", "Création d'une tâche avec type d'activité.")
    d.img("46_planning_gantt", "Diagramme de Gantt : dépendances, chemin critique, retards et date du jour.")
    d.img("47_meteo_propositions", "Prévisions, analyse des activités sensibles et propositions à valider (météo simulée de la démonstration).", maxh=165)

    d.part("Module 06 – Urbanisme et contraintes de site")
    d.module(
        "Réunir les contraintes réglementaires d'un terrain à partir des sources officielles et analyser le règlement du PLU applicable.",
        "Préparer une étude de faisabilité en quelques minutes, avec références et sources, et identifier tôt les contraintes (patrimoine, risques, servitudes).",
        ul("une <b>adresse</b>, une <b>référence cadastrale</b> (code INSEE + section + numéro, ex. 44109 AB 0123) ou des <b>coordonnées GPS</b> ;",
           "le <b>règlement écrit du PLU</b> (PDF) importé dans Documents, catégorie Urbanisme."),
        "<h3>Analyser une parcelle</h3>" + ol(
            "Ouvrez <b>Urbanisme</b>, choisissez le type de recherche et saisissez le terrain, puis <b>Analyser la parcelle</b>.",
            "Archipel41 interroge la Base Adresse Nationale, le cadastre (API Carto IGN), le Géoportail de l'Urbanisme (document, zonage, prescriptions, servitudes), Géorisques.",
            "Consultez la fiche : parcelle et surface, document d'urbanisme, zone, servitudes, prescriptions, patrimoine, risques, et l'encadré <b>Données indisponibles</b>.") +
        "<h3>Étudier les contraintes du PLU</h3>" + ol(
            "Dans <b>Analyse du règlement écrit du PLU</b>, choisissez le règlement importé et vérifiez la zone (ex. UB).",
            "Cochez éventuellement <b>Synthèse rédigée par l'IA</b>, puis cliquez sur <b>Analyser</b>.",
            "Pour chaque thème (destinations, emprise au sol, hauteur, implantations, aspect, stationnement, espaces verts, réseaux), Archipel41 affiche l'article, l'extrait exact, la page et les valeurs relevées.",
            "Consultez les <b>indicateurs de faisabilité</b> (ex. emprise maximale = surface × pourcentage cité) et les recommandations.",
            "Cliquez sur <b>Rapport de faisabilité</b> pour obtenir le PDF avec sources, dates de consultation et incertitudes."),
        "Sur le terrain de démonstration (2 290 m², zone UB fictive), le règlement fixe une emprise au sol de 40 % : Archipel41 calcule une emprise maximale indicative "
        "de 916 m², relève une hauteur de 9 m au faîtage, 30 % d'espaces verts de pleine terre (687 m²) et signale la servitude AC1 (abords de monument historique : avis de l'ABF).",
        ul("fiche de site avec tracé de la parcelle ;", "extraits réglementaires cités avec article et page ;", "thèmes non trouvés explicitement signalés ;",
           "rapport de faisabilité PDF avec sources et incertitudes."),
        ul("Vérifiez que le règlement importé est la version opposable (modifications, révisions).", "Consultez aussi les OAP et le règlement graphique.",
           "Sécurisez le projet par un certificat d'urbanisme opérationnel."),
        ul("Archipel41 n'invente aucune règle : si un thème n'est pas trouvé dans le document fourni, il l'indique.",
           "Toutes les communes n'ont pas publié leur document sur le Géoportail de l'Urbanisme (RNU, cartes communales, documents non numérisés).",
           "Les indicateurs sont des calculs indicatifs à partir des valeurs citées ; ils ne remplacent pas l'instruction.",
           "Les services publics peuvent être momentanément indisponibles : ils figurent alors dans « Données indisponibles »."))
    d.img("48_urbanisme", "Analyse d'une parcelle (mode démonstration, données fictives) et analyse du règlement avec indicateurs.", maxh=175)

    d.part("Module 07 – Assistant IA intégré")
    d.module(
        "Répondre aux questions de l'équipe à partir des documents et des données des projets, en citant les sources.",
        "Retrouver une information dans les pièces écrites, les comptes rendus et les archives, résumer, identifier des risques et préparer des rapports.",
        ul("une question en langage courant ;", "le contexte : un projet ou toute l'agence."),
        ol("Ouvrez <b>Assistant IA</b> (ou le bouton <b>Assistant</b> en haut de n'importe quel écran).",
           "Choisissez le contexte (projet ou agence).",
           "Posez la question, ou cliquez sur une suggestion.",
           "Lisez la réponse ; dépliez <b>source(s) citée(s)</b> pour voir les extraits et ouvrir les documents.",
           "Reprenez une conversation passée dans la liste des conversations."),
        "« Quelle est l'emprise au sol autorisée en zone UB ? » — l'assistant cite l'article UB 9 du règlement (40 %) avec la référence [S1] vers le document et la page.",
        ul("<b>Avec un fournisseur d'IA</b> : réponse rédigée, structurée, avec renvois [S1], [S2] vers les extraits ;",
           "<b>sans fournisseur</b> (mode extractif) : les passages les plus pertinents de vos documents, avec leurs références ;",
           "conversations conservées par utilisateur."),
        ul("Posez des questions précises et sélectionnez le projet concerné.", "Vérifiez toujours la source d'une information réglementaire ou chiffrée.",
           "Marquez confidentiels les documents sensibles."),
        ul("Les documents et projets confidentiels ne sont jamais transmis à un fournisseur externe sans autorisation explicite de l'administrateur.",
           "L'IA peut se tromper : ses réponses sont une aide à la décision.", "Seuls les documents dont le texte a pu être extrait sont interrogeables."))
    d.img("32_assistant", "Réponse de l'assistant avec ses sources (mode sans IA générative).")
    d.img("50_assistant_panneau", "L'assistant accessible depuis n'importe quel écran.")

    d.part("Module 08 – Documents")
    d.module(
        "Conserver, classer, versionner, prévisualiser et retrouver tous les documents de l'agence et des projets.",
        "Une source unique et à jour pour les plans, pièces écrites, devis, contrats, comptes rendus, photos et maquettes.",
        ul("les fichiers : PDF, DOCX, XLSX, CSV, images, DWG, DXF, IFC, PLN, PLA, ZIP… ;", "projet, catégorie, mots-clés, confidentialité."),
        "<h3>Importer, organiser et retrouver</h3>" + ol(
            "Ouvrez <b>Documents</b> (portée : projet actif ou toute l'agence).",
            "Cochez <b>Confidentiel</b> si nécessaire, puis <b>Importer</b> ou glissez-déposez des fichiers (une archive ZIP est dépliée).",
            "Le texte est extrait automatiquement (OCR pour les scans) et indexé pour la recherche.",
            "Cliquez sur un document : onglets <b>Aperçu</b>, <b>Classement</b> (nom, catégorie, projet, mots-clés, description), <b>Versions</b>, <b>Historique</b>.",
            "<b>Nouvelle version</b> : déposez la version mise à jour (même format) ; les anciennes restent consultables.",
            "Recherchez par nom ou contenu, ou utilisez la <b>Recherche dans le contenu des documents</b> (recherche sémantique).",
            "Cochez plusieurs documents puis <b>Exporter</b> pour les obtenir dans une archive ZIP."),
        "Camille importe le règlement du PLU ; la recherche « hauteur maximale zone UB » renvoie l'extrait de l'article UB 10 (9 mètres au faîtage).",
        ul("bibliothèque filtrable ; aperçu page par page des PDF ; versions et historique ;", "recherche plein texte et sémantique ; export groupé."),
        ul("Choisissez la bonne catégorie : elle sert aux filtres et aux modules (Urbanisme, Devis).", "Déposez une nouvelle version plutôt qu'un nouveau document."),
        ul("Les fichiers CAO/BIM (DWG, DXF, IFC, PLN, PLA) sont conservés et versionnés mais ne sont pas visualisés : ouvrez-les avec votre logiciel métier.",
           "Taille maximale par fichier : 200 Mo (paramétrable sur le serveur)."))
    d.img("30_documents", "Bibliothèque documentaire et recherche dans le contenu.", maxh=165)
    d.img("31_document_apercu", "Aperçu d'un document PDF, page par page.")

    d.part("Module 09 – Clients et entreprises")
    d.module(
        "Tenir à jour les fiches des maîtres d'ouvrage et des entreprises : coordonnées, contacts, spécialités, devis, marchés, projets, documents, historique et observations.",
        "Retrouver instantanément un interlocuteur, l'historique des échanges et les références d'une entreprise.",
        ul("nom ou raison sociale, type (particulier, entreprise, collectivité, promoteur) ou spécialités ;", "SIRET (14 chiffres), e-mail, téléphone, adresse ;", "contacts nommés."),
        ol("Ouvrez <b>Clients et entreprises</b>, onglet <b>Clients</b> ou <b>Entreprises</b>.",
           "Cliquez sur <b>Nouveau client</b> ou <b>Nouvelle entreprise</b>, remplissez la fiche, puis <b>Créer</b>.",
           "Sur la fiche, consultez les onglets <b>Projets</b>, <b>Devis</b>, <b>Marchés</b>, <b>Documents</b> et ajoutez des notes dans <b>Historique</b>."),
        "Camille crée le client « M. et Mme Martin » puis les entreprises Bâti Ouest et Durand & Fils ; lors de l'import des devis, Archipel41 rattache automatiquement chaque devis à la fiche entreprise correspondante.",
        ul("fiches complètes et reliées aux projets, devis et marchés ;", "historique daté des échanges."),
        ul("Créez les entreprises avant d'importer leurs devis (rattachement automatique).", "Notez dans l'historique chaque échange important."),
        "Archipel41 ne vérifie pas en ligne la validité des SIRET ni les attestations d'assurance.")
    d.img("06_nouveau_client", "Création d'une fiche client.")
    d.img("07_nouvelle_entreprise", "Création d'une fiche entreprise.")
    d.img("08_annuaire_entreprises", "Annuaire des entreprises.")

    d.part("Module 10 – Finances")
    d.module(
        "Suivre le budget de chaque opération : budget initial et actualisé, marchés, travaux supplémentaires, factures, acomptes, situations, paiements, dépenses, écarts.",
        "Détecter tôt les dérives budgétaires, suivre la facturation des entreprises et les échéances de paiement.",
        ul("budget initial du projet et, si besoin, lignes budgétaires par lot ;", "écritures : nature, libellé, lot, entreprise, montant HT, taux de TVA, dates, statut."),
        ol("Sans projet actif, la <b>vue d'ensemble</b> liste tous les projets ; cliquez sur l'un d'eux.",
           "Onglet <b>Écritures</b> : <b>+ Écriture</b>, choisissez la nature (marché, travaux supplémentaires, facture, acompte, situation, paiement, dépense, honoraires), saisissez le montant HT et la TVA, puis <b>Enregistrer</b> ; le TTC est calculé automatiquement.",
           "Onglet <b>Budget</b> : ajustez les lignes budgétaires (initial / actualisé).",
           "Onglet <b>Synthèse par lot</b> : budget, engagé, facturé, écarts ; alertes de dépassement et d'échéances.",
           "Cliquez sur <b>Rapport financier (Excel)</b> pour l'exporter."),
        "Camille enregistre le marché du lot 02 attribué à Bâti Ouest : 34 783,00 € HT, soit 41 739,60 € TTC calculés par le moteur.",
        ul("indicateurs : budget initial, actualisé, engagé, facturé, payé, reste à payer, échéances dépassées ;", "synthèse et graphique par lot ; alertes."),
        ul("Enregistrez chaque avenant en « travaux supplémentaires ».", "Saisissez les paiements pour suivre le reste à payer.", "Renseignez les échéances des factures et situations."),
        "Archipel41 n'est pas un logiciel de comptabilité : il ne produit ni écritures comptables ni factures d'honoraires.")
    d.img("33_ecriture_financiere", "Saisie d'une écriture (marché).")
    d.img("34_finances_projet", "Synthèse financière du projet.")

    d.part("Module 11 – Rapports")
    d.module(
        "Produire des documents professionnels aux couleurs de l'agence : rapports de devis, urbanistiques, de chantier, comptes rendus, rapports financiers et synthèses de projets.",
        "Communiquer avec les maîtres d'ouvrage et les entreprises sans ressaisie.",
        ul("le type de rapport et le format (PDF, XLSX, DOCX, CSV) ;", "le projet, ou le comparatif / l'analyse / le rendez-vous concerné."),
        ol("Ouvrez <b>Rapports</b> et choisissez le type de rapport.", "Choisissez le projet et, selon le cas, le comparatif, l'analyse urbanistique ou le rendez-vous.",
           "Choisissez le format puis cliquez sur <b>Générer et télécharger</b>.",
           "Le rapport est aussi classé dans les documents du projet (catégorie Rapport) et listé dans « Rapports générés »."),
        "Camille génère la synthèse du projet Maison Martin en PDF pour la réunion avec les clients.",
        ul("documents mis en page (logo, titres, tableaux colorés, pied de page paginé) ;", "versions Excel exploitables (formats numériques) et Word modifiables."),
        ul("Générez le rapport de devis depuis le comparatif validé.", "Relisez et complétez la version Word avant envoi si nécessaire."),
        "Les rapports reflètent les données au moment de leur génération : régénérez-les après toute modification.")
    d.img("35_rapports", "Génération de rapports.")

    # ===================================================================== transversal
    d.part("Travailler hors connexion et synchroniser")
    d.sec("Application Windows")
    d.p("L'application Windows fonctionne entièrement hors connexion : vos données sont sur le poste. Seuls la météo, l'urbanisme, l'IA en ligne et la synchronisation "
        "nécessitent Internet. Lorsque le poste est raccordé à un serveur central, il se synchronise automatiquement ; au retour du réseau, les modifications "
        "en attente sont envoyées et celles des collègues reçues.")
    d.sec("Navigateur (PWA)")
    d.p("Dans un navigateur connecté au serveur central, l'application peut être installée comme une application (menu du navigateur › « Installer Archipel41 »). "
        "Hors connexion, les pages déjà consultées restent disponibles et les créations/modifications sont mises en <b>file d'attente</b> sur l'appareil ; "
        "elles sont envoyées automatiquement au retour du réseau. Le badge « Hors ligne » indique le nombre de modifications en attente.")
    d.img("43_hors_connexion", "Hors connexion : le badge orange signale les modifications en attente.")
    d.sec("Conflits")
    d.p("Si une modification hors ligne concerne un élément modifié entre-temps par un collègue, elle n'écrase rien : elle apparaît dans "
        "<b>Paramètres › Synchronisation</b>, où vous comparez champ par champ « ma version » et « la version du serveur » et choisissez celle à conserver.")
    d.warn("Le stockage local seul ne permet pas de partager des données entre appareils : le travail en équipe nécessite le serveur central.")

    d.part("Gérer les utilisateurs et les permissions")
    d.p("L'administrateur gère les comptes dans <b>Paramètres › Utilisateurs et permissions</b> : création, rôle, désactivation (un compte désactivé ne peut plus se connecter), "
        "réinitialisation du mot de passe. La matrice des permissions est affichée sous la liste.")
    d.img("05_utilisateurs_permissions", "Utilisateurs de l'agence et matrice des permissions.", maxh=160)
    d.ul("Les données de chaque agence sont strictement isolées.",
         "Un projet <b>confidentiel</b> n'est visible que de son équipe, des chefs de projet et des administrateurs.",
         "Le <b>journal d'audit</b> (Paramètres › Journal) trace connexions, créations, modifications, suppressions, validations, sauvegardes et restaurations.",
         "Le dernier administrateur ne peut pas être rétrogradé ni désactivé.")

    d.part("Utilisation sur tablette et smartphone")
    d.p("L'interface s'adapte aux petits écrans : la barre latérale devient un menu ☰, les tableaux défilent horizontalement dans leur cadre.")
    d.raw('<div class="grid2">')
    d.img("51_smartphone_accueil", "Tableau de bord sur smartphone.", phone=True)
    d.img("52_smartphone_menu", "Menu des modules sur smartphone.", phone=True)
    d.raw("</div>")
    d.img("51_tablette_devis", "Module Devis sur tablette.", maxh=150)

    d.part("Questions fréquentes")
    d.table(["Question", "Réponse"], [
        ["Une prestation n'apparaît pas dans un devis : est-elle exclue ?", "Non. Elle est « non renseignée » : demandez à l'entreprise de préciser. Seule une mention expresse rend un poste « non inclus »."],
        ["Les totaux du devis diffèrent de ceux de l'entreprise.", "Le moteur recalcule chaque ligne (quantité × prix unitaire, arrondi au centime) ; l'écart et sa cause sont affichés dans les anomalies."],
        ["Puis-je modifier un devis validé ?", "Oui (selon vos droits) ; la modification est historisée et le devis peut être revalidé."],
        ["L'assistant répond « mode sans IA générative ».", "Aucun fournisseur d'IA n'est configuré ou autorisé pour ce contenu : il cite les passages pertinents de vos documents."],
        ["La météo affiche « simulée ».", "Le mode démonstration de la météo est activé (Paramètres › Météo)."],
        ["Comment retrouver un ancien document ?", "Recherche globale (en haut) ou recherche dans le contenu (module Documents)."],
    ], [38, 62])
    return d
