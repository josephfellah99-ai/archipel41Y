"""Urbanisme et contraintes de site — sources publiques officielles françaises.

- Base Adresse Nationale (api-adresse.data.gouv.fr) : géocodage ;
- API Carto IGN (apicarto.ign.fr) : module cadastre (parcelles) et module GPU
  (Géoportail de l'Urbanisme : document d'urbanisme, zonage, prescriptions,
  informations, servitudes d'utilité publique) ;
- Géorisques (georisques.gouv.fr) : risques naturels et technologiques, sismicité,
  retrait-gonflement des argiles ;
- Légifrance (API PISTE, identifiants OAuth requis) : textes du code de l'urbanisme.

Principe : chaque information restituée est accompagnée de sa source et de sa date
de consultation. Toute source en échec ou sans résultat est listée dans
`unavailable` : rien n'est déduit ni inventé.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone

import httpx

TIMEOUT = 20.0

SUP_LABELS = {
    "AC1": "Monuments historiques (abords) – avis de l'Architecte des Bâtiments de France",
    "AC2": "Sites inscrits et classés", "AC4": "Site patrimonial remarquable (SPR)",
    "EL7": "Alignement des voies", "PM1": "Plan de prévention des risques naturels (PPRN)",
    "PM3": "Plan de prévention des risques technologiques (PPRT)", "I4": "Lignes électriques",
    "T1": "Voies ferrées", "T5": "Dégagement aéronautique", "AS1": "Périmètres de protection des captages d'eau",
    "PT1": "Télécommunications (protection contre les perturbations)", "PT2": "Télécommunications (obstacles)",
    "EL3": "Halage et marchepied", "A4": "Cours d'eau non domaniaux",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def http_client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, headers={"User-Agent": "Archipel41/1.0"})


def polygon_area_m2(geom: dict | None) -> float | None:
    """Surface géodésique approchée d'un (Multi)Polygon GeoJSON WGS84 (projection locale)."""
    if not geom:
        return None
    polys = geom["coordinates"] if geom.get("type") == "MultiPolygon" else [geom.get("coordinates", [])]
    total = 0.0
    for poly in polys:
        for ri, ring in enumerate(poly):
            if len(ring) < 3:
                continue
            lat0 = math.radians(sum(p[1] for p in ring) / len(ring))
            r = 6371008.8
            pts = [(math.radians(p[0]) * r * math.cos(lat0), math.radians(p[1]) * r) for p in ring]
            a = 0.0
            for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
                a += x1 * y2 - x2 * y1
            total += abs(a) / 2 * (1 if ri == 0 else -1)
    return round(total, 1)


def centroid(geom: dict) -> tuple[float, float] | None:
    try:
        ring = (geom["coordinates"][0][0] if geom["type"] == "MultiPolygon" else geom["coordinates"][0])
        return (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))
    except (KeyError, IndexError, TypeError, ZeroDivisionError):
        return None


