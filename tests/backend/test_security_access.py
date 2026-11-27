"""Lots 2 et 3 : modes de connexion, autorisations par module et par projet, comptes, invitations,
accès invité (isolement), commentaires et notifications. Toutes les vérifications sont faites côté serveur."""
import io

import pytest

from conftest import PASSWORD, new_agency


def login(client, email, mode=None, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password, **({"mode": mode} if mode else {})})


def set_perms(client, ag, role, perms):
    r = client.put(f"/api/users/{ag[role + '_id']}", json={"permissions": perms}, headers=ag["admin"])
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ modes de connexion
def test_login_modes_and_connection_log(client, agency):
    assert login(client, agency["member_email"], "admin").status_code == 403          # collaborateur ≠ administrateur
    assert login(client, agency["member_email"], "collaborateur").status_code == 200
    assert login(client, agency["admin_email"], "admin").status_code == 200
    assert login(client, agency["admin_email"], "admin", "mauvais").status_code == 401
    logs = client.get("/api/history/connections", headers=agency["admin"])
    if logs.status_code == 200:  # module historique (lot 4)
        rows = logs.json()["items"]
        assert any(not r["success"] and r["reason"] == "identifiants incorrects" for r in rows)
        assert all("password" not in str(r).lower() or "mot de passe" in str(r).lower() for r in rows)


def test_roles_catalog(client, agency):
    roles = {r["code"]: r for r in client.get("/api/roles", headers=agency["viewer"]).json()}
    assert set(roles) == {"admin", "manager", "member", "viewer"}
    assert roles["manager"]["label"] == "Gestionnaire" and roles["viewer"]["label"] == "Lecteur"
    cat = client.get("/api/permissions/catalog", headers=agency["viewer"]).json()
    assert {"finances", "devis", "documents", "terrain"} <= {m["code"] for m in cat["modules"]}


# ------------------------------------------------------------------ autorisations par module (côté serveur)
def test_module_permissions_enforced_server_side(client, agency, project):
    pid = project["id"]
    set_perms(client, agency, "member", {"modules": {"finances": "none", "agenda": "read"}})
    m = agency["member"]
    for url in ("/api/finance-entries", "/api/finances/overview", f"/api/projects/{pid}/finances", "/api/budget-lines"):
        assert client.get(url, headers=m).status_code == 403, url
    assert client.get("/api/projects", headers=m).status_code == 200           # le reste reste accessible
    assert client.get("/api/events", headers=m).status_code == 200              # agenda en consultation
    r = client.post("/api/events", json={"title": "RDV", "start": "2027-01-11T08:00:00Z", "end": "2027-01-11T09:00:00Z"}, headers=m)
    assert r.status_code == 403 and "Agenda" in r.json()["detail"]
    me = client.get("/api/auth/me", headers=m).json()
    assert me["permissions"]["modules"]["finances"] == "none" and me["permissions"]["modules"]["agenda"] == "read"
    # un lecteur peut recevoir le droit de modifier un module précis
    set_perms(client, agency, "viewer", {"modules": {"annuaire": "write"}})
    assert client.post("/api/clients", json={"name": "Client autorisé"}, headers=agency["viewer"]).status_code == 201
    assert client.post("/api/projects", json={"code": "X", "name": "Interdit"}, headers=agency["viewer"]).status_code == 403
    # seul un administrateur modifie les autorisations
    r = client.put(f"/api/users/{agency['member_id']}", json={"permissions": {"modules": {"finances": "full"}}}, headers=agency["member"])
    assert r.status_code == 200 and client.get("/api/finance-entries", headers=m).status_code == 403
    # module inconnu refusé
    assert client.put(f"/api/users/{agency['member_id']}", json={"permissions": {"modules": {"pirate": "full"}}}, headers=agency["admin"]).status_code == 422


def test_project_permissions(client, agency, project):
    other = client.post("/api/projects", json={"code": "T-02", "name": "Autre projet"}, headers=agency["admin"]).json()
    # projets attribués uniquement
    client.put(f"/api/projects/{project['id']}", json={"team": [{"user_id": agency["member_id"], "role": "Chef de projet"}],
                                                       "version": project["version"]}, headers=agency["admin"])
    set_perms(client, agency, "member", {"assigned_only": True})
    ids = {p["id"] for p in client.get("/api/projects", headers=agency["member"]).json()}
    assert project["id"] in ids and other["id"] not in ids
    assert client.get(f"/api/projects/{other['id']}", headers=agency["member"]).status_code in (403, 404)
    # consultation seule sur un projet
    set_perms(client, agency, "member", {"projects": {project["id"]: "read"}})
    cur = client.get(f"/api/projects/{project['id']}", headers=agency["member"]).json()
    r = client.put(f"/api/projects/{project['id']}", json={"name": "Modifié", "version": cur["version"]}, headers=agency["member"])
    assert r.status_code == 403 and "consultation" in r.json()["detail"]
    assert client.post("/api/lots", json={"project_id": project["id"], "code": "01", "name": "Lot"}, headers=agency["member"]).status_code == 403
    assert client.post("/api/lots", json={"project_id": other["id"], "code": "01", "name": "Lot"}, headers=agency["member"]).status_code == 201
    # projet masqué
    set_perms(client, agency, "member", {"projects": {other["id"]: "none"}})
    assert other["id"] not in {p["id"] for p in client.get("/api/projects", headers=agency["member"]).json()}


