"""Espace collaboratif : équipe, notifications, commentaires et activité récente."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..crud import audit, check_project_access, to_dict
from ..db import get_db, utcnow
from ..models import AuditLog, Comment, Document, Event, Notification, Project, Task, User
from ..security import ROLE_LABELS, accessible_project_ids, get_current_user, module_level, require
from ..services.collab import entity_label, mentions_in, notify_comment

router = APIRouter(prefix="/api", tags=["collaboration"])

COMMENTABLE = {"projects": Project, "documents": Document, "tasks": Task, "events": Event}


# ------------------------------------------------------------------ notifications
@router.get("/notifications")
def my_notifications(unread: bool = False, limit: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Notification).filter(Notification.user_id == user.id, Notification.agency_id == user.agency_id,
                                      Notification.deleted.is_(False))
    if unread:
        q = q.filter(Notification.read_at.is_(None))
    rows = q.order_by(Notification.created_at.desc()).limit(min(limit, 200)).all()
    names = {u.id: u.full_name for u in db.query(User).filter(User.agency_id == user.agency_id)}
    unread_n = db.query(func.count(Notification.id)).filter(Notification.user_id == user.id, Notification.read_at.is_(None),
                                                             Notification.deleted.is_(False)).scalar()
    return {"unread": unread_n, "items": [{**to_dict(n), "actor": names.get(n.actor_id)} for n in rows]}


@router.post("/notifications/read")
def mark_read(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Notification).filter(Notification.user_id == user.id, Notification.read_at.is_(None))
    ids = payload.get("ids")
    if ids:
        q = q.filter(Notification.id.in_(ids))
    n = 0
    for x in q:
        x.read_at = utcnow()
        n += 1
    db.commit()
    return {"ok": True, "marked": n}


# ------------------------------------------------------------------ commentaires
def _target(db: Session, user: User, entity: str, entity_id: str):
    model = COMMENTABLE.get(entity)
    if not model:
        raise HTTPException(422, "Type d'élément non commentable.")
    obj = db.get(model, entity_id)
    if not obj or obj.agency_id != user.agency_id or obj.deleted:
        raise HTTPException(404, "Élément introuvable.")
    pid = obj.id if model is Project else getattr(obj, "project_id", None)
    check_project_access(db, user, pid)
    if entity == "documents" and module_level(user, "documents") == "none":
        raise HTTPException(403, "Accès aux documents non autorisé.")
    return obj, pid


def _comment_out(c: Comment, me: User) -> dict:
    d = to_dict(c)
    d["mine"] = c.author_id == me.id
    return d


@router.get("/comments")
def list_comments(entity: str, entity_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    _target(db, user, entity, entity_id)
    rows = db.query(Comment).filter(Comment.agency_id == user.agency_id, Comment.entity == entity, Comment.entity_id == entity_id,
                                    Comment.deleted.is_(False)).order_by(Comment.created_at).all()
    return [_comment_out(c, user) for c in rows]


@router.post("/comments", status_code=201)
def add_comment(payload: dict, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    body = str(payload.get("body") or "").strip()
    if not body:
        raise HTTPException(422, "Le commentaire est vide.")
    if len(body) > 5000:
        raise HTTPException(422, "Le commentaire ne doit pas dépasser 5 000 caractères.")
    entity, entity_id = str(payload.get("entity") or ""), str(payload.get("entity_id") or "")
    _, pid = _target(db, user, entity, entity_id)
    mentions = mentions_in(db, user.agency_id, body)
    c = Comment(agency_id=user.agency_id, project_id=pid, entity=entity, entity_id=entity_id, author_id=user.id,
                author_name=user.full_name, body=body, mentions=mentions, updated_by=user.id, version=1)
    db.add(c)
    db.flush()
    from ..crud import record_change

    record_change(db, c, "create", user)
    audit(db, user, "commentaire", entity, entity_id, f"Commentaire sur {entity_label(db, entity, entity_id)}", request, project_id=pid)
    notify_comment(db, c, user)
    db.commit()
    return _comment_out(c, user)


@router.put("/comments/{cid}")
def edit_comment(cid: str, payload: dict, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    c = db.get(Comment, cid)
    if not c or c.agency_id != user.agency_id or c.deleted:
        raise HTTPException(404, "Commentaire introuvable.")
    if c.author_id != user.id:
        raise HTTPException(403, "Seul l'auteur peut modifier son commentaire.")
    body = str(payload.get("body") or "").strip()
    if not body:
        raise HTTPException(422, "Le commentaire est vide.")
    old = c.body
    c.body, c.edited, c.version, c.updated_at = body, True, c.version + 1, utcnow()
    audit(db, user, "commentaire_modifie", c.entity, c.entity_id, "Commentaire modifié", request, project_id=c.project_id,
          changes={"texte": {"avant": old, "apres": body}})
    db.commit()
    return _comment_out(c, user)


@router.delete("/comments/{cid}")
def delete_comment(cid: str, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    c = db.get(Comment, cid)
    if not c or c.agency_id != user.agency_id or c.deleted:
        raise HTTPException(404, "Commentaire introuvable.")
    if c.author_id != user.id and user.role != "admin":
        raise HTTPException(403, "Seul l'auteur ou un administrateur peut supprimer ce commentaire.")
    c.deleted, c.version = True, c.version + 1
    audit(db, user, "commentaire_supprime", c.entity, c.entity_id, f"Commentaire de {c.author_name} supprimé", request,
          project_id=c.project_id, changes={"texte": {"avant": c.body, "apres": None}})
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ équipe
def _visible_projects(db: Session, viewer: User) -> list[Project]:
    allowed = accessible_project_ids(db, viewer)
    q = db.query(Project).filter(Project.agency_id == viewer.agency_id, Project.deleted.is_(False))
    if allowed is not None:
        q = q.filter(Project.id.in_(allowed or [""]))
    return q.all()


@router.get("/team")
def team(user: User = Depends(require("read")), db: Session = Depends(get_db)):
    users = db.query(User).filter(User.agency_id == user.agency_id, User.deleted.is_(False)).order_by(User.full_name).all()
    projects = _visible_projects(db, user)
    open_tasks = dict(db.query(Task.responsible_id, func.count(Task.id)).filter(
        Task.agency_id == user.agency_id, Task.deleted.is_(False), Task.progress < 100, Task.responsible_id.isnot(None),
        Task.project_id.in_([p.id for p in projects] or [""])).group_by(Task.responsible_id).all())
    out = []
    for u in users:
        mine = [p for p in projects if any(m.get("user_id") == u.id for m in (p.team or []))]
        out.append({"id": u.id, "full_name": u.full_name, "email": u.email, "phone": u.phone, "job_title": u.job_title,
                    "role": u.role, "role_label": ROLE_LABELS.get(u.role, u.role), "color": u.color, "active": u.active,
                    "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                    "projects": [{"id": p.id, "code": p.code, "name": p.name,
                                  "role": next((m.get("role") for m in p.team if m.get("user_id") == u.id), None)} for p in mine],
                    "open_tasks": open_tasks.get(u.id, 0)})
    return out


@router.get("/team/{user_id}")
def member(user_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u or u.agency_id != user.agency_id or u.deleted:
        raise HTTPException(404, "Collaborateur introuvable.")
    projects = _visible_projects(db, user)
    pids = [p.id for p in projects]
    tasks = db.query(Task).filter(Task.agency_id == user.agency_id, Task.deleted.is_(False), Task.responsible_id == u.id,
                                  Task.project_id.in_(pids or [""])).order_by(Task.start_date).all()
    pname = {p.id: f"{p.code} – {p.name}" for p in projects}
    acts = (db.query(AuditLog).filter(AuditLog.agency_id == user.agency_id, AuditLog.user_id == u.id,
                                      AuditLog.action.in_(["create", "update", "delete", "commentaire"]))
            .order_by(AuditLog.at.desc()).limit(200).all())
    acts = [a for a in acts if not a.project_id or a.project_id in pname][:30]
    return {"id": u.id, "full_name": u.full_name, "email": u.email, "phone": u.phone, "job_title": u.job_title,
            "role_label": ROLE_LABELS.get(u.role, u.role), "color": u.color, "active": u.active,
            "projects": [{"id": p.id, "label": pname[p.id]} for p in projects if any(m.get("user_id") == u.id for m in (p.team or []))],
            "tasks": [{"id": t.id, "name": t.name, "project": pname.get(t.project_id), "start_date": t.start_date.isoformat() if t.start_date else None,
                       "duration_days": t.duration_days, "progress": t.progress} for t in tasks],
            "activity": [{"at": a.at.isoformat(), "action": a.action, "entity": a.entity, "summary": a.summary,
                          "project": pname.get(a.project_id)} for a in acts]}


@router.get("/team/activity/recent")
def recent_activity(days: int = 14, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    """Activité récente visible par l'utilisateur (projets autorisés uniquement)."""
    since = utcnow() - timedelta(days=max(1, min(days, 90)))
    allowed = accessible_project_ids(db, user)
    rows = (db.query(AuditLog).filter(AuditLog.agency_id == user.agency_id, AuditLog.at >= since,
                                      AuditLog.action.in_(["create", "update", "delete", "commentaire", "invitation_creee"]))
            .order_by(AuditLog.at.desc()).limit(400).all())
    names = {u.id: u.full_name for u in db.query(User).filter(User.agency_id == user.agency_id)}
    out = []
    for a in rows:
        if a.project_id and allowed is not None and a.project_id not in allowed:
            continue
        if a.module and a.module in ("finances", "devis", "documents", "agenda", "planning", "annuaire") and module_level(user, a.module) == "none":
            continue
        if a.entity in ("users", "invitations", "settings") and user.role != "admin":
            continue
        out.append({"at": a.at.isoformat(), "user": names.get(a.user_id, a.actor_label or "—"), "action": a.action,
                    "entity": a.entity, "module": a.module, "summary": a.summary, "project_id": a.project_id})
        if len(out) >= 60:
            break
    return out


