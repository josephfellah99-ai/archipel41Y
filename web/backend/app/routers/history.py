"""Historique et activité : journal d'activité, connexions, erreurs techniques, diagnostic, intégrité, conservation.

- Activité : consultable par tous, limitée aux projets et modules autorisés ; complète pour les administrateurs.
- Connexions, erreurs, diagnostic, intégrité et conservation : administrateurs uniquement.
- Aucune route ne permet de modifier une entrée de journal ; seule la purge selon la durée de conservation
  (paramétrée par un administrateur) supprime des entrées anciennes, et elle est elle-même journalisée.
"""
from __future__ import annotations

import csv
import io
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..crud import audit
from ..db import get_db, utcnow
from ..models import AuditLog, ConnectionLog, ErrorLog, Project, User
from ..security import MODULES, accessible_project_ids, get_current_user, module_level, require
from ..services import settings_store
from ..services.journal import aware, log_error, redact, verify_chain

router = APIRouter(prefix="/api/history", tags=["historique"])

ACTION_LABELS = {
    "create": "Création", "update": "Modification", "delete": "Suppression", "login": "Connexion", "login_failed": "Échec de connexion",
    "password_change": "Changement de mot de passe", "setup": "Création de l'agence", "commentaire": "Commentaire",
    "commentaire_modifie": "Commentaire modifié", "commentaire_supprime": "Commentaire supprimé", "invitation_creee": "Invitation créée",
    "invitation_revoquee": "Invitation révoquée", "consultation_invite": "Consultation invité", "invite_demo": "Accès démonstration",
    "validate": "Validation", "import": "Importation", "export": "Exportation", "restore": "Restauration", "backup": "Sauvegarde",
    "purge_journaux": "Purge des journaux", "parametre": "Paramètre modifié", "resolution_erreur": "Erreur résolue",
}
MODULE_LABELS = {**MODULES, "parametres": "Paramètres", "invites": "Accès invités", "equipe": "Équipe et collaboration"}
SEVERITIES = ("info", "avertissement", "erreur", "critique")
RETENTION_DEFAULT = {"activity_days": 1095, "connections_days": 365, "errors_days": 180}
_CLIENT_ERR: dict[str, list[float]] = defaultdict(list)


def _parse_date(v: str | None, end: bool = False) -> datetime | None:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(v)
    except ValueError:
        raise HTTPException(422, f"Date invalide : « {v} » (format attendu AAAA-MM-JJ).")
    if len(v) == 10 and end:
        d = d + timedelta(days=1)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


# ------------------------------------------------------------------ activité
def _activity_query(db: Session, user: User, user_id=None, project_id=None, module=None, action=None, entity=None,
                    date_from=None, date_to=None, q=None, entity_id=None):
    qy = db.query(AuditLog).filter(AuditLog.agency_id == user.agency_id)
    if user.role != "admin":
        allowed = accessible_project_ids(db, user)
        qy = qy.filter(AuditLog.action.in_(["create", "update", "delete", "commentaire", "validate", "import"]))
        qy = qy.filter(~AuditLog.entity.in_(["users", "invitations", "settings", "agencies"]))
        if allowed is not None:
            qy = qy.filter(or_(AuditLog.project_id.is_(None), AuditLog.project_id.in_(allowed or [""])))
        hidden = [m for m in MODULES if module_level(user, m) == "none"]
        if hidden:
            qy = qy.filter(or_(AuditLog.module.is_(None), ~AuditLog.module.in_(hidden)))
    if user_id:
        qy = qy.filter(AuditLog.user_id == user_id)
    if project_id:
        qy = qy.filter(AuditLog.project_id == project_id)
    if module:
        qy = qy.filter(AuditLog.module == module)
    if action:
        qy = qy.filter(AuditLog.action == action)
    if entity:
        qy = qy.filter(AuditLog.entity == entity)
    if entity_id:
        qy = qy.filter(AuditLog.entity_id == entity_id)
    if date_from:
        qy = qy.filter(AuditLog.at >= _parse_date(date_from))
    if date_to:
        qy = qy.filter(AuditLog.at < _parse_date(date_to, end=True))
    if q:
        like = f"%{q.strip()}%"
        qy = qy.filter(or_(AuditLog.summary.ilike(like), AuditLog.actor_label.ilike(like)))
    return qy


