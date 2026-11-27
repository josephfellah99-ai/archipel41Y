"""Invitations et accès invité.

Sécurité :
- code aléatoire de 12 caractères (alphabet sans caractères ambigus, ≈ 60 bits), affiché UNE seule fois,
  stocké uniquement sous forme d'empreinte HMAC-SHA-256 (clé secrète du serveur) ;
- expiration, nombre d'utilisations, révocation immédiate (invitation et sessions ouvertes) ;
- limitation des tentatives par adresse IP ; journalisation de chaque connexion et consultation ;
- le jeton invité n'est accepté par AUCUNE route standard : seules les routes /api/guest/* le servent,
  et elles ne renvoient que les projets, modules et documents autorisés par l'invitation ;
- invitation « démonstration » : session dans l'agence de démonstration (données fictives, séparées).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from ..config import get_settings
from ..crud import audit, to_dict
from ..db import get_db, utcnow
from ..models import Agency, Comment, Document, GuestSession, Invitation, Project, Task, User
from ..schemas import InvitationIn
from ..security import GuestPrincipal, create_access_token, get_principal, require
from ..services.journal import aware, log_connection

router = APIRouter(prefix="/api", tags=["invitations"])

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_TRIES: dict[str, list[float]] = defaultdict(list)
MAX_TRIES, WINDOW = 8, 600
GUEST_DOC_CATEGORIES_DEFAULT = ["plan", "rapport", "compte_rendu", "photo", "urbanisme"]


def _hash_code(code: str) -> str:
    norm = code.upper().replace("-", "").replace(" ", "")
    return hmac.new(get_settings().secret_key.encode(), norm.encode(), hashlib.sha256).hexdigest()


def new_code() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def _status(inv: Invitation) -> str:
    now = datetime.now(timezone.utc)
    if inv.revoked_at:
        return "revoquee"
    if aware(inv.expires_at) < now:
        return "expiree"
    if inv.uses >= inv.max_uses:
        return "epuisee"
    return "active"


def invitation_out(db: Session, inv: Invitation) -> dict:
    d = {k: v for k, v in to_dict(inv).items() if k != "code_hash"}
    d["status"] = _status(inv)
    d["code_masque"] = f"••••-••••-{inv.code_hint}"
    projects = {p.id: f"{p.code} – {p.name}" for p in db.query(Project).filter(Project.id.in_(inv.project_ids or [""]))}
    d["projects"] = [{"id": pid, "label": projects.get(pid, "projet supprimé")} for pid in inv.project_ids or []]
    creator = db.get(User, inv.created_by)
    d["created_by_name"] = creator.full_name if creator else "—"
    d["sessions"] = db.query(GuestSession).filter(GuestSession.invitation_id == inv.id).count()
    return d


# ------------------------------------------------------------------ gestion (administrateurs)
@router.get("/invitations")
def list_invitations(admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    rows = db.query(Invitation).filter(Invitation.agency_id == admin.agency_id).order_by(Invitation.created_at.desc()).all()
    return [invitation_out(db, i) for i in rows]


@router.post("/invitations", status_code=201)
def create_invitation(payload: InvitationIn, request: Request, admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    agency = db.get(Agency, admin.agency_id)
    if payload.kind == "projet":
        if agency.is_demo:
            pass
        for pid in payload.project_ids:
            p = db.get(Project, pid)
            if not p or p.agency_id != admin.agency_id or p.deleted:
                raise HTTPException(404, "Projet introuvable pour cette invitation.")
    expires = aware(payload.expires_at) if payload.expires_at else datetime.now(timezone.utc) + timedelta(days=payload.valid_days)
    if expires <= datetime.now(timezone.utc):
        raise HTTPException(422, "La date d'expiration doit être dans le futur.")
    code = new_code()
    inv = Invitation(agency_id=admin.agency_id, kind=payload.kind, label=payload.label, guest_name=payload.guest_name,
                     guest_email=payload.guest_email, code_hash=_hash_code(code), code_hint=code[-4:], created_by=admin.id,
                     expires_at=expires, max_uses=payload.max_uses, project_ids=payload.project_ids if payload.kind == "projet" else [],
                     modules=payload.modules, doc_categories=payload.doc_categories, can_download=payload.can_download,
                     can_comment=payload.can_comment and payload.kind == "projet", session_hours=payload.session_hours)
    db.add(inv)
    db.flush()
    audit(db, admin, "invitation_creee", "invitations", inv.id,
          f"Invitation « {inv.label} » ({'démonstration' if inv.kind == 'demo' else 'projet'}), expire le {expires:%d/%m/%Y}", request)
    db.commit()
    out = invitation_out(db, inv)
    out["code"] = code  # affiché une seule fois
    return out


@router.post("/invitations/{inv_id}/revoke")
def revoke_invitation(inv_id: str, request: Request, admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    inv = db.get(Invitation, inv_id)
    if not inv or inv.agency_id != admin.agency_id:
        raise HTTPException(404, "Invitation introuvable.")
    now = utcnow()
    inv.revoked_at = inv.revoked_at or now
    n = 0
    for s in db.query(GuestSession).filter(GuestSession.invitation_id == inv.id, GuestSession.revoked_at.is_(None)):
        s.revoked_at = now
        n += 1
    audit(db, admin, "invitation_revoquee", "invitations", inv.id, f"Invitation « {inv.label} » révoquée ({n} session(s) fermée(s))", request)
    db.commit()
    return invitation_out(db, inv)


@router.get("/invitations/{inv_id}/sessions")
def invitation_sessions(inv_id: str, admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    inv = db.get(Invitation, inv_id)
    if not inv or inv.agency_id != admin.agency_id:
        raise HTTPException(404, "Invitation introuvable.")
    rows = db.query(GuestSession).filter(GuestSession.invitation_id == inv.id).order_by(GuestSession.created_at.desc()).all()
    from ..services.journal import device_from_ua

    return [{"id": s.id, "created_at": s.created_at.isoformat(), "expires_at": s.expires_at.isoformat(),
             "revoked_at": s.revoked_at.isoformat() if s.revoked_at else None, "ip": s.ip, "device": device_from_ua(s.user_agent)} for s in rows]


# ------------------------------------------------------------------ connexion invitée
def _guest_token(sess: GuestSession, inv: Invitation) -> str:
    s = get_settings()
    payload = {"sub": sess.id, "agency": sess.agency_id, "inv": inv.id, "typ": "guest",
               "iat": int(time.time()), "exp": int(aware(sess.expires_at).timestamp())}
    return jwt.encode(payload, s.secret_key, algorithm="HS256")


@router.post("/guest/redeem")
def redeem(payload: dict, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "?"
    now_t = time.time()
    _TRIES[ip] = [t for t in _TRIES[ip] if now_t - t < WINDOW]
    if len(_TRIES[ip]) >= MAX_TRIES:
        log_connection(db, kind="invite", success=False, request=request, reason="trop de tentatives", security_event="limitation_tentatives")
        db.commit()
        raise HTTPException(429, "Trop de tentatives. Réessayez dans quelques minutes.")
    code = str(payload.get("code") or "").strip()
    if len(code.replace("-", "").replace(" ", "")) != 12:
        _TRIES[ip].append(now_t)
        raise HTTPException(422, "Le code d'invitation comporte 12 caractères (format XXXX-XXXX-XXXX).")
    inv = db.query(Invitation).filter(Invitation.code_hash == _hash_code(code)).first()
    status = _status(inv) if inv else None
    if not inv or status != "active":
        _TRIES[ip].append(now_t)
        reason = {"revoquee": "invitation révoquée", "expiree": "invitation expirée", "epuisee": "nombre d'utilisations atteint"}.get(status or "", "code inconnu")
        log_connection(db, kind="invite", success=False, request=request, agency_id=inv.agency_id if inv else None,
                       identity=f"invitation ••{code[-4:]}", reason=reason,
                       security_event="code_invalide" if not inv else None)
        db.commit()
        msg = {"revoquee": "Cette invitation a été révoquée.", "expiree": "Cette invitation a expiré.",
               "epuisee": "Cette invitation a déjà été utilisée le nombre de fois autorisé."}.get(status or "", "Code d'invitation invalide.")
        raise HTTPException(401, msg)
    now = datetime.now(timezone.utc)
    if inv.kind == "demo":
        demo = db.query(Agency).filter(Agency.is_demo.is_(True)).first()
        if not demo:
            raise HTTPException(409, "L'espace de démonstration n'est pas encore créé sur ce serveur. Demandez à l'administrateur de le créer.")
        guest_user = (db.query(User).filter(User.agency_id == demo.id, User.email == "invite@archipel41.demo").first())
        if not guest_user:
            from ..security import hash_password

            guest_user = User(agency_id=demo.id, email="invite@archipel41.demo", full_name="Visiteur (démonstration)", role="member",
                              password_hash=hash_password(secrets.token_urlsafe(32)), color="#8A8F8C")
            db.add(guest_user)
            db.flush()
        inv.uses += 1
        inv.last_used_at = utcnow()
        log_connection(db, kind="invite", success=True, request=request, agency_id=inv.agency_id,
                       identity=f"invitation démonstration « {inv.label} »")
        audit(db, None, "invite_demo", "invitations", inv.id, f"Accès démonstration via « {inv.label} »", request)
        db.commit()
        return {"kind": "demo", "token": create_access_token(guest_user), "expires_at": None,
                "message": "Vous accédez à l'espace de DÉMONSTRATION : toutes les données sont fictives."}
    sess = GuestSession(agency_id=inv.agency_id, invitation_id=inv.id,
                        expires_at=min(aware(inv.expires_at), now + timedelta(hours=inv.session_hours)),
                        ip=ip, user_agent=(request.headers.get("user-agent") or "")[:300])
    db.add(sess)
    inv.uses += 1
    inv.last_used_at = utcnow()
    db.flush()
    log_connection(db, kind="invite", success=True, request=request, agency_id=inv.agency_id,
                   identity=f"invité · {inv.guest_name or inv.label}", session_id=sess.id)
    db.commit()
    return {"kind": "projet", "token": _guest_token(sess, inv), "expires_at": sess.expires_at.isoformat()}


def guest_scope(db: Session, g: GuestPrincipal) -> dict:
    inv = g.invitation
    projects = db.query(Project).filter(Project.id.in_(inv.project_ids or [""]), Project.agency_id == g.agency_id,
                                        Project.deleted.is_(False)).all()
    return {"invitation": inv.label, "expires_at": aware(g.session.expires_at).isoformat(), "modules": inv.modules,
            "can_download": inv.can_download, "can_comment": inv.can_comment,
            "projects": [{"id": p.id, "code": p.code, "name": p.name} for p in projects]}


def _guest(request: Request, db: Session) -> GuestPrincipal:
    p = get_principal(request, db)
    if p.role != "guest":
        raise HTTPException(403, "Réservé aux accès invités.")
    return p


def _guest_project(db: Session, g: GuestPrincipal, project_id: str) -> Project:
    if project_id not in (g.invitation.project_ids or []):
        raise HTTPException(403, "Ce projet n'est pas partagé avec vous.")
    p = db.get(Project, project_id)
    if not p or p.agency_id != g.agency_id or p.deleted:
        raise HTTPException(404, "Projet introuvable.")
    return p


def _need(g: GuestPrincipal, module: str):
    if module not in (g.invitation.modules or []):
        raise HTTPException(403, "Cette partie du projet n'est pas partagée avec vous.")


def _visible_docs(db: Session, g: GuestPrincipal, project_id: str):
    cats = g.invitation.doc_categories or GUEST_DOC_CATEGORIES_DEFAULT
    q = db.query(Document).filter(Document.agency_id == g.agency_id, Document.project_id == project_id, Document.deleted.is_(False),
                                  Document.confidential.is_(False), Document.category.in_(cats), Document.status != "archive")
    if not g.invitation.doc_categories:
        q = q.filter(Document.status == "valide")  # par défaut : uniquement les documents validés
    return q


def _log_view(db: Session, g: GuestPrincipal, request: Request, what: str, entity: str | None = None, entity_id: str | None = None):
    from ..models import AuditLog

    db.add(AuditLog(agency_id=g.agency_id, user_id=None, action="consultation_invite", entity=entity, entity_id=entity_id,
                    summary=f"{g.full_name} ({g.invitation.label}) : {what}", ip=request.client.host if request.client else None,
                    actor_label=f"Invité · {g.full_name}", module="invites"))


@router.get("/guest/me")
def guest_me(request: Request, db: Session = Depends(get_db)):
    g = _guest(request, db)
    return guest_scope(db, g)


@router.get("/guest/projects/{project_id}")
def guest_project(project_id: str, request: Request, db: Session = Depends(get_db)):
    g = _guest(request, db)
    p = _guest_project(db, g, project_id)
    _need(g, "fiche")
    _log_view(db, g, request, f"fiche du projet {p.code}", "projects", p.id)
    db.commit()
    # Données volontairement limitées : aucune information financière, aucun membre de l'équipe interne
    return {"id": p.id, "code": p.code, "name": p.name, "status": p.status, "address": p.address, "postal_code": p.postal_code,
            "city": p.city, "program": p.program, "description": p.description, "surface_m2": p.surface_m2,
            "start_date": p.start_date.isoformat() if p.start_date else None, "end_date": p.end_date.isoformat() if p.end_date else None,
            "progress": p.progress, "current_phase": p.current_phase,
            "phases": [{"code": ph.get("code"), "label": ph.get("label"), "status": ph.get("status"), "start": ph.get("start"),
                        "end": ph.get("end"), "progress": ph.get("progress")} for ph in (p.phases or []) if ph.get("enabled", True)],
            "latitude": p.latitude if "terrain" in (g.invitation.modules or []) else None,
            "longitude": p.longitude if "terrain" in (g.invitation.modules or []) else None}


@router.get("/guest/projects/{project_id}/documents")
def guest_documents(project_id: str, request: Request, db: Session = Depends(get_db)):
    g = _guest(request, db)
    _guest_project(db, g, project_id)
    _need(g, "documents")
    rows = _visible_docs(db, g, project_id).order_by(Document.updated_at.desc()).all()
    return [{"id": d.id, "name": d.name, "category": d.category, "extension": d.extension, "size": d.size,
             "updated_at": d.updated_at.isoformat() if d.updated_at else None, "status": d.status, "page_count": d.page_count} for d in rows]


def _guest_doc(db: Session, g: GuestPrincipal, doc_id: str) -> Document:
    d = db.get(Document, doc_id)
    if not d or d.agency_id != g.agency_id or not d.project_id or d.project_id not in (g.invitation.project_ids or []):
        raise HTTPException(404, "Document introuvable.")
    _need(g, "documents")
    if not _visible_docs(db, g, d.project_id).filter(Document.id == d.id).first():
        raise HTTPException(403, "Ce document n'est pas partagé avec vous.")
    return d


@router.get("/guest/documents/{doc_id}/file")
def guest_file(doc_id: str, request: Request, download: bool = False, db: Session = Depends(get_db)):
    g = _guest(request, db)
    d = _guest_doc(db, g, doc_id)
    if download and not g.invitation.can_download:
        raise HTTPException(403, "Le téléchargement n'est pas autorisé pour cette invitation.")
    from ..routers.documents import _disposition, _version
    from ..services import storage

    v = _version(db, d, None)
    _log_view(db, g, request, f"{'téléchargement' if download else 'consultation'} de « {d.name} »", "documents", d.id)
    db.commit()
    return FileResponse(storage.path_for(v.storage_key), media_type=d.mime or "application/octet-stream",
                        headers={"Content-Disposition": _disposition("attachment" if download else "inline", v.filename),
                                 "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                                 "Content-Security-Policy": "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"})


@router.get("/guest/documents/{doc_id}/pages")
def guest_pages(doc_id: str, request: Request, db: Session = Depends(get_db)):
    g = _guest(request, db)
    d = _guest_doc(db, g, doc_id)
    return {"pages": (d.page_count or 0) if (d.extension or "").lower() == "pdf" else 0}


@router.get("/guest/documents/{doc_id}/page/{n}")
def guest_page(doc_id: str, n: int, request: Request, db: Session = Depends(get_db)):
    """Aperçu page par page (consultation sans téléchargement du fichier source)."""
    g = _guest(request, db)
    d = _guest_doc(db, g, doc_id)
    from ..routers.documents import _version
    from ..services import storage
    import io as _io

    import pypdfium2 as pdfium

    v = _version(db, d, None)
    pdf = pdfium.PdfDocument(str(storage.path_for(v.storage_key)))
    try:
        if n < 1 or n > len(pdf):
            raise HTTPException(404, "Page inexistante.")
        img = pdf[n - 1].render(scale=1.4).to_pil()
        buf = _io.BytesIO()
        img.save(buf, "PNG", optimize=True)
    finally:
        pdf.close()
    if n == 1:
        _log_view(db, g, request, f"aperçu de « {d.name} »", "documents", d.id)
        db.commit()
    return Response(buf.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/guest/projects/{project_id}/planning")
def guest_planning(project_id: str, request: Request, db: Session = Depends(get_db)):
    g = _guest(request, db)
    _guest_project(db, g, project_id)
    _need(g, "planning")
    rows = db.query(Task).filter(Task.project_id == project_id, Task.deleted.is_(False), Task.agency_id == g.agency_id).order_by(Task.start_date).all()
    return [{"id": t.id, "name": t.name, "start_date": t.start_date.isoformat() if t.start_date else None, "duration_days": t.duration_days,
             "progress": t.progress, "milestone": t.milestone} for t in rows]


@router.get("/guest/comments")
def guest_comments(entity: str, entity_id: str, request: Request, db: Session = Depends(get_db)):
    g = _guest(request, db)
    pid = _comment_target_project(db, g, entity, entity_id)
    rows = db.query(Comment).filter(Comment.agency_id == g.agency_id, Comment.entity == entity, Comment.entity_id == entity_id,
                                    Comment.deleted.is_(False), Comment.project_id == pid).order_by(Comment.created_at).all()
    return [{"id": c.id, "author_name": c.author_name, "guest": c.guest, "body": c.body, "created_at": c.created_at.isoformat()} for c in rows]


def _comment_target_project(db: Session, g: GuestPrincipal, entity: str, entity_id: str) -> str:
    if entity == "projects":
        _guest_project(db, g, entity_id)
        return entity_id
    if entity == "documents":
        return _guest_doc(db, g, entity_id).project_id
    raise HTTPException(403, "Commentaires non disponibles pour cet élément.")


@router.post("/guest/comments", status_code=201)
def guest_add_comment(payload: dict, request: Request, db: Session = Depends(get_db)):
    g = _guest(request, db)
    if not g.invitation.can_comment:
        raise HTTPException(403, "Les commentaires ne sont pas autorisés pour cette invitation.")
    body = str(payload.get("body") or "").strip()
    if not body or len(body) > 5000:
        raise HTTPException(422, "Le commentaire doit contenir entre 1 et 5 000 caractères.")
    entity, entity_id = str(payload.get("entity")), str(payload.get("entity_id"))
    pid = _comment_target_project(db, g, entity, entity_id)
    c = Comment(agency_id=g.agency_id, project_id=pid, entity=entity, entity_id=entity_id, author_id=None,
                author_name=f"{g.full_name} (invité)", guest=True, body=body, mentions=[])
    db.add(c)
    db.flush()
    from ..services.collab import notify_comment

    notify_comment(db, c, actor=None, extra_recipients={g.invitation.created_by})  # l'auteur de l'invitation est toujours prévenu
    _log_view(db, g, request, "commentaire ajouté", entity, entity_id)
    db.commit()
    return {"id": c.id, "author_name": c.author_name, "guest": True, "body": c.body, "created_at": c.created_at.isoformat()}
