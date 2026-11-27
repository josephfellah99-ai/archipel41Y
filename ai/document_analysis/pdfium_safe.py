"""Accès sérialisé à pdfium (rendu des pages PDF).

pdfium n'est PAS conçu pour être utilisé par plusieurs fils d'exécution simultanément : deux rendus
parallèles (aperçu de plusieurs pages, OCR d'un PDF scanné pendant un aperçu…) peuvent corrompre la
mémoire et arrêter brutalement le processus (« Segmentation fault » sous Linux, arrêt du moteur local
sous Windows). Toute utilisation de pdfium — directe (pypdfium2) ou indirecte (pdfplumber.to_image) —
passe donc par ce verrou unique.
"""
from __future__ import annotations

import io
import threading
from pathlib import Path

PDFIUM_LOCK = threading.RLock()


def page_count(path: str | Path) -> int:
    import pypdfium2 as pdfium

    with PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(str(path))
        try:
            return len(pdf)
        finally:
            pdf.close()


def render_png(path: str | Path, n: int, scale: float = 1.6) -> bytes:
    """Page n (1 = première) rendue en PNG. Lève IndexError si la page n'existe pas."""
    import pypdfium2 as pdfium

    with PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(str(path))
        try:
            if n < 1 or n > len(pdf):
                raise IndexError(n)
            page = pdf[n - 1]
            try:
                img = page.render(scale=max(0.5, min(scale, 3.0))).to_pil()
            finally:
                page.close()
        finally:
            pdf.close()
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
