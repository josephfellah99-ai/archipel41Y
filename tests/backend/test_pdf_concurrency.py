"""Non-régression : arrêt brutal du moteur lors de l'aperçu d'un PDF (rendus pdfium simultanés).

Le test s'exécute dans un sous-processus : un plantage natif (segmentation fault) y est détecté
par son code de sortie au lieu d'arrêter la suite de tests."""
import subprocess
import sys
import textwrap

from conftest import DEMO, ROOT

SCRIPT = textwrap.dedent('''
    import sys, threading
    sys.path.insert(0, sys.argv[2])
    from ai.document_analysis.pdfium_safe import page_count, render_png
    from ai.document_analysis.extract import extract_document
    path = sys.argv[1]
    errors = []
    def preview():
        for _ in range(4):
            n = page_count(path)
            for i in range(1, n + 1):
                render_png(path, i, 1.6)
    def ocr():
        for _ in range(1):
            extract_document(sys.argv[3])
    threads = [threading.Thread(target=preview) for _ in range(6)] + [threading.Thread(target=ocr)]
    for t in threads: t.start()
    for t in threads: t.join()
    print("OK")
''')


def test_parallel_pdf_rendering_does_not_crash_engine():
    pdf = DEMO / "Devis_Durand_Lot02_GrosOeuvre.pdf"
    scan = DEMO / "Devis_LeGoff_Lot02_scan.pdf"
    r = subprocess.run([sys.executable, "-c", SCRIPT, str(pdf), str(ROOT), str(scan)], capture_output=True, text=True, timeout=600)
    assert r.returncode == 0 and "OK" in r.stdout, f"code {r.returncode} : {r.stderr[-800:]}"
