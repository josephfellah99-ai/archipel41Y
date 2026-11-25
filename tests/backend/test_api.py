"""Tests d'intégration de l'API (exécutés sur SQLite et sur PostgreSQL)."""
import io
import json
import uuid
import zipfile
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from conftest import DEMO, PASSWORD, new_agency, upload


# ------------------------------------------------------------------ installation et authentification
def test_health_and_setup_and_login(client):
    assert client.get("/api/health").json()["status"] == "ok"
    st = client.get("/api/setup/status").json()
    if st["needs_setup"]:
        r = client.post("/api/setup", json={"agency_name": "Atelier Réel", "admin_email": "admin@atelier.fr", "admin_name": "Admin",
                                            "admin_password": "court"})
        assert r.status_code == 422  # politique de mot de passe
        r = client.post("/api/setup", json={"agency_name": "Atelier Réel", "admin_email": "admin@atelier.fr", "admin_name": "Admin",
                                            "admin_password": PASSWORD})
        assert r.status_code == 201
    r = client.post("/api/setup", json={"agency_name": "Autre", "admin_email": "x@y.fr", "admin_name": "X", "admin_password": PASSWORD})
    assert r.status_code == 409  # configuration initiale unique
    r = client.post("/api/auth/login", json={"email": "admin@atelier.fr", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["user"]["role"] == "admin" and "password_hash" not in r.json()["user"]
    assert client.post("/api/auth/login", json={"email": "admin@atelier.fr", "password": "faux"}).status_code == 401


def test_users_and_permissions(client, agency):
    r = client.post("/api/users", json={"email": f"n{uuid.uuid4().hex[:5]}@t.fr", "full_name": "Nouveau", "role": "member", "password": PASSWORD},
                    headers=agency["admin"])
    assert r.status_code == 201
    assert client.post("/api/users", json={"email": "z@t.fr", "full_name": "Z", "role": "admin", "password": PASSWORD},
                       headers=agency["manager"]).status_code == 403
    # lecture seule
    assert client.get("/api/projects", headers=agency["viewer"]).status_code == 200
    assert client.post("/api/projects", json={"code": "V", "name": "V"}, headers=agency["viewer"]).status_code == 403
    # collaborateur : création oui, suppression non
    p = client.post("/api/projects", json={"code": "M", "name": "M"}, headers=agency["member"]).json()
    assert client.delete(f"/api/projects/{p['id']}", headers=agency["member"]).status_code == 403
    assert client.delete(f"/api/projects/{p['id']}", headers=agency["manager"]).status_code == 200
    # dernier administrateur protégé
    r = client.put(f"/api/users/{agency['admin_id']}", json={"role": "member"}, headers=agency["admin"])
    assert r.status_code == 409
    roles = client.get("/api/roles", headers=agency["viewer"]).json()
    assert {r["code"] for r in roles} == {"admin", "manager", "member", "viewer"}


def test_agency_isolation(client, agency, project):
    other = new_agency()
    assert client.get(f"/api/projects/{project['id']}", headers=other["admin"]).status_code == 404
    assert project["id"] not in [p["id"] for p in client.get("/api/projects", headers=other["admin"]).json()]
    r = client.put(f"/api/projects/{project['id']}", json={"name": "piraté"}, headers=other["admin"])
    assert r.status_code == 404
    r = client.post("/api/lots", json={"project_id": project["id"], "code": "01", "name": "X"}, headers=other["admin"])
    assert r.status_code == 404


def test_confidential_project_visible_only_to_team(client, agency):
    p = client.post("/api/projects", json={"code": "C", "name": "Secret", "confidential": True,
                                           "team": [{"user_id": agency["member_id"], "role": "x"}]}, headers=agency["admin"]).json()
    assert client.get(f"/api/projects/{p['id']}", headers=agency["member"]).status_code == 200
    assert client.get(f"/api/projects/{p['id']}", headers=agency["viewer"]).status_code == 403
    assert p["id"] not in [x["id"] for x in client.get("/api/projects", headers=agency["viewer"]).json()]


# ------------------------------------------------------------------ projets, concurrence, historique, hors ligne
def test_project_crud_versions_history_and_validation(client, agency):
    h = agency["admin"]
    assert client.post("/api/projects", json={"code": "", "name": "x"}, headers=h).status_code == 422
    assert client.post("/api/projects", json={"code": "D", "name": "x", "start_date": "2026-05-01", "end_date": "2026-01-01"}, headers=h).status_code == 422
    p = client.post("/api/projects", json={"code": "P1", "name": "Maison"}, headers=h).json()
    assert len(p["phases"]) == 10 and [x["code"] for x in p["phases"]][-1] == "AOR" and p["current_phase"] == "ESQ"
    r1 = client.put(f"/api/projects/{p['id']}", json={"name": "Maison A", "version": p["version"]}, headers=h)
    assert r1.status_code == 200 and r1.json()["version"] == p["version"] + 1
    r2 = client.put(f"/api/projects/{p['id']}", json={"name": "Maison B", "version": p["version"]}, headers=h)
    assert r2.status_code == 409 and r2.json()["detail"]["current"]["name"] == "Maison A"
    hist = client.get(f"/api/projects/{p['id']}/history", headers=h).json()
    assert hist[0]["changes"]["name"] == {"avant": "Maison", "apres": "Maison A"}


def test_offline_replay_is_idempotent(client, agency):
    cid = str(uuid.uuid4())
    h = {**agency["admin"], "X-Client-Id": cid}
    r1 = client.post("/api/clients", json={"name": "Client hors ligne"}, headers=h)
    r2 = client.post("/api/clients", json={"name": "Client hors ligne"}, headers=h)
    assert r1.json()["id"] == r2.json()["id"] == cid
    assert sum(1 for c in client.get("/api/clients", headers=agency["admin"]).json() if c["id"] == cid) == 1


def test_clients_companies_validation(client, agency):
    h = agency["admin"]
    assert client.post("/api/companies", json={"name": "X", "siret": "123"}, headers=h).status_code == 422
    assert client.post("/api/clients", json={"name": "X", "email": "pas-un-email"}, headers=h).status_code == 422
    c = client.post("/api/companies", json={"name": "Charpentes Test", "siret": "123 456 789 00012", "specialties": ["Charpente"],
                                            "contacts": [{"name": "Paul", "email": "p@x.fr"}]}, headers=h).json()
    assert c["siret"] == "12345678900012"
    assert client.get(f"/api/companies/{c['id']}/related", headers=h).status_code == 200


# ------------------------------------------------------------------ devis : import → revue → validation → comparaison → exports
def test_quote_workflow(client, agency, project):
    h, pid = agency["admin"], project["id"]
    lot = client.post("/api/lots", json={"project_id": pid, "code": "02", "name": "Gros œuvre", "budget": 36000}, headers=h).json()
    with open(DEMO / "DPGF_Lot02_GrosOeuvre.xlsx", "rb") as f:
        r = client.post("/api/dpgf/import", files={"file": ("DPGF.xlsx", f.read())}, data={"project_id": pid, "lot_id": lot["id"]}, headers=h)
    assert r.status_code == 201 and r.json()["count"] == 14
    with open(DEMO / "CCTP_Lot02_GrosOeuvre.pdf", "rb") as f:
        assert client.post("/api/cctp/import", files={"file": ("CCTP.pdf", f.read())}, data={"project_id": pid, "lot_id": lot["id"]}, headers=h).json()["count"] >= 8
    files = [("files", (n, open(DEMO / n, "rb").read())) for n in ("Devis_BatiOuest_Lot02_GrosOeuvre.pdf", "Devis_Durand_Lot02_GrosOeuvre.pdf")]
    r = client.post("/api/quotes/import", files=files, data={"project_id": pid, "lot_id": lot["id"]}, headers=h)
    assert r.status_code == 201, r.text
    quotes = [x["quote"] for x in r.json()]
    bo = next(q for q in quotes if q["reference"] == "BO-2026-118")
    assert bo["computed"]["total_ht"] == 34783.0 and any(a["code"] == "calcul_ligne" for a in bo["anomalies"])
    # correction humaine de la ligne erronée → recalcul déterministe
    lines = bo["lines"]
    for l in lines:
        if l["code"] == "3.3":
            l["total_ht"] = 3402
    r = client.put(f"/api/quotes/{bo['id']}/lines", json={"lines": lines}, headers=h)
    assert r.status_code == 200 and not any(a["code"] == "calcul_ligne" for a in r.json()["anomalies"])
    assert any(l["corrected"] for l in r.json()["lines"])
    bad = [dict(lines[0], status="nimporte")]
    assert client.put(f"/api/quotes/{bo['id']}/lines", json={"lines": bad}, headers=h).status_code == 422
    # validation réservée
    assert client.post(f"/api/quotes/{bo['id']}/validate", headers=agency["member"]).status_code == 403
    assert client.post(f"/api/quotes/{bo['id']}/validate", headers=agency["manager"]).json()["status"] == "valide"
    # comparaison
    r = client.post("/api/comparisons", json={"project_id": pid, "lot_id": lot["id"]}, headers=h)
    assert r.status_code == 201, r.text
    cmp = r.json()
    assert cmp["result"]["has_reference"] and len(cmp["result"]["summaries"]) == 2 and "Conclusion" in cmp["conclusion"]
    durand = next(s for s in cmp["result"]["summaries"] if "Durand" in s["company"])
    assert durand["counts"]["non_inclus"] >= 1 and durand["counts"]["non_renseigne"] >= 1
    for fmt, magic in (("xlsx", b"PK"), ("docx", b"PK"), ("pdf", b"%PDF"), ("csv", b"\xef\xbb\xbf")):
        e = client.get(f"/api/comparisons/{cmp['id']}/export?fmt={fmt}", headers=h)
        assert e.status_code == 200 and e.content.startswith(magic)
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(client.get(f"/api/comparisons/{cmp['id']}/export?fmt=xlsx", headers=h).content))
    assert {"Synthèse", "Comparatif détaillé"} <= set(wb.sheetnames)
    assert client.post("/api/comparisons", json={"project_id": pid, "quote_ids": [bo["id"]]}, headers=h).status_code == 422


def test_quote_zip_import(client, agency, project):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.write(DEMO / "Devis_MenuiseriesAtlantique_Lot05.xlsx", "offres/Devis_MenuiseriesAtlantique_Lot05.xlsx")
        zf.write(DEMO / "Devis_AluConceptOuest_Lot05.docx", "offres/Devis_AluConceptOuest_Lot05.docx")
    r = client.post("/api/quotes/import", files=[("files", ("offres.zip", buf.getvalue()))], data={"project_id": project["id"]}, headers=agency["admin"])
    assert r.status_code == 201 and len(r.json()) == 2
    totals = sorted(x["quote"]["computed"]["total_ht"] for x in r.json())
    assert totals == [15640.0, 18810.0]


# ------------------------------------------------------------------ documents
def test_documents_versions_search_and_downloads(client, agency, project):
    h = agency["admin"]
    r = upload(client, h, DEMO / "Reglement_PLU_FICTIF_Demo.pdf", "/api/documents/upload", project_id=project["id"], category="urbanisme")
    assert r.status_code == 201
    doc = r.json()["documents"][0]
    assert doc["text_status"] == "ok" and doc["category"] == "urbanisme"
    hits = client.get("/api/documents/search?q=emprise au sol zone UB", headers=h).json()
    assert hits and hits[0]["document_id"] == doc["id"] and "40 %" in hits[0]["text"]
    with open(DEMO / "Reglement_PLU_FICTIF_Demo.pdf", "rb") as f:
        r = client.post(f"/api/documents/{doc['id']}/versions", files={"file": ("Reglement_v2.pdf", f.read())}, data={"comment": "v2"}, headers=h)
    assert r.json()["document"]["current_version"] == 2
    d = client.get(f"/api/documents/{doc['id']}", headers=h).json()
    assert [v["number"] for v in d["versions"]] == [2, 1]
    dl = client.get(f"/api/documents/{doc['id']}/download?version=1", headers=h)
    assert dl.status_code == 200 and dl.content.startswith(b"%PDF") and "attachment" in dl.headers["content-disposition"]
    assert client.get(f"/api/documents/{doc['id']}/pages", headers=h).json()["pages"] >= 1
    png = client.get(f"/api/documents/{doc['id']}/page/1", headers=h)
    assert png.content.startswith(b"\x89PNG")
    z = client.post("/api/documents/export", json={"ids": [doc["id"]]}, headers=h)
    assert zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    with open(DEMO / "CCTP_Lot02_GrosOeuvre.pdf", "rb") as f:
        r = client.post(f"/api/documents/{doc['id']}/versions", files={"file": ("autre.docx", f.read())}, headers=h)
    assert r.status_code == 422  # format différent refusé


# ------------------------------------------------------------------ agenda
def test_agenda_conflicts_and_reminders(client, agency):
    h, uid = agency["admin"], agency["admin_id"]
    start = datetime.now(timezone.utc) + timedelta(minutes=20)
    ev = {"title": "Réunion A", "start": start.isoformat(), "end": (start + timedelta(hours=1)).isoformat(),
          "participants": [{"user_id": uid, "name": "Admin"}], "reminder_minutes": 30}
    r1 = client.post("/api/events", json=ev, headers=h).json()
    assert r1["conflicts"] == []
    r2 = client.post("/api/events", json={**ev, "title": "Réunion B", "start": (start + timedelta(minutes=30)).isoformat(),
                                          "end": (start + timedelta(minutes=90)).isoformat()}, headers=h).json()
    assert r2["conflicts"] and r2["conflicts"][0]["title"] == "Réunion A"
    assert client.post("/api/events", json={**ev, "end": (start - timedelta(hours=1)).isoformat()}, headers=h).status_code == 422
    rem = client.get("/api/events/reminders", headers=h).json()
    assert any(x["title"] == "Réunion A" for x in rem)
    eid = r1["event"]["id"]
    client.put(f"/api/events/{eid}", json={"minutes": "Décidé : report du coulage.\n- Action : Bâti Ouest doit fournir le PV avant vendredi."}, headers=h)
    s = client.post(f"/api/events/{eid}/summarize", headers=h).json()["summary"]
    assert "report du coulage" in s and "PV" in s
    rep = client.post("/api/reports", json={"kind": "compte_rendu", "fmt": "docx", "event_id": eid}, headers=h)
    assert rep.status_code == 201


# ------------------------------------------------------------------ planning et météo
def _mock_weather(monkeypatch, rainy=True):
    from app.services import weather

    def handler(request: httpx.Request):
        if "adresse" in request.url.host:
            return httpx.Response(200, json={"features": [{"geometry": {"coordinates": [-1.55, 47.21]}, "properties": {"label": "Nantes", "citycode": "44109"}}]})
        today = date.today()
        n = 10
        return httpx.Response(200, json={"daily": {
            "time": [(today + timedelta(days=i)).isoformat() for i in range(n)],
            "weather_code": [63 if (rainy and i < 4) else 1 for i in range(n)],
            "temperature_2m_max": [12] * n, "temperature_2m_min": [6] * n,
            "precipitation_sum": [15 if (rainy and i < 4) else 0 for i in range(n)],
            "precipitation_probability_max": [90 if i < 4 else 5 for i in range(n)],
            "wind_speed_10m_max": [15] * n, "wind_gusts_10m_max": [30] * n}})

    monkeypatch.setattr(weather, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))


