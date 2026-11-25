"""Météo de chantier : géocodage (Base Adresse Nationale), prévisions Open-Meteo
(sans clé API) et analyse des risques par type d'activité.

Mode démonstration : prévisions SIMULÉES, déterministes, explicitement marquées.
"""
from __future__ import annotations

import hashlib
import math
from datetime import date, timedelta

import httpx

TIMEOUT = 15.0

WEATHER_CODES = {
    0: "Ciel clair", 1: "Peu nuageux", 2: "Partiellement nuageux", 3: "Couvert", 45: "Brouillard", 48: "Brouillard givrant",
    51: "Bruine légère", 53: "Bruine", 55: "Bruine forte", 56: "Bruine verglaçante", 57: "Bruine verglaçante forte",
    61: "Pluie faible", 63: "Pluie", 65: "Pluie forte", 66: "Pluie verglaçante", 67: "Pluie verglaçante forte",
    71: "Neige faible", 73: "Neige", 75: "Neige forte", 77: "Grains de neige", 80: "Averses", 81: "Averses",
    82: "Averses violentes", 85: "Averses de neige", 86: "Averses de neige fortes", 95: "Orage", 96: "Orage avec grêle",
    99: "Orage violent avec grêle",
}

# Seuils indicatifs (à adapter aux prescriptions du CCTP, des fiches techniques et des DTU)
RULES: dict[str, list[tuple[str, str, float, str]]] = {
    "beton": [("tmin", "<", 5, "Risque de gel du béton frais (T° min < 5 °C) : prévoir adjuvant/protection ou décaler le coulage"),
              ("tmax", ">", 30, "Forte chaleur (> 30 °C) : cure renforcée, coulage tôt le matin"),
              ("rain", ">", 5, "Pluie > 5 mm : risque de délavage du béton frais")],
    "fondations": [("tmin", "<", 5, "Risque de gel pour le béton de fondation"), ("rain", ">", 10, "Fouilles inondées possibles (> 10 mm)")],
    "terrassement": [("rain", ">", 10, "Pluie > 10 mm : sols détrempés, portance et circulation des engins dégradées")],
    "maconnerie": [("tmin", "<", 0, "Gel : mortiers et maçonneries à protéger (T° min < 0 °C)"), ("rain", ">", 8, "Pluie soutenue : protéger les ouvrages frais")],
    "charpente": [("gust", ">", 60, "Rafales > 60 km/h : levage des éléments de charpente déconseillé"), ("rain", ">", 8, "Pluie : protéger les bois")],
    "couverture": [("wind", ">", 40, "Vent > 40 km/h : travail en toiture dangereux"), ("gust", ">", 60, "Rafales > 60 km/h"),
                   ("rain", ">", 2, "Pluie : couverture hors d'eau non assurée")],
    "etancheite": [("rain", ">", 0.5, "Pluie : pose d'étanchéité impossible sur support humide"), ("tmin", "<", 5, "T° < 5 °C : collage des membranes compromis"),
                   ("wind", ">", 40, "Vent fort en toiture")],
    "facade": [("rain", ">", 1, "Pluie : enduits et ravalement à reporter"), ("tmin", "<", 5, "T° < 5 °C : prise des enduits compromise"),
               ("gust", ">", 70, "Rafales : sécurité des échafaudages à vérifier")],
    "peinture_ext": [("rain", ">", 0.5, "Pluie : peinture extérieure impossible"), ("prob", ">", 60, "Probabilité de pluie > 60 %"),
                     ("tmin", "<", 5, "T° < 5 °C : séchage compromis")],
    "menuiseries_ext": [("gust", ">", 70, "Rafales > 70 km/h : manutention des grands vitrages déconseillée")],
    "vrd": [("rain", ">", 10, "Pluie forte : terrassements VRD et enrobés à reporter"), ("tmin", "<", 3, "T° < 3 °C : mise en œuvre des enrobés déconseillée")],
    "grue": [("gust", ">", 72, "Rafales > 72 km/h : grue à mettre en girouette (arrêt du levage)")],
}
ACTIVITY_LABELS = {
    "terrassement": "Terrassement", "fondations": "Fondations", "beton": "Béton / coulage", "maconnerie": "Maçonnerie",
    "charpente": "Charpente", "couverture": "Couverture", "etancheite": "Étanchéité", "facade": "Façade / enduits",
    "peinture_ext": "Peinture extérieure", "menuiseries_ext": "Menuiseries extérieures", "vrd": "VRD", "grue": "Levage / grue",
    "interieur": "Travaux intérieurs", "second_oeuvre": "Second œuvre", "autre": "Autre",
}


def http_client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, headers={"User-Agent": "Archipel41/1.0"})


def geocode(address: str, geocoder_url: str, client: httpx.Client | None = None) -> dict | None:
    c = client or http_client()
    r = c.get(geocoder_url, params={"q": address, "limit": 1})
    r.raise_for_status()
    feats = r.json().get("features") or []
    if not feats:
        return None
    f = feats[0]
    lon, lat = f["geometry"]["coordinates"]
    p = f.get("properties", {})
    return {"latitude": lat, "longitude": lon, "label": p.get("label"), "citycode": p.get("citycode"),
            "postcode": p.get("postcode"), "city": p.get("city"), "score": p.get("score")}


