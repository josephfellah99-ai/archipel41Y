"""ARCHIPEL41 — Le guide pratique (style typographique suisse).
Génère docs/ARCHIPEL41_GUIDE_PRATIQUE.pdf :  .venv/bin/python docs/sources/guide_suisse.py
"""
from __future__ import annotations

import base64
import html as H
import io
import subprocess
from datetime import date
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SHOTS = HERE.parent / "screenshots"
RED = "#D52B1E"

CSS = f"""
* {{ box-sizing: border-box; }}
body {{ font-family: Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #111; font-size: 9.3pt; line-height: 1.48; margin: 0; }}
b, strong {{ font-weight: 600; }}
.red {{ color: {RED}; }}

/* ---------- couverture ---------- */
.cover {{ height: 262mm; position: relative; page-break-after: always; }}
.cover .bar {{ position: absolute; left: 0; top: 0; width: 58mm; height: 58mm; background: {RED}; }}
.cover .grid {{ position: absolute; inset: 0; background-image: linear-gradient(to right, #eee 0.3pt, transparent 0.3pt);
               background-size: 14.5mm 100%; }}
.cover .kicker {{ position: absolute; left: 66mm; top: 0; font-size: 8pt; letter-spacing: .14em; text-transform: uppercase; line-height: 1.6; }}
.cover h1 {{ position: absolute; left: 0; top: 92mm; margin: 0; font-size: 62pt; line-height: .92; letter-spacing: -.035em; font-weight: 700; }}
.cover .lead {{ position: absolute; left: 0; top: 172mm; width: 120mm; font-size: 15pt; line-height: 1.3; letter-spacing: -.01em; font-weight: 400; }}
.cover .meta {{ position: absolute; left: 0; bottom: 0; width: 100%; border-top: 1.4pt solid #111; padding-top: 3mm;
               display: grid; grid-template-columns: 1fr 1fr 1fr; font-size: 7.6pt; letter-spacing: .04em; }}
.cover .meta b {{ display: block; text-transform: uppercase; letter-spacing: .12em; font-size: 6.8pt; margin-bottom: 1mm; }}

/* ---------- sommaire ---------- */
.toc {{ page-break-after: always; }}
.toc h2 {{ font-size: 30pt; letter-spacing: -.03em; margin: 0 0 10mm; font-weight: 700; }}
.toc .row {{ display: grid; grid-template-columns: 16mm 1fr 14mm; border-top: .5pt solid #111; padding: 2.1mm 0; font-size: 10pt; align-items: baseline; }}
.toc .row .n {{ color: {RED}; font-weight: 700; }}
.toc .row .p {{ text-align: right; }}
.toc .row.sub {{ border-top: .3pt solid #ccc; font-size: 8.6pt; padding: 1.3mm 0; color: #444; }}

/* ---------- chapitres ---------- */
.chap {{ page-break-before: always; }}
.chap-head {{ display: grid; grid-template-columns: 42mm 1fr; column-gap: 8mm; border-top: 2pt solid #111; padding-top: 3mm; margin-bottom: 9mm; }}
.chap-head .num {{ font-size: 46pt; line-height: .9; font-weight: 700; color: {RED}; letter-spacing: -.04em; }}
.chap-head h2 {{ font-size: 25pt; line-height: 1.02; letter-spacing: -.03em; margin: 0; font-weight: 700; }}
.chap-head .intro {{ grid-column: 2; font-size: 11.5pt; line-height: 1.38; margin-top: 4mm; letter-spacing: -.005em; }}
.mark {{ font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 3px; letter-spacing: 0; font-weight: 400; color: #fff; line-height: 0; position: absolute; }}

.blk {{ display: grid; grid-template-columns: 42mm 1fr; column-gap: 8mm; margin: 0 0 5.5mm; page-break-inside: auto; }}
.blk > .lab {{ font-size: 6.9pt; letter-spacing: .13em; text-transform: uppercase; font-weight: 600; padding-top: 1.2mm; border-top: .5pt solid #111; }}
.blk > .body {{ border-top: .5pt solid #111; padding-top: 1mm; }}
.blk > .body > :first-child {{ margin-top: 0; }}
h3 {{ font-size: 11pt; margin: 4mm 0 1.5mm; letter-spacing: -.01em; font-weight: 600; page-break-after: avoid; }}
p {{ margin: 0 0 2.2mm; }}
ul {{ list-style: none; padding: 0; margin: 0 0 2.5mm; }}
ul li {{ padding-left: 5mm; position: relative; margin: .5mm 0; }}
ul li::before {{ content: '—'; position: absolute; left: 0; }}
ol {{ list-style: none; counter-reset: s; padding: 0; margin: 0 0 3mm; }}
ol li {{ counter-increment: s; display: grid; grid-template-columns: 7mm 1fr; margin: .8mm 0; page-break-inside: avoid; }}
ol li::before {{ content: counter(s, decimal-leading-zero); color: {RED}; font-weight: 700; font-size: 8.4pt; padding-top: .2mm; }}
.keep {{ border-top: 2pt solid {RED}; padding-top: 2mm; margin: 3mm 0 3.5mm; page-break-inside: avoid; }}
.keep .t {{ font-size: 6.9pt; letter-spacing: .13em; text-transform: uppercase; font-weight: 700; color: {RED}; margin-bottom: 1mm; }}
.quote {{ font-size: 14pt; line-height: 1.28; letter-spacing: -.015em; margin: 2mm 0 4mm; }}
figure {{ margin: 1mm 0 5mm; page-break-inside: avoid; }}
figure img {{ width: 100%; border: .5pt solid #111; display: block; }}
figure.half img {{ width: 62%; }}
figcaption {{ font-size: 7.2pt; margin-top: 1.4mm; display: grid; grid-template-columns: 14mm 1fr; }}
figcaption b {{ color: {RED}; }}
table {{ width: 100%; border-collapse: collapse; font-size: 8.4pt; margin: 0 0 3mm; }}
th {{ text-align: left; font-size: 6.8pt; letter-spacing: .12em; text-transform: uppercase; font-weight: 600; border-bottom: 1pt solid #111; padding: 1.2mm 2mm 1.2mm 0; }}
td {{ border-bottom: .3pt solid #bbb; padding: 1.5mm 2mm 1.5mm 0; vertical-align: top; }}
tr {{ page-break-inside: avoid; }}
.tag {{ display: inline-block; white-space: nowrap; font-size: 6.6pt; letter-spacing: .1em; text-transform: uppercase; border: .5pt solid #111; padding: 0 1.2mm; font-weight: 600; }}
.tag.r {{ border-color: {RED}; color: {RED}; }}
.two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6mm; }}
.flow {{ display: grid; grid-template-columns: repeat(5, 1fr); border-top: 1pt solid #111; margin: 1mm 0 4mm; }}
.flow div {{ border-right: .5pt solid #111; padding: 2mm 2mm 2mm 0; font-size: 7.6pt; line-height: 1.3; }}
.flow div:last-child {{ border-right: 0; }}
.flow div b {{ display: block; color: {RED}; font-size: 13pt; letter-spacing: -.02em; margin-bottom: 1mm; }}
code {{ font-family: 'JetBrains Mono', Consolas, monospace; font-size: 7.8pt; }}
"""


