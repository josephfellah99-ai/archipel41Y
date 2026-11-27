"""Module 03 – Devis et comparateur intelligent."""
from __future__ import annotations

import json
import re
import zipfile
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ai.document_analysis.calc import compute_quote
from ai.document_analysis.comparator import STATUS_LABELS, compare, rule_based_conclusion, similarity
from ai.document_analysis.extract import expand_zip
from ai.document_analysis.quote_parser import ParsedLine, ParsedQuote, parse_quote
from ai.document_analysis.specs import parse_cctp, parse_dpgf
from ai.prompts import load as load_prompt

from ..crud import audit, create_obj, delete_obj, get_owned, record_change, scoped_query, to_dict, update_obj
from ..db import get_db, utcnow
from ..models import (Agency, CctpRequirement, Company, Comparison, Document, DpgfItem, Lot, Project, Quote, QuoteLine,
                      User)
from ..schemas import QuoteIn
from ..security import check_project_access, require
from ..services import ai as ai_service
from ..services import documents as docsvc
from ..services import exports
from ..services import settings_store

router = APIRouter(prefix="/api", tags=["devis"])


# ------------------------------------------------------------------ utilitaires
def lines_of(db: Session, quote_id: str) -> list[QuoteLine]:
    return (db.query(QuoteLine).filter(QuoteLine.quote_id == quote_id, QuoteLine.deleted.is_(False))
            .order_by(QuoteLine.position).all())


def recompute(db: Session, q: Quote) -> None:
    lines = [to_dict(l) for l in lines_of(db, q.id)]
    default_vat = None
    rates = [l["vat_rate"] for l in lines if l.get("vat_rate") is not None]
    if not rates:
        default_vat = settings_store.get(db, q.agency_id, "agency").get("default_vat", 20)
    computed, anomalies = compute_quote(lines, default_vat=default_vat, declared_ht=q.declared_ht,
                                        declared_tva=q.declared_tva, declared_ttc=q.declared_ttc)
    q.computed = computed
    q.anomalies = anomalies


def quote_out(db: Session, q: Quote, with_lines: bool = True) -> dict:
    d = to_dict(q)
    if q.company_id:
        c = db.get(Company, q.company_id)
        d["company_name"] = c.name if c else q.company_name_raw
    else:
        d["company_name"] = q.company_name_raw
    if with_lines:
        d["lines"] = [to_dict(l) for l in lines_of(db, q.id)]
    return d


def match_company(db: Session, agency_id: str, name: str | None, siret: str | None) -> Company | None:
    rows = db.query(Company).filter(Company.agency_id == agency_id, Company.deleted.is_(False)).all()
    if siret:
        for c in rows:
            if c.siret and c.siret == siret:
                return c
    if name:
        best, score = None, 0.0
        for c in rows:
            s = similarity(name, c.name)
            if s > score:
                best, score = c, s
        if best and score >= 0.62:
            return best
    return None


def llm_extract(db: Session, user: User, text: str, confidential: bool) -> ParsedQuote | None:
    allowed, reason = ai_service.may_send(db, user.agency_id, confidential)
    if not allowed:
        raise HTTPException(409, reason)
    out = ai_service.generate(db, user.agency_id, load_prompt("quote_extraction", text=text[:60000]), confidential,
                              max_tokens=12000, system="Tu es un extracteur de données structurées. Tu réponds uniquement en JSON.")
    if not out:
        raise HTTPException(502, "Le fournisseur d'IA n'a pas répondu.")
    m = re.search(r"\{.*\}", out, re.S)
    try:
        data = json.loads(m.group(0) if m else out)
    except json.JSONDecodeError:
        raise HTTPException(502, "Réponse de l'IA illisible : utilisez l'extraction par règles.")
    q = ParsedQuote(method="ia")
    for k in ("company_name", "reference", "quote_date", "validity_days", "delay_text", "delay_days", "payment_terms",
              "default_vat", "declared_ht", "declared_tva", "declared_ttc"):
        setattr(q, k, data.get(k))
    for k in ("exclusions", "reserves", "conditions", "variants"):
        setattr(q, k, [str(x)[:400] for x in data.get(k) or []])
    allowed_status = {"inclus", "exclu", "optionnel", "variante", "a_verifier"}
    for ln in data.get("lines") or []:
        if not ln.get("designation"):
            continue
        st = ln.get("status") if ln.get("status") in allowed_status else "a_verifier"
        q.lines.append(ParsedLine(designation=str(ln["designation"])[:1000], quantity=_num(ln.get("quantity")),
                                  unit=ln.get("unit"), unit_price=_num(ln.get("unit_price")), total_ht=_num(ln.get("total_ht")),
                                  vat_rate=_num(ln.get("vat_rate")), status=st, code=ln.get("code"), section=ln.get("section"),
                                  confidence=0.75))
    q.confidence = 0.75
    q.warnings.append("Extraction réalisée par l'IA : les montants ont été recalculés par le moteur déterministe ; vérifiez chaque ligne.")
    return q


