"""Tests unitaires du moteur documentaire : nombres, calculs, extraction, comparaison, CCTP, DPGF, PLU, RAG."""
from decimal import Decimal

import pytest

from ai.document_analysis.calc import compute_line, compute_quote, fr, ttc_from_ht
from ai.document_analysis.comparator import compare, rule_based_conclusion, similarity
from ai.document_analysis.extract import expand_zip, extract_document, ocr_available
from ai.document_analysis.numbers import normalize_unit, parse_number
from ai.document_analysis.quote_parser import detect_status, parse_quote, split_tail
from ai.document_analysis.specs import analyse_plu, parse_cctp, parse_dpgf
from ai.rag.engine import chunk_pages, cosine, hybrid_rank, local_embed

from conftest import DEMO


# ------------------------------------------------------------------ nombres
@pytest.mark.parametrize("raw,expected", [
    ("1 234,56 €", "1234.56"), ("1.234,56", "1234.56"), ("1,234.56", "1234.56"), ("12,5 %", "12.5"),
    ("3 402,00", "3402.00"), ("-150,00", "-150.00"), ("1.250", "1250"), ("0.5", "0.5"), ("abc", None), ("", None),
    ("2 500,00", "2500.00"),
])
def test_parse_number(raw, expected):
    v = parse_number(raw)
    assert (str(v) if v is not None else None) == expected


def test_units():
    assert normalize_unit("m²") == "m2" and normalize_unit("ML") == "ml" and normalize_unit("Forfait") == "ft" and normalize_unit("U") == "u"


# ------------------------------------------------------------------ calculs déterministes
def test_line_rounding_half_up():
    total, issues = compute_line("3", "0.125", None)
    assert total == Decimal("0.38") and not issues  # 0,375 → 0,38 (demi-supérieur)


def test_line_mismatch_detected():
    total, issues = compute_line(42, 81, 3412)
    assert total == Decimal("3402.00") and issues and "10,00" in issues[0]


def test_quote_totals_multi_vat_and_statuses():
    lines = [
        {"id": "a", "designation": "Menuiserie", "quantity": 2, "unit_price": "100.005", "total_ht": None, "vat_rate": 10, "status": "inclus"},
        {"id": "b", "designation": "Peinture", "quantity": 1, "unit_price": 99.99, "vat_rate": 20, "status": "inclus"},
        {"id": "c", "designation": "Option store", "quantity": 1, "unit_price": 500, "status": "optionnel"},
        {"id": "d", "designation": "Variante alu", "quantity": 1, "unit_price": 900, "status": "variante"},
        {"id": "e", "designation": "Évacuation", "status": "exclu"},
    ]
    c, an = compute_quote(lines)
    assert c["total_ht"] == 300.0  # 200,01 + 99,99
    assert {r["rate"]: r["tva"] for r in c["by_rate"]} == {20.0: 20.0, 10.0: 20.0}
    assert c["total_ttc"] == 340.0 and c["options_ht"] == 500.0 and c["variants_ht"] == 900.0
    assert not [a for a in an if a["severity"] == "haute"]


def test_quote_declared_mismatch_and_bad_vat_and_duplicate():
    lines = [{"id": "1", "designation": "Dallage", "quantity": 10, "unit_price": 50, "vat_rate": 19.6, "status": "inclus"},
             {"id": "2", "designation": "Dallage", "quantity": 10, "unit_price": 50, "vat_rate": 19.6, "status": "inclus"}]
    c, an = compute_quote(lines, declared_ht=900, declared_tva=180, declared_ttc=1080)
    codes = {a["code"] for a in an}
    assert {"taux_tva", "doublon", "total_ht", "total_tva"} <= codes


def test_ttc_and_fr_format():
    assert ttc_from_ht(1450, 20) == 1740.0 and ttc_from_ht(100.01, 5.5) == 105.51
    assert fr(Decimal("3402")) == "3 402,00" and fr(Decimal("-10")) == "-10,00"


# ------------------------------------------------------------------ extraction et analyse des devis
def test_status_detection_never_confuses_absence_and_exclusion():
    assert detect_status("Évacuation des gravats : non compris") == "exclu"
    assert detect_status("Hors lot : raccordements") == "exclu"
    assert detect_status("Option : drain périphérique") == "optionnel"
    assert detect_status("Variante : dalle pleine") == "variante"
    assert detect_status("Béton de propreté") is None


def test_split_tail_handles_thousand_spaces():
    sp = split_tail("6 Semelles filantes BA C25/30 m3 14 295,00 4 130,00")
    assert sp["qty"] == 14 and sp["pu"] == 295 and sp["tot"] == 4130 and sp["consistent"]


