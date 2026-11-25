"""Module 05 – Planning (Gantt) et météo de chantier."""
from __future__ import annotations

from datetime import date, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..crud import create_obj, get_owned, record_change, scoped_query, to_dict, update_obj
from ..db import get_db, utcnow
from ..models import Project, Proposal, Task, User
from ..security import check_project_access, require
from ..services import settings_store
from ..services import weather as wx

router = APIRouter(prefix="/api", tags=["planning"])


def task_end(t: dict) -> date:
    s = date.fromisoformat(str(t["start_date"]))
    return s + timedelta(days=max(0, int(t["duration_days"] or 0) - (0 if t.get("milestone") else 1)))


def schedule(tasks: list[dict], today: date | None = None) -> dict:
    """Calcule fins, violations de dépendances (fin→début), chemin critique et retards."""
    today = today or date.today()
    by_id = {t["id"]: t for t in tasks}
    order, seen, temp = [], set(), set()
    cycles = []

    def visit(tid):
        if tid in seen:
            return
        if tid in temp:
            cycles.append(tid)
            return
        temp.add(tid)
        for dep in by_id[tid].get("depends_on") or []:
            if dep in by_id:
                visit(dep)
        temp.discard(tid)
        seen.add(tid)
        order.append(tid)

    for tid in by_id:
        visit(tid)
    info = {}
    for tid in order:
        t = by_id[tid]
        start = date.fromisoformat(str(t["start_date"]))
        end = task_end(t)
        earliest = None
        for dep in t.get("depends_on") or []:
            if dep in info:
                e = info[dep]["end"] + timedelta(days=1)
                earliest = e if earliest is None or e > earliest else earliest
        violation = bool(earliest and start < earliest)
        expected = 0
        dur = max(1, int(t["duration_days"] or 1))
        if today >= start:
            expected = min(100, round(((today - start).days + 1) / dur * 100))
        late_days = 0
        if t.get("progress", 0) < 100 and today > end:
            late_days = (today - end).days
        info[tid] = {"id": tid, "end": end, "earliest_start": earliest, "dependency_violation": violation,
                     "expected_progress": expected, "late": t.get("progress", 0) + 10 < expected or late_days > 0,
                     "late_days": late_days,
                     "baseline_drift": ((end - date.fromisoformat(str(t["baseline_end"]))).days if t.get("baseline_end") else None)}
    # chemin critique : chaîne de dépendances aboutissant à la fin la plus tardive
    critical = set()
    if info:
        last = max(info.values(), key=lambda x: x["end"])
        cur = last["id"]
        while cur:
            critical.add(cur)
            deps = [d for d in by_id[cur].get("depends_on") or [] if d in info]
            if not deps:
                break
            cur = max(deps, key=lambda d: info[d]["end"])
    out = []
    for t in tasks:
        i = info.get(t["id"], {})
        out.append({**t, "end_date": i.get("end").isoformat() if i.get("end") else None,
                    "earliest_start": i.get("earliest_start").isoformat() if i.get("earliest_start") else None,
                    "dependency_violation": i.get("dependency_violation", False), "expected_progress": i.get("expected_progress", 0),
                    "late": i.get("late", False), "late_days": i.get("late_days", 0), "critical": t["id"] in critical,
                    "baseline_drift": i.get("baseline_drift")})
    start = min((date.fromisoformat(str(t["start_date"])) for t in tasks), default=None)
    end = max((info[t]["end"] for t in info), default=None)
    return {"tasks": out, "start": start.isoformat() if start else None, "end": end.isoformat() if end else None,
            "cycles": cycles, "late_count": sum(1 for t in out if t["late"]),
            "violations": sum(1 for t in out if t["dependency_violation"])}


def project_tasks(db: Session, user: User, project_id: str) -> list[dict]:
    check_project_access(db, user, project_id)
    rows = scoped_query(db, Task, user).filter(Task.project_id == project_id).order_by(Task.start_date, Task.name).all()
    return [to_dict(t) for t in rows]


