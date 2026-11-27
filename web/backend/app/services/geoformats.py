"""Lecture des fichiers géographiques → GeoJSON WGS84 (sans dépendance externe).

Formats : GeoJSON, KML, KMZ (y compris GroundOverlay), GPX, Shapefile (.shp + .shx/.dbf/.prj/.cpg, isolés ou
en archive ZIP), GeoPackage (.gpkg), DXF (ASCII), images géoréférencées (GeoTIFF, fichier de calage
.jgw/.pgw/.tfw/.wld), modèle numérique de terrain (grille ESRI ASCII .asc).

Chaque lecteur renvoie un `GeoResult` : FeatureCollection en WGS84, système source, avertissements, et pour
les rasters une image PNG prête à afficher avec son emprise. Les coordonnées sont converties par geocrs.
"""
from __future__ import annotations

import io
import json
import math
import re
import struct
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from . import geocrs

MAX_FEATURES = 25000


class GeoError(Exception):
    pass


@dataclass
class GeoResult:
    features: list = field(default_factory=list)
    epsg: int | None = None
    crs_note: str = ""
    warnings: list = field(default_factory=list)
    image_png: bytes | None = None
    image_bounds: list | None = None      # [minLon, minLat, maxLon, maxLat]
    stats: dict = field(default_factory=dict)
    format: str = ""

    def collection(self) -> dict:
        return {"type": "FeatureCollection", "features": self.features}


# ------------------------------------------------------------------ outils géométriques
def _walk(coords, fn):
    if isinstance(coords, (list, tuple)) and coords and isinstance(coords[0], (int, float)):
        return fn(coords)
    return [_walk(c, fn) for c in coords]


def _all_xy(geom) -> list:
    out = []
    if not geom:
        return out
    if geom["type"] == "GeometryCollection":
        for g in geom["geometries"]:
            out += _all_xy(g)
        return out
    _walk(geom["coordinates"], lambda c: out.append((c[0], c[1])))
    return out


def reproject_features(features: list, epsg: int) -> None:
    if epsg in (4326, 4171):
        return

    def conv(c):
        lon, lat = geocrs.to_wgs84(epsg, c[0], c[1])
        return [round(lon, 8), round(lat, 8)] + ([c[2]] if len(c) > 2 else [])

    for f in features:
        g = f.get("geometry")
        if not g:
            continue
        if g["type"] == "GeometryCollection":
            for gg in g["geometries"]:
                gg["coordinates"] = _walk(gg["coordinates"], conv)
        else:
            g["coordinates"] = _walk(g["coordinates"], conv)


def bounds(features: list) -> list | None:
    xs, ys = [], []
    for f in features:
        for x, y in _all_xy(f.get("geometry")):
            xs.append(x)
            ys.append(y)
    return [min(xs), min(ys), max(xs), max(ys)] if xs else None


def _finalize(res: GeoResult, epsg_hint: int | None, override: int | None) -> GeoResult:
    pts = [xy for f in res.features for xy in _all_xy(f.get("geometry"))]
    epsg = override or epsg_hint
    if override:
        res.crs_note = f"système imposé à l'import : {geocrs.NAMES.get(override, override)}"
    elif epsg_hint:
        res.crs_note = f"système lu dans le fichier : {geocrs.NAMES.get(epsg_hint, epsg_hint)}"
    else:
        epsg, note = geocrs.guess_epsg([p[0] for p in pts[:5000]], [p[1] for p in pts[:5000]])
        res.crs_note = note
        if epsg and epsg != 4326:
            res.warnings.append(f"Système de coordonnées non indiqué dans le fichier : {note}. Vérifiez la position sur la carte.")
    if epsg is None:
        raise GeoError("Les coordonnées ne correspondent à aucun système reconnu (plan en coordonnées locales ?). "
                       "Indiquez le système de coordonnées à l'import, ou consultez le fichier dans la visionneuse de plans.")
    if epsg == 27572:
        res.warnings.append("Lambert II étendu (NTF) : conversion à quelques mètres près — ne pas utiliser pour une implantation.")
    try:
        reproject_features(res.features, epsg)
    except ValueError as ex:
        raise GeoError(str(ex))
    res.epsg = epsg
    if len(res.features) > MAX_FEATURES:
        res.warnings.append(f"{len(res.features)} objets : seuls les {MAX_FEATURES} premiers sont conservés.")
        res.features = res.features[:MAX_FEATURES]
    b = bounds(res.features)
    if b and not (-180 <= b[0] <= 180 and -90 <= b[1] <= 90):
        raise GeoError("Les coordonnées converties sont hors du globe : le système de coordonnées est probablement erroné.")
    return res


