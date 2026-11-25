"""Module 06 – Urbanisme et contraintes de site."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ai.document_analysis.specs import analyse_plu
from ai.prompts import load as load_prompt

from ..crud import create_obj, delete_obj, get_owned, scoped_query, to_dict, update_obj
from ..db import get_db
from ..models import Document, ParcelAnalysis, Project, User
from ..security import check_project_access, require
from ..services import ai as ai_service
from ..services import documents as docsvc
from ..services import settings_store
from ..services import urbanisme as urb

router = APIRouter(prefix="/api/urbanisme", tags=["urbanisme"])


@router.get("/analyses")
def list_analyses(project_id: str | None = None, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    q = scoped_query(db, ParcelAnalysis, user)
    if project_id:
        q = q.filter(ParcelAnalysis.project_id == project_id)
    return [{k: v for k, v in to_dict(a).items() if k not in ("results", "geometry")} for a in q.order_by(ParcelAnalysis.created_at.desc())]


@router.post("/analyses", status_code=201)
def run_analysis(payload: dict, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    qtype, query = payload.get("query_type"), (payload.get("query") or "").strip()
    if qtype not in ("adresse", "cadastre", "coordonnees") or not query:
        raise HTTPException(422, "Indiquez une adresse, une référence cadastrale ou des coordonnées.")
    project_id = payload.get("project_id") or None
    check_project_access(db, user, project_id)
    cfg = settings_store.get(db, user.agency_id, "urbanisme")
    if cfg.get("demo"):
        result, mode = urb.demo_result(query), "demo"
    else:
        try:
            with urb.http_client() as c:
                result = urb.SiteAnalyzer(cfg, c).run(qtype, query)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        mode = "reel"
    loc = result.get("location", {})
    parcel = loc.pop("parcel", None)
    a = create_obj(db, ParcelAnalysis, {
        "project_id": project_id, "query_type": qtype, "query": query, "label": loc.get("label") or query,
        "insee": loc.get("insee"), "section": loc.get("section"), "numero": loc.get("numero"),
        "latitude": loc.get("latitude"), "longitude": loc.get("longitude"), "geometry": parcel.get("geometry") if parcel else None,
        "area_m2": result.get("area_m2"), "results": result, "sources": result.get("sources", []),
        "unavailable": result.get("unavailable", []), "mode": mode,
        "rules": {"feasibility": urb.feasibility(result, None)}}, user, request)
    if project_id and loc.get("latitude") is not None:
        p = db.get(Project, project_id)
        if p.latitude is None:
            p.latitude, p.longitude = loc["latitude"], loc["longitude"]
        terrain = dict(p.terrain or {})
        terrain.update({"parcelle": f"{loc.get('insee') or ''} {loc.get('section') or ''} {loc.get('numero') or ''}".strip(),
                        "surface_cadastrale_m2": result.get("area_m2"),
                        "zone_plu": ", ".join(z["code"] for z in result.get("zones", []) if z.get("code")) or None})
        update_obj(db, p, {"terrain": terrain}, user, None)
    db.commit()
    return to_dict(a)


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    return to_dict(get_owned(db, ParcelAnalysis, analysis_id, user))


@router.delete("/analyses/{analysis_id}")
def delete_analysis(analysis_id: str, request: Request, user: User = Depends(require("delete")), db: Session = Depends(get_db)):
    delete_obj(db, get_owned(db, ParcelAnalysis, analysis_id, user), user, request)
    db.commit()
    return {"ok": True}


@router.post("/analyses/{analysis_id}/plu")
def analyse_reglement(analysis_id: str, payload: dict, request: Request, user: User = Depends(require("write")),
                      db: Session = Depends(get_db)):
    """Analyse du règlement écrit (document importé) pour la zone du terrain."""
    a = get_owned(db, ParcelAnalysis, analysis_id, user)
    doc = get_owned(db, Document, payload.get("document_id") or "", user)
    zone = payload.get("zone") or next((z.get("code") for z in (a.results or {}).get("zones", []) if z.get("code")), None)
    ex = docsvc.extract_from_version(docsvc.current_version(db, doc))
    plu = analyse_plu(ex, zone)
    plu["document_id"] = doc.id
    feas = urb.feasibility(a.results or {}, plu)
    rules = {"plu": plu, "feasibility": feas}
    if payload.get("use_ai"):
        allowed, reason = ai_service.may_send(db, user.agency_id, doc.confidential)
        if allowed:
            excerpts = "\n\n".join(f"[S{i + 1}] {t['label']} – {t.get('article') or ''} (p. {t.get('page')}) : {t['excerpt']}"
                                   for i, t in enumerate(v for v in plu["themes"].values() if v["found"]))
            site = {k: (a.results or {}).get(k) for k in ("location", "area_m2", "zones", "servitudes", "prescriptions", "risques")}
            text = ai_service.generate(db, user.agency_id, load_prompt("plu_analysis", site=site, excerpts=excerpts),
                                       doc.confidential, 3500)
            rules["ai_summary"] = text
        else:
            rules["ai_summary_unavailable"] = reason
    update_obj(db, a, {"rules": rules}, user, None, request)
    db.commit()
    return to_dict(a)


@router.get("/legifrance")
def legifrance(q: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    cfg = settings_store.get(db, user.agency_id, "urbanisme")
    lf = urb.Legifrance(cfg)
    if not lf.configured:
        raise HTTPException(409, "Légifrance n'est pas configuré : renseignez vos identifiants PISTE dans Paramètres › Urbanisme.")
    try:
        return {"results": lf.search_code_urbanisme(q), "source": "Légifrance – API PISTE (DILA)"}
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"Légifrance injoignable ou identifiants refusés ({type(exc).__name__}).")
