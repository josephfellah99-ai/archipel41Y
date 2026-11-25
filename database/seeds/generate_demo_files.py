"""Génère les pièces FICTIVES de démonstration (devis, DPGF, CCTP, règlement de PLU).

Toutes les entreprises, personnes, adresses et règles sont inventées ; chaque
document porte la mention « DOCUMENT FICTIF – DÉMONSTRATION ARCHIPEL41 ».
Usage : python generate_demo_files.py [dossier_sortie]
"""
from __future__ import annotations

import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "demo_files"
OUT.mkdir(parents=True, exist_ok=True)
FICTIF = "DOCUMENT FICTIF – DÉMONSTRATION ARCHIPEL41"

DPGF = [
    ("1.1", "Installation de chantier, clôture et panneau", "ft", 1, 3200, "2.1"),
    ("1.2", "Démolition partielle mur porteur existant y compris étaiement", "m2", 18, 95, "2.2"),
    ("2.1", "Terrassement en pleine masse et mise en dépôt", "m3", 65, 28, "3.1"),
    ("2.2", "Fouilles en rigole pour semelles", "m3", 22, 42, "3.1"),
    ("3.1", "Béton de propreté ép. 5 cm", "m2", 48, 14, "3.2"),
    ("3.2", "Semelles filantes en béton armé C25/30", "m3", 14, 310, "3.2"),
    ("3.3", "Dallage béton armé ép. 13 cm sur hérisson et film polyane", "m2", 42, 78, "3.3"),
    ("4.1", "Murs en blocs béton creux ép. 20 cm", "m2", 96, 68, "4.1"),
    ("4.2", "Chaînages et poteaux en béton armé", "ml", 64, 46, "4.2"),
    ("4.3", "Plancher poutrelles et hourdis béton, table de compression", "m2", 42, 92, "4.3"),
    ("4.4", "Linteaux en béton armé", "u", 8, 165, "4.2"),
    ("5.1", "Enduit hydrofuge sur soubassement", "m2", 30, 32, "5.1"),
    ("6.1", "Évacuation des gravats en décharge agréée", "ft", 1, 1400, "6.1"),
    ("6.2", "Nettoyage de fin de chantier", "ft", 1, 450, "6.2"),
]


def money(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fr(v) -> str:
    s = f"{money(v):,.2f}"
    return s.replace(",", " ").replace(".", ",")


def qfr(v) -> str:
    return (f"{v:g}").replace(".", ",")


styles = getSampleStyleSheet()
small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, leading=10)
norm = ParagraphStyle("norm", parent=styles["Normal"], fontSize=9.5, leading=12)
h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=15, spaceAfter=4)