def _feat(geom, props=None):
    return {"type": "Feature", "geometry": geom, "properties": props or {}}


# ------------------------------------------------------------------ GeoJSON
def read_geojson(data: bytes, override: int | None = None) -> GeoResult:
    try:
        obj = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as ex:
        raise GeoError(f"Fichier GeoJSON illisible : {ex}")
    hint = geocrs.epsg_from_text(((obj.get("crs") or {}).get("properties") or {}).get("name")) if isinstance(obj, dict) else None
    if obj.get("type") == "FeatureCollection":
        feats = obj.get("features") or []
    elif obj.get("type") == "Feature":
        feats = [obj]
    elif obj.get("type") in ("Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon", "GeometryCollection"):
        feats = [_feat(obj)]
    else:
        raise GeoError("Ce fichier JSON n'est pas du GeoJSON (type FeatureCollection, Feature ou géométrie attendu).")
    feats = [_feat(f.get("geometry"), f.get("properties") or {}) for f in feats if f.get("geometry")]
    return _finalize(GeoResult(features=feats, format="GeoJSON"), hint, override)


# ------------------------------------------------------------------ KML / KMZ / GPX
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kml_coords(text: str) -> list:
    out = []
    for tok in (text or "").split():
        parts = tok.split(",")
        if len(parts) >= 2:
            try:
                out.append([float(parts[0]), float(parts[1])])
            except ValueError:
                pass
    return out


def _kml_geom(el) -> dict | None:
    name = _local(el.tag)
    if name == "Point":
        c = _kml_coords(next((x.text for x in el.iter() if _local(x.tag) == "coordinates"), ""))
        return {"type": "Point", "coordinates": c[0]} if c else None
    if name == "LineString":
        c = _kml_coords(next((x.text for x in el.iter() if _local(x.tag) == "coordinates"), ""))
        return {"type": "LineString", "coordinates": c} if len(c) >= 2 else None
    if name == "Polygon":
        rings = []
        for b in el:
            if _local(b.tag) in ("outerBoundaryIs", "innerBoundaryIs"):
                c = _kml_coords(next((x.text for x in b.iter() if _local(x.tag) == "coordinates"), ""))
                if len(c) >= 4:
                    (rings.insert(0, c) if _local(b.tag) == "outerBoundaryIs" else rings.append(c))
        return {"type": "Polygon", "coordinates": rings} if rings else None
    if name == "MultiGeometry":
        geoms = [g for g in (_kml_geom(c) for c in el) if g]
        return {"type": "GeometryCollection", "geometries": geoms} if geoms else None
    return None


def read_kml(data: bytes, images: dict | None = None) -> GeoResult:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as ex:
        raise GeoError(f"Fichier KML illisible : {ex}")
    res = GeoResult(format="KML")
    for pm in root.iter():
        tag = _local(pm.tag)
        if tag == "Placemark":
            props = {}
            for ch in pm:
                t = _local(ch.tag)
                if t in ("name", "description") and ch.text:
                    props[t] = ch.text.strip()
                if t == "ExtendedData":
                    for d in ch.iter():
                        if _local(d.tag) in ("Data", "SimpleData"):
                            val = d.text if _local(d.tag) == "SimpleData" else next((v.text for v in d if _local(v.tag) == "value"), None)
                            if d.get("name") and val is not None:
                                props[d.get("name")] = val
            geom = next((g for g in (_kml_geom(c) for c in pm) if g), None)
            if geom:
                res.features.append(_feat(geom, props))
        elif tag == "GroundOverlay" and images is not None:
            href = next((x.text for x in pm.iter() if _local(x.tag) == "href"), None)
            box = {(_local(x.tag)): float(x.text) for x in pm.iter() if _local(x.tag) in ("north", "south", "east", "west") and x.text}
            if href and len(box) == 4 and href in images:
                res.image_png = _to_png(images[href])
                res.image_bounds = [box["west"], box["south"], box["east"], box["north"]]
    if not res.features and not res.image_png:
        raise GeoError("Aucun objet géographique trouvé dans le fichier KML.")
    return _finalize(res, 4326, None) if res.features else _raster_only(res, 4326)


def read_kmz(data: bytes) -> GeoResult:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise GeoError("Archive KMZ illisible.")
    kml = next((n for n in z.namelist() if n.lower().endswith(".kml")), None)
    if not kml:
        raise GeoError("Aucun fichier KML dans l'archive KMZ.")
    images = {n: z.read(n) for n in z.namelist() if n.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))}
    res = read_kml(z.read(kml), images)
    res.format = "KMZ"
    return res


