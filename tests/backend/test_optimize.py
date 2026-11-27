"""Lecture fiable des nombres, caractéristiques techniques, remarques et optimisation à qualité constante."""
import io
from decimal import Decimal

import pytest

from ai.document_analysis.comparator import compare
from ai.document_analysis.quote_parser import split_tail
from ai.document_analysis.values import compare_value, extract_values

from conftest import DEMO


# ------------------------------------------------------------------ nombres : jamais confondus
@pytest.mark.parametrize("line,des,qty,pu,tot,vat", [
    # nombre technique en fin de désignation : n'est PAS une quantité
    ("Menuiserie PVC 1250 x 1350 Uw 1,3 u 4 890,00 3 560,00", "Menuiserie PVC 1250 x 1350 Uw 1,3", "4", "890.00", "3560.00", None),
    ("Fourreau TPC Ø 90 ml 40 6,50 260,00", "Fourreau TPC Ø 90", "40", "6.50", "260.00", None),
    ("Porte coupe-feu EI 30 u 2 1 150,00 2 300,00 10 %", "Porte coupe-feu EI 30", "2", "1150.00", "2300.00", "10"),
    ("Charpente 2024 ft 1 9 800,00 9 800,00", "Charpente 2024", "1", "9800.00", "9800.00", None),
    # séparateurs de milliers et TVA en colonne sans « % »
    ("Terrassement m3 1 200 18,00 21 600,00", "Terrassement", "1200", "18.00", "21600.00", None),
    ("Mur parpaing 20x20x50 m2 150 52,00 7 800,00 20", "Mur parpaing 20x20x50", "150", "52.00", "7800.00", "20"),
    # nombres techniques au milieu de la désignation
    ("Béton C25/30 dosé 350 kg m3 12 145,00 1 740,00", "Béton C25/30 dosé 350 kg", "12", "145.00", "1740.00", None),
    ("1.2.3 Semelles filantes 60x30 ml 42 81,00 3 402,00", "Semelles filantes 60x30", "42", "81.00", "3402.00", None),
])
def test_numbers_never_confused(line, des, qty, pu, tot, vat):
    r = split_tail(line)
    assert r is not None, line
    assert r["des"] == des
    assert (r["qty"], r["pu"], r["tot"]) == (Decimal(qty), Decimal(pu), Decimal(tot))
    assert r["consistent"] is True
    assert (str(r["vat"]) if r["vat"] is not None else None) == vat


def test_inconsistent_line_is_flagged_not_hidden():
    r = split_tail("Enduit de façade m2 100 25,00 2 600,00")
    assert r is not None and r["consistent"] is False  # 100 × 25 = 2 500 ≠ 2 600 : signalé, jamais corrigé en silence


# ------------------------------------------------------------------ caractéristiques techniques
def _kinds(des):
    return {v.kind: v.display() for v in extract_values(des)}


def test_technical_values():
    assert _kinds("Béton C25/30 dosé 350 kg/m3") == {"classe_beton": "C25/30", "dosage": "350 kg/m³"}
    assert _kinds("Dallage BA 13 cm sur hérisson")["epaisseur"] == "130 mm"
    assert _kinds("Dalle ép. 0,20 m")["epaisseur"] == "200 mm"
    assert _kinds("Menuiserie PVC Uw 1,3")["uw"] == "1,3 W/m².K"
    assert _kinds("Isolant R=7 300 mm") == {"r_thermique": "7 m².K/W", "epaisseur": "300 mm"}
    assert _kinds("Fourreau Ø 90 mm") == {"diametre": "90 mm"}  # pas une épaisseur
    assert _kinds("Semelles 60x30 cm") == {"dimensions": "60×30"}
    assert _kinds("Porte EI 60")["coupe_feu"] == "EI 60"
    assert _kinds("Enduit monocouche") == {}


def test_quality_direction():
    v = lambda d: extract_values(d)[0]  # noqa: E731
    assert compare_value(v("Béton C20/25"), v("Béton C25/30")) == "inferieur"
    assert compare_value(v("Fenêtre Uw 1,6"), v("Fenêtre Uw 1,3")) == "inferieur"   # Uw : plus bas = mieux
    assert compare_value(v("Fenêtre Uw 1,1"), v("Fenêtre Uw 1,3")) == "superieur"
    assert compare_value(v("Dalle ép. 18 cm"), v("Dalle ép. 20 cm")) == "inferieur"
    assert compare_value(v("Fourreau Ø 63"), v("Fourreau Ø 90")) == "different"


# ------------------------------------------------------------------ optimisation : synthétique
def _q(qid, company, lines, total):
    return {"id": qid, "company": company, "computed": {"total_ht": total, "total_ttc": total * 1.2}, "lines": lines,
            "exclusions": [], "reserves": [], "anomalies": []}


def _l(i, des, unit, qty, pu):
    return {"id": i, "designation": des, "unit": unit, "quantity": qty, "unit_price": pu,
            "total_ht": float(Decimal(str(qty)) * Decimal(str(pu))), "status": "inclus"}


REF = [{"id": "r1", "code": "1", "designation": "Dallage béton ép. 20 cm", "unit": "m2", "quantity": 100},
       {"id": "r2", "code": "2", "designation": "Béton de fondation C25/30", "unit": "m3", "quantity": 10},
       {"id": "r3", "code": "3", "designation": "Enduit de façade", "unit": "m2", "quantity": 200}]


