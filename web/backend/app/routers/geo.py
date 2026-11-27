"""Terrain et cartographie : couches d'un projet, imports géographiques, services WMS/WMTS/WFS,
annotations, export, identification de parcelle, fonds de carte.

Important : les limites cadastrales sont INDICATIVES (plan cadastral à finalité fiscale) ; elles ne valent pas
bornage. Seul un géomètre-expert établit les limites de propriété (bornage contradictoire)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from xml.sax.saxutils import escape

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..crud import create_obj, delete_obj, get_owned, scoped_query, to_dict, update_obj
from ..db import get_db
from ..models import GeoLayer, Project, User
from ..security import check_project_access, require
from ..services import geocrs, geoformats, settings_store, storage
from ..services import documents as docsvc

router = APIRouter(prefix="/api", tags=["terrain"])

CADASTRE_NOTICE = ("Données cadastrales indicatives : le plan cadastral a une finalité fiscale et ne constitue pas une "
                   "preuve de propriété. Seul un bornage contradictoire réalisé par un géomètre-expert établit les limites.")

# Fonds de carte publics (sans clé). IGN Géoplateforme : Licence Ouverte Etalab 2.0 ; OpenStreetMap : ODbL.
BASEMAPS = [
    {"id": "osm", "label": "Plan OpenStreetMap", "type": "xyz", "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
     "attribution": "© les contributeurs d'OpenStreetMap (ODbL)", "max_zoom": 19},
    {"id": "ign_plan", "label": "Plan IGN", "type": "wmts", "max_zoom": 19, "attribution": "© IGN – Géoplateforme (Licence Ouverte Etalab 2.0)",
     "url": "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&FORMAT=image/png&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"},
    {"id": "ign_ortho", "label": "Photographies aériennes (IGN)", "type": "wmts", "max_zoom": 20, "attribution": "© IGN – Géoplateforme (Licence Ouverte Etalab 2.0)",
     "url": "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&FORMAT=image/jpeg&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"},
]
OVERLAYS = [
    {"id": "ign_cadastre", "label": "Parcelles cadastrales (IGN, indicatif)", "type": "wmts", "max_zoom": 20, "opacity": 0.85,
     "attribution": "© IGN / DGFiP – Parcellaire Express (Licence Ouverte Etalab 2.0)",
     "url": "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=CADASTRALPARCELS.PARCELLAIRE_EXPRESS&STYLE=PCI%20vecteur&FORMAT=image/png&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"},
]


@router.get("/geo/basemaps")
def basemaps(user: User = Depends(require("read"))):
    return {"basemaps": BASEMAPS, "overlays": OVERLAYS, "crs": [{"epsg": k, "label": v} for k, v in geocrs.NAMES.items()],
            "notice": CADASTRE_NOTICE}


def _project(db: Session, user: User, pid: str, write: bool = False) -> Project:
    p = db.get(Project, pid)
    if not p or p.agency_id != user.agency_id or p.deleted:
        raise HTTPException(404, "Projet introuvable.")
    check_project_access(db, user, pid, write=write)
    return p


def _layer_out(l: GeoLayer, light: bool = False) -> dict:
    d = to_dict(l)
    d["feature_count"] = len((l.data or {}).get("features", [])) if l.data else 0
    if light:
        d.pop("data", None)
    if l.image:
        d["image"] = {k: v for k, v in l.image.items() if k != "png_key"}
    return d


@router.get("/projects/{pid}/geo/layers")
def list_layers(pid: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    _project(db, user, pid)
    rows = scoped_query(db, GeoLayer, user).filter(GeoLayer.project_id == pid).order_by(GeoLayer.position, GeoLayer.created_at).all()
    return [_layer_out(l) for l in rows]


def _store_layer(db, user, request, pid, name, res: geoformats.GeoResult, document_id=None, source_format=None, crs_note="") -> GeoLayer:
    image = None
    if res.image_png:
        key, _ = storage.store_bytes(user.agency_id, res.image_png)
        image = {"png_key": key, "bounds": res.image_bounds, "document_id": document_id, "opacity": 0.75}
    kind = "image" if res.image_png and not res.features else "vector"
    n = scoped_query(db, GeoLayer, user).filter(GeoLayer.project_id == pid).count()
    layer = create_obj(db, GeoLayer, {
        "project_id": pid, "name": name[:200], "kind": kind, "source_format": source_format or res.format, "document_id": document_id,
        "data": res.collection() if res.features else None, "image": image, "visible": True, "position": n,
        "bounds": geoformats.bounds(res.features) if res.features else res.image_bounds, "crs_source": geocrs.NAMES.get(res.epsg, str(res.epsg)) if res.epsg else None,
        "notes": "\n".join([x for x in [crs_note or res.crs_note, *res.warnings] if x]) or None,
        "style": {"color": ["#253A33", "#B07A26", "#46678C", "#9C3B29", "#5E4B8B"][n % 5], "weight": 2, "fillOpacity": 0.15},
    }, user, request)
    return layer


@router.post("/projects/{pid}/geo/import", status_code=201)
async def import_layer(pid: str, request: Request, files: list[UploadFile] = File(...), name: str | None = Form(None),
                       epsg: int | None = Form(None), keep_document: bool = Form(True),
                       user: User = Depends(require("write")), db: Session = Depends(get_db)):
    _project(db, user, pid, write=True)
    if epsg and epsg not in geocrs.NAMES:
        raise HTTPException(422, "Système de coordonnées non pris en charge.")
    contents = {f.filename or "fichier": await f.read() for f in files}
    total = sum(len(v) for v in contents.values())
    if total > 200 * 1024 * 1024:
        raise HTTPException(413, "Fichiers trop volumineux (200 Mo au maximum).")
    try:
        res = geoformats.read_any(contents, epsg)
    except geoformats.GeoError as ex:
        from ..services.journal import log_error

        log_error(db, source="import", severity="avertissement", module="terrain", message=f"Import géographique refusé : {ex}",
                  context={"fichiers": list(contents)}, agency_id=user.agency_id, user_id=user.id)
        db.commit()
        raise HTTPException(422, str(ex))
    except Exception as ex:  # fichier corrompu
        raise HTTPException(422, f"Fichier illisible ({type(ex).__name__}). Vérifiez qu'il n'est pas endommagé.")
    doc_id = None
    if keep_document:
        main = max(contents, key=lambda k: len(contents[k]))
        if len(contents) > 1:  # ensemble Shapefile : archivé en ZIP pour conserver l'original complet
            import io
            import zipfile

            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for k, v in contents.items():
                    z.writestr(k, v)
            main, data = main.rsplit(".", 1)[0] + ".zip", buf.getvalue()
        else:
            data = contents[main]
        doc, _ = docsvc.add_document(db, user, main, data, project_id=pid, category="urbanisme" if res.format != "DXF" else "plan",
                                     tags=["cartographie"])
        doc_id = doc.id
    layer_name = name or next(iter(contents)).rsplit(".", 1)[0]
    layer = _store_layer(db, user, request, pid, layer_name, res, doc_id)
    db.commit()
    out = _layer_out(layer)
    out.update({"warnings": res.warnings, "crs_note": res.crs_note, "stats": res.stats, "format": res.format})
    return out


@router.post("/projects/{pid}/geo/place-image", status_code=201)
async def place_image(pid: str, request: Request, file: UploadFile = File(...), bounds: str = Form(...), name: str | None = Form(None),
                      user: User = Depends(require("write")), db: Session = Depends(get_db)):
    """Plan non géoréférencé (PDF, image) positionné manuellement sur la carte (emprise saisie)."""
    _project(db, user, pid, write=True)
    try:
        b = [float(x) for x in json.loads(bounds)]
        assert len(b) == 4 and -180 <= b[0] < b[2] <= 180 and -90 <= b[1] < b[3] <= 90
    except Exception:
        raise HTTPException(422, "Emprise invalide [ouest, sud, est, nord] en degrés.")
    data = await file.read()
    fname = file.filename or "plan"
    if fname.lower().endswith(".pdf"):
        from ai.document_analysis.pdfium_safe import render_png

        p = docsvc.temp_copy(data, ".pdf")
        try:
            png = render_png(p, 1, 2.0)
        finally:
            p.unlink(missing_ok=True)
    else:
        png = geoformats._to_png(data)
    doc, _ = docsvc.add_document(db, user, fname, data, project_id=pid, category="plan", tags=["cartographie"])
    res = geoformats.GeoResult(image_png=png, image_bounds=b, format="Plan positionné manuellement", epsg=4326)
    layer = _store_layer(db, user, request, pid, name or fname.rsplit(".", 1)[0], res, doc.id,
                         crs_note="Positionné manuellement : précision limitée, à vérifier sur le fond de carte.")
    db.commit()
    return _layer_out(layer)


@router.post("/projects/{pid}/geo/service", status_code=201)
def add_service(pid: str, payload: dict, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    """Service cartographique : WMS / WMTS (affichés par le navigateur) ou WFS (objets récupérés par le serveur)."""
    _project(db, user, pid, write=True)
    kind = payload.get("kind")
    url = str(payload.get("url") or "").strip()
    if kind not in ("wms", "wmts", "wfs") or not url.startswith(("https://", "http://")):
        raise HTTPException(422, "Type de service (WMS, WMTS ou WFS) et adresse http(s) requis.")
    layers = str(payload.get("layers") or "").strip()
    name = str(payload.get("name") or layers or kind.upper())[:200]
    if kind == "wfs":
        if not layers:
            raise HTTPException(422, "Nom de la couche WFS (typeName) requis.")
        params = {"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature", "TYPENAMES": layers, "OUTPUTFORMAT": "application/json",
                  "SRSNAME": "EPSG:4326", "COUNT": "5000"}
        try:
            with httpx.Client(timeout=30) as c:
                r = c.get(url, params=params)
            r.raise_for_status()
            res = geoformats.read_geojson(r.content)
        except (httpx.HTTPError, geoformats.GeoError) as ex:
            from ..services.net import explain
            raise HTTPException(502, explain(ex, "Le service WFS") if isinstance(ex, httpx.HTTPError) else f"Réponse du service WFS illisible : {ex}")
        layer = _store_layer(db, user, request, pid, name, res, source_format="WFS")
        layer.service = {"url": url, "layers": layers, "kind": "wfs"}
        layer.kind = "wfs"
    else:
        layer = create_obj(db, GeoLayer, {"project_id": pid, "name": name, "kind": kind, "source_format": kind.upper(), "visible": True,
                                          "service": {"url": url, "layers": layers, "format": payload.get("format") or "image/png",
                                                      "attribution": payload.get("attribution") or "", "opacity": 0.8},
                                          "position": scoped_query(db, GeoLayer, user).filter(GeoLayer.project_id == pid).count()}, user, request)
    db.commit()
    return _layer_out(layer)


@router.put("/geo/layers/{lid}")
def update_layer(lid: str, payload: dict, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    l = get_owned(db, GeoLayer, lid, user)
    data = {k: payload[k] for k in ("name", "visible", "style", "position", "notes") if k in payload}
    if "image" in payload and l.image:
        img = dict(l.image)
        for k in ("opacity", "bounds"):
            if k in (payload["image"] or {}):
                img[k] = payload["image"][k]
        data["image"] = img
    if "service" in payload and l.service:
        data["service"] = {**l.service, **{k: v for k, v in (payload["service"] or {}).items() if k in ("opacity", "attribution")}}
    if "data" in payload and l.kind == "annotations":
        fc = payload["data"] or {}
        if fc.get("type") != "FeatureCollection":
            raise HTTPException(422, "FeatureCollection attendue.")
        data["data"] = fc
        data["bounds"] = geoformats.bounds(fc.get("features", []))
    update_obj(db, l, data, user, payload.get("version"), request)
    db.commit()
    return _layer_out(l)


@router.delete("/geo/layers/{lid}")
def delete_layer(lid: str, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    l = get_owned(db, GeoLayer, lid, user)
    delete_obj(db, l, user, request)
    db.commit()
    return {"ok": True}


@router.get("/geo/layers/{lid}/image")
def layer_image(lid: str, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    l = get_owned(db, GeoLayer, lid, user)
    if not l.image or not storage.exists(l.image.get("png_key", "")):
        raise HTTPException(404, "Image indisponible.")
    return Response(storage.path_for(l.image["png_key"]).read_bytes(), media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})


@router.post("/projects/{pid}/geo/annotations")
def annotations_layer(pid: str, request: Request, user: User = Depends(require("write")), db: Session = Depends(get_db)):
    """Couche d'annotations du projet (créée au besoin) : repères, observations, mesures dessinées."""
    _project(db, user, pid, write=True)
    l = scoped_query(db, GeoLayer, user).filter(GeoLayer.project_id == pid, GeoLayer.kind == "annotations").first()
    if not l:
        l = create_obj(db, GeoLayer, {"project_id": pid, "name": "Annotations et observations", "kind": "annotations", "visible": True,
                                      "data": {"type": "FeatureCollection", "features": []}, "position": 999,
                                      "style": {"color": "#9C3B29", "weight": 3, "fillOpacity": 0.15}}, user, request)
        db.commit()
    return _layer_out(l)