# ------------------------------------------------------------------ chantiers
@router.get("/chantiers")
def chantiers(all: bool = False, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    """Vue d'ensemble des chantiers : avancement, phase, incidents ouverts, tâches en retard, prochaine visite."""
    from datetime import date as _date

    from ..models import Incident

    projects = [p for p in _visible_projects(db, user) if all or p.status in ("chantier", "reception")]
    today = _date.today()
    out = []
    for p in sorted(projects, key=lambda x: (x.status != "chantier", x.code)):
        incidents = db.query(Incident).filter(Incident.project_id == p.id, Incident.deleted.is_(False), Incident.status != "clos").all()
        tasks = db.query(Task).filter(Task.project_id == p.id, Task.deleted.is_(False)).all()
        late = [t for t in tasks if t.start_date and t.progress < 100 and (t.start_date + timedelta(days=t.duration_days or 0)) < today]
        upcoming = sorted([t for t in tasks if t.progress < 100 and t.start_date and t.start_date >= today], key=lambda t: t.start_date)[:3]
        nxt = None
        if module_level(user, "agenda") != "none":
            ev = (db.query(Event).filter(Event.project_id == p.id, Event.deleted.is_(False), Event.start >= utcnow())
                  .order_by(Event.start).first())
            nxt = {"title": ev.title, "start": ev.start.isoformat(), "location": ev.location} if ev else None
        out.append({"id": p.id, "code": p.code, "name": p.name, "status": p.status, "city": p.city, "progress": p.progress,
                    "current_phase": p.current_phase, "color": getattr(p, "color", None),
                    "incidents": len(incidents), "incidents_graves": sum(1 for i in incidents if i.severity in ("haute", "critique")),
                    "tasks": len(tasks), "late": [{"name": t.name, "start_date": t.start_date.isoformat()} for t in late[:5]], "late_count": len(late),
                    "upcoming": [{"name": t.name, "start_date": t.start_date.isoformat()} for t in upcoming], "next_event": nxt})
    return out
