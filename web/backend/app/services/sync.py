"""Synchronisation local-first entre un poste (mode bureau, SQLite) et le serveur central.

Principe (concurrence optimiste par version) :
- chaque modification locale marque la ligne `dirty` ; `base_version` mémorise la
  dernière version connue du serveur ;
- PUSH : le serveur accepte si sa version == base_version, sinon il renvoie un
  CONFLIT avec sa propre version des données ;
- PULL : le poste reçoit les lignes modifiées depuis son curseur (journal des
  modifications du serveur) ; une ligne locale non poussée et modifiée à distance
  devient un conflit ;
- les conflits ne sont jamais résolus silencieusement : l'utilisateur choisit
  « garder ma version » ou « garder la version du serveur ».
Les fichiers des documents sont transférés séparément et vérifiés par SHA-256.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
import uuid
from datetime import date, datetime

import httpx
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from ..crud import jsonable, record_change, to_dict
from ..db import SessionLocal, utcnow
from ..models import (Agency, ChangeLog, Document, DocumentVersion, Event, Project, SYNC_MODELS, Setting, SyncConflict,
                      Task, User, Conversation)
from . import settings_store, storage

log = logging.getLogger("archipel41.sync")
SKIP = {"dirty", "base_version"}
BATCH = 200


def row_payload(obj) -> dict:
    d = to_dict(obj, include_internal=True)
    for k in SKIP:
        d.pop(k, None)
    return d


def _coerce(model, data: dict) -> dict:
    out = {}
    cols = {c.key: c for c in inspect(model).mapper.columns}
    for k, v in data.items():
        if k not in cols or k in SKIP:
            continue
        col = cols[k]
        if v is not None:
            try:
                pt = col.type.python_type
            except NotImplementedError:
                pt = None
            if pt is datetime and isinstance(v, str):
                v = datetime.fromisoformat(v)
            elif pt is date and isinstance(v, str):
                v = date.fromisoformat(v[:10])
        out[k] = v
    return out


# =========================================================================== côté SERVEUR
def server_push(db: Session, user: User, device_id: str, changes: list[dict]) -> list[dict]:
    results = []
    for ch in changes[:1000]:
        entity, oid = ch.get("entity"), ch.get("id")
        model = SYNC_MODELS.get(entity)
        if model is None or not oid:
            results.append({"entity": entity, "id": oid, "status": "rejected", "reason": "Entité inconnue."})
            continue
        if entity == "users" and user.role != "admin" and oid != user.id:
            results.append({"entity": entity, "id": oid, "status": "rejected", "reason": "Droits insuffisants."})
            continue
        if user.role == "viewer":
            results.append({"entity": entity, "id": oid, "status": "rejected", "reason": "Compte en lecture seule."})
            continue
        data = _coerce(model, ch.get("data") or {})
        data.pop("agency_id", None)
        data.pop("version", None)
        obj = db.get(model, oid)
        base = int(ch.get("base_version") or 0)
        if obj is not None and obj.agency_id != user.agency_id:
            results.append({"entity": entity, "id": oid, "status": "rejected", "reason": "Isolation des agences."})
            continue
        if obj is None:
            obj = model(**{**data, "id": oid})
            obj.agency_id = user.agency_id
            obj.version = 1
            db.add(obj)
            db.flush()
            op = "create"
        elif obj.version == base:
            for k, v in data.items():
                if k not in ("id", "created_at"):
                    setattr(obj, k, v)
            obj.version = base + 1
            op = "delete" if obj.deleted else "update"
        else:
            results.append({"entity": entity, "id": oid, "status": "conflict", "version": obj.version, "server": row_payload(obj)})
            continue
        db.add(ChangeLog(agency_id=user.agency_id, entity=entity, entity_id=oid, version=obj.version, op=op,
                         user_id=user.id, device_id=device_id))
        results.append({"entity": entity, "id": oid, "status": "accepted", "version": obj.version})
    db.commit()
    return results


def server_pull(db: Session, user: User, since: int, limit: int = 500) -> dict:
    rows = (db.query(ChangeLog).filter(ChangeLog.agency_id == user.agency_id, ChangeLog.seq > since)
            .order_by(ChangeLog.seq).limit(limit).all())
    latest: dict[tuple, int] = {}
    for r in rows:
        latest[(r.entity, r.entity_id)] = r.seq
    out = []
    order = list(SYNC_MODELS)
    for (entity, eid), seq in sorted(latest.items(), key=lambda kv: (order.index(kv[0][0]) if kv[0][0] in order else 99, kv[1])):
        model = SYNC_MODELS.get(entity)
        obj = db.get(model, eid) if model else None
        if obj is None or obj.agency_id != user.agency_id:
            continue
        out.append({"entity": entity, "id": eid, "version": obj.version, "data": row_payload(obj)})
    cursor = rows[-1].seq if rows else since
    agency = db.get(Agency, user.agency_id)
    return {"changes": out, "cursor": cursor, "more": len(rows) == limit,
            "agency": {"id": agency.id, "name": agency.name, "is_demo": agency.is_demo}}


# =========================================================================== côté POSTE
class SyncClient:
    def __init__(self, db: Session, agency_id: str, http: httpx.Client | None = None):
        self.db = db
        self.agency_id = agency_id
        self.cfg = settings_store.get(db, agency_id, "sync")
        self.http = http or httpx.Client(timeout=60.0)

    def _url(self, path: str) -> str:
        return self.cfg["server_url"].rstrip("/") + path

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.cfg['token']}"}

    def _save_cfg(self, **patch) -> None:
        self.cfg.update(patch)
        settings_store.put(self.db, self.agency_id, "sync", patch)

    # ------------------------------------------------------------- raccordement
    def link(self, server_url: str, email: str, password: str) -> dict:
        r = self.http.post(server_url.rstrip("/") + "/api/auth/login", json={"email": email, "password": password})
        if r.status_code == 401:
            raise ValueError("Identifiants refusés par le serveur.")
        r.raise_for_status()
        body = r.json()
        remote_agency = body["agency"]["id"]
        device_id = self.cfg.get("device_id") or str(uuid.uuid4())
        new_agency = self.agency_id
        relinked = remote_agency != self.agency_id
        if relinked:
            new_agency = relink_agency(self.db, self.agency_id, remote_agency, body["agency"]["name"])
            self.agency_id = new_agency
        settings_store.put(self.db, new_agency, "sync", {
            "server_url": server_url.rstrip("/"), "email": email, "token": body["token"], "device_id": device_id,
            "enabled": True, "remote_agency_id": remote_agency, "last_pull_seq": 0, "last_error": None})
        self.db.commit()
        self.cfg = settings_store.get(self.db, new_agency, "sync")
        return {"agency_id": new_agency, "agency_name": body["agency"]["name"], "relinked": relinked}

    # ------------------------------------------------------------- push
    def push(self) -> dict:
        stats = {"sent": 0, "accepted": 0, "conflicts": 0, "rejected": 0, "files": 0}
        for entity, model in SYNC_MODELS.items():
            while True:
                dirty = (self.db.query(model).filter(model.agency_id == self.agency_id, model.dirty.is_(True))
                         .limit(BATCH).all())
                if not dirty:
                    break
                payload = [{"entity": entity, "id": o.id, "base_version": o.base_version, "data": row_payload(o)} for o in dirty]
                r = self.http.post(self._url("/api/sync/push"), headers=self._headers(),
                                   json={"device_id": self.cfg["device_id"], "changes": payload})
                if r.status_code == 401:
                    raise PermissionError("Session expirée sur le serveur : reconnectez le poste (Paramètres › Synchronisation).")
                r.raise_for_status()
                by_id = {o.id: o for o in dirty}
                for res in r.json()["results"]:
                    o = by_id.get(res["id"])
                    if o is None:
                        continue
                    stats["sent"] += 1
                    if res["status"] == "accepted":
                        o.version = o.base_version = res["version"]
                        o.dirty = False
                        stats["accepted"] += 1
                        if entity == "document_versions":
                            stats["files"] += self._upload_file(o)
                    elif res["status"] == "conflict":
                        self._conflict(entity, o, res["server"], res["version"])
                        o.dirty = False
                        stats["conflicts"] += 1
                    else:
                        o.dirty = False
                        stats["rejected"] += 1
                        log.warning("Synchronisation refusée %s/%s : %s", entity, o.id, res.get("reason"))
                self.db.commit()
        return stats

    def _upload_file(self, v: DocumentVersion) -> int:
        if not storage.exists(v.storage_key):
            return 0
        data = storage.path_for(v.storage_key).read_bytes()
        r = self.http.put(self._url(f"/api/sync/files/{v.id}"), headers=self._headers(), content=data)
        r.raise_for_status()
        return 1

    def _conflict(self, entity: str, local, remote: dict, remote_version: int) -> None:
        exists = (self.db.query(SyncConflict).filter(SyncConflict.entity_id == local.id, SyncConflict.status == "ouvert").first())
        if exists:
            exists.remote_data, exists.remote_version = jsonable(remote), remote_version
            exists.local_data = jsonable(row_payload(local))
            return
        self.db.add(SyncConflict(agency_id=self.agency_id, entity=entity, entity_id=local.id,
                                 local_data=jsonable(row_payload(local)), remote_data=jsonable(remote),
                                 local_version=local.version, remote_version=remote_version))

    # ------------------------------------------------------------- pull
    def pull(self) -> dict:
        stats = {"received": 0, "applied": 0, "conflicts": 0, "files": 0}
        since = int(self.cfg.get("last_pull_seq") or 0)
        touched_versions = []
        while True:
            r = self.http.get(self._url("/api/sync/pull"), headers=self._headers(), params={"since": since})
            if r.status_code == 401:
                raise PermissionError("Session expirée sur le serveur : reconnectez le poste (Paramètres › Synchronisation).")
            r.raise_for_status()
            body = r.json()
            for ch in body["changes"]:
                stats["received"] += 1
                res = self._apply(ch)
                stats[res] = stats.get(res, 0) + 1
                if ch["entity"] == "document_versions" and res == "applied":
                    touched_versions.append(ch["id"])
            since = body["cursor"]
            self._save_cfg(last_pull_seq=since)
            self.db.commit()
            if not body["more"]:
                break
        for vid in touched_versions:
            stats["files"] += self._download_file(vid)
        self.db.commit()
        return stats

    def _apply(self, ch: dict) -> str:
        model = SYNC_MODELS[ch["entity"]]
        data = _coerce(model, ch["data"])
        data["agency_id"] = self.agency_id
        obj = self.db.get(model, ch["id"])
        if ch["entity"] == "users" and obj is None:
            dup = self.db.query(User).filter(User.email == data.get("email"), User.id != ch["id"]).first()
            if dup:
                merge_user(self.db, dup.id, ch["id"])
        if obj is None:
            obj = model(**data)
            obj.dirty, obj.base_version = False, ch["version"]
            self.db.add(obj)
            self.db.flush()
            return "applied"
        open_conflict = (self.db.query(SyncConflict).filter(SyncConflict.entity_id == obj.id, SyncConflict.status == "ouvert").first())
        if open_conflict:
            # conflit en attente de décision : on met à jour la version serveur connue, sans toucher aux données locales
            open_conflict.remote_data, open_conflict.remote_version = jsonable(ch["data"]), ch["version"]
            return "conflicts"
        if obj.dirty and ch["version"] > obj.base_version:
            self._conflict(ch["entity"], obj, ch["data"], ch["version"])
            obj.dirty = False
            return "conflicts"
        if ch["version"] > obj.base_version or ch["version"] > obj.version:
            for k, v in data.items():
                if k != "id":
                    setattr(obj, k, v)
            obj.version = obj.base_version = ch["version"]
            obj.dirty = False
            return "applied"
        return "skipped"

    def _download_file(self, version_id: str) -> int:
        v = self.db.get(DocumentVersion, version_id)
        if v is None:
            return 0
        local_key = f"{self.agency_id}/{v.sha256[:2]}/{v.sha256}"
        if v.storage_key != local_key:
            v.storage_key = local_key
        if storage.exists(local_key):
            v.file_synced = True
            return 0
        r = self.http.get(self._url(f"/api/sync/files/{version_id}"), headers=self._headers())
        if r.status_code != 200:
            v.file_synced = False
            return 0
        if hashlib.sha256(r.content).hexdigest() != v.sha256:
            log.error("Empreinte invalide pour le fichier %s", version_id)
            v.file_synced = False
            return 0
        storage.store_bytes(self.agency_id, r.content)
        v.file_synced = True
        doc = self.db.get(Document, v.document_id)
        if doc and doc.current_version == v.number:
            from .documents import index_document, run_extraction

            ex = run_extraction(storage.path_for(local_key), v.filename)
            v.text = ex.text or None
            index_document(self.db, doc, v, ex)
        return 1

    def run(self) -> dict:
        if not self.cfg.get("server_url") or not self.cfg.get("token"):
            raise ValueError("Synchronisation non configurée.")
        started = time.time()
        try:
            push = self.push()
            pull = self.pull()
            self._save_cfg(last_sync_at=utcnow().isoformat(), last_error=None)
            self.db.commit()
            return {"ok": True, "push": push, "pull": pull, "duration_s": round(time.time() - started, 2)}
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            self.db.rollback()
            self._save_cfg(last_error="Serveur injoignable : les modifications restent enregistrées sur ce poste "
                                      f"et seront envoyées au retour du réseau ({type(exc).__name__}).")
            self.db.commit()
            raise
        except Exception as exc:
            self.db.rollback()
            self._save_cfg(last_error=str(exc)[:500])
            self.db.commit()
            raise


# =========================================================================== utilitaires
def merge_user(db: Session, old_id: str, new_id: str) -> None:
    """Fusionne un compte local avec le compte serveur de même e-mail (remappe les références)."""
    for model, col in ((Task, "responsible_id"), (Event, "organizer_id"), (Conversation, "user_id")):
        db.query(model).filter(getattr(model, col) == old_id).update({col: new_id}, synchronize_session=False)
    for p in db.query(Project).all():
        if any(m.get("user_id") == old_id for m in p.team or []):
            p.team = [{**m, "user_id": new_id} if m.get("user_id") == old_id else m for m in p.team]
    for e in db.query(Event).all():
        if any(m.get("user_id") == old_id for m in e.participants or []):
            e.participants = [{**m, "user_id": new_id} if m.get("user_id") == old_id else m for m in e.participants]
    db.query(User).filter(User.id == old_id).delete()
    db.flush()


def relink_agency(db: Session, old: str, new: str, name: str) -> str:
    """Rattache les données locales à l'agence du serveur (même identifiant des deux côtés)."""
    old_agency = db.get(Agency, old)
    if db.get(Agency, new) is None:
        db.add(Agency(id=new, name=name, siret=old_agency.siret if old_agency else None,
                      address=old_agency.address if old_agency else None))
        db.flush()
    from ..models import (AuditLog, CalendarAccount, ConnectionLog, DocumentChunk, ErrorLog, GuestSession, Invitation)

    for model in list(SYNC_MODELS.values()) + [Setting, ChangeLog, AuditLog, SyncConflict, DocumentChunk, ConnectionLog, ErrorLog,
                                               Invitation, GuestSession, CalendarAccount]:
        db.query(model).filter(model.agency_id == old).update({"agency_id": new}, synchronize_session=False)
    from .journal import reseal_agency

    reseal_agency(db, new)  # l'identifiant d'agence entre dans l'empreinte du journal chaîné
    for model in SYNC_MODELS.values():
        db.query(model).filter(model.agency_id == new).update({"dirty": True, "base_version": 0}, synchronize_session=False)
    for v in db.query(DocumentVersion).filter(DocumentVersion.agency_id == new):
        if storage.exists(v.storage_key):
            data = storage.path_for(v.storage_key).read_bytes()
            v.storage_key, _ = storage.store_bytes(new, data)
    if old_agency:
        db.delete(old_agency)
    db.flush()
    return new


_thread: threading.Thread | None = None
_stop = threading.Event()


def start_background(interval_seconds: int = 60) -> None:
    """Boucle de synchronisation automatique (mode bureau)."""
    global _thread
    if _thread and _thread.is_alive():
        return

    def loop():
        last_run: dict[str, float] = {}
        while not _stop.wait(interval_seconds):
            db = SessionLocal()
            try:
                for s in db.query(Setting).filter(Setting.key == "sync").all():
                    cfg = settings_store.get(db, s.agency_id, "sync")
                    if not cfg.get("enabled") or not cfg.get("token"):
                        continue
                    every = max(1, int(cfg.get("interval_minutes") or 5)) * 60
                    if time.time() - last_run.get(s.agency_id, 0) < every:
                        continue
                    last_run[s.agency_id] = time.time()
                    try:
                        SyncClient(db, s.agency_id).run()
                    except Exception as exc:  # erreur déjà consignée dans la configuration
                        log.info("Synchronisation automatique non aboutie : %s", exc)
            finally:
                db.close()

    _thread = threading.Thread(target=loop, name="archipel41-sync", daemon=True)
    _thread.start()


def stop_background() -> None:
    _stop.set()
