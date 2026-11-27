"""Point d'entrée FastAPI d'Archipel41 (serveur central et moteur local du mode bureau)."""
from __future__ import annotations

import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import APP_VERSION, ROOT_DIR, get_settings

if str(ROOT_DIR) not in sys.path:  # rend le paquet `ai` importable
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from pydantic import ValidationError as PydanticValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402

from .routers import agenda, assistant, auth, collab, documents, entities, guest, insights, planning, quotes, reports, system, urbanisme  # noqa: E402

log = logging.getLogger("archipel41")


def setup_logging() -> None:
    s = get_settings()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s – %(message)s")
    root = logging.getLogger()
    root.setLevel(s.log_level)
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        fh = RotatingFileHandler(s.logs_dir / "archipel41.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "SAMEORIGIN")
        h.setdefault("Referrer-Policy", "same-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(self)")
        if request.url.path.startswith("/api/"):
            h.setdefault("Cache-Control", "no-store")
        elif not request.url.path.startswith("/assets/"):
            h.setdefault("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' data: blob: https://*.tile.openstreetmap.org https://data.geopf.fr; "
                         "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-src 'self' blob:; "
                         "object-src 'self' blob:; font-src 'self' data:; worker-src 'self'")
        if request.url.scheme == "https":
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.url.path.startswith("/api/") and request.method != "GET":
            log.info("%s %s → %s (%.0f ms)", request.method, request.url.path, response.status_code, (time.time() - start) * 1000)
        return response


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(ROOT_DIR / "database" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT_DIR / "database" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", get_settings().resolved_database_url().replace("%", "%%"))
    command.upgrade(cfg, "head")


def create_app(migrate: bool = True) -> FastAPI:
    s = get_settings()
    setup_logging()
    if migrate:
        run_migrations()
    app = FastAPI(title="Archipel41 API", version=APP_VERSION,
                  description="API REST d'Archipel41 – gestion intelligente d'une agence d'architecture.",
                  docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json")
    app.add_middleware(SecurityHeaders)
    if s.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in s.cors_origins.split(",")],
                           allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

    def _validation_response(raw_errors) -> JSONResponse:
        errors, details = [], []
        for e in raw_errors:
            loc = ".".join(str(x) for x in e.get("loc", []) if x not in ("body", "query"))
            msg = e.get("msg", "").replace("Value error, ", "")
            errors.append(f"{loc} : {msg}" if loc else msg)
            details.append({"loc": [str(x) for x in e.get("loc", [])], "msg": msg, "type": e.get("type")})
        return JSONResponse(status_code=422, content={"detail": "Données invalides – " + " ; ".join(errors), "errors": details})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return _validation_response(exc.errors())

    @app.exception_handler(PydanticValidationError)
    async def model_validation_handler(request: Request, exc: PydanticValidationError):
        return _validation_response(exc.errors())

    @app.exception_handler(Exception)
    async def crash_handler(request: Request, exc: Exception):
        log.exception("Erreur non gérée sur %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Erreur interne : l'incident a été consigné dans le journal."})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": APP_VERSION, "mode": s.mode}

    # Les routes spécifiques précèdent les routes CRUD génériques (/{id})
    for r in (auth.router, guest.router, collab.router, documents.router, quotes.router, agenda.router, planning.router, urbanisme.router,
              assistant.router, insights.router, reports.router, system.router, entities.extra, *entities.routers):
        app.include_router(r)

    dist = Path(s.frontend_dist)
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"detail": "Ressource API introuvable."}, status_code=404)
            target = (dist / path).resolve()
            if path and target.is_file() and dist.resolve() in target.parents:
                return FileResponse(target)
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

    if s.mode == "desktop":
        from .services import sync

        sync.start_background()
    log.info("Archipel41 %s démarré (mode %s, base %s)", APP_VERSION, s.mode, "SQLite" if s.is_sqlite else "PostgreSQL")
    return app
