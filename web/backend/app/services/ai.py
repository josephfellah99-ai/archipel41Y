"""Service IA : choix du fournisseur, garde-fous de confidentialité, RAG et assistant."""
from __future__ import annotations

import json
from datetime import date

from sqlalchemy.orm import Session

from ai.llm.providers import AIError, NoProvider, Provider, build_provider
from ai.prompts import load as load_prompt
from ai.rag.engine import LOCAL_MODEL, hybrid_rank, local_embed

from ..crud import scoped_query, to_dict
from ..models import (Agency, Company, Document, DocumentChunk, Event, Incident, Lot, Project, Quote, Task, User)
from . import settings_store


def get_config(db: Session, agency_id: str) -> dict:
    return settings_store.get(db, agency_id, "ai")


def get_provider(db: Session, agency_id: str) -> Provider:
    return build_provider(get_config(db, agency_id))


def get_embedder(db: Session, agency_id: str):
    p = get_provider(db, agency_id)
    return p if p.supports_embeddings and p.available else None


def status(db: Session, agency_id: str) -> dict:
    cfg = get_config(db, agency_id)
    p = build_provider(cfg)
    return {**p.describe(), "model": getattr(p, "model", None), "allow_documents": cfg.get("allow_documents", True),
            "allow_confidential": cfg.get("allow_confidential", False),
            "mode": "generatif" if p.available else "sans_ia_generative"}


def may_send(db: Session, agency_id: str, confidential: bool) -> tuple[bool, str | None]:
    """Peut-on transmettre ce contenu au fournisseur configuré ?"""
    cfg = get_config(db, agency_id)
    p = get_provider(db, agency_id)
    if not p.available:
        return False, "Aucun fournisseur d'IA générative configuré."
    if not p.external:
        return True, None  # modèle local : les données ne quittent pas l'infrastructure
    if not cfg.get("allow_documents", True):
        return False, "L'envoi de documents à un fournisseur externe est désactivé dans les paramètres."
    if confidential and not cfg.get("allow_confidential", False):
        return False, ("Contenu confidentiel : l'envoi à un fournisseur d'IA externe n'est pas autorisé "
                       "(Paramètres › Intelligence artificielle).")
    return True, None


def retrieve(db: Session, user: User, query: str, project_id: str | None = None, k: int = 8,
             exclude_confidential: bool = False) -> list[dict]:
    q = scoped_query(db, Document, user)
    if project_id:
        q = q.filter(Document.project_id == project_id)
    docs = {d.id: d for d in q.all()}
    if not docs:
        return []
    cq = db.query(DocumentChunk).filter(DocumentChunk.agency_id == user.agency_id,
                                        DocumentChunk.document_id.in_(list(docs)))
    if exclude_confidential:
        cq = cq.filter(DocumentChunk.confidential.is_(False))
    if db.bind.dialect.name == "postgresql":
        # PostgreSQL : présélection en base par similarité vectorielle (pgvector, opérateur <=>)
        # et par recherche plein texte française (index GIN), puis classement hybride.
        from sqlalchemy import text as sql

        qv = "[" + ",".join(f"{x:.6f}" for x in local_embed(query)) + "]"
        params = {"a": user.agency_id, "docs": list(docs), "q": qv, "m": LOCAL_MODEL, "t": query}
        ids = {r[0] for r in db.execute(sql(
            "select id from document_chunks where agency_id = :a and document_id = any(:docs) and embedding_model = :m "
            "order by embedding <=> cast(:q as vector) limit 80"), params)}
        ids |= {r[0] for r in db.execute(sql(
            "select id from document_chunks where agency_id = :a and document_id = any(:docs) and "
            "to_tsvector('french', text) @@ plainto_tsquery('french', :t) "
            "order by ts_rank(to_tsvector('french', text), plainto_tsquery('french', :t)) desc limit 80"), params)}
        ids |= {r[0] for r in db.execute(sql(
            "select id from document_chunks where agency_id = :a and document_id = any(:docs) and embedding_model <> :m limit 200"), params)}
        cq = cq.filter(DocumentChunk.id.in_(ids)) if ids else cq.filter(False)
    chunks = cq.all()
    models = {c.embedding_model for c in chunks}
    qvecs = {}
    if LOCAL_MODEL in models:
        qvecs[LOCAL_MODEL] = local_embed(query)
    for m in models - {LOCAL_MODEL}:
        emb = get_embedder(db, user.agency_id)
        if emb:
            try:
                qvecs[m] = emb.embed([query])[0]
            except Exception:
                pass
    cands = []
    for c in chunks:
        d = docs[c.document_id]
        cands.append({"text": c.text, "embedding": c.embedding if c.embedding_model in qvecs else None,
                      "_model": c.embedding_model, "document_id": d.id, "document": d.name, "page": c.page,
                      "project_id": d.project_id, "confidential": c.confidential, "category": d.category})
    # rang séparé par modèle d'embedding puis fusion
    ranked = []
    for m in models:
        sub = [c for c in cands if c["_model"] == m]
        ranked += hybrid_rank(query, sub, qvecs.get(m), k)
    for c in ranked:  # les rapports générés sont des documents dérivés : on privilégie les pièces sources
        if c["category"] == "rapport":
            c["score"] = round(c["score"] * 0.6, 4)
    ranked.sort(key=lambda c: c["score"], reverse=True)
    out = []
    for c in ranked[:k]:
        c.pop("embedding", None)
        c.pop("_model", None)
        out.append(c)
    return out


