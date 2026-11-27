"""Remarques techniques et optimisation économique des offres — à qualité constante.

Principe : chercher les économies SANS dégrader la qualité.
- Une économie n'est jamais calculée à partir d'une offre techniquement inférieure
  à la référence, ni d'un prix anormalement bas : ces offres sont signalées, pas
  prises pour cible.
- La cible de négociation d'un poste est la MÉDIANE des prix conformes (et non le
  minimum), pour rester réaliste et éviter de pousser vers la malfaçon.
- Les coûts cachés (postes absents, quantités sous-estimées) sont ajoutés pour
  obtenir le coût réel probable de chaque offre.

Tous les montants sont calculés en arithmétique décimale exacte (Decimal) et
arrondis au centime (demi-supérieur), comme le moteur de calcul des devis.
"""
from __future__ import annotations

import statistics
from decimal import ROUND_HALF_UP, Decimal

from .calc import fr
from .numbers import normalize_unit
from .values import LABELS, by_kind, compare_value, extract_values

CENT = Decimal("0.01")
LOW_PRICE = -0.40          # ≤ −40 % de la médiane : prix anormalement bas
HIGH_PRICE = 0.10          # ≥ +10 % de la médiane conforme : levier de négociation
MIN_SAVING = Decimal("100")  # en dessous, le levier n'est pas signalé
QTY_GAP = 0.10             # écart de quantité significatif (10 %)
FORFAIT_UNITS = {"ft", "ens"}
SEVERITY_ORDER = {"haute": 0, "moyenne": 1, "info": 2}


