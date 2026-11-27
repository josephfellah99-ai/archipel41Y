"""Lot 7 — bibliothèque documentaire : visionneuses, annotations, arborescence ARCHIPEL 41, suggestions, nommage, similaires."""
import hashlib
import io
from pathlib import Path

import pytest

from conftest import upload

DEMO = Path(__file__).resolve().parents[2] / "database" / "seeds" / "demo_files"


def _up(client, h, tmp_path, name, data, project_id=None, **form):
    p = tmp_path / name
    p.write_bytes(data)
    r = upload(client, h, p, "/api/documents/upload", project_id=project_id, **form)
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------------------------------------ visionneuses
def test_viewer_xlsx_french_numbers(client, agency, project, tmp_path):
    import datetime as dt

    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Synthèse"
    ws.append(["Lot", "Montant HT", "Date"])
    ws.append(["Gros œuvre", 1250.5, dt.date(2026, 11, 27)])
    ws.append(["Charpente", 98000, None])
    buf = io.BytesIO(); wb.save(buf)
    d = _up(client, agency["admin"], tmp_path, "Tableau_lots.xlsx", buf.getvalue(), project["id"])["documents"][0]
    v = client.get(f"/api/documents/{d['id']}/view", headers=agency["viewer"]).json()
    assert v["kind"] == "sheet" and v["sheets"][0]["name"] == "Synthèse"
    rows = v["sheets"][0]["rows"]
    assert rows[1] == ["Gros œuvre", "1 250,5", "27/11/2026"] and rows[2][1] == "98 000"


