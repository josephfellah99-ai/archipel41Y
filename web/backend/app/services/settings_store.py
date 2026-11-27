"""Paramètres par agence (clés API chiffrées au repos, jamais renvoyées en clair)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Setting
from . import crypto

SECRET_FIELDS = {"api_key", "client_secret", "password", "token"}

DEFAULTS = {
    "ai": {"provider": "aucun", "model": None, "base_url": None, "embedding_model": None, "effort": "medium",
           "allow_documents": True, "allow_confidential": False, "external": None},
    "weather": {"provider": "open-meteo", "base_url": "https://api.open-meteo.com/v1/forecast",
                "geocoder": "https://api-adresse.data.gouv.fr/search/", "demo": False},
    "urbanisme": {"apicarto": "https://apicarto.ign.fr/api", "georisques": "https://georisques.gouv.fr/api/v1",
                  "geocoder": "https://api-adresse.data.gouv.fr/search/",
                  "legifrance_client_id": None, "legifrance_client_secret": None,
                  "legifrance_oauth": "https://oauth.piste.gouv.fr/api/oauth/token",
                  "legifrance_api": "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app", "demo": False},
    "sync": {"server_url": None, "email": None, "token": None, "interval_minutes": 5, "enabled": False,
             "device_id": None, "last_pull_seq": 0, "last_sync_at": None, "last_error": None, "remote_agency_id": None},
    "agency": {"default_vat": 20, "currency": "EUR", "phases": None},
    "backup": {"auto": True, "keep": 10, "last_backup_at": None},
    "calendar": {"microsoft_client_id": None, "microsoft_client_secret": None, "microsoft_tenant": "common",
                 "google_client_id": None, "google_client_secret": None, "public_base_url": None, "interval_minutes": 15},
}


def is_secret(key: str) -> bool:
    return any(key.endswith(s) for s in SECRET_FIELDS)


def get(db: Session, agency_id: str, key: str) -> dict:
    """Valeurs effectives, secrets déchiffrés (usage interne serveur uniquement)."""
    row = db.query(Setting).filter(Setting.agency_id == agency_id, Setting.key == key).first()
    value = dict(DEFAULTS.get(key, {}))
    for k, v in ((row.value if row else {}) or {}).items():
        if k.endswith("_enc"):
            value[k[:-4]] = crypto.decrypt(v)
        else:
            value[k] = v
    return value


def get_public(db: Session, agency_id: str, key: str) -> dict:
    """Valeurs affichables : les secrets sont masqués (« sk-…abcd »)."""
    out = {}
    for k, v in get(db, agency_id, key).items():
        if is_secret(k):
            out[k] = crypto.mask(v) if v else None
            out[k + "_set"] = bool(v)
        else:
            out[k] = v
    return out


def put(db: Session, agency_id: str, key: str, patch: dict) -> dict:
    row = db.query(Setting).filter(Setting.agency_id == agency_id, Setting.key == key).first()
    current = dict(row.value or {}) if row else {}
    for k, v in patch.items():
        if k.endswith("_set"):
            continue
        if is_secret(k):
            if v in (None, ""):
                if patch.get(k + "_clear"):
                    current.pop(k + "_enc", None)
                continue  # champ vide = conserver le secret existant
            if isinstance(v, str) and "…" in v:
                continue  # valeur masquée renvoyée telle quelle
            current[k + "_enc"] = crypto.encrypt(str(v))
        elif not k.endswith("_clear"):
            current[k] = v
    if row:
        row.value = current
    else:
        db.add(Setting(agency_id=agency_id, key=key, value=current))
    db.flush()
    return get_public(db, agency_id, key)