def read_gpx(data: bytes) -> GeoResult:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as ex:
        raise GeoError(f"Fichier GPX illisible : {ex}")
    res = GeoResult(format="GPX")

    def pt(e):
        return [float(e.get("lon")), float(e.get("lat"))]

    for e in root.iter():
        t = _local(e.tag)
        name = next((c.text for c in e if _local(c.tag) == "name"), None)
        if t == "wpt":
            res.features.append(_feat({"type": "Point", "coordinates": pt(e)}, {"name": name} if name else {}))
        elif t in ("trkseg", "rte"):
            pts = [pt(p) for p in e if _local(p.tag) in ("trkpt", "rtept")]
            if len(pts) >= 2:
                res.features.append(_feat({"type": "LineString", "coordinates": pts}, {"name": name} if name else {}))
    if not res.features:
        raise GeoError("Aucun point ni trace dans le fichier GPX.")
    return _finalize(res, 4326, None)


# ------------------------------------------------------------------ WKB (GeoPackage)
def parse_wkb(b: bytes, off: int = 0) -> tuple[dict, int]:
    bo = "<" if b[off] == 1 else ">"
    (gtype,) = struct.unpack_from(bo + "I", b, off + 1)
    off += 5
    has_z = bool(gtype & 0x80000000) or 1000 <= (gtype & 0xFFFF) < 2000 or 3000 <= (gtype & 0xFFFF) < 4000
    has_m = bool(gtype & 0x40000000) or 2000 <= (gtype & 0xFFFF) < 4000
    if gtype & 0x20000000:  # EWKB avec SRID
        off += 4
    base = (gtype & 0x0FFFFFFF) % 1000
    dim = 2 + has_z + has_m

    def coords(n, o):
        pts = []
        for _ in range(n):
            v = struct.unpack_from(bo + "d" * dim, b, o)
            pts.append([v[0], v[1]])
            o += 8 * dim
        return pts, o

    if base == 1:
        p, off = coords(1, off)
        return {"type": "Point", "coordinates": p[0]}, off
    if base == 2:
        (n,) = struct.unpack_from(bo + "I", b, off)
        p, off = coords(n, off + 4)
        return {"type": "LineString", "coordinates": p}, off
    if base == 3:
        (nr,) = struct.unpack_from(bo + "I", b, off)
        off += 4
        rings = []
        for _ in range(nr):
            (n,) = struct.unpack_from(bo + "I", b, off)
            p, off = coords(n, off + 4)
            rings.append(p)
        return {"type": "Polygon", "coordinates": rings}, off
    if base in (4, 5, 6, 7):
        (n,) = struct.unpack_from(bo + "I", b, off)
        off += 4
        parts = []
        for _ in range(n):
            g, off = parse_wkb(b, off)
            parts.append(g)
        if base == 7:
            return {"type": "GeometryCollection", "geometries": parts}, off
        kind = {4: "MultiPoint", 5: "MultiLineString", 6: "MultiPolygon"}[base]
        return {"type": kind, "coordinates": [g["coordinates"] for g in parts]}, off
    raise GeoError(f"Géométrie WKB de type {base} non prise en charge.")


def read_gpkg(data: bytes) -> GeoResult:
    import sqlite3
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "f.gpkg"
        p.write_bytes(data)
        try:
            con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            layers = con.execute("SELECT c.table_name, g.column_name, g.srs_id FROM gpkg_contents c JOIN gpkg_geometry_columns g "
                                 "ON g.table_name = c.table_name WHERE c.data_type = 'features'").fetchall()
        except sqlite3.DatabaseError:
            raise GeoError("Ce fichier n'est pas un GeoPackage valide.")
        if not layers:
            raise GeoError("Le GeoPackage ne contient aucune couche vectorielle.")
        res = GeoResult(format="GeoPackage")
        srs = {layers[0][2]}
        for table, gcol, srs_id in layers:
            srs.add(srs_id)
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
            for row in con.execute(f'SELECT * FROM "{table}" LIMIT {MAX_FEATURES}'):
                rec = dict(zip(cols, row))
                blob = rec.pop(gcol, None)
                if not blob or blob[:2] != b"GP":
                    continue
                flags = blob[3]
                env = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}.get((flags >> 1) & 0x07, 0)
                try:
                    geom, _ = parse_wkb(blob, 8 + env)
                except (struct.error, GeoError):
                    continue
                props = {k: v for k, v in rec.items() if isinstance(v, (str, int, float)) and k not in ("fid",)}
                props["couche"] = table
                res.features.append(_feat(geom, props))
        con.close()
        if len(srs) > 1:
            res.warnings.append("Couches dans plusieurs systèmes de coordonnées : le premier est appliqué à toutes.")
        hint = layers[0][2] if layers[0][2] in geocrs.NAMES else None
        return _finalize(res, hint, None)


