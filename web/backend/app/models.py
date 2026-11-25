"""Modèles de données Archipel41.

Toutes les entités métier héritent de `SyncMixin` :
- `id` UUID texte (généré côté client ou serveur, stable entre appareils) ;
- `agency_id` : isolation stricte des données par agence ;
- `version` : révision incrémentée à chaque modification (concurrence optimiste) ;
- `deleted` : suppression logique (propagée par la synchronisation) ;
- `dirty` / `base_version` : état de synchronisation (utilisé uniquement en mode bureau).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, Embedding, JSONType, UTCDateTime, new_id, utcnow


class SyncMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Synchronisation (mode bureau)
    dirty: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    base_version: Mapped[int] = mapped_column(Integer, default=0)


# --------------------------------------------------------------------------- Agence & utilisateurs
class Agency(Base):
    __tablename__ = "agencies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    siret: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1)


class User(SyncMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)
    email: Mapped[str] = mapped_column(String(200))
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="member")  # admin|manager|member|viewer
    password_hash: Mapped[str] = mapped_column(String(300))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferences: Mapped[dict] = mapped_column(JSONType, default=dict)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


# --------------------------------------------------------------------------- Clients & entreprises
class Client(SyncMixin, Base):
    __tablename__ = "clients"
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30), default="particulier")  # particulier|entreprise|collectivite|promoteur
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    siret: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contacts: Mapped[list] = mapped_column(JSONType, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    history: Mapped[list] = mapped_column(JSONType, default=list)


class Company(SyncMixin, Base):
    __tablename__ = "companies"
    name: Mapped[str] = mapped_column(String(200))
    siret: Mapped[str | None] = mapped_column(String(20), nullable=True)
    specialties: Mapped[list] = mapped_column(JSONType, default=list)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contacts: Mapped[list] = mapped_column(JSONType, default=list)
    insurance: Mapped[str | None] = mapped_column(String(300), nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    history: Mapped[list] = mapped_column(JSONType, default=list)


# --------------------------------------------------------------------------- Projets
class Project(SyncMixin, Base):
    __tablename__ = "projects"
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    client_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("clients.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    program: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="etude")  # etude|consultation|chantier|reception|archive
    phases: Mapped[list] = mapped_column(JSONType, default=list)
    current_phase: Mapped[str | None] = mapped_column(String(20), nullable=True)
    team: Mapped[list] = mapped_column(JSONType, default=list)  # [{user_id, role}]
    terrain: Mapped[dict] = mapped_column(JSONType, default=dict)
    surface_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_initial: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    fee_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    confidential: Mapped[bool] = mapped_column(Boolean, default=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)


class Lot(SyncMixin, Base):
    __tablename__ = "lots"
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("companies.id"), nullable=True)
    budget: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    contract_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="a_consulter")  # a_consulter|consultation|attribue|en_cours|receptionne
    progress: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Incident(SyncMixin, Base):
    __tablename__ = "incidents"
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    lot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    company_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    date: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="moyenne")  # faible|moyenne|haute|critique
    status: Mapped[str] = mapped_column(String(20), default="ouvert")  # ouvert|en_cours|clos
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)


# --------------------------------------------------------------------------- Planning
class Task(SyncMixin, Base):
    __tablename__ = "tasks"
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="chantier")  # chantier|etude|administratif|todo
    start_date: Mapped[date] = mapped_column(Date)
    duration_days: Mapped[int] = mapped_column(Integer, default=1)
    milestone: Mapped[bool] = mapped_column(Boolean, default=False)
    depends_on: Mapped[list] = mapped_column(JSONType, default=list)
    responsible_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    company_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    activity: Mapped[str] = mapped_column(String(30), default="autre")
    priority: Mapped[str] = mapped_column(String(10), default="normale")  # basse|normale|haute
    baseline_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    baseline_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Proposal(SyncMixin, Base):
    """Proposition d'ajustement (météo, IA…) soumise à validation humaine."""

    __tablename__ = "proposals"
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    source: Mapped[str] = mapped_column(String(30), default="meteo")
    kind: Mapped[str] = mapped_column(String(30), default="decaler_tache")
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="en_attente")  # en_attente|acceptee|refusee
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


