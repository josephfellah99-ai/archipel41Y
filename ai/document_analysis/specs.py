"""Analyse des pièces écrites : DPGF, CCTP et règlement de PLU."""
from __future__ import annotations

import re

from .extract import ExtractResult
from .numbers import fold, normalize_unit, parse_number
from .quote_parser import _header_map, is_total_label

# --------------------------------------------------------------------------- DPGF


def parse_dpgf(ex: ExtractResult) -> list[dict]:
    """Lignes d'une DPGF (tableaux Excel/CSV/PDF) : code, désignation, unité, quantité, PU estimé."""
    items: list[dict] = []
    for page_no, rows in ex.tables:
        mapping: dict[str, int] = {}
        section = None
        for row in rows:
            if not mapping:
                mapping = _header_map(row)
                continue
            get = lambda k: row[mapping[k]] if k in mapping and mapping[k] < len(row) else ""  # noqa: E731
            des = get("designation").strip()
            if not des or is_total_label(des):
                continue
            qty = parse_number(get("quantity"))
            unit = get("unit").strip()
            if qty is None and not unit:
                section = des[:200]
                continue
            ref = None
            m = re.search(r"(?:cctp|art\.?|article)\s*([\d.]+)", " ".join(row), re.I)
            if m:
                ref = m.group(1).strip(".")
            pu = parse_number(get("unit_price"))
            items.append({
                "position": len(items), "code": (get("code") or "").strip() or None, "section": section,
                "designation": des, "unit": normalize_unit(unit) if unit else None,
                "quantity": float(qty) if qty is not None else None,
                "estimated_unit_price": float(pu) if pu is not None else None, "cctp_ref": ref,
            })
    return items


# --------------------------------------------------------------------------- CCTP
ARTICLE_RX = re.compile(
    r"^\s*(?:article\s+)?(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s*[-–:.]?\s+([A-ZÉÈÀÂÎÔÛÇ][^\n]{3,120})$", re.M | re.I
)
TECH_RX = [
    r"\bC\d{2}/\d{2}\b", r"\bX[CDFSA]\d\b", r"\bDTU\s?\d{1,2}(?:\.\d)?\b", r"\bNF\s?(?:EN|P|DTU)?\s?[\d-]{2,}(?:-\d+)?\b",
    r"\bR\s?=\s?\d+(?:[.,]\d+)?\b", r"\b[ée]p(?:aisseur|\.)\s*\d+\s*(?:mm|cm)\b", r"\b\d+\s*mm\b",
    r"\bHA\s?\d+\b", r"\bclasse\s+[A-Z0-9]+\b", r"\bRE\s?2020\b", r"\bPV\s+d'essai\b", r"\bavis technique\b",
]


def parse_cctp(ex: ExtractResult) -> list[dict]:
    reqs: list[dict] = []
    for page in ex.pages:
        matches = list(ARTICLE_RX.finditer(page.text))
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(page.text)
            body = page.text[start:end].strip()
            title = m.group(2).strip()
            if len(body) < 15 and not re.search(r"\d", title):
                continue
            kws: list[str] = []
            for rx in TECH_RX:
                for k in re.findall(rx, body, re.I):
                    k = k.strip()
                    if k and k not in kws:
                        kws.append(k)
            # Mots porteurs du titre (désignation de l'ouvrage)
            for w in re.findall(r"[A-Za-zÀ-ÿ]{5,}", title):
                wf = fold(w)
                if wf not in ("article", "generalites", "prescriptions", "ouvrages", "travaux") and w not in kws:
                    kws.append(w.lower())
            reqs.append({"article": m.group(1), "title": title[:300], "text": body[:4000], "keywords": kws[:12],
                         "page": page.number})
    return reqs