def test_quality_guard_and_exact_savings():
    a = _q("A", "Alpha", [_l("a1", "Dallage béton ép. 20 cm", "m2", 100, 40), _l("a2", "Béton fondation C25/30", "m3", 10, 150),
                          _l("a3", "Enduit façade", "m2", 200, 30)], 11500)
    b = _q("B", "Bêta", [_l("b1", "Dallage béton ép. 16 cm", "m2", 100, 30), _l("b2", "Béton fondation C25/30", "m3", 10, 160),
                         _l("b3", "Enduit façade", "m2", 170, 25)], 8850)
    c = _q("C", "Gamma", [_l("c1", "Dallage béton ép. 20 cm", "m2", 100, 52), _l("c2", "Béton fondation C25/30", "m3", 12, 155),
                          _l("c3", "Enduit façade", "m2", 200, 26.1)], 12280)
    res = compare([a, b, c], REF)
    opt = res["optimization"]
    rem = opt["remarks"]
    # Bêta : épaisseur 16 cm < 20 cm → écart de qualité haute, prix exclu des cibles
    assert any(r["company"] == "Bêta" and r["category"] == "qualite" and r["severity"] == "haute" and "160 mm au lieu de 200 mm" in r["message"] for r in rem)
    dallage = next(r for r in res["rows"] if r["designation"].startswith("Dallage"))
    assert dallage["target_ht"] == 4600.0          # médiane des seules offres conformes (4 000 et 5 200), pas 3 000
    gamma = next(o for o in opt["offers"] if o["company"] == "Gamma")
    lv = next(x for x in gamma["levers"] if x["kind"] == "prix")
    assert lv["saving_ht"] == 600.0                # 5 200 − 4 600, exact au centime
    # Gamma : 12 m³ au lieu de 10 → économie exacte 2 × 155 = 310
    assert any(x["kind"] == "quantite" and x["saving_ht"] == 310.0 for x in gamma["levers"])
    # Bêta : 170 m² d'enduit au lieu de 200 → coût caché 30 × 25 = 750
    beta = next(o for o in opt["offers"] if o["company"] == "Bêta")
    assert any(h["kind"] == "sous_quantite" and h["amount_ht"] == 750.0 for h in beta["hidden"])
    assert beta["quality_issues"] >= 1 and opt["recommended_quote_id"] != "B"
    # arithmétique décimale : pas d'erreur de flottant (26,1 × 200 = 5 220,00)
    assert next(r for r in res["rows"] if r["designation"].startswith("Enduit"))["cells"]["C"]["amount"] == 5220.0


# ------------------------------------------------------------------ bout en bout sur les devis de démonstration
def test_demo_real_cost_and_levers(client, agency, project):
    h, pid = agency["admin"], project["id"]
    lot = client.post("/api/lots", json={"project_id": pid, "code": "02", "name": "Gros œuvre"}, headers=h).json()
    with open(DEMO / "DPGF_Lot02_GrosOeuvre.xlsx", "rb") as f:
        client.post("/api/dpgf/import", files={"file": ("DPGF.xlsx", f.read())}, data={"project_id": pid, "lot_id": lot["id"]}, headers=h)
    files = [("files", (n, open(DEMO / n, "rb").read())) for n in
             ("Devis_BatiOuest_Lot02_GrosOeuvre.pdf", "Devis_Durand_Lot02_GrosOeuvre.pdf", "Devis_LeGoff_Lot02_scan.pdf")]
    assert client.post("/api/quotes/import", files=files, data={"project_id": pid, "lot_id": lot["id"]}, headers=h).status_code == 201
    cmp = client.post("/api/comparisons", json={"project_id": pid, "lot_id": lot["id"]}, headers=h).json()
    opt = cmp["result"]["optimization"]
    offers = {o["company"]: o for o in opt["offers"]}
    durand = next(v for k, v in offers.items() if "Durand" in k)
    assert durand["total_ht"] == 28432.0 and durand["hidden_costs_ht"] == 2560.0 and durand["probable_cost_ht"] == 30992.0
    legoff = next(v for k, v in offers.items() if "Le Goff" in k)
    assert legoff["negotiable_ht"] == 1361.0 and len(legoff["levers"]) == 4
    # le prix anormalement bas de Durand (béton de propreté −57 %) est signalé et n'est jamais une cible
    assert any("anormalement bas" in r["message"] and "Durand" in (r["company"] or "") for r in opt["remarks"])
    propre = next(r for r in cmp["result"]["rows"] if r["designation"].startswith("Béton de propreté"))
    assert propre["target_ht"] == 744.0  # médiane de 720 et 768, sans 312
    assert "Optimisation économique à qualité constante" in cmp["conclusion"]
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(client.get(f"/api/comparisons/{cmp['id']}/export?fmt=xlsx", headers=h).content))
    assert {"Optimisation", "Leviers de négociation", "Remarques techniques"} <= set(wb.sheetnames)
    assert client.get(f"/api/comparisons/{cmp['id']}/export?fmt=pdf", headers=h).content.startswith(b"%PDF")