class G:
    def __init__(self):
        self.out: list[str] = []
        self.toc: list[tuple[int, str, str, str]] = []
        self.n = 0
        self.sub = 0
        self.nfig = 0

    # structure ---------------------------------------------------------
    def chap(self, title: str, intro: str = ""):
        self.n += 1
        self.sub = 0
        sid = f"s{self.n}"
        num = f"{self.n:02d}"
        self.toc.append((1, num, title, sid))
        self.out.append(f'<section class="chap"><div class="chap-head"><div class="num"><span class="mark">ZZ{sid}ZZ</span>{num}</div>'
                        f'<h2>{H.escape(title)}</h2>' + (f'<div class="intro">{intro}</div>' if intro else "") + "</div>")

    def end(self):
        self.out.append("</section>")

    def block(self, label: str, body: str, toc: bool = False):
        mark = ""
        if toc:
            self.sub += 1
            sid = f"s{self.n}x{self.sub}"
            self.toc.append((2, "", label, sid))
            mark = f'<span class="mark">ZZ{sid}ZZ</span>'
        self.out.append(f'<div class="blk"><div class="lab">{mark}{label}</div><div class="body">{body}</div></div>')

    # contenus ----------------------------------------------------------
    @staticmethod
    def ol(*items):
        return "<ol>" + "".join(f"<li><span>{i}</span></li>" for i in items) + "</ol>"

    @staticmethod
    def ul(*items):
        return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"

    @staticmethod
    def keep(text, title="À retenir"):
        return f'<div class="keep"><div class="t">{title}</div>{text}</div>'

    @staticmethod
    def table(head, rows):
        return "<table><thead><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>" + \
            "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table>"

    def fig(self, name: str, caption: str, half: bool = False):
        self.nfig += 1
        im = Image.open(SHOTS / f"{name}.png").convert("RGB")
        if im.width > 2000:
            im = im.resize((2000, int(im.height * 2000 / im.width)), Image.LANCZOS)
        if im.height > im.width * 1.05 and not half:
            im = im.crop((0, 0, im.width, int(im.width * 1.05)))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=84, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return (f'<figure class="{"half" if half else ""}"><img src="data:image/jpeg;base64,{b64}">'
                f'<figcaption><b>Fig. {self.nfig:02d}</b><span>{caption}</span></figcaption></figure>')

    def render(self) -> str:
        today = date.today().strftime("%d.%m.%Y")
        toc = "".join(
            f'<div class="row{" sub" if lvl == 2 else ""}"><span class="n">{num}</span><span>{H.escape(t)}</span><span class="p" data-toc="{sid}"></span></div>'
            for lvl, num, t, sid in self.toc)
        cover = f"""<section class="cover"><div class="grid"></div><div class="bar"></div>
<div class="kicker">Archipel41<br>Guide pratique<br>Version 1.0</div>
<h1>Archipel41.<br>Mode<br>d'emploi.</h1>
<div class="lead">Utiliser l'application, partie par partie, et tirer le meilleur de chacune de ses fonctions — pour l'agence d'architecture.</div>
<div class="meta"><div><b>Édition</b>{today}</div><div><b>Public</b>Architectes, chefs de projet, collaborateurs</div><div><b>Plateformes</b>Windows · navigateur · tablette · smartphone</div></div></section>"""
        return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Archipel41 — Guide pratique</title><style>{CSS}</style></head>
