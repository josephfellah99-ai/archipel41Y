"""Lancement : python -m app  (utilisé par l'application de bureau et le script serveur)."""
import faulthandler
import time

import uvicorn

from .config import get_settings
from .main import create_app


def _report_previous_crash(s) -> None:
    """Un plantage natif (ex. bibliothèque C) ne peut pas être journalisé au moment où il survient :
    faulthandler écrit la pile dans crash.log ; au démarrage suivant, l'incident est versé au journal
    technique (gravité « critique ») puis le fichier est archivé."""
    crash = s.logs_dir / "crash.log"
    if not crash.exists() or crash.stat().st_size == 0:
        return
    trace = crash.read_text(encoding="utf-8", errors="replace")[-6000:]
    from .services.journal import log_error_isolated

    ref = log_error_isolated(source="python", severity="critique", module=None,
                             message="Arrêt inattendu du moteur local lors de la session précédente.",
                             explanation="Le moteur s'est arrêté brutalement (erreur native). Il a été redémarré ; "
                                         "transmettez cette référence au support avec le journal si le problème se reproduit.",
                             context={"trace": trace})
    crash.rename(s.logs_dir / f"crash-{time.strftime('%Y%m%d-%H%M%S')}{'-' + ref if ref else ''}.log")


if __name__ == "__main__":
    s = get_settings()
    app = create_app()
    try:
        _report_previous_crash(s)
    except Exception:
        pass
    crash_file = open(s.logs_dir / "crash.log", "a", encoding="utf-8")  # noqa: SIM115 – ouvert pour toute la durée du processus
    faulthandler.enable(crash_file, all_threads=True)
    uvicorn.run(app, host=s.host, port=s.port, log_level="warning", proxy_headers=True)
