"""Poste de bureau en mémoire (mode desktop, SQLite) + serveur central réel dans un processus séparé."""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "web" / "backend")]
os.environ["ARCHIPEL_DATA_DIR"] = tempfile.mkdtemp(prefix="a41desk_")
os.environ["ARCHIPEL_MODE"] = "desktop"
os.environ.pop("ARCHIPEL_DATABASE_URL", None)
PASSWORD = "Test#Archipel41"
SERVER_DB = os.environ.get("ARCHIPEL_TEST_DATABASE_URL", "")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Server:
    def __init__(self):
        self.port = free_port()
        self.data = tempfile.mkdtemp(prefix="a41srv_")
        self.proc = None

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def start(self):
        env = {**os.environ, "ARCHIPEL_MODE": "server", "ARCHIPEL_DATA_DIR": self.data, "ARCHIPEL_PORT": str(self.port),
               "ARCHIPEL_DATABASE_URL": SERVER_DB}
        if not SERVER_DB:
            env.pop("ARCHIPEL_DATABASE_URL")
        self.proc = subprocess.Popen([sys.executable, "-m", "app"], cwd=ROOT / "web" / "backend", env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                if httpx.get(self.url + "/api/health", timeout=1).status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(0.2)
        raise RuntimeError("serveur non démarré")

    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait(10)


@pytest.fixture(scope="module")
def server():
    if SERVER_DB.startswith("postgresql"):
        from sqlalchemy import create_engine, text

        eng = create_engine(SERVER_DB)
        with eng.begin() as c:
            for (t,) in c.execute(text("select tablename from pg_tables where schemaname='public' and tablename <> 'spatial_ref_sys'")):
                c.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        eng.dispose()
    s = Server()
    s.start()
    yield s
    s.stop()


@pytest.fixture(scope="module")
def desktop():
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
