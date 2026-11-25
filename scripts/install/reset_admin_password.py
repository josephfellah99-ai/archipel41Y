"""Réinitialise le mot de passe d'un compte (à exécuter sur le poste ou le serveur, avec accès aux données).
   Poste Windows :  "%LOCALAPPDATA%\Programs\Archipel41\resources\python\python.exe" reset_admin_password.py --email ... (voir guide)
   Serveur Docker : docker compose exec app python /app/scripts/install/reset_admin_password.py --email ...
"""
import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "web" / "backend", ROOT.parent / "backend", ROOT.parent / "backend" / "web" / "backend"):
    sys.path.insert(0, str(p))

from app.db import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--email", required=True)
a = ap.parse_args()
pw = getpass.getpass("Nouveau mot de passe : ")
if len(pw) < 10:
    sys.exit("Le mot de passe doit contenir au moins 10 caractères.")
db = SessionLocal()
u = db.query(User).filter(User.email == a.email.lower()).first()
if not u:
    sys.exit("Compte introuvable.")
u.password_hash = hash_password(pw)
u.active = True
u.version += 1
u.dirty = True
db.commit()
print(f"Mot de passe de {u.email} réinitialisé.")
