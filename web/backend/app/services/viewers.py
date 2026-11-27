"""Visionneuses côté serveur : tableur (xlsx, xls, csv, ods via LibreOffice absent → texte), Word (docx), plan DXF (SVG), maquette IFC (résumé).

Sécurité : le HTML et le SVG sont construits ici à partir de texte échappé ; aucun contenu du fichier n'est injecté tel quel.
Les visionneuses lisent une copie en mémoire : le fichier original n'est jamais modifié.
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import io
import math
import re
from collections import Counter

MAX_ROWS, MAX_COLS, MAX_SHEETS = 300, 40, 12


class ViewError(Exception):
    pass


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "VRAI" if v else "FAUX"
    if isinstance(v, (int, float)):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return ""
        if isinstance(v, float) and not v.is_integer():
            s = f"{v:,.4f}".rstrip("0").rstrip(".")
        else:
            s = f"{int(v):,}"
        return s.replace(",", " ").replace(".", ",")
    if isinstance(v, dt.datetime):
        return v.strftime("%d/%m/%Y %H:%M") if (v.hour or v.minute) else v.strftime("%d/%m/%Y")
    if isinstance(v, dt.date):
        return v.strftime("%d/%m/%Y")
    return str(v)


def _trim(rows: list[list[str]]) -> list[list[str]]:
    while rows and not any(rows[-1]):
        rows.pop()
    width = max((max((i + 1 for i, c in enumerate(r) if c), default=0) for r in rows), default=0)
    return [r[:width] + [""] * (width - len(r[:width])) for r in rows]


def sheet_xlsx(data: bytes) -> dict:
    import openpyxl

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # fichier protégé, corrompu…
        raise ViewError(f"Classeur illisible : {exc.__class__.__name__}") from exc
    sheets = []
    for ws in wb.worksheets[:MAX_SHEETS]:
        rows, total = [], 0
        for r in ws.iter_rows(values_only=True):
            total += 1
            if len(rows) < MAX_ROWS:
                rows.append([_cell(v) for v in r[:MAX_COLS]])
        rows = _trim(rows)
        sheets.append({"name": ws.title, "rows": rows, "n_rows": total, "truncated": total > MAX_ROWS or (ws.max_column or 0) > MAX_COLS})
    wb.close()
    return {"kind": "sheet", "sheets": sheets, "more_sheets": max(0, len(wb.sheetnames) - MAX_SHEETS)}


def sheet_xls(data: bytes) -> dict:
    import xlrd

    try:
        wb = xlrd.open_workbook(file_contents=data)
    except Exception as exc:
        raise ViewError(f"Classeur .xls illisible : {exc.__class__.__name__}") from exc
    sheets = []
    for sh in wb.sheets()[:MAX_SHEETS]:
        rows = []
        for i in range(min(sh.nrows, MAX_ROWS)):
            row = []
            for j in range(min(sh.ncols, MAX_COLS)):
                c = sh.cell(i, j)
                if c.ctype == xlrd.XL_CELL_DATE:
                    try:
                        row.append(_cell(xlrd.xldate.xldate_as_datetime(c.value, wb.datemode)))
                        continue
                    except Exception:
                        pass
                row.append(_cell(c.value if c.value != "" else None))
            rows.append(row)
        sheets.append({"name": sh.name, "rows": _trim(rows), "n_rows": sh.nrows, "truncated": sh.nrows > MAX_ROWS or sh.ncols > MAX_COLS})
    return {"kind": "sheet", "sheets": sheets, "more_sheets": max(0, wb.nsheets - MAX_SHEETS)}


def sheet_csv(data: bytes) -> dict:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:4000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","
    rows, total = [], 0
    for r in csv.reader(io.StringIO(text), dialect):
        total += 1
        if len(rows) < MAX_ROWS:
            rows.append([c for c in r[:MAX_COLS]])
    return {"kind": "sheet", "sheets": [{"name": "CSV", "rows": _trim(rows), "n_rows": total, "truncated": total > MAX_ROWS}], "more_sheets": 0}


def word_docx(data: bytes) -> dict:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        d = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ViewError(f"Document Word illisible : {exc.__class__.__name__}") from exc

    def runs(p: Paragraph) -> str:
        out = []
        for r in p.runs:
            t = html.escape(r.text)
            if not t:
                continue
            if r.bold:
                t = f"<b>{t}</b>"
            if r.italic:
                t = f"<i>{t}</i>"
            if r.underline:
                t = f"<u>{t}</u>"
            out.append(t)
        return "".join(out) or html.escape(p.text)

    parts, n = [], 0
    for el in d.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(el, d)
            if not p.text.strip():
                continue
            style = (p.style.name or "").lower() if p.style is not None else ""
            m = re.search(r"(heading|titre)\s*(\d)", style)
            if m:
                lvl = min(4, int(m.group(2)) + 1)
                parts.append(f"<h{lvl}>{runs(p)}</h{lvl}>")
            elif style in ("title", "titre"):
                parts.append(f"<h1>{runs(p)}</h1>")
            elif "list" in style or "liste" in style:
                parts.append(f"<p class='li'>• {runs(p)}</p>")
            else:
                parts.append(f"<p>{runs(p)}</p>")
        elif tag == "tbl":
            t = Table(el, d)
            rows = []
            for row in t.rows[:MAX_ROWS]:
                cells, last = [], None
                for c in row.cells[:MAX_COLS]:
                    if c._tc is last:  # cellules fusionnées
                        continue
                    last = c._tc
                    cells.append(f"<td>{'<br>'.join(html.escape(x.text) for x in c.paragraphs if x.text.strip())}</td>")
                rows.append("<tr>" + "".join(cells) + "</tr>")
            parts.append("<table>" + "".join(rows) + "</table>")
        n += 1
        if len(parts) > 3000:
            parts.append("<p><i>… document tronqué pour l'aperçu.</i></p>")
            break
    head = []
    for s in d.sections[:1]:
        h = " · ".join(html.escape(p.text) for p in s.header.paragraphs if p.text.strip())
        if h:
            head.append(f"<div class='hdr'>{h}</div>")
    return {"kind": "html", "html": "".join(head + parts) or "<p><i>Document vide.</i></p>"}


# ---------------------------------------------------------------------------------------------- DXF → SVG
ACI = {1: "#d52b1e", 2: "#c9a106", 3: "#2e7d46", 4: "#1b8a8a", 5: "#2a4fa0", 6: "#8e3a8e", 7: "#222222", 8: "#7a7a7a", 9: "#a8a8a8"}


def plan_dxf(data: bytes) -> dict:
    from .geoformats import GeoError, parse_dxf

    try:
        d = parse_dxf(data)
    except GeoError as exc:
        raise ViewError(str(exc)) from exc
    ents, ext = d["entities"], d["extents"]
    if not ext:
        raise ViewError("Aucune entité 2D lisible dans ce DXF (lignes, polylignes, cercles, textes).")
    x0, y0, x1, y1 = ext
    w, h = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
    pad = 0.02 * max(w, h)
    vb = f"{x0 - pad:.4f} {-(y1 + pad):.4f} {w + 2 * pad:.4f} {h + 2 * pad:.4f}"
    stroke = max(w, h) / 900
    layers: dict[str, list[str]] = {}
    for e in ents[:60000]:
        col = ACI.get(e.get("color") or 7, "#222222")
        if e["kind"] in ("line", "polygon"):
            pts = " ".join(f"{x:.4f},{-y:.4f}" for x, y in e["coords"])
            tag = "polygon" if e["kind"] == "polygon" else "polyline"
            layers.setdefault(e["layer"], []).append(f'<{tag} points="{pts}" fill="none" stroke="{col}" stroke-width="1" vector-effect="non-scaling-stroke"/>')
        elif e["kind"] == "point":
            x, y = e["coords"]
            layers.setdefault(e["layer"], []).append(f'<circle cx="{x:.4f}" cy="{-y:.4f}" r="{stroke * 2:.4f}" fill="{col}"/>')
        elif e["kind"] == "text":
            x, y = e["coords"]
            size = e.get("height") or stroke * 12
            layers.setdefault(e["layer"], []).append(
                f'<text x="{x:.4f}" y="{-y:.4f}" font-size="{size:.4f}" fill="{col}" font-family="Inter,Arial,sans-serif">{html.escape(e["text"])}</text>')
    groups = "".join(f'<g data-layer="{html.escape(name)}">{"".join(items)}</g>' for name, items in layers.items())
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" preserveAspectRatio="xMidYMid meet">{groups}</svg>'
    return {"kind": "svg", "svg": svg, "layers": [{"name": k, "count": len(v)} for k, v in sorted(layers.items())],
            "units": d.get("units"), "extents": ext, "entities": len(ents), "unsupported": d.get("unsupported", {}),
            "notice": "Aperçu 2D simplifié (lignes, polylignes, cercles, arcs, points, textes). Blocs, cotes et hachures ne sont pas dessinés : ouvrez le plan dans votre logiciel de CAO pour le détail."}


# ---------------------------------------------------------------------------------------------- IFC (résumé)
IFC_LABELS = {
    "IFCWALL": "Murs", "IFCWALLSTANDARDCASE": "Murs", "IFCSLAB": "Dalles", "IFCBEAM": "Poutres", "IFCCOLUMN": "Poteaux",
    "IFCDOOR": "Portes", "IFCWINDOW": "Fenêtres", "IFCROOF": "Toitures", "IFCSTAIR": "Escaliers", "IFCSTAIRFLIGHT": "Volées d'escalier",
    "IFCRAILING": "Garde-corps", "IFCCURTAINWALL": "Murs-rideaux", "IFCCOVERING": "Revêtements", "IFCFOOTING": "Fondations",
    "IFCPILE": "Pieux", "IFCRAMP": "Rampes", "IFCSPACE": "Locaux (espaces)", "IFCFURNISHINGELEMENT": "Mobilier", "IFCFURNITURE": "Mobilier",
    "IFCPLATE": "Plaques", "IFCMEMBER": "Éléments d'ossature", "IFCBUILDINGELEMENTPROXY": "Objets génériques",
    "IFCFLOWTERMINAL": "Terminaux (fluides)", "IFCFLOWSEGMENT": "Réseaux (segments)", "IFCOPENINGELEMENT": "Réservations / ouvertures",
}


def _ifc_str(s: str) -> str:
    s = s.strip()
    if s in ("$", "*", ""):
        return ""
    if s.startswith("'") and s.endswith("'"):
        s = s[1:-1].replace("''", "'")
    # \X2\00E9\X0\ → é ; \S\i → caractère ISO 8859 décalé
    s = re.sub(r"\\X2\\([0-9A-Fa-f]+)\\X0\\", lambda m: "".join(chr(int(m.group(1)[i:i + 4], 16)) for i in range(0, len(m.group(1)), 4)), s)
    s = re.sub(r"\\S\\(.)", lambda m: chr(ord(m.group(1)) + 128), s)
    return s


def _split_args(a: str) -> list[str]:
    out, depth, cur, q = [], 0, [], False
    for ch in a:
        if ch == "'" and not q:
            q = True
        elif ch == "'" and q:
            q = False
        if not q and ch == "(":
            depth += 1
        elif not q and ch == ")":
            depth -= 1
        if ch == "," and depth == 0 and not q:
            out.append("".join(cur)); cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def model_ifc(data: bytes) -> dict:
    text = data.decode("utf-8", "replace")
    if "ISO-10303-21" not in text[:200]:
        raise ViewError("Fichier IFC non reconnu (format STEP attendu ; IFC-XML et IFC-ZIP ne sont pas lus par l'aperçu).")
    schema = (re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", text) or [None, "?"])[1]
    app = (re.search(r"FILE_NAME\s*\((.*?)\);", text, re.S) or [None, ""])[1]
    ents = {}
    for m in re.finditer(r"^#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*?)\);\s*$", text, re.M | re.S):
        ents[m.group(1)] = (m.group(2), m.group(3))
    counts = Counter(t for t, _ in ents.values())

    def named(kind):
        out = []
        for _id, (t, a) in ents.items():
            if t == kind:
                args = _split_args(a)
                out.append({"name": _ifc_str(args[2]) if len(args) > 2 else "", "description": _ifc_str(args[3]) if len(args) > 3 else "",
                            "args": args})
        return out

    storeys = []
    for s in named("IFCBUILDINGSTOREY"):
        elev = s["args"][9].strip() if len(s["args"]) > 9 else "$"
        try:
            ev = float(elev)
        except ValueError:
            ev = None
        storeys.append({"name": s["name"] or "(sans nom)", "elevation": ev})
    storeys.sort(key=lambda s: (s["elevation"] is None, s["elevation"] or 0))
    elements = Counter()
    for t, n in counts.items():
        if t in IFC_LABELS:
            elements[IFC_LABELS[t]] += n
    proj = named("IFCPROJECT")
    psets = counts.get("IFCPROPERTYSET", 0)
    authoring = _split_args(app)[5] if app and len(_split_args(app)) > 5 else ""
    return {"kind": "ifc", "summary": {
        "schema": schema, "project": proj[0]["name"] if proj else "", "authoring": _ifc_str(authoring),
        "sites": [s["name"] for s in named("IFCSITE")], "buildings": [b["name"] for b in named("IFCBUILDING")],
        "storeys": storeys, "elements": [{"label": k, "count": v} for k, v in elements.most_common()],
        "spaces": [s["name"] for s in named("IFCSPACE")][:200], "property_sets": psets, "entities": len(ents)},
        "notice": "Résumé de la maquette (structure spatiale et nombre d'objets par type). Pour la vue 3D, ouvrez le fichier dans une visionneuse IFC."}


def view(extension: str, data: bytes) -> dict:
    ext = (extension or "").lower()
    if ext in ("xlsx", "xlsm"):
        return sheet_xlsx(data)
    if ext == "xls":
        return sheet_xls(data)
    if ext in ("csv", "tsv"):
        return sheet_csv(data)
    if ext == "docx":
        return word_docx(data)
    if ext == "dxf":
        return plan_dxf(data)
    if ext == "ifc":
        return model_ifc(data)
    raise ViewError(f"Pas de visionneuse pour le format .{ext}.")


VIEWABLE = {"xlsx", "xlsm", "xls", "csv", "tsv", "docx", "dxf", "ifc"}
