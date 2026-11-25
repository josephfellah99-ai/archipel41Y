"""Module 07 – Assistant IA intégré et recherche globale."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..crud import create_obj, delete_obj, get_owned, record_change, scoped_query, to_dict
from ..db import get_db, utcnow
from ..models import Client, Company, Conversation, Document, Event, Project, Quote, Task, User
from ..security import check_project_access, require
from ..services import ai as ai_service

router = APIRouter(prefix="/api", tags=["assistant"])


@router.get("/assistant/status")
def status(user: User = Depends(require("read")), db: Session = Depends(get_db)):
    return ai_service.status(db, user.agency_id)


@router.post("/assistant/ask")
def ask(payload: dict, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(422, "Posez une question.")
    if len(question) > 8000:
        raise HTTPException(422, "Question trop longue (8 000 caractères maximum).")
    project_id = payload.get("project_id") or None
    check_project_access(db, user, project_id)
    conv = None
    if payload.get("conversation_id"):
        conv = get_owned(db, Conversation, payload["conversation_id"], user)
        if conv.user_id != user.id:
            raise HTTPException(403, "Conversation d'un autre utilisateur.")
    history = [{"role": m["role"], "content": m["content"]} for m in (conv.messages if conv else [])][-8:]
    res = ai_service.answer(db, user, question, project_id, history)
    now = utcnow().isoformat()
    msgs = list(conv.messages if conv else []) + [
        {"role": "user", "content": question, "at": now},
        {"role": "assistant", "content": res["answer"], "sources": res["sources"], "mode": res["mode"], "at": now}]
    if conv:
        conv.messages = msgs
        conv.version += 1
        record_change(db, conv, "update", user)
    else:
        conv = create_obj(db, Conversation, {"user_id": user.id, "project_id": project_id, "title": question[:80], "messages": msgs}, user)
    db.commit()
    return {**res, "conversation_id": conv.id}


@router.get("/conversations")
def conversations(user: User = Depends(require("read")), db: Session = Depends(get_db)):
    rows = (db.query(Conversation).filter(Conversation.agency_id == user.agency_id, Conversation.user_id == user.id,
                                          Conversation.deleted.is_(False)).order_by(Conversation.updated_at.desc()).limit(100))
    return [{"id": c.id, "title": c.title, "project_id": c.project_id, "updated_at": c.updated_at.isoformat(),
             "count": len(c.messages or [])} for c in rows]


@router.get("/conversations/{cid}")
def conversation(cid: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    c = get_owned(db, Conversation, cid, user)
    if c.user_id != user.id:
        raise HTTPException(403, "Conversation d'un autre utilisateur.")
    return to_dict(c)


@router.delete("/conversations/{cid}")
def delete_conversation(cid: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    c = get_owned(db, Conversation, cid, user)
    if c.user_id != user.id:
        raise HTTPException(403, "Conversation d'un autre utilisateur.")
    delete_obj(db, c, user)
    db.commit()
    return {"ok": True}


@router.get("/search")
def global_search(q: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    """Recherche transversale (archives) : projets, clients, entreprises, devis, tâches, rendez-vous, documents."""
    if len(q.strip()) < 2:
        return {"results": [], "passages": []}
    like = f"%{q.strip()}%"
    out = []
    specs = [
        (Project, "projet", [Project.name, Project.code, Project.city, Project.address], lambda o: f"{o.code} – {o.name}", "/projets/{id}"),
        (Client, "client", [Client.name, Client.email, Client.city], lambda o: o.name, "/annuaire/clients/{id}"),
        (Company, "entreprise", [Company.name, Company.email, Company.city], lambda o: o.name, "/annuaire/entreprises/{id}"),
        (Quote, "devis", [Quote.reference, Quote.company_name_raw], lambda o: f"Devis {o.reference or ''} {o.company_name_raw or ''}", "/devis/{id}"),
        (Task, "tâche", [Task.name], lambda o: o.name, "/planning?project={project_id}"),
        (Event, "rendez-vous", [Event.title, Event.location, Event.minutes], lambda o: f"{o.title} ({o.start:%d/%m/%Y})", "/agenda?event={id}"),
        (Document, "document", [Document.name, Document.description], lambda o: o.name, "/documents?doc={id}"),
    ]
    for model, kind, cols, label, link in specs:
        for o in scoped_query(db, model, user).filter(or_(*[c.ilike(like) for c in cols])).limit(8):
            out.append({"kind": kind, "id": o.id, "label": label(o),
                        "link": link.replace("{id}", o.id).replace("{project_id}", getattr(o, "project_id", "") or "")})
    passages = ai_service.retrieve(db, user, q, None, k=6)
    return {"results": out, "passages": passages}
