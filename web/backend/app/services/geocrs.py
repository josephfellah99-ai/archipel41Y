"""Systèmes de coordonnées utilisés en France → WGS84 (longitude, latitude), sans dépendance externe.

Pris en charge :
- EPSG:4326 / 4171 (WGS84 / RGF93 géographiques ; écart RGF93–WGS84 < 1 m, négligé) ;
- EPSG:2154 Lambert-93 et EPSG:3942 à 3950 (Lambert coniques conformes 9 zones CC42 à CC50), ellipsoïde GRS80 ;
- EPSG:27572 NTF / Lambert II étendu (ancien cadastre) : Clarke 1880 IGN + transformation NTF → WGS84
  à 3 paramètres (précision de l'ordre de quelques mètres, à signaler à l'utilisateur) ;
- EPSG:32630 / 32631 / 32632 (UTM WGS84 zones 30 à 32 nord) et EPSG:3857 (Pseudo-Mercator web).

Formules : projection conique conforme de Lambert (Snyder, « Map Projections — A Working Manual », USGS 1987,
§15) et transverse de Mercator (§8), identiques aux algorithmes IGN pour le Lambert-93.
"""
from __future__ import annotations

import math
import re

GRS80 = (6378137.0, 1 / 298.257222101)
WGS84 = (6378137.0, 1 / 298.257223563)
CLARKE_IGN = (6378249.2, 1 / 293.4660212936269)
PARIS_MERIDIAN = 2.33722916666667  # 2°20'14,025" E de Greenwich

NAMES = {4326: "WGS84 (GPS)", 4171: "RGF93 géographique", 2154: "RGF93 / Lambert-93", 27572: "NTF / Lambert II étendu",
         3857: "Pseudo-Mercator (web)", **{3900 + z: f"RGF93 / CC{z}" for z in range(42, 51)},
         **{32600 + z: f"WGS84 / UTM {z} N" for z in (30, 31, 32)}}


def _e(f):
    return math.sqrt(2 * f - f * f)


class LCC:
    """Lambert conique conforme : sécant (2 parallèles) ou tangent (1 parallèle + facteur d'échelle k0)."""

    def __init__(self, ellps, lon0, lat0, x0, y0, phi1=None, phi2=None, k0=1.0):
        self.a, f = ellps
        self.e = _e(f)
        self.lon0 = math.radians(lon0)
        self.x0, self.y0 = x0, y0
        p0 = math.radians(lat0)
        if phi1 is not None:
            p1, p2 = math.radians(phi1), math.radians(phi2)
            m1, m2 = self._m(p1), self._m(p2)
            t1, t2 = self._t(p1), self._t(p2)
            self.n = (math.log(m1) - math.log(m2)) / (math.log(t1) - math.log(t2))
            self.F = m1 / (self.n * t1 ** self.n)
        else:
            self.n = math.sin(p0)
            self.F = self._m(p0) / (self.n * self._t(p0) ** self.n) * k0
        self.rho0 = self.a * self.F * self._t(p0) ** self.n

    def _m(self, p):
        return math.cos(p) / math.sqrt(1 - (self.e * math.sin(p)) ** 2)

    def _t(self, p):
        es = self.e * math.sin(p)
        return math.tan(math.pi / 4 - p / 2) / ((1 - es) / (1 + es)) ** (self.e / 2)

    def forward(self, lon, lat):
        rho = self.a * self.F * self._t(math.radians(lat)) ** self.n
        th = self.n * (math.radians(lon) - self.lon0)
        return self.x0 + rho * math.sin(th), self.y0 + self.rho0 - rho * math.cos(th)

    def inverse(self, x, y):
        dx, dy = x - self.x0, self.rho0 - (y - self.y0)
        rho = math.copysign(math.hypot(dx, dy), self.n)
        t = (rho / (self.a * self.F)) ** (1 / self.n)
        th = math.atan2(dx, dy)
        lon = th / self.n + self.lon0
        phi = math.pi / 2 - 2 * math.atan(t)
        for _ in range(15):
            es = self.e * math.sin(phi)
            nxt = math.pi / 2 - 2 * math.atan(t * ((1 - es) / (1 + es)) ** (self.e / 2))
            if abs(nxt - phi) < 1e-12:
                phi = nxt
                break
            phi = nxt
        return math.degrees(lon), math.degrees(phi)


class UTM:
    def __init__(self, zone: int, ellps=WGS84):
        self.a, f = ellps
        self.e2 = 2 * f - f * f
        self.k0 = 0.9996
        self.lon0 = math.radians(zone * 6 - 183)

    def inverse(self, x, y):
        a, e2, k0 = self.a, self.e2, self.k0
        ep2 = e2 / (1 - e2)
        x -= 500000.0
        m = y / k0
        mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
        e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
        p1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
              + (151 * e1 ** 3 / 96) * math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
        c1 = ep2 * math.cos(p1) ** 2
        t1 = math.tan(p1) ** 2
        n1 = a / math.sqrt(1 - e2 * math.sin(p1) ** 2)
        r1 = a * (1 - e2) / (1 - e2 * math.sin(p1) ** 2) ** 1.5
        d = x / (n1 * k0)
        lat = p1 - (n1 * math.tan(p1) / r1) * (d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
                                               + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720)
        lon = self.lon0 + (d - (1 + 2 * t1 + c1) * d ** 3 / 6 + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120) / math.cos(p1)
        return math.degrees(lon), math.degrees(lat)


