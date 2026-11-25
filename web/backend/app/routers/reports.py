"""Module 11 – Rapports (PDF, XLSX, CSV, DOCX)."""
from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..crud import create_obj, get_owned, scoped_query, to_dict
from ..db import get_db
from ..models import (Agency, Client, Company, Comparison, Document, Event, Incident, Lot, ParcelAnalysis, Project, Quote,
                      Report, Task, User)
from ..schemas import PHASE_LABELS
from ..security import require
from ..services import documents as docsvc
from ..services import exports
from ..services.exports import eur
from .insights import finance_summary
from .planning import schedule
from .quotes import comparison_blocks

router = APIRouter(prefix="/api/reports", tags=["rapports"])

KINDS = {"devis": "Rapport d'analyse des devis", "urbanisme": "Rapport urbanistique et de faisabilité",
         "chantier": "Rapport de chantier", "compte_rendu": "Compte rendu de réunion", "financier": "Rapport financier",
         "synthese": "Synthèse de projet"}
STATUS = {"etude": "Études", "consultation": "Consultation", "chantier": "Chantier", "reception": "Réception", "archive": "Archivé"}


def _d(v) -> str:
    if not v:
        return "—"
    return date.fromisoformat(str(v)[:10]).strftime("%d/%m/%Y")


def project_header(db: Session, p: Project) -> list[dict]:
    client = db.get(Client, p.client_id) if p.client_id else None
    return [{"type": "kv", "items": [
        ("Projet", f"{p.code} – {p.name}"), ("Maître d'ouvrage", client.name if client else "—"),
        ("Adresse", f"{p.address or ''} {p.postal_code or ''} {p.city or ''}".strip() or "—"),
        ("Statut / phase", f"{STATUS.get(p.status, p.status)} / {p.current_phase or '—'}"),
        ("Avancement global", f"{p.progress} %"), ("Budget initial", eur(p.budget_initial)),
        ("Dates", f"{_d(p.start_date)} → {_d(p.end_date)}")]}]


def blocks_chantier(db: Session, user: User, p: Project) -> list[dict]:
    b = project_header(db, p)
    sched = schedule([to_dict(t) for t in scoped_query(db, Task, user).filter(Task.project_id == p.id).order_by(Task.start_date)])
    b += [{"type": "h2", "text": "Planning"},
          {"type": "p", "text": f"Période : {_d(sched['start'])} → {_d(sched['end'])}. {sched['late_count']} tâche(s) en retard, "
                                f"{sched['violations']} dépendance(s) non respectée(s)."},
          {"type": "table", "columns": ["Tâche", "Début", "Fin", "Durée (j)", "Avancement", "Attendu", "État"],
           "widths": [0.34, 0.11, 0.11, 0.09, 0.11, 0.1, 0.14],
           "rows": [[t["name"], _d(t["start_date"]), _d(t["end_date"]), t["duration_days"], f"{t['progress']} %",
                     f"{t['expected_progress']} %", "En retard" if t["late"] else ("Critique" if t["critical"] else "Conforme")]
                    for t in sched["tasks"]]}]
    companies = {c.id: c.name for c in db.query(Company).filter(Company.agency_id == user.agency_id)}
    lots = scoped_query(db, Lot, user).filter(Lot.project_id == p.id).order_by(Lot.code).all()
    if lots:
        b += [{"type": "h2", "text": "Lots et entreprises"},
              {"type": "table", "columns": ["Lot", "Désignation", "Entreprise", "Statut", "Avancement"],
               "rows": [[l.code, l.name, companies.get(l.company_id, "—"), l.status.replace("_", " "), f"{l.progress} %"] for l in lots]}]
    inc = scoped_query(db, Incident, user).filter(Incident.project_id == p.id).order_by(Incident.date.desc()).all()
    b.append({"type": "h2", "text": "Incidents et observations"})
    b.append({"type": "table", "columns": ["Date", "Gravité", "Statut", "Intitulé", "Description"],
              "widths": [0.1, 0.1, 0.1, 0.25, 0.45],
              "rows": [[_d(i.date), i.severity, i.status, i.title, i.description or ""] for i in inc]} if inc
             else {"type": "p", "text": "Aucun incident enregistré."})
    return b