def test_planning_schedule_weather_proposals(client, agency, project, monkeypatch):
    h, pid = agency["admin"], project["id"]
    today = date.today()
    a = client.post("/api/tasks", json={"project_id": pid, "name": "Terrassement", "start_date": (today - timedelta(days=10)).isoformat(),
                                        "duration_days": 5, "activity": "terrassement", "progress": 50}, headers=h).json()
    b = client.post("/api/tasks", json={"project_id": pid, "name": "Dallage béton", "start_date": today.isoformat(), "duration_days": 3,
                                        "activity": "beton", "depends_on": [a["id"]]}, headers=h).json()
    assert client.post("/api/tasks", json={"project_id": pid, "name": "x", "start_date": today.isoformat(), "activity": "inconnue"}, headers=h).status_code == 422
    s = client.get(f"/api/projects/{pid}/schedule", headers=h).json()
    ta = next(t for t in s["tasks"] if t["id"] == a["id"])
    assert ta["late"] and ta["late_days"] > 0 and ta["critical"]
    _mock_weather(monkeypatch)
    w = client.get(f"/api/projects/{pid}/weather", headers=h).json()
    assert not w["forecast"]["simulated"] and w["analysis"][0]["task_id"] == b["id"] and w["analysis"][0]["suggested_start"]
    props = client.post(f"/api/projects/{pid}/weather/proposals", headers=h).json()
    assert len(props) == 1 and props[0]["status"] == "en_attente"
    assert client.post(f"/api/proposals/{props[0]['id']}/accept", headers=agency["member"]).status_code == 403  # validation requise
    r = client.post(f"/api/proposals/{props[0]['id']}/accept", headers=agency["manager"]).json()
    assert r["proposal"]["status"] == "acceptee" and "Dallage béton" in r["moved_tasks"]
    moved = client.get(f"/api/tasks/{b['id']}", headers=h).json()
    assert moved["start_date"] == props[0]["payload"]["to"]


