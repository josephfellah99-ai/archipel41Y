"""Configuration initiale, connexion et gestion des utilisateurs."""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import APP_VERSION, get_settings
from ..crud import audit, create_obj, get_owned, record_change, to_dict, update_obj
from ..db import get_db, utcnow
from ..models import Agency, GuestSession, User
from ..schemas import LoginIn, SetupIn, UserCreate, UserUpdate
from ..security import (LEVEL_LABELS, MODULES, PERMISSIONS, ROLE_DEFAULT_LEVEL, ROLE_LABELS, ROLES, create_access_token,
                        effective_permissions, get_current_user, get_principal, hash_password, require,
                        validate_password_strength, verify_password)
from ..services.journal import log_connection

router = APIRouter(prefix="/api", tags=["auth"])

_FAILS: dict[str, list[float]] = defaultdict(list)
MAX_FAILS, MAX_FAILS_IP, WINDOW = 5, 20, 300


def _throttle(*keys: str, limits: tuple[int, ...] | None = None) -> None:
    now = time.time()
    for i, key in enumerate(keys):
        limit = (limits or (MAX_FAILS,) * len(keys))[i]
        _FAILS[key] = [t for t in _FAILS[key] if now - t < WINDOW]
        if len(_FAILS[key]) >= limit:
            raise HTTPException(429, "Trop de tentatives de connexion. Réessayez dans quelques minutes.")


def _fail(*keys: str) -> None:
    for k in keys:
        _FAILS[k].append(time.time())


def user_out(u: User) -> dict:
    d = to_dict(u)
    d["role_label"] = ROLE_LABELS.get(u.role, u.role)
    return d


@router.get("/setup/status")
def setup_status(db: Session = Depends(get_db)):
    s = get_settings()
    real = db.query(Agency).filter(Agency.is_demo.is_(False)).count()
    demo = db.query(Agency).filter(Agency.is_demo.is_(True)).count()
    return {"needs_setup": real == 0 and demo == 0, "has_real_agency": real > 0, "has_demo": demo > 0,
            "mode": s.mode, "version": APP_VERSION, "database": "sqlite" if s.is_sqlite else "postgresql"}


@router.post("/setup", status_code=201)
def setup(payload: SetupIn, request: Request, db: Session = Depends(get_db)):
    if db.query(Agency).filter(Agency.is_demo.is_(False)).count():
        raise HTTPException(409, "L'application est déjà configurée.")
    validate_password_strength(payload.admin_password)
    if db.query(User).filter(User.email == payload.admin_email.lower()).first():
        raise HTTPException(409, "Cette adresse e-mail est déjà utilisée.")
    agency = Agency(name=payload.agency_name, siret=payload.agency_siret, address=payload.agency_address)
    db.add(agency)
    db.flush()
    admin = User(agency_id=agency.id, email=payload.admin_email.lower(), full_name=payload.admin_name, role="admin",
                 password_hash=hash_password(payload.admin_password), color="#253A33")
    db.add(admin)
    db.flush()
    record_change(db, admin, "create", admin)
    audit(db, admin, "setup", "agencies", agency.id, f"Création de l'agence {agency.name}", request)
    admin.last_login_at = utcnow()
    log_connection(db, kind="admin", success=True, request=request, agency_id=agency.id, user_id=admin.id, identity=admin.email,
                   reason="création de l'agence")
    db.commit()
    return {"token": create_access_token(admin), "user": user_out(admin)}


