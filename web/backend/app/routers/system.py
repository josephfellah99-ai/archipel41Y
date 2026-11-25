"""Paramètres, informations système, sauvegarde/restauration, synchronisation, audit, démonstration."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from ai.document_analysis.extract import find_libreoffice, find_tesseract
from ai.llm.providers import AIError

from ..config import APP_VERSION, get_settings
from ..crud import audit, jsonable, scoped_query, to_dict
from ..db import get_db, utcnow
from ..models import (Agency, AuditLog, Document, DocumentVersion, SYNC_MODELS, SyncConflict, User)
from ..security import get_current_user, require
from ..services import ai as ai_service
from ..services import backup as backup_svc
from ..services import documents as docsvc
from ..services import settings_store, storage
from ..services import sync as sync_svc

router = APIRouter(prefix="/api", tags=["système"])
EDITABLE = {"ai", "weather", "urbanisme", "agency", "backup"}


@router.get("/system/info")
def info(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = get_settings()
    out = {"version": APP_VERSION, "mode": s.mode, "env": s.env, "database": "sqlite" if s.is_sqlite else "postgresql",
           "ocr": bool(find_tesseract(s.tesseract_cmd or None)), "libreoffice": bool(find_libreoffice(s.libreoffice_cmd or None)),
           "ai": ai_service.status(db, user.agency_id)}
    if user.role == "admin":
        out["data_dir"] = str(s.data_dir)
        if not s.is_sqlite:
            try:
                exts = {r[0]: r[1] for r in db.execute(__import__("sqlalchemy").text("select extname, extversion from pg_extension"))}
                out["extensions"] = exts
            except Exception:
                out["extensions"] = {}
    return out


@router.get("/settings/{key}")
def get_setting(key: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    if key not in EDITABLE | {"sync"}:
        raise HTTPException(404, "Paramètre inconnu.")
    return settings_store.get_public(db, user.agency_id, key)


@router.put("/settings/{key}")
def put_setting(key: str, payload: dict, request: Request, user: User = Depends(require("admin")), db: Session = Depends(get_db)):
    if key not in EDITABLE:
        raise HTTPException(404, "Paramètre inconnu.")
    if key == "ai" and payload.get("provider") not in (None, "aucun", "anthropic", "openai_compat"):
        raise HTTPException(422, "Fournisseur d'IA inconnu.")
    out = settings_store.put(db, user.agency_id, key, payload)
    audit(db, user, "settings", "settings", None, f"Paramètres « {key} » modifiés", request)
    db.commit()
    return out


@router.post("/settings/ai/test")
def test_ai(user: User = Depends(require("admin")), db: Session = Depends(get_db)):
    p = ai_service.get_provider(db, user.agency_id)
    if not p.available:
        return {"ok": False, "message": "Aucun fournisseur configuré : l'application fonctionne en mode sans IA générative."}
    try:
        r = p.chat("Réponds uniquement par le mot OK.", [{"role": "user", "content": "Test de connexion Archipel41."}], 50)
        return {"ok": True, "message": f"Connexion réussie ({r.provider} – {r.model}).", "reply": r.text[:100]}
    except AIError as exc:
        return {"ok": False, "message": str(exc)}


@router.post("/settings/{key}/test")
def test_service(key: str, user: User = Depends(require("admin")), db: Session = Depends(get_db)):
    cfg = settings_store.get(db, user.agency_id, key)
    targets = {"weather": [cfg.get("base_url"), cfg.get("geocoder")],
               "urbanisme": [cfg.get("apicarto") + "/gpu/municipality?insee=44109", cfg.get("georisques") + "/gaspar/risques?code_insee=44109",
                             cfg.get("geocoder") + "?q=nantes&limit=1"]}.get(key)
    if not targets:
        raise HTTPException(404, "Aucun test pour ce service.")
    res = []
    for url in targets:
        try:
            r = httpx.get(url, params={"latitude": 47.2, "longitude": -1.55, "daily": "temperature_2m_max"} if "open-meteo" in url else None,
                          timeout=10, headers={"User-Agent": "Archipel41/1.0"})
            res.append({"url": url.split("?")[0], "ok": r.status_code < 500, "status": r.status_code})
        except httpx.HTTPError as exc:
            res.append({"url": url.split("?")[0], "ok": False, "status": type(exc).__name__})
    return {"ok": all(x["ok"] for x in res), "results": res}


# ------------------------------------------------------------------ sauvegardes
@router.post("/backups")
def make_backup(request: Request, include_files: bool = True, user: User = Depends(require("admin")), db: Session = Depends(get_db)):
    data, manifest = backup_svc.create_backup(db, user.agency_id, include_files)
    name = f"archipel41_sauvegarde_{utcnow():%Y%m%d_%H%M%S}.zip"
    path = get_settings().backups_dir / user.agency_id
    path.mkdir(parents=True, exist_ok=True)
    (path / name).write_bytes(data)
    cfg = settings_store.get(db, user.agency_id, "backup")
    keep = int(cfg.get("keep") or 10)
    files = sorted(path.glob("archipel41_sauvegarde_*.zip"))
    for old in files[:-keep]:
        old.unlink(missing_ok=True)
    settings_store.put(db, user.agency_id, "backup", {"last_backup_at": manifest["created_at"]})
    audit(db, user, "backup", None, None, name, request)
    db.commit()
    return {"name": name, "size": len(data), "manifest": manifest}


@router.get("/backups")
def list_backups(user: User = Depends(require("admin"))):
    path = get_settings().backups_dir / user.agency_id
    return [{"name": p.name, "size": p.stat().st_size, "created_at": p.stat().st_mtime}
            for p in sorted(path.glob("*.zip"), reverse=True)] if path.exists() else []


@router.get("/backups/{name}")
def download_backup(name: str, user: User = Depends(require("admin"))):
    path = (get_settings().backups_dir / user.agency_id / storage.safe_filename(name))
    if not path.exists() or not name.endswith(".zip"):
        raise HTTPException(404, "Sauvegarde introuvable.")
    return FileResponse(path, media_type="application/zip", filename=path.name)


@router.post("/backups/inspect")
async def inspect_backup(file: UploadFile = File(...), user: User = Depends(require("admin"))):
    try:
        return backup_svc.read_manifest(await file.read())
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/restore")
async def restore(request: Request, file: UploadFile = File(...), confirm: str = "", user: User = Depends(require("admin")),
                  db: Session = Depends(get_db)):
    if confirm != "RESTAURER":
        raise HTTPException(422, "Confirmation requise : saisissez RESTAURER.")
    data = await file.read()
    # sauvegarde de sécurité avant écrasement
    pre, _ = backup_svc.create_backup(db, user.agency_id, True)
    path = get_settings().backups_dir / user.agency_id
    path.mkdir(parents=True, exist_ok=True)
    (path / f"archipel41_sauvegarde_{utcnow():%Y%m%d_%H%M%S}_avant_restauration.zip").write_bytes(pre)
    try:
        res = backup_svc.restore_backup(db, user.agency_id, data)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    for d in db.query(Document).filter(Document.agency_id == user.agency_id, Document.deleted.is_(False)):
        v = db.query(DocumentVersion).filter(DocumentVersion.document_id == d.id, DocumentVersion.number == d.current_version).first()
        if v and storage.exists(v.storage_key):
            ex = docsvc.run_extraction(storage.path_for(v.storage_key), v.filename)
            docsvc.index_document(db, d, v, ex)
    db.add(AuditLog(agency_id=user.agency_id, action="restore", summary=f"Restauration depuis {file.filename}"))
    db.commit()
    return res


# ------------------------------------------------------------------ synchronisation (serveur)
@router.post("/sync/push")
def sync_push(payload: dict, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    if get_settings().mode != "server":
        raise HTTPException(409, "Ce poste n'est pas un serveur de synchronisation.")
    return {"results": sync_svc.server_push(db, user, str(payload.get("device_id") or "")[:64], payload.get("changes") or [])}


@router.get("/sync/pull")
def sync_pull(since: int = 0, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    if get_settings().mode != "server":
        raise HTTPException(409, "Ce poste n'est pas un serveur de synchronisation.")
    return sync_svc.server_pull(db, user, since)


@router.get("/sync/files/{version_id}")
def sync_file_get(version_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    v = db.get(DocumentVersion, version_id)
    if not v or v.agency_id != user.agency_id:
        raise HTTPException(404, "Fichier introuvable.")
    key = f"{user.agency_id}/{v.sha256[:2]}/{v.sha256}"
    if not storage.exists(key):
        raise HTTPException(404, "Fichier non encore reçu par le serveur.")
    return FileResponse(storage.path_for(key), media_type="application/octet-stream")


@router.put("/sync/files/{version_id}")
async def sync_file_put(version_id: str, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    v = db.get(DocumentVersion, version_id)
    if not v or v.agency_id != user.agency_id:
        raise HTTPException(404, "Version inconnue : synchronisez d'abord les métadonnées.")
    data = await request.body()
    key, sha = storage.store_bytes(user.agency_id, data)
    if sha != v.sha256:
        raise HTTPException(422, "Empreinte SHA-256 du fichier incorrecte.")
    v.storage_key, v.file_synced = key, True
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ synchronisation (poste)
@router.get("/sync/status")
def sync_status(user: User = Depends(require("read")), db: Session = Depends(get_db)):
    cfg = settings_store.get_public(db, user.agency_id, "sync")
    pending = sum(db.query(m).filter(m.agency_id == user.agency_id, m.dirty.is_(True)).count() for m in SYNC_MODELS.values())
    conflicts = db.query(SyncConflict).filter(SyncConflict.agency_id == user.agency_id, SyncConflict.status == "ouvert").count()
    return {"mode": get_settings().mode, "configured": bool(cfg.get("server_url") and cfg.get("token_set")),
            "server_url": cfg.get("server_url"), "email": cfg.get("email"), "enabled": cfg.get("enabled"),
            "interval_minutes": cfg.get("interval_minutes"), "last_sync_at": cfg.get("last_sync_at"),
            "last_error": cfg.get("last_error"), "pending_changes": pending, "open_conflicts": conflicts}


@router.post("/sync/configure")
def sync_configure(payload: dict, request: Request, user: User = Depends(require("admin")), db: Session = Depends(get_db)):
    if get_settings().mode != "desktop":
        raise HTTPException(409, "La synchronisation se configure sur les postes en mode bureau.")
    url = (payload.get("server_url") or "").strip()
    if not url.startswith(("https://", "http://")):
        raise HTTPException(422, "Adresse du serveur invalide (https://…).")
    try:
        res = sync_svc.SyncClient(db, user.agency_id).link(url, payload.get("email", ""), payload.get("password", ""))
    except ValueError as exc:
        raise HTTPException(401, str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"Serveur injoignable : {type(exc).__name__}")
    if "interval_minutes" in payload:
        settings_store.put(db, res["agency_id"], "sync", {"interval_minutes": int(payload["interval_minutes"] or 5)})
    db.add(AuditLog(agency_id=res["agency_id"], user_id=user.id, action="sync_link", summary=url))
    db.commit()
    return {**res, "message": "Poste raccordé. Reconnectez-vous si l'agence a changé." if res["relinked"] else "Poste raccordé."}


@router.post("/sync/run")
def sync_run(user: User = Depends(require("read")), db: Session = Depends(get_db)):
    try:
        return sync_svc.SyncClient(db, user.agency_id).run()
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    except PermissionError as exc:
        raise HTTPException(401, str(exc))
    except httpx.HTTPError:
        raise HTTPException(503, settings_store.get(db, user.agency_id, "sync").get("last_error") or "Serveur injoignable.")


@router.post("/sync/disable")
def sync_disable(user: User = Depends(require("admin")), db: Session = Depends(get_db)):
    settings_store.put(db, user.agency_id, "sync", {"enabled": False})
    db.commit()
    return {"ok": True}


@router.get("/sync/conflicts")
def conflicts(user: User = Depends(require("read")), db: Session = Depends(get_db)):
    return [{c.key: jsonable(getattr(x, c.key)) for c in x.__table__.columns}
            for x in db.query(SyncConflict).filter(SyncConflict.agency_id == user.agency_id).order_by(SyncConflict.detected_at.desc()).limit(200)]


@router.post("/sync/conflicts/{cid}/resolve")
def resolve(cid: str, payload: dict, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    c = db.get(SyncConflict, cid)
    if not c or c.agency_id != user.agency_id or c.status != "ouvert":
        raise HTTPException(404, "Conflit introuvable ou déjà résolu.")
    choice = payload.get("keep")
    model = SYNC_MODELS[c.entity]
    obj = db.get(model, c.entity_id)
    if choice == "local":
        data = sync_svc._coerce(model, c.local_data)
        data.pop("agency_id", None)
        for k, v in data.items():
            if k != "id":
                setattr(obj, k, v)
        obj.base_version = c.remote_version
        obj.dirty = True  # sera poussé au prochain cycle et remplacera la version serveur
    elif choice == "remote":
        data = sync_svc._coerce(model, c.remote_data)
        data.pop("agency_id", None)
        for k, v in data.items():
            if k != "id":
                setattr(obj, k, v)
        obj.version = obj.base_version = c.remote_version
        obj.dirty = False
    else:
        raise HTTPException(422, "Choix attendu : local ou remote.")
    c.status, c.resolution, c.resolved_by, c.resolved_at = "resolu", choice, user.id, utcnow()
    db.add(AuditLog(agency_id=user.agency_id, user_id=user.id, action="sync_resolve", entity=c.entity, entity_id=c.entity_id,
                    summary=f"Conflit résolu : version {'locale' if choice == 'local' else 'serveur'} conservée"))
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ audit
@router.get("/audit")
def audit_log(limit: int = 200, user: User = Depends(require("admin")), db: Session = Depends(get_db)):
    names = {u.id: u.full_name for u in db.query(User).filter(User.agency_id == user.agency_id)}
    rows = db.query(AuditLog).filter(AuditLog.agency_id == user.agency_id).order_by(AuditLog.at.desc()).limit(min(limit, 2000))
    return [{"at": r.at.isoformat(), "user": names.get(r.user_id, "—"), "action": r.action, "entity": r.entity,
             "entity_id": r.entity_id, "summary": r.summary, "ip": r.ip} for r in rows]


# ------------------------------------------------------------------ démonstration
@router.post("/demo")
def create_demo(payload: dict, db: Session = Depends(get_db)):
    """Crée l'espace de DÉMONSTRATION (agence fictive séparée, comptes dédiés)."""
    if db.query(Agency).filter(Agency.is_demo.is_(True)).count():
        raise HTTPException(409, "L'espace de démonstration existe déjà (compte demo@archipel41.demo).")
    from ..security import validate_password_strength

    pw = payload.get("password") or ""
    validate_password_strength(pw)
    import sys
    from pathlib import Path

    from ..config import ROOT_DIR

    sys.path.insert(0, str(ROOT_DIR / "database" / "seeds"))
    from demo_seed import seed_demo  # noqa: E402

    info = seed_demo(db, pw)
    db.commit()
    return info