def quote_pdf(path: Path, company: dict, lines: list[tuple], vat: float, extra_blocks: list[tuple[str, list[str]]],
              ref: str, qdate: str, delay: str, validity: str, payment: str, declared_override: dict | None = None):
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    el = [Paragraph(f"<b>{company['name']}</b>", h1),
          Paragraph(f"{company['address']} – Tél. {company['phone']} – SIRET {company['siret']}", small),
          Paragraph(FICTIF, ParagraphStyle("f", parent=small, textColor=colors.red)), Spacer(1, 6 * mm),
          Paragraph(f"<b>DEVIS N° {ref}</b> &nbsp;&nbsp; Date : {qdate}", norm),
          Paragraph("Client : M. et Mme Lambert (fictifs) – Maîtrise d'œuvre : Atelier Démo Architectes", norm),
          Paragraph("Objet : Extension et rénovation d'une maison individuelle – LOT 02 GROS ŒUVRE", norm), Spacer(1, 4 * mm)]
    data = [["N°", "Désignation", "U", "Qté", "PU HT", "Montant HT"]]
    total = Decimal("0")
    for ln in lines:
        code, des, unit, qty, pu = ln[:5]
        declared = ln[5] if len(ln) > 5 else None
        if qty is None:
            data.append([code, Paragraph(des, small), unit or "", "", "", pu])  # mention texte
            continue
        amount = money(Decimal(str(qty)) * Decimal(str(pu)))
        shown = money(declared) if declared is not None else amount
        if not des.lower().startswith(("option", "variante")):
            total += shown
        data.append([code, Paragraph(des, small), unit, qfr(qty), fr(pu), fr(shown)])
    t = Table(data, colWidths=[12 * mm, 90 * mm, 10 * mm, 14 * mm, 22 * mm, 26 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5), ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E3D8")), ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    el.append(t)
    tva = money(total * Decimal(str(vat)) / 100)
    ttc = total + tva
    d = {"ht": total, "tva": tva, "ttc": ttc}
    if declared_override:
        d.update({k: Decimal(str(v)) for k, v in declared_override.items()})
    el += [Spacer(1, 4 * mm), Paragraph(f"<b>TOTAL HT : {fr(d['ht'])} €</b>", norm),
           Paragraph(f"TVA {qfr(vat)} % : {fr(d['tva'])} €", norm), Paragraph(f"<b>TOTAL TTC : {fr(d['ttc'])} €</b>", norm),
           Spacer(1, 4 * mm), Paragraph(f"Délai d'exécution : {delay}", norm),
           Paragraph(f"Validité de l'offre : {validity}", norm), Paragraph(f"Conditions de paiement : {payment}", norm)]
    for title, items in extra_blocks:
        el += [Spacer(1, 3 * mm), Paragraph(f"<b>{title}</b>", norm)] + [Paragraph(f"- {i}", norm) for i in items]
    doc.build(el)


def text_quote_pdf(path: Path, company: dict, body: list[str]):
    """Devis mis en page « texte » (sans grille) : teste la lecture ligne à ligne."""
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=A4)
    y = 285 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(18 * mm, y, company["name"])
    y -= 6 * mm
    c.setFont("Helvetica", 8.5)
    c.drawString(18 * mm, y, f"{company['address']} - SIRET {company['siret']}")
    y -= 5 * mm
    c.setFillColor(colors.red)
    c.drawString(18 * mm, y, FICTIF)
    c.setFillColor(colors.black)
    y -= 9 * mm
    for ln in body:
        if y < 18 * mm:
            c.showPage()
            y = 280 * mm
        if ln.startswith("##"):
            c.setFont("Helvetica-Bold", 9.5)
            c.drawString(18 * mm, y, ln[2:].strip())
        elif "\t" in ln:
            c.setFont("Helvetica", 8.8)
            parts = ln.split("\t")
            c.drawString(18 * mm, y, parts[0])
            xs = [125, 137, 152, 172, 192]
            for x, p in zip(xs[-(len(parts) - 1):], parts[1:]):
                c.drawRightString(x * mm, y, p)
        else:
            c.setFont("Helvetica", 8.8)
            c.drawString(18 * mm, y, ln)
        y -= 5.2 * mm
    c.save()


