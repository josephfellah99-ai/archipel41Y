"""Lancement : python -m app  (utilisé par l'application de bureau et le script serveur)."""
import uvicorn

from .config import get_settings
from .main import create_app

if __name__ == "__main__":
    s = get_settings()
    uvicorn.run(create_app(), host=s.host, port=s.port, log_level="warning", proxy_headers=True)