def test_viewer_docx_escapes_content(client, agency, project, tmp_path):
    import docx
    d = docx.Document()
    d.add_heading("Article 1 – Objet", level=1)
    d.add_paragraph("Texte avec <script>alert(1)</script> à afficher tel quel.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text, t.cell(1, 0).text, t.cell(1, 1).text = "Lot", "Montant", "02", "12 000 €"
    buf = io.BytesIO(); d.save(buf)
    doc = _up(client, agency["admin"], tmp_path, "Note.docx", buf.getvalue(), project["id"])["documents"][0]
    v = client.get(f"/api/documents/{doc['id']}/view", headers=agency["admin"]).json()
    assert v["kind"] == "html" and "<h2>" in v["html"] and "<table>" in v["html"] and "12 000 €" in v["html"]
    assert "<script>" not in v["html"] and "&lt;script&gt;" in v["html"]


DXF = """0\nSECTION\n2\nENTITIES\n0\nLINE\n8\nMURS\n10\n0.0\n20\n0.0\n11\n10.0\n21\n0.0\n0\nLWPOLYLINE\n8\nMURS\n90\n4\n70\n1\n10\n0\n20\n0\n10\n10\n20\n0\n10\n10\n20\n6\n10\n0\n20\n6\n0\nTEXT\n8\nTEXTES\n10\n2.0\n20\n3.0\n40\n0.5\n1\nSéjour <b>\n0\nCIRCLE\n8\nPOTEAUX\n10\n5\n20\n3\n40\n0.3\n0\nENDSEC\n0\nEOF\n"""


def test_viewer_dxf_svg(client, agency, project, tmp_path):
    doc = _up(client, agency["admin"], tmp_path, "Plan_RDC.dxf", DXF.encode(), project["id"])["documents"][0]
    v = client.get(f"/api/documents/{doc['id']}/view", headers=agency["admin"]).json()
    assert v["kind"] == "svg" and v["svg"].startswith("<svg") and "<polyline" in v["svg"] and "<polygon" in v["svg"]
    assert "Séjour &lt;b&gt;" in v["svg"] and "<b>" not in v["svg"]
    assert {l["name"] for l in v["layers"]} == {"MURS", "TEXTES", "POTEAUX"}
    assert v["extents"] == [0.0, 0.0, 10.0, 6.0]


IFC = """ISO-10303-21;
HEADER;FILE_DESCRIPTION(('ViewDefinition'),'2;1');FILE_NAME('maquette.ifc','2026-11-27T10:00:00',('A41'),('ARCHIPEL 41'),'IFC','ArchiCAD 27','');FILE_SCHEMA(('IFC4'));ENDSEC;
DATA;
#1=IFCPROJECT('0a',#2,'Extension concession',$,$,$,$,$,$);
#10=IFCSITE('0b',#2,'Terrain',$,$,$,$,$,.ELEMENT.,$,$,$,$,$);
#11=IFCBUILDING('0c',#2,'B\\X2\\00E2\\X0\\timent A',$,$,$,$,$,.ELEMENT.,$,$,$);
#20=IFCBUILDINGSTOREY('0d',#2,'R+1',$,$,$,$,$,.ELEMENT.,3.2);
#21=IFCBUILDINGSTOREY('0e',#2,'RDC',$,$,$,$,$,.ELEMENT.,0.);
#30=IFCWALL('1a',#2,'Mur 1',$,$,$,$,$,$);
#31=IFCWALL('1b',#2,'Mur 2',$,$,$,$,$,$);
#32=IFCWALLSTANDARDCASE('1c',#2,'Mur 3',$,$,$,$,$,$);
#40=IFCDOOR('2a',#2,'Porte',$,$,$,$,$,$,$,$,$,$);
#50=IFCSPACE('3a',#2,'Atelier',$,$,$,$,$,.ELEMENT.,.INTERNAL.,$);
ENDSEC;
END-ISO-10303-21;
"""


def test_viewer_ifc_summary(client, agency, project, tmp_path):
    doc = _up(client, agency["admin"], tmp_path, "Maquette.ifc", IFC.encode(), project["id"])["documents"][0]
    v = client.get(f"/api/documents/{doc['id']}/view", headers=agency["admin"]).json()
    s = v["summary"]
    assert v["kind"] == "ifc" and s["schema"] == "IFC4" and s["project"] == "Extension concession"
    assert s["buildings"] == ["Bâtiment A"] and [x["name"] for x in s["storeys"]] == ["RDC", "R+1"]
    assert {e["label"]: e["count"] for e in s["elements"]}["Murs"] == 3 and s["spaces"] == ["Atelier"]


def test_viewer_unsupported_and_invalid(client, agency, project, tmp_path):
    doc = _up(client, agency["admin"], tmp_path, "Plan.dwg", b"AC1032 binaire", project["id"])["documents"][0]
    assert client.get(f"/api/documents/{doc['id']}/view", headers=agency["admin"]).status_code == 415
    bad = _up(client, agency["admin"], tmp_path, "Faux.xlsx", b"pas un classeur", project["id"])["documents"][0]
    r = client.get(f"/api/documents/{bad['id']}/view", headers=agency["admin"])
    assert r.status_code == 422 and "illisible" in r.json()["detail"]


# ------------------------------------------------------------------------------------------------ annotations
def test_annotations_rights_and_original_untouched(client, agency, project, tmp_path):
    pdf = (DEMO / "CCTP_Lot02_GrosOeuvre.pdf").read_bytes()
    doc = _up(client, agency["admin"], tmp_path, "CCTP_Lot02.pdf", pdf, project["id"])["documents"][0]
    url = f"/api/documents/{doc['id']}/annotations"
    body = {"page": 1, "kind": "zone", "geometry": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.1}, "text": "Vérifier la classe d'exposition du béton"}
    assert client.post(url, json=body, headers=agency["viewer"]).status_code == 403
    assert client.post(url, json={**body, "geometry": {"x": 0.9, "y": 0.2, "w": 0.3, "h": 0.1}}, headers=agency["member"]).status_code == 422
    assert client.post(url, json={**body, "text": "  "}, headers=agency["member"]).status_code == 422
    assert client.post(url, json={**body, "page": 999}, headers=agency["member"]).status_code == 422
    a = client.post(url, json=body, headers=agency["member"])
    assert a.status_code == 201, a.text
    a = a.json()
    assert a["author"] == "Member Test" and a["version_number"] == 1
    lst = client.get(url, headers=agency["viewer"]).json()
    assert len(lst) == 1 and lst[0]["text"].startswith("Vérifier")
    # un lecteur ne modifie pas ; l'auteur oui ; un gestionnaire peut supprimer
    assert client.put(f"/api/documents/annotations/{a['id']}", json={"resolved": True, "version": a["version"]}, headers=agency["viewer"]).status_code == 403
    r = client.put(f"/api/documents/annotations/{a['id']}", json={"resolved": True, "version": a["version"]}, headers=agency["member"])
    assert r.status_code == 200 and r.json()["resolved"] is True
    assert client.delete(f"/api/documents/annotations/{a['id']}", headers=agency["manager"]).status_code == 200
    assert client.get(url, headers=agency["admin"]).json() == []
    # le fichier original n'a pas changé
    dl = client.get(f"/api/documents/{doc['id']}/download", headers=agency["admin"])
    assert hashlib.sha256(dl.content).hexdigest() == hashlib.sha256(pdf).hexdigest()