def test_weather_service_down_is_reported(client, agency, project, monkeypatch):
    from app.services import weather

    def boom(request):
        raise httpx.ConnectError("réseau coupé")

    monkeypatch.setattr(weather, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(boom)))
    r = client.get(f"/api/projects/{project['id']}/weather", headers=agency["admin"])
    assert r.status_code == 503 and "injoignable" in r.json()["detail"]


# ------------------------------------------------------------------ urbanisme (réponses simulées des API officielles)
def _mock_urbanisme(monkeypatch, with_zone=True):
    from app.services import urbanisme

    ring = [[-1.5541, 47.2180], [-1.5533, 47.2180], [-1.5533, 47.2185], [-1.5541, 47.2185], [-1.5541, 47.2180]]

    def handler(request: httpx.Request):
        u = str(request.url)
        if "api-adresse" in u:
            return httpx.Response(200, json={"features": [{"geometry": {"coordinates": [-1.5537, 47.21825]}, "properties": {"label": "12 rue X 44000 Nantes", "citycode": "44109", "score": 0.95}}]})
        if "/cadastre/parcelle" in u:
            return httpx.Response(200, json={"features": [{"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": [[ring]]},
                                                           "properties": {"code_dep": "44", "code_com": "109", "section": "AB", "numero": "0123", "nom_com": "Nantes", "contenance": 2290, "idu": "44109000AB0123"}}]})
        if "/gpu/zone-urba" in u:
            return httpx.Response(200, json={"features": [{"properties": {"libelle": "UB", "libelong": "Zone urbaine mixte", "typezone": "U", "destdomi": "habitat"}}] if with_zone else []})
        if "/gpu/assiette-sup-s" in u:
            return httpx.Response(200, json={"features": [{"properties": {"suptype": "ac1", "nomsuplitt": "Abords de l'église"}}]})
        if "/gpu/document" in u:
            return httpx.Response(200, json={"features": [{"properties": {"du_type": "PLUi", "nom": "PLUm Nantes", "datappro": "2019-04-05"}}]})
        if "/gpu/" in u:
            return httpx.Response(200, json={"features": []})
        if "georisques" in u and "gaspar" in u:
            return httpx.Response(200, json={"data": [{"risques_detail": [{"libelle_risque_long": "Inondation"}]}]})
        if "georisques" in u and "zonage_sismique" in u:
            return httpx.Response(200, json={"data": [{"zone_sismicite": "3 - Modérée"}]})
        if "georisques" in u and "rga" in u:
            return httpx.Response(503)
        return httpx.Response(404)

    monkeypatch.setattr(urbanisme, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))


