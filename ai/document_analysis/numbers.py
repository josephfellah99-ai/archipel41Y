"""Lecture des nombres et normalisation de texte au format français."""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

_NUM_CLEAN = re.compile(r"[€\s  ]|EUR|HT|TTC", re.I)
NUMBER_TOKEN = r"-?\d{1,3}(?:[ \u00a0\u202f.]\d{3})+(?:,\d+)?(?!\d)|-?\d+(?:[.,]\d+)?"
NUMBER_RE = re.compile(rf"(?<![\w/])({NUMBER_TOKEN})(?![\w/])")


def parse_number(value) -> Decimal | None:
    """« 1 234,56 € » → Decimal('1234.56') ; « 1.234,5 » → 1234.5 ; « 12,5 % » → 12.5."""
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    s = str(value).strip()
    if not s or s in ("-", "—", "/"):
        return None
    s = s.replace("%", "")
    s = _NUM_CLEAN.sub("", s)
    s = s.replace("O", "0") if re.fullmatch(r"[\dO.,-]+", s) else s  # confusion OCR O/0
    if not re.fullmatch(r"-?[\d.,]+", s):
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        s = s.replace(",", ".") if len(parts) == 2 else s.replace(",", "")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    elif "." in s:
        head, tail = s.split(".")
        if len(tail) == 3 and len(head) <= 3 and head not in ("0", "-0"):
            # « 1.250 » est ambigu : en France le point sépare souvent les milliers
            s = head + tail
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def fold(text: str) -> str:
    """Minuscules sans accents (pour comparaisons)."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().replace("œ", "oe").replace("æ", "ae")


UNIT_ALIASES = {
    "u": "u", "un": "u", "unite": "u", "unité": "u", "pce": "u", "pc": "u", "piece": "u", "pièce": "u", "nb": "u",
    "ens": "ens", "ensemble": "ens", "ft": "ft", "fft": "ft", "forfait": "ft", "for": "ft", "f": "ft", "lot": "ens",
    "m": "ml", "ml": "ml", "mètre": "ml", "metre": "ml", "m.l": "ml", "mlin": "ml",
    "m2": "m2", "m²": "m2", "m 2": "m2", "mq": "m2",
    "m3": "m3", "m³": "m3",
    "kg": "kg", "t": "t", "tonne": "t", "h": "h", "heure": "h", "j": "j", "jour": "j",
    "l": "l", "litre": "l", "pm": "pm", "p.m.": "pm", "mois": "mois", "sem": "sem",
}
UNIT_PATTERN = r"(?:m²|m³|m2|m3|ml|m\.l|ens|ft|fft|forfait|u|un|pce|pc|nb|kg|t|h|j|l|pm|p\.m\.|m|lot|mois)"


def normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = fold(str(unit)).strip().strip(".")
    return UNIT_ALIASES.get(u, u[:12] or None)


FRENCH_VAT_RATES = (Decimal("20"), Decimal("10"), Decimal("5.5"), Decimal("2.1"), Decimal("0"))
