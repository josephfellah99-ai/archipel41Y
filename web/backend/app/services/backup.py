"""Sauvegarde et restauration d'une agence (données + fichiers) au format ZIP.

Contenu de l'archive :
  manifest.json   – version, date, agence, nombre d'enregistrements, empreintes SHA-256 ;
  data/<table>.json – enregistrements de l'agence (toutes tables) ;
  files/<clé>     – fichiers des documents (adressage par contenu).
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import date, datetime

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from ..config import APP_VERSION, get_settings
from ..crud import jsonable
from ..db import utcnow
from ..models import (Agency, AuditLog, ChangeLog, DocumentChunk, DocumentVersion, SYNC_MODELS, Setting, SyncConflict)
from . import storage

FORMAT = "archipel41-backup/1"
EXTRA = {"settings": Setting, "change_log": ChangeLog, "audit_logs": AuditLog, "sync_conflicts": SyncConflict}


def _rows(db: Session, model, agency_id: str) -> list[dict]:
    cols = [c.key for c in inspect(model).mapper.column_attrs]
    return [{c: jsonable(getattr(o, c)) for c in cols} for o in db.query(model).filter(model.agency_id == agency_id)]


def create_backup(db: Session, agency_id: str, include_files: bool = True) -> tuple[bytes, dict]:
    agency = db.get(Agency, agency_id)
    buf = io.BytesIO()
    counts, hashes = {}, {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data/agency.json", json.dumps({c.key: jsonable(getattr(agency, c.key)) for c in inspect(Agency).mapper.column_attrs}))
        for name, model in {**SYNC_MODELS, **EXTRA}.items():
            rows = _rows(db, model, agency_id)
            raw = json.dumps(rows, ensure_ascii=False).encode()
            zf.writestr(f"data/{name}.json", raw)
            counts[name] = len(rows)
            hashes[name] = hashlib.sha256(raw).hexdigest()
        nfiles = 0
        if include_files:
            for v in db.query(DocumentVersion).filter(DocumentVersion.agency_id == agency_id):
                if storage.exists(v.storage_key):
                    zf.write(storage.path_for(v.storage_key), f"files/{v.storage_key}")
                    nfiles += 1
        manifest = {"format": FORMAT, "app_version": APP_VERSION, "created_at": utcnow().isoformat(), "agency_id": agency_id,
                    "agency_name": agency.name, "is_demo": agency.is_demo, "counts": counts, "sha256": hashes, "files": nfiles,
                    "database": "sqlite" if get_settings().is_sqlite else "postgresql", "mode": get_settings().mode}
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return buf.getvalue(), manifest


def _coerce(model, row: dict) -> dict:
    out = {}
    for col in inspect(model).mapper.columns:
        k = col.key
        if k not in row:
            continue
        v = row[k]
        if v is not None:
            pytype = None
            try:
                pytype = col.type.python_type
            except NotImplementedError:
                pass
            if pytype is datetime and isinstance(v, str):
                v = datetime.fromisoformat(v)
            elif pytype is date and isinstance(v, str):
                v = date.fromisoformat(v[:10])
        out[k] = v
    return out


def read_manifest(data: bytes) -> dict:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        m = json.loads(zf.read("manifest.json"))
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError):
        raise ValueError("Archive de sauvegarde invalide (manifest.json absent ou illisible).")
    if m.get("format") != FORMAT:
        raise ValueError("Format de sauvegarde non reconnu.")
    names = set(zf.namelist())
    for name, h in (m.get("sha256") or {}).items():
        if f"data/{name}.json" not in names:
            raise ValueError(f"Archive incomplète : la table « {name} » annoncée dans le manifeste est absente.")
        if hashlib.sha256(zf.read(f"data/{name}.json")).hexdigest() != h:
            raise ValueError(f"Archive corrompue : empreinte invalide pour « {name} ».")
    return m


def restore_backup(db: Session, agency_id: str, data: bytes) -> dict:
    """Remplace toutes les données de l'agence courante par celles de l'archive."""
    m = read_manifest(data)
    zf = zipfile.ZipFile(io.BytesIO(data))
    src_agency = m["agency_id"]
    models = {**SYNC_MODELS, **EXTRA}
    # suppression (ordre inverse des dépendances) ; PostgreSQL : autorise la purge du journal protégé, pour cette opération seulement
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text

        db.execute(text("SET LOCAL archipel.allow_log_purge = 'on'"))
    db.query(DocumentChunk).filter(DocumentChunk.agency_id == agency_id).delete()
    for name in reversed(list(models)):
        db.query(models[name]).filter(models[name].agency_id == agency_id).delete(synchronize_session=False)
    db.flush()
    restored = {}
    names = set(zf.namelist())
    for name, model in models.items():
        # une archive d'une version antérieure ne contient pas les tables apparues depuis : restaurées vides
        rows = json.loads(zf.read(f"data/{name}.json")) if f"data/{name}.json" in names else []
        for row in rows:
            if name == "audit_logs" and row.get("agency_id") != agency_id:
                row["hash"] = row["prev_hash"] = None  # entrées d'une autre agence : conservées, hors chaînage
            row["agency_id"] = agency_id  # restauration dans l'agence courante
            if name == "change_log":
                row.pop("seq", None)
            db.add(model(**_coerce(model, row)))
        restored[name] = len(rows)
        db.flush()
    a = json.loads(zf.read("data/agency.json"))
    agency = db.get(Agency, agency_id)
    for k in ("name", "siret", "address", "email", "phone"):
        setattr(agency, k, a.get(k))
    nfiles = 0
    for info in zf.infolist():
        if info.filename.startswith("files/") and not info.is_dir():
            key = info.filename[len("files/"):]
            parts = key.split("/")
            if len(parts) != 3 or ".." in parts:
                continue
            new_key = f"{agency_id}/{parts[1]}/{parts[2]}"
            p = storage.path_for(new_key)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(zf.read(info))
            nfiles += 1
    if src_agency != agency_id:
        for v in db.query(DocumentVersion).filter(DocumentVersion.agency_id == agency_id):
            v.storage_key = v.storage_key.replace(src_agency + "/", agency_id + "/", 1)
    db.flush()
    return {"restored": restored, "files": nfiles, "source": {k: m[k] for k in ("created_at", "agency_name", "app_version")}}