# --------------------------------------------------------------------------- PLU
PLU_THEMES = {
    "destination": ("Destinations et occupations du sol", [r"occupations? (et utilisations? )?du sol (interdites|admises|soumises)",
                                                         r"destinations?", r"usages? (et affectations? )?des sols", r"interdi"]),
    "emprise": ("Emprise au sol", [r"emprise au sol"]),
    "hauteur": ("Hauteur des constructions", [r"hauteur"]),
    "implantation_voies": ("Implantation par rapport aux voies", [r"implantation.{0,60}(voies|emprises publiques|alignement)"]),
    "implantation_limites": ("Implantation par rapport aux limites séparatives", [r"limites? s[ée]paratives?"]),
    "implantation_meme_terrain": ("Implantation sur une même propriété", [r"(les )?unes? par rapport aux autres|m[eê]me propri[ée]t[ée]"]),
    "aspect": ("Aspect extérieur et prescriptions architecturales", [r"aspect ext[ée]rieur", r"qualit[ée] urbaine", r"toitures?", r"cl[ôo]tures?"]),
    "stationnement": ("Stationnement", [r"stationnement"]),
    "espaces_verts": ("Espaces libres et espaces verts", [r"\bespaces? (libres|verts)", r"\bplantations?\b", r"\bpleine terre", r"coefficient de biotope"]),
    "reseaux": ("Desserte par les réseaux", [r"r[ée]seaux", r"assainissement", r"eaux pluviales"]),
}
VALUE_RX = re.compile(
    r"(\d{1,3}(?:[.,]\d{1,2})?\s*(?:%|m(?:è|e)tres?\b|m\b|m²|places?)|R\s?\+\s?\d(?:\s?\+\s?(?:C|A|attique|combles))?)", re.I
)


def find_zone_section(text: str, zone: str) -> tuple[int, int] | None:
    """Localise le chapitre du règlement consacré à une zone (ex. « UB »)."""
    if not zone:
        return None
    z = re.escape(zone.strip())
    rx = re.compile(rf"^[^\n]{{0,40}}\b(?:zone|secteur|chapitre[^\n]{{0,30}})\s*{z}\b[^\n]*$|^\s*{z}\s*[-–:]\s+[^\n]+$", re.I | re.M)
    m = rx.search(text)
    if not m:
        return None
    start = m.start()
    nxt = re.compile(r"^[^\n]{0,40}\b(?:zone|chapitre[^\n]{0,30})\s*(?!%s\b)[A-Z]{1,3}[a-z0-9]{0,3}\b[^\n]*$" % z, re.M | re.I)
    m2 = nxt.search(text, m.end() + 200)
    return start, (m2.start() if m2 else len(text))


def analyse_plu(ex: ExtractResult, zone: str | None) -> dict:
    """Recherche, dans le règlement fourni, les dispositions applicables à la zone.

    Seuls des extraits réellement présents dans le document sont restitués, avec page.
    Les thèmes non trouvés sont signalés comme tels — aucune règle n'est inventée."""
    full = ""
    offsets = []
    for p in ex.pages:
        offsets.append((len(full), p.number))
        full += p.text + "\n"

    def page_at(pos: int) -> int | None:
        pg = None
        for off, num in offsets:
            if off <= pos:
                pg = num
        return pg

    span = find_zone_section(full, zone) if zone else None
    scope_note = None
    if span is None:
        span = (0, len(full))
        scope_note = (f"Chapitre de la zone « {zone} » non localisé : la recherche porte sur l'ensemble du document."
                      if zone else "Zone non précisée : la recherche porte sur l'ensemble du document.")
    text = full[span[0]:span[1]]
    themes = {}
    art_rx = re.compile(r"^\s*(?:article|art\.?)\s*([A-Z]{0,3}\s?\d{1,2}[a-z]?|[A-Z]{1,3}\s?\d(?:\.\d){0,2})\b[^\n]*$", re.I | re.M)
    articles = list(art_rx.finditer(text))
    for key, (label, patterns) in PLU_THEMES.items():
        found = None
        for i, a in enumerate(articles):
            line = a.group(0)
            if any(re.search(p, fold(line)) for p in patterns):
                end = articles[i + 1].start() if i + 1 < len(articles) else min(len(text), a.end() + 3000)
                excerpt = text[a.start():end].strip()
                found = {"article": line.strip()[:200], "excerpt": excerpt[:2500], "page": page_at(span[0] + a.start()),
                         "values": list(dict.fromkeys(v.strip() for v in VALUE_RX.findall(excerpt)))[:10]}
                break
        if not found:
            for p in patterns:
                m = re.search(p, fold(text))
                if m:
                    s = max(0, m.start() - 200)
                    excerpt = text[s:m.end() + 800].strip()
                    found = {"article": None, "excerpt": excerpt, "page": page_at(span[0] + m.start()),
                             "values": list(dict.fromkeys(v.strip() for v in VALUE_RX.findall(excerpt)))[:10],
                             "note": "Mention trouvée hors d'un article identifié : vérifier le contexte."}
                    break
        themes[key] = {"label": label, "found": bool(found), **(found or {"excerpt": None,
                       "message": "Non trouvé dans le document fourni — à vérifier dans le règlement complet."})}
    return {"zone": zone, "scope_note": scope_note, "themes": themes, "document": ex.filename,
            "page_count": len(ex.pages)}
