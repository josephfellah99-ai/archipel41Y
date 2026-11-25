"""Bibliothèque documentaire : import, versions, extraction de texte, index RAG."""
from __future__ import annotations

import mimetypes
import tempfile
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ai.document_analysis.extract import ExtractResult, extract_document
from ai.rag.engine import LOCAL_MODEL, chunk_pages, local_embed

from ..config import get_settings
from ..crud import audit, create_obj, record_change
from ..models import Document, DocumentChunk, DocumentVersion, User
from . import storage

ALLOWED_EXT = {
    ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif", ".svg",
    ".xlsx", ".xlsm", ".xls", ".csv", ".docx", ".doc", ".odt", ".ods", ".txt", ".md", ".rtf",
    ".dwg", ".dxf", ".ifc", ".pln", ".pla", ".rvt", ".skp", ".3dm", ".zip", ".pptx", ".msg", ".eml",
}
CATEGORY_BY_EXT = {".dwg": "plan", ".dxf": "plan", ".pln": "maquette", ".pla": "maquette", ".ifc": "maquette",
                   ".rvt": "maquette", ".jpg": "photo", ".jpeg": "photo", ".png": "photo"}


def guess_category(filename: str) -> str:
    n = filename.lower()
    for key, cat in (("devis", "devis"), ("cctp", "cctp"), ("dpgf", "dpgf"), ("plu", "urbanisme"), ("reglement", "urbanisme"),
                     ("cr_", "compte_rendu"), ("compte", "compte_rendu"), ("facture", "facture"), ("contrat", "contrat"),
                     ("marche", "contrat"), ("plan", "plan")):
        if key in n:
            return cat
    return CATEGORY_BY_EXT.get(Path(n).suffix, "autre")


def check_upload(filename: str, data: bytes) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(415, f"Type de fichier non autorisé : {ext or 'sans extension'}.")
    max_mb = get_settings().max_upload_mb
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(413, f"Fichier trop volumineux (maximum {max_mb} Mo).")
    head = data[:8]
    if ext == ".pdf" and not head.startswith(b"%PDF"):
        raise HTTPException(422, "Le fichier ne semble pas être un PDF valide.")
    if ext in (".exe", ".dll", ".bat", ".cmd", ".ps1", ".js", ".vbs") or head.startswith(b"MZ"):
        raise HTTPException(415, "Les fichiers exécutables sont refusés.")


def run_extraction(path: Path, filename: str) -> ExtractResult:
    s = get_settings()
    return extract_document(path, filename, tesseract_cmd=s.tesseract_cmd or None, libreoffice_cmd=s.libreoffice_cmd or None)


def index_document(db: Session, doc: Document, version: DocumentVersion, ex: ExtractResult, embedder=None) -> int:
    db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
    chunks = chunk_pages([(p.number, p.text) for p in ex.pages])
    if not chunks:
        return 0
    model = LOCAL_MODEL
    vectors = None
    if embedder is not None:
        try:
            vectors = embedder.embed([c.text for c in chunks])
            model = f"provider:{getattr(embedder, 'embedding_model', 'ext')}"
        except Exception:
            vectors = None
            model = LOCAL_MODEL
    for i, c in enumerate(chunks):
        db.add(DocumentChunk(
            agency_id=doc.agency_id, document_id=doc.id, project_id=doc.project_id, version=version.number,
            chunk_index=c.index, page=c.page, text=c.text, embedding_model=model,
            embedding=vectors[i] if vectors else local_embed(c.text), confidential=doc.confidential))
    return len(chunks)


def add_document(db: Session, user: User, filename: str, data: bytes, *, project_id: str | None = None,
                 category: str | None = None, confidential: bool = False, tags: list[str] | None = None,
                 description: str | None = None, linked: dict | None = None, existing: Document | None = None,
                 comment: str | None = None) -> tuple[Document, ExtractResult]:
    filename = storage.safe_filename(filename)
    check_upload(filename, data)
    key, sha = storage.store_bytes(user.agency_id, data)
    ext = Path(filename).suffix.lower()
    if existing is None:
        doc = create_obj(db, Document, {
            "project_id": project_id, "name": filename, "category": category or guess_category(filename),
            "tags": tags or [], "mime": mimetypes.guess_type(filename)[0] or "application/octet-stream",
            "extension": ext.lstrip("."), "size": len(data), "current_version": 1, "confidential": confidential,
            "description": description, "linked": linked or {},
        }, user)
        number = 1
    else:
        doc = existing
        number = (doc.current_version or 1) + 1
        doc.current_version = number
        doc.size = len(data)
        doc.version += 1
        doc.updated_by = user.id
        record_change(db, doc, "update", user, {"nouvelle_version": number})
        audit(db, user, "new_version", "documents", doc.id, f"{doc.name} v{number}")
    ver = create_obj(db, DocumentVersion, {
        "document_id": doc.id, "number": number, "filename": filename, "storage_key": key, "sha256": sha,
        "size": len(data), "comment": comment,
    }, user)
    ex = run_extraction(storage.path_for(key), filename)
    ver.text = ex.text[:2_000_000] if ex.text else None
    doc.text_status = ex.status
    doc.page_count = len(ex.pages) or None
    from .ai import get_embedder

    index_document(db, doc, ver, ex, get_embedder(db, user.agency_id))
    db.flush()
    return doc, ex


def current_version(db: Session, doc: Document) -> DocumentVersion:
    ver = (db.query(DocumentVersion)
           .filter(DocumentVersion.document_id == doc.id, DocumentVersion.number == doc.current_version,
                   DocumentVersion.deleted.is_(False)).first())
    if not ver:
        raise HTTPException(404, "Version du document introuvable.")
    return ver


def extract_from_version(ver: DocumentVersion) -> ExtractResult:
    if not storage.exists(ver.storage_key):
        raise HTTPException(409, "Le fichier n'est pas encore disponible sur cet appareil (synchronisation en attente).")
    return run_extraction(storage.path_for(ver.storage_key), ver.filename)


def temp_copy(data: bytes, suffix: str) -> Path:
    f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    f.write(data)
    f.close()
    return Path(f.name)