@router.get("/projects/{project_id}/schedule")
def get_schedule(project_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    return schedule(project_tasks(db, user, project_id))


@router.post("/projects/{project_id}/schedule/propagate")
def propagate(project_id: str, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    """Propose (sans appliquer) le recalage des tâches dont une dépendance n'est pas respectée."""
    sched = schedule(project_tasks(db, user, project_id))
    created = []
    for t in sched["tasks"]:
        if t["dependency_violation"] and t["earliest_start"]:
            p = create_obj(db, Proposal, {
                "project_id": project_id, "source": "planning", "kind": "decaler_tache", "target_id": t["id"],
                "payload": {"from": t["start_date"], "to": t["earliest_start"]},
                "reason": f"« {t['name']} » démarre avant la fin de sa tâche prédécesseur : recaler au {date.fromisoformat(t['earliest_start']):%d/%m/%Y}."}, user)
            created.append(to_dict(p))
    db.commit()
    return created


@router.post("/projects/{project_id}/baseline")
def set_baseline(project_id: str, user: User = Depends(require("validate")), db: Session = Depends(get_db)):
    for t in scoped_query(db, Task, user).filter(Task.project_id == project_id).all():
        d = to_dict(t)
        update_obj(db, t, {"baseline_start": t.start_date, "baseline_end": task_end(d)}, user, None)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ météo
def _weather_for(db: Session, user: User, project: Project) -> dict:
    cfg = settings_store.get(db, user.agency_id, "weather")
    if cfg.get("demo"):
        fc = wx.demo_forecast(project.id)
        return {"forecast": fc, "location": {"label": f"{project.address or ''} {project.city or ''} (simulation)",
                                             "latitude": project.latitude, "longitude": project.longitude}}
    lat, lon = project.latitude, project.longitude
    label = f"{project.address or ''} {project.postal_code or ''} {project.city or ''}".strip()
    try:
        with wx.http_client() as c:
            if lat is None or lon is None:
                if not label:
                    raise HTTPException(422, "Renseignez l'adresse du chantier dans la fiche projet pour obtenir la météo.")
                g = wx.geocode(label, cfg["geocoder"], c)
                if not g:
                    raise HTTPException(404, "Adresse du chantier introuvable par le service de géocodage.")
                lat, lon = g["latitude"], g["longitude"]
                project.latitude, project.longitude = lat, lon
                db.commit()
            fc = wx.forecast(lat, lon, cfg["base_url"], c)
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"Service météo injoignable ({type(exc).__name__}). Vérifiez la connexion Internet "
                                 "ou activez le mode démonstration dans Paramètres › Météo.")
    return {"forecast": fc, "location": {"label": label, "latitude": lat, "longitude": lon}}


@router.get("/projects/{project_id}/weather")
def project_weather(project_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    check_project_access(db, user, project_id)
    project = db.get(Project, project_id)
    w = _weather_for(db, user, project)
    analysis = wx.analyse_tasks(project_tasks(db, user, project_id), w["forecast"]["days"])
    return {**w, "analysis": analysis, "activities": wx.ACTIVITY_LABELS,
            "disclaimer": "Seuils indicatifs : à confronter aux prescriptions du CCTP, des fiches techniques et des DTU."}


@router.post("/projects/{project_id}/weather/proposals")
def weather_proposals(project_id: str, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    data = project_weather(project_id, user, db)
    pending = {p.target_id for p in db.query(Proposal).filter(Proposal.project_id == project_id, Proposal.status == "en_attente",
                                                              Proposal.deleted.is_(False))}
    created = []
    for a in data["analysis"]:
        if a["task_id"] in pending:
            continue
        risks = sorted({r for d in a["risky_days"] for r in d["risks"]})
        reason = (f"Météo : {len(a['risky_days'])} jour(s) défavorable(s) pour « {a['task']} » ({a['activity_label']}) — "
                  + "; ".join(risks[:3]) + ". " + a["recommendation"] + ".")
        payload = {"from": a["start_date"], "to": a["suggested_start"], "risky_days": [d["date"] for d in a["risky_days"]],
                   "simulated": data["forecast"]["simulated"]}
        p = create_obj(db, Proposal, {"project_id": project_id, "source": "meteo",
                                      "kind": "decaler_tache" if a["suggested_start"] else "alerte",
                                      "target_id": a["task_id"], "payload": payload, "reason": reason}, user)
        created.append(to_dict(p))
    db.commit()
    return created


# ------------------------------------------------------------------ propositions
@router.get("/proposals")
def list_proposals(project_id: str | None = None, status: str | None = "en_attente", user: User = Depends(require("read")),
                   db: Session = Depends(get_db)):
    q = scoped_query(db, Proposal, user)
    if project_id:
        q = q.filter(Proposal.project_id == project_id)
    if status:
        q = q.filter(Proposal.status == status)
    return [to_dict(p) for p in q.order_by(Proposal.created_at.desc()).all()]


def _shift_with_successors(db: Session, user: User, task: Task, new_start: date, request: Request | None) -> list[str]:
    delta = (new_start - task.start_date).days
    moved = [task.name]
    update_obj(db, task, {"start_date": new_start}, user, None, request)
    if delta <= 0:
        return moved
    tasks = {t.id: t for t in db.query(Task).filter(Task.project_id == task.project_id, Task.deleted.is_(False))}
    frontier = [task.id]
    while frontier:
        cur = frontier.pop()
        cur_end = task_end(to_dict(tasks[cur]))
        for t in tasks.values():
            if cur in (t.depends_on or []) and t.start_date <= cur_end:
                update_obj(db, t, {"start_date": cur_end + timedelta(days=1)}, user, None, request)
                moved.append(t.name)
                frontier.append(t.id)
    return moved


@router.post("/proposals/{proposal_id}/{decision}")
def decide(proposal_id: str, decision: str, request: Request, user: User = Depends(require("validate")),
           db: Session = Depends(get_db)):
    if decision not in ("accept", "reject"):
        raise HTTPException(404, "Action inconnue.")
    p = get_owned(db, Proposal, proposal_id, user)
    if p.status != "en_attente":
        raise HTTPException(409, "Cette proposition a déjà été traitée.")
    moved = []
    if decision == "accept" and p.kind == "decaler_tache" and p.payload.get("to"):
        task = get_owned(db, Task, p.target_id, user)
        moved = _shift_with_successors(db, user, task, date.fromisoformat(p.payload["to"]), request)
    p.status = "acceptee" if decision == "accept" else "refusee"
    p.decided_by, p.decided_at = user.id, utcnow()
    p.version += 1
    record_change(db, p, "update", user, {"status": p.status})
    db.commit()
    return {"proposal": to_dict(p), "moved_tasks": moved}