def D(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def money(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def eur(v) -> str:
    return f"{fr(v)} €"


def _qty(v) -> str:
    return fr(v, None)


def _remark(out: list, *, severity: str, category: str, message: str, action: str, quote: dict | None = None,
            row: dict | None = None, impact=None, impact_kind: str | None = None) -> None:
    out.append({
        "severity": severity, "category": category, "message": message, "action": action,
        "quote_id": quote["quote_id"] if quote else None, "company": quote["company"] if quote else None,
        "row_key": row["key"] if row else None, "designation": row["designation"] if row else None,
        "impact_ht": float(money(impact)) if impact is not None else None, "impact_kind": impact_kind,
    })


def analyse(result: dict) -> dict:
    """Complète un résultat de compare() : caractéristiques techniques par cellule,
    remarques techniques, leviers d'économie et coût réel probable de chaque offre."""
    rows = result["rows"]
    summaries = {s["quote_id"]: s for s in result["summaries"]}
    has_ref = result.get("has_reference")
    remarks: list[dict] = []
    levers: dict[str, list[dict]] = {qid: [] for qid in summaries}
    hidden: dict[str, list[dict]] = {qid: [] for qid in summaries}
    inferior: dict[tuple[str, str], bool] = {}

    # ------------------------------------------------------------ 1) qualité technique
    for row in rows:
        ref_vals = by_kind(extract_values(row["designation"])) if (has_ref and not row.get("extra")) else {}
        row["specs"] = [v.to_dict() for v in ref_vals.values()]
        offer_vals: dict[str, dict] = {}
        for qid, c in row["cells"].items():
            vals = by_kind(extract_values(c.get("designation") or "")) if c.get("designation") else {}
            c["specs"] = [v.to_dict() for v in vals.values()]
            offer_vals[qid] = vals
            if c["status"] not in ("inclus", "a_verifier") or not ref_vals:
                continue
            q = summaries[qid]
            for kind, rv in ref_vals.items():
                ov = vals.get(kind)
                if ov is None:
                    if kind != "dimensions":
                        _remark(remarks, severity="moyenne", category="qualite", quote=q, row=row,
                                message=f"{LABELS[kind]} demandée ({rv.display()}) non précisée dans l'offre.",
                                action="Faire confirmer par écrit la caractéristique exacte proposée.")
                    continue
                verdict = compare_value(ov, rv)
                if verdict == "inferieur":
                    inferior[(row["key"], qid)] = True
                    c["quality"] = "inferieur"
                    _remark(remarks, severity="haute", category="qualite", quote=q, row=row,
                            message=f"Qualité inférieure à la référence : {LABELS[kind].lower()} {ov.display()} au lieu de {rv.display()}.",
                            action="Exiger la mise en conformité ou une moins-value justifiée ; ne pas retenir ce prix comme référence.")
                elif verdict == "different":
                    inferior[(row["key"], qid)] = True
                    c["quality"] = "different"
                    _remark(remarks, severity="moyenne", category="qualite", quote=q, row=row,
                            message=f"{LABELS[kind]} différente de la référence : {ov.display()} au lieu de {rv.display()}.",
                            action="Vérifier l'équivalence technique (fiche produit, avis de l'ingénieur) avant de comparer les prix.")
                elif verdict == "superieur":
                    c["quality"] = "superieur"
                    _remark(remarks, severity="info", category="qualite", quote=q, row=row,
                            message=f"Prestation supérieure à la demande : {LABELS[kind].lower()} {ov.display()} au lieu de {rv.display()}.",
                            action="Si ce surcroît n'est pas utile, demander une variante conforme à la référence (économie possible).")
        # Équivalence entre offres (avec ou sans DPGF)
        kinds = set().union(*[set(v) for v in offer_vals.values()]) if offer_vals else set()
        for kind in kinds:
            present = {qid: v[kind] for qid, v in offer_vals.items() if kind in v and row["cells"][qid]["status"] == "inclus"}
            if len(present) < 2 or len({str(v.value) for v in present.values()}) < 2 or kind in ref_vals:
                continue
            detail = ", ".join(f"{summaries[qid]['company']} {v.display()}" for qid, v in present.items())
            _remark(remarks, severity="moyenne", category="qualite", row=row,
                    message=f"Offres non équivalentes techniquement ({LABELS[kind].lower()}) : {detail}.",
                    action="Comparer à prestation égale : demander à chaque entreprise de chiffrer la même caractéristique.")
            # l'offre la moins performante ne sert pas de cible de prix
            ranked = sorted(present.items(), key=lambda kv: kv[1].value if not isinstance(kv[1].value, str) else 0)
            worst = ranked[0] if present[ranked[0][0]].better == "higher" else ranked[-1]
            if present[worst[0]].better != "equal":
                inferior[(row["key"], worst[0])] = True

    # ------------------------------------------------------------ 2) prix, quantités, périmètre
    for row in rows:
        ref_q = D(row["quantity"]) if row.get("quantity") else None
        ref_u = normalize_unit(row.get("unit"))
        conform: list[Decimal] = []
        for qid, c in row["cells"].items():
            if c["status"] == "inclus" and c.get("amount") and not inferior.get((row["key"], qid)) \
                    and (c.get("deviation") is None or c["deviation"] > LOW_PRICE):
                conform.append(D(c["amount"]))
        target = money(D(statistics.median(conform))) if len(conform) >= 2 else None
        row["target_ht"] = float(target) if target is not None else None
        row["conform_min"] = float(min(conform)) if conform else None

        for qid, c in row["cells"].items():
            q = summaries[qid]
            amount = D(c["amount"]) if c.get("amount") is not None else None
            # prix anormalement bas → risque qualité
            if c["status"] == "inclus" and c.get("deviation") is not None and c["deviation"] <= LOW_PRICE:
                _remark(remarks, severity="haute", category="prix", quote=q, row=row,
                        message=f"Prix anormalement bas ({c['deviation'] * 100:+.0f} % par rapport à la médiane) : {eur(c['amount'])} HT.",
                        action="Demander la justification (quantités, prestations comprises) : risque d'oubli, de malfaçon ou d'avenant.")
            # levier de négociation à qualité constante
            if c["status"] == "inclus" and amount and target and not inferior.get((row["key"], qid)) \
                    and amount > target * (1 + Decimal(str(HIGH_PRICE))) and amount - target >= MIN_SAVING:
                saving = money(amount - target)
                pct = float((amount - target) / target * 100)
                levers[qid].append({"kind": "prix", "row_key": row["key"], "designation": row["designation"],
                                    "amount_ht": float(amount), "target_ht": float(target), "saving_ht": float(saving),
                                    "text": f"Prix supérieur de {pct:.0f} % à la médiane des offres conformes : "
                                            f"{eur(amount)} → cible {eur(target)} (économie {eur(saving)})."})
            # quantités par rapport à la DPGF
            if has_ref and c["status"] == "inclus" and ref_q and c.get("quantity") and c.get("unit_price") is not None and not row.get("extra"):
                oq, pu = D(c["quantity"]), D(c["unit_price"])
                if ref_q and abs(oq - ref_q) / ref_q > Decimal(str(QTY_GAP)):
                    gap = money((oq - ref_q) * pu)
                    if oq > ref_q:
                        levers[qid].append({"kind": "quantite", "row_key": row["key"], "designation": row["designation"],
                                            "amount_ht": float(amount or 0), "target_ht": float(money(ref_q * pu)),
                                            "saving_ht": float(gap),
                                            "text": f"Quantité {_qty(oq)} {c.get('unit') or ''} au lieu de {_qty(ref_q)} (DPGF) : "
                                                    f"ramener à la quantité de référence fait économiser {eur(gap)}."})
                        _remark(remarks, severity="moyenne", category="quantite", quote=q, row=row, impact=gap, impact_kind="economie",
                                message=f"Quantité surestimée : {_qty(oq)} au lieu de {_qty(ref_q)} (DPGF), soit {eur(gap)} HT en trop.",
                                action="Demander la correction de la quantité ou la justification du métré.")
                    else:
                        hidden[qid].append({"kind": "sous_quantite", "row_key": row["key"], "designation": row["designation"],
                                            "amount_ht": float(-gap),
                                            "text": f"Quantité {_qty(oq)} au lieu de {_qty(ref_q)} : supplément probable {eur(-gap)} en cours de chantier."})
                        _remark(remarks, severity="haute", category="quantite", quote=q, row=row, impact=-gap, impact_kind="surcout",
                                message=f"Quantité sous-estimée : {_qty(oq)} au lieu de {_qty(ref_q)} (DPGF) — risque de travaux supplémentaires ≈ {eur(-gap)} HT.",
                                action="Faire chiffrer la quantité de la DPGF : l'offre paraît moins chère mais le coût final sera plus élevé.")
            # forfait sur un poste quantifié
            ou = normalize_unit(c.get("unit"))
            if c["status"] == "inclus" and ou in FORFAIT_UNITS and ref_u and ref_u not in FORFAIT_UNITS and ref_q:
                _remark(remarks, severity="moyenne", category="prix", quote=q, row=row,
                        message=f"Chiffré au forfait alors que la référence est en {row.get('unit')} ({_qty(ref_q)}).",
                        action="Demander la décomposition quantité × prix unitaire pour contrôler le prix et les futurs avenants.")
            # périmètre : postes absents ou exclus = coûts cachés
            if not row.get("extra") and c["status"] in ("non_renseigne", "non_inclus"):
                val = row.get("median") or row.get("estimate")
                if val:
                    hidden[qid].append({"kind": c["status"], "row_key": row["key"], "designation": row["designation"],
                                        "amount_ht": float(money(D(val))),
                                        "text": ("Exclu" if c["status"] == "non_inclus" else "Non renseigné")
                                                + f" : valorisé {eur(val)} (médiane des autres offres ou estimation DPGF)."})
                _remark(remarks, severity="haute" if c["status"] == "non_inclus" else "moyenne", category="perimetre",
                        quote=q, row=row, impact=D(val) if val else None, impact_kind="surcout" if val else None,
                        message=("Poste exclu par l'entreprise" if c["status"] == "non_inclus" else "Poste absent de l'offre (non renseigné)")
                                + (f" — valeur estimée {eur(val)} HT." if val else "."),
                        action="Faire préciser par écrit : inclus sans plus-value, oubli à chiffrer, ou exclusion à confier à un autre lot.")
            if c["status"] == "non_comparable":
                _remark(remarks, severity="moyenne", category="prix", quote=q, row=row,
                        message=c.get("note") or "Unité différente de la référence.",
                        action="Demander un prix dans l'unité de la référence pour pouvoir comparer.")

    # ------------------------------------------------------------ 3) conditions et lecture
    for q in result["summaries"]:
        for res in q.get("reserves") or []:
            _remark(remarks, severity="moyenne", category="conditions", quote=q,
                    message=f"Réserve de l'entreprise : « {res[:160]} ».", action="Faire lever la réserve avant attribution.")
        if q.get("validity_days") is not None and q["validity_days"] < 30:
            _remark(remarks, severity="info", category="conditions", quote=q,
                    message=f"Validité courte de l'offre : {q['validity_days']} jours.",
                    action="Demander une prolongation de validité si l'attribution risque d'être retardée.")
        for a in q.get("anomaly_details") or []:
            if a.get("severity") == "haute":
                _remark(remarks, severity="haute", category="calcul", quote=q,
                        message=a["message"] + (f" ({a['designation'][:60]})" if a.get("designation") else ""),
                        action="Demander un devis rectifié : le montant contractuel doit être arithmétiquement juste.")

    # ------------------------------------------------------------ 4) coût réel probable et synthèse
    offers = []
    for qid, s in summaries.items():
        base = D(s["total_ht"])
        hid = money(sum((D(h["amount_ht"]) for h in hidden[qid]), Decimal("0")))
        sav = money(sum((D(lv["saving_ht"]) for lv in levers[qid]), Decimal("0")))
        quality_issues = sum(1 for r in remarks if r["quote_id"] == qid and r["category"] == "qualite" and r["severity"] == "haute")
        offers.append({
            "quote_id": qid, "company": s["company"], "total_ht": float(base),
            "hidden_costs_ht": float(hid), "probable_cost_ht": float(money(base + hid)),
            "negotiable_ht": float(sav), "target_cost_ht": float(money(base + hid - sav)),
            "options_ht": s.get("options_ht") or 0.0, "quality_issues": quality_issues,
            "levers": sorted(levers[qid], key=lambda x: -x["saving_ht"]),
            "hidden": sorted(hidden[qid], key=lambda x: -x["amount_ht"]),
        })
    offers.sort(key=lambda o: o["target_cost_ht"])
    eligible = [o for o in offers if o["quality_issues"] == 0] or offers
    recommended = min(eligible, key=lambda o: o["target_cost_ht"]) if eligible else None

    # offre recomposée : meilleur prix CONFORME par poste (indicatif : plancher réaliste du lot)
    floor = Decimal("0")
    floor_complete = True
    for row in rows:
        if row.get("extra"):
            continue
        if row.get("conform_min") is not None:
            floor += D(row["conform_min"])
        elif row.get("median") or row.get("estimate"):
            floor += D(row.get("median") or row.get("estimate"))
            floor_complete = False
        else:
            floor_complete = False

    remarks.sort(key=lambda r: (SEVERITY_ORDER[r["severity"]], r["company"] or "", r["designation"] or ""))
    return {
        "remarks": remarks,
        "offers": offers,
        "recommended_quote_id": recommended["quote_id"] if recommended else None,
        "floor_ht": float(money(floor)), "floor_complete": floor_complete,
        "counts": {sev: sum(1 for r in remarks if r["severity"] == sev) for sev in SEVERITY_ORDER},
        "rules": {"low_price": LOW_PRICE, "high_price": HIGH_PRICE, "min_saving": float(MIN_SAVING), "qty_gap": QTY_GAP},
    }


def optimization_text(opt: dict) -> str:
    """Paragraphe « Optimisation économique » pour la conclusion et les rapports."""
    if not opt or not opt.get("offers"):
        return ""
    parts = ["\n### Optimisation économique à qualité constante"]
    for o in opt["offers"]:
        line = (f"- **{o['company']}** : {eur(o['total_ht'])} HT annoncés"
                + (f" + {eur(o['hidden_costs_ht'])} de coûts cachés probables (postes absents, quantités sous-estimées)" if o["hidden_costs_ht"] else "")
                + f" = **{eur(o['probable_cost_ht'])} HT de coût réel probable**")
        if o["negotiable_ht"]:
            line += f" ; {len(o['levers'])} levier(s) de négociation pour {eur(o['negotiable_ht'])} → objectif {eur(o['target_cost_ht'])} HT"
        if o["quality_issues"]:
            line += f" ; ⚠ {o['quality_issues']} écart(s) de qualité par rapport à la référence"
        parts.append(line + ".")
    rec = next((o for o in opt["offers"] if o["quote_id"] == opt.get("recommended_quote_id")), None)
    if rec:
        if rec["quality_issues"] == 0:
            parts.append(f"\nMeilleur rapport coût réel / qualité : **{rec['company']}** — objectif {eur(rec['target_cost_ht'])} HT "
                         "après intégration des coûts cachés et négociation, sans écart de qualité constaté par rapport à la référence.")
        else:
            parts.append(f"\nAucune offre n'est exempte d'écart de qualité ; la moins coûteuse en coût réel est **{rec['company']}**, "
                         "sous réserve de mise en conformité.")
        open_points = [r for r in opt["remarks"] if r["quote_id"] == rec["quote_id"] and r["severity"] == "haute"]
        if open_points:
            parts.append(f"Conditions avant attribution ({len(open_points)}) :")
            for r in open_points[:6]:
                parts.append(f"  - {(r['designation'] + ' : ') if r['designation'] else ''}{r['message']} → {r['action']}")
        for lv in rec["levers"][:5]:
            parts.append(f"  - Levier : {lv['designation'][:70]} — {lv['text']}")
    parts.append(f"\nPlancher réaliste du lot : {eur(opt['floor_ht'])} HT — somme, poste par poste, du meilleur prix CONFORME "
                 "(prix anormalement bas et prestations inférieures exclus)"
                 + ("" if opt["floor_complete"] else " ; indicatif, certains postes n'ont pas de prix conforme") + ".")
    below = [o for o in opt["offers"] if o["probable_cost_ht"] < opt["floor_ht"]]
    for o in below:
        parts.append(f"Le coût réel probable de **{o['company']}** ({eur(o['probable_cost_ht'])} HT) est inférieur à ce plancher : "
                     "ses prix les plus bas doivent être justifiés avant de conclure à une économie réelle.")
    parts.append("Les prix anormalement bas et les offres techniquement inférieures ne servent jamais de cible : "
                 "la cible de négociation est la médiane des offres conformes.")
    return "\n".join(parts)
