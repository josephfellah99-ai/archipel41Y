"""Stockage des fichiers (adressage par contenu, hors de la racine web)."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ..config import get_settings

SAFE = re.compile(r'[\x00-\x1f\x7f<>:"/\\\\|?*]+')


WINDOWS_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.I)


def safe_filename(name: str) -> str:
    """Nom de fichier sûr qui CONSERVE les accents et la ponctuation usuelle (« Pièces écrites – Réunion n°2.pdf »).
    Seuls sont remplacés les séparateurs de chemin, les caractères interdits par Windows et les caractères de contrôle.
    (Le fichier est stocké sous son empreinte : le nom n'est qu'une métadonnée.)"""
    import unicodedata

    name = unicodedata.normalize("NFC", name or "")
    name = Path(name.replace("\\", "/")).name
    name = SAFE.sub("_", name).strip(" .") or "fichier"
    if WINDOWS_RESERVED.match(name):
        name = "_" + name
    return name[:180]


def store_bytes(agency_id: str, data: bytes) -> tuple[str, str]:
    sha = hashlib.sha256(data).hexdigest()
    key = f"{agency_id}/{sha[:2]}/{sha}"
    path = get_settings().files_dir / key
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(data)
    return key, sha


def path_for(key: str) -> Path:
    base = get_settings().files_dir.resolve()
    p = (base / key).resolve()
    if base not in p.parents:
        raise ValueError("Chemin de fichier invalide.")
    return p


def exists(key: str) -> bool:
    try:
        return path_for(key).exists()
    except ValueError:
        return False
