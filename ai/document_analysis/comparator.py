"""Comparateur d'offres déterministe.

Statuts d'une cellule (offre × prestation) :
- inclus         : poste chiffré (ou mentionné « compris ») dans l'offre ;
- non_inclus     : poste EXPRESSÉMENT exclu par l'entreprise (ligne « non compris »,
                   ou correspondance avec la liste des exclusions du devis) ;
- non_renseigne  : poste absent de l'offre — sans mention d'exclusion ;
- optionnel      : poste proposé en option ;
- variante       : poste proposé en variante ;
- non_comparable : unité incompatible avec la référence (ex. m² contre ml) ;
- a_verifier     : correspondance incertaine ou ligne signalée à vérifier.
"""
from __future__ import annotations

import re
import statistics
from difflib import SequenceMatcher

from .numbers import fold, normalize_unit

STOPWORDS = set(
    "de du des la le les l d un une et en a au aux pour par sur sous avec y compris compris yc dans "
    "ou the of fourniture pose mise oeuvre f mo fourniture-et-pose type selon ens ensemble".split()
)
GENERIC_CCTP = set("conforme conformement selon dtu nf en norme mise oeuvre entrepreneur assure travaux ouvrage cm mm "
                   "avec sans suivant prescription article lot classe exposition".split())
MATCH_THRESHOLD = 0.52
UNSURE_THRESHOLD = 0.40
UNUSUAL_DEVIATION = 0.30
STRONG_DEVIATION = 0.50

STATUS_LABELS = {
    "inclus": "Inclus",
    "non_inclus": "Non inclus (exclu)",
    "non_renseigne": "Non renseigné",
    "optionnel": "Optionnel",
    "variante": "Variante",
    "non_comparable": "Non comparable",
    "a_verifier": "À vérifier",
}


ABBREVIATIONS = {
    "ba": "beton arme", "bc": "beton", "ep": "epaisseur", "ht": "hauteur", "fdc": "fin de chantier",
    "pp": "pleine", "mo": "", "maconn": "maconnerie", "chainage": "chainage", "elec": "electricite",
    "plomb": "plomberie", "menuis": "menuiserie", "alu": "aluminium", "pv": "", "vr": "volet roulant",
}


def tokens(text: str) -> set[str]:
    t = fold(text)
    t = re.sub(r"[^a-z0-9/ ]+", " ", t)
    words = []
    for w in t.split():
        words.extend(ABBREVIATIONS.get(w, w).split())
    out = set()
    for w in words:
        if w in STOPWORDS or len(w) < 2:
            continue
        if w.isalpha() and len(w) > 4 and w.endswith(("s", "x")):
            w = w[:-1]
        out.add(w)
    return out


def similarity(a: str, b: str, code_a: str | None = None, code_b: str | None = None) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    jacc = len(ta & tb) / len(ta | tb)
    contain = len(ta & tb) / min(len(ta), len(tb))
    seq = SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    score = 0.35 * jacc + 0.35 * contain + 0.30 * seq
    if code_a and code_b and code_a.strip(". ") == code_b.strip(". "):
        score = min(1.0, score + 0.25)
    return round(score, 3)


def _amount(line: dict) -> float | None:
    if line.get("total_ht") is not None:
        return float(line["total_ht"])
    if line.get("quantity") is not None and line.get("unit_price") is not None:
        return round(float(line["quantity"]) * float(line["unit_price"]), 2)
    return None


def _best_match(ref: dict, lines: list[dict], used: set[str]) -> tuple[dict | None, float]:
    if ref.get("_dpgf_id"):
        for ln in lines:
            if ln.get("dpgf_item_id") == ref["_dpgf_id"] and ln["id"] not in used:
                return ln, 1.0  # correspondance validée manuellement
    best, best_score = None, 0.0
    for ln in lines:
        if ln["id"] in used:
            continue
        s = similarity(ref["designation"], ln["designation"], ref.get("code"), ln.get("code"))
        if s > best_score:
            best, best_score = ln, s
    return best, best_score


def _exclusion_hit(designation: str, exclusions: list[str]) -> str | None:
    for ex in exclusions or []:
        if similarity(designation, ex) >= 0.45 or (tokens(designation) and tokens(designation) <= tokens(ex)):
            return ex
    return None


