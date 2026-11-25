"""Moteur CRUD générique : isolation par agence, droits, concurrence optimiste,
journal des modifications (historique + synchronisation) et audit."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import inspect, or_
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db, utcnow
from .models import AuditLog, ChangeLog, Project, SYNC_MODELS, User
from .security import accessible_project_ids, check_project_access, get_current_user, require

INTERNAL_FIELDS = {"dirty", "base_version", "password_hash"}
ENTITY_BY_MODEL = {m: name for name, m in SYNC_MODELS.items()}


def jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    return value


def to_dict(obj, include_internal: bool = False) -> dict:
    out = {}
    for col in inspect(obj).mapper.column_attrs:
        k = col.key
        if not include_internal and k in INTERNAL_FIELDS:
            continue
        out[k] = jsonable(getattr(obj, k))
    return out


def column_names(model) -> set[str]:
    return {c.key for c in inspect(model).column_attrs}


def record_change(db: Session, obj, op: str, user: User | None, changes: dict | None = None) -> None:
    """Journalise une modification. En mode bureau, marque l'objet « à synchroniser »."""
    entity = ENTITY_BY_MODEL.get(type(obj))
    if entity is None:
        return
    if get_settings().mode == "desktop":
        obj.dirty = True
    db.add(
        ChangeLog(
            agency_id=obj.agency_id,
            entity=entity,
            entity_id=obj.id,
            version=obj.version,
            op=op,
            user_id=user.id if user else None,
            changes=jsonable(changes) if changes else None,
        )
    )


def audit(db: Session, user: User | None, action: str, entity: str | None = None,
          entity_id: str | None = None, summary: str | None = None, request: Request | None = None) -> None:
    db.add(
        AuditLog(
            agency_id=user.agency_id if user else None,
            user_id=user.id if user else None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            summary=(summary or "")[:2000],
            ip=request.client.host if request and request.client else None,
        )
    )


def get_owned(db: Session, model, obj_id: str, user: User, allow_deleted: bool = False):
    obj = db.get(model, obj_id)
    if obj is None or obj.agency_id != user.agency_id or (obj.deleted and not allow_deleted):
        raise HTTPException(404, "Élément introuvable.")
    pid = obj.id if isinstance(obj, Project) else getattr(obj, "project_id", None)
    if pid:
        check_project_access(db, user, pid)
    return obj


def create_obj(db: Session, model, data: dict, user: User, request: Request | None = None):
    cols = column_names(model)
    # password_hash n'est jamais présent dans un schéma de formulaire (extra="forbid") : seul le code serveur le fournit
    data = {k: v for k, v in data.items() if k in cols and k not in {"dirty", "base_version", "agency_id", "version"}}
    if "project_id" in data and data["project_id"]:
        check_project_access(db, user, data["project_id"])
    obj = model(**data)
    obj.agency_id = user.agency_id
    obj.updated_by = user.id
    obj.version = 1
    db.add(obj)
    db.flush()
    record_change(db, obj, "create", user)
    audit(db, user, "create", ENTITY_BY_MODEL.get(model), obj.id, _label(obj), request)
    return obj


def update_obj(db: Session, obj, data: dict, user: User, expected_version: int | None,
               request: Request | None = None):
    if expected_version is not None and expected_version != obj.version:
        raise HTTPException(
            409,
            detail={
                "message": "Conflit de modification : cet élément a été modifié entre-temps par un autre utilisateur ou appareil.",
                "current": to_dict(obj),
            },
        )
    cols = column_names(type(obj))
    changes = {}
    for k, v in data.items():
        if k in cols and k not in INTERNAL_FIELDS | {"id", "agency_id", "version", "created_at"}:
            old = getattr(obj, k)
            if jsonable(old) != jsonable(v):
                changes[k] = {"avant": jsonable(old), "apres": jsonable(v)}
                setattr(obj, k, v)
    if "project_id" in changes and data.get("project_id"):
        check_project_access(db, user, data["project_id"])
    if changes:
        obj.version += 1
        obj.updated_by = user.id
        obj.updated_at = utcnow()
        record_change(db, obj, "update", user, changes)
        audit(db, user, "update", ENTITY_BY_MODEL.get(type(obj)), obj.id,
              f"{_label(obj)} : {', '.join(changes)}", request)
    return obj


def delete_obj(db: Session, obj, user: User, request: Request | None = None):
    obj.deleted = True
    obj.version += 1
    obj.updated_by = user.id
    obj.updated_at = utcnow()
    record_change(db, obj, "delete", user)
    audit(db, user, "delete", ENTITY_BY_MODEL.get(type(obj)), obj.id, _label(obj), request)