def _kml_coords(coords) -> str:
    return " ".join(f"{c[0]},{c[1]}" for c in coords)


def _kml_geom(g) -> str:
    t = g["type"]
    if t == "Point":
        return f"<Point><coordinates>{g['coordinates'][0]},{g['coordinates'][1]}</coordinates></Point>"
    if t == "LineString":
        return f"<LineString><coordinates>{_kml_coords(g['coordinates'])}</coordinates></LineString>"
    if t == "Polygon":
        rings = g["coordinates"]
        inner = "".join(f"<innerBoundaryIs><LinearRing><coordinates>{_kml_coords(r)}</coordinates></LinearRing></innerBoundaryIs>" for r in rings[1:])
        return f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{_kml_coords(rings[0])}</coordinates></LinearRing></outerBoundaryIs>{inner}</Polygon>"
    if t.startswith("Multi"):
        sub = t[5:]
        return "<MultiGeometry>" + "".join(_kml_geom({"type": sub, "coordinates": c}) for c in g["coordinates"]) + "</MultiGeometry>"
    if t == "GeometryCollection":
        return "<MultiGeometry>" + "".join(_kml_geom(x) for x in g["geometries"]) + "</MultiGeometry>"
    return ""


@router.get("/projects/{pid}/geo/export")
def export_layers(pid: str, fmt: str = "geojson", user: User = Depends(require("read")), db: Session = Depends(get_db)):
    p = _project(db, user, pid)
    feats = []
    for l in scoped_query(db, GeoLayer, user).filter(GeoLayer.project_id == pid).all():
        for f in (l.data or {}).get("features", []):
            feats.append({**f, "properties": {**(f.get("properties") or {}), "couche": l.name}})
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    fname = f"{p.code}_terrain_{stamp}"
    if fmt == "geojson":
        body = json.dumps({"type": "FeatureCollection", "name": fname, "features": feats}, ensure_ascii=False)
        return Response(body, media_type="application/geo+json", headers={"Content-Disposition": f'attachment; filename="{fname}.geojson"'})
    if fmt == "kml":
        pms = []
        for f in feats:
            props = f.get("properties") or {}
            label = props.get("label") or props.get("name") or props.get("texte") or props.get("couche") or ""
            desc = "<br/>".join(f"{escape(str(k))} : {escape(str(v))}" for k, v in props.items() if v not in (None, ""))
            pms.append(f"<Placemark><name>{escape(str(label))}</name><description><![CDATA[{desc}]]></description>{_kml_geom(f['geometry'])}</Placemark>")
        body = f'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>{escape(fname)}</name>{"".join(pms)}</Document></kml>'
        return Response(body, media_type="application/vnd.google-earth.kml+xml", headers={"Content-Disposition": f'attachment; filename="{fname}.kml"'})
    raise HTTPException(422, "Format d'export : geojson ou kml.")


