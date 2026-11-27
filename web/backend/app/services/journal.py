"""Journalisation : connexions, modifications (chaînées) et erreurs techniques.

Règles :
- aucun mot de passe, jeton, clé ou secret n'est jamais enregistré (filtrage systématique) ;
- chaque entrée du journal d'activité est chaînée à la précédente (SHA-256) : une modification
  ou une suppression directe en base est détectable (vérification `verify_chain`) ;
- les erreurs reçoivent un identifiant court (ex. « E-7K2QF9 ») communiqué à l'utilisateur.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models import AuditLog, ConnectionLog, ErrorLog

SECRET_KEYS = re.compile(r"pass(word)?|mot_de_passe|token|jeton|secret|api_key|apikey|authorization|cookie|code|tokens_enc|password_hash|key$", re.I)
SECRET_VALUES = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+|eyJ[A-Za-z0-9._\-]{20,}|sk-[A-Za-z0-9\-_]{10,}", re.I)


def redact(value, depth: int = 0):
    """Supprime récursivement toute valeur susceptible d'être un secret."""
    if depth > 6:
        return "…"
    if isinstance(value, dict):
        return {k: ("[masqué]" if SECRET_KEYS.search(str(k)) else redact(v, depth + 1)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, depth + 1) for v in list(value)[:200]]
    if isinstance(value, str):
        return SECRET_VALUES.sub(lambda m: (m.group(1) or "") + "[masqué]", value)[:4000]
    return value


def device_from_ua(ua: str | None) -> str:
    ua = ua or ""
    if "Archipel41" in ua or "Electron" in ua:
        app = "Application Windows"
    elif re.search(r"Edg/", ua):
        app = "Edge"
    elif re.search(r"Chrome/", ua):
        app = "Chrome"
    elif re.search(r"Firefox/", ua):
        app = "Firefox"
    elif re.search(r"Safari/", ua):
        app = "Safari"
    elif re.search(r"python|httpx|curl|testclient", ua, re.I):
        app = "Client technique"
    else:
        app = "Navigateur"
    if re.search(r"iPhone|Android.+Mobile", ua):
        kind = "smartphone"
    elif re.search(r"iPad|Android|Tablet", ua):
        kind = "tablette"
    elif re.search(r"Windows", ua):
        kind = "ordinateur Windows"
    elif re.search(r"Macintosh|Mac OS", ua):
        kind = "ordinateur Mac"
    elif re.search(r"Linux", ua):
        kind = "ordinateur Linux"
    else:
        kind = "appareil inconnu"
    return f"{app} · {kind}"


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    return request.client.host if request.client else None


def log_connection(db: Session, *, kind: str, success: bool, request: Request | None, agency_id: str | None = None,
                   user_id: str | None = None, identity: str | None = None, reason: str | None = None,
                   session_id: str | None = None, security_event: str | None = None) -> None:
    ua = request.headers.get("user-agent") if request else None
    db.add(ConnectionLog(agency_id=agency_id, user_id=user_id, identity=(identity or "")[:200] or None, kind=kind, success=success,
                         reason=reason, ip=client_ip(request), user_agent=(ua or "")[:300] or None, device=device_from_ua(ua),
                         session_id=session_id, security_event=security_event))