class SiteAnalyzer:
    def __init__(self, cfg: dict, client: httpx.Client | None = None):
        self.cfg = cfg
        self.c = client or http_client()
        self.sources: list[dict] = []
        self.unavailable: list[dict] = []

    # ------------------------------------------------------------------ outils
    def _get(self, label: str, url: str, params: dict) -> dict | list | None:
        try:
            r = self.c.get(url, params=params)
            if r.status_code == 404:
                self.unavailable.append({"source": label, "reason": "Aucune donnée pour cette localisation (404)."})
                return None
            r.raise_for_status()
            data = r.json()
            self.sources.append({"source": label, "url": str(r.url), "consulted_at": now_iso()})
            return data
        except httpx.HTTPError as exc:
            from .net import explain
            self.unavailable.append({"source": label, "reason": explain(exc, "Le service")})
        except ValueError:
            self.unavailable.append({"source": label, "reason": "Réponse illisible du service."})
        return None

    def _gpu(self, layer: str, geom: dict, label: str) -> list[dict]:
        data = self._get(f"Géoportail de l'Urbanisme – {label}", f"{self.cfg['apicarto']}/gpu/{layer}",
                         {"geom": json.dumps(geom)})
        feats = (data or {}).get("features") if isinstance(data, dict) else None
        return [f.get("properties", {}) for f in feats or []]

    # ------------------------------------------------------------------ étapes
    def locate(self, query_type: str, query: str) -> dict:
        loc: dict = {"query_type": query_type, "query": query}
        if query_type == "coordonnees":
            m = re.match(r"^\s*(-?\d+(?:[.,]\d+)?)\s*[,; ]\s*(-?\d+(?:[.,]\d+)?)\s*$", query)
            if not m:
                raise ValueError("Coordonnées attendues sous la forme « latitude, longitude » (ex. 47.2184, -1.5536).")
            loc["latitude"], loc["longitude"] = float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
        elif query_type == "adresse":
            data = self._get("Base Adresse Nationale", self.cfg["geocoder"], {"q": query, "limit": 1})
            feats = (data or {}).get("features") or []
            if not feats:
                if data is not None:
                    self.unavailable.append({"source": "Base Adresse Nationale", "reason": "Adresse introuvable."})
                return loc
            f = feats[0]
            loc["longitude"], loc["latitude"] = f["geometry"]["coordinates"]
            loc["label"] = f["properties"].get("label")
            loc["insee"] = f["properties"].get("citycode")
            loc["geocoding_score"] = f["properties"].get("score")
        elif query_type == "cadastre":
            m = re.match(r"^\s*(\d{5})\s*[- ]?\s*(?:(\d{3})\s*[- ]?)?\s*([0A-Z]{1,2})\s*[- ]?\s*(\d{1,4})\s*$", query.upper())
            if not m:
                raise ValueError("Référence cadastrale attendue : code INSEE + section + numéro (ex. 44109 AB 0123).")
            loc["insee"], prefix, loc["section"], num = m.group(1), m.group(2), m.group(3).rjust(2, "0"), m.group(4)
            loc["numero"] = num.rjust(4, "0")
            params = {"code_insee": loc["insee"], "section": loc["section"], "numero": loc["numero"]}
            if prefix:
                params["com_abs"] = prefix
            data = self._get("Cadastre (API Carto IGN)", f"{self.cfg['apicarto']}/cadastre/parcelle", params)
            feats = (data or {}).get("features") or []
            if feats:
                loc["parcel"] = feats[0]
                c = centroid(feats[0]["geometry"])
                if c:
                    loc["longitude"], loc["latitude"] = c
            elif data is not None:
                self.unavailable.append({"source": "Cadastre (API Carto IGN)", "reason": "Parcelle introuvable."})
        return loc

    def parcel_at_point(self, loc: dict) -> None:
        if "parcel" in loc or loc.get("latitude") is None:
            return
        pt = {"type": "Point", "coordinates": [loc["longitude"], loc["latitude"]]}
        data = self._get("Cadastre (API Carto IGN)", f"{self.cfg['apicarto']}/cadastre/parcelle", {"geom": json.dumps(pt)})
        feats = (data or {}).get("features") or []
        if feats:
            loc["parcel"] = feats[0]
        elif data is not None:
            self.unavailable.append({"source": "Cadastre (API Carto IGN)", "reason": "Aucune parcelle à ce point."})

    def run(self, query_type: str, query: str) -> dict:
        loc = self.locate(query_type, query)
        self.parcel_at_point(loc)
        result: dict = {"location": loc}
        parcel = loc.get("parcel")
        geom = parcel["geometry"] if parcel else (
            {"type": "Point", "coordinates": [loc["longitude"], loc["latitude"]]} if loc.get("latitude") is not None else None)
        if parcel:
            p = parcel.get("properties", {})
            loc.update({"insee": loc.get("insee") or (p.get("code_dep", "") + p.get("code_com", "")),
                        "section": p.get("section"), "numero": p.get("numero"), "commune": p.get("nom_com"),
                        "idu": p.get("idu"), "contenance_m2": p.get("contenance")})
            result["area_m2"] = p.get("contenance") or polygon_area_m2(parcel["geometry"])
            result["area_source"] = "Contenance cadastrale" if p.get("contenance") else "Surface calculée à partir de la géométrie cadastrale"
        if geom is None:
            self.unavailable.append({"source": "Localisation", "reason": "Impossible de localiser le terrain : analyse interrompue."})
            return self._finish(result)
        docs = self._gpu("document", geom, "document d'urbanisme")
        result["documents"] = [{"type": d.get("du_type") or d.get("typedoc"), "name": d.get("nom") or d.get("grid_title"),
                                "approved": d.get("datappro"), "status": d.get("etat"), "partition": d.get("partition"),
                                "id": d.get("gpu_doc_id") or d.get("id")} for d in docs]
        zones = self._gpu("zone-urba", geom, "zonage")
        result["zones"] = [{"code": z.get("libelle"), "label": z.get("libelong"), "type": z.get("typezone"),
                            "destination": z.get("destdomi"), "approved": z.get("datappro"), "doc_id": z.get("idurba"),
                            "reglement_url": z.get("urlfic"), "partition": z.get("partition")} for z in zones]
        if not zones:
            sect = self._gpu("secteur-cc", geom, "carte communale")
            if sect:
                result["zones"] = [{"code": s.get("libelle"), "label": s.get("libelong"), "type": "carte communale",
                                    "destination": s.get("destdomi")} for s in sect]
            else:
                self.unavailable.append({"source": "Géoportail de l'Urbanisme – zonage",
                                         "reason": "Aucun zonage publié (commune possiblement soumise au RNU, ou document non numérisé)."})
        presc = []
        for layer, kind in (("prescription-surf", "surfacique"), ("prescription-lin", "linéaire"), ("prescription-pct", "ponctuelle")):
            for p in self._gpu(layer, geom, f"prescriptions ({kind})"):
                presc.append({"label": p.get("libelle"), "text": p.get("txt"), "type": p.get("typepsc"), "kind": kind,
                              "sub_type": p.get("stypepsc")})
        result["prescriptions"] = presc
        infos = []
        for layer, kind in (("info-surf", "surfacique"), ("info-lin", "linéaire"), ("info-pct", "ponctuelle")):
            for p in self._gpu(layer, geom, f"informations ({kind})"):
                infos.append({"label": p.get("libelle"), "text": p.get("txt"), "type": p.get("typeinf"), "kind": kind})
        result["informations"] = infos
        sups = []
        for layer in ("assiette-sup-s", "assiette-sup-l", "assiette-sup-p"):
            for s in self._gpu(layer, geom, "servitudes d'utilité publique"):
                cat = (s.get("suptype") or "").upper()
                sups.append({"category": cat, "label": s.get("nomsuplitt") or s.get("nomass") or SUP_LABELS.get(cat, cat),
                             "category_label": SUP_LABELS.get(cat), "id": s.get("idsup")})
        result["servitudes"] = sups
        result["patrimoine"] = [s for s in sups if s["category"] in ("AC1", "AC2", "AC4")]
        self._risks(loc, result)
        return self._finish(result)

    def _risks(self, loc: dict, result: dict) -> None:
        if loc.get("latitude") is None:
            return
        latlon = f"{loc['longitude']},{loc['latitude']}"
        base = self.cfg["georisques"]
        risks = {}
        g = self._get("Géorisques – risques recensés (GASPAR)", f"{base}/gaspar/risques", {"latlon": latlon})
        if isinstance(g, dict):
            det = []
            for item in g.get("data") or []:
                for r in item.get("risques_detail") or []:
                    det.append(r.get("libelle_risque_long"))
            risks["commune"] = sorted({d for d in det if d})
        s = self._get("Géorisques – zonage sismique", f"{base}/zonage_sismique", {"latlon": latlon})
        if isinstance(s, dict) and s.get("data"):
            risks["sismicite"] = s["data"][0].get("zone_sismicite")
        a = self._get("Géorisques – retrait-gonflement des argiles", f"{base}/rga", {"latlon": latlon})
        if isinstance(a, dict) and (a.get("exposition") or a.get("codeExposition")):
            risks["argiles"] = a.get("exposition") or a.get("codeExposition")
        result["risques"] = risks

    def _finish(self, result: dict) -> dict:
        result["sources"] = self.sources
        result["unavailable"] = self.unavailable
        return result