def main():
    # ---------------------------------------------------------------- Devis A (tableau, complet, 1 erreur de calcul)
    a = {"name": "Bâti Ouest Construction SARL", "address": "8 impasse des Carriers, 44800 Saint-Herblain",
         "phone": "02 00 00 00 01", "siret": "000 000 001 00011"}
    a_lines = [
        ("1.1", "Installation de chantier, clôture et panneau", "ft", 1, 3400),
        ("1.2", "Démolition partielle du mur porteur existant, y compris étaiement", "m2", 18, 98),
        ("2.1", "Terrassement en pleine masse, mise en dépôt sur site", "m3", 65, 29),
        ("2.2", "Fouilles en rigole pour semelles filantes", "m3", 22, 44),
        ("3.1", "Béton de propreté épaisseur 5 cm", "m2", 48, 15),
        ("3.2", "Semelles filantes béton armé C25/30 XC1", "m3", 14, 325),
        ("3.3", "Dallage béton armé ép. 13 cm sur hérisson et polyane", "m2", 42, 81, 3412.00),  # erreur : 42×81=3402
        ("4.1", "Murs en blocs béton creux ép. 20 cm, NF", "m2", 96, 71),
        ("4.2", "Chaînages horizontaux et verticaux, poteaux BA", "ml", 64, 47),
        ("4.3", "Plancher poutrelles hourdis béton avec table de compression", "m2", 42, 95),
        ("4.4", "Linteaux béton armé préfabriqués", "u", 8, 170),
        ("5.1", "Enduit hydrofuge sur soubassement", "m2", 30, 33),
        ("6.1", "Évacuation des gravats en décharge agréée", "ft", 1, 1450),
        ("6.2", "Nettoyage de fin de chantier", "ft", 1, 480),
    ]
    quote_pdf(OUT / "Devis_BatiOuest_Lot02_GrosOeuvre.pdf", a, a_lines, 20, [
        ("Conditions particulières", ["Révision des prix selon index BT01 au-delà de 3 mois.",
                                       "Assurance décennale : contrat n° FICTIF-0001."]),
    ], "BO-2026-118", "14/10/2026", "8 semaines à compter de l'ordre de service", "3 mois",
              "acompte de 30 % à la commande, solde à 30 jours fin de mois")

    # ---------------------------------------------------------------- Devis B (texte, exclusion, absence, option, prix anormal)
    b = {"name": "SAS Maçonnerie Durand & Fils", "address": "21 route de Vannes, 44700 Orvault", "siret": "000 000 002 00022"}
    b_items = [
        ("1", "Installation de chantier", "ft", 1, 2600),
        ("2", "Démolition mur porteur avec étaiement", "m2", 18, 90),
        ("3", "Terrassement pleine masse", "m3", 65, 26),
        ("4", "Fouilles en rigole", "m3", 22, 40),
        ("5", "Béton de propreté 5 cm", "m2", 48, 6.5),  # prix anormalement bas
        ("6", "Semelles filantes BA C25/30", "m3", 14, 295),
        ("7", "Dallage BA 13 cm sur hérisson", "m2", 42, 74),
        ("8", "Murs blocs béton 20 cm", "m2", 96, 64),
        ("9", "Chaînages et poteaux BA", "ml", 64, 43),
        ("10", "Plancher poutrelles hourdis", "m2", 42, 88),
        ("11", "Linteaux BA", "u", 8, 150),
        ("12", "Nettoyage fin de chantier", "ft", 1, 300),
    ]
    body = ["DEVIS N° MD-26-0457", "Date : 21/10/2026", "Chantier : Extension maison Lambert (fictif) - Lot 02 Gros oeuvre", "",
            "##Désignation\tU\tQté\tPU HT\tMontant HT"]
    total = Decimal("0")
    for code, des, u, q, pu in b_items:
        amt = money(Decimal(str(q)) * Decimal(str(pu)))
        total += amt
        body.append(f"{code} {des}\t{u}\t{qfr(q)}\t{fr(pu)}\t{fr(amt)}")
    opt = money(Decimal("38") * Decimal("62"))
    body += [f"13 Option : drain périphérique PVC avec géotextile\tml\t38\t{fr(62)}\t{fr(opt)}", ""]
    tva = money(total * Decimal("0.20"))
    body += [f"Total HT {fr(total)} €", f"TVA 20 % {fr(tva)} €", f"Total TTC {fr(total + tva)} €", "",
             "Délai : 7 semaines", "Validité de l'offre : 60 jours",
             "Conditions de paiement : 40 % à la commande, solde à réception de facture", "",
             "##Exclusions", "Evacuation des gravats et frais de décharge", "Raccordements aux réseaux",
             "##Réserves", "Prix établis sous réserve d'un sol de portance normale (étude G2 non fournie)"]
    text_quote_pdf(OUT / "Devis_Durand_Lot02_GrosOeuvre.pdf", b, body)

    # ---------------------------------------------------------------- Devis C (scanné, variante, réserve)
    c = {"name": "Entreprise Le Goff Bâtiment", "address": "3 rue du Port, 44200 Nantes", "phone": "02 00 00 00 03",
         "siret": "000 000 003 00033"}
    c_lines = [
        ("1.1", "Installation de chantier", "ft", 1, 3900),
        ("1.2", "Démolition mur porteur et étaiement", "m2", 18, 110),
        ("2.1", "Terrassement en pleine masse", "m3", 65, 34),
        ("2.2", "Fouilles en rigole", "m3", 22, 48),
        ("3.1", "Béton de propreté ép. 5 cm", "m2", 48, 16),
        ("3.2", "Semelles filantes béton armé C25/30", "m3", 14, 340),
        ("3.3", "Dallage béton armé 13 cm sur hérisson", "m2", 42, 86),
        ("4.1", "Murs en blocs béton 20 cm", "m2", 96, 76),
        ("4.2", "Chaînages et poteaux béton armé", "ml", 64, 52),
        ("4.3", "Plancher poutrelles hourdis", "m2", 42, 99),
        ("4.4", "Linteaux béton armé", "u", 8, 180),
        ("5.1", "Enduit hydrofuge soubassement", "m2", 30, 36),
        ("6.1", "Évacuation des gravats en décharge", "ft", 1, 1600),
        ("6.2", "Nettoyage de fin de chantier", "ft", 1, 520),
        ("V1", "Variante : plancher dalle pleine béton coulée en place", "m2", 42, 118),
    ]
    pdf_c = OUT / "_source_LeGoff.pdf"
    quote_pdf(pdf_c, c, c_lines, 20, [("Réserves", ["Sous réserve des conclusions de l'étude de sol G2 PRO."])],
              "LG-1093", "28/10/2026", "10 semaines", "90 jours", "30 % à la commande, situations mensuelles")
    subprocess.run(["pdftoppm", "-r", "200", "-png", "-singlefile", str(pdf_c), str(OUT / "_scan")], check=True)
    from PIL import Image, ImageFilter

    img = Image.open(OUT / "_scan.png").convert("L").rotate(0.6, expand=True, fillcolor=255)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img.save(OUT / "Devis_LeGoff_Lot02_scan.jpg", quality=80)
    img.convert("RGB").save(OUT / "Devis_LeGoff_Lot02_scan.pdf", "PDF", resolution=200)
    for f in ("_scan.png", "_source_LeGoff.pdf"):
        (OUT / f).unlink()

    # ---------------------------------------------------------------- DPGF (Excel)
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DPGF Lot 02"
    ws.append([FICTIF])
    ws.append(["DPGF – LOT 02 GROS ŒUVRE – Extension maison Lambert"])
    ws.append([])
    ws.append(["N°", "Désignation", "Unité", "Quantité", "PU HT estimé", "Montant HT", "Réf. CCTP"])
    for code, des, u, q, pu, ref in DPGF:
        ws.append([code, des, u, q, pu, q * pu, f"CCTP art. {ref}"])
    for col, w in zip("ABCDEFG", (8, 62, 8, 10, 14, 14, 14)):
        ws.column_dimensions[col].width = w
    wb.save(OUT / "DPGF_Lot02_GrosOeuvre.xlsx")

    # ---------------------------------------------------------------- Devis Lot 05 en Excel et en Word
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Menuiseries Atlantique SAS – " + FICTIF])
    ws.append(["Devis n° MA-5521 du 02/11/2026 – Lot 05 Menuiseries extérieures"])
    ws.append([])
    ws.append(["Réf", "Désignation", "Unité", "Quantité", "Prix unitaire HT", "Total HT", "TVA"])
    rows5 = [("A1", "Baie coulissante aluminium 240x215 RAL 7016", "u", 2, 3150), ("A2", "Fenêtre PVC 2 vantaux 120x135", "u", 4, 980),
             ("A3", "Porte d'entrée aluminium vitrée", "u", 1, 2850), ("A4", "Volets roulants motorisés", "u", 6, 640),
             ("A5", "Pose et calfeutrement", "ft", 1, 1900)]
    for r in rows5:
        ws.append([r[0], r[1], r[2], r[3], r[4], r[3] * r[4], "10%"])
    tot = sum(r[3] * r[4] for r in rows5)
    ws.append([])
    ws.append(["", "Total HT", "", "", "", tot])
    ws.append(["", "TVA 10 %", "", "", "", round(tot * 0.10, 2)])
    ws.append(["", "Total TTC", "", "", "", round(tot * 1.10, 2)])
    ws.append(["", "Délai : 6 semaines après validation des plans d'exécution"])
    wb.save(OUT / "Devis_MenuiseriesAtlantique_Lot05.xlsx")

    import docx

    d = docx.Document()
    d.add_heading("Alu Concept Ouest – Devis n° ACO-778", 1)
    d.add_paragraph(FICTIF)
    d.add_paragraph("Date : 05/11/2026 – Lot 05 Menuiseries extérieures – Extension maison Lambert (fictif)")
    t = d.add_table(rows=1, cols=6)
    for i, h in enumerate(["N°", "Désignation", "U", "Qté", "PU HT", "Montant HT"]):
        t.rows[0].cells[i].text = h
    rows5b = [("1", "Baie coulissante aluminium 240x215", "u", 2, 3390), ("2", "Fenêtre PVC 2 vantaux 120x135", "u", 4, 1040),
              ("3", "Porte d'entrée aluminium", "u", 1, 2600), ("4", "Pose et calfeutrement", "ft", 1, 2100)]
    for r in rows5b:
        cells = t.add_row().cells
        for i, v in enumerate([r[0], r[1], r[2], qfr(r[3]), fr(r[4]), fr(r[3] * r[4])]):
            cells[i].text = v
    cells = t.add_row().cells
    cells[1].text = "Volets roulants motorisés : non compris"
    tot = sum(r[3] * r[4] for r in rows5b)
    d.add_paragraph(f"Total HT : {fr(tot)} €")
    d.add_paragraph(f"TVA 10 % : {fr(tot * 0.10)} €")
    d.add_paragraph(f"Total TTC : {fr(tot * 1.10)} €")
    d.add_paragraph("Délai d'exécution : 5 semaines")
    d.save(OUT / "Devis_AluConceptOuest_Lot05.docx")

    # ---------------------------------------------------------------- CCTP
    doc = SimpleDocTemplate(str(OUT / "CCTP_Lot02_GrosOeuvre.pdf"), pagesize=A4)
    el = [Paragraph("CCTP – LOT 02 GROS ŒUVRE", h1), Paragraph(FICTIF, small), Spacer(1, 5 * mm)]
    cctp = [
        ("2.1", "Installation de chantier", "L'entrepreneur assure la clôture du chantier, le panneau réglementaire et les branchements provisoires."),
        ("2.2", "Démolitions", "Démolition partielle du mur porteur après mise en place d'un étaiement justifié par note de calcul."),
        ("3.1", "Terrassements", "Terrassements en pleine masse et fouilles en rigole conformément au DTU 12."),
        ("3.2", "Fondations", "Béton de propreté de 5 cm. Semelles filantes en béton C25/30 classe d'exposition XC1, armatures HA conformes NF EN 10080, selon DTU 13.1."),
        ("3.3", "Dallage", "Dallage de 13 cm sur hérisson de 20 cm et film polyane 150 microns, conforme au DTU 13.3."),
        ("4.1", "Maçonnerie", "Murs en blocs béton creux de 20 cm conformes NF EN 771-3, mise en œuvre selon DTU 20.1."),
        ("4.2", "Béton armé", "Chaînages, poteaux et linteaux en béton armé C25/30 conformes au DTU 21."),
        ("4.3", "Planchers", "Plancher poutrelles et hourdis avec table de compression de 5 cm, avis technique en cours de validité."),
        ("5.1", "Enduits", "Enduit hydrofuge sur soubassement jusqu'à 30 cm au-dessus du terrain fini, DTU 26.1."),
        ("6.1", "Gravats et nettoyage", "Évacuation des gravats en décharge agréée avec bordereaux de suivi. Nettoyage de fin de chantier."),
    ]
    for art, title, body in cctp:
        el += [Paragraph(f"<b>{art} {title}</b>", norm), Paragraph(body, norm), Spacer(1, 3 * mm)]
    doc.build(el)

    # ---------------------------------------------------------------- Règlement de PLU FICTIF
    doc = SimpleDocTemplate(str(OUT / "Reglement_PLU_FICTIF_Demo.pdf"), pagesize=A4)
    el = [Paragraph("RÈGLEMENT DE PLU – COMMUNE FICTIVE DE DÉMOVILLE", h1),
          Paragraph(FICTIF + " – Ce règlement est inventé et ne s'applique à aucun territoire réel.", small), Spacer(1, 5 * mm)]
    plu = [
        ("ZONE UA – Centre ancien", None),
        ("Article UA 1 – Occupations et utilisations du sol interdites", "Sont interdites les constructions à usage industriel et les entrepôts."),
        ("Article UA 9 – Emprise au sol", "L'emprise au sol des constructions ne peut excéder 70 % de la superficie du terrain."),
        ("Article UA 10 – Hauteur des constructions", "La hauteur maximale est fixée à 12 mètres au faîtage (R+2+C)."),
        ("ZONE UB – Secteur pavillonnaire", None),
        ("Article UB 1 – Occupations et utilisations du sol interdites", "Sont interdites les installations classées soumises à autorisation, les dépôts de véhicules et les constructions à usage d'entrepôt."),
        ("Article UB 2 – Occupations soumises à conditions particulières", "Les extensions des constructions existantes sont admises dans la limite des règles ci-après."),
        ("Article UB 6 – Implantation par rapport aux voies et emprises publiques", "Les constructions s'implantent avec un recul minimal de 5 m par rapport à l'alignement des voies."),
        ("Article UB 7 – Implantation par rapport aux limites séparatives", "Les constructions s'implantent en limite séparative ou avec un retrait au moins égal à la moitié de la hauteur, sans pouvoir être inférieur à 3 m."),
        ("Article UB 9 – Emprise au sol", "L'emprise au sol des constructions ne peut excéder 40 % de la superficie du terrain."),
        ("Article UB 10 – Hauteur des constructions", "La hauteur maximale des constructions est fixée à 9 mètres au faîtage et 6 mètres à l'égout du toit (R+1+C)."),
        ("Article UB 11 – Aspect extérieur", "Les toitures à deux pans auront une pente comprise entre 35 et 45°. Les toitures terrasses sont admises pour les extensions. Les clôtures sur rue n'excéderont pas 1,50 m."),
        ("Article UB 12 – Stationnement", "Il est exigé 2 places de stationnement par logement, dont une couverte."),
        ("Article UB 13 – Espaces libres et plantations", "30 % au moins de la superficie du terrain sera traitée en espaces verts de pleine terre."),
    ]
    for title, body in plu:
        el.append(Paragraph(f"<b>{title}</b>", norm if body else h1))
        if body:
            el += [Paragraph(body, norm), Spacer(1, 3 * mm)]
    doc.build(el)
    print("Fichiers générés dans", OUT)
    for f in sorted(OUT.iterdir()):
        print(" -", f.name, f.stat().st_size, "octets")


if __name__ == "__main__":
    main()