# ------------------------------------------------------------------ journal d'activité chaîné
def _entry_digest(e: AuditLog, prev: str | None) -> str:
    payload = json.dumps({
        "prev": prev or "", "id": e.id, "agency": e.agency_id, "user": e.user_id, "at": aware(e.at).strftime("%Y-%m-%dT%H:%M:%S.%f") if e.at else "",
        "action": e.action, "entity": e.entity, "entity_id": e.entity_id, "summary": e.summary, "module": e.module,
        "project": e.project_id, "changes": e.changes, "result": e.result,
    }, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def seal(db: Session, e: AuditLog) -> None:
    """Calcule le chaînage de l'entrée par rapport à la dernière entrée scellée de l'agence."""
    from ..db import new_id

    if not e.id:
        e.id = new_id()
    if e.at is None:
        e.at = utcnow()
    if e.at.tzinfo is None:
        e.at = e.at.replace(tzinfo=timezone.utc)
    key = ("audit_last", e.agency_id)
    prev = db.info.get(key)
    if prev is None:
        last = (db.query(AuditLog.hash).filter(AuditLog.agency_id == e.agency_id, AuditLog.hash.isnot(None))
                .order_by(AuditLog.at.desc(), AuditLog.id.desc()).first())
        prev = last[0] if last else None
    e.prev_hash = prev
    e.hash = _entry_digest(e, prev)
    db.info[key] = e.hash


def reseal_agency(db: Session, agency_id: str) -> int:
    """Recalcule le chaînage d'une agence (après rattachement d'un poste à l'agence du serveur central :
    l'identifiant d'agence fait partie de l'empreinte). Le contenu des entrées n'est pas modifié."""
    db.flush()
    prev = None
    n = 0
    for e in db.query(AuditLog).filter(AuditLog.agency_id == agency_id).order_by(AuditLog.at.asc(), AuditLog.id.asc()):
        e.prev_hash = prev
        e.hash = _entry_digest(e, prev)
        prev = e.hash
        n += 1
    db.info[("audit_last", agency_id)] = prev
    return n


def verify_chain(db: Session, agency_id: str) -> dict:
    """Recalcule le chaînage : signale toute entrée modifiée, supprimée ou insérée hors application."""
    rows = (db.query(AuditLog).filter(AuditLog.agency_id == agency_id, AuditLog.hash.isnot(None))
            .order_by(AuditLog.at.asc(), AuditLog.id.asc()).all())
    by_hash = {r.hash: r for r in rows}
    broken = []
    for i, r in enumerate(rows):
        if r.hash != _entry_digest(r, r.prev_hash):
            broken.append({"id": r.id, "at": r.at.isoformat(), "probleme": "contenu modifié après enregistrement"})
        elif r.prev_hash and r.prev_hash not in by_hash and i > 0:  # la plus ancienne entrée restante peut suivre une purge
            broken.append({"id": r.id, "at": r.at.isoformat(), "probleme": "entrée précédente supprimée"})
    return {"entries": len(rows), "intact": not broken, "anomalies": broken[:50]}


# ------------------------------------------------------------------ erreurs techniques
EXPLANATIONS = {
    "api": "Le serveur n'a pas pu traiter la demande. Les informations saisies n'ont pas été modifiées.",
    "sync": "La synchronisation entre ce poste et le serveur central a échoué ; les modifications locales sont conservées et seront renvoyées.",
    "import": "Le fichier n'a pas pu être lu ou analysé. Vérifiez son format et qu'il n'est pas protégé par un mot de passe.",
    "validation": "Une donnée saisie ne respecte pas le format attendu.",
    "calcul": "Un calcul a produit un résultat incohérent ; les montants concernés doivent être vérifiés.",
    "chargement": "Une page ou des données n'ont pas pu être chargées.",
    "base": "La base de données a refusé l'opération (contrainte, verrou ou espace disque).",
    "python": "Erreur interne du serveur ; l'incident a été consigné.",
    "javascript": "Erreur dans l'interface ; rechargez la page. L'incident a été consigné.",
    "document": "La génération du document a échoué.",
    "agenda": "La synchronisation avec l'agenda externe a échoué.",
}
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_ref() -> str:
    return "E-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))


def log_error(db: Session, *, source: str, message: str, severity: str = "erreur", module: str | None = None,
              context: dict | None = None, path: str | None = None, agency_id: str | None = None,
              user_id: str | None = None, explanation: str | None = None) -> ErrorLog:
    e = ErrorLog(ref=new_ref(), source=source, severity=severity, module=module, message=redact(message)[:4000],
                 explanation=explanation or EXPLANATIONS.get(source), context=redact(context or {}), path=(path or "")[:300] or None,
                 agency_id=agency_id, user_id=user_id)
    db.add(e)
    return e


def log_error_isolated(**kw) -> str | None:
    """Enregistre une erreur dans une session indépendante (la transaction en cours a pu échouer)."""
    from ..db import SessionLocal

    try:
        with SessionLocal() as s:
            e = log_error(s, **kw)
            s.commit()
            return e.ref
    except Exception:  # le journal ne doit jamais provoquer d'erreur supplémentaire
        return None


def aware(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