def compare(quotes: list[dict], reference: list[dict] | None = None, cctp: list[dict] | None = None) -> dict:
    """quotes : [{id, company, total(computed dict), delay_days, exclusions, reserves, anomalies, lines:[...]}]
    reference : lignes DPGF [{id, code, designation, unit, quantity, estimated_unit_price}] (optionnel)."""
    reference = reference or []
    rows: list[dict] = []
    used: dict[str, set[str]] = {q["id"]: set() for q in quotes}

    # 1) lignes de référence : DPGF si disponible, sinon l'offre la plus détaillée sert de pivot
    if reference:
        refs = [{"key": f"dpgf:{r['id']}", "_dpgf_id": r["id"], "code": r.get("code"), "designation": r["designation"],
                 "unit": r.get("unit"), "quantity": r.get("quantity"), "estimated_unit_price": r.get("estimated_unit_price"),
                 "section": r.get("section"), "origin": "DPGF"} for r in reference]
    else:
        pivot = max(quotes, key=lambda q: len(q["lines"]), default=None)
        refs = []
        if pivot:
            for ln in pivot["lines"]:
                refs.append({"key": f"line:{ln['id']}", "code": ln.get("code"), "designation": ln["designation"],
                             "unit": ln.get("unit"), "quantity": ln.get("quantity"), "section": ln.get("section"),
                             "origin": pivot["company"], "_pivot_line": ln["id"], "_pivot_quote": pivot["id"]})

    def build_row(ref: dict) -> dict:
        row = {"key": ref["key"], "code": ref.get("code"), "designation": ref["designation"], "unit": ref.get("unit"),
               "quantity": ref.get("quantity"), "section": ref.get("section"), "origin": ref.get("origin"),
               "estimated_unit_price": ref.get("estimated_unit_price"), "cells": {}}
        for q in quotes:
            if ref.get("_pivot_quote") == q["id"]:
                ln = next(l for l in q["lines"] if l["id"] == ref["_pivot_line"])
                score = 1.0
            else:
                ln, score = _best_match(ref, q["lines"], used[q["id"]])
            cell = {"status": "non_renseigne", "score": round(score, 2), "line_id": None, "amount": None,
                    "unit_price": None, "quantity": None, "unit": None, "designation": None, "note": None}
            if ln is not None and score >= UNSURE_THRESHOLD:
                used[q["id"]].add(ln["id"])
                amount = _amount(ln)
                cell.update(line_id=ln["id"], amount=amount, unit_price=ln.get("unit_price"), quantity=ln.get("quantity"),
                            unit=ln.get("unit"), designation=ln["designation"])
                st = ln.get("status") or "inclus"
                cell["status"] = {"exclu": "non_inclus"}.get(st, st)
                ref_u, ln_u = normalize_unit(ref.get("unit")), normalize_unit(ln.get("unit"))
                if cell["status"] == "inclus" and ref_u and ln_u and ref_u != ln_u and "ft" not in (ref_u, ln_u) and "ens" not in (ref_u, ln_u):
                    cell["status"] = "non_comparable"
                    cell["note"] = f"Unité de l'offre ({ln.get('unit')}) différente de la référence ({ref.get('unit')})."
                elif score < MATCH_THRESHOLD and cell["status"] == "inclus":
                    cell["status"] = "a_verifier"
                    cell["note"] = "Correspondance incertaine entre les libellés : à confirmer."
                elif cell["status"] == "inclus" and amount in (None, 0):
                    cell["note"] = "Mentionné comme compris, sans montant détaillé."
                if cell["status"] == "inclus" and ref.get("quantity") and ln.get("quantity"):
                    rq, lq = float(ref["quantity"]), float(ln["quantity"])
                    if rq and abs(lq - rq) / rq > 0.10:
                        cell["note"] = f"Quantité différente de la référence : {lq:g} au lieu de {rq:g}."
                        cell["quantity_gap"] = True
            else:
                hit = _exclusion_hit(ref["designation"], q.get("exclusions", []))
                if hit:
                    cell["status"] = "non_inclus"
                    cell["note"] = f"Exclu par l'entreprise : « {hit} »."
                else:
                    cell["note"] = "Aucune ligne correspondante dans l'offre (absence ≠ exclusion : à faire préciser)."
            row["cells"][q["id"]] = cell
        return row

    for ref in refs:
        rows.append(build_row(ref))

    # 2) lignes des offres non rattachées → prestations supplémentaires, regroupées entre offres
    extra_rows = []
    for q in quotes:
        for ln in q["lines"]:
            if ln["id"] in used[q["id"]]:
                continue
            ref = {"key": f"extra:{ln['id']}", "code": ln.get("code"), "designation": ln["designation"], "unit": ln.get("unit"),
                   "quantity": ln.get("quantity"), "section": ln.get("section"), "origin": q["company"],
                   "_pivot_line": ln["id"], "_pivot_quote": q["id"]}
            row = build_row(ref)
            row["extra"] = True
            extra_rows.append(row)
    rows.extend(extra_rows)

    # 3) analyse des prix par ligne
    for row in rows:
        vals = [c["amount"] for c in row["cells"].values() if c["status"] == "inclus" and c["amount"]]
        row["median"] = round(statistics.median(vals), 2) if vals else None
        row["min"] = min(vals) if vals else None
        row["max"] = max(vals) if vals else None
        est = None
        if row.get("estimated_unit_price") and row.get("quantity"):
            est = round(float(row["estimated_unit_price"]) * float(row["quantity"]), 2)
        row["estimate"] = est
        basis = row["median"] if len(vals) >= 2 else est
        for c in row["cells"].values():
            c["deviation"] = None
            if c["status"] == "inclus" and c["amount"] and basis:
                dev = (c["amount"] - basis) / basis
                c["deviation"] = round(dev, 3)
                if abs(dev) >= STRONG_DEVIATION:
                    c["flag"] = "ecart_fort"
                elif abs(dev) >= UNUSUAL_DEVIATION:
                    c["flag"] = "ecart"
        row["is_min"] = None
        if len(vals) >= 2:
            for qid, c in row["cells"].items():
                if c["status"] == "inclus" and c["amount"] == row["min"]:
                    row["is_min"] = qid

    # 4) synthèse par offre
    summaries = []
    for q in quotes:
        counts = {k: 0 for k in STATUS_LABELS}
        unusual = []
        missing_value = 0.0
        for row in rows:
            c = row["cells"][q["id"]]
            if row.get("extra") and c["status"] in ("non_renseigne", "non_inclus"):
                continue  # prestation proposée par une autre entreprise seulement
            counts[c["status"]] += 1
            if c.get("flag"):
                unusual.append({"designation": row["designation"], "deviation": c["deviation"], "amount": c["amount"]})
            if c["status"] in ("non_renseigne", "non_inclus") and not row.get("extra"):
                if row["median"]:
                    missing_value += row["median"]
                elif row.get("estimate"):
                    missing_value += row["estimate"]
        total_ht = (q.get("computed") or {}).get("total_ht") or 0.0
        ref_rows = [r for r in rows if not r.get("extra")]
        completeness = (counts["inclus"] - sum(1 for r in rows if r.get("extra") and r["cells"][q["id"]]["status"] == "inclus")) / len(ref_rows) if ref_rows else 1.0
        summaries.append({
            "quote_id": q["id"], "company": q["company"], "total_ht": total_ht,
            "total_ttc": (q.get("computed") or {}).get("total_ttc"),
            "options_ht": (q.get("computed") or {}).get("options_ht"),
            "variants_ht": (q.get("computed") or {}).get("variants_ht"),
            "adjusted_ht": round(total_ht + missing_value, 2),
            "missing_value": round(missing_value, 2),
            "counts": counts, "completeness": round(max(0.0, completeness), 3),
            "unusual": unusual, "delay_days": q.get("delay_days"), "delay_text": q.get("delay_text"),
            "anomalies": len([a for a in q.get("anomalies", []) if a.get("severity") == "haute"]),
            "line_errors": len([a for a in q.get("anomalies", []) if a.get("code") in ("calcul_ligne", "taux_tva", "doublon")]),
            "totals_mismatch": any(a.get("code") in ("total_ht", "total_tva", "total_ttc", "coherence_declaree") for a in q.get("anomalies", [])),
            "anomaly_details": q.get("anomalies", []),
            "exclusions": q.get("exclusions", []), "reserves": q.get("reserves", []),
            "validity_days": q.get("validity_days"),
        })

    # 5) conformité CCTP : ouvrage cité + précisions techniques (classes, épaisseurs…)
    cctp_checks = []
    for req in cctp or []:
        title_kw = [k for k in (req.get("keywords") or []) if not re.search(r"\d", k)]
        specs = [k for k in (req.get("keywords") or []) if re.search(r"\d", k) and not re.match(r"(?i)(dtu|nf)", k)]
        refs = [k for k in (req.get("keywords") or []) if re.match(r"(?i)(dtu|nf)", k)]
        if not title_kw and not specs:
            continue
        per_quote = {}
        for q in quotes:
            blob_tokens = set().union(*[tokens(ln["designation"]) for ln in q["lines"]]) if q["lines"] else set()
            blob = fold(" ".join(ln["designation"] for ln in q["lines"]))
            req_tokens = (tokens(req.get("title") or "") | tokens((req.get("text") or "")[:220])) - GENERIC_CCTP
            ouvrage = len(req_tokens & blob_tokens) >= 2 or any(tokens(k) & blob_tokens for k in title_kw)
            found_specs = [k for k in specs if fold(k) in blob]
            missing_specs = [k for k in specs if k not in found_specs]
            if not ouvrage:
                status, msg = "absent", "Ouvrage non identifié dans l'offre."
            elif missing_specs:
                status, msg = "a_verifier", "Précisions techniques non citées : " + ", ".join(missing_specs)
            else:
                status, msg = "mentionne", "Ouvrage et caractéristiques cités."
            per_quote[q["id"]] = {"status": status, "found": found_specs, "missing": missing_specs, "message": msg}
        cctp_checks.append({"article": req.get("article"), "title": req.get("title"), "keywords": title_kw,
                            "specs": specs, "references": refs, "quotes": per_quote})

    ranking = _rank(summaries)
    return {
        "rows": rows,
        "summaries": summaries,
        "ranking": ranking,
        "cctp": cctp_checks,
        "has_reference": bool(reference),
        "status_labels": STATUS_LABELS,
        "thresholds": {"match": MATCH_THRESHOLD, "unsure": UNSURE_THRESHOLD, "unusual": UNUSUAL_DEVIATION},
    }


