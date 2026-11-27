"""Référentiel documentaire ARCHIPEL 41 : arborescence type d'un projet, suggestion de classement, contrôle de nommage.

Principes (validés par l'agence le 27/11/2026) :
- une suggestion n'est qu'une proposition : le document n'est classé que si un utilisateur l'accepte ;
- chaque suggestion cite la règle ou la note « Classer ici » qui la justifie, avec un niveau de certitude ;
- le contrôle de nommage (R50 / R51) conseille, il ne renomme jamais : le nom de fichier d'origine reste conservé
  dans les versions (R52).
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "arborescence_a41.json"


@lru_cache(maxsize=1)
def template() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def folders() -> list[dict]:
    return template()["dossiers"]


def folder_paths() -> set[str]:
    return {f["path"] for f in folders()}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[_\-.]+", " ", s)


# (motif sur le nom + la description + le début du texte, dossier, règle source, certitude)
# L'ordre compte : les règles les plus spécifiques d'abord.
RULES: list[tuple[str, str, str, str]] = [
    (r"\bordre de service\b|\bos\s?n|\bos\b.*sign|\bexe1 ?t\b", "5-Réalisation/05_Organisation chantier/64_OS", "R49 — original de l'OS signé dans 64_OS", "Probable"),
    (r"\bavenant", "5-Réalisation/01_Marchés - OS/23_Avenants Marchés", "Dossier 23_Avenants Marchés", "Probable"),
    (r"acte d engagement|\bmarche de base\b|\bmarche de travaux\b", "5-Réalisation/01_Marchés - OS/22_Marchés de Base", "Note « Classer ici » de 22_Marchés de Base (acte d'engagement)", "Probable"),
    (r"sous traitan", "5-Réalisation/01_Marchés - OS/24_Agrement sous-traitants", "Dossier 24_Agrement sous-traitants", "Probable"),
    (r"\bdiuo\b|intervention ulterieure", "5-Réalisation/13_Fin Travaux/142_DIUO", "Note « Classer ici » de 142_DIUO", "Probable"),
    (r"\bdgd\b|decompte general|decompte final", "5-Réalisation/13_Fin Travaux/143_DGD", "Note « Classer ici » de 143_DGD", "Probable"),
    (r"\bdoe\b|ouvrages executes|recolement", "5-Réalisation/13_Fin Travaux/141_DOE", "Note « Classer ici » de 141_DOE", "Probable"),
    (r"parfait achevement|\bgpa\b|garantie decennale|biennale", "5-Réalisation/13_Fin Travaux/144_Parfait Achèvement", "Note « Classer ici » de 144_Parfait Achèvement", "Probable"),
    (r"\bdaact\b|\bdact\b|achevement des travaux|attestation", "5-Réalisation/13_Fin Travaux/145-Attestations", "Note « Classer ici » de 145-Attestations", "À confirmer"),
    (r"\bopr\b|reception des travaux|levee des reserves|\breserves\b|pv de reception", "5-Réalisation/12_OPR-Réception", "Note « Classer ici » de 12_OPR-Réception", "Probable"),
    (r"hors d eau|hors d air|reception inter entreprises", "5-Réalisation/11_Jalons", "Note « Classer ici » de 11_Jalons", "Probable"),
    (r"fiche (d )?agrement|validation (des )?materiaux|fiche produit", "5-Réalisation/08_Visa/91_Visa Archi", "Modèles de 91_Visa Archi (fiche de validation fournitures / matériaux)", "Probable"),
    (r"suivi (des )?visa|liste previsionnelle", "5-Réalisation/08_Visa/93_Gestion des Visas", "Modèles de 93_Gestion des Visas", "Probable"),
    (r"\bvisa\b", "5-Réalisation/08_Visa/91_Visa Archi", "Dossier 08_Visa (visa de conformité architecturale)", "À confirmer"),
    (r"\bsynthese\b|note de calcul", "5-Réalisation/07_Synthese", "Note « Classer ici » de 07_Synthese", "À confirmer"),
    (r"echantillon|prototype|cellule temoin|pv d essai", "5-Réalisation/06_EXE entreprises/71_Lots/Temoins Echantillons", "Note « Classer ici » de Temoins Echantillons", "Probable"),
    (r"compte rendu de (reunion de )?chantier|\bcrc\b", "5-Réalisation/09_CR", "Note « Classer ici » de 09_CR", "Probable"),
    (r"\bodj\b|ordre du jour|\bcrr\b|\bcr\b|compte rendu", "1-Administration/12_Comptes-rendus", "R19 — CR des réunions d'études dans 12_Comptes-rendus", "À confirmer"),
    (r"\bdroc\b|ouverture de chantier", "5-Réalisation/05_Organisation chantier/63_DROC", "Dossier 63_DROC", "Probable"),
    (r"panneau de chantier", "5-Réalisation/05_Organisation chantier/61_Panneau chantier", "Dossier 61_Panneau chantier", "Probable"),
    (r"installation de chantier|\bpic\b", "5-Réalisation/05_Organisation chantier/62_Plan d'installation", "Dossier 62_Plan d'installation", "Probable"),
    (r"\bpgc\b|\bppsps\b|\bsps\b|hygiene et securite", "5-Réalisation/05_Organisation chantier/66_Hygiene et Securite", "Dossier 66_Hygiene et Securite", "À confirmer"),
    (r"situation de travaux|proposition de paiement|compte prorata|travaux modificatifs|\bftm\b", "5-Réalisation/03_Gestion Financière", "Note « Classer ici » de 03_Gestion Financière", "Probable"),
    (r"analyse des offres|rapport d analyse|negociation", "4-Economie - Appel Offres/06_Analyse/02_Analyse Offres", "Note « Classer ici » de 02_Analyse Offres", "Probable"),
    (r"designation|notification|lettre de refus", "4-Economie - Appel Offres/06_Analyse/03_Designation entreprises", "Note « Classer ici » de 03_Designation entreprises", "À confirmer"),
    (r"\bcctp\b|\bcctc\b|clauses techniques", "4-Economie - Appel Offres/03_CCTP", "Dossier 03_CCTP (CCTC avec les CCTP, réponse de l'agence)", "Probable"),
    (r"\bdpgf\b|decomposition du prix|\bbpu\b|\bdqe\b", "4-Economie - Appel Offres/04_DPGF", "Dossier 04_DPGF", "Probable"),
    (r"\bccap\b|\bccag\b|clauses administratives", "4-Economie - Appel Offres/02_CCAG-CCAP", "Dossier 02_CCAG-CCAP", "Probable"),
    (r"estimati|\bestimation\b", "4-Economie - Appel Offres/01_Estimatif", "Dossier 01_Estimatif", "Probable"),
    (r"\bdevis\b|\boffre\b|variante|fiche question", "4-Economie - Appel Offres/06_Analyse/01_Offres-Echanges", "Note « Classer ici » de 01_Offres-Echanges (offres par lot)", "Probable"),
    (r"permis de construire|\bpcm?\b|cerfa|declaration prealable|permis de demolir|recepisse|recours", "3-Autorisation", "Note « Enregistrements » de 3-Autorisation", "À confirmer"),
    (r"\bplu\b|plan local d urbanisme|reglement d urbanisme", "2-Conception/01_Données d'entrée/Reglementations/PLU", "Note « Classer ici » de Reglementations (règles d'urbanisme)", "Probable"),
    (r"geotechni|etude de sol|\bg2\b|pollution|sondage", "2-Conception/01_Données d'entrée/Contexte-Existant/Géotechnique", "Note « Rapports - sol » de Contexte-Existant", "Probable"),
    (r"geometre|releve topo|topographi|bornage", "2-Conception/01_Données d'entrée/Contexte-Existant/Géometre", "Note « Relevés » de Contexte-Existant", "Probable"),
    (r"cadastr|parcellaire", "2-Conception/01_Données d'entrée/Contexte-Existant/Plan parcellaire", "Dossier Plan parcellaire", "Probable"),
    (r"amiante|diagnostic|relevé des existants|releve des existants", "2-Conception/01_Données d'entrée/Contexte-Existant", "Note « Relevés » de Contexte-Existant", "À confirmer"),
    (r"\bprogramme\b", "2-Conception/01_Données d'entrée/Programme", "Dossier Programme", "Probable"),
    (r"check ?list|liste (de controle|d exigences)|grille d analyse", "2-Conception/01_Données d'entrée/Check-list", "Dossier Check-list", "Probable"),
    (r"tableau des surfaces|\bsurfaces\b", "2-Conception/02_Etudes/03_Sujets specifiques/10_Surfaces", "Note « Classer ici » de 10_Surfaces", "Probable"),
    (r"securite incendie|\bssi\b|desenfumage", "2-Conception/02_Etudes/03_Sujets specifiques/20_Securite incendie", "Dossier 20_Securite incendie", "À confirmer"),
    (r"\bhqe\b|breeam|\bleed\b|developpement durable|\bre2020\b", "2-Conception/02_Etudes/03_Sujets specifiques/21_Developt - Durable", "Note « Classer ici » de 21_Developt - Durable", "Probable"),
    (r"acousti", "2-Conception/02_Etudes/03_Sujets specifiques/60_Acoustique", "Dossier 60_Acoustique", "À confirmer"),
    (r"presentation", "2-Conception/02_Etudes/04_Presentations", "Dossier 04_Presentations", "À confirmer"),
    (r"facture|honoraires", "1-Administration/10_General/1_Contrat - Factures/Factures", "R48 — factures émises et reçues", "Probable"),
    (r"contrat de maitrise|lettre de commande|\bcontrat\b", "1-Administration/10_General/1_Contrat - Factures/Contrat", "Dossier Contrat (contrat de maîtrise d'œuvre)", "Probable"),
    (r"faits marquants|synoptique|planning general|planification", "1-Administration/10_General/2_Planification", "Liste Démarrage — planning et tableau des faits marquants", "Probable"),
    (r"annuaire", "", "Liste Démarrage — l'annuaire est à la racine du dossier projet", "Probable"),
    (r"courrier|\blettre\b|correspondance", "1-Administration/11_Correspondances", "R45 — correspondance par interlocuteur", "À confirmer"),
    (r"publication|communique|presse", "1-Administration/15_Communication", "Note « Classer ici » de 15_Communication", "À confirmer"),
]
PHASES = {"esq": "02_ESQ", "aps": "03_APS", "apd": "04_APD", "pcg": "05_PCG", "pro": "06_PRO", "dce": "07_DCE", "diag": "01_DIAG"}
# repli par catégorie lorsque aucun mot-clé ne s'applique
CATEGORY_FALLBACK = {
    "cctp": ("4-Economie - Appel Offres/03_CCTP", "catégorie « CCTP »"), "dpgf": ("4-Economie - Appel Offres/04_DPGF", "catégorie « DPGF »"),
    "devis": ("4-Economie - Appel Offres/06_Analyse/01_Offres-Echanges", "catégorie « devis »"),
    "contrat": ("1-Administration/10_General/1_Contrat - Factures/Contrat", "catégorie « contrat »"),
    "facture": ("1-Administration/10_General/1_Contrat - Factures/Factures", "catégorie « facture »"),
    "urbanisme": ("2-Conception/01_Données d'entrée/Reglementations", "catégorie « urbanisme »"),
    "courrier": ("1-Administration/11_Correspondances", "catégorie « courrier »"),
    "compte_rendu": ("1-Administration/12_Comptes-rendus", "catégorie « compte rendu »"),
    "plan": ("2-Conception/02_Etudes/02_Pièces graphiques", "catégorie « plan »"),
}


def suggest_folder(name: str, description: str | None = None, text: str | None = None, category: str | None = None,
                   project_status: str | None = None, extension: str | None = None) -> dict | None:
    """Propose un dossier de l'arborescence, avec la règle qui le justifie. Ne classe jamais automatiquement."""
    hay = _norm(" ".join(x for x in (name, description or "", (text or "")[:1500]) if x))
    title = _norm(" ".join(x for x in (name, description or "") if x))
    # livrable de phase : « …-APS-… » ou « … APD indice B » dans le nom
    m = re.search(r"\b(esq|aps|apd|pcg|pro|dce|diag)\b", title)
    if m and re.search(r"\bind(ice)?\b|\blivrable|\bdossier\b|\bplans?\b", title):
        return {"folder": f"2-Conception/03_Livrables/{PHASES[m.group(1)]}", "reason": f"Livrable de la phase {m.group(1).upper()} (nom du fichier)",
                "source": "R20 — chaque émission de livrable dans 03_Livrables", "certitude": "Probable"}
    for pat, folder, source, cert in RULES:
        # les mots-clés du titre comptent davantage que ceux du contenu
        where = "nom" if re.search(pat, title) else ("contenu" if re.search(pat, hay) else None)
        if not where:
            continue
        if folder == "5-Réalisation/09_CR" or folder == "1-Administration/12_Comptes-rendus":
            folder = "5-Réalisation/09_CR" if (project_status in ("chantier", "reception") or "chantier" in hay) else "1-Administration/12_Comptes-rendus"
        return {"folder": folder, "reason": f"Mot-clé reconnu dans le {where} du document", "source": source,
                "certitude": cert if where == "nom" else "À confirmer"}
    if (extension or "").lower() in ("jpg", "jpeg", "png", "heic", "webp") or category == "photo":
        f = "5-Réalisation/10_Photos" if project_status in ("chantier", "reception") else "2-Conception/01_Données d'entrée/Contexte-Existant/Photos"
        return {"folder": f, "reason": "Photographie, selon l'avancement du projet", "source": "Dossiers Photos (existant / chantier)", "certitude": "À confirmer"}
    if category in CATEGORY_FALLBACK:
        f, why = CATEGORY_FALLBACK[category]
        return {"folder": f, "reason": f"Déduit de la {why}", "source": "Catégorie du document", "certitude": "À confirmer"}
    return None