def _num(v):
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def apply_parsed(db: Session, user: User, q: Quote, parsed: ParsedQuote, replace_lines: bool = True) -> None:
    for ln in lines_of(db, q.id):
        if replace_lines:
            delete_obj(db, ln, user)
    for i, pl in enumerate(parsed.lines):
        create_obj(db, QuoteLine, {"quote_id": q.id, "position": i, "section": pl.section, "code": pl.code,
                                   "designation": pl.designation, "quantity": pl.quantity, "unit": pl.unit,
                                   "unit_price": pl.unit_price, "total_ht": pl.total_ht, "vat_rate": pl.vat_rate,
                                   "status": pl.status, "confidence": pl.confidence, "page": pl.page, "raw": pl.raw,
                                   "corrected": False}, user)
    qd = None
    if parsed.quote_date:
        try:
            qd = date.fromisoformat(parsed.quote_date)
        except ValueError:
            qd = None
    company = match_company(db, user.agency_id, parsed.company_name, parsed.siret)
    q.company_id = q.company_id or (company.id if company else None)
    q.company_name_raw = parsed.company_name
    q.reference, q.quote_date, q.validity_days = parsed.reference, qd, parsed.validity_days
    q.delay_text, q.delay_days, q.payment_terms = parsed.delay_text, parsed.delay_days, parsed.payment_terms
    q.conditions, q.exclusions, q.reserves, q.variants = parsed.conditions, parsed.exclusions, parsed.reserves, parsed.variants
    q.declared_ht, q.declared_tva, q.declared_ttc = parsed.declared_ht, parsed.declared_tva, parsed.declared_ttc
    q.extraction = {"method": parsed.method, "confidence": parsed.confidence, "warnings": parsed.warnings,
                    "siret": parsed.siret, "company_matched": bool(company), "at": utcnow().isoformat()}
    q.status = "a_verifier"
    db.flush()
    recompute(db, q)
    q.version += 1
    record_change(db, q, "update", user, {"extraction": parsed.method})


# ------------------------------------------------------------------ devis
@router.get("/quotes")
def list_quotes(project_id: str | None = None, lot_id: str | None = None, status: str | None = None,
                user: User = Depends(require("read")), db: Session = Depends(get_db)):
    q = scoped_query(db, Quote, user)
    if project_id:
        q = q.filter(Quote.project_id == project_id)
    if lot_id:
        q = q.filter(Quote.lot_id == lot_id)
    if status:
        q = q.filter(Quote.status == status)
    return [quote_out(db, x, with_lines=False) for x in q.order_by(Quote.created_at.desc()).all()]


@router.post("/quotes/import", status_code=201)
async def import_quotes(request: Request, files: list[UploadFile] = File(...), project_id: str = Form(...),
                        lot_id: str | None = Form(None), method: str = Form("regles"),
                        user: User = Depends(require("write")), db: Session = Depends(get_db)):
    check_project_access(db, user, project_id)
    project = db.get(Project, project_id)
    results = []
    for f in files:
        data = await f.read()
        items = [(f.filename or "devis", data)]
        if (f.filename or "").lower().endswith(".zip"):
            tmp = docsvc.temp_copy(data, ".zip")
            try:
                items = expand_zip(tmp)
            except (zipfile.BadZipFile, ValueError) as exc:
                raise HTTPException(422, f"Archive ZIP invalide : {exc}")
            finally:
                tmp.unlink(missing_ok=True)
        for name, content in items:
            doc, ex = docsvc.add_document(db, user, name, content, project_id=project_id, category="devis",
                                          confidential=project.confidential, linked={"lot_id": lot_id})
            q = create_obj(db, Quote, {"project_id": project_id, "lot_id": lot_id or None, "document_id": doc.id}, user, request)
            parsed = None
            if method == "ia":
                parsed = llm_extract(db, user, ex.text, project.confidential or doc.confidential)
            if parsed is None:
                parsed = parse_quote(ex)
            apply_parsed(db, user, q, parsed)
            doc.linked = {**(doc.linked or {}), "quote_id": q.id}
            results.append({"quote": quote_out(db, q), "extraction": ex.to_dict()})
    db.commit()
    return results