<body>{cover}<section class="toc"><h2>Sommaire</h2>{toc}</section>{''.join(self.out)}</body></html>"""


def build() -> G:
    g = G()

    # ================================================================ 01
    g.chap("Comprendre Archipel41",
           "Un seul outil pour ce qui, dans une agence, est d'ordinaire dispersé entre tableurs, dossiers partagés, agendas et courriels.")
    g.block("L'idée", "<div class='quote'>Archipel41 lit, calcule, compare et propose. L'architecte décide.</div>"
            "<p>Le logiciel prend en charge la part répétitive du métier — ressaisir des devis, vérifier des totaux, chercher un article de règlement, "
            "tenir un planning à jour — pour libérer du temps de conception et de décision.</p>")
    g.block("Trois principes", g.table(["Principe", "Ce que cela signifie pour vous"], [
        ["<b>L'architecte décide</b>", "Aucune donnée extraite n'est validée, aucun planning n'est modifié sans l'action d'un utilisateur habilité."],
        ["<b>Des chiffres exacts</b>", "Totaux, TVA et arrondis sont recalculés par un moteur de calcul, jamais par l'intelligence artificielle."],
        ["<b>Rien d'inventé</b>", "Une information absente est signalée comme telle ; chaque réponse cite sa source."],
    ]))
    g.block("Les 11 parties", g.table(["Chap.", "Partie", "Sert à"], [
        ["04", "Tableau de bord", "Voir en une minute ce qui demande une action"],
        ["05", "Projets et chantiers", "Tout savoir d'une opération, de l'esquisse à la réception"],
        ["06", "Devis et comparateur", "Lire, contrôler et comparer les offres des entreprises"],
        ["07", "Agenda", "Organiser rendez-vous, réunions et visites"],
        ["08", "Planning et météo", "Ordonner le chantier et anticiper les intempéries"],
        ["09", "Urbanisme", "Connaître les contraintes d'un terrain"],
        ["10", "Assistant IA", "Interroger documents et projets en langage courant"],
        ["11", "Documents", "Classer, versionner, retrouver toutes les pièces"],
        ["12", "Clients et entreprises", "Tenir l'annuaire et l'historique des relations"],
        ["13", "Finances", "Suivre budgets, marchés, factures et paiements"],
        ["14", "Rapports", "Produire des documents prêts à envoyer"],
    ]))
    g.block("Sans IA, avec IA", "<p>Archipel41 fonctionne entièrement <b>sans</b> fournisseur d'intelligence artificielle : extraction des devis par règles, "
            "recherche dans vos documents, conclusions automatiques. Un fournisseur configuré (Claude, Mistral, OpenAI ou un modèle local) ajoute "
            "la rédaction : conclusions argumentées, synthèses, réponses de l'assistant.</p>")
    g.end()

    # ================================================================ 02
    g.chap("Premiers pas", "Installer, ouvrir, s'orienter. Dix minutes suffisent.")
    g.block("Installer", g.ol("Lancez <b>Archipel41-Setup-1.0.0-x64.exe</b>. Si Windows affiche « Windows a protégé votre ordinateur » : <b>Informations complémentaires</b>, puis <b>Exécuter quand même</b>.",
                              "Acceptez les conditions, choisissez <b>Pour moi uniquement</b>, puis <b>Installer</b>.",
                              "Ouvrez Archipel41 depuis l'icône du Bureau. Le premier démarrage prend une vingtaine de secondes."))
    g.block("Choisir", g.ol("<b>Explorer la démonstration</b> : une agence fictive complète pour découvrir sans rien saisir.",
                            "<b>Créer mon agence</b> : votre agence réelle et votre compte administrateur.") +
            g.keep("Les deux agences sont strictement séparées. La démonstration est signalée en permanence par un bandeau ; elle ne se mélange jamais à vos données.") +
            g.fig("01_premier_demarrage", "L'écran de bienvenue."))
    g.block("S'orienter", g.fig("44_tableau_de_bord", "L'interface : modules à gauche, outils en haut, contenu au centre.") +
            g.table(["Élément", "Usage"], [
                ["Barre latérale", "Les 11 parties, puis Paramètres et votre compte. Sur téléphone : bouton ☰."],
                ["Sélecteur de projet", "Fixe le <b>projet actif</b> ; les autres parties s'y rapportent automatiquement."],
                ["Recherche", "Retrouve un projet, une entreprise, un devis… et cherche aussi dans le <b>contenu</b> des documents."],
                ["Badge de connexion", "En ligne, hors ligne, synchronisé. Un clic lance une synchronisation."],
                ["Cloche", "Rappels des prochains rendez-vous."],
                ["Lune", "Mode sombre."],
                ["Assistant", "L'assistant IA, accessible depuis n'importe quel écran."],
            ]))
    g.block("Former l'équipe", g.ol("<b>Paramètres › Utilisateurs</b> : créez un compte par collaborateur.",
                                    "Attribuez le bon rôle (voir chapitre 17).",
                                    "Chacun change son mot de passe dans <b>Paramètres › Mon compte</b>."))
    g.end()

    # ================================================================ 03
    g.chap("Une journée avec Archipel41", "Comment l'outil s'insère dans le rythme réel d'une agence.")
    g.block("Le fil", '<div class="flow"><div><b>08:30</b>Tableau de bord : alertes, rendez-vous, tâches en retard.</div>'
            '<div><b>09:00</b>Devis reçus : import, vérification, validation.</div><div><b>11:00</b>Visite de chantier : compte rendu, incident, photos.</div>'
            '<div><b>14:00</b>Faisabilité d\'un terrain : urbanisme, règlement, rapport.</div><div><b>17:30</b>Comparatif et rapport au client ; finances à jour.</div></div>')
    g.block("Le bon réflexe", "<p>Commencez toujours par <b>choisir le projet actif</b> en haut de l'écran : devis, planning, documents, finances et assistant "
            "s'y placent automatiquement. Vous évitez ainsi de rattacher une pièce au mauvais dossier.</p>")
    g.end()

    # ================================================================ 04 – 14 modules
    def module(title, intro, fait, steps, profiter, figs, limite=None, extra=None):
        g.chap(title, intro)
        g.block("Ce qu'il fait", fait)
        g.block("Comment l'utiliser", steps)
        if extra:
            for lab, body in extra:
                g.block(lab, body)
        g.block("Pour en profiter", profiter + (g.keep(limite, "Limite à connaître") if limite else ""))
        if figs:
            g.block("Écrans", "".join(g.fig(n, c) for n, c in figs))
        g.end()

    module("Tableau de bord", "La première page de la journée.",
           "<p>Rassemble les projets actifs, chantiers en cours, devis à vérifier, rendez-vous, tâches prioritaires, budgets, alertes, météo des chantiers "
           "et activité récente de l'équipe — avec une <b>synthèse du jour</b> rédigée automatiquement.</p>",
           g.ol("Filtrez par période (7, 30 ou 90 jours), par projet ou par collaborateur.",
                "Lisez la synthèse du jour, puis traitez les alertes, des plus graves (point rouge) aux moins urgentes.",
                "Cliquez sur un élément pour l'ouvrir directement."),
           g.ul("Faites-en votre rituel du matin : cinq minutes pour ne rien laisser passer.",
                "Filtrez sur un collaborateur pour préparer un point individuel.",
                "Renseignez l'adresse des chantiers pour voir leur météo à trois jours."),
           [("49_mode_sombre", "Le tableau de bord, ici en mode sombre.")])

    module("Projets et chantiers", "La fiche unique de chaque opération.",
           "<p>Maître d'ouvrage, équipe, phases de la mission (ESQ, APS, APD, PC, PRO, DCE, ACT, EXE/VISA, DET, AOR), terrain, lots, entreprises, "
           "échéances, incidents, documents et avancement.</p>",
           g.ol("<b>Nouveau projet</b> : code, nom, maître d'ouvrage, adresse, surface, budget.",
                "Onglet <b>Phases</b> : désactivez celles hors mission, datez les autres, cochez la phase en cours.",
                "Onglet <b>Lots</b> : un lot par corps d'état, avec budget et entreprise attributaire.",
                "Onglets <b>Terrain</b>, <b>Équipe</b>, <b>Incidents</b>, <b>Documents</b> : complétez au fil de l'eau."),
           g.ul("Cochez <b>Projet confidentiel</b> pour un dossier sensible : seule son équipe le voit, et il n'est jamais envoyé à une IA externe sans autorisation.",
                "Tenez la phase en cours et l'avancement à jour : ils alimentent le tableau de bord.",
                "Signalez un incident le jour même ; il apparaît dans les rapports de chantier."),
           [("10_fiche_projet", "La fiche projet."), ("11_phases_projet", "Les phases de la mission, adaptables au contrat.")])

    module("Devis et comparateur", "La partie qui fait gagner le plus de temps.",
           "<p>Lit les devis — PDF, PDF scannés, images, Excel, CSV, Word, archives ZIP —, en extrait chaque ligne, contrôle tous les calculs, "
           "puis compare les offres entre elles, avec la DPGF et le CCTP, jusqu'à une conclusion argumentée.</p>",
           g.ol("Choisissez le projet et le lot, puis déposez les devis dans la zone d'import.",
                "Onglet <b>DPGF et CCTP</b> : déposez la DPGF (référence des quantités) et le CCTP (exigences techniques).",
                "Ouvrez chaque devis : comparez avec le document affiché à droite, corrigez si besoin, <b>Enregistrez</b>, puis <b>Validez</b>.",
                "Cochez les devis d'un même lot et cliquez sur <b>Comparer</b>.",
                "Lisez le classement, filtrez le tableau, consultez la conclusion ; exportez en Excel ou en rapport PDF."),
           g.ul("Importez <b>toujours la DPGF</b> avant de comparer : c'est elle qui rend les offres comparables poste par poste.",
                "Regardez le <b>montant à périmètre comparable</b> : il réintègre ce que l'offre a oublié ou exclu.",
                "Utilisez le filtre « Non renseignés / exclus » pour préparer vos questions aux entreprises.",
                "Un prix très inférieur à la médiane n'est pas une bonne affaire avant d'être justifié."),
           [("16_revue_devis", "Vérification d'un devis : calculs contrôlés, anomalies, document source."),
            ("20_comparatif_tableau", "Le comparatif : classement et tableau ligne à ligne."),
            ("22_comparatif_conclusion", "La conclusion argumentée.")],
           "Le contrôle du CCTP vérifie que les exigences sont <i>mentionnées</i> dans les offres, pas la conformité réelle des ouvrages.",
           extra=[("Les 7 statuts", g.table(["Statut", "Lecture"], [
               ['<span class="tag">Inclus</span>', "Poste chiffré, ou mentionné « compris »."],
               ['<span class="tag r">Non inclus</span>', "Exclu <b>expressément</b> par l'entreprise."],
               ['<span class="tag r">Non renseigné</span>', "<b>Absent</b> de l'offre, sans exclusion : à faire préciser. Ce n'est pas une exclusion."],
               ['<span class="tag">Optionnel</span>', "Proposé en option, hors total."],
               ['<span class="tag">Variante</span>', "Solution alternative, hors total."],
               ['<span class="tag">Non comparable</span>', "Unité différente de la référence (m² au lieu de ml…)."],
               ['<span class="tag">À vérifier</span>', "Correspondance incertaine ou ligne « pour mémoire »."],
           ]) + g.keep("Une prestation absente n'est jamais confondue avec une prestation exclue. C'est la distinction la plus utile en analyse des offres.")),
                  ("Le classement", "<p>Chaque offre reçoit un score sur 100 : <b>prix</b> à périmètre comparable 50&nbsp;%, <b>complétude</b> 25&nbsp;%, "
                   "<b>risques</b> (anomalies, réserves, prix anormaux) 15&nbsp;%, <b>délai</b> 10&nbsp;%. Le détail est affiché : le classement est transparent et discutable.</p>")])

    module("Agenda", "Rendez-vous, réunions et visites, sans double réservation.",
           "<p>Vues jour, semaine et mois ; participants internes et externes ; rappels ; comptes rendus et documents associés ; détection des conflits.</p>",
           g.ol("<b>+ Rendez-vous</b>, ou double-clic sur un créneau.",
                "Objet, type, projet, horaires, lieu, participants, rappel.",
                "Un encadré signale tout conflit avec l'agenda d'un participant.",
                "Après la réunion : rédigez le compte rendu, cliquez sur <b>Résumer</b>, puis générez le PDF."),
           g.ul("Rattachez chaque rendez-vous à son projet : il nourrit la fiche projet et l'assistant.",
                "Notez dans le compte rendu qui fait quoi et pour quand : la synthèse en extrait les actions."),
           [("26_agenda_semaine", "La vue semaine."), ("25_conflit_agenda", "Un conflit détecté avant enregistrement.")],
           "L'agenda n'est pas encore synchronisé avec Outlook ou Google Agenda.")

    module("Planning et météo", "Ordonner le chantier, anticiper le temps qu'il fera.",
           "<p>Diagramme de Gantt interactif — tâches, durées, jalons, dépendances, responsables, entreprises, avancement, retards, chemin critique — "
           "et prévisions météo à 14 jours croisées avec la nature des travaux.</p>",
           g.ol("<b>+ Tâche</b> : nom, début, durée, dépendances et surtout <b>type d'activité</b> (béton, couverture, façade…).",
                "Glissez une barre pour la déplacer ; tirez son bord droit pour changer sa durée.",
                "<b>Figer la référence</b> pour mesurer ensuite les glissements.",
                "Onglet <b>Météo</b> : lisez l'analyse, puis <b>Proposer des ajustements</b>.",
                "Un chef de projet accepte ou refuse chaque proposition ; les tâches suivantes se recalent seules."),
           g.ul("Le contour rouge indique le <b>chemin critique</b> : c'est là qu'un retard coûte le plus.",
                "Mettez à jour l'avancement chaque semaine : l'écart avec l'avancement attendu révèle les retards.",
                "Confrontez les seuils météo au CCTP et aux fiches techniques des produits."),
           [("46_planning_gantt", "Le Gantt : dépendances, chemin critique, retards."),
            ("47_meteo_propositions", "Analyse météo et propositions à valider.")],
           "Les prévisions sont fiables à quelques jours ; au-delà, elles restent indicatives.")

    module("Urbanisme", "Les contraintes d'un terrain, sources à l'appui.",
           "<p>À partir d'une adresse, d'une référence cadastrale ou de coordonnées : parcelle, surface, document d'urbanisme, zonage, prescriptions, "
           "servitudes, patrimoine, risques — puis analyse du règlement du PLU, article par article, avec indicateurs de faisabilité.</p>",
           g.ol("Saisissez le terrain et cliquez sur <b>Analyser la parcelle</b>.",
                "Lisez la fiche et l'encadré <b>Données indisponibles</b>.",
                "Importez le règlement du PLU dans Documents, choisissez-le, vérifiez la zone, cliquez sur <b>Analyser</b>.",
                "Consultez extraits, valeurs, indicateurs, puis générez le <b>rapport de faisabilité</b>."),
           g.ul("Utilisez-le dès le premier rendez-vous client : en quelques minutes, vous savez ce que le terrain permet.",
                "Un indicateur comme l'emprise maximale est calculé à partir de la valeur <i>citée</i> : la source est toujours affichée.",
                "Vérifiez la version opposable du règlement et sécurisez le projet par un certificat d'urbanisme."),
           [("48_urbanisme", "Analyse d'un terrain fictif et de son règlement.")],
           "Archipel41 n'invente aucune règle : un thème absent du règlement fourni est signalé comme tel.")

    module("Assistant IA", "Poser une question, obtenir une réponse sourcée.",
           "<p>Interroge vos documents, vos projets, vos comptes rendus et vos archives, dans le contexte du projet actif, et cite ses sources.</p>",
           g.ol("Ouvrez l'assistant depuis la barre latérale ou le bouton en haut à droite.",
                "Choisissez le contexte : un projet ou toute l'agence.",
                "Posez votre question en langage courant ; dépliez les sources pour vérifier."),
           g.ul("Soyez précis : « Quelle classe de béton exige le CCTP pour les fondations ? » plutôt que « béton ? ».",
                "Demandez des synthèses : « Résume les décisions des trois dernières réunions de chantier ».",
                "Demandez des risques : « Quels points du comparatif dois-je faire préciser aux entreprises ? »."),
           [("32_assistant", "Une réponse citant l'article du règlement.")],
           "Les documents confidentiels ne quittent jamais l'agence sans l'autorisation explicite de l'administrateur.")

    module("Documents", "Toutes les pièces, au même endroit, dans leur dernière version.",
           "<p>Import, aperçu, classement, versions, historique, recherche dans le contenu, rattachement aux projets, export groupé. "
           "PDF, Word, Excel, images, et fichiers DWG, DXF, IFC, PLN, PLA.</p>",
           g.ol("<b>Importer</b> ou glisser-déposer ; une archive ZIP est dépliée automatiquement.",
                "Ouvrez un document pour l'aperçu, le classement, les versions et l'historique.",
                "<b>Nouvelle version</b> plutôt que nouveau document : l'historique reste intact.",
                "Cherchez par nom ou par contenu ; exportez une sélection en ZIP."),
           g.ul("Choisissez la bonne catégorie : Devis, CCTP, DPGF, Urbanisme… Elle sert aux autres parties.",
                "Les documents scannés sont lus automatiquement : ils deviennent eux aussi interrogeables."),
           [("30_documents", "La bibliothèque et la recherche dans le contenu.")],
           "Les fichiers de CAO et de BIM sont conservés et versionnés, mais s'ouvrent dans votre logiciel métier.")

    module("Clients et entreprises", "L'annuaire vivant de l'agence.",
           "<p>Coordonnées, contacts, spécialités, devis, marchés, projets, documents, historique des échanges et observations.</p>",
           g.ol("Onglet <b>Clients</b> ou <b>Entreprises</b>, puis <b>Nouveau</b>.",
                "Complétez la fiche et les contacts.",
                "Sur la fiche : projets, devis, marchés, documents ; notez chaque échange dans <b>Historique</b>."),
           g.ul("Créez les entreprises <b>avant</b> d'importer leurs devis : le rattachement devient automatique.",
                "Utilisez l'évaluation (1 à 5) et les observations pour capitaliser l'expérience de l'agence."),
           [("08_annuaire_entreprises", "L'annuaire des entreprises.")])

    module("Finances", "Le budget sous contrôle, lot par lot.",
           "<p>Budget initial et actualisé, marchés, travaux supplémentaires, factures, acomptes, situations, paiements, dépenses, honoraires et écarts.</p>",
           g.ol("Sans projet actif : vue d'ensemble de tous les projets.",
                "Onglet <b>Écritures</b> : saisissez chaque marché, avenant, situation, facture, paiement ; le TTC est calculé.",
                "Onglet <b>Synthèse par lot</b> : budget, engagé, facturé, écart.",
                "Exportez le rapport financier en Excel."),
           g.ul("Enregistrez chaque avenant en « travaux supplémentaires » : le budget actualisé reste juste.",
                "Renseignez les échéances : les retards de paiement remontent sur le tableau de bord."),
           [("34_finances_projet", "La synthèse financière d'un projet.")],
           "Archipel41 n'est pas un logiciel de comptabilité.")

    module("Rapports", "Des documents prêts à envoyer, aux couleurs de l'agence.",
           "<p>Rapports de devis, urbanistiques, de chantier, comptes rendus, rapports financiers et synthèses de projets — en PDF, Excel, Word ou CSV.</p>",
           g.ol("Choisissez le type de rapport, le projet et, selon le cas, le comparatif, l'analyse ou le rendez-vous.",
                "Choisissez le format, puis <b>Générer et télécharger</b>.",
                "Le rapport est aussi classé dans les documents du projet."),
           g.ul("PDF pour envoyer, Word pour compléter avant envoi, Excel pour retravailler les chiffres.",
                "Régénérez le rapport après chaque modification : il reflète l'état du moment."),
           [("35_rapports", "La génération des rapports.")])

    # ================================================================ scénarios
    g.chap("Quatre scénarios complets", "Les enchaînements qui font gagner le plus de temps.")
    g.block("Analyse des offres", g.ol("Projet actif, lot sélectionné.", "Import de la DPGF et du CCTP.", "Import de tous les devis en une fois (ou en ZIP).",
                                       "Vérification et validation de chaque devis.", "Comparaison, filtre « non renseignés / exclus ».",
                                       "Questions écrites aux entreprises, nouvelle version des devis.", "Comparatif final, rapport PDF au maître d'ouvrage.",
                                       "Saisie du marché retenu dans Finances, entreprise attributaire dans le lot."), toc=True)
    g.block("Suivi de chantier", g.ol("Planning avec types d'activité et référence figée.", "Chaque lundi : météo, propositions d'ajustement.",
                                      "Réunion de chantier dans l'Agenda, compte rendu et synthèse.", "Incidents dans la fiche projet.",
                                      "Situations et paiements dans Finances.", "Rapport de chantier mensuel au client."), toc=True)
    g.block("Étude de faisabilité", g.ol("Analyse de la parcelle par adresse.", "Import du règlement du PLU.", "Analyse de la zone, indicateurs.",
                                         "Question à l'assistant sur un point précis.", "Rapport de faisabilité au client."), toc=True)
    g.block("Clôture d'un projet", g.ol("Réception : incidents clos, avancement à 100&nbsp;%.", "Derniers paiements dans Finances.",
                                        "Synthèse de projet en PDF.", "Statut « Archivé » : le projet sort des listes actives mais reste consultable."), toc=True)
    g.end()

    # ================================================================ équipe
    g.chap("Travailler en équipe, partout", "Hors connexion, à plusieurs, sur tous les écrans.")
    g.block("Hors connexion", "<p>L'application Windows garde toutes vos données sur le poste : elle fonctionne sans Internet. Dans le navigateur, les pages consultées "
            "restent disponibles et vos modifications sont mises en file d'attente, puis envoyées au retour du réseau.</p>" +
            g.fig("43_hors_connexion", "Hors connexion : les modifications attendent, rien n'est perdu."))
    g.block("À plusieurs", "<p>Le travail en équipe passe par un <b>serveur central</b> de l'agence. Chaque poste s'y synchronise automatiquement. "
            "Si deux personnes modifient le même élément, Archipel41 ne tranche pas : il vous montre les deux versions et vous choisissez.</p>"
            + g.keep("Le stockage local seul ne permet pas de partager des données entre appareils : pour travailler à plusieurs, il faut le serveur central."))
    g.block("Sur téléphone", "<div class='two'>" + g.fig("51_smartphone_accueil", "Le tableau de bord sur smartphone.", True)
            + g.fig("52_smartphone_menu", "Le menu des parties.", True) + "</div>")
    g.end()

    g.chap("Rôles et sécurité", "Chacun voit et fait ce qui correspond à son rôle.")
    g.block("Les rôles", g.table(["Rôle", "Peut"], [
        ["Administrateur", "Tout, y compris utilisateurs, paramètres, sauvegardes et journal d'audit."],
        ["Chef de projet", "Créer, modifier, supprimer et <b>valider</b> (devis, ajustements de planning)."],
        ["Collaborateur", "Créer et modifier."],
        ["Lecture seule", "Consulter."],
    ]))
    g.block("Les protections", g.ul("Projets confidentiels visibles de leur seule équipe.", "Clés d'accès aux services chiffrées, jamais réaffichées.",
                                    "Journal d'audit de toutes les actions sensibles.", "Sauvegardes vérifiées par empreinte, restauration confirmée."))
    g.block("Sauvegarder", g.ol("<b>Paramètres › Sauvegardes › Sauvegarder maintenant</b>.", "Rangez l'archive sur un disque externe ou un espace partagé.",
                                "Au moins une fois par semaine, et toujours avant une mise à jour."))
    g.end()

    g.chap("Dix conseils pour en tirer le meilleur")
    g.block("Les conseils", g.ol(
        "Choisissez toujours le <b>projet actif</b> avant de travailler.",
        "Créez les <b>entreprises</b> avant d'importer leurs devis.",
        "Importez la <b>DPGF</b> avant de comparer.",
        "Ne confondez jamais « <b>non renseigné</b> » et « <b>non inclus</b> ».",
        "Donnez un <b>type d'activité</b> à chaque tâche extérieure du planning.",
        "Rattachez chaque rendez-vous et chaque document à son <b>projet</b>.",
        "Marquez <b>confidentiels</b> les dossiers sensibles.",
        "Posez à l'assistant des <b>questions précises</b> et vérifiez ses sources.",
        "Tenez les <b>finances</b> à jour à chaque situation de travaux.",
        "<b>Sauvegardez</b> chaque semaine."))
    g.block("Pour aller plus loin", "<p>Le <b>Guide utilisateur</b> détaille chaque écran ; le <b>Guide d'installation</b> couvre la configuration, la synchronisation "
            "et le dépannage ; la <b>Documentation technique</b> s'adresse à votre prestataire informatique.</p>")
    g.end()
    return g


if __name__ == "__main__":
    g = build()
    html_path = HERE / "GUIDE_PRATIQUE.html"
    html_path.write_text(g.render(), encoding="utf-8")
    subprocess.run(["node", str(HERE / "render_pdf.cjs"), str(html_path), str(HERE.parent / "ARCHIPEL41_GUIDE_PRATIQUE.pdf"), "Guide pratique", "swiss"], check=True)