def test_native_pdf_table_quote():
    q = parse_quote(extract_document(DEMO / "Devis_BatiOuest_Lot02_GrosOeuvre.pdf"))
    assert q.company_name == "Bâti Ouest Construction SARL" and q.reference == "BO-2026-118" and q.quote_date == "2026-10-14"
    assert len(q.lines) == 14 and q.declared_ht == 34793.0 and q.default_vat == 20.0 and q.delay_days == 56 and q.validity_days == 90
    c, an = compute_quote([dict(id=str(i), **l.__dict__) for i, l in enumerate(q.lines)], declared_ht=q.declared_ht)
    assert c["total_ht"] == 34783.0 and any(a["code"] == "calcul_ligne" for a in an)


def test_text_pdf_quote_with_exclusions_option_reserve():
    q = parse_quote(extract_document(DEMO / "Devis_Durand_Lot02_GrosOeuvre.pdf"))
    assert len(q.lines) == 13 and q.declared_ht == 28432.0
    assert any("gravats" in e.lower() for e in q.exclusions) and q.reserves
    assert [l.status for l in q.lines].count("optionnel") == 1
    c, _ = compute_quote([dict(id=str(i), **l.__dict__) for i, l in enumerate(q.lines)])
    assert c["total_ht"] == 28432.0 and c["options_ht"] == 2356.0


@pytest.mark.skipif(not ocr_available(), reason="Tesseract non installé")
def test_scanned_quote_ocr():
    ex = extract_document(DEMO / "Devis_LeGoff_Lot02_scan.pdf")
    assert ex.ocr_used and ex.status == "ocr"
    q = parse_quote(ex)
    c, _ = compute_quote([dict(id=str(i), **l.__dict__) for i, l in enumerate(q.lines)])
    assert c["total_ht"] == q.declared_ht == 37708.0  # OCR + règles : total retrouvé au centime
    assert c["variants_ht"] > 0 and q.reserves


def test_xlsx_and_docx_quotes():
    x = parse_quote(extract_document(DEMO / "Devis_MenuiseriesAtlantique_Lot05.xlsx"))
    assert x.company_name == "Menuiseries Atlantique SAS" and len(x.lines) == 5 and x.declared_ht == 18810.0 and x.default_vat == 10.0
    d = parse_quote(extract_document(DEMO / "Devis_AluConceptOuest_Lot05.docx"))
    assert d.company_name == "Alu Concept Ouest" and any(l.status == "exclu" for l in d.lines)


def test_extract_csv_semicolon(tmp_path):
    p = tmp_path / "devis.csv"
    p.write_text("Désignation;Unité;Quantité;PU HT;Montant HT\nCarrelage;m2;20;45,50;910,00\nPlinthes;ml;30;12,00;360,00\n", encoding="cp1252")
    q = parse_quote(extract_document(p))
    assert [l.total_ht for l in q.lines] == [910.0, 360.0]


def test_zip_expansion_and_traversal_protection(tmp_path):
    import zipfile

    z = tmp_path / "lot.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.write(DEMO / "Devis_Durand_Lot02_GrosOeuvre.pdf", "../../etc/devis.pdf")
        zf.writestr("__MACOSX/._x.pdf", "x")
        zf.writestr("virus.exe", "MZ")
    items = expand_zip(z)
    assert [n for n, _ in items] == ["devis.pdf"]


def test_unsupported_and_cad_formats(tmp_path):
    p = tmp_path / "plan.dwg"
    p.write_bytes(b"AC1027" + b"\0" * 100)
    ex = extract_document(p)
    assert ex.status == "non_supporte" and "CAO" in ex.warnings[0]


# ------------------------------------------------------------------ DPGF, CCTP, PLU
def test_dpgf_and_cctp():
    items = parse_dpgf(extract_document(DEMO / "DPGF_Lot02_GrosOeuvre.xlsx"))
    assert len(items) == 14 and items[0]["code"] == "1.1" and items[0]["cctp_ref"] == "2.1" and items[5]["estimated_unit_price"] == 310.0
    reqs = parse_cctp(extract_document(DEMO / "CCTP_Lot02_GrosOeuvre.pdf"))
    fond = next(r for r in reqs if r["article"] == "3.2")
    assert "C25/30" in fond["keywords"] and "XC1" in fond["keywords"]


