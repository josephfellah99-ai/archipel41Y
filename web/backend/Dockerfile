# Archipel41 – serveur central (API FastAPI + interface web compilée)
FROM node:22-bookworm-slim AS front
WORKDIR /src/web/frontend
COPY web/frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY web/frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ARCHIPEL_FRONTEND_DIST=/app/web/frontend/dist
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-fra libreoffice-writer-nogui postgresql-client \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY web/backend/requirements*.txt web/backend/
RUN pip install --no-cache-dir -r web/backend/requirements-server.txt
COPY web/backend/app web/backend/app
COPY ai ai
COPY database database
COPY scripts/install/reset_admin_password.py scripts/install/reset_admin_password.py
COPY docs/*.pdf docs/
COPY --from=front /src/web/frontend/dist web/frontend/dist
RUN useradd -r -u 1041 archipel && mkdir -p /data && chown archipel /data
USER archipel
WORKDIR /app/web/backend
EXPOSE 8041
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8041/api/health')"
CMD ["python", "-m", "app"]