def test_urbanisme_analysis_sources_and_unavailable(client, agency, project, monkeypatch):
    h = agency["admin"]
    _mock_urbanisme(monkeypatch)
    r = client.post("/api/urbanisme/analyses", json={"query_type": "adresse", "query": "12 rue X Nantes", "project_id": project["id"]}, headers=h)
    assert r.status_code == 201, r.text
    a = r.json()
    res = a["results"]
    assert a["mode"] == "reel" and a["area_m2"] == 2290 and a["section"] == "AB"
    assert res["zones"][0]["code"] == "UB" and res["patrimoine"][0]["category"] == "AC1"
    assert res["risques"]["sismicite"] == "3 - Modérée" and "argiles" not in res["risques"]
    assert any("argiles" in u["source"] for u in a["unavailable"])  # service en échec : signalé
    assert all(s["consulted_at"] for s in a["sources"])
    p = client.get(f"/api/projects/{project['id']}", headers=h).json()
    assert p["terrain"]["zone_plu"] == "UB" and p["latitude"]
    doc = upload(client, h, DEMO / "Reglement_PLU_FICTIF_Demo.pdf", "/api/documents/upload", category="urbanisme").json()["documents"][0]
    a2 = client.post(f"/api/urbanisme/analyses/{a['id']}/plu", json={"document_id": doc["id"]}, headers=h).json()
    ind = {i["label"]: i for i in a2["rules"]["feasibility"]["indicators"]}
    assert ind["Emprise au sol maximale indicative"]["value"] == 916.0
    rep = client.post("/api/reports", json={"kind": "urbanisme", "fmt": "pdf", "analysis_id": a["id"]}, headers=h)
    assert rep.status_code == 201
    assert client.post("/api/urbanisme/analyses", json={"query_type": "cadastre", "query": "n'importe quoi"}, headers=h).status_code == 422
    assert client.get("/api/urbanisme/legifrance?q=emprise", headers=h).status_code == 409  # non configuré : dit clairement