# ---------------------------------------------------------------------- Légifrance
class Legifrance:
    """Client de l'API Légifrance (PISTE). Identifiants OAuth « client credentials » requis."""

    def __init__(self, cfg: dict, client: httpx.Client | None = None):
        self.cfg = cfg
        self.c = client or http_client()

    @property
    def configured(self) -> bool:
        return bool(self.cfg.get("legifrance_client_id") and self.cfg.get("legifrance_client_secret"))

    def _token(self) -> str:
        r = self.c.post(self.cfg["legifrance_oauth"], data={
            "grant_type": "client_credentials", "client_id": self.cfg["legifrance_client_id"],
            "client_secret": self.cfg["legifrance_client_secret"], "scope": "openid"})
        r.raise_for_status()
        return r.json()["access_token"]

    def search_code_urbanisme(self, query: str, size: int = 5) -> list[dict]:
        tok = self._token()
        body = {"fond": "CODE_DATE", "recherche": {
            "champs": [{"typeChamp": "ALL", "criteres": [{"typeRecherche": "TOUS_LES_MOTS_DANS_UN_CHAMP", "valeur": query,
                                                          "operateur": "ET"}], "operateur": "ET"}],
            "filtres": [{"facette": "NOM_CODE", "valeurs": ["Code de l'urbanisme"]},
                        {"facette": "DATE_VERSION", "singleDate": int(datetime.now().timestamp() * 1000)}],
            "pageNumber": 1, "pageSize": size, "sort": "PERTINENCE", "typePagination": "ARTICLE", "operateur": "ET"}}
        r = self.c.post(self.cfg["legifrance_api"] + "/search", json=body, headers={"Authorization": f"Bearer {tok}"})
        r.raise_for_status()
        out = []
        for res in r.json().get("results") or []:
            for sec in res.get("sections") or []:
                for ext in sec.get("extracts") or []:
                    out.append({"id": ext.get("id"), "num": ext.get("num"), "title": res.get("titles", [{}])[0].get("title"),
                                "text": " ".join(ext.get("values") or [])[:1500],
                                "url": f"https://www.legifrance.gouv.fr/codes/article_lc/{ext.get('id')}" if ext.get("id") else None})
        return out


