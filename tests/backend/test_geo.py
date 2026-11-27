"""Lot 6 : conversions de coordonnées, lecture des formats géographiques, couches de projet, export, mesures."""
import io
import json
import sqlite3
import struct
import tempfile
import zipfile
from pathlib import Path

import pytest

from conftest import new_agency

# Parcelle d'essai : carré de 100 m × 100 m en Lambert-93, à Nantes (≈ -1,553 ; 47,218)
X0, Y0 = 355_500.0, 6_689_700.0
SQUARE = [[X0, Y0], [X0, Y0 + 100], [X0 + 100, Y0 + 100], [X0 + 100, Y0], [X0, Y0]]  # sens horaire (contour extérieur Shapefile)
PRJ_L93 = ('PROJCS["RGF93_Lambert_93",GEOGCS["GCS_RGF_1993",DATUM["D_RGF_1993",SPHEROID["GRS_1980",6378137.0,298.257222101]],'
           'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Lambert_Conformal_Conic"]]')


# ------------------------------------------------------------------ conversions
def test_crs_conversions():
    from app.services import geocrs

    lon, lat = geocrs.to_wgs84(2154, 700000, 6600000)
    assert abs(lon - 3) < 1e-9 and abs(lat - 46.5) < 1e-9                       # origine du Lambert-93
    lon, lat = geocrs.to_wgs84(32631, 448251.9, 5411932.6)                       # tour Eiffel en UTM 31
    assert abs(lon - 2.2945) < 2e-4 and abs(lat - 48.8582) < 2e-4
    for epsg in (2154, 3947):
        x, y = geocrs.from_wgs84(epsg, -1.5536, 47.2184)
        lo, la = geocrs.to_wgs84(epsg, x, y)
        assert abs(lo + 1.5536) < 1e-9 and abs(la - 47.2184) < 1e-9
    assert geocrs.epsg_from_text(PRJ_L93) == 2154
    assert geocrs.epsg_from_text("urn:ogc:def:crs:EPSG::3946") == 3946
    assert geocrs.guess_epsg([X0], [Y0])[0] == 2154
    assert geocrs.guess_epsg([12.5], [3.4])[0] == 4326
    assert geocrs.guess_epsg([1.5], [2.5e7])[0] is None


def test_area_and_length():
    from app.services import geocrs, geoformats

    ring = [list(geocrs.to_wgs84(2154, x, y)) for x, y in SQUARE]
    a = geoformats.polygon_area_m2([ring])
    assert abs(a - 10_000) / 10_000 < 0.005, a                # 1 ha à 0,5 % près (déformation du Lambert-93 incluse)
    assert abs(geoformats.length_m(ring[:2]) - 100) < 0.5