@router.get("/geo/parcel")
def parcel_at(lat: float, lon: float, user: User = Depends(require("read")), db: Session = Depends(get_db)):
    """Identification de la parcelle cadastrale sous un point (API Carto IGN) — information indicative."""
    from ..services.urbanisme import SiteAnalyzer

    cfg = settings_store.get(db, user.agency_id, "urbanisme")
    an = SiteAnalyzer(cfg)
    loc = {"latitude": lat, "longitude": lon}
    an.parcel_at_point(loc)
    parcel = loc.get("parcel")
    if not parcel:
        reason = an.unavailable[0]["reason"] if an.unavailable else "Aucune parcelle à ce point."
        return {"found": False, "reason": reason, "notice": CADASTRE_NOTICE}
    pr = parcel.get("properties") or {}
    ref = f"{pr.get('code_dep', '')}{pr.get('code_com', '')} {pr.get('section', '')} {pr.get('numero', '')}".strip()
    area = geoformats.polygon_area_m2(parcel["geometry"]["coordinates"][0]) if parcel.get("geometry", {}).get("type") == "MultiPolygon" else (
        geoformats.polygon_area_m2(parcel["geometry"]["coordinates"]) if parcel.get("geometry", {}).get("type") == "Polygon" else None)
    return {"found": True, "reference": ref, "commune": pr.get("nom_com"), "section": pr.get("section"), "numero": pr.get("numero"),
            "contenance_m2": pr.get("contenance"), "surface_calculee_m2": round(area) if area else None, "feature": parcel,
            "source": an.sources[0] if an.sources else None, "notice": CADASTRE_NOTICE}


@router.post("/geo/measure")
def measure(payload: dict, user: User = Depends(require("read"))):
    """Longueur (m) ou surface (m²) d'une géométrie WGS84 — même calcul que l'outil de mesure de la carte."""
    g = payload.get("geometry") or {}
    if g.get("type") == "LineString":
        return {"length_m": round(geoformats.length_m(g["coordinates"]), 2)}
    if g.get("type") == "Polygon":
        return {"area_m2": round(geoformats.polygon_area_m2(g["coordinates"]), 2), "perimeter_m": round(geoformats.length_m(g["coordinates"][0]), 2)}
    raise HTTPException(422, "LineString ou Polygon attendu.")
