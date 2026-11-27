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
    "manager": "Gestionnaire",
    "member": "Collaborateur",
    "viewer": "Lecteur",
    "guest": "Invité",
}
# Matrice des permissions par rôle (niveau global, avant les autorisations fines)
PERMISSIONS: dict[str, set[str]] = {
    "read": {"admin", "manager", "member", "viewer"},
    "write": {"admin", "manager", "member"},
    "delete": {"admin", "manager"},
    "validate": {"admin", "manager"},
    "admin": {"admin"},
}

# ------------------------------------------------------------------ autorisations par module
MODULES: dict[str, str] = {
    "projets": "Projets et chantiers",
    "devis": "Devis et comparateur",
    "documents": "Documents",
    "terrain": "Terrain, urbanisme et cartographie",
    "agenda": "Agenda",
    "planning": "Planning et météo",
    "equipe": "Équipe et collaboration",
    "finances": "Finances",
    "annuaire": "Clients et entreprises",
    "assistant": "Assistant IA",
    "rapports": "Rapports",
}
LEVELS = ("none", "read", "write", "full")
LEVEL_LABELS = {"none": "Aucun accès", "read": "Consultation", "write": "Consultation et modification", "full": "Gestion complète"}
ROLE_DEFAULT_LEVEL = {"admin": "full", "manager": "full", "member": "write", "viewer": "read"}
PERMISSION_LEVEL = {"read": "read", "write": "write", "delete": "full", "validate": "full"}

# URL → module : règles ordonnées (la plus précise d'abord), appliquées à CHAQUE requête authentifiée
import re as _re

PATH_RULES: list[tuple[str, str]] = [
    (r"^/api/projects/[^/]+/finances", "finances"),
    (r"^/api/projects/[^/]+/(schedule|baseline|weather)", "planning"),
    (r"^/api/projects/[^/]+/geo", "terrain"),
    (r"^/api/(finances|finance-entries|budget-lines)\b", "finances"),
    (r"^/api/(quotes|comparisons|dpgf|dpgf-items|cctp)\b", "devis"),
    (r"^/api/(events|calendar)\b", "agenda"),
    (r"^/api/(tasks|proposals|planning|weather)\b", "planning"),
    (r"^/api/(urbanisme|geo)\b", "terrain"),
    (r"^/api/documents\b", "documents"),
    (r"^/api/(clients|companies)\b", "annuaire"),
    (r"^/api/(assistant|conversations)\b", "assistant"),
    (r"^/api/reports\b", "rapports"),
    (r"^/api/(projects|lots|incidents|chantiers)\b", "projets"),
    (r"^/api/(comments|team)\b", "equipe"),
]
_COMPILED = [(_re.compile(rx), mod) for rx, mod in PATH_RULES]
# Lectures transverses nécessaires à tous les écrans (listes de choix) : jamais bloquées par un module
SHARED_READS = {"/api/projects", "/api/users", "/api/companies", "/api/clients", "/api/lots"}


def module_for_path(path: str) -> str | None:
    for rx, mod in _COMPILED:
        if rx.search(path):
            return mod
    return None


def _rank(level: str) -> int:
    return LEVELS.index(level) if level in LEVELS else 0


def module_level(user, module: str | None) -> str:
    """Niveau effectif d'un utilisateur sur un module : autorisation fine si définie, sinon niveau du rôle."""
    if getattr(user, "role", None) == "guest":
        return "none"
    base = ROLE_DEFAULT_LEVEL.get(user.role, "none")
    if not module:
        return base
    override = ((user.permissions or {}).get("modules") or {}).get(module)
    if user.role == "admin":
        return "full"  # un administrateur garde toujours la maîtrise complète
    return override if override in LEVELS else base


