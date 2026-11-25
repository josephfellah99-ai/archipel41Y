# PostgreSQL 16 + PostGIS 3.4 + pgvector
FROM postgis/postgis:16-3.4
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-16-pgvector && rm -rf /var/lib/apt/lists/*
COPY init-extensions.sql /docker-entrypoint-initdb.d/20-archipel41-extensions.sql