# --------------------------------------------------------------------------- Agenda
class Event(SyncMixin, Base):
    __tablename__ = "events"
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30), default="rdv_client")  # rdv_client|reunion_entreprise|visite_chantier|interne|autre
    start: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    end: Mapped[datetime] = mapped_column(UTCDateTime)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    participants: Mapped[list] = mapped_column(JSONType, default=list)  # [{user_id?, name, email?}]
    reminder_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    minutes: Mapped[str | None] = mapped_column(Text, nullable=True)  # compte rendu
    document_ids: Mapped[list] = mapped_column(JSONType, default=list)
    organizer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


# --------------------------------------------------------------------------- Documents
class Document(SyncMixin, Base):
    __tablename__ = "documents"
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(40), default="autre")
    tags: Mapped[list] = mapped_column(JSONType, default=list)
    mime: Mapped[str | None] = mapped_column(String(120), nullable=True)
    extension: Mapped[str | None] = mapped_column(String(20), nullable=True)
    size: Mapped[int] = mapped_column(Integer, default=0)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    confidential: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_status: Mapped[str] = mapped_column(String(30), default="en_attente")  # en_attente|ok|ocr|vide|non_supporte|erreur
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    linked: Mapped[dict] = mapped_column(JSONType, default=dict)  # {company_id, client_id, event_id, quote_id}


class DocumentVersion(SyncMixin, Base):
    __tablename__ = "document_versions"
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(300))
    storage_key: Mapped[str] = mapped_column(String(300))
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_synced: Mapped[bool] = mapped_column(Boolean, default=True)


class DocumentChunk(Base):
    """Index RAG (non synchronisé : chaque base le reconstruit localement)."""

    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str] = mapped_column(String(36), index=True)
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    embedding_model: Mapped[str] = mapped_column(String(80))
    embedding = mapped_column(Embedding, nullable=True)
    confidential: Mapped[bool] = mapped_column(Boolean, default=False)


# --------------------------------------------------------------------------- Devis / DPGF
class Quote(SyncMixin, Base):
    __tablename__ = "quotes"
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    lot_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    company_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    company_name_raw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quote_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    validity_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="a_verifier")  # a_verifier|valide|retenu|rejete
    delay_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    delay_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    conditions: Mapped[list] = mapped_column(JSONType, default=list)
    exclusions: Mapped[list] = mapped_column(JSONType, default=list)
    reserves: Mapped[list] = mapped_column(JSONType, default=list)
    variants: Mapped[list] = mapped_column(JSONType, default=list)
    declared_ht: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    declared_tva: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    declared_ttc: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    computed: Mapped[dict] = mapped_column(JSONType, default=dict)
    anomalies: Mapped[list] = mapped_column(JSONType, default=list)
    extraction: Mapped[dict] = mapped_column(JSONType, default=dict)
    validated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class QuoteLine(SyncMixin, Base):
    __tablename__ = "quote_lines"
    quote_id: Mapped[str] = mapped_column(String(36), ForeignKey("quotes.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    section: Mapped[str | None] = mapped_column(String(200), nullable=True)
    code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    designation: Mapped[str] = mapped_column(Text)
    quantity: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unit_price: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    total_ht: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    vat_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="inclus")  # inclus|exclu|optionnel|variante|a_verifier
    dpgf_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected: Mapped[bool] = mapped_column(Boolean, default=False)


class DpgfItem(SyncMixin, Base):
    __tablename__ = "dpgf_items"
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    lot_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    section: Mapped[str | None] = mapped_column(String(200), nullable=True)
    designation: Mapped[str] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    estimated_unit_price: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    cctp_ref: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class CctpRequirement(SyncMixin, Base):
    __tablename__ = "cctp_requirements"
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    lot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    article: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list] = mapped_column(JSONType, default=list)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Comparison(SyncMixin, Base):
    __tablename__ = "comparisons"
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    lot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    quote_ids: Mapped[list] = mapped_column(JSONType, default=list)
    result: Mapped[dict] = mapped_column(JSONType, default=dict)
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    conclusion_source: Mapped[str | None] = mapped_column(String(40), nullable=True)