# ---------------------------------------------------------------------- démonstration
def demo_result(query: str) -> dict:
    """Résultat FICTIF pour la démonstration hors ligne (commune inventée « Démoville »)."""
    ring = [[-1.5541, 47.2180], [-1.5533, 47.2180], [-1.5533, 47.2185], [-1.5541, 47.2185], [-1.5541, 47.2180]]
    geom = {"type": "Polygon", "coordinates": [ring]}
    return {
        "location": {"query": query, "label": "12 rue des Ateliers, 99999 Démoville (FICTIF)", "latitude": 47.21825,
                     "longitude": -1.5537, "insee": "99999", "section": "AB", "numero": "0123", "commune": "Démoville",
                     "parcel": {"type": "Feature", "geometry": geom, "properties": {"contenance": 2290}}},
        "area_m2": 2290, "area_source": "Contenance cadastrale (FICTIVE)",
        "documents": [{"type": "PLU", "name": "PLU de Démoville (FICTIF)", "approved": "2024-06-12", "status": "opposable"}],
        "zones": [{"code": "UB", "label": "Zone urbaine pavillonnaire (FICTIVE)", "type": "U", "destination": "Habitat"}],
        "prescriptions": [{"label": "Élément de paysage à protéger (haie bocagère)", "type": "07", "kind": "linéaire",
                           "text": "Prescription FICTIVE de démonstration"}],
        "informations": [],
        "servitudes": [{"category": "AC1", "label": "Abords de l'église Saint-Démo (FICTIF)",
                        "category_label": SUP_LABELS["AC1"]}],
        "patrimoine": [{"category": "AC1", "label": "Abords de l'église Saint-Démo (FICTIF)", "category_label": SUP_LABELS["AC1"]}],
        "risques": {"commune": ["Inondation (FICTIF)", "Retrait-gonflement des sols argileux (FICTIF)"], "sismicite": "3 (FICTIF)",
                    "argiles": "Moyen (FICTIF)"},
        "sources": [{"source": "MODE DÉMONSTRATION – données fictives, aucune source officielle consultée", "url": None,
                     "consulted_at": now_iso()}],
        "unavailable": [{"source": "Légifrance", "reason": "Mode démonstration : non interrogé."}],
    }