def blocks_financier(db: Session, user: User, p: Project) -> tuple[list[dict], dict]:
    s = finance_summary(db, user, p)
    b = project_header(db, p) + [{"type": "h2", "text": "Synthèse budgétaire (montants HT)"}, {"type": "kv", "items": [
        ("Budget initial", eur(s["budget_initial"])), ("Budget actualisé", eur(s["budget_actualise"])),
        ("Marchés signés", eur(s["marches"])), ("Travaux supplémentaires", eur(s["travaux_supp"])),
        ("Total engagé", eur(s["engage"])), ("Écart engagé / budget", f"{eur(s['ecart'])} ({s['ecart_pct'] if s['ecart_pct'] is not None else '—'} %)"),
        ("Facturé (situations, factures, acomptes)", eur(s["facture"])), ("Payé", eur(s["paye"])),
        ("Reste à payer", eur(s["reste_a_payer"])), ("Dépenses diverses", eur(s["depenses"])), ("Honoraires", eur(s["honoraires"]))]}]
    b += [{"type": "h2", "text": "Détail par lot"},
          {"type": "table", "columns": ["Lot", "Entreprise", "Budget", "Marché", "TS", "Engagé", "Facturé", "Payé", "Écart"],
           "rows": [[f"{l['code']} {l['name']}", l["company"] or "—", eur(l["budget"]), eur(l["marche"]), eur(l["travaux_supp"]),
                     eur(l["engage"]), eur(l["facture"]), eur(l["paye"]), eur(l["ecart"])] for l in s["by_lot"]],
           "raw_rows": [[f"{l['code']} {l['name']}", l["company"], l["budget"], l["marche"], l["travaux_supp"], l["engage"],
                         l["facture"], l["paye"], l["ecart"]] for l in s["by_lot"]],
           "number_formats": [None, None] + ["#,##0.00 €"] * 7}]
    if s["alerts"]:
        b += [{"type": "h2", "text": "Alertes"}, {"type": "bullets", "items": [a["message"] for a in s["alerts"]]}]
    return b, s


def blocks_synthese(db: Session, user: User, p: Project) -> list[dict]:
    b = project_header(db, p)
    if p.description:
        b += [{"type": "h2", "text": "Description"}, {"type": "p", "text": p.description}]
    if p.phases:
        b += [{"type": "h2", "text": "Phases de la mission"},
              {"type": "table", "columns": ["Phase", "Intitulé", "Début", "Fin", "Statut", "Avancement"],
               "rows": [[ph["code"], ph.get("label") or PHASE_LABELS.get(ph["code"], ""), _d(ph.get("start")), _d(ph.get("end")),
                         ph.get("status", "").replace("_", " "), f"{ph.get('progress', 0)} %"] for ph in p.phases if ph.get("enabled", True)]}]
    quotes = scoped_query(db, Quote, user).filter(Quote.project_id == p.id).all()
    if quotes:
        b += [{"type": "h2", "text": "Devis"}, {"type": "table", "columns": ["Référence", "Entreprise", "Total HT (recalculé)", "Statut", "Anomalies"],
              "rows": [[q.reference or "—", q.company_name_raw or "—", eur((q.computed or {}).get("total_ht")), q.status.replace("_", " "),
                        str(len(q.anomalies or []))] for q in quotes]}]
    fb, _ = blocks_financier(db, user, p)
    b += [x for x in fb[1:] if x["type"] != "kv" or x is fb[2]]
    b += blocks_chantier(db, user, p)[1:]
    return b