# ------------------------------------------------------------------ Shapefile
def _signed_area(r):
    return sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1)) / 2


def read_dbf(data: bytes, encoding: str | None = None) -> list[dict]:
    if not data or len(data) < 32:
        return []
    n, hlen, rlen = struct.unpack_from("<IHH", data, 4)
    fields, off = [], 32
    while off < hlen - 1 and data[off] != 0x0D:
        name = data[off:off + 11].split(b"\x00")[0].decode("latin-1").strip()
        fields.append((name, chr(data[off + 11]), data[off + 16], data[off + 17]))
        off += 32
    enc = encoding or "utf-8"
    rows = []
    for i in range(min(n, MAX_FEATURES)):
        rec = data[hlen + i * rlen: hlen + (i + 1) * rlen]
        if not rec or rec[:1] == b"*":
            rows.append({})
            continue
        pos, row = 1, {}
        for name, typ, ln, dec in fields:
            raw = rec[pos:pos + ln]
            pos += ln
            try:
                txt = raw.decode(enc).strip()
            except UnicodeDecodeError:
                txt = raw.decode("cp1252", "replace").strip()
            if typ in "NF" and txt:
                try:
                    row[name] = float(txt) if (dec or "." in txt) else int(txt)
                except ValueError:
                    row[name] = txt
            elif typ == "L":
                row[name] = txt.upper() in ("T", "Y")
            else:
                row[name] = txt
        rows.append(row)
    return rows


def read_shapefile(files: dict[str, bytes], override: int | None = None) -> GeoResult:
    shp = next((v for k, v in files.items() if k.lower().endswith(".shp")), None)
    if not shp:
        raise GeoError("Fichier .shp manquant : importez l'ensemble .shp, .shx, .dbf et .prj (de préférence dans une archive ZIP).")
    prj = next((v for k, v in files.items() if k.lower().endswith(".prj")), None)
    cpg = next((v for k, v in files.items() if k.lower().endswith(".cpg")), None)
    dbf = next((v for k, v in files.items() if k.lower().endswith(".dbf")), None)
    res = GeoResult(format="Shapefile")
    if not prj:
        res.warnings.append("Fichier .prj absent : système de coordonnées déduit des valeurs.")
    if not dbf:
        res.warnings.append("Fichier .dbf absent : les attributs des objets ne sont pas disponibles.")
    attrs = read_dbf(dbf, (cpg.decode().strip() if cpg else None)) if dbf else []
    (code,) = struct.unpack_from(">I", shp, 0)
    if code != 9994:
        raise GeoError("Fichier .shp invalide.")
    off, idx = 100, 0
    while off + 8 <= len(shp) and idx < MAX_FEATURES:
        (_, clen) = struct.unpack_from(">II", shp, off)
        content = shp[off + 8: off + 8 + clen * 2]
        off += 8 + clen * 2
        props = attrs[idx] if idx < len(attrs) else {}
        idx += 1
        if len(content) < 4:
            continue
        (st,) = struct.unpack_from("<i", content, 0)
        base = st % 10
        geom = None
        if st == 0:
            continue
        if base == 1:  # point (1, 11, 21)
            x, y = struct.unpack_from("<dd", content, 4)
            geom = {"type": "Point", "coordinates": [x, y]}
        elif base in (3, 5):  # polyligne / polygone
            nparts, npts = struct.unpack_from("<ii", content, 36)
            parts = list(struct.unpack_from(f"<{nparts}i", content, 44))
            p0 = 44 + 4 * nparts
            pts = [list(struct.unpack_from("<dd", content, p0 + 16 * i)) for i in range(npts)]
            rings = [pts[s:(parts[j + 1] if j + 1 < nparts else npts)] for j, s in enumerate(parts)]
            if base == 3:
                geom = {"type": "LineString", "coordinates": rings[0]} if len(rings) == 1 else {"type": "MultiLineString", "coordinates": rings}
            else:
                polys = []
                for r in rings:
                    if _signed_area(r) <= 0 or not polys:  # anneau horaire = contour extérieur
                        polys.append([r])
                    else:
                        polys[-1].append(r)
                geom = {"type": "Polygon", "coordinates": polys[0]} if len(polys) == 1 else {"type": "MultiPolygon", "coordinates": polys}
        elif base == 8:  # multipoint
            (npts,) = struct.unpack_from("<i", content, 36)
            geom = {"type": "MultiPoint", "coordinates": [list(struct.unpack_from("<dd", content, 40 + 16 * i)) for i in range(npts)]}
        if geom:
            res.features.append(_feat(geom, props))
    hint = geocrs.epsg_from_text(prj.decode("latin-1")) if prj else None
    if prj and not hint and not override:
        res.warnings.append("Système de coordonnées du .prj non reconnu : déduit des valeurs.")
    return _finalize(res, hint, override)


