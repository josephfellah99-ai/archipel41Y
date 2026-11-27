/** Aide contextuelle : une fiche courte par écran (but, étapes, bon à savoir). Le guide pratique complet est
 *  embarqué dans l'application (Paramètres › Guides ou bouton « Guide pratique » du panneau d'aide). */
export type HelpEntry = { n?: string; title: string; but: string; etapes: string[]; savoir?: string[] };

const H: [string, HelpEntry][] = [
  ["/comparatifs/", { n: "04", title: "Comparatif d'offres", but: "Comparer ligne à ligne les offres d'un même lot, avec écarts, remarques techniques et leviers d'optimisation.",
    etapes: ["Lisez la conclusion, puis le tableau : chaque écart renvoie à la ligne du devis d'origine.", "Onglet Remarques : filtrez par gravité, thème ou entreprise.", "Onglet Optimisation : coût réel probable, coûts cachés et leviers de négociation."],
    savoir: ["Aucun montant n'est inventé : une valeur illisible est signalée, jamais devinée.", "La qualité technique est un garde-fou : une économie qui la dégrade est signalée."] }],
  ["/devis", { n: "04", title: "Comparateur — devis", but: "Importer, vérifier et valider les devis avant de les comparer.",
    etapes: ["Importez les PDF (même scannés) dans le lot concerné.", "Ouvrez chaque devis « à vérifier » : corrigez les lignes douteuses en regard du document.", "Validez, puis sélectionnez les devis du lot et lancez la comparaison."],
    savoir: ["Les nombres sont lus à la française (1 250,50) ; quantités, prix unitaires et caractéristiques techniques ne sont jamais confondus."] }],
  ["/projets/", { n: "02", title: "Fiche projet", but: "Tout ce qui concerne une opération : équipe, phases, lots, terrain, incidents, documents, budget.",
    etapes: ["Onglet Phases : gardez celles de la mission, datez-les, cochez la phase en cours.", "Onglet Lots : les lots sont libres — numérotez, renommez, réorganisez selon le projet.", "Onglets Équipe, Terrain, Documents : complétez au fil de l'eau."],
    savoir: ["Un projet confidentiel n'est visible que de son équipe.", "Les lots varient d'un projet à l'autre : il n'y a pas de liste fixe."] }],
  ["/projets", { n: "02", title: "Projets", but: "La liste des opérations de l'agence et leur avancement.",
    etapes: ["« Nouveau projet » : code, nom, maître d'ouvrage, adresse, budget.", "Sélectionnez le projet actif en haut de l'écran : les autres modules s'y alignent."],
    savoir: ["Code projet conseillé : année – numéro – ville – affaire (ex. 26-12 NOR - CON)."] }],
  ["/chantiers", { n: "03", title: "Chantiers", but: "Les opérations en travaux : avancement, incidents, prochaines réunions.",
    etapes: ["Suivez l'avancement et les incidents par chantier.", "Ouvrez Planning et météo pour anticiper les intempéries."] }],
  ["/planning", { n: "03", title: "Planning et météo", but: "Ordonner les tâches du chantier et anticiper le temps qu'il fera.",
    etapes: ["Créez les tâches et leurs dépendances.", "Consultez les propositions de décalage liées à la météo : rien n'est déplacé sans votre accord."] }],
  ["/documents", { n: "05", title: "Documents", but: "Classer, retrouver, consulter et annoter toutes les pièces du projet, dans l'arborescence ARCHIPEL 41.",
    etapes: ["Choisissez un dossier dans l'arborescence, puis « Importer dans ce dossier » — ou importez puis examinez la suggestion de classement.",
      "Ouvrez un document : aperçu (PDF, images, Excel, Word, DXF, IFC), « Annoter » pour poser une zone ou un repère.",
      "Onglet Classement : dossier, statut, documents liés, nom conforme à la convention."],
    savoir: ["Rien n'est jamais écrasé : chaque dépôt crée une nouvelle version, toutes restent téléchargeables.",
      "Une suggestion de classement n'est qu'une proposition : « Classer ici » ou « Ignorer ».",
      "Convention de nommage : composantes séparées par « - », dates AAAA-MM-JJ, « MOA » pour la maîtrise d'ouvrage.",
      "Les annotations n'altèrent jamais le fichier original."] }],
  ["/rapports", { n: "05", title: "Rapports", but: "Produire des documents prêts à envoyer (comptes rendus, synthèses, analyses).",
    etapes: ["Choisissez le modèle et le projet, vérifiez l'aperçu, puis générez."] }],
  ["/terrain", { n: "06", title: "Terrain et cartographie", but: "Le terrain du projet sur une carte : mesures, repères annotés, données du géomètre, analyse urbanistique.",
    etapes: ["Carte : mesurez distances et surfaces, posez des repères annotés.", "Couches et imports : GeoJSON, KML, GPX, Shapefile, DXF, GeoTIFF… les coordonnées Lambert sont converties automatiquement.", "Fiche terrain : références cadastrales, superficie, zone du PLU."],
    savoir: ["Le tracé cadastral est indicatif : ce n'est jamais un bornage officiel.", "L'identification de parcelle demande une connexion internet (service IGN)."] }],
  ["/urbanisme", { n: "06", title: "Analyse urbanistique", but: "Les règles applicables à une parcelle, sources à l'appui.",
    etapes: ["Saisissez l'adresse ou cliquez sur la carte, puis lancez l'analyse.", "Vérifiez chaque règle dans le document source cité."],
    savoir: ["Aucun article n'est inventé : en l'absence de source, l'information est signalée comme manquante."] }],
  ["/agenda", { n: "07", title: "Agenda", but: "Rendez-vous, réunions de chantier, échéances — synchronisés avec Outlook ou Google si vous le souhaitez.",
    etapes: ["Créez un rendez-vous : les conflits sont signalés avant l'enregistrement.", "Paramètres › Agendas : connectez Outlook ou Google (vos mots de passe ne sont jamais stockés)."] }],
  ["/equipe", { n: "08", title: "Équipe", but: "Collaborateurs, rôles, autorisations par module et par projet, invitations par code.",
    etapes: ["Ajoutez un collaborateur et choisissez son rôle.", "Affinez les autorisations module par module ou projet par projet.", "Invitez un partenaire extérieur avec un code à durée limitée."],
    savoir: ["Les autorisations sont vérifiées par le serveur, pas seulement masquées à l'écran.", "Un invité n'accède jamais aux paramètres de l'agence."] }],
  ["/finances", { n: "09", title: "Finances", but: "Budget, engagements et paiements, lot par lot.",
    etapes: ["Saisissez les écritures (montants à la française).", "Comparez budget, engagé et payé par lot."] }],
  ["/assistant", { n: "10", title: "Assistant IA", but: "Poser une question sur vos projets et documents ; la réponse cite ses sources.",
    etapes: ["Choisissez le projet, posez votre question, vérifiez les sources citées."],
    savoir: ["Les documents confidentiels ne sont jamais envoyés à un fournisseur d'IA externe sans autorisation de l'administrateur."] }],
  ["/historique", { n: "11", title: "Historique et activité", but: "Qui a fait quoi, quand ; connexions ; erreurs et diagnostic ; intégrité du journal.",
    etapes: ["Filtrez par projet, module, utilisateur ou opération.", "Cliquez une ligne pour voir l'ancienne et la nouvelle valeur.", "En cas de problème, communiquez la référence E-XXXXXX affichée."],
    savoir: ["Le journal est scellé : toute altération est détectée par le contrôle d'intégrité."] }],
  ["/annuaire", { n: "02", title: "Clients et entreprises", but: "L'annuaire vivant de l'agence.", etapes: ["Créez une fiche, rattachez-la aux projets et aux devis."] }],
  ["/parametres", { n: "12", title: "Paramètres", but: "Agence, IA, météo, urbanisme, agendas, synchronisation, sauvegardes.",
    etapes: ["Réglez chaque onglet une fois ; les sauvegardes peuvent être planifiées."], savoir: ["Aucune clé ni aucun mot de passe n'apparaît en clair dans les journaux."] }],
  ["/recherche", { title: "Recherche", but: "Retrouver un projet, un contact, un devis, une tâche, un rendez-vous ou un passage de document.", etapes: ["Tapez au moins deux caractères dans la barre de recherche."] }],
  ["/", { n: "01", title: "Tableau de bord", but: "La première page de la journée : alertes, rendez-vous, tâches, budgets, météo des chantiers.",
    etapes: ["Lisez la synthèse du jour, puis traitez les alertes de la plus grave à la moins urgente.", "Filtrez par période, projet ou collaborateur."] }],
];

export function helpFor(path: string): HelpEntry {
  for (const [prefix, h] of H) {
    if (prefix === "/" ? path === "/" : path.startsWith(prefix)) return h;
  }
  return H[H.length - 1][1];
}