def _rank(summaries: list[dict]) -> list[dict]:
    """Classement multicritère transparent (prix 50 %, complétude 25 %, risques 15 %, délai 10 %)."""
    if not summaries:
        return []
    prices = [s["adjusted_ht"] for s in summaries if s["adjusted_ht"]]
    delays = [s["delay_days"] for s in summaries if s["delay_days"]]
    pmin = min(prices) if prices else None
    dmin = min(delays) if delays else None
    out = []
    for s in summaries:
        price_score = (pmin / s["adjusted_ht"]) if pmin and s["adjusted_ht"] else 0
        comp_score = s["completeness"]
        low_prices = [u for u in s["unusual"] if (u["deviation"] or 0) < 0]
        risk_score = max(0.0, 1 - 0.15 * s["line_errors"] - 0.10 * s["totals_mismatch"] - 0.10 * len(s["reserves"])
                         - 0.10 * len(low_prices) - 0.05 * (len(s["unusual"]) - len(low_prices)))
        delay_score = (dmin / s["delay_days"]) if dmin and s["delay_days"] else 0.5
        total = 0.5 * price_score + 0.25 * comp_score + 0.15 * risk_score + 0.10 * delay_score
        out.append({"quote_id": s["quote_id"], "company": s["company"], "score": round(total * 100, 1),
                    "details": {"prix": round(price_score * 100), "completude": round(comp_score * 100),
                                "risques": round(risk_score * 100), "delai": round(delay_score * 100)}})
    out.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out