def _names(db: Session, agency_id: str):
    users = {u.id: u.full_name for u in db.query(User).filter(User.agency_id == agency_id)}
    projects = {p.id: f"{p.code} – {p.name}" for p in db.query(Project).filter(Project.agency_id == agency_id)}
    return users, projects


def _activity_row(a: AuditLog, users: dict, projects: dict) -> dict:
    return {"id": a.id, "at": a.at.isoformat(), "user_id": a.user_id, "user": users.get(a.user_id) or a.actor_label or "Système",
            "action": a.action, "action_label": ACTION_LABELS.get(a.action, a.action), "module": a.module,
            "module_label": MODULE_LABELS.get(a.module or "", a.module or "—"), "entity": a.entity, "entity_id": a.entity_id,
            "project_id": a.project_id, "project": projects.get(a.project_id), "summary": a.summary, "changes": a.changes,
            "result": a.result or "succes", "ip": a.ip}


@router.get("/activity")
def activity(user_id: str | None = None, project_id: str | None = None, module: str | None = None, action: str | None = None,
             entity: str | None = None, entity_id: str | None = None, date_from: str | None = None, date_to: str | None = None,
             q: str | None = None, page: int = 1, limit: int = 50, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    qy = _activity_query(db, user, user_id, project_id, module, action, entity, date_from, date_to, q, entity_id)
    total = qy.count()
    limit = max(1, min(limit, 200))
    rows = qy.order_by(AuditLog.at.desc(), AuditLog.id.desc()).offset((max(page, 1) - 1) * limit).limit(limit).all()
    users, projects = _names(db, user.agency_id)
    return {"total": total, "page": page, "limit": limit, "items": [_activity_row(a, users, projects) for a in rows],
            "filters": {"actions": ACTION_LABELS, "modules": MODULE_LABELS}}


def _fmt_changes(ch: dict | None) -> str:
    if not ch:
        return ""
    parts = []
    for k, v in ch.items():
        if isinstance(v, dict) and ("avant" in v or "apres" in v):
            parts.append(f"{k} : {_short(v.get('avant'))} → {_short(v.get('apres'))}")
        else:
            parts.append(f"{k} : {_short(v)}")
    return " ; ".join(parts)


def _short(v) -> str:
    s = "—" if v is None or v == "" else str(v)
    return s if len(s) <= 80 else s[:77] + "…"


def _export(rows: list[list], header: list[str], title: str, fmt: str, filename: str) -> Response:
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(header)
        w.writerows(rows)
        return Response(("﻿" + buf.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'})
    if fmt == "pdf":
        from ..services import exports

        data, mime = exports.render("pdf", title, [{"type": "table", "columns": header, "rows": [[str(c) if c is not None else "" for c in r] for r in rows]}],
                                    {"landscape": True})
        return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'})
    raise HTTPException(422, "Format d'export inconnu (csv ou pdf).")


@router.get("/activity/export")
def activity_export(fmt: str = "csv", user_id: str | None = None, project_id: str | None = None, module: str | None = None,
                    action: str | None = None, entity: str | None = None, date_from: str | None = None, date_to: str | None = None,
                    q: str | None = None, request: Request = None, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    qy = _activity_query(db, user, user_id, project_id, module, action, entity, date_from, date_to, q)
    rows = qy.order_by(AuditLog.at.desc()).limit(20000).all()
    users, projects = _names(db, user.agency_id)
    out = [[aware(a.at).astimezone().strftime("%d/%m/%Y %H:%M:%S"), users.get(a.user_id) or a.actor_label or "Système",
            MODULE_LABELS.get(a.module or "", a.module or ""), projects.get(a.project_id, ""), ACTION_LABELS.get(a.action, a.action),
            a.summary or "", _fmt_changes(a.changes), a.result or "succes"] for a in rows]
    audit(db, user, "export", "audit_logs", None, f"Export de l'historique d'activité ({len(out)} lignes, {fmt.upper()})", request, module="parametres")
    db.commit()
    return _export(out, ["Date et heure", "Auteur", "Module", "Projet", "Opération", "Élément", "Ancienne → nouvelle valeur", "Résultat"],
                   "Historique d'activité", fmt, "historique_activite")


# ------------------------------------------------------------------ connexions (administrateurs)
def _conn_query(db: Session, admin: User, user_id=None, kind=None, success=None, date_from=None, date_to=None, q=None):
    qy = db.query(ConnectionLog).filter(or_(ConnectionLog.agency_id == admin.agency_id,
                                            # tentatives sur une adresse inconnue : rattachées à aucune agence, visibles des administrateurs
                                            ConnectionLog.agency_id.is_(None)))
    if user_id:
        qy = qy.filter(ConnectionLog.user_id == user_id)
    if kind:
        qy = qy.filter(ConnectionLog.kind == kind)
    if success is not None:
        qy = qy.filter(ConnectionLog.success.is_(success))
    if date_from:
        qy = qy.filter(ConnectionLog.at >= _parse_date(date_from))
    if date_to:
        qy = qy.filter(ConnectionLog.at < _parse_date(date_to, end=True))
    if q:
        like = f"%{q.strip()}%"
        qy = qy.filter(or_(ConnectionLog.identity.ilike(like), ConnectionLog.ip.ilike(like), ConnectionLog.device.ilike(like)))
    return qy


def _conn_row(c: ConnectionLog, users: dict) -> dict:
    return {"id": c.id, "at": c.at.isoformat(), "user": users.get(c.user_id), "identity": c.identity, "kind": c.kind, "success": c.success,
            "reason": c.reason, "ip": c.ip, "device": c.device, "security_event": c.security_event}


@router.get("/connections")
def connections(user_id: str | None = None, kind: str | None = None, success: bool | None = None, date_from: str | None = None,
                date_to: str | None = None, q: str | None = None, page: int = 1, limit: int = 50,
                admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    qy = _conn_query(db, admin, user_id, kind, success, date_from, date_to, q)
    total = qy.count()
    limit = max(1, min(limit, 200))
    rows = qy.order_by(ConnectionLog.at.desc()).offset((max(page, 1) - 1) * limit).limit(limit).all()
    users, _ = _names(db, admin.agency_id)
    return {"total": total, "items": [_conn_row(c, users) for c in rows]}


@router.get("/connections/export")
def connections_export(fmt: str = "csv", user_id: str | None = None, kind: str | None = None, success: bool | None = None,
                       date_from: str | None = None, date_to: str | None = None, q: str | None = None,
                       admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    rows = _conn_query(db, admin, user_id, kind, success, date_from, date_to, q).order_by(ConnectionLog.at.desc()).limit(20000).all()
    users, _ = _names(db, admin.agency_id)
    out = [[aware(c.at).astimezone().strftime("%d/%m/%Y %H:%M:%S"), users.get(c.user_id) or "", c.identity or "", c.kind,
            "réussie" if c.success else "échouée", c.reason or "", c.device or "", c.ip or "", c.security_event or ""] for c in rows]
    return _export(out, ["Date et heure", "Utilisateur", "Identifiant saisi", "Type", "Résultat", "Motif", "Appareil", "Adresse IP", "Sécurité"],
                   "Historique des connexions", fmt, "historique_connexions")


# ------------------------------------------------------------------ erreurs techniques
def _err_query(db: Session, admin: User, severity=None, source=None, module=None, resolved=None, date_from=None, date_to=None, q=None):
    qy = db.query(ErrorLog).filter(or_(ErrorLog.agency_id == admin.agency_id, ErrorLog.agency_id.is_(None)))
    if severity:
        qy = qy.filter(ErrorLog.severity == severity)
    if source:
        qy = qy.filter(ErrorLog.source == source)
    if module:
        qy = qy.filter(ErrorLog.module == module)
    if resolved is not None:
        qy = qy.filter(ErrorLog.resolved.is_(resolved))
    if date_from:
        qy = qy.filter(ErrorLog.at >= _parse_date(date_from))
    if date_to:
        qy = qy.filter(ErrorLog.at < _parse_date(date_to, end=True))
    if q:
        like = f"%{q.strip()}%"
        qy = qy.filter(or_(ErrorLog.message.ilike(like), ErrorLog.ref.ilike(like), ErrorLog.path.ilike(like)))
    return qy


def _err_row(e: ErrorLog, users: dict, full: bool = False) -> dict:
    d = {"id": e.id, "ref": e.ref, "at": e.at.isoformat(), "severity": e.severity, "source": e.source, "module": e.module,
         "module_label": MODULE_LABELS.get(e.module or "", e.module), "message": e.message, "explanation": e.explanation,
         "path": e.path, "user": users.get(e.user_id), "resolved": e.resolved}
    if full:
        d["context"] = e.context
    return d


@router.get("/errors")
def errors(severity: str | None = None, source: str | None = None, module: str | None = None, resolved: bool | None = None,
           date_from: str | None = None, date_to: str | None = None, q: str | None = None, page: int = 1, limit: int = 50,
           admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    qy = _err_query(db, admin, severity, source, module, resolved, date_from, date_to, q)
    total = qy.count()
    limit = max(1, min(limit, 200))
    rows = qy.order_by(ErrorLog.at.desc()).offset((max(page, 1) - 1) * limit).limit(limit).all()
    users, _ = _names(db, admin.agency_id)
    return {"total": total, "items": [_err_row(e, users) for e in rows]}


@router.get("/errors/export")
def errors_export(fmt: str = "csv", severity: str | None = None, source: str | None = None, module: str | None = None,
                  resolved: bool | None = None, date_from: str | None = None, date_to: str | None = None, q: str | None = None,
                  admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    rows = _err_query(db, admin, severity, source, module, resolved, date_from, date_to, q).order_by(ErrorLog.at.desc()).limit(20000).all()
    users, _ = _names(db, admin.agency_id)
    out = [[e.ref, aware(e.at).astimezone().strftime("%d/%m/%Y %H:%M:%S"), e.severity, e.source, MODULE_LABELS.get(e.module or "", e.module or ""),
            e.message, e.explanation or "", e.path or "", users.get(e.user_id) or "", "oui" if e.resolved else "non"] for e in rows]
    return _export(out, ["Référence", "Date et heure", "Gravité", "Origine", "Module", "Message technique", "Explication", "Chemin", "Utilisateur", "Résolue"],
                   "Journal technique des erreurs", fmt, "journal_erreurs")


@router.get("/errors/{ref}")
def error_detail(ref: str, admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    e = db.query(ErrorLog).filter(ErrorLog.ref == ref.upper(), or_(ErrorLog.agency_id == admin.agency_id, ErrorLog.agency_id.is_(None))).first()
    if not e:
        raise HTTPException(404, "Référence d'erreur introuvable.")
    users, _ = _names(db, admin.agency_id)
    d = _err_row(e, users, full=True)
    # événements proches (même utilisateur, ± 10 min) pour retrouver l'origine
    near = (db.query(AuditLog).filter(AuditLog.agency_id == admin.agency_id, AuditLog.at >= e.at - timedelta(minutes=10),
                                      AuditLog.at <= e.at + timedelta(minutes=2))
            .filter(AuditLog.user_id == e.user_id if e.user_id else True).order_by(AuditLog.at.desc()).limit(15).all())
    _, projects = _names(db, admin.agency_id)
    d["related_activity"] = [_activity_row(a, users, projects) for a in near]
    return d


@router.post("/errors/{ref}/resolve")
def resolve_error(ref: str, request: Request, admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    e = db.query(ErrorLog).filter(ErrorLog.ref == ref.upper(), or_(ErrorLog.agency_id == admin.agency_id, ErrorLog.agency_id.is_(None))).first()
    if not e:
        raise HTTPException(404, "Référence d'erreur introuvable.")
    e.resolved = True
    audit(db, admin, "resolution_erreur", "error_logs", e.id, f"Erreur {e.ref} marquée résolue", request, module="parametres")
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ erreurs de l'interface (JavaScript)
@router.post("/client-errors", status_code=202)
def client_error(payload: dict, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Erreurs JavaScript remontées par l'interface (limitées à 20 par minute et par utilisateur)."""
    now = time.time()
    _CLIENT_ERR[user.id] = [t for t in _CLIENT_ERR[user.id] if now - t < 60]
    if len(_CLIENT_ERR[user.id]) >= 20:
        return {"ok": False, "ref": None}
    _CLIENT_ERR[user.id].append(now)
    kind = payload.get("kind") if payload.get("kind") in ("javascript", "chargement", "api", "validation", "sync") else "javascript"
    from ..security import module_for_path

    route = str(payload.get("route") or "")[:200]
    mod = {"/finances": "finances", "/devis": "devis", "/comparatifs": "devis", "/agenda": "agenda", "/planning": "planning",
           "/documents": "documents", "/terrain": "terrain", "/urbanisme": "terrain", "/annuaire": "annuaire", "/projets": "projets",
           "/chantiers": "projets", "/equipe": "equipe", "/assistant": "assistant", "/rapports": "rapports"}
    module = next((m for prefix, m in mod.items() if route.startswith(prefix)), None) or module_for_path(str(payload.get("api") or ""))
    e = log_error(db, source=kind, severity="erreur" if kind == "javascript" else "avertissement", module=module,
                  message=str(payload.get("message") or "Erreur inconnue")[:2000],
                  context=redact({"stack": str(payload.get("stack") or "")[:4000], "route": route, "api": payload.get("api"),
                                  "status": payload.get("status"), "navigateur": (request.headers.get("user-agent") or "")[:200],
                                  "ecran": payload.get("screen")}),
                  path=route, agency_id=user.agency_id, user_id=user.id)
    db.commit()
    return {"ok": True, "ref": e.ref}


# ------------------------------------------------------------------ diagnostic
@router.get("/diagnostic")
def diagnostic(admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    now = utcnow()
    day, week = now - timedelta(days=1), now - timedelta(days=7)
    scope = or_(ErrorLog.agency_id == admin.agency_id, ErrorLog.agency_id.is_(None))
    errs7 = db.query(ErrorLog).filter(scope, ErrorLog.at >= week).all()
    by_sev = Counter(e.severity for e in errs7)
    by_src = Counter(e.source for e in errs7)
    by_mod = Counter(MODULE_LABELS.get(e.module or "", e.module or "non déterminé") for e in errs7)
    daily = Counter(aware(e.at).date().isoformat() for e in errs7)
    conn = db.query(ConnectionLog).filter(or_(ConnectionLog.agency_id == admin.agency_id, ConnectionLog.agency_id.is_(None)), ConnectionLog.at >= week).all()
    sec = [c for c in conn if c.security_event or not c.success]
    s = get_settings()
    disk = None
    try:
        import shutil

        du = shutil.disk_usage(s.data_dir)
        disk = {"total_go": round(du.total / 1e9, 1), "libre_go": round(du.free / 1e9, 1), "libre_pct": round(du.free / du.total * 100)}
    except Exception:
        pass
    backup = settings_store.get(db, admin.agency_id, "backup")
    sync = settings_store.get_public(db, admin.agency_id, "sync")
    integrity = verify_chain(db, admin.agency_id)
    alerts = []
    if by_sev.get("critique"):
        alerts.append({"tone": "danger", "message": f"{by_sev['critique']} erreur(s) critique(s) cette semaine."})
    if disk and disk["libre_pct"] < 10:
        alerts.append({"tone": "danger", "message": f"Espace disque faible : {disk['libre_go']} Go libres."})
    if not integrity["intact"]:
        alerts.append({"tone": "danger", "message": "Intégrité du journal d'activité : anomalies détectées (voir l'onglet Intégrité)."})
    lb = backup.get("last_backup_at")
    if not lb or aware(datetime.fromisoformat(lb)) < now - timedelta(days=7):
        alerts.append({"tone": "warn", "message": "Aucune sauvegarde depuis plus de 7 jours."})
    fails = sum(1 for c in conn if not c.success and c.at >= day)
    if fails >= 10:
        alerts.append({"tone": "warn", "message": f"{fails} échecs de connexion en 24 heures."})
    if sync.get("last_error"):
        alerts.append({"tone": "warn", "message": f"Dernière synchronisation en erreur : {sync['last_error']}"})
    return {
        "errors_24h": sum(1 for e in errs7 if aware(e.at) >= day), "errors_7d": len(errs7), "unresolved": sum(1 for e in errs7 if not e.resolved),
        "by_severity": {k: by_sev.get(k, 0) for k in SEVERITIES}, "by_source": dict(by_src.most_common()), "by_module": dict(by_mod.most_common(8)),
        "daily": [{"date": (now - timedelta(days=i)).date().isoformat(), "n": daily.get((now - timedelta(days=i)).date().isoformat(), 0)} for i in range(6, -1, -1)],
        "connections_7d": len(conn), "failed_logins_7d": sum(1 for c in conn if not c.success),
        "security_events": [_conn_row(c, _names(db, admin.agency_id)[0]) for c in sorted(sec, key=lambda c: c.at, reverse=True)[:10]],
        "disk": disk, "database": "SQLite" if s.is_sqlite else "PostgreSQL", "last_backup_at": lb,
        "last_sync_at": sync.get("last_sync_at"), "sync_configured": bool(sync.get("enabled")), "integrity": integrity, "alerts": alerts,
        "retention": {**RETENTION_DEFAULT, **(settings_store.get(db, admin.agency_id, "journal") or {})},
    }


@router.get("/integrity")
def integrity(admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    return verify_chain(db, admin.agency_id)


# ------------------------------------------------------------------ conservation
@router.put("/retention")
def set_retention(payload: dict, request: Request, admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    cur = {**RETENTION_DEFAULT, **(settings_store.get(db, admin.agency_id, "journal") or {})}
    new = dict(cur)
    for k, lo in (("activity_days", 90), ("connections_days", 30), ("errors_days", 30)):
        if k in payload:
            try:
                v = int(payload[k])
            except (TypeError, ValueError):
                raise HTTPException(422, f"{k} : nombre de jours attendu.")
            if not lo <= v <= 3650:
                raise HTTPException(422, f"Durée de conservation entre {lo} jours et 10 ans.")
            new[k] = v
    settings_store.put(db, admin.agency_id, "journal", new)
    audit(db, admin, "parametre", "settings", None, "Durées de conservation des journaux", request, module="parametres",
          changes={k: {"avant": cur[k], "apres": new[k]} for k in new if cur.get(k) != new[k]})
    db.commit()
    return new


def purge(db: Session, agency_id: str, actor: User | None = None) -> dict:
    ret = {**RETENTION_DEFAULT, **(settings_store.get(db, agency_id, "journal") or {})}
    now = utcnow()
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SET LOCAL archipel.allow_log_purge = 'on'"))
    n_a = db.query(AuditLog).filter(AuditLog.agency_id == agency_id, AuditLog.at < now - timedelta(days=ret["activity_days"])).delete(synchronize_session=False)
    n_c = db.query(ConnectionLog).filter(ConnectionLog.agency_id == agency_id, ConnectionLog.at < now - timedelta(days=ret["connections_days"])).delete(synchronize_session=False)
    n_e = db.query(ErrorLog).filter(ErrorLog.agency_id == agency_id, ErrorLog.at < now - timedelta(days=ret["errors_days"])).delete(synchronize_session=False)
    if n_a or n_c or n_e:
        audit(db, actor, "purge_journaux", "audit_logs", None, f"Purge selon la durée de conservation : {n_a} activité(s), {n_c} connexion(s), {n_e} erreur(s)",
              module="parametres") if actor else None
    return {"activity": n_a, "connections": n_c, "errors": n_e}


@router.post("/purge")
def purge_now(admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    res = purge(db, admin.agency_id, admin)
    db.commit()
    return res