# ------------------------------------------------------------------ comptes
def test_account_lifecycle(client, agency):
    a = agency["admin"]
    r = client.post("/api/users", json={"email": "nouveau@test.fr", "full_name": "Nouveau Collab", "role": "member",
                                        "password": "Nouveau#2026x", "permissions": {"modules": {"finances": "none"}}}, headers=a)
    assert r.status_code == 201 and r.json()["permissions"]["modules"]["finances"] == "none"
    uid = r.json()["id"]
    assert client.post("/api/users", json={"email": "x@test.fr", "full_name": "X", "password": "Nouveau#2026x"}, headers=agency["manager"]).status_code == 403
    # désactivation → connexion refusée ; réactivation
    client.put(f"/api/users/{uid}", json={"active": False}, headers=a)
    assert login(client, "nouveau@test.fr", password="Nouveau#2026x").status_code == 403
    client.put(f"/api/users/{uid}", json={"active": True}, headers=a)
    assert login(client, "nouveau@test.fr", password="Nouveau#2026x").status_code == 200
    # plusieurs administrateurs
    client.put(f"/api/users/{agency['manager_id']}", json={"role": "admin"}, headers=a)
    assert client.get("/api/invitations", headers=agency["manager"]).status_code == 200
    # suppression : pas soi-même ; compte supprimé → plus de connexion ; adresse réutilisable
    assert client.delete(f"/api/users/{agency['admin_id']}", headers=a).status_code == 409
    assert client.delete(f"/api/users/{uid}", headers=agency["member"]).status_code == 403
    assert client.delete(f"/api/users/{uid}", headers=a).status_code == 200
    assert login(client, "nouveau@test.fr", password="Nouveau#2026x").status_code == 401
    assert client.post("/api/users", json={"email": "nouveau@test.fr", "full_name": "Nouveau 2", "password": "Nouveau#2026x"}, headers=a).status_code == 201