def _label(obj) -> str:
    for attr in ("name", "title", "designation", "label", "reference", "email"):
        v = getattr(obj, attr, None)
        if v:
            return str(v)[:120]
    return obj.id


def scoped_query(db: Session, model, user: User):
    q = db.query(model).filter(model.agency_id == user.agency_id, model.deleted.is_(False))
    if model is Project or hasattr(model, "project_id"):
        allowed = accessible_project_ids(db, user)
        if allowed is not None:
            if model is Project:
                q = q.filter(model.id.in_(allowed))
            else:
                q = q.filter(or_(model.project_id.is_(None), model.project_id.in_(allowed)))
    return q


def crud_router(
    model,
    path: str,
    schema: type[BaseModel],
    *,
    search_fields: tuple[str, ...] = ("name",),
    filter_fields: tuple[str, ...] = ("project_id",),
    order_by: str | None = None,
    after_change: Callable[[Session, Any, User], None] | None = None,
    tag: str | None = None,
) -> APIRouter:
    router = APIRouter(prefix=f"/api/{path}", tags=[tag or path])

    @router.get("")
    def list_items(
        request: Request,
        q: str | None = None,
        limit: int = Query(500, le=5000),
        offset: int = 0,
        user: User = Depends(require("read")),
        db: Session = Depends(get_db),
    ):
        query = scoped_query(db, model, user)
        for f in filter_fields:
            v = request.query_params.get(f)
            if v:
                query = query.filter(getattr(model, f) == v)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(*[getattr(model, f).ilike(like) for f in search_fields]))
        col = getattr(model, order_by or "updated_at")
        query = query.order_by(col.desc() if not order_by else col)
        return [to_dict(o) for o in query.offset(offset).limit(limit).all()]

    @router.get("/{obj_id}")
    def get_item(obj_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
        return to_dict(get_owned(db, model, obj_id, user))

    @router.post("", status_code=201)
    def create_item(payload: schema, request: Request, user: User = Depends(require("write")),  # type: ignore[valid-type]
                    db: Session = Depends(get_db)):
        data = payload.model_dump()
        client_id = request.headers.get("x-client-id")
        if client_id and len(client_id) == 36:
            if db.get(model, client_id):
                # Rejeu idempotent d'une création hors ligne
                return to_dict(get_owned(db, model, client_id, user))
            data["id"] = client_id
        obj = create_obj(db, model, data, user, request)
        if after_change:
            after_change(db, obj, user)
        db.commit()
        return to_dict(obj)

    @router.put("/{obj_id}")
    def update_item(obj_id: str, payload: dict, request: Request, user: User = Depends(require("write")),
                    db: Session = Depends(get_db)):
        obj = get_owned(db, model, obj_id, user)
        version = payload.pop("version", None)
        current = {k: v for k, v in to_dict(obj).items() if k in schema.model_fields}
        current.update({k: v for k, v in payload.items() if k in schema.model_fields})
        validated = schema.model_validate(current).model_dump()
        update_obj(db, obj, validated, user, version, request)
        if after_change:
            after_change(db, obj, user)
        db.commit()
        return to_dict(obj)

    @router.delete("/{obj_id}")
    def delete_item(obj_id: str, request: Request, version: int | None = None,
                    user: User = Depends(require("delete")), db: Session = Depends(get_db)):
        obj = get_owned(db, model, obj_id, user)
        if version is not None and version != obj.version:
            raise HTTPException(409, detail={"message": "Conflit : élément modifié entre-temps.", "current": to_dict(obj)})
        delete_obj(db, obj, user, request)
        if after_change:
            after_change(db, obj, user)
        db.commit()
        return {"ok": True}

    @router.get("/{obj_id}/history")
    def history(obj_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
        get_owned(db, model, obj_id, user, allow_deleted=True)
        rows = (
            db.query(ChangeLog)
            .filter(ChangeLog.agency_id == user.agency_id, ChangeLog.entity_id == obj_id)
            .order_by(ChangeLog.seq.desc())
            .limit(200)
            .all()
        )
        names = {u.id: u.full_name for u in db.query(User).filter(User.agency_id == user.agency_id)}
        return [
            {"seq": r.seq, "op": r.op, "version": r.version, "at": jsonable(r.at),
             "user": names.get(r.user_id, "—"), "changes": r.changes}
            for r in rows
        ]

    return router
