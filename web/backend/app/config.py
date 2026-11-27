"""Configuration d'Archipel41.

Toutes les valeurs proviennent de variables d'environnement (ou d'un fichier .env).
Aucun secret n'est codé en dur : SECRET_KEY est généré et stocké dans le dossier
de données s'il n'est pas fourni.
"""
from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "1.2.0"
ROOT_DIR = Path(__file__).resolve().parents[3]  # .../ARCHIPEL41


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARCHIPEL_", env_file=".env", extra="ignore")

    # "server" (base centrale partagée) ou "desktop" (base locale d'un poste)
    mode: str = "server"
    env: str = "development"  # development | production | test
    data_dir: Path = Path(os.environ.get("ARCHIPEL_DATA_DIR", str(ROOT_DIR / "var")))
    database_url: str = ""
    secret_key: str = ""
    access_token_minutes: int = 60 * 12
    cors_origins: str = ""
    frontend_dist: Path = ROOT_DIR / "web" / "frontend" / "dist"
    host: str = "127.0.0.1"
    port: int = 8041
    max_upload_mb: int = 200
    tesseract_cmd: str = ""
    libreoffice_cmd: str = ""
    log_level: str = "INFO"

    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'archipel41.db').as_posix()}"

    @property
    def is_sqlite(self) -> bool:
        return self.resolved_database_url().startswith("sqlite")

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"


def _ensure_secret(s: Settings) -> Settings:
    s.data_dir.mkdir(parents=True, exist_ok=True)
    for d in (s.files_dir, s.backups_dir, s.logs_dir):
        d.mkdir(parents=True, exist_ok=True)
    if not s.secret_key:
        key_file = s.data_dir / ".secret_key"
        if key_file.exists():
            s.secret_key = key_file.read_text().strip()
        else:
            s.secret_key = secrets.token_urlsafe(48)
            key_file.write_text(s.secret_key)
            try:
                os.chmod(key_file, 0o600)
            except OSError:
                pass
    return s


@lru_cache
def get_settings() -> Settings:
    return _ensure_secret(Settings())


def reset_settings_cache() -> None:
    get_settings.cache_clear()