def project_context(db: Session, user: User, project_id: str) -> tuple[str, bool]:
    p = db.get(Project, project_id)
    if not p or p.agency_id != user.agency_id:
        return "", False
    lots = db.query(Lot).filter(Lot.project_id == p.id, Lot.deleted.is_(False)).all()
    companies = {c.id: c.name for c in db.query(Company).filter(Company.agency_id == user.agency_id)}
    quotes = db.query(Quote).filter(Quote.project_id == p.id, Quote.deleted.is_(False)).all()
    tasks = db.query(Task).filter(Task.project_id == p.id, Task.deleted.is_(False)).order_by(Task.start_date).limit(40).all()
    incidents = db.query(Incident).filter(Incident.project_id == p.id, Incident.deleted.is_(False)).limit(20).all()
    events = (db.query(Event).filter(Event.project_id == p.id, Event.deleted.is_(False))
              .order_by(Event.start.desc()).limit(10).all())
    lines = [f"PROJET {p.code} – {p.name} ({p.status}), phase actuelle : {p.current_phase or 'n.c.'}, "
             f"avancement {p.progress} %, adresse : {p.address or ''} {p.postal_code or ''} {p.city or ''}.",
             f"Budget initial : {float(p.budget_initial or 0):,.2f} € HT. Surface : {p.surface_m2 or 'n.c.'} m².".replace(",", " "),
             f"Programme : {p.program or 'n.c.'}. Description : {(p.description or '')[:600]}"]
    if p.terrain:
        lines.append("Terrain : " + json.dumps(p.terrain, ensure_ascii=False)[:800])
    for l in lots:
        lines.append(f"Lot {l.code} {l.name} : statut {l.status}, budget {float(l.budget or 0):.2f} €, "
                     f"entreprise {companies.get(l.company_id, 'non attribué')}")
    for q in quotes:
        c = q.computed or {}
        lines.append(f"Devis {q.reference or q.id[:8]} de {companies.get(q.company_id) or q.company_name_raw} : "
                     f"{c.get('total_ht')} € HT (calcul moteur), statut {q.status}, {len(q.anomalies or [])} anomalie(s).")
    for t in tasks:
        lines.append(f"Tâche « {t.name} » du {t.start_date} ({t.duration_days} j), avancement {t.progress} %.")
    for i in incidents:
        lines.append(f"Incident {i.date} [{i.severity}/{i.status}] : {i.title}")
    for e in events:
        lines.append(f"Rendez-vous {e.start:%d/%m/%Y %H:%M} : {e.title}" + (f" — CR : {e.minutes[:300]}" if e.minutes else ""))
    return "\n".join(lines), bool(p.confidential)