@router.get("/quotes/{quote_id}")
def get_quote(quote_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    return quote_out(db, get_owned(db, Quote, quote_id, user))


@router.post("/quotes", status_code=201)
def create_quote(payload: QuoteIn, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    q = create_obj(db, Quote, payload.model_dump(), user, request)
    recompute(db, q)
    db.commit()
    return quote_out(db, q)


@router.put("/quotes/{quote_id}")
def update_quote(quote_id: str, payload: dict, request: Request, user: User = Depends(require("write")),
                 db: Session = Depends(get_db)):
    q = get_owned(db, Quote, quote_id, user)
    version = payload.pop("version", None)
    if payload.get("status") in ("valide", "retenu", "rejete") and user.role not in ("admin", "manager"):
        raise HTTPException(403, "La validation d'un devis est réservée aux chefs de projet et administrateurs.")
    current = {k: v for k, v in to_dict(q).items() if k in QuoteIn.model_fields}
    current.update({k: v for k, v in payload.items() if k in QuoteIn.model_fields})
    update_obj(db, q, QuoteIn.model_validate(current).model_dump(), user, version, request)
    recompute(db, q)
    db.commit()
    return quote_out(db, q)


@router.delete("/quotes/{quote_id}")
def delete_quote(quote_id: str, request: Request, user: User = Depends(require("delete")), db: Session = Depends(get_db)):
    q = get_owned(db, Quote, quote_id, user)
    for ln in lines_of(db, q.id):
        delete_obj(db, ln, user)
    delete_obj(db, q, user, request)
    db.commit()
    return {"ok": True}


@router.put("/quotes/{quote_id}/lines")
def replace_lines(quote_id: str, payload: dict, request: Request, user: User = Depends(require("write")),
                  db: Session = Depends(get_db)):
    """Enregistre les corrections de l'éditeur de lignes (ajouts, modifications, suppressions)."""
    q = get_owned(db, Quote, quote_id, user)
    existing = {l.id: l for l in lines_of(db, q.id)}
    keep = set()
    allowed = {"inclus", "exclu", "optionnel", "variante", "a_verifier"}
    fields = ("position", "section", "code", "designation", "quantity", "unit", "unit_price", "total_ht", "vat_rate",
              "status", "dpgf_item_id")
    for i, row in enumerate(payload.get("lines") or []):
        if not str(row.get("designation") or "").strip():
            raise HTTPException(422, f"Ligne {i + 1} : la désignation est obligatoire.")
        if row.get("status") not in allowed:
            raise HTTPException(422, f"Ligne {i + 1} : statut invalide.")
        data = {k: row.get(k) for k in fields}
        data["position"] = i
        for k in ("quantity", "unit_price", "total_ht", "vat_rate"):
            if data[k] in ("", None):
                data[k] = None
            else:
                try:
                    data[k] = float(str(data[k]).replace(" ", "").replace(",", "."))
                except ValueError:
                    raise HTTPException(422, f"Ligne {i + 1} : valeur numérique invalide ({k}).")
        if data["vat_rate"] is not None and not 0 <= data["vat_rate"] <= 100:
            raise HTTPException(422, f"Ligne {i + 1} : le taux de TVA doit être compris entre 0 et 100 %.")
        lid = row.get("id")
        if lid and lid in existing:
            ln = existing[lid]
            before = {k: to_dict(ln).get(k) for k in fields}
            update_obj(db, ln, data, user, None, request)
            if any(before[k] != to_dict(ln).get(k) for k in fields if k != "position"):
                ln.corrected = True
                ln.confidence = 1.0
            keep.add(lid)
        else:
            ln = create_obj(db, QuoteLine, {**data, "quote_id": q.id, "corrected": True, "confidence": 1.0}, user, request)
            keep.add(ln.id)
    for lid, ln in existing.items():
        if lid not in keep:
            delete_obj(db, ln, user, request)
    db.flush()
    recompute(db, q)
    q.version += 1
    record_change(db, q, "update", user, {"lignes": "corrigées"})
    db.commit()
    return quote_out(db, q)


@router.post("/quotes/{quote_id}/reextract")
def reextract(quote_id: str, method: str = "regles", user: User = Depends(require("write")), db: Session = Depends(get_db)):
    q = get_owned(db, Quote, quote_id, user)
    if not q.document_id:
        raise HTTPException(409, "Ce devis n'est rattaché à aucun document source.")
    doc = get_owned(db, Document, q.document_id, user)
    ex = docsvc.extract_from_version(docsvc.current_version(db, doc))
    project = db.get(Project, q.project_id)
    parsed = llm_extract(db, user, ex.text, project.confidential or doc.confidential) if method == "ia" else parse_quote(ex)
    apply_parsed(db, user, q, parsed)
    db.commit()
    return quote_out(db, q)


@router.post("/quotes/{quote_id}/validate")
def validate_quote(quote_id: str, request: Request, user: User = Depends(require("validate")), db: Session = Depends(get_db)):
    q = get_owned(db, Quote, quote_id, user)
    recompute(db, q)
    q.status = "valide"
    q.validated_by, q.validated_at = user.id, utcnow()
    q.version += 1
    record_change(db, q, "update", user, {"status": "valide"})
    audit(db, user, "validate", "quotes", q.id, q.reference, request)
    db.commit()
    return quote_out(db, q)


@router.post("/quotes/{quote_id}/create-company")
def create_company_from_quote(quote_id: str, request: Request, user: User = Depends(require("write")),
                              db: Session = Depends(get_db)):
    q = get_owned(db, Quote, quote_id, user)
    if not q.company_name_raw:
        raise HTTPException(422, "Nom d'entreprise non détecté : créez la fiche manuellement.")
    siret = (q.extraction or {}).get("siret")
    c = create_obj(db, Company, {"name": q.company_name_raw, "siret": siret, "notes": "Fiche créée depuis un devis importé."},
                   user, request)
    q.company_id = c.id
    q.version += 1
    record_change(db, q, "update", user, {"company_id": c.id})
    db.commit()
    return quote_out(db, q)


# ------------------------------------------------------------------ DPGF / CCTP
@router.post("/dpgf/import", status_code=201)
async def import_dpgf(file: UploadFile = File(...), project_id: str = Form(...), lot_id: str | None = Form(None),
                      replace: bool = Form(True), user: User = Depends(require("write")), db: Session = Depends(get_db)):
    check_project_access(db, user, project_id)
    data = await file.read()
    doc, ex = docsvc.add_document(db, user, file.filename or "DPGF", data, project_id=project_id, category="dpgf")
    items = parse_dpgf(ex)
    if not items:
        raise HTTPException(422, "Aucune ligne de DPGF reconnue (colonnes attendues : désignation, unité, quantité).")
    if replace:
        q = db.query(DpgfItem).filter(DpgfItem.project_id == project_id, DpgfItem.deleted.is_(False))
        q = q.filter(DpgfItem.lot_id == lot_id) if lot_id else q.filter(DpgfItem.lot_id.is_(None))
        for it in q.all():
            delete_obj(db, it, user)
    for it in items:
        create_obj(db, DpgfItem, {**it, "project_id": project_id, "lot_id": lot_id or None, "source_document_id": doc.id}, user)
    db.commit()
    return {"count": len(items), "document_id": doc.id}


@router.post("/cctp/import", status_code=201)
async def import_cctp(file: UploadFile = File(...), project_id: str = Form(...), lot_id: str | None = Form(None),
                      user: User = Depends(require("write")), db: Session = Depends(get_db)):
    check_project_access(db, user, project_id)
    data = await file.read()
    doc, ex = docsvc.add_document(db, user, file.filename or "CCTP", data, project_id=project_id, category="cctp")
    reqs = parse_cctp(ex)
    q = db.query(CctpRequirement).filter(CctpRequirement.project_id == project_id, CctpRequirement.deleted.is_(False))
    q = q.filter(CctpRequirement.lot_id == lot_id) if lot_id else q.filter(CctpRequirement.lot_id.is_(None))
    for r in q.all():
        delete_obj(db, r, user)
    for r in reqs:
        create_obj(db, CctpRequirement, {**r, "project_id": project_id, "lot_id": lot_id or None, "document_id": doc.id}, user)
    db.commit()
    return {"count": len(reqs), "document_id": doc.id, "warnings": ex.warnings}


@router.get("/cctp")
def list_cctp(project_id: str, lot_id: str | None = None, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    q = scoped_query(db, CctpRequirement, user).filter(CctpRequirement.project_id == project_id)
    if lot_id:
        q = q.filter(CctpRequirement.lot_id == lot_id)
    return [to_dict(r) for r in q.order_by(CctpRequirement.article).all()]


# ------------------------------------------------------------------ comparaison
def _quote_payload(db: Session, q: Quote) -> dict:
    out = quote_out(db, q)
    return {"id": q.id, "company": out["company_name"] or f"Devis {q.reference or q.id[:6]}", "computed": q.computed or {},
            "anomalies": q.anomalies or [], "exclusions": q.exclusions or [], "reserves": q.reserves or [],
            "delay_days": q.delay_days, "delay_text": q.delay_text, "validity_days": q.validity_days, "lines": out["lines"]}


@router.post("/comparisons", status_code=201)
def run_comparison(payload: dict, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    project_id = payload.get("project_id")
    check_project_access(db, user, project_id)
    lot_id = payload.get("lot_id") or None
    ids = payload.get("quote_ids") or []
    if not ids:
        q = scoped_query(db, Quote, user).filter(Quote.project_id == project_id, Quote.status != "rejete")
        q = q.filter(Quote.lot_id == lot_id) if lot_id else q
        ids = [x.id for x in q.all()]
    if len(ids) < 2:
        raise HTTPException(422, "Sélectionnez au moins deux devis à comparer.")
    quotes = [get_owned(db, Quote, i, user) for i in ids]
    for q in quotes:
        recompute(db, q)
    ref_q = db.query(DpgfItem).filter(DpgfItem.project_id == project_id, DpgfItem.deleted.is_(False))
    ref_q = ref_q.filter(DpgfItem.lot_id == lot_id) if lot_id else ref_q
    reference = [to_dict(x) for x in ref_q.order_by(DpgfItem.position).all()] if payload.get("use_dpgf", True) else []
    cq = db.query(CctpRequirement).filter(CctpRequirement.project_id == project_id, CctpRequirement.deleted.is_(False))
    cq = cq.filter(CctpRequirement.lot_id == lot_id) if lot_id else cq
    cctp = [to_dict(x) for x in cq.all()] if payload.get("use_cctp", True) else []
    result = compare([_quote_payload(db, q) for q in quotes], reference, cctp)
    lot = db.get(Lot, lot_id) if lot_id else None
    lot_label = f"Lot {lot.code} {lot.name}" if lot else None
    conclusion = rule_based_conclusion(result, lot_label)
    source = "moteur_regles"
    if payload.get("use_ai"):
        project = db.get(Project, project_id)
        facts = {"lot": lot_label, "summaries": [{k: v for k, v in s.items() if k != "anomaly_details"} for s in result["summaries"]],
                 "ranking": result["ranking"], "cctp": result["cctp"][:20],
                 "rows": [{"designation": r["designation"], "cells": {result_s["company"]: {"statut": STATUS_LABELS[r["cells"][result_s["quote_id"]]["status"]],
                           "montant": r["cells"][result_s["quote_id"]]["amount"], "ecart": r["cells"][result_s["quote_id"]].get("deviation")}
                           for result_s in result["summaries"]}} for r in result["rows"][:120]]}
        text = ai_service.generate(db, user.agency_id, load_prompt("comparison_conclusion", facts=json.dumps(facts, ensure_ascii=False)),
                                   bool(project.confidential), max_tokens=3000)
        if text:
            conclusion = text + "\n\n---\n\n" + conclusion
            source = "ia+moteur_regles"
    title = payload.get("title") or f"Comparatif {lot_label or 'des offres'} – {date.today():%d/%m/%Y}"
    cmp = create_obj(db, Comparison, {"project_id": project_id, "lot_id": lot_id, "title": title, "quote_ids": ids,
                                      "result": result, "conclusion": conclusion, "conclusion_source": source}, user, request)
    db.commit()
    return to_dict(cmp)


@router.get("/comparisons")
def list_comparisons(project_id: str | None = None, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    q = scoped_query(db, Comparison, user)
    if project_id:
        q = q.filter(Comparison.project_id == project_id)
    return [{k: v for k, v in to_dict(c).items() if k != "result"} | {"companies": [s["company"] for s in (c.result or {}).get("summaries", [])]}
            for c in q.order_by(Comparison.created_at.desc()).all()]


@router.get("/comparisons/{cmp_id}")
def get_comparison(cmp_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    return to_dict(get_owned(db, Comparison, cmp_id, user))


@router.delete("/comparisons/{cmp_id}")
def delete_comparison(cmp_id: str, request: Request, user: User = Depends(require("delete")), db: Session = Depends(get_db)):
    delete_obj(db, get_owned(db, Comparison, cmp_id, user), user, request)
    db.commit()
    return {"ok": True}


STATUS_COLORS = {"inclus": "#DCE8DF", "non_inclus": "#F4D9D2", "non_renseigne": "#F3E9C9", "optionnel": "#DDE5F0",
                 "variante": "#E6DDF0", "non_comparable": "#E4E4E4", "a_verifier": "#F6E2C6"}


def comparison_blocks(db: Session, cmp: Comparison) -> tuple[list[dict], dict]:
    r = cmp.result
    summaries = r["summaries"]
    qids = [s["quote_id"] for s in summaries]
    blocks: list[dict] = [{"type": "h2", "text": "Synthèse des offres"}]
    blocks.append({"type": "table", "sheet": "Synthèse",
                   "columns": ["Entreprise", "Total HT", "Total TTC", "Périmètre comparable HT", "Inclus", "Non renseignés",
                               "Exclus", "Options", "Variantes", "À vérifier", "Délai (j)", "Anomalies", "Score", "Rang"],
                   "rows": [], "raw_rows": []})
    rank = {x["quote_id"]: x for x in r["ranking"]}
    for s in summaries:
        c = s["counts"]
        row = [s["company"], s["total_ht"], s["total_ttc"], s["adjusted_ht"], c["inclus"], c["non_renseigne"], c["non_inclus"],
               c["optionnel"], c["variante"], c["a_verifier"] + c["non_comparable"], s["delay_days"], s["anomalies"],
               rank[s["quote_id"]]["score"], rank[s["quote_id"]]["rank"]]
        blocks[-1]["raw_rows"].append(row)
        blocks[-1]["rows"].append([row[0], exports.eur(row[1]), exports.eur(row[2]), exports.eur(row[3])] + [("" if v is None else str(v)) for v in row[4:]])
    blocks[-1]["number_formats"] = [None, "#,##0.00 €", "#,##0.00 €", "#,##0.00 €"]
    cols = ["Code", "Désignation", "Unité", "Qté réf."]
    for s in summaries:
        cols += [f"{s['company'][:22]} – statut", f"{s['company'][:22]} – montant HT", f"{s['company'][:22]} – écart"]
    cols += ["Médiane HT"]
    table = {"type": "table", "sheet": "Comparatif détaillé", "columns": cols, "rows": [], "raw_rows": [], "cell_colors": []}
    for i, row in enumerate(r["rows"]):
        raw = [row.get("code") or "", row["designation"], row.get("unit") or "", row.get("quantity")]
        for j, qid in enumerate(qids):
            c = row["cells"][qid]
            raw += [STATUS_LABELS[c["status"]], c["amount"], (round(c["deviation"] * 100, 1) if c.get("deviation") is not None else None)]
            table["cell_colors"].append((i, 4 + j * 3, STATUS_COLORS[c["status"]]))
            if c.get("flag"):
                table["cell_colors"].append((i, 6 + j * 3, "#F4D9D2"))
        raw.append(row.get("median"))
        table["raw_rows"].append(raw)
        disp = []
        for k, v in enumerate(raw):
            if v is None:
                disp.append("")
            elif k >= 4 and (k == len(raw) - 1 or (k - 4) % 3 == 1):
                disp.append(exports.eur(v))
            elif k >= 4 and (k - 4) % 3 == 2:
                disp.append(f"{v:+.0f} %")
            elif isinstance(v, float):
                disp.append(f"{v:g}".replace(".", ","))
            else:
                disp.append(str(v))
        table["rows"].append(disp)
    blocks += [{"type": "h2", "text": "Tableau comparatif détaillé"},
               {"type": "note", "text": "Légende : Inclus · Non inclus (exclu expressément par l'entreprise) · Non renseigné "
                                        "(absent de l'offre, sans mention d'exclusion) · Optionnel · Variante · Non comparable · "
                                        "À vérifier. Écart en % par rapport à la médiane des offres incluses."}, table]
    if r.get("cctp"):
        blocks.append({"type": "h2", "text": "Contrôle des exigences du CCTP"})
        blocks.append({"type": "table", "sheet": "CCTP", "columns": ["Article", "Intitulé"] + [s["company"][:25] for s in summaries],
                       "rows": [[c["article"], c["title"]] + [c["quotes"][q]["message"] for q in qids] for c in r["cctp"]]})
    opt = r.get("optimization")
    if opt:
        blocks.append({"type": "h2", "text": "Coût réel probable et optimisation à qualité constante"})
        cols = ["Entreprise", "Total HT annoncé", "Coûts cachés HT", "Coût réel probable HT", "Économies négociables HT",
                "Objectif HT", "Écarts de qualité"]
        raw = [[o["company"], o["total_ht"], o["hidden_costs_ht"], o["probable_cost_ht"], o["negotiable_ht"], o["target_cost_ht"],
                o["quality_issues"]] for o in opt["offers"]]
        blocks.append({"type": "table", "sheet": "Optimisation", "columns": cols, "raw_rows": raw,
                       "number_formats": [None] + ["#,##0.00 €"] * 5,
                       "rows": [[x[0]] + [exports.eur(v) for v in x[1:6]] + [str(x[6])] for x in raw]})
        lev = [[o["company"], lv["designation"], lv["amount_ht"], lv["target_ht"], lv["saving_ht"], lv["text"]]
               for o in opt["offers"] for lv in o["levers"]]
        if lev:
            blocks.append({"type": "table", "sheet": "Leviers de négociation",
                           "columns": ["Entreprise", "Poste", "Montant HT", "Cible HT", "Économie HT", "Motif"], "raw_rows": lev,
                           "number_formats": [None, None, "#,##0.00 €", "#,##0.00 €", "#,##0.00 €"],
                           "rows": [[x[0], x[1], exports.eur(x[2]), exports.eur(x[3]), exports.eur(x[4]), x[5]] for x in lev]})
        sev = {"haute": "Haute", "moyenne": "Moyenne", "info": "Info"}
        cat = {"qualite": "Qualité", "quantite": "Quantité", "prix": "Prix", "perimetre": "Périmètre",
               "conditions": "Conditions", "calcul": "Calcul"}
        rem = [[sev[x["severity"]], cat.get(x["category"], x["category"]), x["company"] or "Toutes", x["designation"] or "",
                x["message"], x["action"]] for x in opt["remarks"]]
        if rem:
            blocks.append({"type": "h2", "text": "Remarques techniques"})
            blocks.append({"type": "table", "sheet": "Remarques techniques",
                           "columns": ["Gravité", "Thème", "Entreprise", "Poste", "Constat", "Action recommandée"],
                           "rows": rem, "raw_rows": rem})
    blocks += [{"type": "h2", "text": "Conclusion"}, {"type": "markdown", "text": cmp.conclusion or ""}]
    agency = db.get(Agency, cmp.agency_id)
    project = db.get(Project, cmp.project_id)
    meta = {"agency": agency.name if agency else "", "landscape": True, "demo": bool(agency and agency.is_demo),
            "subtitle": f"Projet {project.code} – {project.name}" if project else None}
    return blocks, meta


@router.get("/comparisons/{cmp_id}/export")
def export_comparison(cmp_id: str, fmt: str = "xlsx", user: User = Depends(require("read")), db: Session = Depends(get_db)):
    cmp = get_owned(db, Comparison, cmp_id, user)
    blocks, meta = comparison_blocks(db, cmp)
    data, mime = exports.render(fmt, cmp.title, blocks, meta)
    name = re.sub(r"[^\w-]+", "_", cmp.title)[:80] + "." + fmt
    from .documents import _disposition

    return Response(data, media_type=mime, headers={"Content-Disposition": _disposition("attachment", name)})