def test_urbanisme_no_zoning_reported(client, agency, monkeypatch):
    _mock_urbanisme(monkeypatch, with_zone=False)
    a = client.post("/api/urbanisme/analyses", json={"query_type": "coordonnees", "query": "47.21825, -1.5537"}, headers=agency["admin"]).json()
    assert a["results"]["zones"] == [] and any("RNU" in u["reason"] for u in a["unavailable"])


# ------------------------------------------------------------------ assistant IA (RAG, confidentialité)
def test_assistant_extractive_and_provider_confidentiality(client, agency, monkeypatch):
    h = agency["admin"]
    conf = client.post("/api/projects", json={"code": "S", "name": "Secret", "confidential": True}, headers=h).json()
    upload(client, h, DEMO / "Reglement_PLU_FICTIF_Demo.pdf", "/api/documents/upload", project_id=conf["id"], confidential="true")
    r = client.post("/api/assistant/ask", json={"question": "Quelle hauteur maximale en zone UB ?"}, headers=h).json()
    assert r["mode"] == "extractif" and r["sources"] and "9 mètres" in r["answer"]
    # fournisseur externe simulé : les contenus confidentiels ne doivent jamais lui parvenir
    from ai.llm.providers import ChatResult, Provider
    from app.services import ai as ai_service

    seen = []

    class FakeExternal(Provider):
        name, external = "fake", True
        model = "fake-1"

        @property
        def available(self):
            return True

        def chat(self, system, messages, max_tokens=4000):
            seen.append(messages[-1]["content"])
            return ChatResult(text="Réponse [S1]", provider="fake", model="fake-1")

    monkeypatch.setattr(ai_service, "get_provider", lambda db, aid: FakeExternal())
    monkeypatch.setattr(ai_service, "get_config", lambda db, aid: {"allow_documents": True, "allow_confidential": False})
    r = client.post("/api/assistant/ask", json={"question": "Hauteur en zone UB ?"}, headers=h).json()
    assert r["mode"] == "generatif" and seen and "9 mètres" not in seen[-1]
    r = client.post("/api/assistant/ask", json={"question": "Hauteur ?", "project_id": conf["id"]}, headers=h).json()
    assert r["mode"] == "extractif"  # projet confidentiel : pas d'envoi externe
    monkeypatch.setattr(ai_service, "get_config", lambda db, aid: {"allow_documents": True, "allow_confidential": True})
    client.post("/api/assistant/ask", json={"question": "Hauteur en zone UB ?"}, headers=h)
    assert "9 mètres" in seen[-1]  # autorisation explicite de l'administrateur
    convs = client.get("/api/conversations", headers=h).json()
    assert convs and client.get("/api/conversations/" + convs[0]["id"], headers=agency["manager"]).status_code == 403