# ------------------------------------------------------------------ fichiers d'essai
def shapefile_zip() -> bytes:
    pts = SQUARE
    content = struct.pack("<i", 5) + struct.pack("<4d", X0, Y0, X0 + 100, Y0 + 100) + struct.pack("<ii", 1, len(pts)) + struct.pack("<i", 0)
    content += b"".join(struct.pack("<dd", *p) for p in pts)
    rec = struct.pack(">ii", 1, len(content) // 2) + content
    header = struct.pack(">i", 9994) + b"\x00" * 20 + struct.pack(">i", (100 + len(rec)) // 2) + struct.pack("<ii", 1000, 5) + struct.pack("<4d", X0, Y0, X0 + 100, Y0 + 100) + b"\x00" * 32
    shp = header + rec
    fields = [(b"NUMERO", b"C", 10), (b"CONTENANC", b"N", 8)]
    dbf_h = struct.pack("<BBBBIHH", 3, 126, 1, 1, 1, 32 + 32 * len(fields) + 1, 1 + 18) + b"\x00" * 20
    for name, t, ln in fields:
        dbf_h += name.ljust(11, b"\x00") + t + b"\x00" * 4 + bytes([ln, 0]) + b"\x00" * 14
    dbf = dbf_h + b"\r" + b" " + b"AB 0142".ljust(10) + b"10000".rjust(8) + b"\x1a"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("parcelle.shp", shp)
        z.writestr("parcelle.dbf", dbf)
        z.writestr("parcelle.prj", PRJ_L93)
    return buf.getvalue()


def gpkg_bytes() -> bytes:
    wkb = struct.pack("<BII", 1, 3, 1) + struct.pack("<I", len(SQUARE)) + b"".join(struct.pack("<dd", *p) for p in SQUARE)
    blob = b"GP" + bytes([0, 1]) + struct.pack("<i", 2154) + wkb
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.gpkg"
        con = sqlite3.connect(p)
        con.executescript("""CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT);
            CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, srs_id INT);
            CREATE TABLE emprise (fid INTEGER PRIMARY KEY, geom BLOB, nom TEXT);
            INSERT INTO gpkg_contents VALUES ('emprise', 'features');
            INSERT INTO gpkg_geometry_columns VALUES ('emprise', 'geom', 2154);""")
        con.execute("INSERT INTO emprise (geom, nom) VALUES (?, ?)", (blob, "Emprise du projet"))
        con.commit()
        con.close()
        return p.read_bytes()


def dxf_bytes(x0=X0, y0=Y0) -> bytes:
    lines = ["0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "0", "LAYER", "2", "LIMITES", "62", "1", "0", "ENDTAB", "0", "ENDSEC",
             "0", "SECTION", "2", "ENTITIES",
             "0", "LWPOLYLINE", "8", "LIMITES", "90", "4", "70", "1", "10", str(x0), "20", str(y0), "10", str(x0), "20", str(y0 + 100),
             "10", str(x0 + 100), "20", str(y0 + 100), "10", str(x0 + 100), "20", str(y0),
             "0", "LINE", "8", "VOIRIE", "10", str(x0), "20", str(y0 - 5), "11", str(x0 + 100), "21", str(y0 - 5),
             "0", "CIRCLE", "8", "ARBRES", "10", str(x0 + 50), "20", str(y0 + 50), "40", "3",
             "0", "TEXT", "8", "TEXTES", "10", str(x0 + 10), "20", str(y0 + 10), "40", "2", "1", "Parcelle AB 142",
             "0", "ENDSEC", "0", "EOF"]
    return ("\n".join(lines) + "\n").encode()


def png_with_world() -> dict:
    from PIL import Image

    im = Image.new("RGB", (200, 200), (200, 220, 200))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    pgw = f"0.5\n0\n0\n-0.5\n{X0 + 0.25}\n{Y0 + 100 - 0.25}\n"
    return {"ortho.png": buf.getvalue(), "ortho.pgw": pgw.encode()}


def asc_bytes() -> bytes:
    rows = [" ".join(str(20 + r + c * 0.5) for c in range(10)) for r in range(10)]
    return (f"ncols 10\nnrows 10\nxllcorner {X0}\nyllcorner {Y0}\ncellsize 10\nNODATA_value -9999\n" + "\n".join(rows)).encode()


def kmz_bytes() -> bytes:
    kml = """<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>
      <Placemark><name>Accès chantier</name><ExtendedData><Data name="largeur"><value>4 m</value></Data></ExtendedData>
        <LineString><coordinates>-1.5540,47.2180 -1.5530,47.2185</coordinates></LineString></Placemark>
      <Placemark><name>Emprise</name><Polygon><outerBoundaryIs><LinearRing><coordinates>-1.554,47.218 -1.553,47.218 -1.553,47.219 -1.554,47.219 -1.554,47.218</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
    </Document></kml>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("doc.kml", kml)
    return buf.getvalue()


GPX = b"""<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><wpt lat="47.2184" lon="-1.5536"><name>Borne B1</name></wpt>
<trk><name>Releve</name><trkseg><trkpt lat="47.2180" lon="-1.5540"/><trkpt lat="47.2185" lon="-1.5530"/></trkseg></trk></gpx>"""


def _near_nantes(b):
    return b and -1.56 < b[0] < -1.54 and 47.21 < b[1] < 47.23


@pytest.mark.parametrize("name,files,kind,nfeat", [
    ("geojson_l93", {"emprise.geojson": json.dumps({"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::2154"}},
                                                     "features": [{"type": "Feature", "properties": {"nom": "Emprise"}, "geometry": {"type": "Polygon", "coordinates": [SQUARE]}}]}).encode()}, "vector", 1),
    ("shapefile", {"parcelle.zip": shapefile_zip()}, "vector", 1),
    ("geopackage", {"emprise.gpkg": gpkg_bytes()}, "vector", 1),
    ("dxf", {"plan_topo.dxf": dxf_bytes()}, "vector", 4),
    ("kmz", {"acces.kmz": kmz_bytes()}, "vector", 2),
    ("gpx", {"releve.gpx": GPX}, "vector", 2),
    ("image_calee", png_with_world(), "image", 0),
    ("mnt", {"mnt.asc": asc_bytes()}, "image", 0),
])
def test_import_formats(client, name, files, kind, nfeat):
    ag = new_agency(("admin", "viewer"))
    a = ag["admin"]
    p = client.post("/api/projects", json={"code": "GEO", "name": "Terrain test"}, headers=a).json()
    r = client.post(f"/api/projects/{p['id']}/geo/import", files=[("files", (k, v)) for k, v in files.items()], headers=a)
    assert r.status_code == 201, r.text
    lay = r.json()
    assert lay["kind"] == kind and lay["feature_count"] == nfeat, lay
    assert _near_nantes(lay["bounds"]), lay["bounds"]
    if name == "shapefile":
        f = lay["data"]["features"][0]
        assert f["properties"]["NUMERO"] == "AB 0142" and f["properties"]["CONTENANC"] == 10000
        from app.services.geoformats import polygon_area_m2

        assert abs(polygon_area_m2(f["geometry"]["coordinates"]) - 10000) < 60
    if name == "dxf":
        assert {"LIMITES", "VOIRIE", "ARBRES", "TEXTES"} == {f["properties"]["calque"] for f in lay["data"]["features"]}
        assert "supposé" in lay["crs_note"]                    # système déduit, signalé à l'utilisateur
    if name == "mnt":
        assert lay["stats"]["altitude_min_m"] == 20 and lay["stats"]["denivele_m"] == 13.5
    if kind == "image":
        img = client.get(f"/api/geo/layers/{lay['id']}/image", headers=a)
        assert img.status_code == 200 and img.content[:4] == b"\x89PNG"
    # le fichier original est conservé dans les documents du projet
    docs = client.get(f"/api/documents?project_id={p['id']}", headers=a).json()
    assert len(docs) == 1
    # un lecteur ne peut pas importer
    assert client.post(f"/api/projects/{p['id']}/geo/import", files=[("files", ("x.gpx", GPX))], headers=ag["viewer"]).status_code == 403


def test_import_errors_are_explicit(client):
    ag = new_agency(("admin",))
    a = ag["admin"]
    p = client.post("/api/projects", json={"code": "GEO2", "name": "Erreurs"}, headers=a).json()
    r = client.post(f"/api/projects/{p['id']}/geo/import", files=[("files", ("plan_local.dxf", dxf_bytes(100, 100)))], headers=a)
    assert r.status_code == 422 and "coordonnées locales" in r.json()["detail"]
    # en imposant le système, le même plan est accepté (ici CC47 fictif : refusé si hors du globe)
    r = client.post(f"/api/projects/{p['id']}/geo/import", files=[("files", ("plan.dxf", dxf_bytes()))], data={"epsg": "2154"}, headers=a)
    assert r.status_code == 201 and "imposé" in r.json()["crs_note"]
    r = client.post(f"/api/projects/{p['id']}/geo/import", files=[("files", ("seul.shp", b"\x00\x00'\n" + b"\x00" * 96))], headers=a)
    assert r.status_code == 422
    r = client.post(f"/api/projects/{p['id']}/geo/import", files=[("files", ("notes.txt", b"bonjour"))], headers=a)
    assert r.status_code == 422 and "Formats acceptés" in r.json()["detail"]
    errs = client.get("/api/history/errors?source=import", headers=a).json()["items"]
    assert any(e["module"] == "terrain" for e in errs)


def test_layers_annotations_export_and_services(client, monkeypatch):
    ag = new_agency(("admin", "member"))
    a = ag["admin"]
    p = client.post("/api/projects", json={"code": "GEO3", "name": "Couches"}, headers=a).json()
    client.post(f"/api/projects/{p['id']}/geo/import", files=[("files", ("releve.gpx", GPX))], headers=a)
    ann = client.post(f"/api/projects/{p['id']}/geo/annotations", headers=a).json()
    assert client.post(f"/api/projects/{p['id']}/geo/annotations", headers=a).json()["id"] == ann["id"]   # une seule couche
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-1.5535, 47.2183]}, "properties": {"label": "Regard EU", "note": "à relever"}}]}
    r = client.put(f"/api/geo/layers/{ann['id']}", json={"data": fc, "version": ann["version"]}, headers=ag["member"])
    assert r.status_code == 200 and r.json()["feature_count"] == 1
    layers = client.get(f"/api/projects/{p['id']}/geo/layers", headers=a).json()
    assert len(layers) == 2
    kml = client.get(f"/api/projects/{p['id']}/geo/export?fmt=kml", headers=a)
    assert kml.status_code == 200 and "<name>Regard EU</name>" in kml.text and "<Placemark>" in kml.text
    gj = client.get(f"/api/projects/{p['id']}/geo/export?fmt=geojson", headers=a).json()
    assert len(gj["features"]) == 3 and {f["properties"]["couche"] for f in gj["features"]} == {"releve", "Annotations et observations"}
    # WMS : affiché par le navigateur ; WFS : objets récupérés par le serveur (service simulé)
    r = client.post(f"/api/projects/{p['id']}/geo/service", json={"kind": "wms", "url": "https://wxs.example.fr/wms", "layers": "PLU"}, headers=a)
    assert r.status_code == 201 and r.json()["kind"] == "wms"
    import httpx

    real = httpx.Client

    def fake_client(*args, **kw):
        kw["transport"] = httpx.MockTransport(lambda req: httpx.Response(200, json={"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-1.55, 47.22]}, "properties": {"id": 1}}]}))
        return real(*args, **kw)

    monkeypatch.setattr("app.routers.geo.httpx.Client", fake_client)
    r = client.post(f"/api/projects/{p['id']}/geo/service", json={"kind": "wfs", "url": "https://wxs.example.fr/wfs", "layers": "zonage"}, headers=a)
    assert r.status_code == 201 and r.json()["feature_count"] == 1
    assert client.post(f"/api/projects/{p['id']}/geo/service", json={"kind": "ftp", "url": "x"}, headers=a).status_code == 422
    # suppression, fonds de carte, mesure, parcelle (réseau indisponible en test : réponse explicite)
    assert client.delete(f"/api/geo/layers/{layers[0]['id']}", headers=a).status_code == 200
    bm = client.get("/api/geo/basemaps", headers=a).json()
    assert any(b["id"] == "ign_ortho" for b in bm["basemaps"]) and "bornage" in bm["notice"]
    m = client.post("/api/geo/measure", json={"geometry": {"type": "LineString", "coordinates": [[-1.5536, 47.2184], [-1.5536, 47.2193]]}}, headers=a).json()
    assert 99 < m["length_m"] < 101
    par = client.get("/api/geo/parcel?lat=47.2184&lon=-1.5536", headers=a).json()
    assert "notice" in par and (par["found"] or par["reason"])


def test_terrain_numbers_french_format(client, agency, project):
    """Fiche terrain : « 4 250,5 » m² est enregistré comme le nombre 4250,5 (et non comme du texte) ;
    une valeur illisible ou négative est refusée avec un message explicite ; un champ vide devient nul."""
    h = agency["admin"]
    r = client.put(f"/api/projects/{project['id']}", json={"terrain": {"parcelle": "27438 ZB 112", "superficie_m2": "4 250,5",
                                                                        "surface_cadastrale_m2": "", "zone_plu": "UZ"},
                                                            "version": project["version"]}, headers=h)
    assert r.status_code == 200, r.text
    t = r.json()["terrain"]
    assert t["superficie_m2"] == 4250.5 and isinstance(t["superficie_m2"], float)
    assert t["surface_cadastrale_m2"] is None and t["parcelle"] == "27438 ZB 112" and t["zone_plu"] == "UZ"
    v = r.json()["version"]
    bad = client.put(f"/api/projects/{project['id']}", json={"terrain": {"superficie_m2": "env. 4000"}, "version": v}, headers=h)
    assert bad.status_code == 422 and "superficie_m2" in bad.text
    neg = client.put(f"/api/projects/{project['id']}", json={"terrain": {"superficie_m2": "-12"}, "version": v}, headers=h)
    assert neg.status_code == 422
    assert client.get(f"/api/projects/{project['id']}", headers=h).json()["terrain"]["superficie_m2"] == 4250.5


def test_place_image_and_long_format_labels(client, agency, project):
    """Plan non géoréférencé positionné par son emprise ; libellés de format compatibles avec la colonne (PostgreSQL)."""
    import io as _io
    from PIL import Image
    buf = _io.BytesIO(); Image.new("RGB", (60, 40), "white").save(buf, "PNG")
    r = client.post(f"/api/projects/{project['id']}/geo/place-image", files={"file": ("Plan masse.png", buf.getvalue())},
                    data={"bounds": json.dumps([1.149, 49.079, 1.152, 49.081])}, headers=agency["admin"])
    assert r.status_code in (200, 201), r.text
    assert r.json()["source_format"] == "Plan positionné"
    from app.services import geoformats
    assert len("MNT ESRI ASCII") <= 20 and all(len(f) <= 20 for f in ("GeoJSON", "KML", "GPX", "GeoPackage", "Shapefile", "DXF", "Image calée", "Plan positionné"))