# ------------------------------------------------------------------ DXF
ACI = {1: "#ff0000", 2: "#ffff00", 3: "#00ff00", 4: "#00ffff", 5: "#0000ff", 6: "#ff00ff", 7: "#000000", 8: "#808080", 9: "#c0c0c0"}


def parse_dxf(data: bytes) -> dict:
    """Lecture des entités 2D d'un DXF ASCII : {entities: [...], layers: {nom: couleur}, units, extents}."""
    if data[:22].startswith(b"AutoCAD Binary DXF"):
        raise GeoError("DXF binaire non pris en charge : enregistrez le plan au format DXF ASCII.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("cp1252", "replace")
    lines = text.splitlines()
    pairs = [(lines[i].strip(), lines[i + 1].rstrip("\r")) for i in range(0, len(lines) - 1, 2)]
    ents, layers, units = [], {}, None
    section, cur, i = None, None, 0
    n = len(pairs)

    def flush():
        if cur:
            ents.append(cur)

    while i < n:
        code, val = pairs[i]
        if code == "0" and val == "SECTION":
            section = pairs[i + 1][1] if i + 1 < n else None
            i += 2
            continue
        if code == "0" and val == "ENDSEC":
            flush()
            cur = None
            section = None
            i += 1
            continue
        if section == "HEADER" and code == "9" and val == "$INSUNITS" and i + 1 < n:
            units = int(pairs[i + 1][1] or 0)
        if section == "TABLES" and code == "0" and val == "LAYER":
            name, color = None, 7
            j = i + 1
            while j < n and pairs[j][0] != "0":
                if pairs[j][0] == "2":
                    name = pairs[j][1]
                if pairs[j][0] == "62":
                    color = abs(int(pairs[j][1] or 7))
                j += 1
            if name:
                layers[name] = ACI.get(color, "#333333")
            i = j
            continue
        if section in ("ENTITIES", "BLOCKS") and code == "0":
            flush()
            cur = {"type": val, "layer": "0", "pts": [], "section": section} if section == "ENTITIES" else None
            i += 1
            continue
        if cur is not None:
            c = int(code) if code.lstrip("-").isdigit() else -1
            try:
                if c == 8:
                    cur["layer"] = val
                elif c in (10, 20):
                    if c == 10:
                        cur["pts"].append([float(val), None])
                    elif cur["pts"]:
                        cur["pts"][-1][1] = float(val)
                elif c in (11, 21):
                    if c == 11:
                        cur["p2"] = [float(val), None]
                    elif "p2" in cur:
                        cur["p2"][1] = float(val)
                elif c == 40:
                    cur["r"] = float(val)
                elif c == 50:
                    cur["a0"] = float(val)
                elif c == 51:
                    cur["a1"] = float(val)
                elif c == 70:
                    cur["flags"] = int(val or 0)
                elif c == 1:
                    cur["text"] = (cur.get("text") or "") + val
                elif c == 62:
                    cur["color"] = abs(int(val or 0))
            except ValueError:
                pass
        i += 1
    flush()
    # POLYLINE + VERTEX : regroupement
    out, poly = [], None
    for e in ents:
        if e["type"] == "POLYLINE":
            poly = {"type": "LWPOLYLINE", "layer": e["layer"], "pts": [], "flags": e.get("flags", 0), "color": e.get("color")}
        elif e["type"] == "VERTEX" and poly is not None:
            if e["pts"] and e["pts"][0][1] is not None:
                poly["pts"].append(e["pts"][0])
        elif e["type"] == "SEQEND" and poly is not None:
            out.append(poly)
            poly = None
        else:
            out.append(e)
    ents = []
    unsupported: dict[str, int] = {}
    for e in out:
        t = e["type"]
        pts = [p for p in e.get("pts", []) if p[1] is not None]
        if t == "LINE" and pts and e.get("p2") and e["p2"][1] is not None:
            ents.append({"kind": "line", "layer": e["layer"], "coords": [pts[0], e["p2"]], "color": e.get("color")})
        elif t == "LWPOLYLINE" and len(pts) >= 2:
            closed = bool(e.get("flags", 0) & 1)
            ents.append({"kind": "polygon" if closed and len(pts) >= 3 else "line", "layer": e["layer"],
                         "coords": pts + ([pts[0]] if closed else []), "color": e.get("color")})
        elif t in ("CIRCLE", "ARC") and pts and e.get("r"):
            cx, cy, r = pts[0][0], pts[0][1], e["r"]
            a0, a1 = (0.0, 360.0) if t == "CIRCLE" else (e.get("a0", 0.0), e.get("a1", 360.0))
            if a1 <= a0:
                a1 += 360
            nseg = max(8, int((a1 - a0) / 7.5))
            arc = [[cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / nseg)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / nseg))] for k in range(nseg + 1)]
            ents.append({"kind": "polygon" if t == "CIRCLE" else "line", "layer": e["layer"], "coords": arc, "color": e.get("color")})
        elif t == "POINT" and pts:
            ents.append({"kind": "point", "layer": e["layer"], "coords": pts[0], "color": e.get("color")})
        elif t in ("TEXT", "MTEXT") and pts and e.get("text"):
            txt = re.sub(r"\\[A-Za-z][^;]*;|[{}]|\\P", " ", e["text"]).strip()
            ents.append({"kind": "text", "layer": e["layer"], "coords": pts[0], "text": txt, "height": e.get("r"), "color": e.get("color")})
        elif t not in ("VERTEX", "SEQEND", "ENDBLK", "BLOCK", "ATTDEF", "ATTRIB", "VIEWPORT"):
            unsupported[t] = unsupported.get(t, 0) + 1
        for ln in [e["layer"]]:
            layers.setdefault(ln, "#333333")
    xs = [c[0] for e in ents for c in (e["coords"] if e["kind"] in ("line", "polygon") else [e["coords"]])]
    ys = [c[1] for e in ents for c in (e["coords"] if e["kind"] in ("line", "polygon") else [e["coords"]])]
    return {"entities": ents, "layers": layers, "units": units, "unsupported": unsupported,
            "extents": [min(xs), min(ys), max(xs), max(ys)] if xs else None}