def test_settings_secrets_never_returned(client, agency):
    h = agency["admin"]
    r = client.put("/api/settings/ai", json={"provider": "anthropic", "api_key": "sk-ant-TESTSECRET-1234567890"}, headers=h).json()
    assert "TESTSECRET" not in json.dumps(r) and r["api_key_set"]
    g = client.get("/api/settings/ai", headers=agency["viewer"]).json()
    assert "TESTSECRET" not in json.dumps(g)
    from app.db import SessionLocal
    from app.models import Setting

    db = SessionLocal()
    raw = db.query(Setting).filter(Setting.agency_id == agency["agency_id"], Setting.key == "ai").first().value
    db.close()
    assert "TESTSECRET" not in json.dumps(raw)  # chiffré au repos
    r = client.put("/api/settings/ai", json={"provider": "anthropic", "model": "claude-opus-5-5", "api_key": ""}, headers=h).json()
    assert r["api_key_set"]  # champ vide = secret conservé
    assert client.put("/api/settings/ai", json={"provider": "aucun"}, headers=agency["manager"]).status_code == 403


# ------------------------------------------------------------------ finances, tableau de bord, rapports
def test_finances_dashboard_reports(client, agency, project):
    h, pid = agency["admin"], project["id"]
    lot = client.post("/api/lots", json={"project_id": pid, "code": "03", "name": "Charpente", "budget": 20000}, headers=h).json()
    for kind, amount, status, due in (("marche", 21000, "valide", None), ("travaux_supp", 1000, "valide", None),
                                      ("situation", 5000, "emis", (date.today() - timedelta(days=3)).isoformat()), ("paiement", 2000, "paye", None)):
        r = client.post("/api/finance-entries", json={"project_id": pid, "lot_id": lot["id"], "kind": kind, "label": kind, "entry_date": date.today().isoformat(),
                                                      "amount_ht": amount, "vat_rate": 20, "status": status, "due_date": due}, headers=h)
        assert r.status_code == 201 and r.json()["amount_ttc"] == round(amount * 1.2, 2)
    f = client.get(f"/api/projects/{pid}/finances", headers=h).json()
    assert f["engage"] == 22000 and f["facture"] == 5000 and f["paye"] == 2000 and f["en_retard"] == 1
    lotf = f["by_lot"][0]
    assert lotf["ecart"] == 2000 and lotf["ecart_pct"] == 10.0
    d = client.get(f"/api/dashboard?project_id={pid}", headers=h).json()
    assert d["kpis"]["projets_actifs"] == 1 and any("dépassement" in a["message"] for a in d["alerts"])
    assert client.get("/api/dashboard/daily-summary", headers=h).json()["source"] == "regles"
    for kind in ("chantier", "financier", "synthese"):
        for fmt in ("pdf", "xlsx", "csv", "docx"):
            r = client.post("/api/reports", json={"kind": kind, "fmt": fmt, "project_id": pid}, headers=h)
            assert r.status_code == 201, (kind, fmt, r.text)
            dl = client.get(r.json()["download_url"], headers=h)
            assert dl.status_code == 200 and len(dl.content) > 100
    assert len(client.get(f"/api/reports?project_id={pid}", headers=h).json()) == 12