def blocks_urbanisme(db: Session, a: ParcelAnalysis) -> list[dict]:
    r = a.results or {}
    loc = r.get("location", {})
    b = []
    if a.mode == "demo":
        b.append({"type": "note", "text": "MODE DÉMONSTRATION : toutes les données de ce rapport sont fictives."})
    b += [{"type": "h2", "text": "Identification du terrain"}, {"type": "kv", "items": [
        ("Recherche", f"{a.query_type} : {a.query}"), ("Localisation", loc.get("label") or "—"),
        ("Commune (INSEE)", f"{loc.get('commune') or '—'} ({a.insee or '—'})"),
        ("Parcelle", f"Section {a.section or '—'} n° {a.numero or '—'}"),
        ("Surface", f"{a.area_m2:,.0f} m² – {r.get('area_source', '')}".replace(",", " ") if a.area_m2 else "Non disponible"),
        ("Coordonnées", f"{a.latitude:.6f}, {a.longitude:.6f}" if a.latitude else "—")]}]
    b.append({"type": "h2", "text": "Document d'urbanisme et zonage"})
    if r.get("documents"):
        b.append({"type": "bullets", "items": [f"{d.get('type') or ''} {d.get('name') or ''} – approuvé le {_d(d.get('approved'))} ({d.get('status') or 'statut n.c.'})" for d in r["documents"]]})
    b.append({"type": "bullets", "items": [f"Zone **{z.get('code')}** – {z.get('label') or ''}" + (f" (destination dominante : {z['destination']})" if z.get("destination") else "") for z in r.get("zones", [])]}
             if r.get("zones") else {"type": "p", "text": "Zonage non disponible."})
    for key, title in (("prescriptions", "Prescriptions"), ("servitudes", "Servitudes d'utilité publique"), ("patrimoine", "Patrimoine")):
        b.append({"type": "h3", "text": title})
        items = r.get(key) or []
        b.append({"type": "bullets", "items": [f"{i.get('label') or i.get('category')}" + (f" – {i['category_label']}" if i.get("category_label") else "") for i in items]}
                 if items else {"type": "p", "text": "Aucune donnée publiée pour ce terrain dans les sources interrogées."})
    risks = r.get("risques") or {}
    b.append({"type": "h3", "text": "Risques"})
    b.append({"type": "kv", "items": [("Risques recensés sur la commune", ", ".join(risks.get("commune") or []) or "Non disponible"),
                                       ("Zone de sismicité", str(risks.get("sismicite") or "Non disponible")),
                                       ("Retrait-gonflement des argiles", str(risks.get("argiles") or "Non disponible"))]})
    plu = (a.rules or {}).get("plu")
    b.append({"type": "h2", "text": "Analyse du règlement écrit"})
    if plu:
        b.append({"type": "p", "text": f"Document analysé : {plu.get('document')} – zone {plu.get('zone') or 'non précisée'}."})
        if plu.get("scope_note"):
            b.append({"type": "note", "text": plu["scope_note"]})
        rows = []
        for t in plu["themes"].values():
            rows.append([t["label"], t.get("article") or "—", (t.get("excerpt") or t.get("message") or "")[:700], ", ".join(t.get("values") or []), str(t.get("page") or "—")])
        b.append({"type": "table", "columns": ["Thème", "Article", "Extrait (texte du règlement)", "Valeurs relevées", "Page"],
                  "widths": [0.15, 0.17, 0.46, 0.14, 0.08], "rows": rows})
    else:
        b.append({"type": "p", "text": "Aucun règlement analysé : importez le règlement écrit du PLU dans Documents puis lancez l'analyse."})
    feas = (a.rules or {}).get("feasibility") or {}
    if feas.get("indicators"):
        b += [{"type": "h2", "text": "Indicateurs de faisabilité (calculés à partir des valeurs citées)"},
              {"type": "table", "columns": ["Indicateur", "Valeur", "Calcul", "Source"],
               "rows": [[i["label"], f"{i['value']} {i['unit']}", i["formula"], i["source"]] for i in feas["indicators"]]}]
    if (a.rules or {}).get("ai_summary"):
        b += [{"type": "h2", "text": "Analyse rédigée par l'assistant IA (à vérifier)"}, {"type": "markdown", "text": a.rules["ai_summary"]}]
    b += [{"type": "h2", "text": "Recommandations"}, {"type": "bullets", "items": feas.get("recommendations") or []},
          {"type": "h2", "text": "Sources consultées"},
          {"type": "table", "columns": ["Source", "Date de consultation", "Requête"],
           "rows": [[s["source"], _d(s.get("consulted_at")), (s.get("url") or "")[:120]] for s in a.sources or []]},
          {"type": "h2", "text": "Informations indisponibles et incertitudes"},
          {"type": "bullets", "items": [f"{u['source']} : {u['reason']}" for u in a.unavailable or []] or ["Aucune source en échec."]},
          {"type": "note", "text": "Ce rapport est établi à partir des données publiques disponibles à la date de consultation. Il ne se substitue "
                                   "pas à un certificat d'urbanisme ni à la lecture complète des pièces opposables du document d'urbanisme."}]
    return b