# --------------------------------------------------------------------------- Finances
class BudgetLine(SyncMixin, Base):
    __tablename__ = "budget_lines"
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    lot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    label: Mapped[str] = mapped_column(String(200))
    initial_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    current_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class FinanceEntry(SyncMixin, Base):
    __tablename__ = "finance_entries"
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    lot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    company_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    quote_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))  # marche|travaux_supp|facture|acompte|situation|paiement|depense|honoraires
    label: Mapped[str] = mapped_column(String(200))
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entry_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount_ht: Mapped[float] = mapped_column(Numeric(14, 2))
    vat_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=20)
    amount_ttc: Mapped[float] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(20), default="prevu")  # prevu|emis|valide|paye|annule
    situation_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


# --------------------------------------------------------------------------- Urbanisme
class ParcelAnalysis(SyncMixin, Base):
    __tablename__ = "parcel_analyses"
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    query_type: Mapped[str] = mapped_column(String(20))  # adresse|cadastre|coordonnees
    query: Mapped[str] = mapped_column(String(300))
    label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    insee: Mapped[str | None] = mapped_column(String(10), nullable=True)
    section: Mapped[str | None] = mapped_column(String(10), nullable=True)
    numero: Mapped[str | None] = mapped_column(String(10), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    results: Mapped[dict] = mapped_column(JSONType, default=dict)
    rules: Mapped[dict] = mapped_column(JSONType, default=dict)
    sources: Mapped[list] = mapped_column(JSONType, default=list)
    unavailable: Mapped[list] = mapped_column(JSONType, default=list)
    mode: Mapped[str] = mapped_column(String(20), default="reel")  # reel|demo


# --------------------------------------------------------------------------- Rapports, IA
class Report(SyncMixin, Base):
    __tablename__ = "reports"
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(300))
    fmt: Mapped[str] = mapped_column(String(10))
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    params: Mapped[dict] = mapped_column(JSONType, default=dict)


class Conversation(SyncMixin, Base):
    __tablename__ = "conversations"
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    messages: Mapped[list] = mapped_column(JSONType, default=list)


# --------------------------------------------------------------------------- Système
class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("agency_id", "key", name="uq_settings_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str] = mapped_column(String(36), index=True)
    key: Mapped[str] = mapped_column(String(80))
    value: Mapped[dict] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    action: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(60), nullable=True)


class ChangeLog(Base):
    """Journal des modifications (historique + curseur de synchronisation)."""

    __tablename__ = "change_log"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency_id: Mapped[str] = mapped_column(String(36), index=True)
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer)
    op: Mapped[str] = mapped_column(String(10))  # create|update|delete
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    changes: Mapped[dict | None] = mapped_column(JSONType, nullable=True)


Index("ix_change_log_entity", ChangeLog.entity, ChangeLog.entity_id)


class SyncConflict(Base):
    __tablename__ = "sync_conflicts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str] = mapped_column(String(36), index=True)
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    local_data: Mapped[dict] = mapped_column(JSONType)
    remote_data: Mapped[dict] = mapped_column(JSONType)
    local_version: Mapped[int] = mapped_column(Integer)
    remote_version: Mapped[int] = mapped_column(Integer)
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(20), default="ouvert")  # ouvert|resolu
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


# Entités synchronisées, dans l'ordre de dépendance (clés étrangères).
SYNC_MODELS: dict[str, type] = {
    "users": User,
    "clients": Client,
    "companies": Company,
    "projects": Project,
    "lots": Lot,
    "incidents": Incident,
    "tasks": Task,
    "proposals": Proposal,
    "events": Event,
    "documents": Document,
    "document_versions": DocumentVersion,
    "quotes": Quote,
    "quote_lines": QuoteLine,
    "dpgf_items": DpgfItem,
    "cctp_requirements": CctpRequirement,
    "comparisons": Comparison,
    "budget_lines": BudgetLine,
    "finance_entries": FinanceEntry,
    "parcel_analyses": ParcelAnalysis,
    "reports": Report,
    "conversations": Conversation,
}
