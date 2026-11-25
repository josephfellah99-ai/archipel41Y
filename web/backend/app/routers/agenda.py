"""Module 04 – Agenda et rendez-vous."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ai.prompts import load as load_prompt

from ..crud import create_obj, delete_obj, get_owned, scoped_query, to_dict, update_obj
from ..db import get_db, utcnow
from ..models import Event, Project, User
from ..schemas import EventIn
from ..security import require
from ..services import ai as ai_service

router = APIRouter(prefix="/api/events", tags=["agenda"])


def _dt(v: str) -> datetime:
    d = datetime.fromisoformat(v.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _keys(participants: list[dict]) -> set[str]:
    out = set()
    for p in participants or []:
        if p.get("user_id"):
            out.add("u:" + p["user_id"])
        elif p.get("email"):
            out.add("e:" + p["email"].lower())
        elif p.get("name"):
            out.add("n:" + p["name"].strip().lower())
    return out


def find_conflicts(db: Session, user: User, start: datetime, end: datetime, participants: list[dict],
                   organizer_id: str | None, exclude_id: str | None = None) -> list[dict]:
    keys = _keys(participants)
    if organizer_id:
        keys.add("u:" + organizer_id)
    if not keys:
        return []
    rows = (db.query(Event).filter(Event.agency_id == user.agency_id, Event.deleted.is_(False),
                                   Event.start < end, Event.end > start).all())
    names = {u.id: u.full_name for u in db.query(User).filter(User.agency_id == user.agency_id)}
    out = []
    for e in rows:
        if e.id == exclude_id:
            continue
        ek = _keys(e.participants)
        if e.organizer_id:
            ek.add("u:" + e.organizer_id)
        common = keys & ek
        if common:
            who = [names.get(k[2:], k[2:]) if k.startswith("u:") else k[2:] for k in common]
            out.append({"event_id": e.id, "title": e.title, "start": e.start.isoformat(), "end": e.end.isoformat(),
                        "participants": sorted(who)})
    return out


@router.get("")
def list_events(start: str | None = None, end: str | None = None, project_id: str | None = None,
                participant: str | None = None, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    q = scoped_query(db, Event, user)
    if start:
        q = q.filter(Event.end >= _dt(start))
    if end:
        q = q.filter(Event.start <= _dt(end))
    if project_id:
        q = q.filter(Event.project_id == project_id)
    rows = q.order_by(Event.start).limit(3000).all()
    if participant:
        rows = [e for e in rows if e.organizer_id == participant or any(p.get("user_id") == participant for p in e.participants or [])]
    return [to_dict(e) for e in rows]


@router.post("/check")
def check(payload: dict, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    return find_conflicts(db, user, _dt(payload["start"]), _dt(payload["end"]), payload.get("participants") or [],
                          payload.get("organizer_id"), payload.get("exclude_id"))


@router.get("/reminders")
def reminders(minutes_ahead: int = 60 * 24, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    """Rendez-vous dont le rappel tombe maintenant (pour les notifications du poste)."""
    now = utcnow()
    rows = (db.query(Event).filter(Event.agency_id == user.agency_id, Event.deleted.is_(False),
                                   Event.start >= now, Event.start <= now + timedelta(minutes=minutes_ahead),
                                   Event.reminder_minutes.isnot(None)).all())
    out = []
    for e in rows:
        mine = e.organizer_id == user.id or any(p.get("user_id") == user.id for p in e.participants or [])
        if mine and e.start - timedelta(minutes=e.reminder_minutes or 0) <= now:
            out.append({"id": e.id, "title": e.title, "start": e.start.isoformat(), "location": e.location,
                        "reminder_key": f"{e.id}:{e.version}"})
    return out


@router.get("/{event_id}")
def get_event(event_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    return to_dict(get_owned(db, Event, event_id, user))


@router.post("", status_code=201)
def create_event(payload: EventIn, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["organizer_id"] = data.get("organizer_id") or user.id
    cid = request.headers.get("x-client-id")
    if cid and len(cid) == 36:
        existing = db.get(Event, cid)
        if existing:
            return {"event": to_dict(existing), "conflicts": []}
        data["id"] = cid
    conflicts = find_conflicts(db, user, payload.start, payload.end, data["participants"], data["organizer_id"])
    e = create_obj(db, Event, data, user, request)
    db.commit()
    return {"event": to_dict(e), "conflicts": conflicts}


@router.put("/{event_id}")
def update_event(event_id: str, payload: dict, request: Request, user: User = Depends(require("write")),
                 db: Session = Depends(get_db)):
    e = get_owned(db, Event, event_id, user)
    version = payload.pop("version", None)
    cur = {k: v for k, v in to_dict(e).items() if k in EventIn.model_fields}
    cur.update({k: v for k, v in payload.items() if k in EventIn.model_fields})
    data = EventIn.model_validate(cur).model_dump()
    update_obj(db, e, data, user, version, request)
    conflicts = find_conflicts(db, user, e.start, e.end, e.participants, e.organizer_id, e.id)
    db.commit()
    return {"event": to_dict(e), "conflicts": conflicts}


@router.delete("/{event_id}")
def delete_event(event_id: str, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    e = get_owned(db, Event, event_id, user)
    if user.role == "member" and e.organizer_id != user.id:
        raise HTTPException(403, "Seul l'organisateur ou un chef de projet peut supprimer ce rendez-vous.")
    delete_obj(db, e, user, request)
    db.commit()
    return {"ok": True}


@router.post("/{event_id}/summarize")
def summarize(event_id: str, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    e = get_owned(db, Event, event_id, user)
    if not (e.minutes or "").strip():
        raise HTTPException(422, "Rédigez ou collez d'abord le compte rendu.")
    conf = bool(e.project_id and (db.get(Project, e.project_id) or Project(confidential=False)).confidential)
    text = ai_service.generate(db, user.agency_id, load_prompt("meeting_summary", text=e.minutes[:40000]), conf, 2000)
    if text is None:
        # Repli déterministe : repérage des actions et décisions
        lines = [l.strip(" -•*") for l in e.minutes.splitlines() if l.strip()]
        actions = [l for l in lines if any(k in l.lower() for k in ("action", "doit", "à faire", "devra", "fournir", "transmettre", "avant le"))]
        decisions = [l for l in lines if any(k in l.lower() for k in ("décid", "valid", "accord", "retenu", "acté"))]
        text = "**Synthèse automatique (sans IA générative)**\n\n### Décisions\n" + ("\n".join(f"- {d}" for d in decisions) or "- Aucune décision repérée") \
            + "\n\n### Actions\n" + ("\n".join(f"- {a}" for a in actions) or "- Aucune action repérée")
    return {"summary": text}
