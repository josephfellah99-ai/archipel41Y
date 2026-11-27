"""Génère les trois PDF de documentation dans docs/ :  .venv/bin/python docs/sources/build_docs.py"""
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import doc_technique  # noqa: E402
import guide_installation  # noqa: E402
import guide_utilisation  # noqa: E402

VERSION = "1.2.0"
DATE = date.today().strftime("%d/%m/%Y")
OUT = HERE.parent
TARGETS = [(guide_installation, "GUIDE_INSTALLATION_ARCHIPEL41.pdf", "Guide d'installation et de démarrage"),
           (guide_utilisation, "GUIDE_UTILISATION_ARCHIPEL41.pdf", "Guide utilisateur"),
           (doc_technique, "DOCUMENTATION_TECHNIQUE.pdf", "Documentation technique")]

for module, pdf, short in TARGETS:
    doc = module.build()
    html_path = HERE / (Path(pdf).stem + ".html")
    html_path.write_text(doc.html(VERSION, DATE), encoding="utf-8")
    subprocess.run(["node", str(HERE / "render_pdf.cjs"), str(html_path), str(OUT / pdf), short], check=True)
