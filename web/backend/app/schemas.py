"""Schémas Pydantic : validation stricte des formulaires côté serveur."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

PHASE_CODES = ["ESQ", "APS", "APD", "PC", "PRO", "DCE", "ACT", "EXE/VISA", "DET", "AOR"]
PHASE_LABELS = {
    "ESQ": "Esquisse",
    "APS": "Avant-projet sommaire",
    "APD": "Avant-projet définitif",
    "PC": "Permis de construire",
    "PRO": "Projet",
    "DCE": "Dossier de consultation des entreprises",
    "ACT": "Assistance aux contrats de travaux",
    "EXE/VISA": "Études d'exécution / Visa",
    "DET": "Direction de l'exécution des travaux",
    "AOR": "Assistance aux opérations de réception",
}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _non_empty(v: str) -> str:
    if v is None or not str(v).strip():
        raise ValueError("Champ obligatoire.")
    return v


# ---------------------------------------------------------------- contacts / sous-objets
class Contact(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = ""
    role: str | None = None
    email: str | None = None
    phone: str | None = None


class Phase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code: str
    label: str | None = None
    enabled: bool = True
    start: date | None = None
    end: date | None = None
    status: Literal["a_venir", "en_cours", "terminee"] = "a_venir"
    progress: int = Field(0, ge=0, le=100)
    fee_share: float | None = None


class TeamMember(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    role: str | None = None


class Participant(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str | None = None
    name: str = ""
    email: str | None = None


# ---------------------------------------------------------------- Clients
class ClientIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["particulier", "entreprise", "collectivite", "promoteur"] = "particulier"
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=300)
    postal_code: str | None = Field(None, max_length=10)
    city: str | None = Field(None, max_length=120)
    siret: str | None = Field(None, max_length=20)
    contacts: list[Contact] = []
    notes: str | None = None
    history: list[dict] = []

    @field_validator("email", mode="before")
    @classmethod
    def empty_email(cls, v):
        return v or None

    @field_validator("siret")
    @classmethod
    def siret_ok(cls, v):
        if v:
            digits = v.replace(" ", "")
            if not digits.isdigit() or len(digits) != 14:
                raise ValueError("Le SIRET doit comporter 14 chiffres.")
            return digits
        return v


class CompanyIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    siret: str | None = Field(None, max_length=20)
    specialties: list[str] = []
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=300)
    postal_code: str | None = Field(None, max_length=10)
    city: str | None = Field(None, max_length=120)
    contacts: list[Contact] = []
    insurance: str | None = None
    rating: int | None = Field(None, ge=1, le=5)
    notes: str | None = None
    history: list[dict] = []

    _empty_email = field_validator("email", mode="before")(lambda cls, v: v or None)
    _siret = field_validator("siret")(ClientIn.siret_ok.__func__)


# ---------------------------------------------------------------- Projets
class ProjectIn(Strict):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    client_id: str | None = None
    description: str | None = None
    program: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=300)
    postal_code: str | None = Field(None, max_length=10)
    city: str | None = Field(None, max_length=120)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    status: Literal["etude", "consultation", "chantier", "reception", "archive"] = "etude"
    phases: list[Phase] | None = None
    current_phase: str | None = None
    team: list[TeamMember] = []
    terrain: dict[str, Any] = {}
    surface_m2: float | None = Field(None, ge=0)
    budget_initial: float | None = Field(None, ge=0)
    fee_rate: float | None = Field(None, ge=0, le=100)
    start_date: date | None = None
    end_date: date | None = None
    progress: int = Field(0, ge=0, le=100)
    confidential: bool = False
    color: str | None = None

    @model_validator(mode="after")
    def dates_ok(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("La date de fin doit être postérieure à la date de début.")
        return self


class LotIn(Strict):
    project_id: str
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    company_id: str | None = None
    budget: float | None = Field(None, ge=0)
    contract_amount: float | None = Field(None, ge=0)
    status: Literal["a_consulter", "consultation", "attribue", "en_cours", "receptionne"] = "a_consulter"
    progress: int = Field(0, ge=0, le=100)
    notes: str | None = None


class IncidentIn(Strict):
    project_id: str
    lot_id: str | None = None
    company_id: str | None = None
    date: date
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    severity: Literal["faible", "moyenne", "haute", "critique"] = "moyenne"
    status: Literal["ouvert", "en_cours", "clos"] = "ouvert"
    resolution: str | None = None


# ---------------------------------------------------------------- Planning
ACTIVITIES = [
    "terrassement", "fondations", "beton", "maconnerie", "charpente", "couverture",
    "etancheite", "facade", "peinture_ext", "menuiseries_ext", "vrd", "grue",
    "interieur", "second_oeuvre", "autre",
]


class TaskIn(Strict):
    project_id: str
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["chantier", "etude", "administratif", "todo"] = "chantier"
    start_date: date
    duration_days: int = Field(1, ge=0, le=3650)
    milestone: bool = False
    depends_on: list[str] = []
    responsible_id: str | None = None
    company_id: str | None = None
    lot_id: str | None = None
    progress: int = Field(0, ge=0, le=100)
    activity: str = "autre"
    priority: Literal["basse", "normale", "haute"] = "normale"
    baseline_start: date | None = None
    baseline_end: date | None = None
    notes: str | None = None

    @field_validator("activity")
    @classmethod
    def act(cls, v):
        if v not in ACTIVITIES:
            raise ValueError("Type d'activité inconnu.")
        return v


# ---------------------------------------------------------------- Agenda
class EventIn(Strict):
    title: str = Field(min_length=1, max_length=200)
    kind: Literal["rdv_client", "reunion_entreprise", "visite_chantier", "interne", "autre"] = "rdv_client"
    start: datetime
    end: datetime
    all_day: bool = False
    location: str | None = Field(None, max_length=300)
    project_id: str | None = None
    participants: list[Participant] = []
    reminder_minutes: int | None = Field(None, ge=0, le=60 * 24 * 14)
    description: str | None = None
    minutes: str | None = None
    document_ids: list[str] = []
    organizer_id: str | None = None

    @model_validator(mode="after")
    def order(self):
        if self.end < self.start:
            raise ValueError("La fin du rendez-vous doit être postérieure à son début.")
        return self


# ---------------------------------------------------------------- Documents
DOC_CATEGORIES = [
    "plan", "devis", "cctp", "dpgf", "contrat", "facture", "compte_rendu", "photo",
    "administratif", "urbanisme", "maquette", "rapport", "courrier", "autre",
]


class DocumentPatch(Strict):
    name: str | None = Field(None, min_length=1, max_length=300)
    category: str | None = None
    tags: list[str] | None = None
    project_id: str | None = None
    confidential: bool | None = None
    description: str | None = None
    linked: dict | None = None

    @field_validator("category")
    @classmethod
    def cat(cls, v):
        if v is not None and v not in DOC_CATEGORIES:
            raise ValueError("Catégorie inconnue.")
        return v


# ---------------------------------------------------------------- Devis
LINE_STATUSES = ["inclus", "exclu", "optionnel", "variante", "a_verifier"]


class QuoteLineIn(Strict):
    quote_id: str
    position: int = 0
    section: str | None = None
    code: str | None = None
    designation: str = Field(min_length=1)
    quantity: float | None = None
    unit: str | None = Field(None, max_length=20)
    unit_price: float | None = None
    total_ht: float | None = None
    vat_rate: float | None = Field(None, ge=0, le=100)
    status: Literal["inclus", "exclu", "optionnel", "variante", "a_verifier"] = "inclus"
    dpgf_item_id: str | None = None
    confidence: float | None = None
    page: int | None = None
    raw: str | None = None
    corrected: bool = True


class QuoteIn(Strict):
    project_id: str
    lot_id: str | None = None
    company_id: str | None = None
    company_name_raw: str | None = None
    document_id: str | None = None
    reference: str | None = None
    quote_date: date | None = None
    validity_days: int | None = Field(None, ge=0)
    status: Literal["a_verifier", "valide", "retenu", "rejete"] = "a_verifier"
    delay_text: str | None = None
    delay_days: int | None = Field(None, ge=0)
    payment_terms: str | None = None
    conditions: list[str] = []
    exclusions: list[str] = []
    reserves: list[str] = []
    variants: list[str] = []
    declared_ht: float | None = None
    declared_tva: float | None = None
    declared_ttc: float | None = None
    notes: str | None = None


class DpgfItemIn(Strict):
    project_id: str
    lot_id: str | None = None
    position: int = 0
    code: str | None = None
    section: str | None = None
    designation: str = Field(min_length=1)
    unit: str | None = None
    quantity: float | None = None
    estimated_unit_price: float | None = None
    cctp_ref: str | None = None
    source_document_id: str | None = None


# ---------------------------------------------------------------- Finances
class BudgetLineIn(Strict):
    project_id: str
    lot_id: str | None = None
    label: str = Field(min_length=1, max_length=200)
    initial_amount: float = 0
    current_amount: float = 0
    notes: str | None = None


FINANCE_KINDS = ["marche", "travaux_supp", "facture", "acompte", "situation", "paiement", "depense", "honoraires"]


class FinanceEntryIn(Strict):
    project_id: str
    lot_id: str | None = None
    company_id: str | None = None
    quote_id: str | None = None
    kind: Literal["marche", "travaux_supp", "facture", "acompte", "situation", "paiement", "depense", "honoraires"]
    label: str = Field(min_length=1, max_length=200)
    reference: str | None = None
    entry_date: date
    due_date: date | None = None
    amount_ht: float
    vat_rate: float = Field(20, ge=0, le=100)
    amount_ttc: float | None = None
    status: Literal["prevu", "emis", "valide", "paye", "annule"] = "prevu"
    situation_number: int | None = None
    progress_percent: float | None = Field(None, ge=0, le=100)
    notes: str | None = None

    @model_validator(mode="after")
    def compute_ttc(self):
        # Le TTC est toujours recalculé par le moteur déterministe (arrondi commercial au centime)
        from ai.document_analysis.calc import ttc_from_ht

        self.amount_ttc = ttc_from_ht(self.amount_ht, self.vat_rate)
        return self


class ProposalIn(Strict):
    project_id: str
    source: str = "manuel"
    kind: str = "decaler_tache"
    target_id: str | None = None
    payload: dict = {}
    reason: str


# ---------------------------------------------------------------- Utilisateurs
class UserCreate(Strict):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    role: Literal["admin", "manager", "member", "viewer"] = "member"
    password: str
    job_title: str | None = None
    phone: str | None = None
    color: str | None = None


class UserUpdate(Strict):
    full_name: str | None = Field(None, min_length=1, max_length=200)
    role: Literal["admin", "manager", "member", "viewer"] | None = None
    active: bool | None = None
    job_title: str | None = None
    phone: str | None = None
    color: str | None = None
    password: str | None = None
    preferences: dict | None = None
    version: int | None = None


class LoginIn(BaseModel):
    email: str
    password: str


class SetupIn(Strict):
    agency_name: str = Field(min_length=1, max_length=200)
    agency_siret: str | None = None
    agency_address: str | None = None
    admin_email: EmailStr
    admin_name: str = Field(min_length=1)
    admin_password: str
