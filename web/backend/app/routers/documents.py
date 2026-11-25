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

from ..crud import delete_obj, get_owned, scoped_query, to_dict, update_obj
from ..db import get_db
from ..models import ChangeLog, Document, DocumentVersion, User
from ..schemas import DOC_CATEGORIES, DocumentPatch
from ..security import require
from ..services import ai as ai_service
from ..services import documents as docsvc
from ..services import storage

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
                   tag: str | None = None, limit: int = 500, user: User = Depends(require("read")),
                   db: Session = Depends(get_db)):
    query = scoped_query(db, Document, user)
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
            report.append({"document_id": doc.id, "name": doc.name, **ex.to_dict()})
    db.commit()
    return {"documents": created, "extraction": report}


@router.get("/search")
def search(q: str, project_id: str | None = None, k: int = 10, user: User = Depends(require("read")),
           db: Session = Depends(get_db)):
    """Recherche sémantique + lexicale (RAG) dans le contenu des documents."""
    return ai_service.retrieve(db, user, q, project_id, k=min(k, 30))


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
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(storage.path_for(v.storage_key)))
    try:
        return {"pages": len(pdf)}
    finally:
        pdf.close()


@router.get("/{doc_id}/page/{n}")
def page_image(doc_id: str, n: int, version: int | None = None, scale: float = 1.6, user: User = Depends(require("read")),
               db: Session = Depends(get_db)):
    """Aperçu d'une page PDF rendue en image côté serveur (fiable sans visionneuse PDF)."""
    d = get_owned(db, Document, doc_id, user)
    v = _version(db, d, version)
    import io as _io

    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(storage.path_for(v.storage_key)))
    try:
        if n < 1 or n > len(pdf):
            raise HTTPException(404, "Page inexistante.")
        img = pdf[n - 1].render(scale=max(0.5, min(scale, 3.0))).to_pil()
        buf = _io.BytesIO()
        img.save(buf, "PNG", optimize=True)
    finally:
        pdf.close()
    return Response(buf.getvalue(), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


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
