"""Module 01 – Tableau de bord et Module 10 – Finances."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai.prompts import load as load_prompt

from ..crud import scoped_query, to_dict
from ..db import get_db, utcnow
from ..models import (AuditLog, BudgetLine, Company, Event, FinanceEntry, Incident, Lot, Project, Proposal, Quote,
                      SyncConflict, Task, User)
from ..security import accessible_project_ids, check_project_access, require
from ..services import ai as ai_service
from ..services import settings_store
from ..services import weather as wx
from ..services.exports import eur
from .planning import schedule

router = APIRouter(prefix="/api", tags=["tableau de bord", "finances"])


def f(v) -> float:
    return float(v or 0)


def finance_summary(db: Session, user: User, project: Project) -> dict:
    entries = [e for e in scoped_query(db, FinanceEntry, user).filter(FinanceEntry.project_id == project.id) if e.status != "annule"]
    blines = scoped_query(db, BudgetLine, user).filter(BudgetLine.project_id == project.id).all()
    lots = scoped_query(db, Lot, user).filter(Lot.project_id == project.id).order_by(Lot.code).all()
    sums = defaultdict(float)
    for e in entries:
        sums[e.kind] += f(e.amount_ht)
    initial = f(project.budget_initial) or sum(f(b.initial_amount) for b in blines)
    actualise = sum(f(b.current_amount) for b in blines) if blines else initial + sums["travaux_supp"]
    engaged = sums["marche"] + sums["travaux_supp"]
    invoiced = sums["facture"] + sums["situation"] + sums["acompte"]
    today = date.today()
    unpaid = [e for e in entries if e.kind in ("facture", "situation", "acompte") and e.status not in ("paye",)]
    overdue = [e for e in unpaid if e.due_date and e.due_date < today]
    by_lot = []
    companies = {c.id: c.name for c in db.query(Company).filter(Company.agency_id == user.agency_id)}
    for lot in lots:
        le = [e for e in entries if e.lot_id == lot.id]
        bl = [b for b in blines if b.lot_id == lot.id]
        budget = sum(f(b.current_amount) for b in bl) if bl else f(lot.budget)
        marche = sum(f(e.amount_ht) for e in le if e.kind == "marche") or f(lot.contract_amount)
        ts = sum(f(e.amount_ht) for e in le if e.kind == "travaux_supp")
        inv = sum(f(e.amount_ht) for e in le if e.kind in ("facture", "situation", "acompte"))
        paid = sum(f(e.amount_ht) for e in le if e.kind == "paiement")
        total = marche + ts
        by_lot.append({"lot_id": lot.id, "code": lot.code, "name": lot.name, "company": companies.get(lot.company_id),
                       "budget": round(budget, 2), "marche": round(marche, 2), "travaux_supp": round(ts, 2),
                       "engage": round(total, 2), "facture": round(inv, 2), "paye": round(paid, 2),
                       "ecart": round(total - budget, 2) if budget else None,
                       "ecart_pct": round((total - budget) / budget * 100, 1) if budget else None,
                       "avancement_financier": round(inv / total * 100, 1) if total else None})
    alerts = []
    if actualise and engaged > actualise:
        alerts.append({"level": "haute", "message": f"Montant engagé ({eur(engaged)}) supérieur au budget actualisé ({eur(actualise)})."})
    for l in by_lot:
        if l["ecart"] and l["ecart"] > 0:
            alerts.append({"level": "moyenne", "message": f"Lot {l['code']} {l['name']} : dépassement de {eur(l['ecart'])} ({l['ecart_pct']:+.1f} %).".replace(".", ",", 0)})
    for e in overdue:
        alerts.append({"level": "moyenne", "message": f"Échéance dépassée : {e.label} ({eur(e.amount_ttc)} TTC, échue le {e.due_date:%d/%m/%Y})."})
    return {
        "project_id": project.id, "budget_initial": round(initial, 2), "budget_actualise": round(actualise, 2),
        "marches": round(sums["marche"], 2), "travaux_supp": round(sums["travaux_supp"], 2), "engage": round(engaged, 2),
        "facture": round(invoiced, 2), "acomptes": round(sums["acompte"], 2), "situations": round(sums["situation"], 2),
        "paye": round(sums["paiement"], 2), "reste_a_payer": round(invoiced - sums["paiement"], 2),
        "reste_a_engager": round(actualise - engaged, 2), "depenses": round(sums["depense"], 2),
        "honoraires": round(sums["honoraires"], 2),
        "ecart": round(engaged - actualise, 2) if actualise else None,
        "ecart_pct": round((engaged - actualise) / actualise * 100, 1) if actualise else None,
        "impayes": [to_dict(e) for e in unpaid], "en_retard": len(overdue), "by_lot": by_lot, "alerts": alerts,
    }


@router.get("/projects/{project_id}/finances")
def project_finances(project_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    check_project_access(db, user, project_id)
    return finance_summary(db, user, db.get(Project, project_id))


@router.get("/finances/overview")
def finances_overview(user: User = Depends(require("read")), db: Session = Depends(get_db)):
    rows = []
    for p in scoped_query(db, Project, user).filter(Project.status != "archive").order_by(Project.code):
        s = finance_summary(db, user, p)
        rows.append({"project_id": p.id, "code": p.code, "name": p.name, "status": p.status,
                     **{k: s[k] for k in ("budget_initial", "budget_actualise", "engage", "facture", "paye", "ecart", "ecart_pct", "en_retard")},
                     "alerts": len(s["alerts"])})
    return rows


# ------------------------------------------------------------------ tableau de bord
@router.get("/dashboard")
def dashboard(period: int = 30, project_id: str | None = None, user_id: str | None = None,
              me: User = Depends(require("read")), db: Session = Depends(get_db)):
    if project_id:
        check_project_access(db, me, project_id)
    today = date.today()
    now = utcnow()
    horizon = now + timedelta(days=max(1, min(period, 365)))
    projects = scoped_query(db, Project, me).filter(Project.status != "archive")
    if project_id:
        projects = projects.filter(Project.id == project_id)
    projects = projects.all()
    if user_id:
        projects = [p for p in projects if any(m.get("user_id") == user_id for m in p.team or [])] or projects
    pids = {p.id for p in projects}
    quotes = [q for q in scoped_query(db, Quote, me).filter(Quote.status == "a_verifier") if q.project_id in pids]
    events = scoped_query(db, Event, me).filter(Event.start >= now - timedelta(hours=2), Event.start <= horizon).order_by(Event.start).all()
    if project_id:
        events = [e for e in events if e.project_id == project_id]
    if user_id:
        events = [e for e in events if e.organizer_id == user_id or any(p.get("user_id") == user_id for p in e.participants or [])]
    tasks_all = [t for t in scoped_query(db, Task, me).filter(Task.progress < 100) if t.project_id in pids]
    if user_id:
        tasks_all = [t for t in tasks_all if t.responsible_id == user_id]
    sched = {t["id"]: t for p in pids for t in schedule([to_dict(x) for x in tasks_all if x.project_id == p])["tasks"]}
    prio = []
    for t in tasks_all:
        s = sched.get(t.id, {})
        if t.priority == "haute" or s.get("late") or (t.start_date <= today + timedelta(days=7)):
            prio.append({**to_dict(t), "late": s.get("late"), "late_days": s.get("late_days"), "end_date": s.get("end_date"),
                         "project": next((p.code for p in projects if p.id == t.project_id), "")})
    prio.sort(key=lambda t: (not t["late"], t["priority"] != "haute", t["start_date"]))
    budgets, alerts = [], []
    for p in projects:
        s = finance_summary(db, me, p)
        budgets.append({"project_id": p.id, "code": p.code, "name": p.name, "budget": s["budget_actualise"], "engage": s["engage"],
                        "facture": s["facture"], "ecart_pct": s["ecart_pct"]})
        for a in s["alerts"]:
            alerts.append({**a, "project": p.code, "module": "finances", "project_id": p.id})
    for t in prio:
        if t["late"]:
            alerts.append({"level": "moyenne", "project": t["project"], "module": "planning", "project_id": t["project_id"],
                           "message": f"Tâche en retard : {t['name']}" + (f" ({t['late_days']} j)" if t.get("late_days") else "")})
    for q in quotes:
        hi = [a for a in q.anomalies or [] if a.get("severity") == "haute"]
        if hi:
            alerts.append({"level": "moyenne", "project": next((p.code for p in projects if p.id == q.project_id), ""), "module": "devis",
                           "project_id": q.project_id, "message": f"Devis {q.reference or ''} ({q.company_name_raw or 'entreprise ?'}) : {len(hi)} anomalie(s) de calcul."})
    for i in scoped_query(db, Incident, me).filter(Incident.status != "clos", Incident.severity.in_(["haute", "critique"])):
        if i.project_id in pids:
            alerts.append({"level": "haute" if i.severity == "critique" else "moyenne", "module": "chantier", "project_id": i.project_id,
                           "project": next((p.code for p in projects if p.id == i.project_id), ""), "message": f"Incident {i.severity} : {i.title}"})
    pending = [p for p in scoped_query(db, Proposal, me).filter(Proposal.status == "en_attente") if p.project_id in pids]
    if pending:
        alerts.append({"level": "basse", "module": "planning", "message": f"{len(pending)} proposition(s) d'ajustement du planning à valider."})
    conflicts = db.query(SyncConflict).filter(SyncConflict.agency_id == me.agency_id, SyncConflict.status == "ouvert").count()
    if conflicts:
        alerts.append({"level": "haute", "module": "synchronisation", "message": f"{conflicts} conflit(s) de synchronisation à résoudre."})
    names = {u.id: u.full_name for u in db.query(User).filter(User.agency_id == me.agency_id)}
    acts = (db.query(AuditLog).filter(AuditLog.agency_id == me.agency_id, AuditLog.action.in_(["create", "update", "delete", "validate", "new_version"]),
                                      AuditLog.at >= now - timedelta(days=max(1, period)))
            .order_by(AuditLog.at.desc()).limit(15).all())
    order = {"haute": 0, "moyenne": 1, "basse": 2}
    alerts.sort(key=lambda a: order.get(a["level"], 3))
    return {
        "kpis": {"projets_actifs": len(projects), "chantiers": sum(1 for p in projects if p.status == "chantier"),
                 "devis_en_attente": len(quotes), "rendez_vous": len(events), "taches_prioritaires": len(prio),
                 "alertes": len(alerts)},
        "projects": [{**{k: v for k, v in to_dict(p).items() if k in ("id", "code", "name", "status", "progress", "city", "current_phase", "color", "latitude", "longitude")}} for p in projects],
        "quotes": [{"id": q.id, "reference": q.reference, "company": q.company_name_raw, "project_id": q.project_id,
                    "total_ht": (q.computed or {}).get("total_ht"), "anomalies": len(q.anomalies or [])} for q in quotes[:10]],
        "events": [to_dict(e) for e in events[:12]], "tasks": prio[:12], "budgets": budgets, "alerts": alerts[:30],
        "activity": [{"at": a.at.isoformat(), "user": names.get(a.user_id, "—"), "action": a.action, "entity": a.entity,
                      "summary": a.summary} for a in acts],
    }


@router.get("/dashboard/weather")
def dashboard_weather(me: User = Depends(require("read")), db: Session = Depends(get_db)):
    """Météo du jour et du lendemain pour les chantiers en cours (géolocalisés)."""
    cfg = settings_store.get(db, me.agency_id, "weather")
    out = []
    for p in scoped_query(db, Project, me).filter(Project.status == "chantier").limit(8):
        if p.latitude is None:
            out.append({"project_id": p.id, "code": p.code, "name": p.name, "error": "Chantier non géolocalisé"})
            continue
        try:
            fc = wx.demo_forecast(p.id, days=3) if cfg.get("demo") else wx.forecast(p.latitude, p.longitude, cfg["base_url"], days=3)
            out.append({"project_id": p.id, "code": p.code, "name": p.name, "days": fc["days"][:3], "simulated": fc["simulated"]})
        except Exception as exc:  # service indisponible : signalé, jamais masqué
            out.append({"project_id": p.id, "code": p.code, "name": p.name, "error": f"Météo indisponible ({type(exc).__name__})"})
    return out


@router.get("/dashboard/daily-summary")
def daily_summary(me: User = Depends(require("read")), db: Session = Depends(get_db)):
    d = dashboard(7, None, None, me, db)
    facts = {"date": date.today().isoformat(), "kpis": d["kpis"],
             "rendez_vous": [{"titre": e["title"], "debut": e["start"], "lieu": e["location"]} for e in d["events"][:8]],
             "taches": [{"nom": t["name"], "projet": t["project"], "retard": t["late"]} for t in d["tasks"][:8]],
             "alertes": [a["message"] for a in d["alerts"][:10]],
             "devis": [{"ref": q["reference"], "entreprise": q["company"], "anomalies": q["anomalies"]} for q in d["quotes"][:5]]}
    text = ai_service.generate(db, me.agency_id, load_prompt("daily_summary", facts=json.dumps(facts, ensure_ascii=False)), False, 1200)
    if text:
        return {"summary": text, "source": "ia"}
    k = d["kpis"]
    parts = [f"**Synthèse du {date.today():%d/%m/%Y}** — {k['projets_actifs']} projet(s) actif(s) dont {k['chantiers']} chantier(s) en cours."]
    today_ev = [e for e in d["events"] if e["start"][:10] == date.today().isoformat()]
    parts.append(f"{len(today_ev)} rendez-vous aujourd'hui" + (" : " + ", ".join(e["title"] for e in today_ev[:4]) if today_ev else "") + ".")
    late = [t for t in d["tasks"] if t["late"]]
    if late:
        parts.append(f"{len(late)} tâche(s) en retard, notamment « {late[0]['name']} » ({late[0]['project']}).")
    if k["devis_en_attente"]:
        parts.append(f"{k['devis_en_attente']} devis à vérifier/valider.")
    hi = [a for a in d["alerts"] if a["level"] == "haute"]
    if hi:
        parts.append("Alertes prioritaires : " + " ; ".join(a["message"] for a in hi[:3]))
    actions = []
    if late:
        actions.append("faire le point sur les tâches en retard")
    if k["devis_en_attente"]:
        actions.append("vérifier les devis importés")
    if hi:
        actions.append("traiter les alertes prioritaires")
    if actions:
        parts.append("Actions recommandées : " + ", ".join(actions) + ".")
    return {"summary": "\n\n".join(parts), "source": "regles"}
