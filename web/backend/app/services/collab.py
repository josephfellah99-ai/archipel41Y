"""Collaboration : notifications et destinataires.

Une notification est créée lorsqu'un collaborateur :
- ajoute un document ou en dépose une nouvelle version ;
- termine une tâche (avancement 100 %) ;
- ajoute un commentaire (avec mention @) ;
- modifie une information importante d'un projet (statut, phase, budget, dates, équipe) ;
- attribue une tâche ou ajoute quelqu'un à l'équipe d'un projet.

Destinataires : l'équipe du projet (et les personnes explicitement concernées), jamais l'auteur de
l'action, jamais une personne qui n'a pas accès au projet (projets confidentiels, autorisations fines).
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from ..models import Comment, Document, Notification, Project, Task, User
from ..security import accessible_project_ids, module_level

IMPORTANT_PROJECT_FIELDS = {"status": "statut", "current_phase": "phase en cours", "budget_initial": "budget",
                            "start_date": "date de début", "end_date": "date de fin", "confidential": "confidentialité",
                            "client_id": "maître d'ouvrage"}


def _users(db: Session, agency_id: str) -> list[User]:
    return db.query(User).filter(User.agency_id == agency_id, User.deleted.is_(False), User.active.is_(True)).all()


def can_see(db: Session, user: User, project_id: str | None, module: str | None = None) -> bool:
    if module and module_level(user, module) == "none":
        return False
    if not project_id:
        return True
    allowed = accessible_project_ids(db, user)
    return allowed is None or project_id in allowed


def project_team_ids(db: Session, project_id: str | None) -> set[str]:
    if not project_id:
        return set()
    p = db.get(Project, project_id)
    return {m.get("user_id") for m in (p.team or []) if m.get("user_id")} if p else set()


def notify(db: Session, agency_id: str, user_ids, *, kind: str, title: str, body: str | None = None, link: str | None = None,
           project_id: str | None = None, actor_id: str | None = None, module: str | None = None) -> int:
    ids = {u for u in user_ids if u and u != actor_id}
    if not ids:
        return 0
    n = 0
    for u in _users(db, agency_id):
        if u.id not in ids or not can_see(db, u, project_id, module):
            continue
        prefs = (u.preferences or {}).get("notifications") or {}
        if prefs.get(kind) is False:
            continue  # l'utilisateur a désactivé ce type de notification
        db.add(Notification(agency_id=agency_id, user_id=u.id, kind=kind, title=title[:300], body=(body or "")[:2000] or None,
                            link=link, project_id=project_id, actor_id=actor_id, version=1))
        n += 1
    return n


def _actor_name(db: Session, actor) -> str:
    if actor is None:
        return "Un invité"
    return getattr(actor, "full_name", None) or "Un collaborateur"


def mentions_in(db: Session, agency_id: str, text: str) -> list[str]:
    """Repère les mentions « @Prénom Nom » ou « @prenom.nom » parmi les collaborateurs de l'agence."""
    found = []
    low = (text or "").lower()
    for u in _users(db, agency_id):
        handles = {"@" + u.full_name.lower(), "@" + u.full_name.lower().replace(" ", "."), "@" + u.email.split("@")[0].lower()}
        first = u.full_name.split(" ")[0].lower()
        if any(h in low for h in handles) or re.search(rf"@{re.escape(first)}\b", low):
            found.append(u.id)
    return found


def entity_link(entity: str, entity_id: str, project_id: str | None) -> str:
    return {"projects": f"/projets/{entity_id}", "documents": f"/documents?doc={entity_id}", "tasks": "/planning",
            "events": "/agenda", "quotes": f"/devis/{entity_id}"}.get(entity, f"/projets/{project_id}" if project_id else "/")


def entity_label(db: Session, entity: str, entity_id: str) -> str:
    from ..models import Event, Quote

    model = {"projects": Project, "documents": Document, "tasks": Task, "events": Event, "quotes": Quote}.get(entity)
    obj = db.get(model, entity_id) if model else None
    for attr in ("name", "title", "reference", "code"):
        if obj is not None and getattr(obj, attr, None):
            return str(getattr(obj, attr))
    return "élément"


