"""Lot 4 : historique d'activité, connexions, journal technique, diagnostic, conservation."""
import io
import zipfile

from conftest import PASSWORD, new_agency


def test_activity_search_before_after_and_scope(client, agency, project):
    a = agency["admin"]
    pid = project["id"]
    r = client.put(f"/api/projects/{pid}", json={"budget_initial": 150000, "version": project["version"]}, headers=a)
    assert r.status_code == 200
    h = client.get(f"/api/history/activity?project_id={pid}&action=update", headers=a).json()
    row = h["items"][0]
    assert row["action_label"] == "Modification" and row["module"] == "projets" and row["user"] == "Admin Test"
    assert row["changes"]["budget_initial"] == {"avant": 100000.0, "apres": 150000.0} or row["changes"]["budget_initial"]["apres"] == 150000
    assert row["project"].startswith("T-01")
    # filtres
    assert client.get(f"/api/history/activity?user_id={agency['viewer_id']}", headers=a).json()["total"] == 0
    assert client.get("/api/history/activity?date_from=2000-01-01&date_to=2000-01-02", headers=a).json()["total"] == 0
    assert client.get("/api/history/activity?module=projets&q=Projet", headers=a).json()["total"] >= 1
    assert client.get("/api/history/activity?date_from=hier", headers=a).status_code == 422
    # périmètre d'un non-administrateur : pas de comptes, pas de projets non autorisés
    client.post("/api/users", json={"email": "z@test.fr", "full_name": "Z", "password": "Zzzzzz#2026"}, headers=a)
    conf = client.post("/api/projects", json={"code": "C9", "name": "Secret", "confidential": True}, headers=a).json()
    rows = client.get("/api/history/activity?limit=200", headers=agency["member"]).json()["items"]
    assert not any(x["entity"] == "users" for x in rows) and not any(x["project_id"] == conf["id"] for x in rows)
    # export CSV : valeurs avant → après, aucun secret
    csv = client.get(f"/api/history/activity/export?fmt=csv&project_id={pid}", headers=a)
    assert csv.status_code == 200 and "100000" in csv.text and "→" in csv.text
    assert client.get(f"/api/history/activity/export?fmt=pdf&project_id={pid}", headers=a).content.startswith(b"%PDF")


def test_connections_and_admin_only(client, agency):
    client.post("/api/auth/login", json={"email": agency["member_email"], "password": "faux"})
    client.post("/api/auth/login", json={"email": agency["member_email"], "password": PASSWORD})
    rows = client.get(f"/api/history/connections?user_id={agency['member_id']}", headers=agency["admin"]).json()["items"]
    assert {r["success"] for r in rows} == {True, False} and all(r["device"] for r in rows)
    assert "faux" not in str(rows)
    for url in ("/api/history/connections", "/api/history/errors", "/api/history/diagnostic", "/api/history/integrity"):
        assert client.get(url, headers=agency["manager"]).status_code == 403, url
    assert client.get("/api/history/connections/export?fmt=csv", headers=agency["admin"]).status_code == 200


def test_error_log_reference_and_redaction(client, app, agency):
    from fastapi.routing import APIRoute

    def boom():
        raise RuntimeError("panne simulée Bearer eyJhbGciOiJIUzI1NiJ9.abcdefghijklmnopqrstuvwxyz password=secret123")

    if not any(getattr(r, "path", "") == "/api/test-crash" for r in app.router.routes):
        app.router.routes.insert(0, APIRoute("/api/test-crash", boom, methods=["GET"]))
    from fastapi.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/test-crash", headers=agency["admin"])
    assert r.status_code == 500 and r.json()["ref"].startswith("E-") and r.json()["ref"] in r.json()["detail"]
    e = client.get(f"/api/history/errors/{r.json()['ref']}", headers=agency["admin"]).json()
    assert e["source"] == "python" and e["explanation"]
    assert "eyJhbGci" not in str(e) and "[masqué]" in e["message"]
    # erreur JavaScript remontée par l'interface
    j = client.post("/api/history/client-errors", json={"message": "TypeError: x is undefined", "stack": "at Foo", "route": "/finances"}, headers=agency["member"]).json()
    assert j["ok"] and client.get(f"/api/history/errors/{j['ref']}", headers=agency["admin"]).json()["module"] == "finances"
    # validation de formulaire refusée : consignée sans la valeur saisie
    client.post("/api/projects", json={"code": "V", "name": "V", "budget_initial": "douze mille"}, headers=agency["admin"])
    v = client.get("/api/history/errors?source=validation", headers=agency["admin"]).json()["items"]
    assert v and "douze" not in str(v)
    assert client.post(f"/api/history/errors/{j['ref']}/resolve", headers=agency["admin"]).status_code == 200
    d = client.get("/api/history/diagnostic", headers=agency["admin"]).json()
    assert d["errors_7d"] >= 2 and set(d["by_severity"]) == {"info", "avertissement", "erreur", "critique"} and d["integrity"]["intact"]


def test_retention_and_purge(client, agency):
    a = agency["admin"]
    assert client.put("/api/history/retention", json={"activity_days": 10}, headers=a).status_code == 422
    r = client.put("/api/history/retention", json={"activity_days": 365, "errors_days": 60}, headers=a).json()
    assert r["activity_days"] == 365 and r["errors_days"] == 60
    assert client.post("/api/history/purge", headers=a).status_code == 200
    assert client.get("/api/history/integrity", headers=a).json()["intact"]


def test_restore_backup_from_previous_version(client):
    """Une sauvegarde de la version 1.0 (sans les nouvelles tables) doit rester restaurable."""
    ag = new_agency(("admin",))
    h = ag["admin"]
    client.post("/api/projects", json={"code": "R1", "name": "Avant"}, headers=h)
    r = client.post("/api/backups", headers=h).json()
    data = client.get(f"/api/backups/{r['name']}", headers=h).content
    # retire les tables apparues depuis la 1.0 et recalcule le manifeste
    import hashlib
    import json

    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        man = json.loads(src.read("manifest.json"))
        for n in src.namelist():
            if n in ("data/comments.json", "data/notifications.json", "data/geo_layers.json", "manifest.json"):
                continue
            z.writestr(n, src.read(n))
        man["sha256"] = {k: v for k, v in man.get("sha256", {}).items() if k not in ("comments", "notifications", "geo_layers")}
        z.writestr("manifest.json", json.dumps(man))
    res = client.post("/api/restore?confirm=RESTAURER", files={"file": ("ancienne.zip", out.getvalue())}, headers=h)
    assert res.status_code == 200, res.text
    assert any(p["code"] == "R1" for p in client.get("/api/projects", headers=h).json())