def answer(db: Session, user: User, question: str, project_id: str | None = None, history: list[dict] | None = None) -> dict:
    """Réponse de l'assistant : RAG + contexte projet ; repli extractif sans IA générative."""
    agency = db.get(Agency, user.agency_id)
    ctx_text, project_conf = ("", False)
    if project_id:
        ctx_text, project_conf = project_context(db, user, project_id)
    # Recherche locale : tous les documents accessibles, y compris confidentiels (rien ne quitte le poste)
    passages = retrieve(db, user, question, project_id, k=8)
    sources = [{"ref": f"S{i + 1}", "document_id": p["document_id"], "document": p["document"], "page": p["page"],
                "excerpt": p["text"][:400], "score": p["score"], "confidential": p["confidential"]} for i, p in enumerate(passages)]
    allowed, reason = may_send(db, user.agency_id, project_conf)
    provider = get_provider(db, user.agency_id)
    if allowed and provider.available:
        ok_conf, _ = may_send(db, user.agency_id, True)
        if not ok_conf:  # fournisseur externe : seuls les extraits non confidentiels sont transmis
            kept = [(s, p) for s, p in zip(sources, passages) if not p["confidential"]]
            sources = [dict(s, ref=f"S{i + 1}") for i, (s, _) in enumerate(kept)]
            passages = [p for _, p in kept]
        system = load_prompt("assistant_system", agency=agency.name if agency else "agence",
                             today=date.today().strftime("%d/%m/%Y"), user=user.full_name)
        ctx = "CONTEXTE DU PROJET :\n" + (ctx_text or "(aucun projet sélectionné)") + "\n\nEXTRAITS DE DOCUMENTS :\n"
        ctx += "\n\n".join(f"[{s['ref']}] {s['document']} (p. {s['page'] or '?'}) :\n{p['text']}"
                           for s, p in zip(sources, passages)) or "(aucun extrait pertinent)"
        msgs = list(history or [])[-8:] + [{"role": "user", "content": ctx + "\n\nQUESTION : " + question}]
        try:
            res = provider.chat(system, msgs, max_tokens=4000)
            return {"answer": res.text, "sources": sources, "mode": "generatif", "provider": res.provider,
                    "model": res.model}
        except AIError as exc:
            reason = str(exc)
    # Repli : réponse extractive (aucun texte généré, uniquement des passages sourcés)
    if sources:
        body = ["**Mode sans IA générative** — voici les passages les plus pertinents trouvés dans vos documents :", ""]
        for s in sources[:5]:
            page = f", p. {s['page']}" if s["page"] else ""
            body.append(f"- **[{s['ref']}] {s['document']}**{page} : « {s['excerpt'][:280].strip()}… »")
    else:
        body = ["**Mode sans IA générative** — aucun passage pertinent n'a été trouvé dans les documents accessibles."]
    if ctx_text and not sources:
        body += ["", "Données du projet disponibles :", ctx_text[:1500]]
    if reason:
        body += ["", f"_{reason}_"]
    return {"answer": "\n".join(body), "sources": sources, "mode": "extractif", "provider": None, "model": None}


def generate(db: Session, agency_id: str, prompt: str, confidential: bool, max_tokens: int = 3000,
             system: str = "Tu es un assistant expert pour une agence d'architecture française. Réponds en français.") -> str | None:
    """Génération courte (conclusions, synthèses). None si l'IA n'est pas disponible/autorisée."""
    allowed, _ = may_send(db, agency_id, confidential)
    if not allowed:
        return None
    try:
        return get_provider(db, agency_id).chat(system, [{"role": "user", "content": prompt}], max_tokens).text
    except AIError:
        return None
