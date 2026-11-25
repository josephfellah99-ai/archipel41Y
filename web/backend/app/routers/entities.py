"""Modules 02 (projets, lots, incidents), 05 (tâches), 09 (clients, entreprises), 10 (finances)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ai.document_analysis.calc import ttc_from_ht

from ..crud import create_obj, crud_router, get_owned, scoped_query, to_dict
from ..db import get_db
from ..models import (BudgetLine, Client, Comparison, Company, Document, DpgfItem, Event, FinanceEntry, Incident, Lot,
                      Project, Quote, Task, User)
from ..schemas import (ACTIVITIES, PHASE_CODES, PHASE_LABELS, BudgetLineIn, ClientIn, CompanyIn, DpgfItemIn,
                       FinanceEntryIn, IncidentIn, LotIn, ProjectIn, TaskIn)
from ..security import require


def default_phases() -> list[dict]:
    return [{"code": c, "label": PHASE_LABELS[c], "enabled": True, "start": None, "end": None, "status": "a_venir", "progress": 0, "fee_share": None} for c in PHASE_CODES]


def _project_defaults(db: Session, p: Project, user: User) -> None:
    if not p.phases:
        p.phases = default_phases()
    if not p.current_phase:
        p.current_phase = next((ph["code"] for ph in p.phases if ph.get("enabled", True)), None)


def _finance_ttc(db: Session, e: FinanceEntry, user: User) -> None:
    e.amount_ttc = ttc_from_ht(e.amount_ht, e.vat_rate)


routers = [
    crud_router(Client, "clients", ClientIn, search_fields=("name", "email", "city"), filter_fields=("kind",), order_by="name", tag="clients"),
    crud_router(Company, "companies", CompanyIn, search_fields=("name", "email", "city"), filter_fields=(), order_by="name", tag="entreprises"),
    crud_router(Project, "projects", ProjectIn, search_fields=("name", "code", "city"), filter_fields=("status", "client_id"),
                after_change=_project_defaults, tag="projets"),
    crud_router(Lot, "lots", LotIn, search_fields=("name", "code"), filter_fields=("project_id", "company_id"), order_by="code", tag="projets"),
    crud_router(Incident, "incidents", IncidentIn, search_fields=("title",), filter_fields=("project_id", "status"), tag="projets"),
    crud_router(Task, "tasks", TaskIn, search_fields=("name",), filter_fields=("project_id", "responsible_id"), order_by="start_date", tag="planning"),
    crud_router(BudgetLine, "budget-lines", BudgetLineIn, search_fields=("label",), filter_fields=("project_id", "lot_id"), order_by="label", tag="finances"),
    crud_router(FinanceEntry, "finance-entries", FinanceEntryIn, search_fields=("label", "reference"),
                filter_fields=("project_id", "lot_id", "kind", "company_id"), order_by="entry_date", after_change=_finance_ttc, tag="finances"),
    crud_router(DpgfItem, "dpgf-items", DpgfItemIn, search_fields=("designation",), filter_fields=("project_id", "lot_id"), order_by="position", tag="devis"),
]

extra = APIRouter(prefix="/api", tags=["projets"])


@extra.get("/meta")
def meta(user: User = Depends(require("read"))):
    return {"phases": [{"code": c, "label": PHASE_LABELS[c]} for c in PHASE_CODES], "activities": ACTIVITIES}


@extra.get("/projects/{project_id}/overview")
def overview(project_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    p = get_owned(db, Project, project_id, user)
    client = db.get(Client, p.client_id) if p.client_id else None
    companies = {c.id: to_dict(c) for c in scoped_query(db, Company, user)}
    lots = [to_dict(l) | {"company": companies.get(l.company_id, {}).get("name")}
            for l in scoped_query(db, Lot, user).filter(Lot.project_id == p.id).order_by(Lot.code)]
    count = lambda m: scoped_query(db, m, user).filter(m.project_id == p.id).count()  # noqa: E731
    team_ids = [m.get("user_id") for m in p.team or []]
    team = [{"id": u.id, "full_name": u.full_name, "role": next((m.get("role") for m in p.team if m.get("user_id") == u.id), None)}
            for u in db.query(User).filter(User.id.in_(team_ids))] if team_ids else []
    involved = sorted({l["company"] for l in lots if l.get("company")} |
                      {q.company_name_raw for q in scoped_query(db, Quote, user).filter(Quote.project_id == p.id) if q.company_name_raw})
    return {"project": to_dict(p), "client": to_dict(client) if client else None, "lots": lots, "team": team,
            "companies": involved,
            "counts": {"documents": count(Document), "quotes": count(Quote), "tasks": count(Task), "incidents": count(Incident),
                       "events": count(Event), "comparisons": count(Comparison)},
            "incidents": [to_dict(i) for i in scoped_query(db, Incident, user).filter(Incident.project_id == p.id).order_by(Incident.date.desc()).limit(50)]}


@extra.get("/clients/{client_id}/related")
def client_related(client_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    c = get_owned(db, Client, client_id, user)
    projects = scoped_query(db, Project, user).filter(Project.client_id == c.id).all()
    pids = [p.id for p in projects]
    docs = scoped_query(db, Document, user).all()
    return {"projects": [to_dict(p) for p in projects],
            "documents": [to_dict(d) for d in docs if (d.linked or {}).get("client_id") == c.id][:100],
            "events": [to_dict(e) for e in scoped_query(db, Event, user).filter(Event.project_id.in_(pids)).order_by(Event.start.desc()).limit(30)] if pids else []}


@extra.get("/companies/{company_id}/related")
def company_related(company_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    c = get_owned(db, Company, company_id, user)
    quotes = scoped_query(db, Quote, user).filter(Quote.company_id == c.id).all()
    lots = scoped_query(db, Lot, user).filter(Lot.company_id == c.id).all()
    entries = scoped_query(db, FinanceEntry, user).filter(FinanceEntry.company_id == c.id, FinanceEntry.kind.in_(["marche", "travaux_supp"])).all()
    pids = {q.project_id for q in quotes} | {l.project_id for l in lots}
    projects = {p.id: p for p in scoped_query(db, Project, user).filter(Project.id.in_(pids))} if pids else {}
    docs = [d for d in scoped_query(db, Document, user) if (d.linked or {}).get("company_id") == c.id or
            any(d.id == q.document_id for q in quotes)]
    return {"quotes": [to_dict(q) | {"project": projects[q.project_id].name if q.project_id in projects else None} for q in quotes],
            "lots": [to_dict(l) | {"project": projects[l.project_id].name if l.project_id in projects else None} for l in lots],
            "markets": [to_dict(e) for e in entries], "projects": [to_dict(p) for p in projects.values()],
            "documents": [to_dict(d) for d in docs[:100]]}