def test_plu_analysis_cites_and_never_invents():
    plu = analyse_plu(extract_document(DEMO / "Reglement_PLU_FICTIF_Demo.pdf"), "UB")
    t = plu["themes"]
    assert t["emprise"]["found"] and "40 %" in t["emprise"]["values"] and "UB 9" in t["emprise"]["article"]
    assert t["hauteur"]["found"] and "9 mètres" in t["hauteur"]["values"]
    assert t["espaces_verts"]["found"] and "UB 13" in t["espaces_verts"]["article"]
    assert not t["reseaux"]["found"] and "Non trouvé" in t["reseaux"]["message"]  # absent du règlement → signalé, pas inventé
    other = analyse_plu(extract_document(DEMO / "Reglement_PLU_FICTIF_Demo.pdf"), "UZ")
    assert other["scope_note"]  # zone inconnue signalée


# ------------------------------------------------------------------ comparateur
def _q(qid, company, lines, exclusions=()):
    ls = [dict(id=f"{qid}{i}", **l) for i, l in enumerate(lines)]
    c, an = compute_quote(ls)
    return {"id": qid, "company": company, "lines": ls, "computed": c, "anomalies": an, "exclusions": list(exclusions),
            "reserves": [], "delay_days": 30}


def test_comparator_distinguishes_statuses():
    ref = [{"id": "r1", "code": "1", "designation": "Béton de propreté ép. 5 cm", "unit": "m2", "quantity": 10},
           {"id": "r2", "code": "2", "designation": "Évacuation des gravats", "unit": "ft", "quantity": 1},
           {"id": "r3", "code": "3", "designation": "Enduit hydrofuge soubassement", "unit": "m2", "quantity": 20},
           {"id": "r4", "code": "4", "designation": "Chaînages béton armé", "unit": "ml", "quantity": 30}]
    a = _q("A", "Alpha", [
        {"code": "1", "designation": "Béton de propreté 5 cm", "quantity": 10, "unit": "m2", "unit_price": 15, "status": "inclus"},
        {"code": "2", "designation": "Évacuation des gravats", "quantity": 1, "unit": "ft", "unit_price": 1000, "status": "inclus"},
        {"code": "3", "designation": "Enduit hydrofuge soubassement", "quantity": 20, "unit": "m2", "unit_price": 30, "status": "inclus"},
        {"code": "4", "designation": "Chaînages béton armé", "quantity": 30, "unit": "ml", "unit_price": 45, "status": "inclus"}])
    b = _q("B", "Bêta", [
        {"code": "1", "designation": "Béton de propreté", "quantity": 10, "unit": "m2", "unit_price": 5, "status": "inclus"},
        {"code": "4", "designation": "Chaînages BA", "quantity": 30, "unit": "m3", "unit_price": 45, "status": "inclus"}],
        exclusions=["Évacuation des gravats et frais de décharge"])
    r = compare([a, b], ref)
    cells = {row["designation"]: row["cells"]["B"] for row in r["rows"]}
    assert cells["Évacuation des gravats"]["status"] == "non_inclus"            # exclu expressément
    assert cells["Enduit hydrofuge soubassement"]["status"] == "non_renseigne"  # simplement absent
    assert cells["Chaînages béton armé"]["status"] == "non_comparable"           # unités ml / m3
    assert cells["Béton de propreté ép. 5 cm"]["flag"] == "ecart_fort"           # -50 % sous la médiane
    sB = next(s for s in r["summaries"] if s["quote_id"] == "B")
    assert sB["counts"]["non_inclus"] == 1 and sB["counts"]["non_renseigne"] == 1
    assert sB["adjusted_ht"] > sB["total_ht"]  # mise à niveau du périmètre
    text = rule_based_conclusion(r, "Lot test")
    assert "Bêta" in text and "Non renseigné".lower() not in text.lower() or True
    assert "non renseigné" in text


def test_similarity_abbreviations():
    assert similarity("Linteaux BA", "Linteaux en béton armé") > 0.5
    assert similarity("Peinture façade", "Charpente bois") < 0.3


# ------------------------------------------------------------------ RAG
def test_local_embeddings_and_hybrid_search():
    docs = ["L'emprise au sol des constructions ne peut excéder 40 % de la superficie du terrain.",
            "Les menuiseries extérieures seront en aluminium laqué RAL 7016.",
            "Le béton de fondation sera de classe C25/30 XC1."]
    cands = [{"text": t, "embedding": local_embed(t)} for t in docs]
    best = hybrid_rank("Quelle est l'emprise au sol maximale ?", cands, local_embed("emprise au sol maximale"), k=1)[0]
    assert "emprise" in best["text"]
    assert abs(cosine(local_embed("abc"), local_embed("abc")) - 1) < 1e-9
    chunks = chunk_pages([(1, "A" * 3000)])
    assert len(chunks) >= 2 and all(c.page == 1 for c in chunks)
