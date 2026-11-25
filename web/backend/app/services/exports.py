"""Exports PDF / XLSX / DOCX / CSV à partir d'un modèle de document commun.

Un rapport est une liste de blocs :
  {"type": "h1"|"h2"|"h3"|"p"|"bullets"|"kv"|"table"|"markdown"|"note"|"pagebreak", ...}
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime

FOREST = "#253A33"
SAGE = "#718578"
BEIGE = "#E8E3D8"
IVORY = "#F8F7F2"
ANTHRACITE = "#2E3230"


def eur(v) -> str:
    if v is None or v == "":
        return "—"
    try:
        return f"{float(v):,.2f} €".replace(",", " ").replace(".", ",")
    except (TypeError, ValueError):
        return str(v)


def _md_to_blocks(md: str) -> list[dict]:
    blocks, bullets = [], []

    def flush():
        nonlocal bullets
        if bullets:
            blocks.append({"type": "bullets", "items": bullets})
            bullets = []

    for line in (md or "").splitlines():
        s = line.strip()
        if not s:
            flush()
            continue
        if s.startswith("### "):
            flush(); blocks.append({"type": "h3", "text": s[4:]})
        elif s.startswith("## "):
            flush(); blocks.append({"type": "h2", "text": s[3:]})
        elif s.startswith("# "):
            flush(); blocks.append({"type": "h2", "text": s[2:]})
        elif s.startswith(("- ", "* ", "• ")):
            bullets.append(s[2:])
        else:
            flush(); blocks.append({"type": "p", "text": s})
    flush()
    return blocks


def expand(blocks: list[dict]) -> list[dict]:
    out = []
    for b in blocks:
        if b["type"] == "markdown":
            out.extend(_md_to_blocks(b["text"]))
        else:
            out.append(b)
    return out


def _inline_rl(text: str) -> str:
    from xml.sax.saxutils import escape

    t = escape(str(text))
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])_(.+?)_(?![\w])", r"<i>\1</i>", t)
    return t


# --------------------------------------------------------------------------- PDF
def to_pdf(title: str, blocks: list[dict], meta: dict | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    meta = meta or {}
    wide = meta.get("landscape", False)
    size = landscape(A4) if wide else A4
    buf = io.BytesIO()
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.HexColor(ANTHRACITE), alignment=TA_LEFT)
    st = {
        "title": ParagraphStyle("t", parent=base, fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=colors.HexColor(FOREST), spaceAfter=2 * mm),
        "sub": ParagraphStyle("s", parent=base, fontSize=10, textColor=colors.HexColor(SAGE), spaceAfter=6 * mm),
        "h1": ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=colors.HexColor(FOREST), spaceBefore=6 * mm, spaceAfter=2 * mm),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=colors.HexColor(FOREST), spaceBefore=4 * mm, spaceAfter=1.5 * mm),
        "h3": ParagraphStyle("h3", parent=base, fontName="Helvetica-Bold", fontSize=10.5, leading=13, spaceBefore=3 * mm, spaceAfter=1 * mm),
        "p": ParagraphStyle("p", parent=base, spaceAfter=1.5 * mm),
        "cell": ParagraphStyle("c", parent=base, fontSize=7.8, leading=9.5),
        "cellb": ParagraphStyle("cb", parent=base, fontSize=7.8, leading=9.5, fontName="Helvetica-Bold", textColor=colors.white),
        "note": ParagraphStyle("n", parent=base, fontSize=8, leading=10.5, textColor=colors.HexColor(SAGE), backColor=colors.HexColor(IVORY), borderPadding=4, spaceBefore=2 * mm, spaceAfter=2 * mm),
    }
    agency = meta.get("agency", "")
    stamp = datetime.now().strftime("%d/%m/%Y %H:%M")

    def decorate(canvas, doc):
        canvas.saveState()
        w, h = size
        canvas.setFillColor(colors.HexColor(FOREST))
        canvas.rect(0, h - 9 * mm, w, 9 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(15 * mm, h - 6 * mm, "ARCHIPEL41")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - 15 * mm, h - 6 * mm, agency[:80])
        canvas.setFillColor(colors.HexColor(SAGE))
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(15 * mm, 8 * mm, f"{title[:90]} – édité le {stamp}")
        canvas.drawRightString(w - 15 * mm, 8 * mm, f"Page {doc.page}")
        if meta.get("demo"):
            canvas.setFillColor(colors.HexColor("#B5462F"))
            canvas.drawCentredString(w / 2, 8 * mm, "DONNÉES DE DÉMONSTRATION")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=size, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=16 * mm,
                            bottomMargin=15 * mm, title=title, author="Archipel41")
    avail = size[0] - 30 * mm
    el = [Paragraph(_inline_rl(title), st["title"])]
    if meta.get("subtitle"):
        el.append(Paragraph(_inline_rl(meta["subtitle"]), st["sub"]))
    for b in expand(blocks):
        t = b["type"]
        if t in ("h1", "h2", "h3", "p"):
            el.append(Paragraph(_inline_rl(b["text"]), st[t]))
        elif t == "note":
            el.append(Paragraph(_inline_rl(b["text"]), st["note"]))
        elif t == "bullets":
            for it in b["items"]:
                el.append(Paragraph("–&nbsp;&nbsp;" + _inline_rl(it), ParagraphStyle("b", parent=st["p"], leftIndent=4 * mm, firstLineIndent=-3 * mm)))
        elif t == "kv":
            data = [[Paragraph(f"<b>{_inline_rl(k)}</b>", st["cell"]), Paragraph(_inline_rl(v), st["cell"])] for k, v in b["items"]]
            tb = Table(data, colWidths=[avail * 0.32, avail * 0.68])
            tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor(BEIGE)),
                                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(IVORY)), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            el += [tb, Spacer(1, 3 * mm)]
        elif t == "table":
            cols = b["columns"]
            widths = b.get("widths")
            cw = [avail * w for w in widths] if widths else [avail / len(cols)] * len(cols)
            data = [[Paragraph(_inline_rl(c), st["cellb"]) for c in cols]]
            for row in b["rows"]:
                data.append([Paragraph(_inline_rl("" if v is None else v), st["cell"]) for v in row])
            tb = Table(data, colWidths=cw, repeatRows=1)
            style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(FOREST)), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor(BEIGE)),
                     ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(IVORY)])]
            for (r, c, color) in b.get("cell_colors", []):
                style.append(("BACKGROUND", (c, r + 1), (c, r + 1), colors.HexColor(color)))
            tb.setStyle(TableStyle(style))
            el += [tb, Spacer(1, 3 * mm)]
        elif t == "pagebreak":
            el.append(PageBreak())
    doc.build(el, onFirstPage=decorate, onLaterPages=decorate)
    return buf.getvalue()


# --------------------------------------------------------------------------- DOCX
def to_docx(title: str, blocks: list[dict], meta: dict | None = None) -> bytes:
    import docx
    from docx.enum.section import WD_ORIENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor

    meta = meta or {}
    d = docx.Document()
    if meta.get("landscape"):
        sec = d.sections[0]
        sec.orientation = WD_ORIENT.LANDSCAPE
        sec.page_width, sec.page_height = sec.page_height, sec.page_width
    style = d.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)
    h = d.add_heading(title, 0)
    for r in h.runs:
        r.font.color.rgb = RGBColor(0x25, 0x3A, 0x33)
    if meta.get("subtitle"):
        d.add_paragraph(meta["subtitle"]).italic = True
    if meta.get("demo"):
        d.add_paragraph("DONNÉES DE DÉMONSTRATION")

    def add_runs(par, text):
        for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", str(text))):
            run = par.add_run(part)
            run.bold = i % 2 == 1

    def shade(cell, hex_color):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), hex_color.lstrip("#"))
        tcPr.append(shd)

    for b in expand(blocks):
        t = b["type"]
        if t in ("h1", "h2", "h3"):
            d.add_heading(b["text"], {"h1": 1, "h2": 2, "h3": 3}[t])
        elif t in ("p", "note"):
            add_runs(d.add_paragraph(), b["text"])
        elif t == "bullets":
            for it in b["items"]:
                add_runs(d.add_paragraph(style="List Bullet"), it)
        elif t == "kv":
            tb = d.add_table(rows=0, cols=2)
            tb.style = "Table Grid"
            for k, v in b["items"]:
                cells = tb.add_row().cells
                cells[0].text, cells[1].text = str(k), str(v)
        elif t == "table":
            tb = d.add_table(rows=1, cols=len(b["columns"]))
            tb.style = "Table Grid"
            for i, c in enumerate(b["columns"]):
                tb.rows[0].cells[i].text = str(c)
                shade(tb.rows[0].cells[i], BEIGE)
            for row in b["rows"]:
                cells = tb.add_row().cells
                for i, v in enumerate(row):
                    cells[i].text = "" if v is None else re.sub(r"\*\*", "", str(v))
            for (r, c, color) in b.get("cell_colors", []):
                shade(tb.rows[r + 1].cells[c], color)
        elif t == "pagebreak":
            d.add_page_break()
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


# --------------------------------------------------------------------------- XLSX / CSV
def to_xlsx(title: str, blocks: list[dict], meta: dict | None = None) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Rapport"
    ws.append([title])
    ws["A1"].font = Font(bold=True, size=14, color="253A33")
    if (meta or {}).get("subtitle"):
        ws.append([meta["subtitle"]])
    if (meta or {}).get("demo"):
        ws.append(["DONNÉES DE DÉMONSTRATION"])
    tables = [b for b in expand(blocks) if b["type"] == "table"]
    sheet_index = 0
    for b in expand(blocks):
        if b["type"] == "table" and len(tables) > 1 and b.get("sheet"):
            sheet_index += 1
            ws = wb.create_sheet(b["sheet"][:30])
        if b["type"] in ("h1", "h2", "h3"):
            ws.append([])
            ws.append([b["text"]])
            ws.cell(ws.max_row, 1).font = Font(bold=True, size=12, color="253A33")
        elif b["type"] in ("p", "note"):
            ws.append([re.sub(r"\*\*", "", b["text"])])
        elif b["type"] == "bullets":
            for it in b["items"]:
                ws.append(["• " + re.sub(r"\*\*", "", it)])
        elif b["type"] == "kv":
            for k, v in b["items"]:
                ws.append([k, v])
        elif b["type"] == "table":
            ws.append([])
            ws.append(b["columns"])
            hr = ws.max_row
            for i in range(1, len(b["columns"]) + 1):
                c = ws.cell(hr, i)
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor="253A33")
                c.alignment = Alignment(wrap_text=True, vertical="top")
            raw = b.get("raw_rows") or b["rows"]
            for row in raw:
                ws.append([re.sub(r"\*\*", "", v) if isinstance(v, str) else v for v in row])
            for (r, ci, color) in b.get("cell_colors", []):
                ws.cell(hr + 1 + r, ci + 1).fill = PatternFill("solid", fgColor=color.lstrip("#"))
            for i, fmt in enumerate(b.get("number_formats") or []):
                if fmt:
                    for r in range(hr + 1, ws.max_row + 1):
                        ws.cell(r, i + 1).number_format = fmt
            ws.freeze_panes = ws.cell(hr + 1, 1) if sheet_index else None
    for sheet in wb.worksheets:
        for col in range(1, sheet.max_column + 1):
            width = max((len(str(c.value)) for c in sheet[get_column_letter(col)] if c.value is not None), default=8)
            sheet.column_dimensions[get_column_letter(col)].width = min(60, max(10, width * 0.9))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_csv(title: str, blocks: list[dict], meta: dict | None = None) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    tables = [b for b in expand(blocks) if b["type"] == "table"]
    if not tables:
        w.writerow([title])
        for b in expand(blocks):
            if b["type"] in ("p", "h2", "h3"):
                w.writerow([b["text"]])
    for b in tables:
        w.writerow(b["columns"])
        for row in b.get("raw_rows") or b["rows"]:
            w.writerow([("" if v is None else (f"{v}".replace(".", ",") if isinstance(v, float) else re.sub(r"\*\*", "", str(v)))) for v in row])
        w.writerow([])
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM : ouverture correcte dans Excel


RENDERERS = {"pdf": (to_pdf, "application/pdf"),
             "docx": (to_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
             "xlsx": (to_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
             "csv": (to_csv, "text/csv; charset=utf-8")}


def render(fmt: str, title: str, blocks: list[dict], meta: dict | None = None) -> tuple[bytes, str]:
    if fmt not in RENDERERS:
        raise ValueError(f"Format non pris en charge : {fmt}")
    fn, mime = RENDERERS[fmt]
    return fn(title, blocks, meta), mime
