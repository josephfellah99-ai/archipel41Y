"""Agendas externes (Outlook / Google) et flux ICS.

L'agenda interne d'Archipel41 fonctionne sans aucun compte externe ; ces routes ne font qu'ajouter
la synchronisation lorsque l'agence l'a configurée."""
from __future__ import annotations

import hashlib
import html
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from ..crud import audit
from ..db import get_db, utcnow
from ..models import CalendarAccount, CalendarLink, CalendarSyncLog, Event, Project, User
from ..security import get_current_user, require
from ..services import calendar_sync as cs
from ..services import settings_store

router = APIRouter(prefix="/api/calendar", tags=["agendas externes"])


def _base(db: Session, agency_id: str, request: Request) -> str:
    cfg = settings_store.get(db, agency_id, "calendar")
    return (cfg.get("public_base_url") or str(request.base_url)).rstrip("/")


def redirect_uri(db: Session, agency_id: str, request: Request) -> str:
    return _base(db, agency_id, request) + "/api/calendar/oauth/callback"


# ------------------------------------------------------------------ configuration (administrateurs)
@router.get("/settings")
def get_settings_(request: Request, admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    v = settings_store.get_public(db, admin.agency_id, "calendar")
    v["redirect_uri"] = redirect_uri(db, admin.agency_id, request)
    v["scopes"] = {"microsoft": cs.Microsoft.scopes, "google": cs.Google.scopes}
    return v


@router.put("/settings")
def put_settings(payload: dict, request: Request, admin: User = Depends(require("admin")), db: Session = Depends(get_db)):
    allowed = {"microsoft_client_id", "microsoft_client_secret", "microsoft_tenant", "google_client_id", "google_client_secret",
               "public_base_url", "interval_minutes", "microsoft_client_secret_clear", "google_client_secret_clear"}
    patch = {k: (v.strip() if isinstance(v, str) else v) for k, v in payload.items() if k in allowed}
    if patch.get("public_base_url") and not str(patch["public_base_url"]).startswith(("http://", "https://")):
        raise HTTPException(422, "L'adresse publique doit commencer par https:// (ou http:// en local).")
    settings_store.put(db, admin.agency_id, "calendar", patch)
    audit(db, admin, "parametre", "settings", None, "Paramètres des agendas externes", request, module="parametres",
          changes={k: {"avant": None, "apres": "[masqué]" if "secret" in k else v} for k, v in patch.items()})
    db.commit()
    return get_settings_(request, admin, db)


# ------------------------------------------------------------------ comptes connectés (par utilisateur)
def _acc_out(db: Session, a: CalendarAccount) -> dict:
    last = db.query(CalendarSyncLog).filter(CalendarSyncLog.account_id == a.id).order_by(CalendarSyncLog.at.desc()).first()
    return {"id": a.id, "provider": a.provider, "provider_label": cs.PROVIDERS[a.provider].label, "account_email": a.account_email,
            "calendars": a.calendars, "status": a.status, "last_sync_at": a.last_sync_at.isoformat() if a.last_sync_at else None,
            "last_error": a.last_error, "rule": (a.delta or {}).get("_rule", "plus_recent"),
            "links": db.query(CalendarLink).filter(CalendarLink.account_id == a.id).count(),
            "last_result": {"success": last.success, "message": last.message, "at": last.at.isoformat()} if last else None}


@router.get("/accounts")
def accounts(user: User = Depends(require("read")), db: Session = Depends(get_db)):
    cfg = settings_store.get(db, user.agency_id, "calendar")
    rows = db.query(CalendarAccount).filter(CalendarAccount.user_id == user.id).all()
    return {"accounts": [_acc_out(db, a) for a in rows],
            "available": {"microsoft": bool(cfg.get("microsoft_client_id")), "google": bool(cfg.get("google_client_id"))},
            "rules": cs.RULES}


@router.post("/connect/{provider}")
def connect(provider: str, request: Request, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    try:
        url = cs.start_oauth(db, user, provider, redirect_uri(db, user.agency_id, request))
    except cs.CalendarError as ex:
        raise HTTPException(409, str(ex))
    return {"authorize_url": url}


def _page(title: str, msg: str, ok: bool, back: str) -> HTMLResponse:
    color = "#253A33" if ok else "#9c3b29"
    return HTMLResponse(f"""<!doctype html><html lang="fr"><meta charset="utf-8"><title>Archipel41</title>
<body style="font-family:Inter,Segoe UI,sans-serif;background:#F8F7F2;color:#2E3230;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div style="max-width:460px;border-top:3px solid {color};background:#fff;padding:28px 32px"><h1 style="font-size:20px;margin:0 0 8px">{html.escape(title)}</h1>
<p style="font-size:14px;line-height:1.5">{html.escape(msg)}</p><p><a href="{html.escape(back)}" style="color:{color}">Revenir à Archipel41</a></p></div>
<script>setTimeout(function(){{location.href={back!r}}},2500)</script></body></html>""", status_code=200 if ok else 400)


@router.get("/oauth/callback", include_in_schema=False)
def oauth_callback(request: Request, state: str = "", code: str = "", error: str = "", error_description: str = "",
                   db: Session = Depends(get_db)):
    back = str(request.base_url).rstrip("/") + "/#/parametres?onglet=agendas"
    if error:
        return _page("Connexion annulée", f"Le fournisseur a refusé ou annulé l'autorisation ({error_description or error}). Aucune donnée n'a été enregistrée.", False, back)
    try:
        acc = cs.finish_oauth(db, state, code)
        log = cs.sync_account(db, acc)
        db.commit()
    except cs.CalendarError as ex:
        db.rollback()
        return _page("Connexion impossible", str(ex), False, back)
    return _page("Agenda connecté", f"{cs.PROVIDERS[acc.provider].label} ({acc.account_email or 'compte'}) est connecté. {log.message or ''}", True, back)


def _own(db: Session, user: User, acc_id: str) -> CalendarAccount:
    a = db.get(CalendarAccount, acc_id)
    if not a or a.user_id != user.id:
        raise HTTPException(404, "Compte d'agenda introuvable.")
    return a


@router.put("/accounts/{acc_id}")
def update_account(acc_id: str, payload: dict, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    a = _own(db, user, acc_id)
    if "calendars" in payload:
        sel = {c.get("id"): bool(c.get("selected")) for c in payload["calendars"] or []}
        a.calendars = [{**c, "selected": sel.get(c["id"], c.get("selected", False))} for c in a.calendars or []]
    if payload.get("status") in ("actif", "suspendu"):
        a.status = payload["status"]
    if payload.get("rule") in cs.RULES:
        a.delta = {**(a.delta or {}), "_rule": payload["rule"]}
    db.commit()
    return _acc_out(db, a)


@router.post("/accounts/{acc_id}/sync")
def sync_now(acc_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    a = _own(db, user, acc_id)
    if a.status == "suspendu":
        raise HTTPException(409, "La synchronisation de ce compte est suspendue.")
    if a.status == "erreur":
        a.status = "actif"
    log = cs.sync_account(db, a)
    db.commit()
    return {"success": log.success, "message": log.message, "account": _acc_out(db, a)}


@router.get("/accounts/{acc_id}/logs")
def sync_logs(acc_id: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    a = _own(db, user, acc_id)
    rows = db.query(CalendarSyncLog).filter(CalendarSyncLog.account_id == a.id).order_by(CalendarSyncLog.at.desc()).limit(50).all()
    return [{"at": r.at.isoformat(), "success": r.success, "message": r.message, "created": r.created, "updated": r.updated,
             "deleted": r.deleted, "conflicts": r.conflicts, "details": r.details} for r in rows]


@router.delete("/accounts/{acc_id}")
def disconnect(acc_id: str, request: Request, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    """Déconnexion : jetons effacés, correspondances supprimées. Les rendez-vous restent dans Archipel41."""
    a = _own(db, user, acc_id)
    db.query(CalendarLink).filter(CalendarLink.account_id == a.id).delete()
    label = cs.PROVIDERS[a.provider].label
    db.delete(a)
    audit(db, user, "update", "users", user.id, f"Agenda {label} déconnecté", request, module="agenda")
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ flux ICS (lecture seule)
def _ics_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/ics-token")
def ics_token(request: Request, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    """Génère (ou renouvelle) l'adresse d'abonnement ICS personnelle ; l'ancienne cesse de fonctionner."""
    token = secrets.token_urlsafe(32)
    user.preferences = {**(user.preferences or {}), "ics_token_hash": _ics_hash(token)}
    audit(db, user, "update", "users", user.id, "Adresse d'abonnement ICS générée", request, module="agenda")
    db.commit()
    return {"url": _base(db, user.agency_id, request) + f"/api/calendar/ics/{token}.ics"}


@router.delete("/ics-token")
def ics_revoke(user: User = Depends(require("read")), db: Session = Depends(get_db)):
    prefs = dict(user.preferences or {})
    prefs.pop("ics_token_hash", None)
    user.preferences = prefs
    db.commit()
    return {"ok": True}


def _ics_escape(s: str | None) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    out, b = [], line.encode("utf-8")
    while len(b) > 74:
        cut = 74
        while (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode())
        b = b" " + b[cut:]
    out.append(b.decode())
    return "\r\n".join(out)


@router.get("/ics/{token}.ics", include_in_schema=False)
def ics_feed(token: str, db: Session = Depends(get_db)):
    h = _ics_hash(token)
    user = next((u for u in db.query(User).filter(User.deleted.is_(False), User.active.is_(True)) if (u.preferences or {}).get("ics_token_hash") == h), None)
    if not user:
        raise HTTPException(404, "Abonnement inconnu ou révoqué.")
    now = utcnow()
    evs = db.query(Event).filter(Event.agency_id == user.agency_id, Event.deleted.is_(False), Event.start >= now - timedelta(days=60),
                                 Event.start <= now + timedelta(days=365)).all()
    from ..security import accessible_project_ids

    allowed = accessible_project_ids(db, user)
    pnames = {p.id: f"{p.code} – {p.name}" for p in db.query(Project).filter(Project.agency_id == user.agency_id)}
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Archipel41//Agenda//FR", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:Archipel41 – {_ics_escape(user.full_name)}", "X-WR-TIMEZONE:Europe/Paris"]
    fmt = lambda d: (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")  # noqa: E731
    for e in evs:
        mine = e.organizer_id == user.id or any(p.get("user_id") == user.id for p in e.participants or [])
        if not mine or (e.project_id and allowed is not None and e.project_id not in allowed):
            continue
        desc = "\n".join(x for x in [f"Projet : {pnames[e.project_id]}" if e.project_id in pnames else "", e.description or ""] if x)
        lines += ["BEGIN:VEVENT", f"UID:{e.id}@archipel41", f"DTSTAMP:{fmt(e.updated_at or now)}", f"SEQUENCE:{e.version}",
                  f"DTSTART:{fmt(e.start)}", f"DTEND:{fmt(e.end)}", _fold(f"SUMMARY:{_ics_escape(e.title)}")]
        if e.location:
            lines.append(_fold(f"LOCATION:{_ics_escape(e.location)}"))
        if desc:
            lines.append(_fold(f"DESCRIPTION:{_ics_escape(desc)}"))
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return Response("\r\n".join(lines) + "\r\n", media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'inline; filename="archipel41.ics"', "Cache-Control": "no-store"})