def read_dxf(data: bytes, override: int | None = None) -> GeoResult:
    d = parse_dxf(data)
    if not d["entities"]:
        raise GeoError("Aucune entité 2D lisible dans le DXF (lignes, polylignes, cercles, arcs, points, textes).")
    res = GeoResult(format="DXF")
    for e in d["entities"]:
        props = {"calque": e["layer"]}
        if e["kind"] == "line":
            g = {"type": "LineString", "coordinates": e["coords"]}
        elif e["kind"] == "polygon":
            g = {"type": "Polygon", "coordinates": [e["coords"]]}
        else:
            g = {"type": "Point", "coordinates": e["coords"]}
            if e["kind"] == "text":
                props["texte"] = e["text"]
        res.features.append(_feat(g, props))
    if d["unsupported"]:
        res.warnings.append("Entités non reprises : " + ", ".join(f"{k} ({v})" for k, v in d["unsupported"].items()) + ".")
    res.stats["calques"] = sorted(d["layers"])
    return _finalize(res, None, override)


# ------------------------------------------------------------------ rasters
def _to_png(data: bytes, max_side: int = 4096) -> bytes:
    from PIL import Image

    im = Image.open(io.BytesIO(data))
    im.load()
    if im.mode not in ("RGB", "RGBA", "L", "LA"):
        im = im.convert("RGBA")
    if max(im.size) > max_side:
        im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _raster_only(res: GeoResult, epsg: int | None) -> GeoResult:
    res.epsg = epsg
    return res


def _bbox_wgs84(epsg: int, minx, miny, maxx, maxy) -> list:
    corners = [geocrs.to_wgs84(epsg, x, y) for x, y in ((minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy))]
    return [min(c[0] for c in corners), min(c[1] for c in corners), max(c[0] for c in corners), max(c[1] for c in corners)]


