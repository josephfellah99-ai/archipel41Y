"""Espace de DÉMONSTRATION d'Archipel41.

Crée une agence FICTIVE « [DÉMO] Atelier Démo Architectes », strictement séparée
des données réelles (agence distincte, drapeau is_demo, bandeau dans l'interface,
mention sur chaque rapport). Les devis de démonstration sont importés avec le
véritable moteur d'extraction et de comparaison.

Comptes créés (mot de passe choisi par l'utilisateur) :
  demo@archipel41.demo (administrateur), claire.martin@archipel41.demo (chef de projet),
  hugo.bernard@archipel41.demo (collaborateur), lea.petit@archipel41.demo (lecture seule)
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

DEMO_DIR = Path(__file__).parent / "demo_files"
PARIS = ZoneInfo("Europe/Paris")


def _dt(d: date, h: int, m: int = 0) -> datetime:
    return datetime.combine(d, time(h, m), tzinfo=PARIS).astimezone(timezone.utc)


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def seed_demo(db: Session, password: str) -> dict:
    from app.crud import create_obj
    from app.models import Agency, User
    from app.routers.entities import default_phases
    from app.security import hash_password
    from app.services import settings_store
    from app.services import documents as docsvc
    from app.models import (BudgetLine, Client, Company, Event, FinanceEntry, Incident, Lot, Project, Quote, Task)
    from ai.document_analysis.calc import ttc_from_ht
    from ai.document_analysis.quote_parser import parse_quote
    from ai.document_analysis.specs import parse_cctp, parse_dpgf

    if not (DEMO_DIR / "Devis_BatiOuest_Lot02_GrosOeuvre.pdf").exists():
        import subprocess
        import sys

        subprocess.run([sys.executable, str(Path(__file__).parent / "generate_demo_files.py"), str(DEMO_DIR)], check=True)

    agency = Agency(name="[DÉMO] Atelier Démo Architectes", siret=None, address="1 place de la Démonstration, 99999 Démoville",
                    email="contact@archipel41.demo", is_demo=True)
    db.add(agency)
    db.flush()
    pw = hash_password(password)
    admin = User(agency_id=agency.id, email="demo@archipel41.demo", full_name="Alex Démo", role="admin", password_hash=pw,
                 job_title="Architecte associé", color="#253A33")
    db.add(admin)
    db.flush()
    people = {}
    for email, name, role, title, color in [
        ("claire.martin@archipel41.demo", "Claire Martin", "manager", "Cheffe de projet", "#718578"),
        ("hugo.bernard@archipel41.demo", "Hugo Bernard", "member", "Architecte collaborateur", "#A07D52"),
        ("lea.petit@archipel41.demo", "Léa Petit", "viewer", "Assistante", "#5C6F8A"),
    ]:
        u = create_obj(db, User, {"email": email, "full_name": name, "role": role, "job_title": title, "color": color,
                                  "password_hash": pw}, admin)
        u.password_hash = pw
        people[role] = u
    settings_store.put(db, agency.id, "weather", {"demo": True})
    settings_store.put(db, agency.id, "urbanisme", {"demo": True})

    today = date.today()
    mon = _monday(today)
    # ---------------------------------------------------------------- annuaire
    lambert = create_obj(db, Client, {"name": "M. et Mme Lambert (fictifs)", "kind": "particulier", "email": "lambert@exemple.demo",
                                      "phone": "06 00 00 00 10", "address": "12 rue des Ateliers", "postal_code": "99999", "city": "Démoville",
                                      "contacts": [{"name": "Julien Lambert", "role": "Maître d'ouvrage", "email": "j.lambert@exemple.demo"}],
                                      "notes": "Souhaite une extension bois lumineuse ; budget serré, sensibles au calendrier."}, admin)
    mairie = create_obj(db, Client, {"name": "Commune de Démoville (fictive)", "kind": "collectivite", "email": "urbanisme@demoville.demo",
                                     "address": "Place de la Mairie", "postal_code": "99999", "city": "Démoville",
                                     "contacts": [{"name": "Service technique", "role": "Maîtrise d'ouvrage publique"}]}, admin)
    sci = create_obj(db, Client, {"name": "SCI Quai Vert (fictive)", "kind": "promoteur", "email": "sci@quaivert.demo", "city": "Démoville"}, admin)
    comp = {}
    for name, specs, city, rating in [
        ("Bâti Ouest Construction SARL", ["Gros œuvre", "Maçonnerie"], "Saint-Herblain", 4),
        ("SAS Maçonnerie Durand & Fils", ["Gros œuvre", "Maçonnerie"], "Orvault", 3),
        ("Entreprise Le Goff Bâtiment", ["Gros œuvre", "Charpente"], "Nantes", 4),
        ("Menuiseries Atlantique SAS", ["Menuiseries extérieures"], "Rezé", 4),
        ("Alu Concept Ouest", ["Menuiseries extérieures", "Serrurerie"], "Carquefou", 3),
        ("Charpentes du Bocage", ["Charpente", "Ossature bois"], "Clisson", 5),
    ]:
        comp[name] = create_obj(db, Company, {"name": name, "specialties": specs,
                                              "city": city, "rating": rating, "email": f"contact@{name.split()[0].lower()}.demo",
                                              "contacts": [{"name": "Conducteur de travaux", "role": "Contact devis"}],
                                              "notes": "Entreprise fictive (démonstration)."}, admin)
    # ---------------------------------------------------------------- projet principal
    ph = default_phases()
    for p in ph:
        if p["code"] in ("ESQ", "APS", "APD", "PC", "PRO", "DCE"):
            p.update(status="terminee", progress=100)
        elif p["code"] == "ACT":
            p.update(status="en_cours", progress=60)
    team = [{"user_id": admin.id, "role": "Architecte mandataire"}, {"user_id": people["manager"].id, "role": "Cheffe de projet"},
            {"user_id": people["member"].id, "role": "Suivi de chantier"}]
    p1 = create_obj(db, Project, {
        "code": "DEMO-24-07", "name": "Extension et rénovation – Maison Lambert", "client_id": lambert.id,
        "description": "Extension à ossature bois de 42 m² sur dalle béton, ouverture d'un mur porteur, reprise des menuiseries extérieures.",
        "program": "Maison individuelle – extension + rénovation", "address": "12 rue des Ateliers", "postal_code": "99999", "city": "Démoville",
        "latitude": 47.21825, "longitude": -1.5537, "status": "chantier", "phases": ph, "current_phase": "ACT", "team": team,
        "terrain": {"parcelle": "99999 AB 0123 (fictive)", "surface_cadastrale_m2": 2290, "zone_plu": "UB", "notes": "Terrain plat, sol argileux à confirmer (G2)."},
        "surface_m2": 168, "budget_initial": 98000, "fee_rate": 11, "start_date": mon - timedelta(days=14),
        "end_date": mon + timedelta(days=140), "progress": 35, "color": "#253A33"}, admin)
    lots = {}
    for code, name, budget, company in [("01", "VRD – Terrassements généraux", 6500, None), ("02", "Gros œuvre", 36000, None),
                                         ("03", "Charpente – Ossature bois", 24000, "Charpentes du Bocage"),
                                         ("05", "Menuiseries extérieures", 17000, None), ("08", "Plâtrerie – Isolation", 9500, None)]:
        lots[code] = create_obj(db, Lot, {"project_id": p1.id, "code": code, "name": name, "budget": budget,
                                          "company_id": comp[company].id if company else None,
                                          "status": "attribue" if company else "consultation"}, admin)
    # DPGF + CCTP + devis (moteur réel)
    def add_file(name, category, lot=None):
        data = (DEMO_DIR / name).read_bytes()
        doc, ex = docsvc.add_document(db, admin, name, data, project_id=p1.id, category=category, linked={"lot_id": lot.id if lot else None})
        return doc, ex

    from app.models import CctpRequirement, DpgfItem, QuoteLine
    doc, ex = add_file("DPGF_Lot02_GrosOeuvre.xlsx", "dpgf", lots["02"])
    for it in parse_dpgf(ex):
        create_obj(db, DpgfItem, {**it, "project_id": p1.id, "lot_id": lots["02"].id, "source_document_id": doc.id}, admin)
    doc, ex = add_file("CCTP_Lot02_GrosOeuvre.pdf", "cctp", lots["02"])
    for r in parse_cctp(ex):
        create_obj(db, CctpRequirement, {**r, "project_id": p1.id, "lot_id": lots["02"].id, "document_id": doc.id}, admin)
    from app.routers.quotes import apply_parsed

    quote_ids = []
    for name, lot in [("Devis_BatiOuest_Lot02_GrosOeuvre.pdf", "02"), ("Devis_Durand_Lot02_GrosOeuvre.pdf", "02"),
                      ("Devis_LeGoff_Lot02_scan.pdf", "02"), ("Devis_MenuiseriesAtlantique_Lot05.xlsx", "05"),
                      ("Devis_AluConceptOuest_Lot05.docx", "05")]:
        doc, ex = add_file(name, "devis", lots[lot])
        q = create_obj(db, Quote, {"project_id": p1.id, "lot_id": lots[lot].id, "document_id": doc.id}, admin)
        apply_parsed(db, admin, q, parse_quote(ex))
        if lot == "02":
            quote_ids.append(q.id)
    db.flush()
    # Comparaison du lot 02
    from app.routers.quotes import _quote_payload, recompute
    from ai.document_analysis.comparator import compare, rule_based_conclusion
    from app.crud import to_dict
    from app.models import Comparison

    qs = [db.get(Quote, i) for i in quote_ids]
    for q in qs:
        recompute(db, q)
    ref = [to_dict(x) for x in db.query(DpgfItem).filter(DpgfItem.lot_id == lots["02"].id).order_by(DpgfItem.position)]
    cctp = [to_dict(x) for x in db.query(CctpRequirement).filter(CctpRequirement.lot_id == lots["02"].id)]
    res = compare([_quote_payload(db, q) for q in qs], ref, cctp)
    create_obj(db, Comparison, {"project_id": p1.id, "lot_id": lots["02"].id, "title": "Comparatif Lot 02 Gros œuvre",
                                "quote_ids": quote_ids, "result": res,
                                "conclusion": rule_based_conclusion(res, "Lot 02 Gros œuvre"), "conclusion_source": "moteur_regles"}, admin)
    # Règlement de PLU fictif (pour le module urbanisme)
    add_file("Reglement_PLU_FICTIF_Demo.pdf", "urbanisme")
    # ---------------------------------------------------------------- planning
    s0 = mon - timedelta(days=14)
    tasks = {}
    plan = [("inst", "Installation de chantier", 0, 3, "autre", [], 100, None),
            ("terr", "Terrassements et fouilles", 3, 5, "terrassement", ["inst"], 100, None),
            ("fond", "Fondations – semelles filantes", 10, 5, "fondations", ["terr"], 80, None),
            ("dall", "Dallage béton", 15, 4, "beton", ["fond"], 0, None),
            ("murs", "Maçonnerie – murs et chaînages", 21, 10, "maconnerie", ["dall"], 0, None),
            ("char", "Charpente – ossature bois", 35, 10, "charpente", ["murs"], 0, "Charpentes du Bocage"),
            ("couv", "Couverture et étanchéité", 49, 6, "couverture", ["char"], 0, None),
            ("menu", "Pose des menuiseries extérieures", 56, 5, "menuiseries_ext", ["couv"], 0, None),
            ("plat", "Plâtrerie – isolation", 63, 12, "interieur", ["menu"], 0, None),
            ("rec", "Réception des travaux", 120, 0, "autre", ["plat"], 0, None)]
    for key, name, off, dur, act, deps, prog, company in plan:
        t = create_obj(db, Task, {"project_id": p1.id, "name": name, "start_date": s0 + timedelta(days=off), "duration_days": dur,
                                  "milestone": dur == 0, "depends_on": [tasks[d].id for d in deps], "activity": act, "progress": prog,
                                  "responsible_id": people["member"].id if act != "autre" else people["manager"].id,
                                  "company_id": comp[company].id if company else None,
                                  "priority": "haute" if key in ("fond", "dall") else "normale",
                                  "baseline_start": s0 + timedelta(days=off), "baseline_end": s0 + timedelta(days=off + max(dur - 1, 0))}, admin)
        tasks[key] = t
    create_obj(db, Task, {"project_id": p1.id, "name": "Relancer Durand : justification du prix du béton de propreté", "kind": "todo",
                          "start_date": today, "duration_days": 2, "priority": "haute", "responsible_id": people["manager"].id}, admin)
    # ---------------------------------------------------------------- incidents
    create_obj(db, Incident, {"project_id": p1.id, "lot_id": lots["02"].id, "date": today - timedelta(days=4),
                              "title": "Venue d'eau en fond de fouille", "severity": "haute", "status": "en_cours",
                              "description": "Pompage mis en place ; vérifier l'assise des semelles avant coulage."}, admin)
    create_obj(db, Incident, {"project_id": p1.id, "date": today - timedelta(days=9), "title": "Réseau EP existant non repéré",
                              "severity": "moyenne", "status": "clos", "resolution": "Dévoiement réalisé par le lot 01."}, admin)
    # ---------------------------------------------------------------- agenda
    ev = [
        ("Réunion de chantier n°3", "visite_chantier", mon + timedelta(days=1), 9, 11, p1.id, [admin, people["manager"], people["member"]],
         "Points : fond de fouille, planning dallage, choix menuiseries.",
         "Présents : A. Démo, C. Martin, H. Bernard, Bâti Ouest.\n- Décidé : coulage du dallage reporté après validation de l'assise.\n"
         "- Action : Bâti Ouest doit fournir le PV de portance avant le vendredi.\n- Action : C. Martin à transmettre le comparatif lot 05 au client."),
        ("Présentation des offres lot 02 aux Lambert", "rdv_client", mon + timedelta(days=2), 14, 15, p1.id, [admin, people["manager"]],
         "Présentation du comparatif et recommandation.", None),
        ("Visite Médiathèque – relevés", "visite_chantier", mon + timedelta(days=2), 14, 16, None, [people["manager"]], None, None),
        ("Réunion d'agence hebdomadaire", "interne", mon + timedelta(days=4), 9, 10, None, [admin, people["manager"], people["member"], people["viewer"]], None, None),
        ("Rendez-vous Menuiseries Atlantique", "reunion_entreprise", mon + timedelta(days=8), 10, 11, p1.id, [people["member"]], None, None),
        ("Commission urbanisme – Démoville", "reunion_entreprise", mon + timedelta(days=10), 16, 18, None, [admin], None, None),
    ]
    for title, kind, d, h1, h2, pid, who, desc, minutes in ev:
        create_obj(db, Event, {"title": title, "kind": kind, "start": _dt(d, h1), "end": _dt(d, h2), "project_id": pid,
                               "location": "Chantier – 12 rue des Ateliers, Démoville" if kind == "visite_chantier" and pid else "Agence",
                               "participants": [{"user_id": u.id, "name": u.full_name} for u in who], "reminder_minutes": 30,
                               "description": desc, "minutes": minutes, "organizer_id": who[0].id}, admin)
    # ---------------------------------------------------------------- finances
    for code, label, amount in [("01", "VRD", 6500), ("02", "Gros œuvre", 36000), ("03", "Charpente", 24000), ("05", "Menuiseries", 17000), ("08", "Plâtrerie", 9500)]:
        create_obj(db, BudgetLine, {"project_id": p1.id, "lot_id": lots[code].id, "label": f"Lot {code} – {label}",
                                    "initial_amount": amount, "current_amount": amount + (1200 if code == "02" else 0)}, admin)
    fe = [("marche", "03", "Charpentes du Bocage", "Marché lot 03 – Charpente ossature bois", 25300, 20, today - timedelta(days=30), "valide", None),
          ("acompte", "03", "Charpentes du Bocage", "Acompte 30 % à la commande", 7590, 20, today - timedelta(days=25), "paye", today - timedelta(days=10)),
          ("paiement", "03", "Charpentes du Bocage", "Règlement acompte lot 03", 7590, 20, today - timedelta(days=12), "paye", None),
          ("travaux_supp", "03", "Charpentes du Bocage", "TS n°1 – renfort de linteau", 1450, 20, today - timedelta(days=6), "valide", None),
          ("situation", "03", "Charpentes du Bocage", "Situation n°1 – approvisionnements", 3200, 20, today - timedelta(days=3), "emis", today - timedelta(days=1)),
          ("honoraires", None, None, "Honoraires phase ACT", 4200, 20, today - timedelta(days=20), "paye", None),
          ("depense", None, None, "Étude de sol G2 AVP", 1850, 20, today - timedelta(days=40), "paye", None)]
    for kind, lot, company, label, ht, vat, d, status, due in fe:
        create_obj(db, FinanceEntry, {"project_id": p1.id, "lot_id": lots[lot].id if lot else None,
                                      "company_id": comp[company].id if company else None, "kind": kind, "label": label,
                                      "entry_date": d, "due_date": due, "amount_ht": ht, "vat_rate": vat,
                                      "amount_ttc": ttc_from_ht(ht, vat), "status": status, "situation_number": 1 if kind == "situation" else None}, admin)
    # ---------------------------------------------------------------- autres projets
    create_obj(db, Project, {"code": "DEMO-25-02", "name": "Médiathèque de Démoville", "client_id": mairie.id, "status": "etude",
                             "phases": default_phases(), "current_phase": "APS", "city": "Démoville", "budget_initial": 1850000,
                             "surface_m2": 1200, "progress": 15, "team": [{"user_id": people["manager"].id, "role": "Cheffe de projet"}],
                             "start_date": today - timedelta(days=60), "end_date": today + timedelta(days=700), "color": "#718578",
                             "description": "Équipement public de 1 200 m² – concours remporté (fictif)."}, admin)
    create_obj(db, Project, {"code": "DEMO-25-05", "name": "Bureaux Quai Vert – réhabilitation", "client_id": sci.id, "status": "consultation",
                             "phases": default_phases(), "current_phase": "DCE", "city": "Démoville", "budget_initial": 640000, "progress": 55,
                             "confidential": True, "team": [{"user_id": admin.id, "role": "Architecte"}],
                             "description": "Projet confidentiel (accès réservé à l'équipe) – démonstration du cloisonnement.", "color": "#A07D52"}, admin)
    db.flush()
    return {"agency_id": agency.id, "agency": agency.name,
            "accounts": ["demo@archipel41.demo", "claire.martin@archipel41.demo", "hugo.bernard@archipel41.demo", "lea.petit@archipel41.demo"]}


if __name__ == "__main__":
    import argparse
    import sys

    root = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(root), str(root / "web" / "backend")]
    ap = argparse.ArgumentParser(description="Crée l'espace de démonstration Archipel41.")
    ap.add_argument("--password", required=True, help="Mot de passe des comptes de démonstration")
    args = ap.parse_args()
    from app.db import SessionLocal
    from app.main import run_migrations

    run_migrations()
    s = SessionLocal()
    print(seed_demo(s, args.password))
    s.commit()