def notify_comment(db: Session, c: Comment, actor, extra_recipients: set[str] | None = None) -> int:
    label = entity_label(db, c.entity, c.entity_id)
    recipients = set(project_team_ids(db, c.project_id)) | set(c.mentions or []) | set(extra_recipients or [])
    # participants précédents de la discussion
    for (aid,) in db.query(Comment.author_id).filter(Comment.entity == c.entity, Comment.entity_id == c.entity_id,
                                                     Comment.author_id.isnot(None)).distinct():
        recipients.add(aid)
    n = 0
    mentioned = set(c.mentions or [])
    if mentioned:
        n += notify(db, c.agency_id, mentioned, kind="mention", title=f"{_actor_name(db, actor)} vous a mentionné(e) — {label}",
                    body=c.body[:300], link=entity_link(c.entity, c.entity_id, c.project_id), project_id=c.project_id,
                    actor_id=getattr(actor, "id", None))
    n += notify(db, c.agency_id, recipients - mentioned, kind="commentaire", title=f"Nouveau commentaire — {label}",
                body=f"{c.author_name} : {c.body[:280]}", link=entity_link(c.entity, c.entity_id, c.project_id),
                project_id=c.project_id, actor_id=getattr(actor, "id", None))
    return n


# ------------------------------------------------------------------ déclencheurs appelés par crud.py et les routeurs
def on_change(db: Session, obj, action: str, user, changes: dict | None = None) -> None:
    """Notifications métier déclenchées par la création / modification d'une entité."""
    try:
        _on_change(db, obj, action, user, changes or {})
    except Exception:  # une notification ne doit jamais faire échouer l'enregistrement
        import logging

        logging.getLogger("archipel41").exception("Notification non créée")


def _on_change(db: Session, obj, action: str, user, changes: dict) -> None:
    actor_id = getattr(user, "id", None)
    who = _actor_name(db, user)
    if isinstance(obj, Document):
        if action == "create":
            notify(db, obj.agency_id, project_team_ids(db, obj.project_id), kind="document_ajoute",
                   title=f"Document ajouté : {obj.name}", body=f"{who} a ajouté « {obj.name} ».", link=f"/documents?doc={obj.id}",
                   project_id=obj.project_id, actor_id=actor_id, module="documents")
        elif action == "update" and changes and set(changes) - {"text_status", "page_count", "size"}:
            fields = ", ".join(sorted(set(changes) - {"text_status", "page_count", "size"}))
            notify(db, obj.agency_id, project_team_ids(db, obj.project_id), kind="document_modifie",
                   title=f"Document modifié : {obj.name}", body=f"{who} a modifié : {fields}.", link=f"/documents?doc={obj.id}",
                   project_id=obj.project_id, actor_id=actor_id, module="documents")
    elif isinstance(obj, Task):
        link = "/planning"
        if "progress" in changes and (changes["progress"].get("apres") or 0) >= 100 > (changes["progress"].get("avant") or 0):
            notify(db, obj.agency_id, project_team_ids(db, obj.project_id) | {obj.responsible_id}, kind="tache_terminee",
                   title=f"Tâche terminée : {obj.name}", body=f"{who} a terminé « {obj.name} ».", link=link,
                   project_id=obj.project_id, actor_id=actor_id, module="planning")
        newresp = obj.responsible_id if action == "create" else (changes.get("responsible_id") or {}).get("apres")
        if newresp:
            notify(db, obj.agency_id, {newresp}, kind="attribution", title=f"Tâche attribuée : {obj.name}",
                   body=f"{who} vous a attribué « {obj.name} »" + (f" (début le {obj.start_date:%d/%m/%Y})." if obj.start_date else "."),
                   link=link, project_id=obj.project_id, actor_id=actor_id, module="planning")
    elif isinstance(obj, Project):
        if action == "update":
            important = [IMPORTANT_PROJECT_FIELDS[k] for k in changes if k in IMPORTANT_PROJECT_FIELDS]
            if important:
                notify(db, obj.agency_id, project_team_ids(db, obj.id), kind="projet_modifie",
                       title=f"Projet {obj.code} modifié", body=f"{who} a modifié : {', '.join(important)}.",
                       link=f"/projets/{obj.id}", project_id=obj.id, actor_id=actor_id, module="projets")
            if "team" in changes:
                before = {m.get("user_id") for m in (changes["team"].get("avant") or [])}
                after = {m.get("user_id") for m in (changes["team"].get("apres") or [])}
                notify(db, obj.agency_id, after - before, kind="attribution", title=f"Vous rejoignez le projet {obj.code}",
                       body=f"{who} vous a ajouté(e) à l'équipe du projet « {obj.name} ».", link=f"/projets/{obj.id}",
                       project_id=obj.id, actor_id=actor_id, module="projets")
        elif action == "create" and obj.team:
            notify(db, obj.agency_id, {m.get("user_id") for m in obj.team}, kind="attribution",
                   title=f"Nouveau projet {obj.code}", body=f"{who} vous a ajouté(e) à l'équipe du projet « {obj.name} ».",
                   link=f"/projets/{obj.id}", project_id=obj.id, actor_id=actor_id, module="projets")
