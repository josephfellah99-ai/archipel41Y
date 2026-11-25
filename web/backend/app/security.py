"""Authentification (JWT), hachage des mots de passe et contrôle des rôles."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import Project, User

PBKDF2_ITERATIONS = 390_000

ROLES = ("admin", "manager", "member", "viewer")
ROLE_LABELS = {
    "admin": "Administrateur",
    "manager": "Chef de projet",
    "member": "Collaborateur",
    "viewer": "Lecture seule",
}
# Matrice des permissions
PERMISSIONS: dict[str, set[str]] = {
    "read": {"admin", "manager", "member", "viewer"},
    "write": {"admin", "manager", "member"},
    "delete": {"admin", "manager"},
    "validate": {"admin", "manager"},
    "admin": {"admin"},
}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS, base64.b64encode(salt).decode(), base64.b64encode(dk).decode()
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(iterations)
        )
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except Exception:
        return False


def validate_password_strength(password: str) -> None:
    if len(password) < 10:
        raise HTTPException(422, "Le mot de passe doit contenir au moins 10 caractères.")
    classes = sum(
        [
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        ]
    )
    if classes < 3:
        raise HTTPException(
            422,
            "Le mot de passe doit combiner au moins trois types de caractères "
            "(minuscules, majuscules, chiffres, symboles).",
        )


def create_access_token(user: User) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "agency": user.agency_id,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.access_token_minutes)).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, s.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(token, s.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expirée, veuillez vous reconnecter.")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton d'authentification invalide.")


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    # Téléchargements directs (liens <a>) : jeton en paramètre
    return request.query_params.get("token")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise.")
    payload = decode_token(token)
    user = db.get(User, payload.get("sub"))
    if not user or not user.active or user.deleted:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Compte inactif ou inexistant.")
    if user.agency_id != payload.get("agency"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide pour cette agence.")
    request.state.user = user
    return user


def require(permission: str):
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in PERMISSIONS[permission]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Action non autorisée pour le rôle « {ROLE_LABELS.get(user.role, user.role)} ».",
            )
        return user

    return dep


def can(user: User, permission: str) -> bool:
    return user.role in PERMISSIONS[permission]


def accessible_project_ids(db: Session, user: User) -> set[str] | None:
    """Projets visibles. None = tous (admin/chef de projet).

    Les projets marqués confidentiels ne sont visibles que de leur équipe."""
    if user.role in ("admin", "manager"):
        return None
    rows = db.query(Project.id, Project.confidential, Project.team).filter(
        Project.agency_id == user.agency_id, Project.deleted.is_(False)
    )
    ids = set()
    for pid, conf, team in rows:
        if not conf or any((m or {}).get("user_id") == user.id for m in (team or [])):
            ids.add(pid)
    return ids


def check_project_access(db: Session, user: User, project_id: str | None) -> None:
    if not project_id:
        return
    p = db.get(Project, project_id)
    if not p or p.agency_id != user.agency_id or p.deleted:
        raise HTTPException(404, "Projet introuvable.")
    allowed = accessible_project_ids(db, user)
    if allowed is not None and project_id not in allowed:
        raise HTTPException(403, "Projet confidentiel : accès réservé à l'équipe du projet.")