def test_annotations_follow_version(client, agency, project, tmp_path):
    img = (DEMO / "photo_chantier.jpg") if (DEMO / "photo_chantier.jpg").exists() else None
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (40, 30), "white").save(buf, "PNG")
    doc = _up(client, agency["admin"], tmp_path, "Facade.png", buf.getvalue(), project["id"])["documents"][0]
    url = f"/api/documents/{doc['id']}/annotations"
    assert client.post(url, json={"page": 1, "kind": "repere", "geometry": {"x": 0.5, "y": 0.5}, "text": "Fissure"}, headers=agency["admin"]).status_code == 201
    p = tmp_path / "Facade.png"; Image.new("RGB", (40, 30), "grey").save(p, "PNG")
    with open(p, "rb") as f:
        assert client.post(f"/api/documents/{doc['id']}/versions", files={"file": ("Facade.png", f.read())}, headers=agency["admin"]).status_code == 201
    assert client.get(url, headers=agency["admin"]).json() == []                      # version 2 : pas d'annotation
    assert len(client.get(url + "?version=1", headers=agency["admin"]).json()) == 1     # version 1 : conservée


# ------------------------------------------------------------------------------------------------ référentiel
def test_tree_suggestion_and_naming(client, agency, project, tmp_path):
    h = agency["admin"]
    up = _up(client, h, tmp_path, "261127_A41-XXX-PRJ_ordre de service signe.txt", "Ordre de service n° 3 – démarrage des travaux".encode(), project["id"])
    rep = up["extraction"][0]
    assert rep["suggestion"]["folder"] == "5-Réalisation/05_Organisation chantier/64_OS" and rep["suggestion"]["source"].startswith("R49")
    n = rep["nommage"]
    assert not n["conforme"] and n["proposition"] == "2026-11-27-A41-XXX-PRJ-ordre de service signe.txt"
    assert any("AAAA-MM-JJ" in i for i in n["issues"]) and any("« - »" in i for i in n["issues"])
    doc = up["documents"][0]
    assert doc["folder"] is None                                   # rien n'est classé sans accord
    # acceptation de la suggestion
    r = client.put(f"/api/documents/{doc['id']}", json={"folder": "/5-Réalisation/05_Organisation chantier/64_OS/", "version": doc["version"]}, headers=h)
    assert r.status_code == 200 and r.json()["folder"] == "5-Réalisation/05_Organisation chantier/64_OS"
    assert client.get(f"/api/documents/{doc['id']}/advice", headers=h).json()["suggestion"] is None
    # dossier propre au projet + document non classé
    d2 = _up(client, h, tmp_path, "Notes diverses.txt", b"Notes", project["id"])["documents"][0]
    client.put(f"/api/documents/{d2['id']}", json={"folder": "5-Réalisation/Lot 6 - Platrerie (variable)", "version": d2["version"]}, headers=h)
    _up(client, h, tmp_path, "Sans classement.txt", b"x", project["id"])
    t = client.get(f"/api/documents/tree?project_id={project['id']}", headers=agency["viewer"]).json()
    by = {f["path"]: f for f in t["folders"]}
    assert t["name"] == "Arborescence projet ARCHIPEL 41" and len([f for f in t["folders"] if not f.get("custom")]) == 141
    assert by["5-Réalisation/05_Organisation chantier/64_OS"]["count"] == 1 and by["5-Réalisation"]["total"] == 2
    assert by["5-Réalisation/Lot 6 - Platrerie (variable)"]["custom"] is True
    assert t["unfiled"] == 1 and "Classer ici" in (by["5-Réalisation/05_Organisation chantier/64_OS"]["note"] or "")
    # filtres de la liste
    lst = client.get(f"/api/documents?project_id={project['id']}&folder=5-Réalisation", headers=h).json()
    assert len(lst) == 2
    assert len(client.get(f"/api/documents?project_id={project['id']}&folder=__none__", headers=h).json()) == 1


