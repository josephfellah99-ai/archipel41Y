"""Lot 5 : synchronisation Outlook (Microsoft Graph) et Google Agenda — testée contre des serveurs simulés
qui reproduisent les points d'accès utilisés (OAuth, liste des calendriers, delta / syncToken, ETag, suppressions,
expiration du jeton). Aucun appel réseau réel."""
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from conftest import new_agency


class FakeProvider:
    """Serveur OAuth + agenda simulé (Microsoft Graph ou Google Calendar)."""

    def __init__(self, kind):
        self.kind = kind
        self.events = {}           # id → dict normalisé {title, start, end, location, description, version}
        self.deleted = set()
        self.seq = 0
        self.changelog = []        # (seq, id)
        self.valid_tokens = set()
        self.refresh_count = 0
        self.code_ok = "code-" + kind

    # helpers -----------------------------------------------------------------
    def _touch(self, eid):
        self.seq += 1
        self.changelog.append((self.seq, eid))
        self.events.get(eid, {}).update(version=self.seq, updated=datetime.now(timezone.utc).isoformat())

    def add_external(self, title, start):
        eid = uuid.uuid4().hex
        self.events[eid] = {"title": title, "start": start, "end": start + timedelta(hours=1), "location": "Chantier", "description": ""}
        self._touch(eid)
        return eid

    def edit_external(self, eid, **kw):
        self.events[eid].update(kw)
        self._touch(eid)

    def delete_external(self, eid):
        self.events.pop(eid, None)
        self.deleted.add(eid)
        self.seq += 1
        self.changelog.append((self.seq, eid))

    def _changed_since(self, since):
        ids = []
        for s, eid in self.changelog:
            if s > since and eid not in ids:
                ids.append(eid)
        return ids

    # format natif ------------------------------------------------------------
    def _ms(self, eid):
        if eid not in self.events:
            return {"id": eid, "@removed": {"reason": "deleted"}}
        e = self.events[eid]
        return {"id": eid, "subject": e["title"], "changeKey": f"ck{e['version']}", "lastModifiedDateTime": e["updated"],
                "start": {"dateTime": e["start"].strftime("%Y-%m-%dT%H:%M:%S.0000000"), "timeZone": "UTC"},
                "end": {"dateTime": e["end"].strftime("%Y-%m-%dT%H:%M:%S.0000000"), "timeZone": "UTC"},
                "isAllDay": False, "location": {"displayName": e.get("location") or ""}, "body": {"content": e.get("description") or ""}}

    def _g(self, eid):
        if eid not in self.events:
            return {"id": eid, "status": "cancelled"}
        e = self.events[eid]
        return {"id": eid, "status": "confirmed", "etag": f'"{e["version"]}"', "updated": e["updated"], "summary": e["title"],
                "start": {"dateTime": e["start"].isoformat()}, "end": {"dateTime": e["end"].isoformat()},
                "location": e.get("location"), "description": e.get("description")}

    def _from_ms(self, b):
        p = lambda d: datetime.fromisoformat(d["dateTime"]).replace(tzinfo=timezone.utc)  # noqa: E731
        return {"title": b["subject"], "start": p(b["start"]), "end": p(b["end"]), "location": (b.get("location") or {}).get("displayName"),
                "description": (b.get("body") or {}).get("content")}

    def _from_g(self, b):
        p = lambda d: datetime.fromisoformat(d["dateTime"].replace("Z", "+00:00"))  # noqa: E731
        return {"title": b["summary"], "start": p(b["start"]), "end": p(b["end"]), "location": b.get("location"), "description": b.get("description")}

    # routage HTTP ------------------------------------------------------------
    def handle(self, req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if url.endswith("/token"):
            form = parse_qs(req.content.decode())
            if form["grant_type"][0] == "authorization_code":
                assert form["code"][0] == self.code_ok and form.get("code_verifier")
            else:
                self.refresh_count += 1
            tok = uuid.uuid4().hex
            self.valid_tokens.add(tok)
            return httpx.Response(200, json={"access_token": tok, "refresh_token": "rt-" + self.kind, "expires_in": 3600})
        auth = req.headers.get("authorization", "")[7:]
        if auth not in self.valid_tokens:
            return httpx.Response(401, json={"error": "invalid_token"})
        u = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        body = json.loads(req.content) if req.content else {}
        if self.kind == "microsoft":
            if u.path.endswith("/me"):
                return httpx.Response(200, json={"mail": "camille@agence.onmicrosoft.com"})
            if u.path.endswith("/me/calendars"):
                return httpx.Response(200, json={"value": [{"id": "CAL1", "name": "Calendrier", "isDefaultCalendar": True}]})
            if u.path.endswith("/calendarView/delta"):
                since = int(q.get("since", "0"))
                ids = self._changed_since(since) if "since" in q else list(self.events)
                return httpx.Response(200, json={"value": [self._ms(i) for i in ids],
                                                 "@odata.deltaLink": f"https://graph.microsoft.com/v1.0/me/calendars/CAL1/calendarView/delta?since={self.seq}"})
            m = re.search(r"/me/calendars/CAL1/events$", u.path)
            if m and req.method == "POST":
                eid = uuid.uuid4().hex
                self.events[eid] = self._from_ms(body)
                self._touch(eid)
                return httpx.Response(201, json=self._ms(eid))
            m = re.search(r"/me/events/([^/]+)$", u.path)
            if m:
                eid = m.group(1)
                if eid not in self.events:
                    return httpx.Response(404, json={})
                if req.method == "PATCH":
                    self.events[eid].update(self._from_ms(body))
                    self._touch(eid)
                    return httpx.Response(200, json=self._ms(eid))
                if req.method == "DELETE":
                    self.delete_external(eid)
                    return httpx.Response(204)
        else:
            if u.path.endswith("/userinfo"):
                return httpx.Response(200, json={"email": "camille@gmail.com"})
            if u.path.endswith("/users/me/calendarList"):
                return httpx.Response(200, json={"items": [{"id": "primary@g", "summary": "Camille", "primary": True}]})
            m = re.search(r"/calendars/([^/]+)/events(?:/([^/]+))?$", u.path)
            if m:
                eid = m.group(2)
                if req.method == "GET" and not eid:
                    since = int(q["syncToken"]) if "syncToken" in q else None
                    ids = self._changed_since(since) if since is not None else list(self.events)
                    return httpx.Response(200, json={"items": [self._g(i) for i in ids], "nextSyncToken": str(self.seq)})
                if req.method == "POST":
                    eid = uuid.uuid4().hex
                    self.events[eid] = self._from_g(body)
                    self._touch(eid)
                    return httpx.Response(200, json=self._g(eid))
                if eid not in self.events:
                    return httpx.Response(410, json={})
                if req.method == "PATCH":
                    self.events[eid].update(self._from_g(body))
                    self._touch(eid)
                    return httpx.Response(200, json=self._g(eid))
                if req.method == "DELETE":
                    self.delete_external(eid)
                    return httpx.Response(204)
        return httpx.Response(404, json={"error": "route simulée inconnue", "url": url})


@pytest.fixture
def fake(request):
    from app.services import calendar_sync as cs

    fp = FakeProvider(request.param)
    cs._transport = httpx.MockTransport(fp.handle)
    yield fp
    cs._transport = None


def _connect(client, ag, fp):
    a = ag["admin"]
    key = "microsoft" if fp.kind == "microsoft" else "google"
    r = client.put("/api/calendar/settings", json={f"{key}_client_id": "app-id-test", f"{key}_client_secret": "secret-test"}, headers=a)
    assert r.status_code == 200 and r.json()[f"{key}_client_secret_set"] and "secret-test" not in r.text
    url = client.post(f"/api/calendar/connect/{key}", headers=a).json()["authorize_url"]
    q = parse_qs(urlparse(url).query)
    assert q["code_challenge_method"] == ["S256"] and "Calendars.ReadWrite" in q["scope"][0] if key == "microsoft" else "calendar.events" in q["scope"][0]
    r = client.get(f"/api/calendar/oauth/callback?state={q['state'][0]}&code={fp.code_ok}")
    assert r.status_code == 200 and "Agenda connecté" in r.text
    accs = client.get("/api/calendar/accounts", headers=a).json()["accounts"]
    assert len(accs) == 1 and accs[0]["calendars"][0]["selected"]
    return accs[0]


@pytest.mark.parametrize("fake", ["microsoft", "google"], indirect=True)
def test_two_way_sync(client, fake):
    ag = new_agency(("admin", "member"))
    a = ag["admin"]
    soon = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=3)
    # rendez-vous existant dans l'agenda externe avant la connexion
    ext1 = fake.add_external("Réunion banque", soon)
    acc = _connect(client, ag, fake)
    # jetons chiffrés en base, jamais en clair
    from app.db import SessionLocal
    from app.models import CalendarAccount

    db = SessionLocal()
    row = db.get(CalendarAccount, acc["id"])
    assert row.tokens_enc and "access_token" not in row.tokens_enc
    db.close()
    evs = client.get("/api/events", headers=a).json()
    assert any(e["title"] == "Réunion banque" and e["source"] == fake.kind for e in evs)       # externe → Archipel41

    # Archipel41 → externe
    r = client.post("/api/events", json={"title": "Visite de chantier lot 02", "kind": "visite_chantier", "start": (soon + timedelta(days=1)).isoformat(),
                                         "end": (soon + timedelta(days=1, hours=2)).isoformat(), "location": "Nantes"}, headers=a).json()
    ev = r["event"] if "event" in r else r
    res = client.post(f"/api/calendar/accounts/{acc['id']}/sync", headers=a).json()
    assert res["success"], res
    assert any(e["title"] == "Visite de chantier lot 02" for e in fake.events.values())

    # modification dans Archipel41 → répercutée
    cur = client.get(f"/api/events/{ev['id']}", headers=a).json()
    client.put(f"/api/events/{ev['id']}", json={"title": "Visite de chantier lot 02 (décalée)", "version": cur["version"]}, headers=a)
    client.post(f"/api/calendar/accounts/{acc['id']}/sync", headers=a)
    assert any(e["title"] == "Visite de chantier lot 02 (décalée)" for e in fake.events.values())

    # modification et suppression dans l'agenda externe → répercutées
    fake.edit_external(ext1, title="Réunion banque (salle B)")
    client.post(f"/api/calendar/accounts/{acc['id']}/sync", headers=a)
    titles = {e["title"] for e in client.get("/api/events", headers=a).json()}
    assert "Réunion banque (salle B)" in titles and "Réunion banque" not in titles
    fake.delete_external(ext1)
    client.post(f"/api/calendar/accounts/{acc['id']}/sync", headers=a)
    assert "Réunion banque (salle B)" not in {e["title"] for e in client.get("/api/events", headers=a).json()}

    # suppression dans Archipel41 → supprimé à l'extérieur
    client.delete(f"/api/events/{ev['id']}", headers=a)
    client.post(f"/api/calendar/accounts/{acc['id']}/sync", headers=a)
    assert not any("Visite de chantier" in e["title"] for e in fake.events.values())

    # conflit : modifié des deux côtés → règle « Archipel41 l'emporte »
    ext2 = fake.add_external("Point MOA", soon + timedelta(days=5))
    client.post(f"/api/calendar/accounts/{acc['id']}/sync", headers=a)
    local = next(e for e in client.get("/api/events", headers=a).json() if e["title"] == "Point MOA")
    client.put(f"/api/calendar/accounts/{acc['id']}", json={"rule": "archipel"}, headers=a)
    client.put(f"/api/events/{local['id']}", json={"title": "Point MOA (version agence)", "version": local["version"]}, headers=a)
    fake.edit_external(ext2, title="Point MOA (version externe)")
    res = client.post(f"/api/calendar/accounts/{acc['id']}/sync", headers=a).json()
    assert "1 conflit" in res["message"]
    assert fake.events[ext2]["title"] == "Point MOA (version agence)"
    logs = client.get(f"/api/calendar/accounts/{acc['id']}/logs", headers=a).json()
    assert logs[0]["details"][0]["decision"] == "version d'Archipel41 conservée"

    # jeton expiré côté fournisseur → renouvellement automatique
    fake.valid_tokens.clear()
    before = fake.refresh_count
    assert client.post(f"/api/calendar/accounts/{acc['id']}/sync", headers=a).json()["success"]
    assert fake.refresh_count == before + 1

    # rendez-vous d'un autre collaborateur : non envoyé dans l'agenda personnel
    client.post("/api/events", json={"title": "RDV de Member", "start": (soon + timedelta(days=2)).isoformat(),
                                     "end": (soon + timedelta(days=2, hours=1)).isoformat()}, headers=ag["member"])
    client.post(f"/api/calendar/accounts/{acc['id']}/sync", headers=a)
    assert not any(e["title"] == "RDV de Member" for e in fake.events.values())

    # suspension puis déconnexion : l'agenda interne reste intact
    client.put(f"/api/calendar/accounts/{acc['id']}", json={"status": "suspendu"}, headers=a)
    assert client.post(f"/api/calendar/accounts/{acc['id']}/sync", headers=a).status_code == 409
    n_local = len(client.get("/api/events", headers=a).json())
    assert client.delete(f"/api/calendar/accounts/{acc['id']}", headers=a).status_code == 200
    assert len(client.get("/api/events", headers=a).json()) == n_local


