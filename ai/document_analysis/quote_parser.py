"""Analyse structurée d'un devis de travaux (méthode déterministe).

Stratégie :
1. tableaux détectés (PDF, Excel, Word) → reconnaissance des colonnes par
   en-têtes (désignation, quantité, unité, PU, montant, TVA) ou par contenu ;
2. à défaut, lecture ligne à ligne du texte (PDF natif ou OCR) ;
3. repérage des totaux déclarés, délais, validité, conditions, exclusions,
   réserves et variantes.

Le statut d'une ligne distingue explicitement « exclu » (mention expresse
« non compris », « hors lot »…) d'une simple absence : une prestation absente
n'est jamais classée comme exclue ici.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal

from .calc import compute_line
from .extract import ExtractResult
from .numbers import NUMBER_TOKEN, UNIT_PATTERN, fold, normalize_unit, parse_number

NUM = NUMBER_TOKEN
MONTHS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
          "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}


@dataclass
class ParsedLine:
    designation: str
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    total_ht: float | None = None
    vat_rate: float | None = None
    status: str = "inclus"
    section: str | None = None
    code: str | None = None
    confidence: float = 0.8
    page: int | None = None
    raw: str | None = None


@dataclass
class ParsedQuote:
    company_name: str | None = None
    siret: str | None = None
    reference: str | None = None
    quote_date: str | None = None
    validity_days: int | None = None
    delay_text: str | None = None
    delay_days: int | None = None
    payment_terms: str | None = None
    default_vat: float | None = None
    declared_ht: float | None = None
    declared_tva: float | None = None
    declared_ttc: float | None = None
    conditions: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    reserves: list[str] = field(default_factory=list)
    variants: list[str] = field(default_factory=list)
    lines: list[ParsedLine] = field(default_factory=list)
    method: str = "regles"
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- utilitaires
def _f(v) -> float | None:
    return float(v) if v is not None else None


STATUS_PATTERNS = [
    ("exclu", re.compile(r"\b(non[\s-]compris|non[\s-]inclus|exclu(e|s|es)?|hors[\s-](lot|marche|prestation|offre)|"
                         r"a la charge (du|de la|des) (maitre d'ouvrage|client|moa|autres? lots?)|non chiffre|sans objet)\b")),
    ("variante", re.compile(r"\bvariantes?\b")),
    ("optionnel", re.compile(r"\b(en option|option(nel(le)?)?|facultati(f|ve)|plus[\s-]value optionnelle)\b")),
    ("a_verifier", re.compile(r"\b(p\.?m\.?|pour memoire|a definir|a preciser|sur devis|selon besoin)\b")),
]


def detect_status(text: str) -> str | None:
    t = fold(text)
    for status, rx in STATUS_PATTERNS:
        if rx.search(t):
            return status
    return None


TOTAL_LINE_RX = re.compile(r"\b(sous[\s-]?total|total|montant\s+(global|total)|net a payer|t\.?v\.?a\.?|t\.?t\.?c\.?|report)\b")


def is_total_label(text: str) -> bool:
    t = fold(text).strip()
    return bool(TOTAL_LINE_RX.match(t)) or t.startswith(("total", "sous-total", "sous total", "tva", "montant ht", "montant ttc", "net a payer"))


def _date_from_text(text: str) -> str | None:
    m = re.search(r"(?:date|le|du|fait le|emis le|établi le|etabli le)\s*:?\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", text, re.I)
    if not m:
        m = re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.](20\d{2})\b", text)
    if m:
        dd, mm, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        yy = yy + 2000 if yy < 100 else yy
        try:
            return date(yy, mm, dd).isoformat()
        except ValueError:
            pass
    m = re.search(r"\b(\d{1,2})\s+(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)\s+(20\d{2})", text, re.I)
    if m:
        try:
            return date(int(m.group(3)), MONTHS[fold(m.group(2))], int(m.group(1))).isoformat()
        except (ValueError, KeyError):
            pass
    return None


def _duration_days(n: int, unit: str) -> int:
    u = fold(unit)
    if u.startswith("sem"):
        return n * 7
    if u.startswith("mois"):
        return n * 30
    if "ouvr" in u:
        return round(n * 7 / 5)
    return n


# --------------------------------------------------------------------------- en-tête & pied de devis
def parse_header(text: str, q: ParsedQuote) -> None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    head = lines[:25]
    legal = re.compile(r"\b(SARL|SAS|SASU|EURL|SA|SCOP|SNC|Entreprise|Ets\.?|[ÉE]tablissements|BTP|B[âa]timent)\b")
    head = [re.split(r"\s[-–]\s*(?:devis\b|document fictif)", ln, flags=re.I)[0].strip() for ln in head
            if not ln.lower().startswith("document fictif") and not ln.startswith("[Feuille") and ln.count(" | ") < 2]
    for ln in head:
        if legal.search(ln) and not re.search(r"devis|client|ma[iî]tre d", ln, re.I) and len(ln) < 90:
            q.company_name = re.split(r"\s[-–|]\s|\s{3,}|,\s*(?:capital|siret|si[eè]ge)", ln, flags=re.I)[0].strip()
            break
    if not q.company_name and head:
        for ln in head[:5]:
            if ln and not re.search(r"devis|page|date|n°", ln, re.I) and re.search(r"[A-Za-z]{3}", ln):
                q.company_name = ln[:120]
                break
    m = re.search(r"SIRE[TN]\s*:?\s*((?:\d[\s.]?){9,14})", text, re.I)
    if m:
        digits = re.sub(r"\D", "", m.group(1))
        q.siret = digits if len(digits) == 14 else None
    m = re.search(r"devis\s*(?:n[°o.]|num[ée]ro|r[ée]f(?:[ée]rence)?\.?)\s*:?\s*([A-Z0-9][\w\-/.]*\d[\w\-/.]*)", text, re.I)
    if m:
        q.reference = m.group(1).rstrip(".")
    q.quote_date = _date_from_text(text)
    m = re.search(r"validit[ée][^\n\d]{0,50}(\d{1,3})\s*(jours?|mois|semaines?)", text, re.I)
    if m:
        q.validity_days = _duration_days(int(m.group(1)), m.group(2))
    m = re.search(r"(d[ée]lai[^\n:]{0,40}|dur[ée]e (?:des|d'ex[ée]cution des) travaux)\s*:?\s*([^\n]{3,120})", text, re.I)
    if m:
        q.delay_text = (m.group(1) + " : " + m.group(2)).strip()[:300]
        m2 = re.search(r"(\d{1,3})\s*(jours?\s*ouvr[ée]s|jours?|semaines?|mois)", m.group(2), re.I)
        if m2:
            q.delay_days = _duration_days(int(m2.group(1)), m2.group(2))


def _amount_after(label_rx: str, text: str) -> Decimal | None:
    found = None
    for m in re.finditer(label_rx + rf"[^\d\n-]{{0,30}}({NUM})\s*(?:€|eur)?", text, re.I):
        v = parse_number(m.group(m.lastindex))
        if v is not None:
            found = v  # dernière occurrence = total général
    return found


def parse_totals(text: str, q: ParsedQuote) -> None:
    rates = re.findall(r"t\.?v\.?a\.?\s*(?:à|a|au taux de)?\s*\(?\s*(\d{1,2}(?:[.,]\d{1,2})?)\s*%", text, re.I)
    if rates:
        r = parse_number(rates[-1])
        q.default_vat = float(r) if r is not None else None
    ht = _amount_after(r"(?:total|montant)\s*(?:g[ée]n[ée]ral\s*|global\s*|des travaux\s*)?h\.?\s?t\.?(?!\w)", text)
    ttc = _amount_after(r"(?:total|montant|net)\s*(?:g[ée]n[ée]ral\s*|global\s*|[àa] payer\s*)?t\.?\s?t\.?\s?c\.?(?!\w)", text)
    tva = None
    for m in re.finditer(rf"(?:montant\s*(?:de\s*la\s*)?|total\s*)?t\.?v\.?a\.?(?:\s*(?:à|a|au taux de)?\s*\(?\s*\d{{1,2}}(?:[.,]\d{{1,2}})?\s*%\s*\)?)?[^\d\n%-]{{0,15}}({NUM})\s*(?:€|eur)?(?!\s*%)", text, re.I):
        v = parse_number(m.group(1))
        if v is not None and not (q.default_vat and v == Decimal(str(q.default_vat)) and "," not in m.group(1)):
            tva = v
    q.declared_ht, q.declared_tva, q.declared_ttc = _f(ht), _f(tva), _f(ttc)


SECTION_KEYS = {
    "exclusions": re.compile(r"^(exclusions?|prestations? non comprises?|non compris|ne sont pas compris|hors (lot|offre|prestations?))\b"),
    "reserves": re.compile(r"^(r[ée]serves?|sous r[ée]serves?|hypoth[eè]ses?)\b"),
    "conditions": re.compile(r"^(conditions?( g[ée]n[ée]rales| particuli[eè]res| de (paiement|r[eè]glement))?|modalit[ée]s|observations|remarques)\b"),
    "variants": re.compile(r"^(variantes?|options?( propos[ée]es)?)\s*:?\s*$"),
}


def parse_clauses(text: str, q: ParsedQuote) -> None:
    mode = None
    for raw in text.splitlines():
        ln = raw.strip().strip("•·-–*").strip()
        if not ln:
            continue
        f = fold(ln)
        switched = False
        for key, rx in SECTION_KEYS.items():
            if rx.match(f) and (":" in ln[:45] or len(ln.split()) <= 5) and len(ln) < 80:
                mode = key
                switched = True
                rest = ln.split(":", 1)[1].strip() if ":" in ln else ""
                if rest:
                    _add_clause(q, mode, rest)
                break
        if switched:
            continue
        if NUMBER_TAIL.search(ln) and not re.search(r"acompte|%|jours", f):
            mode = None if mode in ("variants",) else mode
        if mode and len(ln) > 3 and not is_total_label(ln):
            if re.match(r"^(total|lot|article|page)\b", f):
                mode = None
                continue
            _add_clause(q, mode, ln)
            continue
        if re.search(r"\b(acompte|conditions? de (paiement|r[eè]glement)|r[eè]glement|paiement|virement|[àa] r[ée]ception de facture|\d+ jours fin de mois)\b", f):
            if not q.payment_terms:
                q.payment_terms = ln[:300]
            elif ln not in q.payment_terms:
                q.payment_terms = (q.payment_terms + " ; " + ln)[:600]
        elif re.search(r"\bsous r[ée]serve\b|\br[ée]serve\b", f) and ln not in q.reserves:
            q.reserves.append(ln[:400])
        elif re.search(r"\b(r[ée]vision|actualisation) des prix\b|\bassurance\b|\bd[ée]cennale\b|\bp[ée]nalit[ée]s?\b", f):
            if ln not in q.conditions:
                q.conditions.append(ln[:400])


def _add_clause(q: ParsedQuote, mode: str, text: str) -> None:
    target = getattr(q, mode)
    text = text[:400]
    if text not in target:
        target.append(text)


# --------------------------------------------------------------------------- lignes (texte)
NUMBER_TAIL = re.compile(rf"({NUM})\s*(?:€|eur)?\s*$", re.I)
LINE_RX = re.compile(
    rf"^(?:(?P<code>(?:[A-Z]{{1,2}}[\s.]?)?\d{{1,2}}(?:\.\d{{1,3}}){{0,4}}\.?)\s+)?"
    rf"(?P<des>.+?)\s+"
    rf"(?:(?P<unit1>{UNIT_PATTERN})\.?\s+(?P<qty1>{NUM})|(?P<qty2>{NUM})\s+(?P<unit2>{UNIT_PATTERN})\.?|(?P<qty3>{NUM}))\s+"
    rf"(?P<pu>{NUM})\s*(?:€|eur)?\s+(?P<tot>{NUM})\s*(?:€|eur)?"
    rf"(?:\s+(?P<tva>\d{{1,2}}(?:[.,]\d{{1,2}})?)\s*%)?\s*$",
    re.I,
)
FORFAIT_RX = re.compile(
    rf"^(?:(?P<code>\d{{1,2}}(?:\.\d{{1,3}}){{0,4}}\.?)\s+)?(?P<des>.+?)\s+"
    rf"(?:(?P<unit>ft|fft|forfait|ens|ensemble|lot)\.?\s+(?:1\s+)?)?(?P<tot>\d{{1,3}}(?:[  .]\d{{3}})*,\d{{2}})\s*(?:€|eur)?\s*$",
    re.I,
)
HEADING_RX = re.compile(r"^(?:(lot|chapitre|titre|partie)\s*[\dA-Z]+\s*[-–:.]?\s*.+|(\d{1,2}(?:\.\d{1,2})?)\.?\s*[-–]?\s*[A-ZÉÈÀÂÎÔÛÇŒ][A-ZÉÈÀÂÎÔÛÇŒ '’/&,-]{3,})$")


_PIECE_RX = re.compile(r"^-?\d+(?:[.,]\d+)?$")
_UNIT_RX = re.compile(rf"^{UNIT_PATTERN}\.?$", re.I)
_NOISE_RX = re.compile(r"\b(siret|siren|capital|rcs|iban|bic|t[ée]l\.?|fax|e-?mail|www\.|code ape|tva intracom)\b|\b\d{5}\s+[A-Z][a-zé]+", re.I)


def _groupings(pieces: list[str], n: int):
    """Toutes les façons de regrouper des morceaux numériques en n nombres
    (un groupe ne peut se poursuivre que par des blocs de 3 chiffres : milliers)."""
    if n == 0:
        if not pieces:
            yield []
        return
    for k in range(1, len(pieces) - n + 2):
        head = pieces[:k]
        if k > 1:
            if not re.fullmatch(r"-?\d{1,3}", head[0]) or not all(re.fullmatch(r"\d{3}(?:[.,]\d+)?", h) for h in head[1:]):
                continue
            if any(re.search(r"[.,]", h) for h in head[1:-1]):
                continue
        for rest in _groupings(pieces[k:], n - 1):
            yield [" ".join(head)] + rest


def split_tail(ln: str):
    """Analyse « désignation [unité] qté [unité] PU total [TVA %] » en gérant les
    espaces séparateurs de milliers. Retourne un dict ou None."""
    ln = re.sub(r"\s*€", "", ln)
    vat = None
    m = re.search(r"\s(\d{1,2}(?:[.,]\d{1,2})?)\s*%\s*$", ln)
    if m:
        vat = parse_number(m.group(1))
        ln = ln[: m.start()]
    toks = ln.split()
    pieces: list[str] = []
    unit = None
    unit_pos = None
    i = len(toks) - 1
    while i >= 0:
        t = toks[i]
        if _PIECE_RX.match(t):
            pieces.insert(0, t)
        elif unit is None and _UNIT_RX.match(t) and pieces:
            unit, unit_pos = t, len(pieces)
        else:
            break
        i -= 1
    des_toks = toks[: i + 1]
    if len(pieces) < 3 or not des_toks:
        return None
    best = None
    for g in _groupings(pieces, 3):
        qty, pu, tot = (parse_number(x) for x in g)
        if None in (qty, pu, tot):
            continue
        ok = abs(qty * pu - tot) <= Decimal("0.05") + abs(tot) * Decimal("0.0005")
        cand = (ok, -len(g[0]), qty, pu, tot)
        if best is None or cand[:2] > best[:2]:
            best = cand
    if best is None:
        return None
    ok, _, qty, pu, tot = best
    code = None
    if des_toks and re.fullmatch(r"(?:[A-Z]{1,2}[.]?)?\d{1,2}(?:\.\d{1,3}){0,4}\.?", des_toks[0]):
        code = des_toks[0].strip(".")
        des_toks = des_toks[1:]
    des = " ".join(des_toks).strip(" .:-")
    if not re.search(r"[A-Za-zÀ-ÿ]{3}", des):
        return None
    return {"code": code, "des": des, "qty": qty, "pu": pu, "tot": tot, "unit": unit, "vat": vat, "consistent": ok}


def clean_ocr_line(raw: str) -> str:
    """Supprime les artefacts de grille (|, [, ]) et corrige les confusions courantes."""
    ln = re.sub(r"[|¦\[\]{}_]", " ", raw)
    ln = re.sub(r"(?<=\d)[oO](?=[\d,])", "0", ln)          # 1o0 → 100
    ln = re.sub(r"(?<=\d) ?, ?(?=\d{2}\b)", ",", ln)        # 3 900 ,00 → 3 900,00
    ln = re.sub(r"\bou(?=\s+\d+\.?\s+\d)", "u", ln)          # « u » lu « ou »
    ln = re.sub(r"\b(ft|u|ens|m2|m3|ml)\s+[LlI](?=\s+\d)", r"\1 1", ln)  # « 1 » lu « L »
    ln = re.sub(r"(?<=\d)\.(?=\s)", "", ln)                  # « 8. » → « 8 »
    ln = re.sub(r"\bm\s?[2²]\b", "m2", ln)
    ln = re.sub(r"\bm\s?[3³]\b", "m3", ln)
    return ln


def parse_text_lines(pages: list, ocr: bool) -> list[ParsedLine]:
    out: list[ParsedLine] = []
    section = None
    for page in pages:
        in_clauses = False
        for raw in page.text.splitlines():
            ln = clean_ocr_line(raw) if page.ocr else raw
            ln = re.sub(r"\s+", " ", ln).strip()
            if len(ln) < 4:
                continue
            f = fold(ln)
            if any(rx.match(f) for rx in SECTION_KEYS.values()) and len(ln.split()) <= 5:
                in_clauses = True
                continue
            if is_total_label(ln):
                continue
            if _NOISE_RX.search(ln):
                continue
            sp = split_tail(ln)
            if sp:
                in_clauses = False
                conf = 0.95 if sp["consistent"] else 0.6
                if ocr:
                    conf -= 0.15
                out.append(ParsedLine(
                    designation=sp["des"], quantity=_f(sp["qty"]), unit=normalize_unit(sp["unit"]),
                    unit_price=_f(sp["pu"]), total_ht=_f(sp["tot"]), vat_rate=_f(sp["vat"]),
                    status=detect_status(sp["des"]) or "inclus", section=section, code=sp["code"],
                    confidence=round(conf, 2), page=page.number, raw=raw.strip()))
                continue
            m = FORFAIT_RX.match(ln)
            if m and not in_clauses and re.search(r"[A-Za-zÀ-ÿ]{4}", m.group("des")) and not re.search(r"capital|siret|tel|t[ée]l[ée]phone|iban|bic|rcs", f):
                des = m.group("des").strip(" .:-")
                out.append(ParsedLine(
                    designation=des, quantity=1.0 if m.group("unit") else None,
                    unit=normalize_unit(m.group("unit")) if m.group("unit") else None,
                    unit_price=_f(parse_number(m.group("tot"))) if m.group("unit") else None,
                    total_ht=_f(parse_number(m.group("tot"))), status=detect_status(des) or "inclus",
                    section=section, code=(m.group("code") or "").strip(" .") or None,
                    confidence=0.65 if not ocr else 0.5, page=page.number, raw=raw.strip()))
                continue
            st = detect_status(ln)
            if st in ("exclu", "a_verifier", "optionnel", "variante") and not in_clauses and re.search(r"\b(compris|pm|p\.m\.|option|variante|charge)\b", f) and len(ln) < 160:
                # Poste cité sans prix (« Évacuation des gravats : non compris »)
                des = re.split(r"\s*[:\-–]\s*(?=non|pm|p\.m|en option|option|variante|a la charge|à la charge)", ln, maxsplit=1, flags=re.I)[0]
                out.append(ParsedLine(designation=des.strip(" .:-") or ln, status=st, section=section,
                                      confidence=0.6, page=page.number, raw=raw.strip()))
                continue
            if HEADING_RX.match(ln) and len(ln) < 90 and not NUMBER_TAIL.search(ln):
                section = ln.strip(" :")
                in_clauses = False
    return out


# --------------------------------------------------------------------------- lignes (tableaux)
HEADER_KEYS = {
    "designation": ("designation", "libelle", "description", "prestation", "ouvrage", "nature des travaux", "intitule", "detail"),
    "quantity": ("qte", "qt", "quantite", "quant", "nombre"),
    "unit": ("u", "un", "unite", "unit"),
    "unit_price": ("pu", "p.u", "p.u.", "prix unitaire", "pu ht", "p.u. ht", "prix u", "prix unit", "pu h.t."),
    "total_ht": ("montant", "total", "prix total", "montant ht", "total ht", "montant h.t.", "prix ht", "mt ht"),
    "code": ("n°", "no", "ref", "reference", "code", "art", "article", "poste", "item", "num"),
    "vat_rate": ("tva", "taux tva", "% tva"),
}


def _header_map(row: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(row):
        c = fold(cell).strip().strip(":").replace("  ", " ")
        if not c:
            continue
        for key, words in HEADER_KEYS.items():
            if key in mapping:
                continue
            if c in words or any(c.startswith(w) and len(w) > 2 for w in words):
                if key == "total_ht" and "unit" in c:
                    continue
                mapping[key] = idx
                break
    return mapping if "designation" in mapping and len(mapping) >= 2 else {}


def parse_tables(tables: list[tuple[int, list[list[str]]]], ocr: bool) -> list[ParsedLine]:
    out: list[ParsedLine] = []
    for page_no, rows in tables:
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
            qty, pu, tot = parse_number(get("quantity")), parse_number(get("unit_price")), parse_number(get("total_ht"))
            text_cells = " ".join(c for i, c in enumerate(row) if i != mapping["designation"])
            if qty is None and pu is None and tot is None:
                st = detect_status(des + " " + text_cells)
                if st:
                    out.append(ParsedLine(designation=des, status=st, section=section, confidence=0.7,
                                          page=page_no, raw=" | ".join(row), code=get("code") or None))
                elif re.search(r"\bcompris\b|\binclus\b", fold(text_cells)):
                    out.append(ParsedLine(designation=des, status="inclus", section=section, confidence=0.7,
                                          page=page_no, raw=" | ".join(row), code=get("code") or None))
                else:
                    section = des[:200]
                continue
            computed, issues = compute_line(qty, pu, tot)
            conf = 0.97 if (qty is not None and pu is not None and tot is not None and not issues) else (0.6 if issues else 0.8)
            if ocr:
                conf -= 0.15
            vat = parse_number(get("vat_rate")) if "vat_rate" in mapping else None
            out.append(ParsedLine(
                designation=des, quantity=_f(qty), unit=normalize_unit(get("unit")), unit_price=_f(pu),
                total_ht=_f(tot), vat_rate=_f(vat), status=detect_status(des + " " + text_cells) or "inclus",
                section=section, code=(get("code") or "").strip() or None, confidence=round(conf, 2),
                page=page_no, raw=" | ".join(row)))
    return out


# --------------------------------------------------------------------------- point d'entrée
def parse_quote(ex: ExtractResult) -> ParsedQuote:
    q = ParsedQuote()
    text = ex.text
    q.warnings.extend(ex.warnings)
    parse_header(text, q)
    parse_totals(text, q)
    parse_clauses(text, q)
    table_lines = parse_tables(ex.tables, ex.ocr_used) if ex.tables else []
    text_lines = parse_text_lines(ex.pages, ex.ocr_used)
    # On retient la source la plus riche (tableaux structurés si disponibles)
    if len(table_lines) >= max(2, int(len(text_lines) * 0.6)):
        q.lines, q.method = table_lines, "regles-tableaux"
    else:
        q.lines, q.method = text_lines, "regles-texte"
    if ex.ocr_used:
        q.method += "+ocr"
    if not q.lines:
        q.warnings.append("Aucune ligne de prix n'a été reconnue : saisissez ou corrigez les lignes manuellement, "
                          "ou relancez l'extraction avec l'assistant IA si un fournisseur est configuré.")
    if q.lines:
        q.confidence = round(sum(ln.confidence for ln in q.lines) / len(q.lines), 2)
    for ln in q.lines:
        if ln.vat_rate is None and q.default_vat is not None:
            ln.vat_rate = q.default_vat
    return q
