"""Lot 8 — guides embarqués servis à l'application (liste fermée, lecture seule)."""


def test_guides_list_and_download(client, agency):
    lst = client.get("/api/guides", headers=agency["viewer"])
    assert lst.status_code == 200
    ids = {g["id"]: g for g in lst.json()}
    assert set(ids) == {"guide-pratique", "utilisation", "installation", "technique"}
    assert ids["guide-pratique"]["available"] is True
    r = client.get("/api/guides/guide-pratique", headers=agency["member"])
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF"


def test_guides_closed_list(client, agency):
    assert client.get("/api/guides").status_code == 401
    assert client.get("/api/guides/inconnu", headers=agency["admin"]).status_code == 404
    assert client.get("/api/guides/..%2F..%2Fweb%2Fbackend%2Fapp%2Fconfig.py", headers=agency["admin"]).status_code == 404
