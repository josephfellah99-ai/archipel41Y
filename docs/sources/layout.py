"""Mise en page commune des guides PDF Archipel41 (HTML imprimable → PDF via Chromium)."""
from __future__ import annotations

import base64
import html
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1]
SHOTS = DOCS / "screenshots"
LOGO = (DOCS.parent / "web" / "frontend" / "public" / "favicon.svg").read_text()

CSS = """
@page { size: A4; }
* { box-sizing: border-box; }
body { font-family: Inter, 'Segoe UI', sans-serif; color: #2E3230; font-size: 10.2pt; line-height: 1.55; margin: 0; }
.cover { height: 260mm; display: flex; flex-direction: column; justify-content: space-between; page-break-after: always;
         background: #253A33; color: #F8F7F2; margin: -16mm -16mm 0; padding: 26mm 22mm; }
.cover .brand { display: flex; align-items: center; gap: 14px; letter-spacing: .3em; font-weight: 600; font-size: 13pt; }
.cover .brand svg { width: 46px; height: 46px; }
.cover h1 { font-size: 27pt; line-height: 1.2; font-weight: 600; margin: 0 0 6mm; max-width: 150mm; }
.cover .sub { font-size: 12pt; color: #B9C6BC; max-width: 140mm; }
.cover .meta { font-size: 9pt; color: #B9C6BC; border-top: 1px solid #3f5a51; padding-top: 5mm; }
h1.part { font-size: 19pt; color: #253A33; border-bottom: 2px solid #E8E3D8; padding-bottom: 3mm; margin: 0 0 5mm; page-break-before: always; }
h2 { font-size: 13.5pt; color: #253A33; margin: 7mm 0 2mm; page-break-after: avoid; }
h3 { font-size: 11pt; color: #2E3230; margin: 5mm 0 1.5mm; page-break-after: avoid; }
p { margin: 1.5mm 0 2.5mm; }
.mark { font-size: 2px; color: #fff; line-height: 0; position: absolute; }
ol.steps { counter-reset: s; list-style: none; padding: 0; margin: 2mm 0 4mm; }
ol.steps > li { counter-increment: s; position: relative; padding: 1.4mm 0 1.4mm 10mm; page-break-inside: avoid; }
ol.steps > li::before { content: counter(s); position: absolute; left: 0; top: 1.2mm; width: 6.4mm; height: 6.4mm; border-radius: 50%;
  background: #253A33; color: #fff; font-size: 8.5pt; font-weight: 600; display: flex; align-items: center; justify-content: center; }
ul { margin: 1.5mm 0 3mm; padding-left: 6mm; } li { margin: .6mm 0; }
.note, .warn, .tip, .ex { border-radius: 2.5mm; padding: 3mm 4mm; margin: 3mm 0 4mm; page-break-inside: avoid; font-size: 9.6pt; }
.note { background: #EEF2EF; border-left: 3px solid #718578; }
.warn { background: #FBF1E3; border-left: 3px solid #B07A26; }
.tip { background: #F3F1EA; border-left: 3px solid #253A33; }
.ex { background: #F8F7F2; border: 1px solid #E2DDD1; }
.note b.t, .warn b.t, .tip b.t, .ex b.t { display: block; margin-bottom: 1mm; color: #253A33; }
figure { margin: 3mm 0 5mm; page-break-inside: avoid; text-align: center; }
figure img { max-width: 100%; max-height: 118mm; border: 1px solid #E2DDD1; border-radius: 2mm; box-shadow: 0 1mm 3mm rgba(0,0,0,.06); }
figure.phone img { max-height: 120mm; }
figcaption { font-size: 8.6pt; color: #718578; margin-top: 1.5mm; }
table { width: 100%; border-collapse: collapse; margin: 2mm 0 4mm; font-size: 9pt; page-break-inside: auto; }
th { background: #253A33; color: #fff; text-align: left; padding: 1.6mm 2.2mm; font-weight: 600; }
td { border-bottom: 1px solid #E8E3D8; padding: 1.5mm 2.2mm; vertical-align: top; }
tr { page-break-inside: avoid; }
tr:nth-child(even) td { background: #FAF9F5; }
code, kbd { font-family: 'JetBrains Mono', Consolas, monospace; font-size: 8.6pt; background: #F1EEE6; padding: .2mm 1.2mm; border-radius: 1mm; }
pre { font-family: 'JetBrains Mono', Consolas, monospace; font-size: 8.2pt; background: #F1EEE6; padding: 3mm; border-radius: 2mm; white-space: pre-wrap; page-break-inside: avoid; }
.toc { page-break-after: always; }
.toc h1 { font-size: 19pt; color: #253A33; margin: 0 0 6mm; }
.toc ol { list-style: none; padding: 0; margin: 0; }
.toc li { display: flex; align-items: baseline; gap: 2mm; margin: 1.3mm 0; font-size: 10pt; }
.toc li.lvl1 { font-weight: 600; margin-top: 3mm; }
.toc li.lvl2 { padding-left: 7mm; font-size: 9.4pt; color: #444; }
.toc li .dots { flex: 1; border-bottom: 1px dotted #b8b2a4; transform: translateY(-1mm); }
.toc li .n { min-width: 8mm; text-align: right; font-variant-numeric: tabular-nums; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; }
.badge { display: inline-block; border-radius: 3mm; padding: 0 2mm; font-size: 8pt; font-weight: 600; }
.ok { background: #DCE8DF; color: #2f6a47; } .ko { background: #F4D9D2; color: #9c3b29; } .mid { background: #F6E2C6; color: #8a5a12; }
.module-card { border: 1px solid #E2DDD1; border-radius: 2.5mm; padding: 3mm 4mm; margin: 2mm 0 4mm; page-break-inside: avoid; }
.module-card h4 { margin: 0 0 1mm; font-size: 9.5pt; color: #718578; text-transform: uppercase; letter-spacing: .06em; }
"""