def feasibility(result: dict, plu: dict | None) -> dict:
    """Indicateurs de faisabilité calculés UNIQUEMENT à partir de valeurs citées."""
    area = result.get("area_m2")
    ind = []
    if plu:
        th = plu.get("themes", {})
        emp = th.get("emprise", {})
        pct = next((float(v.replace("%", "").replace(",", ".").strip()) for v in emp.get("values") or [] if v.strip().endswith("%")), None)
        if pct is not None and area:
            ind.append({"label": "Emprise au sol maximale indicative", "value": round(area * pct / 100, 1), "unit": "m²",
                        "formula": f"{area} m² × {pct:g} %", "source": f"{emp.get('article') or 'Règlement'} (p. {emp.get('page')})"})
        ev = th.get("espaces_verts", {})
        pct2 = next((float(v.replace("%", "").replace(",", ".").strip()) for v in ev.get("values") or [] if v.strip().endswith("%")), None)
        if pct2 is not None and area:
            ind.append({"label": "Surface minimale d'espaces verts indicative", "value": round(area * pct2 / 100, 1), "unit": "m²",
                        "formula": f"{area} m² × {pct2:g} %", "source": f"{ev.get('article') or 'Règlement'} (p. {ev.get('page')})"})
        h = th.get("hauteur", {})
        hv = [v for v in h.get("values") or [] if re.search(r"m(è|e)tres?|\bm\b", v)]
        if hv:
            ind.append({"label": "Hauteur(s) citée(s) par le règlement", "value": ", ".join(hv), "unit": "",
                        "formula": "valeurs relevées dans l'article", "source": f"{h.get('article') or 'Règlement'} (p. {h.get('page')})"})
    recos = []
    if result.get("patrimoine"):
        recos.append("Terrain concerné par une protection patrimoniale : consulter l'Architecte des Bâtiments de France en amont.")
    if (result.get("risques") or {}).get("argiles"):
        recos.append("Exposition au retrait-gonflement des argiles : étude géotechnique G1/G2 recommandée (loi ELAN).")
    if result.get("prescriptions"):
        recos.append("Des prescriptions graphiques s'appliquent : vérifier leur portée dans le règlement graphique.")
    if not plu:
        recos.append("Importez le règlement écrit du PLU dans les Documents pour analyser les règles de la zone.")
    recos.append("Vérifier le caractère opposable du document d'urbanisme (modifications/révisions récentes) et les OAP éventuelles.")
    recos.append("Demander un certificat d'urbanisme opérationnel pour sécuriser les règles applicables.")
    return {"indicators": ind, "recommendations": recos}
