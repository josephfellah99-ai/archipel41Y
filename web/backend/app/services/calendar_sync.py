"""Synchronisation des agendas externes : Microsoft 365 / Outlook (Microsoft Graph) et Google Agenda (Calendar API v3).

Principes
- OAuth 2.0 « authorization code » + PKCE ; autorisations minimales :
    Microsoft : offline_access, User.Read, Calendars.ReadWrite
    Google    : openid, email, calendar.calendarlist.readonly, calendar.events
- Aucun mot de passe de compte externe n'est demandé ni stocké ; les jetons sont chiffrés (services.crypto).
- Synchronisation bidirectionnelle par calendrier choisi :
    · Archipel41 → externe : rendez-vous dont l'utilisateur est organisateur ou participant (fenêtre −30 j / +365 j) ;
    · externe → Archipel41 : synchronisation incrémentale (delta Graph / syncToken Google).
- Conflit (modifié des deux côtés depuis la dernière synchronisation) : règle explicite du compte
  « plus_recent » (par défaut), « archipel » ou « externe » ; chaque conflit est consigné dans l'historique.
- Toute erreur est consignée (historique de synchronisation + journal technique) ; l'agenda interne
  continue de fonctionner sans compte externe.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models import CalendarAccount, CalendarLink, CalendarSyncLog, Event, User
from . import crypto, settings_store

log = logging.getLogger("archipel41")

# Transport HTTP injectable (tests : faux serveurs Graph / Google)
_transport: httpx.BaseTransport | None = None
WINDOW_PAST, WINDOW_FUTURE = 30, 365
RULES = {"plus_recent": "La modification la plus récente l'emporte", "archipel": "Archipel41 l'emporte", "externe": "L'agenda externe l'emporte"}


def http() -> httpx.Client:
    return httpx.Client(timeout=20, transport=_transport) if _transport else httpx.Client(timeout=20)


class CalendarError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _iso(d: datetime) -> str:
    d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_dt(s: str | None, tz: str | None = None) -> datetime | None:
    """« 2027-01-11T08:00:00.0000000 » (Graph, UTC), « 2027-01-11T09:00:00+01:00 » ou « 2027-01-11 » (Google)."""
    import re as _re

    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    if len(s) == 10:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    s = _re.sub(r"(\.\d{6})\d+", r"\1", s)  # fractions de seconde au-delà de la microseconde
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)  # Graph renvoie l'heure UTC (en-tête Prefer : outlook.timezone="UTC")
    return d.astimezone(timezone.utc)


# ------------------------------------------------------------------ fournisseurs
class Provider:
    name = ""
    label = ""
    scopes: list[str] = []

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def configured(self) -> bool:
        return bool(self.client_id())

    def client_id(self) -> str | None: ...
    def client_secret(self) -> str | None: ...

    # OAuth
    def authorize_url(self, state: str, redirect_uri: str, challenge: str) -> str: ...
    def token_url(self) -> str: ...

    def _token(self, data: dict) -> dict:
        data = {**data, "client_id": self.client_id()}
        if self.client_secret():
            data["client_secret"] = self.client_secret()
        with http() as c:
            r = c.post(self.token_url(), data=data, headers={"Accept": "application/json"})
        if r.status_code >= 400:
            raise CalendarError(f"Échange de jeton refusé par {self.label} ({r.status_code}) : {r.text[:200]}", r.status_code)
        t = r.json()
        return {"access_token": t["access_token"], "refresh_token": t.get("refresh_token"),
                "expires_at": time.time() + int(t.get("expires_in", 3600)) - 60}

    def exchange(self, code: str, redirect_uri: str, verifier: str) -> dict:
        return self._token({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri, "code_verifier": verifier})

    def refresh(self, tokens: dict) -> dict:
        if not tokens.get("refresh_token"):
            raise CalendarError(f"Autorisation {self.label} expirée : reconnectez le compte.", 401)
        new = self._token({"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]})
        new["refresh_token"] = new.get("refresh_token") or tokens["refresh_token"]
        return new

    # API (implémentées par chaque fournisseur)
    def account_email(self, access: str) -> str | None: ...
    def calendars(self, access: str) -> list[dict]: ...
    def changes(self, access: str, cal_id: str, delta: str | None) -> tuple[list[dict], str | None]: ...
    def create(self, access: str, cal_id: str, ev: dict) -> dict: ...
    def update(self, access: str, cal_id: str, ext_id: str, ev: dict) -> dict: ...
    def delete(self, access: str, cal_id: str, ext_id: str) -> None: ...

    @staticmethod
    def _req(method: str, url: str, access: str, **kw) -> httpx.Response:
        headers = {"Authorization": f"Bearer {access}", "Accept": "application/json", **kw.pop("headers", {})}
        with http() as c:
            r = c.request(method, url, headers=headers, **kw)
        if r.status_code == 401:
            raise CalendarError("Jeton expiré", 401)
        return r


class Microsoft(Provider):
    name, label = "microsoft", "Microsoft 365 / Outlook"
    scopes = ["offline_access", "User.Read", "Calendars.ReadWrite"]
    API = "https://graph.microsoft.com/v1.0"

    def client_id(self):
        return self.cfg.get("microsoft_client_id")

    def client_secret(self):
        return self.cfg.get("microsoft_client_secret")

    def _base(self):
        return f"https://login.microsoftonline.com/{self.cfg.get('microsoft_tenant') or 'common'}/oauth2/v2.0"

    def authorize_url(self, state, redirect_uri, challenge):
        return f"{self._base()}/authorize?" + urlencode({"client_id": self.client_id(), "response_type": "code", "redirect_uri": redirect_uri,
                                                          "response_mode": "query", "scope": " ".join(self.scopes), "state": state,
                                                          "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "select_account"})

    def token_url(self):
        return f"{self._base()}/token"

    def account_email(self, access):
        r = self._req("GET", f"{self.API}/me", access)
        j = r.json() if r.status_code < 400 else {}
        return j.get("mail") or j.get("userPrincipalName")

    def calendars(self, access):
        r = self._req("GET", f"{self.API}/me/calendars", access)
        if r.status_code >= 400:
            raise CalendarError(f"Liste des calendriers indisponible ({r.status_code}).", r.status_code)
        return [{"id": c["id"], "name": c.get("name"), "primary": bool(c.get("isDefaultCalendar"))} for c in r.json().get("value", [])]

    @staticmethod
    def _to_item(e: dict) -> dict:
        if "@removed" in e:
            return {"id": e["id"], "deleted": True}
        return {"id": e["id"], "etag": e.get("changeKey") or e.get("@odata.etag"), "updated": e.get("lastModifiedDateTime"),
                "title": e.get("subject") or "(sans objet)", "start": _parse_dt((e.get("start") or {}).get("dateTime")),
                "end": _parse_dt((e.get("end") or {}).get("dateTime")), "all_day": bool(e.get("isAllDay")),
                "location": (e.get("location") or {}).get("displayName") or None, "description": (e.get("body") or {}).get("content") or None,
                "deleted": bool(e.get("isCancelled"))}

    def changes(self, access, cal_id, delta):
        now = datetime.now(timezone.utc)
        url = delta or (f"{self.API}/me/calendars/{cal_id}/calendarView/delta?" +
                        urlencode({"startDateTime": _iso(now - timedelta(days=WINDOW_PAST)), "endDateTime": _iso(now + timedelta(days=WINDOW_FUTURE))}))
        items, new_delta = [], None
        for _ in range(50):
            r = self._req("GET", url, access, headers={"Prefer": 'outlook.timezone="UTC", odata.maxpagesize=100'})
            if r.status_code == 410:
                return self.changes(access, cal_id, None)  # jeton delta expiré : resynchronisation complète
            if r.status_code >= 400:
                raise CalendarError(f"Lecture des événements Outlook impossible ({r.status_code}).", r.status_code)
            j = r.json()
            items += [self._to_item(e) for e in j.get("value", [])]
            if j.get("@odata.nextLink"):
                url = j["@odata.nextLink"]
                continue
            new_delta = j.get("@odata.deltaLink")
            break
        return items, new_delta

    @staticmethod
    def _body(ev: dict) -> dict:
        b = {"subject": ev["title"], "body": {"contentType": "text", "content": ev.get("description") or ""},
             "start": {"dateTime": _iso(ev["start"])[:-1], "timeZone": "UTC"}, "end": {"dateTime": _iso(ev["end"])[:-1], "timeZone": "UTC"},
             "isAllDay": bool(ev.get("all_day"))}
        if ev.get("location"):
            b["location"] = {"displayName": ev["location"]}
        return b

    def create(self, access, cal_id, ev):
        r = self._req("POST", f"{self.API}/me/calendars/{cal_id}/events", access, json=self._body(ev))
        if r.status_code >= 400:
            raise CalendarError(f"Création dans Outlook refusée ({r.status_code}).", r.status_code)
        return self._to_item(r.json())

    def update(self, access, cal_id, ext_id, ev):
        r = self._req("PATCH", f"{self.API}/me/events/{ext_id}", access, json=self._body(ev))
        if r.status_code == 404:
            raise CalendarError("Événement supprimé dans Outlook.", 404)
        if r.status_code >= 400:
            raise CalendarError(f"Modification dans Outlook refusée ({r.status_code}).", r.status_code)
        return self._to_item(r.json())

    def delete(self, access, cal_id, ext_id):
        r = self._req("DELETE", f"{self.API}/me/events/{ext_id}", access)
        if r.status_code >= 400 and r.status_code != 404:
            raise CalendarError(f"Suppression dans Outlook refusée ({r.status_code}).", r.status_code)


class Google(Provider):
    name, label = "google", "Google Agenda"
    scopes = ["openid", "email", "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
              "https://www.googleapis.com/auth/calendar.events"]
    API = "https://www.googleapis.com/calendar/v3"

    def client_id(self):
        return self.cfg.get("google_client_id")

    def client_secret(self):
        return self.cfg.get("google_client_secret")

    def authorize_url(self, state, redirect_uri, challenge):
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
            "client_id": self.client_id(), "response_type": "code", "redirect_uri": redirect_uri, "scope": " ".join(self.scopes),
            "state": state, "code_challenge": challenge, "code_challenge_method": "S256", "access_type": "offline",
            "prompt": "consent", "include_granted_scopes": "true"})

    def token_url(self):
        return "https://oauth2.googleapis.com/token"

    def account_email(self, access):
        r = self._req("GET", "https://openidconnect.googleapis.com/v1/userinfo", access)
        return (r.json() if r.status_code < 400 else {}).get("email")

    def calendars(self, access):
        r = self._req("GET", f"{self.API}/users/me/calendarList", access, params={"minAccessRole": "writer"})
        if r.status_code >= 400:
            raise CalendarError(f"Liste des calendriers indisponible ({r.status_code}).", r.status_code)
        return [{"id": c["id"], "name": c.get("summaryOverride") or c.get("summary"), "primary": bool(c.get("primary"))}
                for c in r.json().get("items", [])]

    @staticmethod
    def _to_item(e: dict) -> dict:
        if e.get("status") == "cancelled":
            return {"id": e["id"], "deleted": True}
        s, en = e.get("start") or {}, e.get("end") or {}
        return {"id": e["id"], "etag": e.get("etag"), "updated": e.get("updated"), "title": e.get("summary") or "(sans titre)",
                "start": _parse_dt(s.get("dateTime") or s.get("date")), "end": _parse_dt(en.get("dateTime") or en.get("date")),
                "all_day": "date" in s and "dateTime" not in s, "location": e.get("location"), "description": e.get("description"),
                "deleted": False}

    def changes(self, access, cal_id, delta):
        params = {"showDeleted": "true", "singleEvents": "true", "maxResults": "250"}
        if delta:
            params["syncToken"] = delta
        items, page = [], None
        for _ in range(50):
            p = dict(params, **({"pageToken": page} if page else {}))
            r = self._req("GET", f"{self.API}/calendars/{cal_id}/events", access, params=p)
            if r.status_code == 410:
                return self.changes(access, cal_id, None)  # syncToken invalide : resynchronisation complète
            if r.status_code >= 400:
                raise CalendarError(f"Lecture des événements Google impossible ({r.status_code}).", r.status_code)
            j = r.json()
            items += [self._to_item(e) for e in j.get("items", [])]
            page = j.get("nextPageToken")
            if not page:
                return items, j.get("nextSyncToken")
        return items, None

    @staticmethod
    def _body(ev: dict) -> dict:
        if ev.get("all_day"):
            s = {"date": ev["start"].date().isoformat()}
            e = {"date": max(ev["end"], ev["start"] + timedelta(days=1)).date().isoformat()}
        else:
            s, e = {"dateTime": _iso(ev["start"]), "timeZone": "UTC"}, {"dateTime": _iso(ev["end"]), "timeZone": "UTC"}
        return {"summary": ev["title"], "description": ev.get("description") or "", "location": ev.get("location") or "", "start": s, "end": e}

    def create(self, access, cal_id, ev):
        r = self._req("POST", f"{self.API}/calendars/{cal_id}/events", access, json=self._body(ev))
        if r.status_code >= 400:
            raise CalendarError(f"Création dans Google Agenda refusée ({r.status_code}).", r.status_code)
        return self._to_item(r.json())

    def update(self, access, cal_id, ext_id, ev):
        r = self._req("PATCH", f"{self.API}/calendars/{cal_id}/events/{ext_id}", access, json=self._body(ev))
        if r.status_code in (404, 410):
            raise CalendarError("Événement supprimé dans Google Agenda.", 404)
        if r.status_code >= 400:
            raise CalendarError(f"Modification dans Google Agenda refusée ({r.status_code}).", r.status_code)
        return self._to_item(r.json())

    def delete(self, access, cal_id, ext_id):
        r = self._req("DELETE", f"{self.API}/calendars/{cal_id}/events/{ext_id}", access)
        if r.status_code >= 400 and r.status_code not in (404, 410):
            raise CalendarError(f"Suppression dans Google Agenda refusée ({r.status_code}).", r.status_code)


PROVIDERS = {"microsoft": Microsoft, "google": Google}


def provider(db: Session, agency_id: str, name: str) -> Provider:
    if name not in PROVIDERS:
        raise CalendarError("Fournisseur d'agenda inconnu.")
    return PROVIDERS[name](settings_store.get(db, agency_id, "calendar"))


# ------------------------------------------------------------------ OAuth : état et PKCE
_PENDING: dict[str, dict] = {}


def start_oauth(db: Session, user: User, name: str, redirect_uri: str) -> str:
    p = provider(db, user.agency_id, name)
    if not p.configured():
        raise CalendarError(f"La connexion {p.label} n'est pas configurée : un administrateur doit renseigner l'identifiant "
                            "de l'application dans Paramètres › Agendas externes.")
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(24)
    now = time.time()
    for k in [k for k, v in _PENDING.items() if v["exp"] < now]:
        _PENDING.pop(k, None)
    _PENDING[state] = {"user_id": user.id, "agency_id": user.agency_id, "provider": name, "verifier": verifier,
                       "redirect_uri": redirect_uri, "exp": now + 600}
    return p.authorize_url(state, redirect_uri, challenge)


def finish_oauth(db: Session, state: str, code: str) -> CalendarAccount:
    pend = _PENDING.pop(state, None)
    if not pend or pend["exp"] < time.time():
        raise CalendarError("Demande de connexion expirée ou inconnue : recommencez depuis Archipel41.")
    p = provider(db, pend["agency_id"], pend["provider"])
    tokens = p.exchange(code, pend["redirect_uri"], pend["verifier"])
    email = p.account_email(tokens["access_token"])
    cals = p.calendars(tokens["access_token"])
    acc = (db.query(CalendarAccount).filter(CalendarAccount.user_id == pend["user_id"], CalendarAccount.provider == p.name)
           .first())
    if not acc:
        acc = CalendarAccount(agency_id=pend["agency_id"], user_id=pend["user_id"], provider=p.name)
        db.add(acc)
    acc.account_email = email
    acc.tokens_enc = crypto.encrypt(json.dumps(tokens))
    old = {c["id"]: c.get("selected") for c in acc.calendars or []}
    acc.calendars = [{**c, "selected": old.get(c["id"], c["primary"])} for c in cals]
    acc.status, acc.last_error = "actif", None
    acc.delta = acc.delta or {}
    db.flush()
    return acc


def _access(db: Session, acc: CalendarAccount, p: Provider, force_refresh: bool = False) -> str:
    tokens = json.loads(crypto.decrypt(acc.tokens_enc or "") or "{}")
    if not tokens:
        raise CalendarError("Compte non autorisé : reconnectez-le.", 401)
    if force_refresh or tokens.get("expires_at", 0) < time.time():
        tokens = p.refresh(tokens)
        acc.tokens_enc = crypto.encrypt(json.dumps(tokens))
    return tokens["access_token"]


# ------------------------------------------------------------------ synchronisation
def _local_payload(e: Event) -> dict:
    return {"title": e.title, "start": e.start, "end": e.end, "all_day": e.all_day, "location": e.location, "description": e.description}


def _mine(e: Event, user_id: str) -> bool:
    return e.organizer_id == user_id or any(p.get("user_id") == user_id for p in e.participants or [])


def _apply_external(e: Event, it: dict) -> None:
    e.title = (it["title"] or "(sans titre)")[:200]
    e.start, e.end = it["start"], it["end"] or it["start"] + timedelta(hours=1)
    e.all_day, e.location, e.description = it["all_day"], (it.get("location") or None), it.get("description")
    e.version += 1
    e.updated_at = utcnow()


def _external_newer(it: dict, e: Event) -> bool:
    upd = _parse_dt(it.get("updated"))
    loc = e.updated_at if e.updated_at.tzinfo else e.updated_at.replace(tzinfo=timezone.utc)
    return bool(upd and upd > loc)


def sync_account(db: Session, acc: CalendarAccount) -> CalendarSyncLog:
    """Synchronise un compte (tous ses calendriers sélectionnés). Retourne l'entrée d'historique."""
    from ..crud import record_change

    entry = CalendarSyncLog(account_id=acc.id, direction="both", details=[], created=0, updated=0, deleted=0, conflicts=0, success=False)
    db.add(entry)
    user = db.get(User, acc.user_id)
    p = provider(db, acc.agency_id, acc.provider)
    rule = (acc.delta or {}).get("_rule") or "plus_recent"
    try:
        if acc.status == "suspendu":
            entry.message = "Synchronisation suspendue par l'utilisateur."
            return entry
        try:
            access = _access(db, acc, p)
            p.calendars(access)  # vérifie l'autorisation
        except CalendarError as ex:
            if ex.status != 401:
                raise
            access = _access(db, acc, p, force_refresh=True)
        selected = [c for c in acc.calendars or [] if c.get("selected")]
        target = next((c for c in selected if c.get("primary")), selected[0] if selected else None)
        links = {(l.calendar_id, l.external_id): l for l in db.query(CalendarLink).filter(CalendarLink.account_id == acc.id)}
        by_event = {l.event_id: l for l in links.values()}
        delta = dict(acc.delta or {})

        # 1) externe → Archipel41
        for cal in selected:
            items, new_token = p.changes(access, cal["id"], delta.get(cal["id"]))
            for it in items:
                link = links.get((cal["id"], it["id"]))
                ev = db.get(Event, link.event_id) if link else None
                if it.get("deleted"):
                    if link and ev and not ev.deleted:
                        if ev.version != link.local_version and rule != "externe":
                            entry.conflicts += 1
                            entry.details.append({"evenement": ev.title, "conflit": "supprimé dans l'agenda externe, modifié dans Archipel41",
                                                  "decision": "conservé dans Archipel41 et recréé dans l'agenda externe"})
                            db.delete(link)
                            by_event.pop(ev.id, None)
                            links.pop((cal["id"], it["id"]), None)
                            continue
                        ev.deleted, ev.version, ev.updated_at = True, ev.version + 1, utcnow()
                        record_change(db, ev, "delete", user)
                        entry.deleted += 1
                    if link:
                        db.delete(link)
                        by_event.pop(link.event_id, None)
                        links.pop((cal["id"], it["id"]), None)
                    continue
                if not it.get("start"):
                    continue
                if link and ev and not ev.deleted:
                    if it.get("etag") == link.external_etag:
                        continue  # inchangé côté externe (le cas échéant, la modification locale part à l'étape 2)
                    if ev.version != link.local_version:  # modifié des deux côtés
                        keep_external = rule == "externe" or (rule == "plus_recent" and _external_newer(it, ev))
                        entry.conflicts += 1
                        entry.details.append({"evenement": ev.title, "conflit": "modifié dans les deux agendas",
                                              "decision": "version de l'agenda externe conservée" if keep_external else "version d'Archipel41 conservée",
                                              "regle": RULES[rule]})
                        if not keep_external:
                            continue  # la version locale sera renvoyée à l'étape 2
                    _apply_external(ev, it)
                    record_change(db, ev, "update", user)
                    link.external_etag, link.external_updated, link.local_version, link.synced_at = it.get("etag"), it.get("updated"), ev.version, utcnow()
                    entry.updated += 1
                elif not link:
                    ev = Event(agency_id=acc.agency_id, title=(it["title"] or "(sans titre)")[:200], kind="autre", start=it["start"],
                               end=it["end"] or it["start"] + timedelta(hours=1), all_day=it["all_day"], location=it.get("location"),
                               description=it.get("description"), participants=[{"user_id": user.id, "name": user.full_name}],
                               organizer_id=user.id, updated_by=user.id, version=1, source=acc.provider)
                    db.add(ev)
                    db.flush()
                    record_change(db, ev, "create", user)
                    l = CalendarLink(account_id=acc.id, event_id=ev.id, calendar_id=cal["id"], external_id=it["id"],
                                     external_etag=it.get("etag"), external_updated=it.get("updated"), local_version=ev.version)
                    db.add(l)
                    links[(cal["id"], it["id"])] = l
                    by_event[ev.id] = l
                    entry.created += 1
            if new_token:
                delta[cal["id"]] = new_token

        # 2) Archipel41 → externe
        if target:
            now = utcnow()
            q = db.query(Event).filter(Event.agency_id == acc.agency_id, Event.start >= now - timedelta(days=WINDOW_PAST),
                                       Event.start <= now + timedelta(days=WINDOW_FUTURE))
            for ev in q:
                link = by_event.get(ev.id)
                if ev.deleted:
                    if link:
                        p.delete(access, link.calendar_id, link.external_id)
                        db.delete(link)
                        by_event.pop(ev.id, None)
                        entry.deleted += 1
                    continue
                if not _mine(ev, user.id):
                    continue
                if link is None:
                    it = p.create(access, target["id"], _local_payload(ev))
                    db.add(CalendarLink(account_id=acc.id, event_id=ev.id, calendar_id=target["id"], external_id=it["id"],
                                        external_etag=it.get("etag"), external_updated=it.get("updated"), local_version=ev.version))
                    entry.created += 1
                elif ev.version != link.local_version:
                    try:
                        it = p.update(access, link.calendar_id, link.external_id, _local_payload(ev))
                    except CalendarError as ex:
                        if ex.status != 404:
                            raise
                        it = p.create(access, link.calendar_id, _local_payload(ev))  # supprimé à l'extérieur, conservé ici : recréé
                        link.external_id = it["id"]
                    link.external_etag, link.external_updated, link.local_version, link.synced_at = it.get("etag"), it.get("updated"), ev.version, utcnow()
                    entry.updated += 1
        delta["_rule"] = rule
        acc.delta = delta
        acc.last_sync_at, acc.last_error, acc.status = utcnow(), None, "actif"
        entry.success = True
        entry.message = (f"{entry.created} création(s), {entry.updated} modification(s), {entry.deleted} suppression(s)"
                         + (f", {entry.conflicts} conflit(s) résolu(s) selon la règle « {RULES[rule]} »" if entry.conflicts else "") + ".")
    except (CalendarError, httpx.HTTPError) as ex:
        msg = str(ex) if isinstance(ex, CalendarError) else f"{p.label} injoignable : {type(ex).__name__}"
        entry.success, entry.message = False, msg
        acc.last_error = msg
        if isinstance(ex, CalendarError) and ex.status == 401:
            acc.status = "erreur"
        from .journal import log_error

        log_error(db, source="agenda", severity="erreur", module="agenda", message=f"Synchronisation {p.label} : {msg}",
                  context={"compte": acc.account_email, "fournisseur": acc.provider}, agency_id=acc.agency_id, user_id=acc.user_id)
    return entry


# ------------------------------------------------------------------ synchronisation automatique
_thread = None


def start_background(interval_minutes: int = 15) -> None:
    import threading

    global _thread
    if _thread and _thread.is_alive():
        return
    stop = threading.Event()

    def loop():
        from ..db import SessionLocal

        while not stop.wait(interval_minutes * 60):
            db = SessionLocal()
            try:
                for acc in db.query(CalendarAccount).filter(CalendarAccount.status == "actif").all():
                    try:
                        sync_account(db, acc)
                        db.commit()
                    except Exception:
                        db.rollback()
                        log.exception("Synchronisation d'agenda non aboutie")
            finally:
                db.close()

    _thread = threading.Thread(target=loop, name="archipel41-agendas", daemon=True)
    _thread.start()