class Doc:
    def __init__(self, title: str, subtitle: str, short: str):
        self.title, self.subtitle, self.short = title, subtitle, short
        self.parts: list[str] = []
        self.toc: list[tuple[int, str, str]] = []
        self.n1 = 0
        self.n2 = 0

    # --------------------------------------------------------- structure
    def part(self, title: str):
        self.n1 += 1
        self.n2 = 0
        sid = f"s{self.n1}"
        label = f"{self.n1}. {title}"
        self.toc.append((1, label, sid))
        self.parts.append(f'<h1 class="part" id="{sid}"><span class="mark">ZZ{sid}ZZ</span>{html.escape(label)}</h1>')

    def sec(self, title: str):
        self.n2 += 1
        sid = f"s{self.n1}x{self.n2}"
        label = f"{self.n1}.{self.n2} {title}"
        self.toc.append((2, label, sid))
        self.parts.append(f'<h2 id="{sid}"><span class="mark">ZZ{sid}ZZ</span>{html.escape(label)}</h2>')

    def h3(self, t: str):
        self.parts.append(f"<h3>{t}</h3>")

    def p(self, *paras: str):
        self.parts += [f"<p>{x}</p>" for x in paras]

    def steps(self, *items: str):
        self.parts.append('<ol class="steps">' + "".join(f"<li>{i}</li>" for i in items) + "</ol>")

    def ul(self, *items: str):
        self.parts.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")

    def box(self, kind: str, title: str, body: str):
        self.parts.append(f'<div class="{kind}"><b class="t">{title}</b>{body}</div>')

    def note(self, body, title="À savoir"):
        self.box("note", title, body)

    def warn(self, body, title="Attention"):
        self.box("warn", title, body)

    def tip(self, body, title="Bonne pratique"):
        self.box("tip", title, body)

    def ex(self, body, title="Exemple"):
        self.box("ex", title, body)

    def table(self, head: list[str], rows: list[list[str]], widths: list[int] | None = None):
        cols = "".join(f'<col style="width:{w}%">' for w in widths) if widths else ""
        h = "".join(f"<th>{c}</th>" for c in head)
        b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
        self.parts.append(f"<table><colgroup>{cols}</colgroup><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>")

    def pre(self, text: str):
        self.parts.append(f"<pre>{html.escape(text)}</pre>")

    def img(self, name: str, caption: str, phone: bool = False, maxh: int | None = None):
        path = SHOTS / f"{name}.png"
        if not path.exists():
            raise FileNotFoundError(f"Capture manquante : {path}")
        import io

        from PIL import Image

        im = Image.open(path).convert("RGB")
        if im.width > 2200:
            im = im.resize((2200, int(im.height * 2200 / im.width)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=84, optimize=True)
        data = base64.b64encode(buf.getvalue()).decode()
        style = f' style="max-height:{maxh}mm"' if maxh else ""
        self.parts.append(f'<figure class="{"phone" if phone else ""}"><img src="data:image/jpeg;base64,{data}"{style}>'
                          f"<figcaption>{caption}</figcaption></figure>")

    def raw(self, s: str):
        self.parts.append(s)

    def module(self, objectif, utilite, infos, procedure, exemple, resultats, bonnes, limites):
        rows = [("1. Objectif", objectif), ("2. Utilité professionnelle", utilite), ("3. Informations nécessaires", infos)]
        out = "".join(f'<div class="module-card"><h4>{t}</h4>{c}</div>' for t, c in rows)
        self.parts.append(out)
        self.parts.append('<div class="module-card"><h4>4. Procédure d\'utilisation</h4>' + procedure + "</div>")
        for t, c in (("5. Exemple concret", exemple), ("6. Résultats obtenus", resultats), ("7. Bonnes pratiques", bonnes), ("8. Limites", limites)):
            self.parts.append(f'<div class="module-card"><h4>{t}</h4>{c}</div>')

    # --------------------------------------------------------- rendu
    def html(self, version: str, date: str) -> str:
        toc = "".join(
            f'<li class="lvl{l}"><span>{html.escape(t)}</span><span class="dots"></span><span class="n" data-toc="{i}"></span></li>'
            for l, t, i in self.toc)
        return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{html.escape(self.title)}</title>
<style>{CSS}</style></head><body>
<section class="cover"><div class="brand">{LOGO}<span>ARCHIPEL41</span></div>
<div><h1>{html.escape(self.title)}</h1><div class="sub">{html.escape(self.subtitle)}</div></div>
<div class="meta">Version {version} · {date}<br>Logiciel de gestion intelligente d'une agence d'architecture – application web et application Windows</div></section>
<nav class="toc"><h1>Sommaire</h1><ol>{toc}</ol></nav>
{''.join(self.parts)}
</body></html>"""