def effective_permissions(user) -> dict:
    mods = {m: module_level(user, m) for m in MODULES}
    return {
        "read": user.role in PERMISSIONS["read"],
        "write": user.role in PERMISSIONS["write"] or any(_rank(v) >= 2 for v in mods.values()),
        "delete": user.role in PERMISSIONS["delete"],
        "validate": user.role in PERMISSIONS["validate"],
        "admin": user.role == "admin",
        "modules": mods,
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


class GuestPrincipal:
    """Identité d'un invité : n'est PAS un utilisateur. Aucun point d'accès standard ne l'accepte
    (rôle « guest » absent de toutes les permissions) ; seules les routes /api/guest/* le servent."""

    def __init__(self, session, invitation):
        self.id = f"guest:{session.id}"
        self.session_id = session.id
        self.agency_id = session.agency_id
        self.role = "guest"
        self.active = True
        self.deleted = False
        self.full_name = invitation.guest_name or "Invité"
        self.email = invitation.guest_email or ""
        self.permissions = {}
        self.invitation = invitation
        self.session = session


def _guest_from_payload(db: Session, payload: dict):
    from .models import GuestSession, Invitation

    sess = db.get(GuestSession, payload.get("sub"))
    inv = db.get(Invitation, sess.invitation_id) if sess else None
    now = datetime.now(timezone.utc)
    if not sess or not inv or sess.revoked_at or inv.revoked_at or _aware(sess.expires_at) < now or _aware(inv.expires_at) < now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Accès invité expiré ou révoqué.")
    if sess.agency_id != payload.get("agency"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invité invalide.")
    return GuestPrincipal(sess, inv)


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def get_principal(request: Request, db: Session = Depends(get_db)):
    """Utilisateur OU invité (pour les routes qui servent les deux, ex. /api/auth/me)."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise.")
    payload = decode_token(token)
    if payload.get("typ") == "guest":
        g = _guest_from_payload(db, payload)
        request.state.user = g
        return g
    return _user_from_payload(db, payload, request)


def _user_from_payload(db: Session, payload: dict, request: Request) -> User:
    if payload.get("typ") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton d'authentification invalide.")
    user = db.get(User, payload.get("sub"))
    if not user or not user.active or user.deleted:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Compte inactif ou inexistant.")
    if user.agency_id != payload.get("agency"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide pour cette agence.")
    request.state.user = user
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Utilisateur authentifié de l'agence (un invité est refusé)."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise.")
    payload = decode_token(token)
    if payload.get("typ") == "guest":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès invité : cette fonction n'est pas disponible.")
    return _user_from_payload(db, payload, request)


def require(permission: str):
    """Contrôle de rôle + contrôle du module déduit de l'URL (autorisations fines)."""

    def dep(request: Request, user: User = Depends(get_current_user)) -> User:
        if permission == "admin":
            if user.role != "admin":
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Action réservée aux administrateurs.")
            return user
        path = request.url.path
        module = module_for_path(path)
        needed = PERMISSION_LEVEL.get(permission, "read")
        if module:
            level = module_level(user, module)
            shared = permission == "read" and any(path == p for p in SHARED_READS)
            if _rank(level) < _rank(needed) and not shared:
                what = {"read": "consulter", "write": "modifier", "full": "gérer"}[needed]
                raise HTTPException(status.HTTP_403_FORBIDDEN,
                                    f"Vous n'êtes pas autorisé(e) à {what} le module « {MODULES[module]} ».")
            return user
        if user.role not in PERMISSIONS[permission]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Action non autorisée pour le rôle « {ROLE_LABELS.get(user.role, user.role)} ».",
            )
        return user

    return dep


def can(user: User, permission: str) -> bool:
    return user.role in PERMISSIONS[permission]


def project_level(user, project_id: str) -> str | None:
    """Autorisation particulière sur un projet (none|read|write) ou None si aucune."""
    return ((getattr(user, "permissions", None) or {}).get("projects") or {}).get(project_id)


def accessible_project_ids(db: Session, user: User) -> set[str] | None:
    """Projets visibles. None = tous.

    - projets confidentiels : visibles de leur équipe (et des administrateurs / gestionnaires) ;
    - « projets attribués uniquement » : seuls les projets où l'utilisateur est dans l'équipe ;
    - autorisation particulière « none » sur un projet : projet masqué."""
    perms = getattr(user, "permissions", None) or {}
    overrides = perms.get("projects") or {}
    assigned_only = bool(perms.get("assigned_only"))
    if user.role == "admin" or (user.role == "manager" and not assigned_only and not any(v == "none" for v in overrides.values())):
        return None
    rows = db.query(Project.id, Project.confidential, Project.team).filter(
        Project.agency_id == user.agency_id, Project.deleted.is_(False)
    )
    ids = set()
    for pid, conf, team in rows:
        member = any((m or {}).get("user_id") == user.id for m in (team or []))
        ov = overrides.get(pid)
        if ov == "none":
            continue
        if ov in ("read", "write"):
            ids.add(pid)
            continue
        if assigned_only and not member:
            continue
        if conf and not member and user.role != "manager":
            continue
        ids.add(pid)
    return ids


def check_project_access(db: Session, user: User, project_id: str | None, write: bool = False) -> None:
    if not project_id:
        return
    p = db.get(Project, project_id)
    if not p or p.agency_id != user.agency_id or p.deleted:
        raise HTTPException(404, "Projet introuvable.")
    allowed = accessible_project_ids(db, user)
    if allowed is not None and project_id not in allowed:
        raise HTTPException(403, "Accès non autorisé à ce projet.")
    if write and user.role != "admin" and project_level(user, project_id) == "read":
        raise HTTPException(403, f"Projet {p.code} : accès en consultation seule.")