def _eur(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:,.2f} €".replace(",", " ").replace(".", ",")


def rule_based_conclusion(result: dict, lot_label: str | None = None) -> str:
    """Conclusion argumentée produite uniquement à partir des faits calculés."""
    s = {x["quote_id"]: x for x in result["summaries"]}
    rk = result["ranking"]
    if not rk:
        return "Aucune offre à comparer."
    parts = []
    title = f"Analyse comparative{(' – ' + lot_label) if lot_label else ''}"
    parts.append(f"## {title}\n")
    parts.append(f"{len(rk)} offre(s) comparée(s)" + (" sur la base de la DPGF du projet." if result["has_reference"]
                                                      else " (sans DPGF : l'offre la plus détaillée sert de référence)."))
    best = s[rk[0]["quote_id"]]
    cheapest = min(result["summaries"], key=lambda x: x["total_ht"] or 1e18)
    parts.append("\n### Constats chiffrés")
    for r in rk:
        x = s[r["quote_id"]]
        c = x["counts"]
        line = (f"- **{x['company']}** : {_eur(x['total_ht'])} HT déclaré-recalculé ; "
                f"{c['inclus']} poste(s) inclus, {c['non_renseigne']} non renseigné(s), {c['non_inclus']} exclu(s)")
        if c["optionnel"] or c["variante"]:
            line += f", {c['optionnel']} option(s), {c['variante']} variante(s)"
        if c["a_verifier"] or c["non_comparable"]:
            line += f", {c['a_verifier'] + c['non_comparable']} à vérifier/non comparable(s)"
        line += f". Montant à périmètre comparable estimé : {_eur(x['adjusted_ht'])} HT"
        if x["delay_days"]:
            line += f" ; délai annoncé ≈ {x['delay_days']} jours"
        line += f". Score global : {r['score']}/100."
        parts.append(line)
    parts.append("\n### Points d'attention")
    attention = False
    for x in result["summaries"]:
        if x["anomalies"]:
            attention = True
            parts.append(f"- {x['company']} : {x['anomalies']} anomalie(s) de calcul ou de totaux à faire corriger par l'entreprise.")
        if x["unusual"]:
            attention = True
            top = sorted(x["unusual"], key=lambda u: -abs(u["deviation"] or 0))[:3]
            det = "; ".join(f"{u['designation'][:60]} ({u['deviation']*100:+.0f} % vs médiane)" for u in top)
            parts.append(f"- {x['company']} : écarts de prix inhabituels — {det}.")
        if x["counts"]["non_renseigne"]:
            attention = True
            parts.append(f"- {x['company']} : {x['counts']['non_renseigne']} poste(s) non renseigné(s) — "
                         f"absence à faire confirmer (inclus sans plus-value, oubli ou exclusion ?).")
        if x["reserves"]:
            attention = True
            parts.append(f"- {x['company']} : réserves formulées — « {x['reserves'][0][:120]} »" + (" …" if len(x["reserves"]) > 1 else ""))
    for chk in result.get("cctp", []):
        for qid, v in chk["quotes"].items():
            if v["status"] in ("a_verifier", "absent"):
                attention = True
                parts.append(f"- CCTP art. {chk['article']} ({chk['title'][:50]}) – {s[qid]['company']} : {v['message']}")
    if not attention:
        parts.append("- Aucun point bloquant détecté par le moteur de règles.")
    parts.append("\n### Conclusion")
    if best["quote_id"] == cheapest["quote_id"]:
        parts.append(f"L'offre de **{best['company']}** apparaît la mieux placée : elle est la moins-disante "
                     f"({_eur(best['total_ht'])} HT) et obtient le meilleur score multicritère.")
    else:
        parts.append(f"L'offre de **{best['company']}** obtient le meilleur score multicritère ({rk[0]['score']}/100). "
                     f"L'offre de **{cheapest['company']}** est la moins-disante en montant brut ({_eur(cheapest['total_ht'])} HT) "
                     f"mais son périmètre est moins complet ou présente davantage de risques.")
    caveats = []
    if best["counts"]["non_renseigne"] or best["counts"]["non_inclus"]:
        caveats.append("son périmètre doit être complété (postes non renseignés ou exclus valorisés à "
                       f"{_eur(best['missing_value'])} HT dans le montant à périmètre comparable)")
    low = [u for u in best["unusual"] if (u["deviation"] or 0) < 0]
    if low:
        caveats.append(f"{len(low)} prix anormalement bas doivent être justifiés (risque d'offre sous-évaluée)")
    if best["reserves"]:
        caveats.append("ses réserves doivent être levées")
    if caveats:
        parts.append("Toutefois, " + " ; ".join(caveats) + ".")
    parts.append("\nRecommandations : faire lever les points d'attention ci-dessus par écrit avant attribution, "
                 "demander la confirmation des postes non renseignés et la correction des anomalies de calcul. "
                 "Cette conclusion est générée par le moteur de règles d'Archipel41 à partir des données validées ; "
                 "elle constitue une aide à la décision et ne remplace pas l'analyse de l'architecte.")
    return "\n".join(parts)