def test_suggestion_refused_is_not_repeated(client, agency, project, tmp_path):
    h = agency["admin"]
    doc = _up(client, h, tmp_path, "CCTP lot 4 couverture.txt", b"Cahier des clauses techniques particulieres", project["id"])["documents"][0]
    adv = client.get(f"/api/documents/{doc['id']}/advice", headers=h).json()
    assert adv["suggestion"]["folder"] == "4-Economie - Appel Offres/03_CCTP"
    client.put(f"/api/documents/{doc['id']}", json={"linked": {"suggestion_refusee": adv["suggestion"]["folder"]}, "version": doc["version"]}, headers=h)
    assert client.get(f"/api/documents/{doc['id']}/advice", headers=h).json()["suggestion"] is None


def test_naming_rules_unit():
    from app.services.referentiel import check_name, suggest_folder
    assert check_name("2026-11-27-A41-XXX-XXX-PHA-CRR-MOA-001.docx")["conforme"]
    r = check_name("AAMMJJ-A41-X-PHA-CRR-MO-001.docx")
    assert not r["conforme"] and r["proposition"].endswith("-MOA-001.docx")
    assert check_name("Photo chantier.jpg")["conforme"]          # pas de composantes codifiées : rien à redire
    assert suggest_folder("APS_indice_B_plans.pdf")["folder"] == "2-Conception/03_Livrables/03_APS"
    assert suggest_folder("CR chantier 12.pdf", project_status="chantier")["folder"] == "5-Réalisation/09_CR"
    assert suggest_folder("Compte rendu réunion MOA.pdf", project_status="etude")["folder"] == "1-Administration/12_Comptes-rendus"
    assert suggest_folder("IMG_2041.jpg", extension="jpg", project_status="chantier")["folder"] == "5-Réalisation/10_Photos"
    assert suggest_folder("zzz.bin") is None


def test_similar_documents(client, agency, project, tmp_path):
    h = agency["admin"]
    a = _up(client, h, tmp_path, "CCTP beton A.txt", "Béton armé classe d'exposition XC4, enrobage 30 mm, ciment CEM II, dalle de compression.".encode(), project["id"])["documents"][0]
    _up(client, h, tmp_path, "CCTP beton B.txt", "Dalle en béton armé : classe d'exposition XC4, enrobage des armatures 30 mm.".encode(), project["id"])
    _up(client, h, tmp_path, "Planning visite.txt", "Visite du site le mardi matin avec les entreprises candidates.".encode(), project["id"])
    sim = client.get(f"/api/documents/{a['id']}/similar", headers=h).json()
    assert sim and sim[0]["name"] == "CCTP beton B.txt" and all(s["id"] != a["id"] for s in sim)


# ------------------------------------------------------------------------------------------------ noms de fichiers
def test_accented_names_preserved(client, agency, project, tmp_path):
    """Les noms d'origine sont conservés, accents compris (« Pièces écrites – Réunion n°2 ») ;
    seuls les caractères interdits par Windows sont remplacés."""
    up = _up(client, agency["admin"], tmp_path, "Pièces écrites – Réunion n°2.txt", "Compte rendu".encode(), project["id"])
    assert up["documents"][0]["name"] == "Pièces écrites – Réunion n°2.txt"
    from app.services.storage import safe_filename
    assert safe_filename("a<b>c?.txt") == "a_b_c_.txt" and safe_filename("../../etc/passwd") == "passwd" and safe_filename("CON.txt") == "_CON.txt"


def test_zip_names_from_windows_are_decoded(client, agency, project, tmp_path):
    """Archive créée par l'Explorateur Windows (noms en CP850, sans drapeau UTF-8) : les accents sont restitués."""
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Pieces ecrites.txt", "contenu")      # nom ASCII de même longueur, sans drapeau UTF-8
    # remplacer le nom par son encodage OEM (CP850, 18 octets) dans l'en-tête local et le répertoire central
    raw = buf.getvalue().replace(b"Pieces ecrites.txt", "Pièces écrites.txt".encode("cp850"))
    assert zipfile.ZipFile(io.BytesIO(raw)).testzip() is None
    up = _up(client, agency["admin"], tmp_path, "Envoi.zip", raw, project["id"])
    assert [d["name"] for d in up["documents"]] == ["Pièces écrites.txt"]
