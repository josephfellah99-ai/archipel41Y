"""Module 08 – Bibliothèque documentaire."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from urllib.parse import quote as urlquote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ai.document_analysis.extract import expand_zip

from ..crud import create_obj, delete_obj, get_owned, scoped_query, to_dict, update_obj
from ..db import get_db
from ..models import ChangeLog, Document, DocumentAnnotation, DocumentChunk, DocumentVersion, Project, User
from ..schemas import DOC_CATEGORIES, DocumentPatch
from ..security import module_level, require
from ..services import ai as ai_service
from ..services import documents as docsvc
from ..services import referentiel, storage, viewers

router = APIRouter(prefix="/api/documents", tags=["documents"])


def doc_out(db: Session, d: Document) -> dict:
    out = to_dict(d)
    out["versions_count"] = d.current_version
    return out


@router.get("/categories")
def categories(user: User = Depends(require("read"))):
    return DOC_CATEGORIES


@router.get("")
def list_documents(project_id: str | None = None, category: str | None = None, q: str | None = None,
                   tag: str | None = None, folder: str | None = None, status: str | None = None, limit: int = 500,
                   user: User = Depends(require("read")), db: Session = Depends(get_db)):
    query = scoped_query(db, Document, user)
    if folder == "__none__":
        query = query.filter(or_(Document.folder.is_(None), Document.folder == ""))
    elif folder:
        query = query.filter(or_(Document.folder == folder, Document.folder.like(folder.rstrip("/") + "/%")))
    if status:
        query = query.filter(Document.status == status)
    if project_id == "none":
        query = query.filter(Document.project_id.is_(None))
    elif project_id:
        query = query.filter(Document.project_id == project_id)
    if category:
        query = query.filter(Document.category == category)
    if q:
        like = f"%{q}%"
        ids = [r[0] for r in db.query(DocumentVersion.document_id).filter(
            DocumentVersion.agency_id == user.agency_id, DocumentVersion.text.ilike(like)).limit(500)]
        query = query.filter(or_(Document.name.ilike(like), Document.description.ilike(like), Document.id.in_(ids)))
    rows = query.order_by(Document.updated_at.desc()).limit(min(limit, 2000)).all()
    if tag:
        rows = [r for r in rows if tag in (r.tags or [])]
    return [doc_out(db, d) for d in rows]


@router.post("/upload", status_code=201)
async def upload(request: Request, files: list[UploadFile] = File(...), project_id: str | None = Form(None),
                 category: str | None = Form(None), confidential: bool = Form(False), tags: str | None = Form(None),
                 expand_archives: bool = Form(True), user: User = Depends(require("write")), db: Session = Depends(get_db)):
    created, report = [], []
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    for f in files:
        data = await f.read()
        items = [(f.filename or "fichier", data)]
        if expand_archives and (f.filename or "").lower().endswith(".zip"):
            tmp = docsvc.temp_copy(data, ".zip")
            try:
                items = expand_zip(tmp)
            except (zipfile.BadZipFile, ValueError) as exc:
                raise HTTPException(422, f"Archive ZIP invalide : {exc}")
            finally:
                tmp.unlink(missing_ok=True)
        for name, content in items:
            doc, ex = docsvc.add_document(db, user, name, content, project_id=project_id or None, category=category,
                                          confidential=confidential, tags=tag_list)
            created.append(doc_out(db, doc))
            report.append({"document_id": doc.id, "name": doc.name, **ex.to_dict(), **_advice(db, doc, ex.text)})
    db.commit()
    return {"documents": created, "extraction": report}


@router.get("/search")
def search(q: str, project_id: str | None = None, k: int = 10, user: User = Depends(require("read")),
           db: Session = Depends(get_db)):
    """Recherche sémantique + lexicale (RAG) dans le contenu des documents."""
    return ai_service.retrieve(db, user, q, project_id, k=min(k, 30))


def _advice(db: Session, d: Document, text: str | None = None) -> dict:
    """Suggestion de dossier (jamais appliquée d'office) et contrôle du nom selon les conventions de l'agence."""
    p = db.get(Project, d.project_id) if d.project_id else None
    sug = referentiel.suggest_folder(d.name, d.description, text, d.category, p.status if p else None, d.extension) if p else None
    if sug and (sug["folder"] == (d.folder or "") or sug["folder"] == (d.linked or {}).get("suggestion_refusee")):
        sug = None
    return {"suggestion": sug, "nommage": referentiel.check_name(d.name)}


@router.get("/tree")
def tree(project_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    """Arborescence type ARCHIPEL 41 du projet, avec le nombre de documents par dossier."""
    from ..security import check_project_access

    check_project_access(db, user, project_id)
    docs = scoped_query(db, Document, user).filter(Document.project_id == project_id).with_entities(Document.folder).all()
    counts: dict[str, int] = {}
    unfiled = 0
    for (f,) in docs:
        if not f:
            unfiled += 1
            continue
        counts[f] = counts.get(f, 0) + 1
    tpl = referentiel.template()
    known = referentiel.folder_paths()
    out = [{**x, "count": counts.get(x["path"], 0),
            "total": sum(n for k, n in counts.items() if k == x["path"] or k.startswith(x["path"] + "/"))} for x in tpl["dossiers"]]
    custom = [{"path": k, "label": k.split("/")[-1], "fonction": "Dossier propre à ce projet", "note": None, "count": n, "total": n,
               "custom": True} for k, n in sorted(counts.items()) if k not in known]
    return {"name": tpl["nom"], "version": tpl["version"], "conventions": tpl["conventions"], "folders": out + custom,
            "unfiled": unfiled, "total": len(docs)}


@router.put("/annotations/{aid}")
def update_annotation(aid: str, payload: dict, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    a = get_owned(db, DocumentAnnotation, aid, user)
    _can_edit_annotation(user, a)
    data = {k: v for k, v in payload.items() if k in ("text", "resolved", "geometry", "color", "kind")}
    if "geometry" in data:
        data["geometry"] = _geometry(data["geometry"])
    if "text" in data:
        data["text"] = (data["text"] or "").strip()[:2000] or None
    update_obj(db, a, data, user, payload.get("version"), request)
    db.commit()
    return _annotation_out(db, a)


@router.delete("/annotations/{aid}")
def delete_annotation(aid: str, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    a = get_owned(db, DocumentAnnotation, aid, user)
    _can_edit_annotation(user, a)
    delete_obj(db, a, user, request)
    db.commit()
    return {"ok": True}


def _can_edit_annotation(user: User, a: DocumentAnnotation) -> None:
    if a.author_id != user.id and module_level(user, "documents") != "full":
        raise HTTPException(403, "Seuls l'auteur de l'annotation, les gestionnaires et les administrateurs peuvent la modifier.")


def _geometry(g) -> dict:
    try:
        out = {k: float(g[k]) for k in ("x", "y") }
        out["w"], out["h"] = float(g.get("w", 0) or 0), float(g.get("h", 0) or 0)
    except (TypeError, KeyError, ValueError):
        raise HTTPException(422, "Position de l'annotation invalide.")
    if not all(0 <= out[k] <= 1 for k in ("x", "y")) or not (0 <= out["w"] <= 1 and 0 <= out["h"] <= 1) \
            or out["x"] + out["w"] > 1.0001 or out["y"] + out["h"] > 1.0001:
        raise HTTPException(422, "L'annotation doit rester dans les limites de la page.")
    return out


def _annotation_out(db: Session, a: DocumentAnnotation) -> dict:
    out = to_dict(a)
    u = db.get(User, a.author_id) if a.author_id else None
    out["author"] = u.full_name if u else "—"
    return out


@router.get("/{doc_id}")
def get_document(doc_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    d = get_owned(db, Document, doc_id, user)
    out = doc_out(db, d)
    out["versions"] = [to_dict(v) | {"text": None, "has_file": storage.exists(v.storage_key)} for v in
                       db.query(DocumentVersion).filter(DocumentVersion.document_id == d.id, DocumentVersion.deleted.is_(False))
                       .order_by(DocumentVersion.number.desc())]
    return out


@router.put("/{doc_id}")
def patch_document(doc_id: str, payload: dict, request: Request, user: User = Depends(require("write")),
                   db: Session = Depends(get_db)):
    d = get_owned(db, Document, doc_id, user)
    version = payload.pop("version", None)
    data = DocumentPatch.model_validate(payload).model_dump(exclude_unset=True)
    if "status" in data and data["status"] != d.status and data["status"] in ("valide", "archive"):
        from ..security import module_level

        if module_level(user, "documents") != "full":
            raise HTTPException(403, "La validation et l'archivage des documents sont réservés aux gestionnaires et administrateurs.")
    if "folder" in data:
        data["folder"] = (data["folder"] or "").strip().strip("/") or None
    if data.get("related_ids"):
        ok = {x.id for x in db.query(Document).filter(Document.id.in_(data["related_ids"]), Document.agency_id == user.agency_id,
                                                      Document.deleted.is_(False))}
        data["related_ids"] = [x for x in data["related_ids"] if x in ok and x != d.id]
    update_obj(db, d, data, user, version, request)
    if "confidential" in data or "project_id" in data:
        from ..models import DocumentChunk

        db.query(DocumentChunk).filter(DocumentChunk.document_id == d.id).update(
            {"confidential": d.confidential, "project_id": d.project_id})
    db.commit()
    return doc_out(db, d)


@router.delete("/{doc_id}")
def delete_document(doc_id: str, request: Request, user: User = Depends(require("delete")), db: Session = Depends(get_db)):
    d = get_owned(db, Document, doc_id, user)
    delete_obj(db, d, user, request)
    from ..models import DocumentChunk

    db.query(DocumentChunk).filter(DocumentChunk.document_id == d.id).delete()
    db.commit()
    return {"ok": True}


@router.post("/{doc_id}/versions", status_code=201)
async def new_version(doc_id: str, file: UploadFile = File(...), comment: str | None = Form(None),
                      user: User = Depends(require("write")), db: Session = Depends(get_db)):
    d = get_owned(db, Document, doc_id, user)
    data = await file.read()
    if Path(file.filename or "").suffix.lower() != Path(d.name).suffix.lower():
        raise HTTPException(422, "La nouvelle version doit avoir le même format que le document d'origine.")
    doc, ex = docsvc.add_document(db, user, file.filename or d.name, data, existing=d, comment=comment)
    db.commit()
    return {"document": doc_out(db, doc), "extraction": ex.to_dict()}


def _version(db: Session, d: Document, number: int | None) -> DocumentVersion:
    q = db.query(DocumentVersion).filter(DocumentVersion.document_id == d.id, DocumentVersion.deleted.is_(False))
    v = q.filter(DocumentVersion.number == (number or d.current_version)).first()
    if not v:
        raise HTTPException(404, "Version introuvable.")
    if not storage.exists(v.storage_key):
        raise HTTPException(409, "Fichier non encore synchronisé sur cet appareil.")
    return v


def _disposition(kind: str, filename: str) -> str:
    ascii_name = filename.encode("ascii", "ignore").decode() or "document"
    return f'{kind}; filename="{ascii_name}"; filename*=UTF-8\'\'{urlquote(filename)}'


@router.get("/{doc_id}/download")
def download(doc_id: str, version: int | None = None, inline: bool = False, user: User = Depends(require("read")),
             db: Session = Depends(get_db)):
    d = get_owned(db, Document, doc_id, user)
    v = _version(db, d, version)
    return FileResponse(storage.path_for(v.storage_key), media_type=d.mime or "application/octet-stream",
                        headers={"Content-Disposition": _disposition("inline" if inline else "attachment", v.filename),
                                 "X-Content-Type-Options": "nosniff",
                                 "Content-Security-Policy": "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"})


@router.get("/{doc_id}/pages")
def page_count(doc_id: str, version: int | None = None, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    d = get_owned(db, Document, doc_id, user)
    v = _version(db, d, version)
    if (d.extension or "").lower() != "pdf":
        return {"pages": 0}
    from ai.document_analysis.pdfium_safe import page_count as _count

    return {"pages": _count(storage.path_for(v.storage_key))}


@router.get("/{doc_id}/page/{n}")
def page_image(doc_id: str, n: int, version: int | None = None, scale: float = 1.6, user: User = Depends(require("read")),
               db: Session = Depends(get_db)):
    """Aperçu d'une page PDF rendue en image côté serveur (fiable sans visionneuse PDF)."""
    d = get_owned(db, Document, doc_id, user)
    v = _version(db, d, version)
    from ai.document_analysis.pdfium_safe import render_png

    try:
        png = render_png(storage.path_for(v.storage_key), n, scale)
    except IndexError:
        raise HTTPException(404, "Page inexistante.")
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{doc_id}/text")
def text(doc_id: str, version: int | None = None, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    d = get_owned(db, Document, doc_id, user)
    q = db.query(DocumentVersion).filter(DocumentVersion.document_id == d.id,
                                         DocumentVersion.number == (version or d.current_version))
    v = q.first()
    return {"text": (v.text if v else None) or "", "status": d.text_status}


@router.post("/{doc_id}/reindex")
def reindex(doc_id: str, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    d = get_owned(db, Document, doc_id, user)
    v = _version(db, d, None)
    ex = docsvc.extract_from_version(v)
    v.text = ex.text or None
    d.text_status = ex.status
    n = docsvc.index_document(db, d, v, ex, ai_service.get_embedder(db, user.agency_id))
    db.commit()
    return {"chunks": n, **ex.to_dict()}


@router.get("/{doc_id}/history")
def history(doc_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    d = get_owned(db, Document, doc_id, user, allow_deleted=True)
    names = {u.id: u.full_name for u in db.query(User).filter(User.agency_id == user.agency_id)}
    rows = db.query(ChangeLog).filter(ChangeLog.entity_id == d.id).order_by(ChangeLog.seq.desc()).limit(100)
    return [{"op": r.op, "at": r.at.isoformat(), "user": names.get(r.user_id, "—"), "changes": r.changes} for r in rows]


@router.post("/export")
def export_zip(payload: dict, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    """Export groupé (ZIP) d'une sélection de documents."""
    ids = payload.get("ids") or []
    if not ids or len(ids) > 500:
        raise HTTPException(422, "Sélectionnez entre 1 et 500 documents.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        used = set()
        for i in ids:
            d = get_owned(db, Document, i, user)
            v = _version(db, d, None)
            name = v.filename
            while name in used:
                name = f"{Path(name).stem}_{d.id[:4]}{Path(name).suffix}"
            used.add(name)
            zf.write(storage.path_for(v.storage_key), name)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="documents_archipel41.zip"'})


@router.get("/{doc_id}/view")
def view(doc_id: str, version: int | None = None, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    """Visionneuse structurée (tableur, Word, plan DXF, maquette IFC) — lecture seule, l'original n'est pas modifié."""
    d = get_owned(db, Document, doc_id, user)
    ext = (d.extension or "").lower()
    if ext not in viewers.VIEWABLE:
        raise HTTPException(415, f"Pas de visionneuse intégrée pour le format .{ext}.")
    v = _version(db, d, version)
    data = Path(storage.path_for(v.storage_key)).read_bytes()
    if len(data) > 60 * 1024 * 1024:
        raise HTTPException(413, "Fichier trop volumineux pour l'aperçu intégré : téléchargez-le pour l'ouvrir.")
    try:
        return viewers.view(ext, data)
    except viewers.ViewError as exc:
        raise HTTPException(422, str(exc))


@router.get("/{doc_id}/advice")
def advice(doc_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    """Suggestion de classement et contrôle du nom (conseils : rien n'est déplacé ni renommé automatiquement)."""
    d = get_owned(db, Document, doc_id, user)
    v = db.query(DocumentVersion).filter(DocumentVersion.document_id == d.id, DocumentVersion.number == d.current_version).first()
    return _advice(db, d, v.text if v else None)


@router.get("/{doc_id}/annotations")
def list_annotations(doc_id: str, version: int | None = None, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    d = get_owned(db, Document, doc_id, user)
    rows = (db.query(DocumentAnnotation).filter(DocumentAnnotation.agency_id == user.agency_id, DocumentAnnotation.document_id == d.id,
                                                DocumentAnnotation.version_number == (version or d.current_version),
                                                DocumentAnnotation.deleted.is_(False))
            .order_by(DocumentAnnotation.page, DocumentAnnotation.created_at))
    return [_annotation_out(db, a) for a in rows]


@router.post("/{doc_id}/annotations", status_code=201)
def add_annotation(doc_id: str, payload: dict, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    d = get_owned(db, Document, doc_id, user)
    ver = int(payload.get("version_number") or d.current_version)
    if not db.query(DocumentVersion).filter(DocumentVersion.document_id == d.id, DocumentVersion.number == ver,
                                            DocumentVersion.deleted.is_(False)).first():
        raise HTTPException(404, "Version introuvable.")
    page = int(payload.get("page") or 1)
    if page < 1 or (d.page_count and page > d.page_count):
        raise HTTPException(422, "Page inexistante.")
    kind = payload.get("kind") or "zone"
    if kind not in ("zone", "repere", "note"):
        raise HTTPException(422, "Type d'annotation inconnu.")
    text = (payload.get("text") or "").strip()[:2000]
    if not text:
        raise HTTPException(422, "Saisissez le texte de l'annotation.")
    a = create_obj(db, DocumentAnnotation, {"document_id": d.id, "project_id": d.project_id, "version_number": ver, "page": page,
                                             "kind": kind, "geometry": _geometry(payload.get("geometry") or {}), "text": text,
                                             "color": (payload.get("color") or "#D52B1E")[:20], "author_id": user.id}, user, request)
    db.commit()
    return _annotation_out(db, a)


@router.get("/{doc_id}/similar")
def similar(doc_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    """Documents au contenu proche (même recherche hybride que la recherche documentaire)."""
    d = get_owned(db, Document, doc_id, user)
    chunks = (db.query(DocumentChunk.text).filter(DocumentChunk.agency_id == user.agency_id, DocumentChunk.document_id == d.id)
              .order_by(DocumentChunk.chunk_index).limit(3).all())
    query = " ".join(c[0] for c in chunks)[:1500] or d.name
    hits = ai_service.retrieve(db, user, query, None, k=30)
    best: dict[str, dict] = {}
    for h in hits:
        if h["document_id"] == d.id:
            continue
        if h["document_id"] not in best or h["score"] > best[h["document_id"]]["score"]:
            best[h["document_id"]] = {"id": h["document_id"], "name": h["document"], "score": h["score"], "page": h.get("page"),
                                      "excerpt": (h.get("text") or "")[:240]}
    out = sorted(best.values(), key=lambda x: -x["score"])[:6]
    docs = {x.id: x for x in scoped_query(db, Document, user).filter(Document.id.in_([o["id"] for o in out]))}
    for o in out:
        x = docs.get(o["id"])
        o.update({"project_id": x.project_id if x else None, "category": x.category if x else None, "extension": x.extension if x else None})
    return out