def check_name(name: str) -> dict:
    """Contrôle de nommage (conventions validées R50 / R51). Conseil uniquement : rien n'est renommé automatiquement."""
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    issues, fixed = [], stem
    m = re.match(r"^(\d{2})(\d{2})(\d{2})(?=[-_ ])", fixed)
    if m and 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3)) <= 31:
        issues.append("Date au format AAMMJJ : la convention est AAAA-MM-JJ (R50).")
        fixed = f"20{m.group(1)}-{m.group(2)}-{m.group(3)}" + fixed[6:]
    m = re.match(r"^(\d{2})[./](\d{2})[./](\d{4})(?=[-_ ])", fixed)
    if m:
        issues.append("Date au format JJ.MM.AAAA : la convention est AAAA-MM-JJ (R50).")
        fixed = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" + fixed[10:]
    if re.search(r"(?<=[A-Za-z0-9])_(?=[A-Za-z0-9])", fixed) and re.match(r"^(\d{4}-\d{2}-\d{2}|A41)", fixed):
        issues.append("Séparateur « _ » entre composantes : la convention est « - » (R50).")
        fixed = re.sub(r"(?<=[A-Za-z0-9])_(?=[A-Za-z0-9])", "-", fixed)
    if re.search(r"(^|-)MO(-|$)", fixed):
        issues.append("« MO » : la convention pour la maîtrise d'ouvrage est « MOA » (R51).")
        fixed = re.sub(r"(^|-)MO(?=-|$)", r"\1MOA", fixed)
    proposal = fixed + (f".{ext}" if ext else "")
    return {"conforme": not issues, "issues": issues, "proposition": proposal if issues else None,
            "note": "Conseil uniquement : le nom d'origine reste conservé dans l'historique des versions (R52)."}
