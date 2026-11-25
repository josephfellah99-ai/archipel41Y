"""Synchronisation local-first : poste de bureau (SQLite) ↔ serveur central."""
import hashlib

import httpx

from conftest import PASSWORD, ROOT


def login(c, url, email):
    r = (c.post if hasattr(c, "post") else httpx.post)(url + "/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_full_sync_cycle(server, desktop):
    S = httpx.Client(base_url=server.url, timeout=30)
    # --- serveur central : agence + administrateur
    r = S.post("/api/setup", json={"agency_name": "Agence Centrale", "admin_email": "central@agence.fr", "admin_name": "Central",
                                   "admin_password": PASSWORD})
    assert r.status_code == 201
    hs = {"Authorization": "Bearer " + r.json()["token"]}
    S.post("/api/clients", json={"name": "Client existant sur le serveur"}, headers=hs)

    # --- poste de bureau : agence locale, travail hors ligne
    r = desktop.post("/api/setup", json={"agency_name": "Poste portable", "admin_email": "archi@agence.fr", "admin_name": "Archi",
                                         "admin_password": PASSWORD})
    hd = {"Authorization": "Bearer " + r.json()["token"]}
    p = desktop.post("/api/projects", json={"code": "LOC-1", "name": "Projet créé sur le poste"}, headers=hd).json()
    pdf = (ROOT / "database/seeds/demo_files/CCTP_Lot02_GrosOeuvre.pdf").read_bytes()
    doc = desktop.post("/api/documents/upload", files={"files": ("CCTP.pdf", pdf)}, data={"project_id": p["id"]}, headers=hd).json()["documents"][0]
    st = desktop.get("/api/sync/status", headers=hd).json()
    assert st["mode"] == "desktop" and not st["configured"] and st["pending_changes"] >= 4

    # --- raccordement du poste au serveur (l'agence locale adopte l'identifiant de l'agence centrale)
    r = desktop.post("/api/sync/configure", json={"server_url": server.url, "email": "central@agence.fr", "password": PASSWORD}, headers=hd)
    assert r.status_code == 200 and r.json()["relinked"]
    hd = login(desktop, "", "archi@agence.fr")  # nouveau jeton (agence changée)
    r = desktop.post("/api/sync/run", headers=hd)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["push"]["accepted"] >= 4 and res["push"]["conflicts"] == 0 and res["push"]["files"] == 1

    # le serveur a reçu projet, document et fichier (intégrité vérifiée)
    sp = {x["code"]: x for x in S.get("/api/projects", headers=hs).json()}
    assert "LOC-1" in sp
    sdoc = S.get(f"/api/documents/{doc['id']}", headers=hs).json()
    blob = S.get(f"/api/documents/{doc['id']}/download", headers=hs).content
    assert hashlib.sha256(blob).hexdigest() == hashlib.sha256(pdf).hexdigest() and sdoc["name"] == "CCTP.pdf"
    # … et le poste a reçu les données du serveur
    names = [c["name"] for c in desktop.get("/api/clients", headers=hd).json()]
    assert "Client existant sur le serveur" in names
    # l'utilisateur local est désormais connu du serveur (même mot de passe)
    login(S, "", "archi@agence.fr")

    # --- modification concurrente → conflit détecté, jamais écrasé silencieusement
    sv = S.get(f"/api/projects/{p['id']}", headers=hs).json()
    assert S.put(f"/api/projects/{p['id']}", json={"name": "Nom modifié au bureau (serveur)", "version": sv["version"]}, headers=hs).status_code == 200
    dv = desktop.get(f"/api/projects/{p['id']}", headers=hd).json()
    desktop.put(f"/api/projects/{p['id']}", json={"name": "Nom modifié sur le chantier (poste)", "version": dv["version"]}, headers=hd)
    res = desktop.post("/api/sync/run", headers=hd).json()
    assert res["push"]["conflicts"] == 1
    conflicts = [c for c in desktop.get("/api/sync/conflicts", headers=hd).json() if c["status"] == "ouvert"]
    assert len(conflicts) == 1 and conflicts[0]["remote_data"]["name"] == "Nom modifié au bureau (serveur)"
    assert desktop.post(f"/api/sync/conflicts/{conflicts[0]['id']}/resolve", json={"keep": "local"}, headers=hd).status_code == 200
    res = desktop.post("/api/sync/run", headers=hd).json()
    assert res["push"]["accepted"] >= 1 and res["push"]["conflicts"] == 0
    assert S.get(f"/api/projects/{p['id']}", headers=hs).json()["name"] == "Nom modifié sur le chantier (poste)"

    # --- conflit résolu en faveur du serveur
    sv = S.get(f"/api/projects/{p['id']}", headers=hs).json()
    S.put(f"/api/projects/{p['id']}", json={"progress": 40, "version": sv["version"]}, headers=hs)
    dv = desktop.get(f"/api/projects/{p['id']}", headers=hd).json()
    desktop.put(f"/api/projects/{p['id']}", json={"progress": 55, "version": dv["version"]}, headers=hd)
    desktop.post("/api/sync/run", headers=hd)
    c = [c for c in desktop.get("/api/sync/conflicts", headers=hd).json() if c["status"] == "ouvert"][0]
    desktop.post(f"/api/sync/conflicts/{c['id']}/resolve", json={"keep": "remote"}, headers=hd)
    assert desktop.get(f"/api/projects/{p['id']}", headers=hd).json()["progress"] == 40

    # --- coupure réseau : le poste continue de fonctionner, les modifications attendent
    server.stop()
    desktop.post("/api/clients", json={"name": "Client saisi hors connexion"}, headers=hd)
    r = desktop.post("/api/sync/run", headers=hd)
    assert r.status_code == 503 and "injoignable" in r.json()["detail"].lower()
    st = desktop.get("/api/sync/status", headers=hd).json()
    assert st["pending_changes"] >= 1 and st["last_error"]
    server.start()
    res = desktop.post("/api/sync/run", headers=hd).json()
    assert res["push"]["accepted"] >= 1
    assert "Client saisi hors connexion" in [x["name"] for x in S.get("/api/clients", headers=hs).json()]
    assert desktop.get("/api/sync/status", headers=hd).json()["pending_changes"] == 0
