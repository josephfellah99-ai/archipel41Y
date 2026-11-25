"""PostgreSQL : géométries PostGIS (parcelles, projets) et index de recherche.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return  # SQLite (mode bureau) : géométries conservées en GeoJSON, calculs en Python
    op.execute("ALTER TABLE parcel_analyses ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 4326)")
    op.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_parcel_analyses_geom ON parcel_analyses USING gist (geom)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_projects_geom ON projects USING gist (geom)")
    op.execute("""
        CREATE OR REPLACE FUNCTION archipel_parcel_geom() RETURNS trigger AS $$
        BEGIN
          IF NEW.geometry IS NOT NULL THEN
            NEW.geom := ST_SetSRID(ST_GeomFromGeoJSON(NEW.geometry::text), 4326);
          ELSE
            NEW.geom := NULL;
          END IF;
          RETURN NEW;
        END $$ LANGUAGE plpgsql""")
    op.execute("""
        CREATE OR REPLACE FUNCTION archipel_project_geom() RETURNS trigger AS $$
        BEGIN
          IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
            NEW.geom := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
          ELSE
            NEW.geom := NULL;
          END IF;
          RETURN NEW;
        END $$ LANGUAGE plpgsql""")
    op.execute("DROP TRIGGER IF EXISTS trg_parcel_geom ON parcel_analyses")
    op.execute("CREATE TRIGGER trg_parcel_geom BEFORE INSERT OR UPDATE ON parcel_analyses FOR EACH ROW EXECUTE FUNCTION archipel_parcel_geom()")
    op.execute("DROP TRIGGER IF EXISTS trg_project_geom ON projects")
    op.execute("CREATE TRIGGER trg_project_geom BEFORE INSERT OR UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION archipel_project_geom()")
    # Recherche plein texte (français) sur le contenu des documents
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_versions_fts ON document_versions USING gin (to_tsvector('french', coalesce(text, '')))")
    op.execute("CREATE INDEX IF NOT EXISTS ix_chunks_fts ON document_chunks USING gin (to_tsvector('french', text))")


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP TRIGGER IF EXISTS trg_parcel_geom ON parcel_analyses")
    op.execute("DROP TRIGGER IF EXISTS trg_project_geom ON projects")
    op.execute("DROP FUNCTION IF EXISTS archipel_parcel_geom()")
    op.execute("DROP FUNCTION IF EXISTS archipel_project_geom()")
    op.execute("ALTER TABLE parcel_analyses DROP COLUMN IF EXISTS geom")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS geom")