@pytest.mark.parametrize("fake", ["google"], indirect=True)
def test_errors_are_logged_and_internal_agenda_unaffected(client, fake):
    ag = new_agency(("admin",))
    acc = _connect(client, ag, fake)
    from app.services import calendar_sync as cs

    cs._transport = httpx.MockTransport(lambda r: httpx.Response(503, json={}) if "token" not in str(r.url) else fake.handle(r))
    res = client.post(f"/api/calendar/accounts/{acc['id']}/sync", headers=ag["admin"]).json()
    assert not res["success"] and "503" in res["message"]
    errs = client.get("/api/history/errors?source=agenda", headers=ag["admin"]).json()["items"]
    assert errs and errs[0]["module"] == "agenda"
    assert client.post("/api/events", json={"title": "Interne", "start": "2027-03-01T08:00:00Z", "end": "2027-03-01T09:00:00Z"}, headers=ag["admin"]).status_code == 201


def test_not_configured_and_oauth_errors(client):
    ag = new_agency(("admin",))
    r = client.post("/api/calendar/connect/google", headers=ag["admin"])
    assert r.status_code == 409 and "Paramètres" in r.json()["detail"]
    assert client.get("/api/calendar/oauth/callback?state=inconnu&code=x").status_code == 400
    assert "annulée" in client.get("/api/calendar/oauth/callback?error=access_denied").text
    assert client.put("/api/calendar/settings", json={"google_client_id": "x"}, headers=new_agency(("member",))["member"]).status_code == 403