def blocks_cr(db: Session, user: User, e: Event) -> list[dict]:
    project = db.get(Project, e.project_id) if e.project_id else None
    b = [{"type": "kv", "items": [("Objet", e.title), ("Date", f"{e.start:%d/%m/%Y %H:%M} – {e.end:%H:%M}"), ("Lieu", e.location or "—"),
                                  ("Projet", f"{project.code} – {project.name}" if project else "—"),
                                  ("Participants", ", ".join(p.get("name") or p.get("email") or "" for p in e.participants or []) or "—")]}]
    if e.description:
        b += [{"type": "h2", "text": "Ordre du jour"}, {"type": "markdown", "text": e.description}]
    b += [{"type": "h2", "text": "Compte rendu"}, {"type": "markdown", "text": e.minutes or "Compte rendu non rédigé."}]
    docs = [db.get(Document, i) for i in e.document_ids or []]
    if any(docs):
        b += [{"type": "h2", "text": "Documents associés"}, {"type": "bullets", "items": [d.name for d in docs if d]}]
    return b


@router.get("/kinds")
def kinds(user: User = Depends(require("read"))):
    return [{"code": k, "label": v} for k, v in KINDS.items()]


@router.post("", status_code=201)
def generate(payload: dict, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    kind, fmt = payload.get("kind"), payload.get("fmt", "pdf")
    if kind not in KINDS:
        raise HTTPException(422, "Type de rapport inconnu.")
    if fmt not in ("pdf", "xlsx", "csv", "docx"):
        raise HTTPException(422, "Format inconnu (pdf, xlsx, csv, docx).")
    agency = db.get(Agency, user.agency_id)
    meta = {"agency": agency.name, "demo": agency.is_demo}
    project = None
    if kind in ("chantier", "financier", "synthese"):
        project = get_owned(db, Project, payload.get("project_id") or "", user)
        title = f"{KINDS[kind]} – {project.code} {project.name}"
        blocks = {"chantier": lambda: blocks_chantier(db, user, project), "financier": lambda: blocks_financier(db, user, project)[0],
                  "synthese": lambda: blocks_synthese(db, user, project)}[kind]()
        meta["subtitle"] = f"Édité le {date.today():%d/%m/%Y} par {user.full_name}"
    elif kind == "devis":
        cmp = get_owned(db, Comparison, payload.get("comparison_id") or "", user)
        project = db.get(Project, cmp.project_id)
        blocks, m = comparison_blocks(db, cmp)
        meta.update(m)
        title = f"{KINDS[kind]} – {cmp.title}"
    elif kind == "urbanisme":
        a = get_owned(db, ParcelAnalysis, payload.get("analysis_id") or "", user)
        project = db.get(Project, a.project_id) if a.project_id else None
        blocks = blocks_urbanisme(db, a)
        title = f"{KINDS[kind]} – {a.label or a.query}"
        meta["subtitle"] = f"Édité le {date.today():%d/%m/%Y} par {user.full_name}"
    else:
        e = get_owned(db, Event, payload.get("event_id") or "", user)
        project = db.get(Project, e.project_id) if e.project_id else None
        blocks = blocks_cr(db, user, e)
        title = f"{KINDS[kind]} – {e.title} ({e.start:%d/%m/%Y})"
    data, mime = exports.render(fmt, title, blocks, meta)
    filename = re.sub(r"[^\w\-]+", "_", title)[:100].strip("_") + "." + fmt
    doc, _ = docsvc.add_document(db, user, filename, data, project_id=project.id if project else None, category="rapport",
                                 confidential=bool(project and project.confidential))
    rep = create_obj(db, Report, {"project_id": project.id if project else None, "kind": kind, "title": title, "fmt": fmt,
                                  "document_id": doc.id, "params": {k: v for k, v in payload.items() if k.endswith("_id")}}, user, request)
    db.commit()
    return {**to_dict(rep), "download_url": f"/api/documents/{doc.id}/download"}


@router.get("")
def list_reports(project_id: str | None = None, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    q = scoped_query(db, Report, user)
    if project_id:
        q = q.filter(Report.project_id == project_id)
    return [to_dict(r) | {"download_url": f"/api/documents/{r.document_id}/download"} for r in q.order_by(Report.created_at.desc()).limit(300)]
