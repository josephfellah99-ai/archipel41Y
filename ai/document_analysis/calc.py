"""Moteur de calcul déterministe des devis.

Aucun montant n'est calculé par un modèle de langage : tous les totaux, arrondis
et taux de TVA sont contrôlés ici avec l'arithmétique décimale exacte et la
règle d'arrondi commerciale (demi-supérieur au centime).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .numbers import FRENCH_VAT_RATES, fold

CENT = Decimal("0.01")
TOL_LINE = Decimal("0.02")       # tolérance d'écart par ligne (arrondis)
TOL_TOTAL = Decimal("1.00")      # tolérance sur les totaux déclarés


def d(v) -> Decimal | None:
    if v is None or v == "":
        return None
    return v if isinstance(v, Decimal) else Decimal(str(v))


def money(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def fr(v, digits: int | None = 2) -> str:
    """Format français : 3 402,00 (espace fine insécable pour les milliers)."""
    if v is None:
        return "—"
    v = Decimal(str(v))
    if digits is None:
        txt = format(v.normalize(), "f")
        if "." in txt:
            txt = txt.rstrip("0").rstrip(".")
        ent, _, dec = txt.partition(".")
    else:
        ent, _, dec = f"{money(v) if digits == 2 else v:.{digits}f}".partition(".")
    neg = ent.startswith("-")
    ent = ent.lstrip("-")
    groups = []
    while len(ent) > 3:
        groups.insert(0, ent[-3:])
        ent = ent[:-3]
    groups.insert(0, ent)
    out = ("-" if neg else "") + "\u202f".join(groups)
    return out + ("," + dec if dec else "")


@dataclass
class LineCalc:
    id: str | None
    designation: str
    quantity: Decimal | None
    unit_price: Decimal | None
    declared_total: Decimal | None
    vat_rate: Decimal | None
    status: str
    computed_total: Decimal | None = None


def compute_line(qty, pu, declared) -> tuple[Decimal | None, list[str]]:
    """Retourne (montant HT retenu, anomalies)."""
    qty, pu, declared = d(qty), d(pu), d(declared)
    issues = []
    if qty is not None and pu is not None:
        computed = money(qty * pu)
        if declared is not None and abs(computed - declared) > TOL_LINE:
            issues.append(
                f"Écart de calcul : {fr(qty, None)} × {fr(pu)} = {fr(computed)} € HT, montant indiqué {fr(declared)} € HT "
                f"(écart {fr(declared - computed)} €)."
            )
        return computed, issues
    if declared is not None:
        return money(declared), issues
    return None, issues


def _fmt(v: Decimal | None) -> float | None:
    return float(v) if v is not None else None


def compute_quote(lines: list[dict], *, default_vat: float | None = None, declared_ht=None,
                  declared_tva=None, declared_ttc=None) -> tuple[dict, list[dict]]:
    """Calcule les totaux d'un devis et détecte les anomalies.

    `lines` : dicts avec id, designation, quantity, unit_price, total_ht, vat_rate, status.
    Retourne (computed, anomalies)."""
    anomalies: list[dict] = []
    default_rate = d(default_vat) if default_vat is not None else None
    base_by_rate: dict[Decimal, Decimal] = defaultdict(lambda: Decimal("0"))
    total_ht = Decimal("0")
    options_ht = Decimal("0")
    variants_ht = Decimal("0")
    to_check_ht = Decimal("0")
    counts = defaultdict(int)
    missing_rate = False
    seen: dict[tuple, str] = {}

    for ln in lines:
        status = ln.get("status") or "inclus"
        counts[status] += 1
        amount, issues = compute_line(ln.get("quantity"), ln.get("unit_price"), ln.get("total_ht"))
        for msg in issues:
            anomalies.append({"code": "calcul_ligne", "severity": "haute", "message": msg, "line_id": ln.get("id"),
                              "designation": ln.get("designation")})
        if amount is not None and amount < 0 and status == "inclus":
            anomalies.append({"code": "montant_negatif", "severity": "moyenne", "line_id": ln.get("id"),
                              "message": f"Montant négatif (remise ou moins-value ?) : {fr(amount)} €.",
                              "designation": ln.get("designation")})
        rate = d(ln.get("vat_rate"))
        if rate is None:
            rate = default_rate
        if rate is not None and rate not in FRENCH_VAT_RATES:
            anomalies.append({"code": "taux_tva", "severity": "haute", "line_id": ln.get("id"),
                              "message": f"Taux de TVA inhabituel en France : {fr(rate, None)} %.",
                              "designation": ln.get("designation")})
        # Doublons probables
        key = (fold(ln.get("designation") or "").strip(), str(d(ln.get("quantity"))), str(d(ln.get("unit_price"))))
        if key[0] and amount:
            if key in seen:
                anomalies.append({"code": "doublon", "severity": "moyenne", "line_id": ln.get("id"),
                                  "message": "Ligne identique à une ligne précédente (doublon probable).",
                                  "designation": ln.get("designation")})
            else:
                seen[key] = ln.get("id")
        if amount is None:
            if status == "inclus":
                counts["sans_montant"] += 1
            continue
        if status == "inclus":
            total_ht += amount
            if rate is None:
                missing_rate = True
                rate = Decimal("20")
            base_by_rate[rate] += amount
        elif status == "optionnel":
            options_ht += amount
        elif status == "variante":
            variants_ht += amount
        elif status == "a_verifier":
            to_check_ht += amount

    total_ht = money(total_ht)
    by_rate = []
    total_tva = Decimal("0")
    for rate in sorted(base_by_rate, reverse=True):
        base = money(base_by_rate[rate])
        tva = money(base * rate / 100)
        total_tva += tva
        by_rate.append({"rate": float(rate), "base": float(base), "tva": float(tva)})
    total_tva = money(total_tva)
    total_ttc = money(total_ht + total_tva)

    if missing_rate:
        anomalies.append({"code": "tva_absente", "severity": "basse",
                          "message": "Taux de TVA non indiqué : 20 % appliqué par défaut pour le calcul."})
    dht, dtva, dttc = d(declared_ht), d(declared_tva), d(declared_ttc)
    if dht is not None and abs(dht - total_ht) > TOL_TOTAL:
        anomalies.append({"code": "total_ht", "severity": "haute",
                          "message": f"Total HT déclaré {fr(dht)} € ≠ somme des lignes incluses {fr(total_ht)} € "
                                     f"(écart {fr(dht - total_ht)} €)."})
    if dtva is not None and abs(dtva - total_tva) > TOL_TOTAL:
        anomalies.append({"code": "total_tva", "severity": "haute",
                          "message": f"TVA déclarée {fr(dtva)} € ≠ TVA recalculée {fr(total_tva)} €."})
    if dttc is not None and abs(dttc - total_ttc) > TOL_TOTAL:
        anomalies.append({"code": "total_ttc", "severity": "haute",
                          "message": f"Total TTC déclaré {fr(dttc)} € ≠ TTC recalculé {fr(total_ttc)} €."})
    if dht is not None and dtva is not None and dttc is not None and abs(money(dht + dtva) - dttc) > CENT:
        anomalies.append({"code": "coherence_declaree", "severity": "haute",
                          "message": f"Incohérence interne au devis : {fr(dht)} + {fr(dtva)} ≠ {fr(dttc)} €."})
    if counts.get("a_verifier"):
        anomalies.append({"code": "lignes_a_verifier", "severity": "moyenne",
                          "message": f"{counts['a_verifier']} ligne(s) au statut « à vérifier » non comptée(s) dans le total."})
    if counts.get("sans_montant"):
        anomalies.append({"code": "sans_montant", "severity": "basse",
                          "message": f"{counts['sans_montant']} ligne(s) incluse(s) sans montant (compris / pour mémoire)."})

    computed = {
        "total_ht": _fmt(total_ht),
        "total_tva": _fmt(total_tva),
        "total_ttc": _fmt(total_ttc),
        "by_rate": by_rate,
        "options_ht": _fmt(money(options_ht)),
        "variants_ht": _fmt(money(variants_ht)),
        "to_check_ht": _fmt(money(to_check_ht)),
        "counts": dict(counts),
        "lines_count": len(lines),
        "declared_match": all(a["code"] not in ("total_ht", "total_tva", "total_ttc") for a in anomalies),
    }
    return computed, anomalies


def ttc_from_ht(ht, rate) -> float:
    ht, rate = d(ht) or Decimal("0"), d(rate) or Decimal("0")
    return float(money(ht + money(ht * rate / 100)))