def test_ics_feed_and_deadlines(client):
    ag = new_agency(("admin", "member"))
    a = ag["admin"]
    p = client.post("/api/projects", json={"code": "ICS", "name": "Projet ICS", "start_date": "2027-01-01"}, headers=a).json()
    client.post("/api/events", json={"title": "Réunion de chantier n°3", "kind": "reunion_chantier", "project_id": p["id"],
                                     "start": "2027-02-10T08:00:00Z", "end": "2027-02-10T09:30:00Z", "location": "Rue des Lilas, Nantes"}, headers=a)
    client.post("/api/events", json={"title": "Privé de member", "start": "2027-02-11T08:00:00Z", "end": "2027-02-11T09:00:00Z"}, headers=ag["member"])
    url = client.post("/api/calendar/ics-token", headers=a).json()["url"]
    path = urlparse(url).path
    ics = client.get(path)
    assert ics.status_code == 200 and ics.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VCALENDAR" in ics.text and "SUMMARY:Réunion de chantier n°3" in ics.text and "Rue des Lilas\\, Nantes" in ics.text
    assert "Privé de member" not in ics.text and "Projet : ICS" in ics.text
    client.post("/api/calendar/ics-token", headers=a)                    # renouvellement : l'ancienne adresse ne marche plus
    assert client.get(path).status_code == 404
    # échéances : fin de tâche et remise de phase dans l'agenda
    client.post("/api/tasks", json={"project_id": p["id"], "name": "Dossier PC", "start_date": "2027-02-01", "duration_days": 5}, headers=a)
    cur = client.get(f"/api/projects/{p['id']}", headers=a).json()
    phases = [dict(ph, end="2027-02-20") if ph["code"] == "PC" else ph for ph in cur["phases"]]
    client.put(f"/api/projects/{p['id']}", json={"phases": phases, "version": cur["version"]}, headers=a)
    evs = client.get("/api/events?start=2027-02-01T00:00:00Z&end=2027-02-28T00:00:00Z&include_deadlines=true", headers=a).json()
    kinds = {e["kind"] for e in evs}
    assert {"reunion_chantier", "echeance_tache", "livrable"} <= kinds
    assert any(e["title"] == "Remise PC – ICS" for e in evs)
