"""Fixtures communes.

Base de test : SQLite temporaire par défaut ; PostgreSQL (PostGIS + pgvector) si
ARCHIPEL_TEST_DATABASE_URL est défini, ex. postgresql+psycopg://archipel:…@localhost/archipel41_test
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "web" / "backend")]
DEMO = ROOT / "database" / "seeds" / "demo_files"

_tmp = tempfile.mkdtemp(prefix="a41test_")
os.environ["ARCHIPEL_DATA_DIR"] = _tmp
os.environ["ARCHIPEL_MODE"] = "server"
os.environ["ARCHIPEL_ENV"] = "test"
os.environ.pop("ARCHIPEL_DATABASE_URL", None)
if os.environ.get("ARCHIPEL_TEST_DATABASE_URL"):
    os.environ["ARCHIPEL_DATABASE_URL"] = os.environ["ARCHIPEL_TEST_DATABASE_URL"]

PASSWORD = "Test#Archipel41"


def _reset_postgres(url: str) -> None:
    from sqlalchemy import create_engine, text

    eng = create_engine(url)
    with eng.begin() as c:
        tables = [r[0] for r in c.execute(text(
            "select tablename from pg_tables where schemaname='public' and tablename <> 'spatial_ref_sys'"))]
        for t in tables:
            c.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    eng.dispose()


@pytest.fixture(scope="session")
def app():
    url = os.environ.get("ARCHIPEL_DATABASE_URL")
    if url and url.startswith("postgresql"):
        _reset_postgres(url)
    if not (DEMO / "Devis_BatiOuest_Lot02_GrosOeuvre.pdf").exists():
        import subprocess

        subprocess.run([sys.executable, str(ROOT / "database/seeds/generate_demo_files.py"), str(DEMO)], check=True)
    from app.main import create_app

    return create_app()


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


def new_agency(role_users=("admin",), name=None):
    """Crée une agence isolée et ses comptes ; retourne {role: headers}."""
    from app.db import SessionLocal
    from app.models import Agency, User
    from app.security import create_access_token, hash_password

    db = SessionLocal()
    a = Agency(name=name or f"Agence {uuid.uuid4().hex[:6]}")
    db.add(a)
    db.flush()
    out = {"agency_id": a.id}
    pw = hash_password(PASSWORD)
    for role in role_users:
        u = User(agency_id=a.id, email=f"{role}.{uuid.uuid4().hex[:8]}@test.fr", full_name=f"{role.title()} Test", role=role,
                 password_hash=pw)
        db.add(u)
        db.flush()
        out[role] = {"Authorization": f"Bearer {create_access_token(u)}"}
        out[role + "_id"] = u.id
        out[role + "_email"] = u.email
    db.commit()
    db.close()
    return out


@pytest.fixture
def agency():
    return new_agency(("admin", "manager", "member", "viewer"))


@pytest.fixture
def project(client, agency):
    r = client.post("/api/projects", json={"code": "T-01", "name": "Projet de test", "budget_initial": 100000,
                                            "address": "1 rue Test", "city": "Testville"}, headers=agency["admin"])
    assert r.status_code == 201, r.text
    return r.json()


def upload(client, headers, path, url, **form):
    with open(path, "rb") as f:
        return client.post(url, files={"files" if "upload" in url or "quotes/import" in url else "file": (Path(path).name, f.read())},
                           data={k: v for k, v in form.items() if v is not None}, headers=headers)