def forecast(lat: float, lon: float, base_url: str, client: httpx.Client | None = None, days: int = 14) -> dict:
    c = client or http_client()
    r = c.get(base_url, params={
        "latitude": lat, "longitude": lon, "timezone": "Europe/Paris", "forecast_days": min(16, days),
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,"
                 "wind_speed_10m_max,wind_gusts_10m_max",
    })
    r.raise_for_status()
    d = r.json()["daily"]
    out = []
    for i, day in enumerate(d["time"]):
        out.append({
            "date": day, "code": d["weather_code"][i], "label": WEATHER_CODES.get(d["weather_code"][i], "—"),
            "tmax": d["temperature_2m_max"][i], "tmin": d["temperature_2m_min"][i], "rain": d["precipitation_sum"][i],
            "prob": d["precipitation_probability_max"][i], "wind": d["wind_speed_10m_max"][i], "gust": d["wind_gusts_10m_max"][i],
        })
    return {"days": out, "source": "Open-Meteo (open-meteo.com) – données Météo-France/ECMWF", "simulated": False}


def demo_forecast(seed: str, start: date | None = None, days: int = 14) -> dict:
    """Prévisions SIMULÉES (mode démonstration)."""
    start = start or date.today()
    h = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16)
    out = []
    for i in range(days):
        x = (h >> (i % 24)) & 0xFF
        rain = round(max(0.0, (x % 37) - 22) * 0.9, 1) if i not in (2, 3) else 12.5 + (x % 5)
        gust = 35 + (x % 40) + (30 if i == 6 else 0)
        tmin = round(6.5 + 3 * math.sin(i / 2.5) + (x % 3) - (8 if i in (9, 10) else 0), 1)
        code = 63 if rain > 8 else (61 if rain > 1 else (3 if x % 3 else 1))
        out.append({"date": (start + timedelta(days=i)).isoformat(), "code": code, "label": WEATHER_CODES[code],
                    "tmax": round(tmin + 6 + (x % 5), 1), "tmin": tmin, "rain": rain, "prob": min(100, int(rain * 7 + x % 20)),
                    "wind": round(gust * 0.55), "gust": gust})
    return {"days": out, "source": "DONNÉES MÉTÉO SIMULÉES (mode démonstration)", "simulated": True}


def _check(day: dict, metric: str, op: str, thr: float) -> bool:
    v = day.get(metric)
    if v is None:
        return False
    return v < thr if op == "<" else v > thr


def day_risks(day: dict, activity: str) -> list[str]:
    return [msg for metric, op, thr, msg in RULES.get(activity, []) if _check(day, metric, op, thr)]


def analyse_tasks(tasks: list[dict], days: list[dict]) -> list[dict]:
    """Pour chaque tâche sensible dans la fenêtre de prévision : jours à risque et proposition de décalage."""
    by_date = {d["date"]: d for d in days}
    results = []
    if not days:
        return results
    horizon_start, horizon_end = date.fromisoformat(days[0]["date"]), date.fromisoformat(days[-1]["date"])
    for t in tasks:
        act = t.get("activity") or "autre"
        if act not in RULES or t.get("progress", 0) >= 100:
            continue
        start = date.fromisoformat(str(t["start_date"]))
        dur = max(1, int(t.get("duration_days") or 1))
        end = start + timedelta(days=dur - 1)
        if end < horizon_start or start > horizon_end:
            continue
        risky = []
        d = max(start, horizon_start)
        while d <= min(end, horizon_end):
            day = by_date.get(d.isoformat())
            if day and d.weekday() < 5:
                r = day_risks(day, act)
                if r:
                    risky.append({"date": d.isoformat(), "risks": r, "weather": day})
            d += timedelta(days=1)
        if not risky:
            continue
        suggestion = None
        span = min(dur, 5)
        cand = start
        while cand <= horizon_end - timedelta(days=span - 1):
            window = [by_date.get((cand + timedelta(days=k)).isoformat()) for k in range(span)]
            if all(w and not day_risks(w, act) for w in window) and cand.weekday() < 5:
                suggestion = cand
                break
            cand += timedelta(days=1)
        results.append({
            "task_id": t["id"], "task": t["name"], "activity": act, "activity_label": ACTIVITY_LABELS.get(act, act),
            "start_date": start.isoformat(), "end_date": end.isoformat(), "risky_days": risky,
            "suggested_start": suggestion.isoformat() if suggestion and suggestion != start else None,
            "shift_days": (suggestion - start).days if suggestion and suggestion != start else 0,
            "recommendation": (f"Décaler le démarrage au {suggestion:%d/%m/%Y} (première fenêtre favorable de {span} jour(s) ouvré(s))"
                               if suggestion and suggestion != start else
                               "Aucune fenêtre favorable dans l'horizon de prévision : prévoir des protections ou réévaluer à J-2"),
        })
    return results
