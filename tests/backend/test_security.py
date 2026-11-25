"""Tests de sécurité."""
import re
import time
from pathlib import Path

import jwt
import pytest

from conftest import DEMO, PASSWORD, ROOT, new_agency


def test_auth_required_everywhere(client):
    for path in ("/api/projects", "/api/quotes", "/api/documents", "/api/events", "/api/settings/ai", "/api/backups", "/api/audit",
                 "/api/dashboard", "/api/sync/pull", "/api/users"):
        assert client.get(path).status_code == 401, path


def test_forged_and_expired_tokens(client, agency):
    from app.config import get_settings

    payload = {"sub": agency["admin_id"], "agency": agency["agency_id"], "role": "admin", "exp": int(time.time()) + 600}
    forged = jwt.encode(payload, "mauvaise-cle", algorithm="HS256")
    assert client.get("/api/projects", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    expired = jwt.encode({**payload, "exp": int(time.time()) - 10}, get_settings().secret_key, algorithm="HS256")
    r = client.get("/api/projects", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and "expirée" in r.json()["detail"]
    none_alg = jwt.encode(payload, None, algorithm="none") if hasattr(jwt, "encode") else ""
    assert client.get("/api/projects", headers={"Authorization": f"Bearer {none_alg}"}).status_code == 401
    other = new_agency()
    cross = jwt.encode({**payload, "agency": other["agency_id"]}, get_settings().secret_key, algorithm="HS256")
    assert client.get("/api/projects", headers={"Authorization": f"Bearer {cross}"}).status_code == 401


def test_deactivated_user_rejected(client, agency):
    r = client.put(f"/api/users/{agency['member_id']}", json={"active": False}, headers=agency["admin"])
    assert r.status_code == 200
    assert client.get("/api/projects", headers=agency["member"]).status_code == 401


def test_sql_injection_attempts_are_inert(client, agency, project):
    h = agency["admin"]
    for q in ("' OR 1=1 --", "%' UNION SELECT password_hash FROM users --", "\"; DROP TABLE projects; --"):
        r = client.get("/api/projects", params={"q": q}, headers=h)
        assert r.status_code == 200 and r.json() == []
        assert client.get("/api/search", params={"q": q}, headers=h).status_code == 200
    assert client.get(f"/api/projects/{project['id']}", headers=h).status_code == 200  # la table existe toujours


def test_login_throttling(client):
    ag = new_agency(("admin",))
    email = ag["admin_email"]
    codes = [client.post("/api/auth/login", json={"email": email, "password": "mauvais"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429
    assert client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).status_code == 429  # verrou temporaire


def test_upload_restrictions(client, agency, project):
    h = agency["admin"]
    r = client.post("/api/documents/upload", files={"files": ("outil.exe", b"MZ\x90\x00" * 10)}, headers=h)
    assert r.status_code == 415
    r = client.post("/api/documents/upload", files={"files": ("faux.pdf", b"MZ\x90\x00 pas un pdf")}, headers=h)
    assert r.status_code == 422
    r = client.post("/api/documents/upload", files={"files": ("script.js", b"alert(1)")}, headers=h)
    assert r.status_code == 415
    r = client.post("/api/documents/upload", files={"files": ("../../../etc/passwd.txt", b"root:x:0:0")}, headers=h)
    assert r.status_code == 201
    d = r.json()["documents"][0]
    assert d["name"] == "passwd.txt"  # chemin neutralisé


def test_storage_path_traversal_blocked():
    from app.services import storage

    with pytest.raises(ValueError):
        storage.path_for("../../../../etc/passwd")
    assert storage.safe_filename("..\\..\\boot.ini") == "boot.ini"


def test_backup_download_traversal(client, agency):
    r = client.get("/api/backups/..%2F..%2F.secret_key", headers=agency["admin"])
    assert r.status_code == 404


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert r.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_document_download_is_sandboxed(client, agency):
    h = agency["admin"]
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(document.cookie)</script></svg>'
    d = client.post("/api/documents/upload", files={"files": ("plan.svg", svg)}, headers=h).json()["documents"][0]
    r = client.get(f"/api/documents/{d['id']}/download?inline=true", headers=h)
    assert "sandbox" in r.headers["content-security-policy"]


def test_passwords_hashed_and_policy(client, agency):
    from app.db import SessionLocal
    from app.models import User
    from app.security import hash_password, verify_password

    db = SessionLocal()
    u = db.get(User, agency["admin_id"])
    db.close()
    assert u.password_hash.startswith("pbkdf2_sha256$") and PASSWORD not in u.password_hash
    assert verify_password(PASSWORD, u.password_hash) and not verify_password("x", u.password_hash)
    assert hash_password("a") != hash_password("a")  # sel aléatoire
    for weak in ("court1A!", "toutenminuscules", "ToutEnLettres"):
        r = client.post("/api/users", json={"email": f"w{len(weak)}@t.fr", "full_name": "W", "password": weak}, headers=agency["admin"])
        assert r.status_code == 422


def test_viewer_cannot_mutate_anything(client, agency, project):
    h = agency["viewer"]
    calls = [("post", "/api/clients", {"name": "x"}), ("post", "/api/tasks", {"project_id": project["id"], "name": "x", "start_date": "2026-01-01"}),
             ("put", f"/api/projects/{project['id']}", {"name": "x"}), ("post", "/api/events", {"title": "x", "start": "2026-01-01T10:00:00Z", "end": "2026-01-01T11:00:00Z"}),
             ("post", "/api/reports", {"kind": "synthese", "project_id": project["id"]}), ("post", "/api/sync/push", {"changes": [{"entity": "clients", "id": "x", "data": {}}]})]
    for m, url, body in calls:
        r = getattr(client, m)(url, json=body, headers=h)
        assert r.status_code == 403 or (url == "/api/sync/push" and r.json()["results"][0]["status"] == "rejected"), (url, r.status_code)


def test_no_secrets_in_source_tree():
    patterns = [re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), re.compile(r"sk-[A-Za-z0-9]{32,}"), re.compile(r"AKIA[0-9A-Z]{16}"),
                re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----")]
    offenders = []
    for base in ("web/backend/app", "web/frontend/src", "ai", "desktop/electron", "database", "scripts"):
        for p in (ROOT / base).rglob("*"):
            if p.is_file() and p.suffix in {".py", ".ts", ".tsx", ".js", ".cjs", ".json", ".sh", ".yml", ".yaml", ".env", ".ini", ".md"} and "node_modules" not in p.parts:
                txt = p.read_text(errors="ignore")
                offenders += [f"{p}" for rx in patterns if rx.search(txt)]
    env = (ROOT / ".env.example").read_text() if (ROOT / ".env.example").exists() else ""
    assert not offenders, offenders
    assert "ANTHROPIC_API_KEY=" not in env or re.search(r"ANTHROPIC_API_KEY=\s*$", env, re.M)


def test_audit_log_records_sensitive_actions(client, agency, project):
    client.delete(f"/api/projects/{project['id']}", headers=agency["admin"])
    log = client.get("/api/audit", headers=agency["admin"]).json()
    assert any(e["action"] == "delete" and e["entity"] == "projects" for e in log)
    assert client.get("/api/audit", headers=agency["manager"]).status_code == 403