def _ntf_to_wgs84(lon, lat):
    """Changement de datum NTF (Clarke 1880 IGN) → WGS84 : translation géocentrique (−168, −60, +320) m."""
    def to_xyz(lon, lat, ellps):
        a, f = ellps
        e2 = 2 * f - f * f
        la, lo = math.radians(lat), math.radians(lon)
        n = a / math.sqrt(1 - e2 * math.sin(la) ** 2)
        return n * math.cos(la) * math.cos(lo), n * math.cos(la) * math.sin(lo), n * (1 - e2) * math.sin(la)

    x, y, z = to_xyz(lon, lat, CLARKE_IGN)
    x, y, z = x - 168, y - 60, z + 320
    a, f = WGS84
    e2 = 2 * f - f * f
    lo = math.atan2(y, x)
    p = math.hypot(x, y)
    la = math.atan2(z, p * (1 - e2))
    for _ in range(10):
        n = a / math.sqrt(1 - e2 * math.sin(la) ** 2)
        la = math.atan2(z + e2 * n * math.sin(la), p)
    return math.degrees(lo), math.degrees(la)


_LAMBERT93 = LCC(GRS80, 3.0, 46.5, 700000.0, 6600000.0, 44.0, 49.0)
_CC = {z: LCC(GRS80, 3.0, float(z), 1700000.0, 1200000.0 + (z - 42) * 1000000.0, z - 0.75, z + 0.75) for z in range(42, 51)}
# Lambert II étendu : sécant sur 45°53'56,108" et 47°41'45,652" (≡ tangent 52 grades, k0 = 0,99987742)
_L2E = LCC(CLARKE_IGN, 0.0, 46.8, 600000.0, 2200000.0, k0=0.99987742)


def to_wgs84(epsg: int, x: float, y: float) -> tuple[float, float]:
    """Retourne (longitude, latitude) WGS84."""
    if epsg in (4326, 4171, 4258, 4019):
        return x, y
    if epsg == 2154:
        return _LAMBERT93.inverse(x, y)
    if 3942 <= epsg <= 3950:
        return _CC[epsg - 3900].inverse(x, y)
    if epsg == 27572:
        lon, lat = _L2E.inverse(x, y)
        return _ntf_to_wgs84(lon + PARIS_MERIDIAN, lat)
    if epsg in (32630, 32631, 32632):
        return UTM(epsg - 32600).inverse(x, y)
    if epsg in (3857, 900913, 102100):
        return math.degrees(x / 6378137.0), math.degrees(2 * math.atan(math.exp(y / 6378137.0)) - math.pi / 2)
    raise ValueError(f"Système de coordonnées EPSG:{epsg} non pris en charge.")


def from_wgs84(epsg: int, lon: float, lat: float) -> tuple[float, float]:
    if epsg in (4326, 4171):
        return lon, lat
    if epsg == 2154:
        return _LAMBERT93.forward(lon, lat)
    if 3942 <= epsg <= 3950:
        return _CC[epsg - 3900].forward(lon, lat)
    raise ValueError(f"Conversion vers EPSG:{epsg} non prise en charge.")


SUPPORTED = sorted(NAMES)


def epsg_from_text(text: str | None) -> int | None:
    """Reconnaît un système dans un fichier .prj (WKT), une URN GeoJSON (« urn:ogc:def:crs:EPSG::2154 ») ou un libellé."""
    if not text:
        return None
    t = text.upper()
    m = re.search(r'AUTHORITY\["EPSG",\s*"?(\d{4,6})"?\]\]\s*$', t.strip()) or re.search(r"EPSG(?:::|:|\")\s*\"?(\d{4,6})", t)
    if m and int(m.group(1)) in NAMES:
        return int(m.group(1))
    if "LAMBERT_93" in t or "LAMBERT-93" in t or "LAMBERT 93" in t or "RGF93_LAMBERT_93" in t:
        return 2154
    m = re.search(r"\bCC\s?(4[2-9]|50)\b", t)
    if m:
        return 3900 + int(m.group(1))
    if "LAMBERT_II" in t or "LAMBERT II" in t or "NTF" in t and "LAMBERT" in t:
        return 27572
    m = re.search(r"UTM_ZONE_(3[0-2])N", t.replace(" ", "_"))
    if m:
        return 32600 + int(m.group(1))
    if "PSEUDO_MERCATOR" in t or "PSEUDO-MERCATOR" in t or "WEB_MERCATOR" in t:
        return 3857
    if t.startswith("GEOGCS") or "GCS_WGS_1984" in t or "GCS_RGF_1993" in t or "CRS84" in t or "WGS 84" in t and "PROJCS" not in t:
        return 4326
    return None


def guess_epsg(xs: list[float], ys: list[float]) -> tuple[int | None, str]:
    """Déduit le système de coordonnées de l'étendue des valeurs (signalé comme hypothèse)."""
    if not xs:
        return None, "aucune coordonnée"
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if -180 <= x0 and x1 <= 180 and -90 <= y0 and y1 <= 90:
        return 4326, "coordonnées en degrés : WGS84 supposé"
    if 50_000 <= x0 and x1 <= 1_300_000 and 6_000_000 <= y0 and y1 <= 7_200_000:
        return 2154, "étendue compatible avec le Lambert-93 (supposé)"
    if 1_000_000 <= x0 and x1 <= 2_400_000 and 1_000_000 <= y0 and y1 <= 9_300_000:
        zone = 42 + round((((y0 + y1) / 2) - 1_200_000) / 1_000_000)
        if 42 <= zone <= 50:
            return 3900 + zone, f"étendue compatible avec la zone CC{zone} (supposé)"
    if 0 <= x0 and x1 <= 1_200_000 and 1_600_000 <= y0 and y1 <= 2_700_000:
        return 27572, "étendue compatible avec le Lambert II étendu (supposé)"
    return None, "coordonnées locales ou système non reconnu"