@router.post("/auth/login")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "?"
    email = payload.email.lower().strip()
    key, ipkey = f"{email}|{ip}", f"ip|{ip}"
    kind = "admin" if payload.mode == "admin" else "collaborateur"
    try:
        _throttle(key, ipkey, limits=(MAX_FAILS, MAX_FAILS_IP))
    except HTTPException:
        log_connection(db, kind=kind, success=False, request=request, identity=email, reason="trop de tentatives",
                       security_event="limitation_tentatives")
        db.commit()
        raise
    user = db.query(User).filter(User.email == email, User.deleted.is_(False)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        _fail(key, ipkey)
        audit(db, user, "login_failed", "users", user.id if user else None, email[:120], request)
        log_connection(db, kind=kind, success=False, request=request, identity=email, agency_id=user.agency_id if user else None,
                       user_id=user.id if user else None, reason="identifiants incorrects",
                       security_event="echec_repete" if len(_FAILS[key]) >= 3 else None)
        db.commit()
        raise HTTPException(401, "Identifiants incorrects.")
    if not user.active:
        log_connection(db, kind=kind, success=False, request=request, identity=email, agency_id=user.agency_id, user_id=user.id,
                       reason="compte désactivé", security_event="compte_desactive")
        db.commit()
        raise HTTPException(403, "Ce compte est désactivé. Contactez l'administrateur.")
    if payload.mode == "admin" and user.role != "admin":
        log_connection(db, kind=kind, success=False, request=request, identity=email, agency_id=user.agency_id, user_id=user.id,
                       reason="accès administrateur demandé sans droits d'administration")
        db.commit()
        raise HTTPException(403, "Ce compte n'a pas les droits d'administration : utilisez l'accès « Collaborateur ».")
    _FAILS.pop(key, None)
    user.last_login_at = utcnow()
    audit(db, user, "login", "users", user.id, None, request)
    log_connection(db, kind=kind, success=True, request=request, identity=email, agency_id=user.agency_id, user_id=user.id)
    db.commit()
    agency = db.get(Agency, user.agency_id)
    return {"token": create_access_token(user), "user": user_out(user),
            "agency": {"id": agency.id, "name": agency.name, "is_demo": agency.is_demo}}


@router.get("/auth/me")
def me(principal=Depends(get_principal), db: Session = Depends(get_db)):
    agency = db.get(Agency, principal.agency_id)
    ag = {"id": agency.id, "name": agency.name, "is_demo": agency.is_demo, "siret": agency.siret, "address": agency.address,
          "email": agency.email, "phone": agency.phone}
    if principal.role == "guest":
        from .guest import guest_scope

        return {"user": {"id": principal.id, "full_name": principal.full_name, "email": principal.email, "role": "guest",
                         "role_label": "Invité", "version": 0},
                "agency": {"id": agency.id, "name": agency.name, "is_demo": agency.is_demo},
                "permissions": {"read": False, "write": False, "delete": False, "validate": False, "admin": False, "modules": {}},
                "guest": guest_scope(db, principal), "mode": get_settings().mode}
    return {"user": user_out(principal), "agency": ag, "permissions": effective_permissions(principal), "mode": get_settings().mode}


@router.post("/auth/logout")
def logout(request: Request, principal=Depends(get_principal), db: Session = Depends(get_db)):
    if principal.role == "guest":
        sess = db.get(GuestSession, principal.session_id)
        if sess and not sess.revoked_at:
            sess.revoked_at = utcnow()
        log_connection(db, kind="deconnexion", success=True, request=request, agency_id=principal.agency_id,
                       identity=f"invité · {principal.invitation.label}", session_id=principal.session_id)
    else:
        log_connection(db, kind="deconnexion", success=True, request=request, agency_id=principal.agency_id,
                       user_id=principal.id, identity=principal.email)
    db.commit()
    return {"ok": True}


@router.post("/auth/change-password")
def change_password(payload: dict, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.get("current_password", ""), user.password_hash):
        raise HTTPException(403, "Mot de passe actuel incorrect.")
    validate_password_strength(payload.get("new_password", ""))
    user.password_hash = hash_password(payload["new_password"])
    user.version += 1
    record_change(db, user, "update", user, {"password": "modifié"})
    audit(db, user, "password_change", "users", user.id, None, request)
    db.commit()
    return {"ok": True}


@router.put("/agency")
def update_agency(payload: dict, user: User = Depends(require("admin")), db: Session = Depends(get_db)):
    a = db.get(Agency, user.agency_id)
    for k in ("name", "siret", "address", "email", "phone"):
        if k in payload:
            v = (payload[k] or "").strip() or None
            if k == "name" and not v:
                raise HTTPException(422, "Le nom de l'agence est obligatoire.")
            setattr(a, k, v)
    a.version += 1
    audit(db, user, "update", "agencies", a.id, "Coordonnées de l'agence")
    db.commit()
    return {"id": a.id, "name": a.name, "siret": a.siret, "address": a.address, "email": a.email, "phone": a.phone}


# ------------------------------------------------------------------ utilisateurs
@router.get("/users")
def list_users(user: User = Depends(require("read")), db: Session = Depends(get_db)):
    rows = db.query(User).filter(User.agency_id == user.agency_id, User.deleted.is_(False)).order_by(User.full_name).all()
    return [user_out(u) for u in rows]


@router.get("/roles")
def roles(user: User = Depends(get_current_user)):
    return [{"code": r, "label": ROLE_LABELS[r], "permissions": [p for p, rs in PERMISSIONS.items() if r in rs],
             "default_level": ROLE_DEFAULT_LEVEL[r]} for r in ROLES]


@router.get("/permissions/catalog")
def permissions_catalog(user: User = Depends(get_current_user)):
    return {"modules": [{"code": k, "label": v} for k, v in MODULES.items()],
            "levels": [{"code": k, "label": v} for k, v in LEVEL_LABELS.items()],
            "project_levels": [{"code": k, "label": LEVEL_LABELS[k]} for k in ("none", "read", "write")]}


@router.post("/users", status_code=201)
def create_user(payload: UserCreate, request: Request, admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    validate_password_strength(payload.password)
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(409, "Cette adresse e-mail est déjà utilisée.")
    data = payload.model_dump()
    data["email"] = data["email"].lower()
    data["password_hash"] = hash_password(data.pop("password"))
    data["permissions"] = data.get("permissions") or {}
    u = create_obj(db, User, data, admin, request)
    u.password_hash = data["password_hash"]
    db.commit()
    return user_out(u)


@router.delete("/users/{user_id}")
def delete_user(user_id: str, request: Request, admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    """Suppression d'un compte : l'historique (journaux, auteurs) est conservé ; le compte ne peut plus se connecter."""
    target = get_owned(db, User, user_id, admin)
    if target.id == admin.id:
        raise HTTPException(409, "Vous ne pouvez pas supprimer votre propre compte.")
    if target.role == "admin":
        admins = db.query(User).filter(User.agency_id == admin.agency_id, User.role == "admin", User.active.is_(True),
                                       User.deleted.is_(False)).count()
        if admins <= 1:
            raise HTTPException(409, "Impossible de supprimer le dernier administrateur.")
    from ..crud import delete_obj

    target.active = False
    old_email = target.email
    target.email = f"supprime-{target.id[:8]}-{old_email}"[:200]  # libère l'adresse pour un nouveau compte
    delete_obj(db, target, admin, request)
    db.commit()
    return {"ok": True, "message": f"Compte de {target.full_name} supprimé ({old_email})."}


@router.put("/users/{user_id}")
def update_user(user_id: str, payload: UserUpdate, request: Request, current: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    target = get_owned(db, User, user_id, current)
    is_admin = current.role == "admin"
    if not is_admin and target.id != current.id:
        raise HTTPException(403, "Seul un administrateur peut modifier un autre utilisateur.")
    data = payload.model_dump(exclude_unset=True)
    version = data.pop("version", None)
    if not is_admin:
        for forbidden in ("role", "active", "permissions"):
            data.pop(forbidden, None)
    if target.id == current.id and (data.get("role") not in (None, "admin") or data.get("active") is False):
        admins = db.query(User).filter(User.agency_id == current.agency_id, User.role == "admin", User.active.is_(True),
                                       User.deleted.is_(False)).count()
        if admins <= 1:
            raise HTTPException(409, "Impossible de retirer les droits du dernier administrateur.")
    pw = data.pop("password", None)
    update_obj(db, target, data, current, version, request)
    if pw:
        validate_password_strength(pw)
        target.password_hash = hash_password(pw)
        target.version += 1
        record_change(db, target, "update", current, {"password": "modifié"})
    db.commit()
    return user_out(target)