def read_world_image(image: bytes, world: str, override: int | None = None, prj: str | None = None) -> GeoResult:
    """Image + fichier de calage (6 lignes : A, D, B, E, C, F)."""
    from PIL import Image

    try:
        a, d, b, e, c, f = [float(x) for x in world.split()[:6]]
    except ValueError:
        raise GeoError("Fichier de calage invalide (6 valeurs numériques attendues).")
    im = Image.open(io.BytesIO(image))
    w, h = im.size
    res = GeoResult(format="Image calée")
    if abs(d) > 1e-9 or abs(b) > 1e-9:
        res.warnings.append("Image avec rotation : affichée dans son emprise (rotation ignorée).")
    x0, y0 = c - a / 2, f - e / 2
    x1, y1 = x0 + a * w, y0 + e * h
    epsg = override or (geocrs.epsg_from_text(prj) if prj else None)
    if not epsg:
        epsg, note = geocrs.guess_epsg([x0, x1], [y0, y1])
        res.crs_note = note
        if not epsg:
            raise GeoError("Système de coordonnées de l'image non reconnu : indiquez-le à l'import.")
        res.warnings.append(f"Système de coordonnées non indiqué : {note}.")
    res.image_png = _to_png(image)
    res.image_bounds = _bbox_wgs84(epsg, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    res.stats = {"largeur_px": w, "hauteur_px": h, "resolution_m": round(abs(a), 3)}
    return _raster_only(res, epsg)


def read_geotiff(data: bytes, override: int | None = None) -> GeoResult:
    from PIL import Image

    im = Image.open(io.BytesIO(data))
    tags = getattr(im, "tag_v2", {})
    scale, tie, keys = tags.get(33550), tags.get(33922), tags.get(34735)
    if not scale or not tie:
        raise GeoError("TIFF sans géoréférencement (GeoTIFF attendu) : joignez un fichier de calage .tfw, ou placez l'image manuellement.")
    epsg = override
    if not epsg and keys:
        k = list(keys)
        for j in range(4, len(k), 4):
            if k[j] in (3072, 2048) and k[j + 1] == 0 and k[j + 3] in geocrs.NAMES:
                epsg = k[j + 3]
    w, h = im.size
    x0, y0 = tie[3] - tie[0] * scale[0], tie[4] + tie[1] * scale[1]
    world = f"{scale[0]}\n0\n0\n{-scale[1]}\n{x0 + scale[0] / 2}\n{y0 - scale[1] / 2}"
    res = read_world_image(data, world, epsg)
    res.format = "GeoTIFF"
    return res


def read_esri_ascii(data: bytes, override: int | None = None) -> GeoResult:
    """Modèle numérique de terrain (grille ESRI ASCII) → image ombrée + statistiques d'altitude."""
    from PIL import Image

    text = data.decode("latin-1")
    head, vals = {}, []
    lines = text.splitlines()
    i = 0
    while i < len(lines) and re.match(r"^\s*[A-Za-z_]+\s", lines[i]):
        k, v = lines[i].split()[:2]
        head[k.lower()] = float(v)
        i += 1
    try:
        nc, nr, cs = int(head["ncols"]), int(head["nrows"]), head["cellsize"]
    except KeyError:
        raise GeoError("Grille ESRI ASCII invalide (en-tête ncols, nrows, cellsize attendu).")
    nod = head.get("nodata_value", -9999)
    for ln in lines[i:]:
        vals += [float(x) for x in ln.split()]
    if len(vals) < nc * nr:
        raise GeoError("Grille incomplète.")
    grid = [vals[r * nc:(r + 1) * nc] for r in range(nr)]
    valid = [v for v in vals[:nc * nr] if v != nod]
    if not valid:
        raise GeoError("Grille sans valeur.")
    zmin, zmax = min(valid), max(valid)
    x0 = head.get("xllcorner", head.get("xllcenter", 0) - cs / 2)
    y0 = head.get("yllcorner", head.get("yllcenter", 0) - cs / 2)
    img = Image.new("RGBA", (nc, nr))
    px = img.load()
    for r in range(nr):
        for c in range(nc):
            z = grid[r][c]
            if z == nod:
                px[c, r] = (0, 0, 0, 0)
                continue
            dzdx = ((grid[r][min(c + 1, nc - 1)] - grid[r][max(c - 1, 0)]) / (2 * cs)) if nod not in (grid[r][min(c + 1, nc - 1)], grid[r][max(c - 1, 0)]) else 0
            dzdy = ((grid[max(r - 1, 0)][c] - grid[min(r + 1, nr - 1)][c]) / (2 * cs)) if nod not in (grid[max(r - 1, 0)][c], grid[min(r + 1, nr - 1)][c]) else 0
            slope = math.atan(math.hypot(dzdx, dzdy))
            aspect = math.atan2(dzdy, -dzdx)
            shade = max(0.0, math.cos(math.radians(45)) * math.cos(slope) + math.sin(math.radians(45)) * math.sin(slope) * math.cos(math.radians(315) - aspect))
            t = (z - zmin) / (zmax - zmin) if zmax > zmin else 0.5
            base = (int(70 + 150 * t), int(130 + 60 * (1 - abs(t - 0.5) * 2)), int(90 + 40 * (1 - t)))
            px[c, r] = tuple(int(v * (0.45 + 0.55 * shade)) for v in base) + (200,)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    epsg = override
    res = GeoResult(format="MNT (grille ESRI ASCII)")
    if not epsg:
        epsg, note = geocrs.guess_epsg([x0, x0 + nc * cs], [y0, y0 + nr * cs])
        if not epsg:
            raise GeoError("Système de coordonnées du MNT non reconnu : indiquez-le à l'import.")
        res.warnings.append(f"Système de coordonnées non indiqué : {note}.")
    res.image_png = buf.getvalue()
    res.image_bounds = _bbox_wgs84(epsg, x0, y0, x0 + nc * cs, y0 + nr * cs)
    res.stats = {"altitude_min_m": round(zmin, 2), "altitude_max_m": round(zmax, 2), "denivele_m": round(zmax - zmin, 2),
                 "altitude_moyenne_m": round(sum(valid) / len(valid), 2), "pas_m": cs, "colonnes": nc, "lignes": nr}
    return _raster_only(res, epsg)


# ------------------------------------------------------------------ aiguillage
VECTOR_EXT = {"geojson", "json", "kml", "kmz", "gpx", "shp", "zip", "gpkg", "dxf"}
RASTER_EXT = {"tif", "tiff", "jpg", "jpeg", "png", "asc"}


def read_any(files: dict[str, bytes], override: int | None = None) -> GeoResult:
    """files : {nom: contenu}. Un ZIP de Shapefile ou un ensemble .shp/.dbf/.prj est accepté."""
    names = {k.lower(): k for k in files}
    if len(files) == 1 and next(iter(names)).endswith(".zip"):
        z = zipfile.ZipFile(io.BytesIO(next(iter(files.values()))))
        inner = {n.rsplit("/", 1)[-1]: z.read(n) for n in z.namelist() if not n.endswith("/") and not n.startswith("__MACOSX")}
        if not inner:
            raise GeoError("Archive ZIP vide.")
        return read_any(inner, override)
    ext = {k.rsplit(".", 1)[-1] for k in names if "." in k}
    if "shp" in ext:
        return read_shapefile(files, override)
    for k, orig in names.items():
        e = k.rsplit(".", 1)[-1]
        d = files[orig]
        if e in ("geojson", "json"):
            return read_geojson(d, override)
        if e == "kml":
            return read_kml(d)
        if e == "kmz":
            return read_kmz(d)
        if e == "gpx":
            return read_gpx(d)
        if e == "gpkg":
            return read_gpkg(d)
        if e == "dxf":
            return read_dxf(d, override)
        if e == "asc":
            return read_esri_ascii(d, override)
        if e in ("tif", "tiff"):
            wf = next((files[o] for kk, o in names.items() if kk.endswith((".tfw", ".wld"))), None)
            prj = next((files[o].decode("latin-1") for kk, o in names.items() if kk.endswith(".prj")), None)
            return read_world_image(d, wf.decode("latin-1"), override, prj) if wf else read_geotiff(d, override)
        if e in ("jpg", "jpeg", "png"):
            wf = next((files[o] for kk, o in names.items() if kk.endswith((".jgw", ".pgw", ".wld", ".jpgw", ".pngw"))), None)
            prj = next((files[o].decode("latin-1") for kk, o in names.items() if kk.endswith(".prj")), None)
            if not wf:
                raise GeoError("Image sans fichier de calage (.jgw/.pgw) : importez-la comme plan à positionner manuellement.")
            return read_world_image(d, wf.decode("latin-1"), override, prj)
    raise GeoError("Format non reconnu. Formats acceptés : GeoJSON, KML/KMZ, GPX, Shapefile (ZIP), GeoPackage, DXF, "
                   "GeoTIFF, image + fichier de calage, MNT ESRI ASCII (.asc).")


# ------------------------------------------------------------------ mesures (WGS84)
R_EARTH = 6371008.8


def length_m(coords: list) -> float:
    tot = 0.0
    for (lo1, la1), (lo2, la2) in zip([c[:2] for c in coords], [c[:2] for c in coords[1:]]):
        p1, p2 = math.radians(la1), math.radians(la2)
        dp, dl = p2 - p1, math.radians(lo2 - lo1)
        h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        tot += 2 * R_EARTH * math.asin(math.sqrt(h))
    return tot


def ring_area_m2(ring: list) -> float:
    """Aire géodésique approchée (sphère) d'un anneau WGS84 — exacte à mieux que 0,5 % à l'échelle d'une parcelle."""
    if len(ring) < 3:
        return 0.0
    s = 0.0
    for i in range(len(ring) - 1 if ring[0] == ring[-1] else len(ring)):
        lo1, la1 = ring[i][:2]
        lo2, la2 = ring[(i + 1) % len(ring)][:2]
        s += math.radians(lo2 - lo1) * (2 + math.sin(math.radians(la1)) + math.sin(math.radians(la2)))
    return abs(s * R_EARTH ** 2 / 2)


def polygon_area_m2(coords: list) -> float:
    return max(0.0, ring_area_m2(coords[0]) - sum(ring_area_m2(h) for h in coords[1:]))