# ------------------------------------------------------------------ sauvegarde / restauration
def test_backup_and_restore_roundtrip(client):
    ag = new_agency(("admin",))
    h = ag["admin"]
    p = client.post("/api/projects", json={"code": "B1", "name": "À sauvegarder"}, headers=h).json()
    upload(client, h, DEMO / "CCTP_Lot02_GrosOeuvre.pdf", "/api/documents/upload", project_id=p["id"])
    b = client.post("/api/backups", headers=h).json()
    assert b["manifest"]["counts"]["projects"] == 1 and b["manifest"]["files"] == 1
    data = client.get(f"/api/backups/{b['name']}", headers=h).content
    client.put(f"/api/projects/{p['id']}", json={"name": "Modifié après sauvegarde"}, headers=h)
    client.post("/api/projects", json={"code": "B2", "name": "Créé après"}, headers=h)
    assert client.post("/api/restore?confirm=non", files={"file": ("b.zip", data)}, headers=h).status_code == 422
    r = client.post("/api/restore?confirm=RESTAURER", files={"file": ("b.zip", data)}, headers=h)
    assert r.status_code == 200, r.text
    names = [x["name"] for x in client.get("/api/projects", headers=h).json()]
    assert names == ["À sauvegarder"]
    doc = client.get("/api/documents", headers=h).json()[0]
    assert client.get(f"/api/documents/{doc['id']}/download", headers=h).content.startswith(b"%PDF")
    assert client.get("/api/documents/search?q=semelles filantes C25/30", headers=h).json()  # index RAG reconstruit
    corrupted = bytearray(data)
    z = zipfile.ZipFile(io.BytesIO(data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as out:
        for i in z.infolist():
            content = z.read(i)
            if i.filename == "data/projects.json":
                content = content.replace("sauvegarder".encode(), b"altere")
            out.writestr(i, content)
    r = client.post("/api/backups/inspect", files={"file": ("x.zip", buf.getvalue())}, headers=h)
    assert r.status_code == 422 and "corrompue" in r.json()["detail"]
    assert client.post("/api/backups", headers=new_agency(("manager",))["manager"]).status_code == 403


def test_demo_space_is_separate(client):
    st = client.get("/api/setup/status").json()
    if not st["has_demo"]:
        assert client.post("/api/demo", json={"password": "faible"}).status_code == 422
        assert client.post("/api/demo", json={"password": PASSWORD}).status_code == 200
    assert client.post("/api/demo", json={"password": PASSWORD}).status_code == 409
    tok = client.post("/api/auth/login", json={"email": "demo@archipel41.demo", "password": PASSWORD}).json()
    assert tok["agency"]["is_demo"] is True
    hd = {"Authorization": "Bearer " + tok["token"]}
    codes = [p["code"] for p in client.get("/api/projects", headers=hd).json()]
    assert "DEMO-24-07" in codes
    real = client.post("/api/auth/login", json={"email": "admin@atelier.fr", "password": PASSWORD})
    if real.status_code == 200:
        hr = {"Authorization": "Bearer " + real.json()["token"]}
        assert "DEMO-24-07" not in [p["code"] for p in client.get("/api/projects", headers=hr).json()]
