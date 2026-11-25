"""schema initial

Revision ID: 0001
Revises: 
Create Date: 2026-11-25 09:24:00.489184
"""
from alembic import op
import sqlalchemy as sa
import app.db


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Recherche vectorielle (RAG) et données géographiques
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    # ### commandes générées par Alembic (vérifiées) ###
    op.create_table('agencies',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('siret', sa.String(length=20), nullable=True),
    sa.Column('address', sa.String(length=300), nullable=True),
    sa.Column('email', sa.String(length=200), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('is_demo', sa.Boolean(), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('audit_logs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=True),
    sa.Column('user_id', sa.String(length=36), nullable=True),
    sa.Column('at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('action', sa.String(length=40), nullable=False),
    sa.Column('entity', sa.String(length=40), nullable=True),
    sa.Column('entity_id', sa.String(length=36), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('ip', sa.String(length=60), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_logs_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_at'), ['at'], unique=False)

    op.create_table('budget_lines',
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('lot_id', sa.String(length=36), nullable=True),
    sa.Column('label', sa.String(length=200), nullable=False),
    sa.Column('initial_amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('current_amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('budget_lines', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_budget_lines_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_budget_lines_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_budget_lines_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_budget_lines_project_id'), ['project_id'], unique=False)

    op.create_table('cctp_requirements',
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('lot_id', sa.String(length=36), nullable=True),
    sa.Column('document_id', sa.String(length=36), nullable=True),
    sa.Column('article', sa.String(length=60), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('keywords', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('page', sa.Integer(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('cctp_requirements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cctp_requirements_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_cctp_requirements_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_cctp_requirements_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_cctp_requirements_project_id'), ['project_id'], unique=False)

    op.create_table('change_log',
    sa.Column('seq', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('entity', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.String(length=36), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('op', sa.String(length=10), nullable=False),
    sa.Column('at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=True),
    sa.Column('device_id', sa.String(length=64), nullable=True),
    sa.Column('changes', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=True),
    sa.PrimaryKeyConstraint('seq')
    )
    with op.batch_alter_table('change_log', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_change_log_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index('ix_change_log_entity', ['entity', 'entity_id'], unique=False)

    op.create_table('clients',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('email', sa.String(length=200), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('address', sa.String(length=300), nullable=True),
    sa.Column('postal_code', sa.String(length=10), nullable=True),
    sa.Column('city', sa.String(length=120), nullable=True),
    sa.Column('siret', sa.String(length=20), nullable=True),
    sa.Column('contacts', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('history', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_clients_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_clients_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_clients_dirty'), ['dirty'], unique=False)

    op.create_table('companies',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('siret', sa.String(length=20), nullable=True),
    sa.Column('specialties', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('email', sa.String(length=200), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('address', sa.String(length=300), nullable=True),
    sa.Column('postal_code', sa.String(length=10), nullable=True),
    sa.Column('city', sa.String(length=120), nullable=True),
    sa.Column('contacts', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('insurance', sa.String(length=300), nullable=True),
    sa.Column('rating', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('history', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('companies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_companies_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_companies_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_companies_dirty'), ['dirty'], unique=False)

    op.create_table('comparisons',
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('lot_id', sa.String(length=36), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('quote_ids', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('result', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('conclusion', sa.Text(), nullable=True),
    sa.Column('conclusion_source', sa.String(length=40), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('comparisons', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_comparisons_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_comparisons_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_comparisons_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_comparisons_project_id'), ['project_id'], unique=False)

    op.create_table('conversations',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('project_id', sa.String(length=36), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('messages', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_conversations_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversations_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversations_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversations_user_id'), ['user_id'], unique=False)

    op.create_table('document_chunks',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('document_id', sa.String(length=36), nullable=False),
    sa.Column('project_id', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('page', sa.Integer(), nullable=True),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('embedding_model', sa.String(length=80), nullable=False),
    sa.Column('embedding', app.db.Embedding(), nullable=True),
    sa.Column('confidential', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('document_chunks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_document_chunks_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_document_chunks_document_id'), ['document_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_document_chunks_project_id'), ['project_id'], unique=False)

    op.create_table('documents',
    sa.Column('project_id', sa.String(length=36), nullable=True),
    sa.Column('name', sa.String(length=300), nullable=False),
    sa.Column('category', sa.String(length=40), nullable=False),
    sa.Column('tags', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('mime', sa.String(length=120), nullable=True),
    sa.Column('extension', sa.String(length=20), nullable=True),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('current_version', sa.Integer(), nullable=False),
    sa.Column('confidential', sa.Boolean(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('text_status', sa.String(length=30), nullable=False),
    sa.Column('page_count', sa.Integer(), nullable=True),
    sa.Column('linked', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_documents_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_documents_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_documents_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_documents_project_id'), ['project_id'], unique=False)

    op.create_table('events',
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('start', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('end', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('all_day', sa.Boolean(), nullable=False),
    sa.Column('location', sa.String(length=300), nullable=True),
    sa.Column('project_id', sa.String(length=36), nullable=True),
    sa.Column('participants', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('reminder_minutes', sa.Integer(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('minutes', sa.Text(), nullable=True),
    sa.Column('document_ids', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('organizer_id', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_events_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_events_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_events_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_events_project_id'), ['project_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_events_start'), ['start'], unique=False)

    op.create_table('finance_entries',
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('lot_id', sa.String(length=36), nullable=True),
    sa.Column('company_id', sa.String(length=36), nullable=True),
    sa.Column('quote_id', sa.String(length=36), nullable=True),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('label', sa.String(length=200), nullable=False),
    sa.Column('reference', sa.String(length=100), nullable=True),
    sa.Column('entry_date', sa.Date(), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('amount_ht', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('vat_rate', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('amount_ttc', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('situation_number', sa.Integer(), nullable=True),
    sa.Column('progress_percent', sa.Float(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('finance_entries', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_finance_entries_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_finance_entries_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_finance_entries_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_finance_entries_project_id'), ['project_id'], unique=False)

    op.create_table('parcel_analyses',
    sa.Column('project_id', sa.String(length=36), nullable=True),
    sa.Column('query_type', sa.String(length=20), nullable=False),
    sa.Column('query', sa.String(length=300), nullable=False),
    sa.Column('label', sa.String(length=300), nullable=True),
    sa.Column('insee', sa.String(length=10), nullable=True),
    sa.Column('section', sa.String(length=10), nullable=True),
    sa.Column('numero', sa.String(length=10), nullable=True),
    sa.Column('latitude', sa.Float(), nullable=True),
    sa.Column('longitude', sa.Float(), nullable=True),
    sa.Column('geometry', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=True),
    sa.Column('area_m2', sa.Float(), nullable=True),
    sa.Column('results', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('rules', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('sources', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('unavailable', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('mode', sa.String(length=20), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('parcel_analyses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_parcel_analyses_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_parcel_analyses_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_parcel_analyses_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_parcel_analyses_project_id'), ['project_id'], unique=False)

    op.create_table('proposals',
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('source', sa.String(length=30), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('target_id', sa.String(length=36), nullable=True),
    sa.Column('payload', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('decided_by', sa.String(length=36), nullable=True),
    sa.Column('decided_at', app.db.UTCDateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('proposals', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_proposals_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_proposals_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_proposals_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_proposals_project_id'), ['project_id'], unique=False)

    op.create_table('reports',
    sa.Column('project_id', sa.String(length=36), nullable=True),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('fmt', sa.String(length=10), nullable=False),
    sa.Column('document_id', sa.String(length=36), nullable=True),
    sa.Column('params', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_reports_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reports_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_reports_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_reports_project_id'), ['project_id'], unique=False)

    op.create_table('settings',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('value', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('agency_id', 'key', name='uq_settings_key')
    )
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_settings_agency_id'), ['agency_id'], unique=False)

    op.create_table('sync_conflicts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('entity', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.String(length=36), nullable=False),
    sa.Column('local_data', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('remote_data', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('local_version', sa.Integer(), nullable=False),
    sa.Column('remote_version', sa.Integer(), nullable=False),
    sa.Column('detected_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('resolution', sa.String(length=20), nullable=True),
    sa.Column('resolved_by', sa.String(length=36), nullable=True),
    sa.Column('resolved_at', app.db.UTCDateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('sync_conflicts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sync_conflicts_agency_id'), ['agency_id'], unique=False)

    op.create_table('users',
    sa.Column('email', sa.String(length=200), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('password_hash', sa.String(length=300), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('job_title', sa.String(length=120), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('color', sa.String(length=20), nullable=True),
    sa.Column('preferences', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('last_login_at', app.db.UTCDateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email', name='uq_users_email')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_dirty'), ['dirty'], unique=False)

    op.create_table('document_versions',
    sa.Column('document_id', sa.String(length=36), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=300), nullable=False),
    sa.Column('storage_key', sa.String(length=300), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('text', sa.Text(), nullable=True),
    sa.Column('file_synced', sa.Boolean(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('document_versions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_document_versions_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_document_versions_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_document_versions_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_document_versions_document_id'), ['document_id'], unique=False)

    op.create_table('projects',
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('client_id', sa.String(length=36), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('program', sa.String(length=200), nullable=True),
    sa.Column('address', sa.String(length=300), nullable=True),
    sa.Column('postal_code', sa.String(length=10), nullable=True),
    sa.Column('city', sa.String(length=120), nullable=True),
    sa.Column('latitude', sa.Float(), nullable=True),
    sa.Column('longitude', sa.Float(), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('phases', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('current_phase', sa.String(length=20), nullable=True),
    sa.Column('team', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('terrain', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('surface_m2', sa.Float(), nullable=True),
    sa.Column('budget_initial', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('fee_rate', sa.Float(), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('progress', sa.Integer(), nullable=False),
    sa.Column('confidential', sa.Boolean(), nullable=False),
    sa.Column('color', sa.String(length=20), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_projects_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_projects_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_projects_dirty'), ['dirty'], unique=False)

    op.create_table('dpgf_items',
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('lot_id', sa.String(length=36), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=True),
    sa.Column('section', sa.String(length=200), nullable=True),
    sa.Column('designation', sa.Text(), nullable=False),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('quantity', sa.Numeric(precision=14, scale=3), nullable=True),
    sa.Column('estimated_unit_price', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('cctp_ref', sa.String(length=60), nullable=True),
    sa.Column('source_document_id', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('dpgf_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_dpgf_items_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_dpgf_items_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_dpgf_items_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_dpgf_items_lot_id'), ['lot_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_dpgf_items_project_id'), ['project_id'], unique=False)

    op.create_table('incidents',
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('lot_id', sa.String(length=36), nullable=True),
    sa.Column('company_id', sa.String(length=36), nullable=True),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('severity', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('resolution', sa.Text(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_incidents_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_incidents_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_incidents_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_incidents_project_id'), ['project_id'], unique=False)

    op.create_table('lots',
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('company_id', sa.String(length=36), nullable=True),
    sa.Column('budget', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('contract_amount', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('progress', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lots', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lots_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_lots_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_lots_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_lots_project_id'), ['project_id'], unique=False)

    op.create_table('quotes',
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('lot_id', sa.String(length=36), nullable=True),
    sa.Column('company_id', sa.String(length=36), nullable=True),
    sa.Column('company_name_raw', sa.String(length=200), nullable=True),
    sa.Column('document_id', sa.String(length=36), nullable=True),
    sa.Column('reference', sa.String(length=100), nullable=True),
    sa.Column('quote_date', sa.Date(), nullable=True),
    sa.Column('validity_days', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('delay_text', sa.String(length=300), nullable=True),
    sa.Column('delay_days', sa.Integer(), nullable=True),
    sa.Column('payment_terms', sa.Text(), nullable=True),
    sa.Column('conditions', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('exclusions', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('reserves', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('variants', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('declared_ht', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('declared_tva', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('declared_ttc', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('computed', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('anomalies', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('extraction', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('validated_by', sa.String(length=36), nullable=True),
    sa.Column('validated_at', app.db.UTCDateTime(timezone=True), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_quotes_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_quotes_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_quotes_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_quotes_lot_id'), ['lot_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_quotes_project_id'), ['project_id'], unique=False)

    op.create_table('tasks',
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('duration_days', sa.Integer(), nullable=False),
    sa.Column('milestone', sa.Boolean(), nullable=False),
    sa.Column('depends_on', sa.JSON().with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('responsible_id', sa.String(length=36), nullable=True),
    sa.Column('company_id', sa.String(length=36), nullable=True),
    sa.Column('lot_id', sa.String(length=36), nullable=True),
    sa.Column('progress', sa.Integer(), nullable=False),
    sa.Column('activity', sa.String(length=30), nullable=False),
    sa.Column('priority', sa.String(length=10), nullable=False),
    sa.Column('baseline_start', sa.Date(), nullable=True),
    sa.Column('baseline_end', sa.Date(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tasks_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tasks_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_tasks_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_tasks_project_id'), ['project_id'], unique=False)

    op.create_table('quote_lines',
    sa.Column('quote_id', sa.String(length=36), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('section', sa.String(length=200), nullable=True),
    sa.Column('code', sa.String(length=40), nullable=True),
    sa.Column('designation', sa.Text(), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=14, scale=3), nullable=True),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('unit_price', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('total_ht', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('vat_rate', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('dpgf_item_id', sa.String(length=36), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('page', sa.Integer(), nullable=True),
    sa.Column('raw', sa.Text(), nullable=True),
    sa.Column('corrected', sa.Boolean(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agency_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('dirty', sa.Boolean(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['quote_id'], ['quotes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('quote_lines', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_quote_lines_agency_id'), ['agency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_quote_lines_deleted'), ['deleted'], unique=False)
        batch_op.create_index(batch_op.f('ix_quote_lines_dirty'), ['dirty'], unique=False)
        batch_op.create_index(batch_op.f('ix_quote_lines_quote_id'), ['quote_id'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commandes générées par Alembic ###
    with op.batch_alter_table('quote_lines', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_quote_lines_quote_id'))
        batch_op.drop_index(batch_op.f('ix_quote_lines_dirty'))
        batch_op.drop_index(batch_op.f('ix_quote_lines_deleted'))
        batch_op.drop_index(batch_op.f('ix_quote_lines_agency_id'))

    op.drop_table('quote_lines')
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tasks_project_id'))
        batch_op.drop_index(batch_op.f('ix_tasks_dirty'))
        batch_op.drop_index(batch_op.f('ix_tasks_deleted'))
        batch_op.drop_index(batch_op.f('ix_tasks_agency_id'))

    op.drop_table('tasks')
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_quotes_project_id'))
        batch_op.drop_index(batch_op.f('ix_quotes_lot_id'))
        batch_op.drop_index(batch_op.f('ix_quotes_dirty'))
        batch_op.drop_index(batch_op.f('ix_quotes_deleted'))
        batch_op.drop_index(batch_op.f('ix_quotes_agency_id'))

    op.drop_table('quotes')
    with op.batch_alter_table('lots', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lots_project_id'))
        batch_op.drop_index(batch_op.f('ix_lots_dirty'))
        batch_op.drop_index(batch_op.f('ix_lots_deleted'))
        batch_op.drop_index(batch_op.f('ix_lots_agency_id'))

    op.drop_table('lots')
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_incidents_project_id'))
        batch_op.drop_index(batch_op.f('ix_incidents_dirty'))
        batch_op.drop_index(batch_op.f('ix_incidents_deleted'))
        batch_op.drop_index(batch_op.f('ix_incidents_agency_id'))

    op.drop_table('incidents')
    with op.batch_alter_table('dpgf_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_dpgf_items_project_id'))
        batch_op.drop_index(batch_op.f('ix_dpgf_items_lot_id'))
        batch_op.drop_index(batch_op.f('ix_dpgf_items_dirty'))
        batch_op.drop_index(batch_op.f('ix_dpgf_items_deleted'))
        batch_op.drop_index(batch_op.f('ix_dpgf_items_agency_id'))

    op.drop_table('dpgf_items')
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_projects_dirty'))
        batch_op.drop_index(batch_op.f('ix_projects_deleted'))
        batch_op.drop_index(batch_op.f('ix_projects_agency_id'))

    op.drop_table('projects')
    with op.batch_alter_table('document_versions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_document_versions_document_id'))
        batch_op.drop_index(batch_op.f('ix_document_versions_dirty'))
        batch_op.drop_index(batch_op.f('ix_document_versions_deleted'))
        batch_op.drop_index(batch_op.f('ix_document_versions_agency_id'))

    op.drop_table('document_versions')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_dirty'))
        batch_op.drop_index(batch_op.f('ix_users_deleted'))
        batch_op.drop_index(batch_op.f('ix_users_agency_id'))

    op.drop_table('users')
    with op.batch_alter_table('sync_conflicts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sync_conflicts_agency_id'))

    op.drop_table('sync_conflicts')
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_settings_agency_id'))

    op.drop_table('settings')
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_reports_project_id'))
        batch_op.drop_index(batch_op.f('ix_reports_dirty'))
        batch_op.drop_index(batch_op.f('ix_reports_deleted'))
        batch_op.drop_index(batch_op.f('ix_reports_agency_id'))

    op.drop_table('reports')
    with op.batch_alter_table('proposals', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_proposals_project_id'))
        batch_op.drop_index(batch_op.f('ix_proposals_dirty'))
        batch_op.drop_index(batch_op.f('ix_proposals_deleted'))
        batch_op.drop_index(batch_op.f('ix_proposals_agency_id'))

    op.drop_table('proposals')
    with op.batch_alter_table('parcel_analyses', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_parcel_analyses_project_id'))
        batch_op.drop_index(batch_op.f('ix_parcel_analyses_dirty'))
        batch_op.drop_index(batch_op.f('ix_parcel_analyses_deleted'))
        batch_op.drop_index(batch_op.f('ix_parcel_analyses_agency_id'))

    op.drop_table('parcel_analyses')
    with op.batch_alter_table('finance_entries', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_finance_entries_project_id'))
        batch_op.drop_index(batch_op.f('ix_finance_entries_dirty'))
        batch_op.drop_index(batch_op.f('ix_finance_entries_deleted'))
        batch_op.drop_index(batch_op.f('ix_finance_entries_agency_id'))

    op.drop_table('finance_entries')
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_events_start'))
        batch_op.drop_index(batch_op.f('ix_events_project_id'))
        batch_op.drop_index(batch_op.f('ix_events_dirty'))
        batch_op.drop_index(batch_op.f('ix_events_deleted'))
        batch_op.drop_index(batch_op.f('ix_events_agency_id'))

    op.drop_table('events')
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_documents_project_id'))
        batch_op.drop_index(batch_op.f('ix_documents_dirty'))
        batch_op.drop_index(batch_op.f('ix_documents_deleted'))
        batch_op.drop_index(batch_op.f('ix_documents_agency_id'))

    op.drop_table('documents')
    with op.batch_alter_table('document_chunks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_document_chunks_project_id'))
        batch_op.drop_index(batch_op.f('ix_document_chunks_document_id'))
        batch_op.drop_index(batch_op.f('ix_document_chunks_agency_id'))

    op.drop_table('document_chunks')
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_conversations_user_id'))
        batch_op.drop_index(batch_op.f('ix_conversations_dirty'))
        batch_op.drop_index(batch_op.f('ix_conversations_deleted'))
        batch_op.drop_index(batch_op.f('ix_conversations_agency_id'))

    op.drop_table('conversations')
    with op.batch_alter_table('comparisons', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_comparisons_project_id'))
        batch_op.drop_index(batch_op.f('ix_comparisons_dirty'))
        batch_op.drop_index(batch_op.f('ix_comparisons_deleted'))
        batch_op.drop_index(batch_op.f('ix_comparisons_agency_id'))

    op.drop_table('comparisons')
    with op.batch_alter_table('companies', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_companies_dirty'))
        batch_op.drop_index(batch_op.f('ix_companies_deleted'))
        batch_op.drop_index(batch_op.f('ix_companies_agency_id'))

    op.drop_table('companies')
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_clients_dirty'))
        batch_op.drop_index(batch_op.f('ix_clients_deleted'))
        batch_op.drop_index(batch_op.f('ix_clients_agency_id'))

    op.drop_table('clients')
    with op.batch_alter_table('change_log', schema=None) as batch_op:
        batch_op.drop_index('ix_change_log_entity')
        batch_op.drop_index(batch_op.f('ix_change_log_agency_id'))

    op.drop_table('change_log')
    with op.batch_alter_table('cctp_requirements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cctp_requirements_project_id'))
        batch_op.drop_index(batch_op.f('ix_cctp_requirements_dirty'))
        batch_op.drop_index(batch_op.f('ix_cctp_requirements_deleted'))
        batch_op.drop_index(batch_op.f('ix_cctp_requirements_agency_id'))

    op.drop_table('cctp_requirements')
    with op.batch_alter_table('budget_lines', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_budget_lines_project_id'))
        batch_op.drop_index(batch_op.f('ix_budget_lines_dirty'))
        batch_op.drop_index(batch_op.f('ix_budget_lines_deleted'))
        batch_op.drop_index(batch_op.f('ix_budget_lines_agency_id'))

    op.drop_table('budget_lines')
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_logs_at'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_agency_id'))

    op.drop_table('audit_logs')
    op.drop_table('agencies')
    # ### end Alembic commands ###