# ------------------------------------------------------------------ invitations et accès invité
def _doc(client, headers, project_id, name, category="plan"):
    pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
    r = client.post("/api/documents/upload", files={"files": (name, pdf, "application/pdf")},
                    data={"project_id": project_id, "category": category}, headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    return (body[0] if isinstance(body, list) else body.get("documents", [body])[0])


def test_invitation_project_guest_isolation(client, agency, project):
    a = agency["admin"]
    other = client.post("/api/projects", json={"code": "T-09", "name": "Projet non partagé"}, headers=a).json()
    plan = _doc(client, a, project["id"], "Plan_RDC.pdf", "plan")
    draft = _doc(client, a, project["id"], "Plan_brouillon.pdf", "plan")
    secret = _doc(client, a, project["id"], "Devis_confidentiel.pdf", "devis")
    assert client.put(f"/api/documents/{plan['id']}", json={"status": "valide"}, headers=a).status_code == 200
    assert client.put(f"/api/documents/{draft['id']}", json={"status": "valide"}, headers=agency["member"]).status_code == 403
    assert client.post("/api/invitations", json={"kind": "projet", "label": "x", "project_ids": [project["id"]]}, headers=agency["member"]).status_code == 403
    r = client.post("/api/invitations", json={"kind": "projet", "label": "Présentation M. Martin", "guest_name": "M. Martin",
                                              "project_ids": [project["id"]], "modules": ["fiche", "documents"], "max_uses": 2,
                                              "valid_days": 3, "can_download": False, "can_comment": True}, headers=a)
    assert r.status_code == 201, r.text
    inv, code = r.json(), r.json()["code"]
    assert len(code) == 14 and code.count("-") == 2
    listed = client.get("/api/invitations", headers=a).json()
    assert all("code" not in i and "code_hash" not in i for i in listed)     # jamais réaffiché
    g = client.post("/api/guest/redeem", json={"code": code.lower()}).json()
    gh = {"Authorization": f"Bearer {g['token']}"}
    # aucune route standard n'accepte un invité
    for url in ("/api/projects", f"/api/projects/{project['id']}", "/api/documents", "/api/users", "/api/finance-entries",
                "/api/settings/ai", "/api/invitations", "/api/notifications", "/api/audit"):
        assert client.get(url, headers=gh).status_code == 403, url
    assert client.post("/api/projects", json={"code": "Z", "name": "Z"}, headers=gh).status_code == 403
    me = client.get("/api/auth/me", headers=gh).json()
    assert me["user"]["role"] == "guest" and me["guest"]["projects"][0]["id"] == project["id"]
    # projet partagé : fiche sans données financières
    p = client.get(f"/api/guest/projects/{project['id']}", headers=gh).json()
    assert p["name"] == "Projet de test" and "budget_initial" not in p and "team" not in p
    assert client.get(f"/api/guest/projects/{other['id']}", headers=gh).status_code == 403
    # documents : uniquement validés, catégories autorisées ; pas de téléchargement
    docs = {d["name"] for d in client.get(f"/api/guest/projects/{project['id']}/documents", headers=gh).json()}
    assert docs == {"Plan_RDC.pdf"}
    assert client.get(f"/api/guest/documents/{draft['id']}/file", headers=gh).status_code == 403
    assert client.get(f"/api/guest/documents/{secret['id']}/file", headers=gh).status_code == 403
    assert client.get(f"/api/guest/documents/{plan['id']}/file", headers=gh).status_code == 200
    assert client.get(f"/api/guest/documents/{plan['id']}/file?download=true", headers=gh).status_code == 403
    assert client.get(f"/api/guest/projects/{project['id']}/planning", headers=gh).status_code == 403   # module non partagé
    # commentaire invité → notification à l'équipe
    client.put(f"/api/projects/{project['id']}", json={"team": [{"user_id": agency["member_id"]}],
                                                       "version": client.get(f"/api/projects/{project['id']}", headers=a).json()["version"]}, headers=a)
    assert client.post("/api/guest/comments", json={"entity": "projects", "entity_id": project["id"], "body": "Merci pour la présentation."}, headers=gh).status_code == 201
    notes = client.get("/api/notifications", headers=agency["member"]).json()["items"]
    assert any(n["kind"] == "commentaire" and "invité" in (n["body"] or "") for n in notes)
    # usages limités
    assert client.post("/api/guest/redeem", json={"code": code}).status_code == 200
    r = client.post("/api/guest/redeem", json={"code": code})
    assert r.status_code == 401 and "nombre de fois" in r.json()["detail"]
    # révocation immédiate : la session ouverte est coupée
    client.post(f"/api/invitations/{inv['id']}/revoke", headers=a)
    assert client.get(f"/api/guest/projects/{project['id']}", headers=gh).status_code == 401
    # un invité d'une autre agence ne voit rien
    other_ag = new_agency(("admin",))
    assert client.get("/api/invitations", headers=other_ag["admin"]).json() == []


@pytest.fixture(autouse=True)
def _reset_throttle():
    from app.routers import guest

    guest._TRIES.clear()
    yield
    guest._TRIES.clear()


def test_invitation_bruteforce_and_expiry(client, agency, project):
    from app.db import SessionLocal
    from app.models import Invitation
    from datetime import datetime, timedelta, timezone

    r = client.post("/api/invitations", json={"kind": "projet", "label": "Expirée", "project_ids": [project["id"]]}, headers=agency["admin"]).json()
    db = SessionLocal()
    inv = db.get(Invitation, r["id"])
    inv.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    db.close()
    assert client.post("/api/guest/redeem", json={"code": r["code"]}).json()["detail"] == "Cette invitation a expiré."
    statuses = [client.post("/api/guest/redeem", json={"code": f"AAAA-BBBB-CC{i:02d}"}, headers={"X-Forwarded-For": "1.2.3.4"}).status_code for i in range(12)]
    assert 429 in statuses                         # limitation des tentatives


def test_demo_invitation(client, agency):
    r = client.post("/api/invitations", json={"kind": "demo", "label": "Découverte"}, headers=agency["admin"]).json()
    res = client.post("/api/guest/redeem", json={"code": r["code"]})
    if res.status_code == 409:   # espace de démonstration non créé
        assert client.post("/api/demo", json={"password": "Demo#Archipel41"}).status_code in (200, 201, 409)
        res = client.post("/api/guest/redeem", json={"code": r["code"]})
    assert res.status_code == 200 and res.json()["kind"] == "demo"
    h = {"Authorization": f"Bearer {res.json()['token']}"}
    me = client.get("/api/auth/me", headers=h).json()
    assert me["agency"]["is_demo"] is True and me["agency"]["id"] != agency["agency_id"]
    # aucune donnée de l'agence réelle
    real = {p["id"] for p in client.get("/api/projects", headers=agency["admin"]).json()}
    assert not real & {p["id"] for p in client.get("/api/projects", headers=h).json()}


# ------------------------------------------------------------------ commentaires et notifications
def test_comments_mentions_notifications(client, agency, project):
    a = agency["admin"]
    client.put(f"/api/projects/{project['id']}", json={"team": [{"user_id": agency["member_id"]}, {"user_id": agency["manager_id"]}],
                                                       "version": project["version"]}, headers=a)
    notes = client.get("/api/notifications", headers=agency["member"]).json()
    assert any(n["kind"] == "attribution" for n in notes["items"])
    r = client.post("/api/comments", json={"entity": "projects", "entity_id": project["id"], "body": "@Manager Test peux-tu valider le CCTP ?"},
                    headers=agency["member"])
    assert r.status_code == 201 and r.json()["mentions"] == [agency["manager_id"]]
    mg = client.get("/api/notifications?unread=true", headers=agency["manager"]).json()
    assert any(n["kind"] == "mention" for n in mg["items"]) and mg["unread"] >= 1
    assert not any(n["kind"] in ("mention", "commentaire") for n in client.get("/api/notifications", headers=agency["member"]).json()["items"])
    # seul l'auteur modifie ; l'administrateur peut supprimer
    cid = r.json()["id"]
    assert client.put(f"/api/comments/{cid}", json={"body": "x"}, headers=agency["manager"]).status_code == 403
    assert client.put(f"/api/comments/{cid}", json={"body": "@Manager Test peux-tu valider le CCTP v2 ?"}, headers=agency["member"]).json()["edited"]
    assert client.post("/api/comments", json={"entity": "projects", "entity_id": project["id"], "body": "x"}, headers=agency["viewer"]).status_code == 403
    client.post("/api/notifications/read", json={}, headers=agency["manager"])
    assert client.get("/api/notifications?unread=true", headers=agency["manager"]).json()["unread"] == 0
    assert client.delete(f"/api/comments/{cid}", headers=a).status_code == 200
    # tâche attribuée puis terminée
    t = client.post("/api/tasks", json={"project_id": project["id"], "name": "Visa plans", "start_date": "2027-01-04",
                                        "duration_days": 3, "responsible_id": agency["member_id"]}, headers=a).json()
    assert any(n["kind"] == "attribution" and "Visa plans" in n["title"] for n in client.get("/api/notifications", headers=agency["member"]).json()["items"])
    client.put(f"/api/tasks/{t['id']}", json={"progress": 100, "version": t["version"]}, headers=agency["member"])
    assert any(n["kind"] == "tache_terminee" for n in client.get("/api/notifications", headers=agency["manager"]).json()["items"])
    # équipe
    team = client.get("/api/team", headers=agency["viewer"]).json()
    mem = next(u for u in team if u["id"] == agency["member_id"])
    assert mem["projects"][0]["id"] == project["id"]
    assert client.get(f"/api/team/{agency['member_id']}", headers=agency["viewer"]).json()["tasks"][0]["name"] == "Visa plans"
    assert len(client.get("/api/team/activity/recent", headers=agency["viewer"]).json()) > 0


def test_notifications_respect_confidentiality(client, agency):
    a = agency["admin"]
    p = client.post("/api/projects", json={"code": "C-01", "name": "Confidentiel", "confidential": True,
                                           "team": [{"user_id": agency["manager_id"]}]}, headers=a).json()
    client.post("/api/comments", json={"entity": "projects", "entity_id": p["id"], "body": "@Member Test regarde ça"}, headers=a)
    assert not any(n["project_id"] == p["id"] for n in client.get("/api/notifications", headers=agency["member"]).json()["items"])


# ------------------------------------------------------------------ journal chaîné
def test_audit_chain_detects_tampering(client, agency, project):
    from app.db import SessionLocal
    from app.models import AuditLog
    from app.services.journal import verify_chain

    db = SessionLocal()
    assert verify_chain(db, agency["agency_id"])["intact"]
    e = db.query(AuditLog).filter(AuditLog.agency_id == agency["agency_id"], AuditLog.hash.isnot(None)).first()
    e.summary = "falsifié"
    db.commit()
    res = verify_chain(db, agency["agency_id"])
    db.close()
    assert not res["intact"] and res["anomalies"][0]["probleme"] == "contenu modifié après enregistrement"
