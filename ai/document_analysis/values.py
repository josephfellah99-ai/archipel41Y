"""Caractéristiques techniques lues dans les désignations.

Une désignation contient souvent des nombres qui ne sont NI des quantités NI des
montants : épaisseur, classe de béton, résistance thermique, coefficient Uw,
diamètre, degré coupe-feu, affaiblissement acoustique, dosage… Ce module les
reconnaît, les typé et les normalise pour pouvoir comparer la QUALITÉ des
offres, et non seulement leur prix.

Chaque valeur porte :
- kind     : nature de la caractéristique (epaisseur, classe_beton, r_thermique…) ;
- value    : valeur normalisée (mm, MPa, m².K/W, W/m².K, min, dB, kg/m³) ;
- unit     : unité normalisée ;
- text     : extrait exact du libellé (traçabilité) ;
- better   : sens de la qualité — "higher" (plus = mieux), "lower" (moins = mieux)
             ou "equal" (doit être identique : diamètre, dimensions).

Aucune valeur n'est déduite ni inventée : seul ce qui est écrit est lu.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .numbers import fold, parse_number

LABELS = {
    "epaisseur": "Épaisseur",
    "classe_beton": "Classe de béton",
    "r_thermique": "Résistance thermique R",
    "uw": "Coefficient Uw",
    "ug": "Coefficient Ug",
    "up": "Coefficient Up",
    "lambda": "Conductivité λ",
    "diametre": "Diamètre",
    "coupe_feu": "Résistance au feu",
    "acoustique": "Isolement acoustique",
    "dosage": "Dosage",
    "dimensions": "Dimensions",
    "classe_upec": "Classement UPEC",
}


@dataclass
class TechValue:
    kind: str
    value: float | str
    unit: str
    text: str
    better: str
    shown: str | None = None

    @property
    def label(self) -> str:
        return LABELS.get(self.kind, self.kind)

    def display(self) -> str:
        if self.shown:
            return self.shown
        if isinstance(self.value, str):
            return self.value
        v = f"{self.value:g}".replace(".", ",")
        return f"{v} {self.unit}".strip()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["label"] = self.label
        d["display"] = self.display()
        return d


N = r"(\d+(?:[.,]\d+)?)"
_RULES: list[tuple[str, re.Pattern, str]] = [
    # épaisseur : « ép. 20 cm », « épaisseur 200 mm », « e=18cm »
    ("epaisseur", re.compile(rf"\b(?:ep(?:aisseur)?\.?|e\s*=)\s*{N}\s*(mm|cm|m)\b"), "higher"),
    ("classe_beton", re.compile(r"\bc\s?(\d{2,3})\s?/\s?(\d{2,3})\b"), "higher"),
    ("r_thermique", re.compile(rf"\br\s*(?:=|:)?\s*{N}(?:\s*m2\.?k/w|\s*m²\.?k/w)?\b(?!\s*(?:mm|cm|m\b|/|db))"), "higher"),
    ("uw", re.compile(rf"\buw\s*(?:=|:|<|≤|<=)?\s*{N}"), "lower"),
    ("ug", re.compile(rf"\bug\s*(?:=|:|<|≤|<=)?\s*{N}"), "lower"),
    ("up", re.compile(rf"\bup\s*(?:=|:|<|≤|<=)?\s*{N}"), "lower"),
    ("lambda", re.compile(rf"(?:λ|\blambda)\s*(?:=|:)?\s*{N}"), "lower"),
    ("diametre", re.compile(rf"(?:ø|⌀|\bdiam(?:etre)?\.?|\bdn)\s*{N}\s*(mm)?"), "equal"),
    ("coupe_feu", re.compile(r"\b(rei|ei|e|cf|pf)\s?(\d{2,3})\b"), "higher"),
    ("acoustique", re.compile(rf"\b(rw|dnt,?a|rа|ra)\s*(?:\(c\))?\s*(?:=|:|>|≥|>=)?\s*{N}\s*db\b"), "higher"),
    ("dosage", re.compile(rf"\bdos[ée]e?s?\s*(?:a|à)?\s*{N}\s*kg(?:\s*/\s*m3|/m³)?"), "higher"),
    ("dimensions", re.compile(r"\b(\d{2,4})\s?[x×]\s?(\d{2,4})(?:\s?[x×]\s?(\d{2,4}))?\b"), "equal"),
    ("classe_upec", re.compile(r"\bu(\d[sp]?)\s?p(\d)\s?e(\d)\s?c(\d)\b"), "higher"),
]


def _num(txt: str) -> float | None:
    v = parse_number(txt)
    return float(v) if v is not None else None


def extract_values(designation: str) -> list[TechValue]:
    """Liste des caractéristiques techniques écrites dans une désignation."""
    if not designation:
        return []
    src = designation
    f = fold(src).replace("²", "2").replace("³", "3")
    out: list[TechValue] = []
    seen: set[str] = set()
    for kind, rx, better in _RULES:
        for m in rx.finditer(f):
            text = src[m.start(): m.end()].strip() if len(src) == len(f) else m.group(0)
            if kind == "epaisseur":
                v, u = _num(m.group(1)), m.group(2)
                if v is None:
                    continue
                v = v * {"mm": 1, "cm": 10, "m": 1000}[u]
                out.append(TechValue(kind, round(v, 1), "mm", text, better))
            elif kind == "classe_beton":
                fck, fcube = int(m.group(1)), int(m.group(2))
                if not (8 <= fck <= 100 and fcube > fck):
                    continue
                out.append(TechValue(kind, float(fck), "MPa", text, better, shown=f"C{fck}/{fcube}"))
            elif kind == "coupe_feu":
                prefix = m.group(1).upper()
                minutes = int(m.group(2))
                if minutes not in (15, 20, 30, 45, 60, 90, 120, 180, 240):
                    continue
                out.append(TechValue(kind, float(minutes), "min", text, better, shown=f"{prefix} {minutes}"))
            elif kind == "acoustique":
                v = _num(m.group(2))
                if v is None:
                    continue
                out.append(TechValue(kind, v, "dB", text, better))
            elif kind == "dimensions":
                dims = [int(g) for g in m.groups() if g]
                out.append(TechValue(kind, "×".join(str(x) for x in dims), "", text, better))
            elif kind == "classe_upec":
                out.append(TechValue(kind, "U{}P{}E{}C{}".format(*m.groups()).upper(), "", text, better))
            elif kind == "diametre":
                v = _num(m.group(1))
                if v is None:
                    continue
                out.append(TechValue(kind, v, "mm", text, better))
            else:
                v = _num(m.group(1))
                if v is None:
                    continue
                unit = {"r_thermique": "m².K/W", "uw": "W/m².K", "ug": "W/m².K", "up": "W/m².K",
                        "lambda": "W/m.K", "dosage": "kg/m³"}.get(kind, "")
                if kind == "r_thermique" and not (0.1 <= v <= 20):
                    continue
                if kind in ("uw", "ug", "up") and not (0.05 <= v <= 6):
                    continue
                out.append(TechValue(kind, v, unit, text, better))
            seen.add(kind)
    # Épaisseur écrite sans « ép. » (« Dallage BA 13 cm ») : longueur isolée en cm/mm,
    # sauf diamètre (Ø 90 mm), dimension (60x30 cm) ou épaisseur déjà lue.
    if "epaisseur" not in seen:
        for m in re.finditer(r"(?<![\d,.])(\d+(?:[.,]\d+)?)\s*(mm|cm)\b", f):
            before = f[max(0, m.start() - 8): m.start()]
            after = f[m.end(): m.end() + 3]
            if re.search(r"(ø|⌀|diam\.?|dn|[x×]|r\s*=?)\s*$", before) or re.match(r"\s*[x×]", after):
                continue
            v = _num(m.group(1))
            if v is None:
                continue
            v = v * (10 if m.group(2) == "cm" else 1)
            text = src[m.start(): m.end()] if len(src) == len(f) else m.group(0)
            out.append(TechValue("epaisseur", round(v, 1), "mm", text, "higher"))
            break
    # dédoublonnage (même nature, même valeur)
    uniq: dict[tuple, TechValue] = {}
    for tv in out:
        uniq.setdefault((tv.kind, tv.value), tv)
    return list(uniq.values())


def by_kind(values: list[TechValue]) -> dict[str, TechValue]:
    """Première valeur par nature (les désignations n'en contiennent en général qu'une)."""
    out: dict[str, TechValue] = {}
    for v in values:
        out.setdefault(v.kind, v)
    return out


def compare_value(offer: TechValue, ref: TechValue) -> str:
    """'equivalent' | 'superieur' | 'inferieur' | 'different' — qualité de l'offre par rapport à la référence."""
    if offer.value == ref.value:
        return "equivalent"
    if offer.better == "equal" or isinstance(offer.value, str) or isinstance(ref.value, str):
        if offer.kind == "classe_upec" and isinstance(offer.value, str) and isinstance(ref.value, str):
            a = re.findall(r"\d", offer.value)
            b = re.findall(r"\d", ref.value)
            if len(a) == len(b) == 4:
                if all(x >= y for x, y in zip(a, b)):
                    return "superieur"
                if all(x <= y for x, y in zip(a, b)):
                    return "inferieur"
        return "different"
    hi = offer.value > ref.value
    if offer.better == "higher":
        return "superieur" if hi else "inferieur"
    return "inferieur" if hi else "superieur"
