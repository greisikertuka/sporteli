"""Catalog: the single source of truth for datasets, fields, synonyms, owners and parsing.

Everything user-facing is an L10n dict ``{"sq": ..., "en": ...}``. Owners are role-based
placeholders; replace their names with the ones confirmed at the municipal desk.

Parsing helpers here are shared by ingest (coercion), indicators (formatting) and the copilot
(routing), so Albanian dates, month names, numbers and admin-unit spellings are handled the
same way everywhere.
"""

from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

L10n = dict[str, str]
FieldType = Literal["string", "date", "int", "float"]


def t(sq: str, en: str) -> L10n:
    """Build an L10n dict."""
    return {"sq": sq, "en": en}


# --------------------------------------------------------------------------------------------
# Owners, areas, units, population bases
# --------------------------------------------------------------------------------------------

OWNERS: dict[str, L10n] = {
    "citizen_relations": t("Sektori i Marrëdhënieve me Qytetarët", "Citizen Relations Sector"),
    "finance": t("Drejtoria e Financës dhe Buxhetit", "Finance and Budget Directorate"),
    "public_services": t("Drejtoria e Shërbimeve Publike", "Public Services Directorate"),
    "local_revenue": t("Drejtoria e të Ardhurave Vendore", "Local Revenue Directorate"),
    "hr": t("Drejtoria e Burimeve Njerëzore", "Human Resources Directorate"),
    "statistics": t("Sektori i Statistikës dhe Performancës", "Statistics and Performance Sector"),
}


def owner(key: str) -> dict:
    """Owner in the API shape ``{"key": ..., "name": L10n}``."""
    return {"key": key, "name": dict(OWNERS[key])}


AREAS: dict[str, L10n] = {
    "requests": t("Kërkesat qytetare", "Citizen requests"),
    "finance": t("Financat", "Finance"),
    "waste": t("Mbetjet", "Waste"),
    "revenue": t("Të ardhurat vendore", "Local revenue"),
    "hr": t("Burimet njerëzore", "Human resources"),
}


def area(key: str) -> dict:
    """Area in the API shape ``{"key": ..., "name": L10n}``."""
    return {"key": key, "name": dict(AREAS[key])}


UNIT_LABELS: dict[str, L10n] = {
    "count": t("numër", "count"),
    "percent": t("%", "%"),
    "days": t("ditë", "days"),
    "kg_per_resident": t("kg/banor/vit", "kg/resident/year"),
    "lek_per_ton": t("lekë/ton", "lek/tonne"),
    "per_1000": t("për 1.000 banorë", "per 1,000 residents"),
}

POPULATION_BASES: dict[str, L10n] = {
    "census_2023": t("Censusi 2023", "Census 2023"),
    "civil_registry": t("Regjistri civil", "Civil registry"),
}
DEFAULT_POPULATION_BASIS = "census_2023"

SYNTHETIC_BADGE: L10n = t("Të dhëna sintetike", "Synthetic data")

WASTE_PROGRAMME_CODE = "05100"
"""Budget programme (national functional code) for waste management; used by WST-03/REV-02."""

CLEANING_FEE_PATTERN = "pastrim"
"""Normalised substring that identifies the cleaning fee in ``revenue.revenue_type``."""


# --------------------------------------------------------------------------------------------
# Text normalisation
# --------------------------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w]+", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def strip_diacritics(text: str) -> str:
    """Remove combining marks: ë→e, ç→c (keeps case)."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_text(value: object) -> str:
    """Casefold, strip diacritics, turn punctuation/underscores into spaces, collapse spaces.

    >>> normalize_text("  Njësia   Administrative (NJA) ")
    'njesia administrative nja'
    """
    if value is None:
        return ""
    text = strip_diacritics(str(value)).casefold()
    text = _PUNCT_RE.sub(" ", text).replace("_", " ")
    return _SPACE_RE.sub(" ", text).strip()


_PAREN_RE = re.compile(r"\([^)]*\)|\[[^\]]*\]")


def header_key(value: object) -> str:
    """Normalised header without parenthesised notes such as units or dates.

    >>> header_key("Numri i punonjësve (31.08.2026)")
    'numri i punonjesve'
    """
    return normalize_text(_PAREN_RE.sub(" ", str(value or "")))


# --------------------------------------------------------------------------------------------
# Datasets and fields
# --------------------------------------------------------------------------------------------

Normalizer = Literal[
    "month", "date", "admin_unit", "line_type", "basis", "programme_code", "status", "text"
]


@dataclass(frozen=True)
class Field:
    key: str
    type: FieldType
    required: bool
    label: L10n
    synonyms: tuple[str, ...]
    """Header phrasings (sq with and without diacritics, en). Compare with ``header_key``."""
    normalizer: Normalizer | None = None
    money: bool = False
    """Value in lek; the file's unit multiplier (e.g. 1,000 for "(000 lekë)") applies."""
    reconcile: bool = False
    """Sum is reconciled against the file's total row on load."""

    def api(self) -> dict:
        return {
            "key": self.key,
            "label": dict(self.label),
            "type": self.type,
            "required": self.required,
        }


@dataclass(frozen=True)
class Dataset:
    key: str
    table: str
    name: L10n
    owner: str
    fields: tuple[Field, ...]
    unlocks: tuple[str, ...]
    export_name: L10n
    """How the gap card names the missing export ("eksporti i ...")."""
    keywords: tuple[str, ...] = ()
    """Normalised topic keywords for copilot routing (no diacritics)."""
    sample_file: str | None = None
    reference: bool = False

    def field(self, key: str) -> Field:
        for f in self.fields:
            if f.key == key:
                return f
        raise KeyError(f"{self.key}.{key}")

    @property
    def field_keys(self) -> list[str]:
        return [f.key for f in self.fields]

    @property
    def required_fields(self) -> list[str]:
        return [f.key for f in self.fields if f.required]

    def api(self) -> dict:
        """Static part of ``DatasetInfo`` (loaded/sources/rows are added from the DB)."""
        return {
            "key": self.key,
            "name": dict(self.name),
            "owner": owner(self.owner),
            "table": self.table,
            "fields": [f.api() for f in self.fields],
            "unlocks": list(self.unlocks),
        }


def _month_field(required: bool = True) -> Field:
    return Field(
        "month",
        "date",
        required,
        t("Muaji", "Month"),
        (
            "Muaji",
            "Muaj",
            "Periudha",
            "Periudha raportuese",
            "Data",
            "Viti muaji",
            "Muaji viti",
            "month",
            "period",
            "reporting month",
            "date",
        ),
        normalizer="month",
    )


def _admin_unit_field(required: bool) -> Field:
    return Field(
        "admin_unit",
        "string",
        required,
        t("Njësia administrative", "Administrative unit"),
        (
            "Njësia administrative",
            "Njesia administrative",
            "Njësia",
            "Njesia",
            "NJA",
            "Nj. administrative",
            "Njësi administrative",
            "Zona",
            "Territori",
            "administrative unit",
            "admin unit",
            "unit",
            "area",
            "district",
        ),
        normalizer="admin_unit",
    )


DATASETS: dict[str, Dataset] = {
    "requests": Dataset(
        key="requests",
        table="request",
        name=t("Kërkesat qytetare", "Citizen requests"),
        owner="citizen_relations",
        export_name=t("regjistri i kërkesave qytetare", "citizen requests register"),
        unlocks=("REQ-01", "REQ-02", "REQ-03", "REQ-04"),
        keywords=("kerkes", "ankes", "sportel", "request", "complaint", "ticket"),
        sample_file="01_SINTETIKE_kerkesat_qytetare_jan-gus_2026.xlsx",
        fields=(
            Field(
                "request_id",
                "string",
                True,
                t("Nr. i kërkesës", "Request no."),
                (
                    "Nr.",
                    "Nr",
                    "Numri",
                    "Nr. i kërkesës",
                    "Nr i kerkeses",
                    "Numri i kërkesës",
                    "Nr. protokolli",
                    "Nr protokolli",
                    "Kodi i kërkesës",
                    "ID",
                    "request id",
                    "request no",
                    "request number",
                    "case id",
                    "ticket id",
                ),
            ),
            Field(
                "created_at",
                "date",
                True,
                t("Data e regjistrimit", "Registration date"),
                (
                    "Data e regjistrimit",
                    "Data e regjistrimit të kërkesës",
                    "Data e kërkesës",
                    "Data e kerkeses",
                    "Data e krijimit",
                    "Data e paraqitjes",
                    "Regjistruar më",
                    "Data",
                    "created",
                    "created at",
                    "date created",
                    "registration date",
                    "submitted",
                    "date submitted",
                ),
                normalizer="date",
            ),
            Field(
                "closed_at",
                "date",
                False,
                t("Data e mbylljes", "Closing date"),
                (
                    "Data e mbylljes",
                    "Data e zgjidhjes",
                    "Data e përfundimit",
                    "Mbyllur më",
                    "Zgjidhur më",
                    "closed",
                    "closed at",
                    "date closed",
                    "resolution date",
                    "resolved on",
                ),
                normalizer="date",
            ),
            Field(
                "category",
                "string",
                True,
                t("Kategoria", "Category"),
                (
                    "Kategoria",
                    "Kategori",
                    "Lloji i kërkesës",
                    "Lloji i kerkeses",
                    "Tema",
                    "Problematika",
                    "Lloji",
                    "category",
                    "request type",
                    "type",
                    "topic",
                ),
                normalizer="text",
            ),
            Field(
                "department",
                "string",
                False,
                t("Drejtoria përgjegjëse", "Responsible directorate"),
                (
                    "Drejtoria përgjegjëse",
                    "Drejtoria pergjegjese",
                    "Drejtoria",
                    "Sektori përgjegjës",
                    "Njësia përgjegjëse",
                    "Struktura përgjegjëse",
                    "Përgjegjës",
                    "department",
                    "directorate",
                    "responsible department",
                    "assigned to",
                ),
                normalizer="text",
            ),
            _admin_unit_field(required=False),
            Field(
                "channel",
                "string",
                False,
                t("Kanali", "Channel"),
                (
                    "Kanali",
                    "Kanali i paraqitjes",
                    "Mënyra e paraqitjes",
                    "Menyra e paraqitjes",
                    "Mënyra e dorëzimit",
                    "channel",
                    "intake channel",
                    "submission channel",
                ),
                normalizer="text",
            ),
            Field(
                "status",
                "string",
                True,
                t("Statusi", "Status"),
                ("Statusi", "Status", "Gjendja", "Faza", "status", "state", "stage"),
                normalizer="status",
            ),
            Field(
                "sla_days",
                "int",
                False,
                t("Afati (ditë)", "Deadline (days)"),
                (
                    "Afati (ditë)",
                    "Afati",
                    "Afati ligjor",
                    "Afati në ditë",
                    "Ditë afat",
                    "Afati i zgjidhjes",
                    "SLA",
                    "SLA days",
                    "deadline",
                    "deadline days",
                    "days allowed",
                ),
            ),
        ),
    ),
    "budget": Dataset(
        key="budget",
        table="budget_line",
        name=t("Zbatimi i buxhetit", "Budget execution"),
        owner="finance",
        export_name=t("raporti i zbatimit të buxhetit", "budget execution report"),
        unlocks=("FIN-01", "FIN-02", "WST-03", "REV-02"),
        keywords=("buxhet", "shpenzim", "investim", "kapital", "budget", "spending", "capital"),
        sample_file="02_SINTETIKE_zbatimi_buxhetit_jan-gus_2026.xlsx",
        fields=(
            _month_field(),
            Field(
                "programme_code",
                "string",
                True,
                t("Kodi i programit", "Programme code"),
                (
                    "Kodi i programit",
                    "Kodi programit",
                    "Kodi",
                    "Kodi funksional",
                    "Nr. programi",
                    "Programi (kodi)",
                    "programme code",
                    "program code",
                    "functional code",
                    "code",
                ),
                normalizer="programme_code",
            ),
            Field(
                "programme",
                "string",
                False,
                t("Programi", "Programme"),
                (
                    "Programi",
                    "Emërtimi i programit",
                    "Emertimi i programit",
                    "Emërtimi",
                    "Përshkrimi",
                    "Programi buxhetor",
                    "programme",
                    "program",
                    "programme name",
                    "program name",
                ),
                normalizer="text",
            ),
            Field(
                "line_type",
                "string",
                False,
                t("Lloji i shpenzimit", "Expenditure type"),
                (
                    "Lloji i shpenzimit",
                    "Lloji i shpenzimeve",
                    "Kategoria e shpenzimit",
                    "Korrente/Kapitale",
                    "Natyra e shpenzimit",
                    "Lloji",
                    "expenditure type",
                    "spending type",
                    "line type",
                    "current capital",
                ),
                normalizer="line_type",
            ),
            Field(
                "planned_lek",
                "float",
                True,
                t("Plani (lekë)", "Planned (lek)"),
                (
                    "Plani",
                    "Plan",
                    "Plani vjetor",
                    "Buxheti i planifikuar",
                    "Parashikimi",
                    "Planifikuar",
                    "planned",
                    "plan",
                    "budgeted",
                    "budget",
                ),
                money=True,
                reconcile=True,
            ),
            Field(
                "actual_lek",
                "float",
                True,
                t("Fakti (lekë)", "Actual (lek)"),
                (
                    "Fakti",
                    "Fakt",
                    "Realizimi",
                    "Realizuar",
                    "Shpenzime faktike",
                    "Shpenzimi faktik",
                    "Zbatimi",
                    "actual",
                    "actual spending",
                    "spent",
                    "executed",
                ),
                money=True,
                reconcile=True,
            ),
        ),
    ),
    "waste": Dataset(
        key="waste",
        table="waste_collection",
        name=t("Pastrimi dhe mbetjet", "Cleaning and waste collection"),
        owner="public_services",
        export_name=t("eksporti i grumbullimit të mbetjeve", "waste collection export"),
        unlocks=("WST-01", "WST-02", "WST-03"),
        keywords=(
            "mbetje",
            "mbeturin",
            "pastrim",
            "plehra",
            "grumbullim",
            "waste",
            "garbage",
            "rubbish",
            "trash",
            "tonne",
        ),
        sample_file="zarfi-1_SINTETIKE_pastrimi_mbetjet_2026.csv",
        fields=(
            _month_field(),
            _admin_unit_field(required=True),
            Field(
                "tonnes",
                "float",
                True,
                t("Sasia (ton)", "Quantity (tonnes)"),
                (
                    "Sasia (ton)",
                    "Sasia",
                    "Tonazhi",
                    "Ton",
                    "Tonë",
                    "Mbetje (ton)",
                    "Sasia e mbetjeve",
                    "Sasia e grumbulluar",
                    "Pesha",
                    "tonnes",
                    "tons",
                    "tonnage",
                    "quantity",
                    "weight",
                ),
                reconcile=True,
            ),
            Field(
                "trips",
                "int",
                False,
                t("Nr. i kursimeve", "Collection trips"),
                (
                    "Nr. i kursimeve",
                    "Nr i kursimeve",
                    "Numri i kursimeve",
                    "Nr. i kurseve",
                    "Kurse",
                    "Nr. i udhëtimeve",
                    "Udhëtime",
                    "Nr. i xhirove",
                    "trips",
                    "collection trips",
                    "runs",
                ),
                reconcile=True,
            ),
            Field(
                "households_served",
                "int",
                False,
                t("Familje të mbuluara", "Households served"),
                (
                    "Familje të mbuluara",
                    "Familje te mbuluara",
                    "Familje",
                    "Numri i familjeve",
                    "Abonentë",
                    "Familje të shërbyera",
                    "households",
                    "households served",
                    "families served",
                ),
            ),
        ),
    ),
    "revenue": Dataset(
        key="revenue",
        table="revenue",
        name=t("Taksat dhe tarifat — arkëtimi", "Taxes and fees — collection"),
        owner="local_revenue",
        export_name=t(
            "eksporti i arkëtimit të taksave dhe tarifave", "tax and fee collection export"
        ),
        unlocks=("REV-01", "REV-02"),
        keywords=(
            "taks",
            "tarif",
            "arketim",
            "te ardhura",
            "pagues",
            "tax",
            "fee",
            "revenue",
            "collection",
        ),
        sample_file="zarfi-2_SINTETIKE_taksat_tarifat_arketimi_2026.xlsx",
        fields=(
            _month_field(),
            Field(
                "revenue_type",
                "string",
                True,
                t("Lloji i të ardhurës", "Revenue type"),
                (
                    "Lloji i të ardhurës",
                    "Lloji i te ardhures",
                    "Lloji i taksës",
                    "Taksa/Tarifa",
                    "Taksa / tarifa",
                    "Emërtimi i të ardhurës",
                    "Zëri",
                    "revenue type",
                    "tax type",
                    "revenue item",
                ),
                normalizer="text",
            ),
            Field(
                "payer_type",
                "string",
                False,
                t("Kategoria e paguesit", "Payer category"),
                (
                    "Kategoria e paguesit",
                    "Kategoria e paguesve",
                    "Paguesi",
                    "Lloji i paguesit",
                    "Familje/Biznes",
                    "payer type",
                    "payer category",
                    "taxpayer type",
                ),
                normalizer="text",
            ),
            Field(
                "planned_lek",
                "float",
                False,
                t("Plani (lekë)", "Planned (lek)"),
                (
                    "Plani",
                    "Plan",
                    "Parashikimi",
                    "Planifikuar",
                    "Detyrimi",
                    "planned",
                    "plan",
                    "forecast",
                    "assessed",
                ),
                money=True,
                reconcile=True,
            ),
            Field(
                "collected_lek",
                "float",
                True,
                t("Arkëtuar (lekë)", "Collected (lek)"),
                (
                    "Arkëtuar",
                    "Arketuar",
                    "Arkëtimi",
                    "Të arkëtuara",
                    "Shuma e arkëtuar",
                    "Realizimi",
                    "Fakti",
                    "collected",
                    "received",
                    "actual",
                ),
                money=True,
                reconcile=True,
            ),
        ),
    ),
    "staff": Dataset(
        key="staff",
        table="staff",
        name=t("Burimet njerëzore", "Human resources"),
        owner="hr",
        export_name=t("eksporti i burimeve njerëzore", "human resources export"),
        unlocks=("HR-01", "HR-02"),
        keywords=(
            "punonjes",
            "staf",
            "personel",
            "burime njerezore",
            "rotacion",
            "largime",
            "staff",
            "employee",
            "headcount",
            "turnover",
            "workforce",
        ),
        sample_file="zarfi-3_SINTETIKE_burimet_njerezore_2026.xlsx",
        fields=(
            Field(
                "department",
                "string",
                True,
                t("Drejtoria", "Directorate"),
                (
                    "Drejtoria",
                    "Drejtoria / njësia",
                    "Njësia organizative",
                    "Struktura",
                    "Sektori",
                    "department",
                    "directorate",
                    "organisational unit",
                ),
                normalizer="text",
            ),
            Field(
                "headcount",
                "int",
                True,
                t("Numri i punonjësve", "Headcount"),
                (
                    "Numri i punonjësve",
                    "Numri i punonjesve",
                    "Nr. punonjësve",
                    "Nr. i punonjësve",
                    "Punonjës",
                    "Efektivi",
                    "Numri i stafit",
                    "headcount",
                    "employees",
                    "staff count",
                    "number of employees",
                ),
                reconcile=True,
            ),
            Field(
                "hires",
                "int",
                False,
                t("Pranime", "Hires"),
                (
                    "Pranime",
                    "Pranime në punë",
                    "Punësime të reja",
                    "Emërime",
                    "hires",
                    "new hires",
                    "joiners",
                ),
                reconcile=True,
            ),
            Field(
                "leavers",
                "int",
                False,
                t("Largime", "Leavers"),
                (
                    "Largime",
                    "Largime nga puna",
                    "Ndërprerje",
                    "Lirime",
                    "Dorëheqje",
                    "leavers",
                    "departures",
                    "exits",
                    "separations",
                ),
                reconcile=True,
            ),
            Field(
                "as_of",
                "date",
                False,
                t("Data e gjendjes", "As of date"),
                (
                    "Data e gjendjes",
                    "Gjendja më",
                    "Më datë",
                    "Data e raportimit",
                    "Data",
                    "as of",
                    "snapshot date",
                    "reporting date",
                ),
                normalizer="date",
            ),
        ),
    ),
    "population": Dataset(
        key="population",
        table="population",
        name=t("Popullsia sipas njësive administrative", "Population by administrative unit"),
        owner="statistics",
        export_name=t("tabela e popullsisë", "population reference table"),
        unlocks=("WST-02", "HR-01"),
        keywords=("popullsi", "banore", "population", "resident", "census", "censusi"),
        sample_file="ref_SINTETIKE_popullsia_njesite.csv",
        reference=True,
        fields=(
            _admin_unit_field(required=True),
            Field(
                "basis",
                "string",
                True,
                t("Baza", "Basis"),
                ("Baza", "Burimi", "Burimi i të dhënave", "Baza e popullsisë", "basis", "source"),
                normalizer="basis",
            ),
            Field(
                "residents",
                "int",
                True,
                t("Banorë", "Residents"),
                (
                    "Banorë",
                    "Banore",
                    "Popullsia",
                    "Numri i banorëve",
                    "Nr. banorësh",
                    "residents",
                    "population",
                    "inhabitants",
                ),
            ),
        ),
    ),
}

FACT_TABLES: tuple[str, ...] = tuple(d.table for d in DATASETS.values())


def get_dataset(key: str) -> Dataset:
    try:
        return DATASETS[key]
    except KeyError as exc:
        raise KeyError(f"unknown dataset: {key}") from exc


def dataset_for_table(table: str) -> Dataset:
    for d in DATASETS.values():
        if d.table == table:
            return d
    raise KeyError(f"unknown table: {table}")


def datasets_for_topic(text: str) -> list[str]:
    """Dataset keys whose topic keywords appear in ``text`` (diacritic-insensitive)."""
    norm = f" {normalize_text(text)} "
    hits = []
    for d in DATASETS.values():
        if any(f" {kw}" in norm for kw in d.keywords):
            hits.append(d.key)
    return hits


# --------------------------------------------------------------------------------------------
# Administrative units
# --------------------------------------------------------------------------------------------

ADMIN_UNITS: tuple[str, ...] = (
    "Elbasan",
    "Bradashesh",
    "Funarë",
    "Gjergjan",
    "Gjinar",
    "Gracen",
    "Labinot-Fushë",
    "Labinot-Mal",
    "Papër",
    "Shirgjan",
    "Shushicë",
    "Tregan",
    "Zavalinë",
)

_EXTRA_ADMIN_VARIANTS: dict[str, str] = {
    "elbasan qyteti": "Elbasan",
    "elbasan qytet": "Elbasan",
    "qyteti elbasan": "Elbasan",
    "qyteti i elbasanit": "Elbasan",
    "elbasani": "Elbasan",
    "qyteti": "Elbasan",
    "bashkia elbasan": "Elbasan",
    "fushe labinot": "Labinot-Fushë",
    "labinot fushe": "Labinot-Fushë",
    "labinot fusha": "Labinot-Fushë",
    "labinoti fushe": "Labinot-Fushë",
    "labinot mal": "Labinot-Mal",
    "labinot mali": "Labinot-Mal",
    "labinoti mal": "Labinot-Mal",
    "papri": "Papër",
    "papra": "Papër",
    "funara": "Funarë",
    "shushica": "Shushicë",
    "zavalina": "Zavalinë",
}

_ADMIN_PREFIX_RE = re.compile(r"^(njesia administrative|njesia|nj a|nja|na|komuna)\s+")


def _build_admin_variants() -> dict[str, str]:
    variants: dict[str, str] = {}
    for name in ADMIN_UNITS:
        n = normalize_text(name)
        variants[n] = name
        variants[n + "i"] = name  # definite form: Shirgjani, Tregani, Gjinari
        if n.endswith("e"):
            variants[n[:-1] + "a"] = name  # Funara, Shushica, Zavalina
    variants.update(_EXTRA_ADMIN_VARIANTS)
    return variants


ADMIN_UNIT_VARIANTS: dict[str, str] = _build_admin_variants()


def match_admin_unit(value: object) -> str | None:
    """Canonical admin-unit name for a spelling variant, or None if it is not recognised."""
    n = normalize_text(value)
    if not n:
        return None
    n = _ADMIN_PREFIX_RE.sub("", n)
    if n in ADMIN_UNIT_VARIANTS:
        return ADMIN_UNIT_VARIANTS[n]
    compact = n.replace(" ", "")
    for key, name in ADMIN_UNIT_VARIANTS.items():
        if key.replace(" ", "") == compact:
            return name
    return None


def normalize_admin_unit(value: object) -> str | None:
    """Canonical admin-unit name; unknown values are kept (trimmed) so no data is lost.

    >>> normalize_admin_unit(" Shirgjani ")
    'Shirgjan'
    >>> normalize_admin_unit("labinot fushe")
    'Labinot-Fushë'
    """
    if value is None:
        return None
    raw = _SPACE_RE.sub(" ", str(value)).strip()
    if not raw:
        return None
    return match_admin_unit(raw) or raw


# --------------------------------------------------------------------------------------------
# Value normalisers for coded columns
# --------------------------------------------------------------------------------------------


def normalize_line_type(value: object) -> str | None:
    """'Korrente' → 'current', 'Kapitale'/'Investime' → 'capital'; unknown kept as-is."""
    n = normalize_text(value)
    if not n:
        return None
    if n.startswith(("kapital", "capital", "invest")):
        return "capital"
    if n.startswith(("korent", "korrent", "current", "operativ", "recurrent")):
        return "current"
    return str(value).strip()


def normalize_basis(value: object) -> str | None:
    """Population basis label → ``census_2023`` / ``civil_registry``; unknown kept as-is."""
    n = normalize_text(value)
    if not n:
        return None
    if "census" in n or "censusi" in n or "instat" in n:
        return "census_2023"
    if "civil" in n or "gjendj" in n or "regjist" in n:
        return "civil_registry"
    return str(value).strip()


def normalize_programme_code(value: object) -> str | None:
    """Programme codes are 5-digit strings; restores lost leading zeros ('5100' → '05100')."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    raw = str(value).strip()
    if not raw:
        return None
    if raw.isdigit() and len(raw) < 5:
        return raw.zfill(5)
    return raw


REQUEST_STATUSES: dict[str, L10n] = {
    "E mbyllur": t("E mbyllur", "Closed"),
    "Në proces": t("Në proces", "In progress"),
    "E re": t("E re", "New"),
    "E refuzuar": t("E refuzuar", "Rejected"),
}


def normalize_status(value: object) -> str | None:
    """Request status → one of ``REQUEST_STATUSES`` when recognised; unknown kept as-is."""
    n = normalize_text(value)
    if not n:
        return None
    if n.startswith(("e mbyllur", "mbyllur", "zgjidhur", "e zgjidhur", "closed", "resolved")):
        return "E mbyllur"
    if n.startswith(("ne proces", "proces", "ne shqyrtim", "in progress", "open")):
        return "Në proces"
    if n in {"e re", "re", "new", "e regjistruar", "regjistruar"}:
        return "E re"
    if n.startswith(("e refuzuar", "refuzuar", "rejected", "refused")):
        return "E refuzuar"
    return str(value).strip()


# --------------------------------------------------------------------------------------------
# Numbers, dates and months
# --------------------------------------------------------------------------------------------

_NUM_STRIP_RE = re.compile(r"[^\d,.\-+]")
_MISSING_TOKENS = {"", "-", "–", "—", "n/a", "na", "nan", "null", "none", "..", "...", "x"}


def parse_number(value: object) -> float | None:
    """Parse a number written in Albanian or English style.

    Handles decimal comma ("1.234,5"), thousands dots ("1.234" → 1234), English style
    ("1,234.5"), spaces/non-breaking spaces, units and currency ("12 lekë", "85%"), and
    accounting negatives ("(1.234)"). Returns None for blanks and dashes; raises ValueError
    for text that is not a number.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        f = float(value)
        return None if math.isnan(f) else f
    raw = str(value).strip()
    if raw.casefold() in _MISSING_TOKENS:
        return None
    negative = raw.startswith("(") and raw.endswith(")")
    s = _NUM_STRIP_RE.sub("", raw.replace(" ", "").replace(" ", ""))
    if not s or not any(ch.isdigit() for ch in s):
        raise ValueError(f"not a number: {value!r}")
    if s.startswith("+"):
        s = s[1:]
    if s.count("-") > 1 or ("-" in s and not s.startswith("-")):
        raise ValueError(f"not a number: {value!r}")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):  # 1.234,5
            s = s.replace(".", "").replace(",", ".")
        else:  # 1,234.5
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "") if s.count(",") > 1 else s.replace(",", ".")
    elif "." in s:
        head, _, tail = s.rpartition(".")
        if s.count(".") > 1 or (len(tail) == 3 and head.lstrip("-") not in {"", "0"}):
            s = s.replace(".", "")  # 1.234 or 1.234.567 (Albanian thousands)
    try:
        f = float(s)
    except ValueError as exc:
        raise ValueError(f"not a number: {value!r}") from exc
    return -f if negative else f


def parse_int(value: object) -> int | None:
    f = parse_number(value)
    return None if f is None else int(round(f))


ALBANIAN_MONTHS: dict[str, int] = {
    "janar": 1,
    "shkurt": 2,
    "mars": 3,
    "prill": 4,
    "maj": 5,
    "qershor": 6,
    "korrik": 7,
    "gusht": 8,
    "shtator": 9,
    "tetor": 10,
    "nentor": 11,
    "dhjetor": 12,
}
MONTH_NAMES_SQ: tuple[str, ...] = (
    "janar",
    "shkurt",
    "mars",
    "prill",
    "maj",
    "qershor",
    "korrik",
    "gusht",
    "shtator",
    "tetor",
    "nëntor",
    "dhjetor",
)
MONTH_NAMES_EN: tuple[str, ...] = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _month_lookup() -> dict[str, int]:
    table: dict[str, int] = {}
    for name, num in ALBANIAN_MONTHS.items():
        table[name] = num
        table[name + "i"] = num  # definite: janari, shkurti, korriku
        table[name[:3]] = num
    table["prilli"] = 4
    table["maji"] = 5
    for num, name in enumerate(MONTH_NAMES_EN, start=1):
        table[name.casefold()] = num
        table[name[:3].casefold()] = num
    table["sept"] = 9
    table["shk"] = 2
    table["sht"] = 9
    table["nen"] = 11
    table["dhj"] = 12
    return table


_MONTH_WORDS = _month_lookup()

_ISO_MONTH_RE = re.compile(r"^(\d{4})[-/.](\d{1,2})$")
_MONTH_YEAR_RE = re.compile(r"^(\d{1,2})[-/.](\d{4})$")
_DMY_RE = re.compile(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})$")
_YMD_RE = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ t].*)?$")
_DATE_IN_TEXT_RE = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})|(\d{4})-(\d{2})-(\d{2})")


def _year(y: int) -> int:
    return y + 2000 if y < 100 else y


def parse_date(value: object) -> dt.date | None:
    """Parse a date: date/datetime objects, "dd.mm.yyyy", "dd/mm/yyyy", "yyyy-mm-dd".

    Returns None for blanks; raises ValueError for text that is not a date.
    """
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    raw = str(value).strip()
    if raw.casefold() in _MISSING_TOKENS:
        return None
    m = _DMY_RE.match(raw)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), _year(int(m.group(3)))
        return dt.date(y, mo, d)
    m = _YMD_RE.match(raw)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    raise ValueError(f"not a date: {value!r}")


def parse_month(value: object, default_year: int | None = None) -> dt.date | None:
    """Parse a month to the first day of that month.

    Accepts "Janar 2026", "janar", "Korrik-2026", "2026-01", "01.2026", "01/2026",
    "2026-01-15", "15.01.2026" and date/datetime objects. A bare month name needs
    ``default_year``. Returns None for blanks; raises ValueError otherwise.
    """
    if value is None:
        return None
    if isinstance(value, dt.datetime | dt.date):
        d = value.date() if isinstance(value, dt.datetime) else value
        return d.replace(day=1)
    raw = str(value).strip()
    if raw.casefold() in _MISSING_TOKENS:
        return None
    m = _ISO_MONTH_RE.match(raw)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), 1)
    m = _MONTH_YEAR_RE.match(raw)
    if m:
        return dt.date(int(m.group(2)), int(m.group(1)), 1)
    try:
        return parse_date(raw).replace(day=1)  # type: ignore[union-attr]
    except ValueError:
        pass
    words = normalize_text(raw).split()
    month = next((_MONTH_WORDS[w] for w in words if w in _MONTH_WORDS), None)
    year = next((int(w) for w in words if w.isdigit() and len(w) == 4), None)
    if month is not None:
        year = year or default_year
        if year is None:
            raise ValueError(f"month without year: {value!r}")
        return dt.date(year, month, 1)
    raise ValueError(f"not a month: {value!r}")


def find_date_in_text(text: object) -> dt.date | None:
    """First date found inside free text, e.g. a header "Numri i punonjësve (31.08.2026)"."""
    if not text:
        return None
    m = _DATE_IN_TEXT_RE.search(str(text))
    if not m:
        return None
    try:
        if m.group(1):
            return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        return dt.date(int(m.group(4)), int(m.group(5)), int(m.group(6)))
    except ValueError:
        return None


_THOUSANDS_RE = re.compile(r"\(\s*0{3}\s*(leke|lek|all)?\s*\)|mije leke|mije lek|ne mije|000 leke")
_MILLIONS_RE = re.compile(r"\(\s*mln|milion|\(\s*0{6}\s*")


def unit_multiplier_from_text(text: object) -> int:
    """Money multiplier implied by a header or title: "(000 lekë)" → 1000, "(mln lekë)" → 1e6."""
    n = strip_diacritics(str(text or "")).casefold()
    if _MILLIONS_RE.search(n):
        return 1_000_000
    if _THOUSANDS_RE.search(n):
        return 1_000
    return 1


def coerce_value(dataset: str, field_key: str, raw: object, *, multiplier: float = 1) -> object:
    """Coerce one raw cell to the canonical type/normalisation of ``dataset.field_key``.

    Returns None for blanks; raises ValueError for values that cannot be parsed.
    ``multiplier`` is applied to money fields only.
    """
    f = get_dataset(dataset).field(field_key)
    if f.normalizer == "month":
        return parse_month(raw)
    if f.type == "date":
        return parse_date(raw)
    if f.type == "float":
        num = parse_number(raw)
        if num is None:
            return None
        return num * multiplier if f.money else num
    if f.type == "int":
        return parse_int(raw)
    # strings
    if raw is None:
        return None
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    if isinstance(raw, dt.datetime | dt.date):
        raw = raw.isoformat()[:10]
    match f.normalizer:
        case "admin_unit":
            return normalize_admin_unit(raw)
        case "line_type":
            return normalize_line_type(raw)
        case "basis":
            return normalize_basis(raw)
        case "programme_code":
            return normalize_programme_code(raw)
        case "status":
            return normalize_status(raw)
    text = _SPACE_RE.sub(" ", str(raw)).strip()
    return text or None


__all__ = [
    "ADMIN_UNITS",
    "AREAS",
    "DATASETS",
    "DEFAULT_POPULATION_BASIS",
    "FACT_TABLES",
    "OWNERS",
    "POPULATION_BASES",
    "UNIT_LABELS",
    "Dataset",
    "Field",
    "L10n",
    "area",
    "coerce_value",
    "dataset_for_table",
    "datasets_for_topic",
    "find_date_in_text",
    "get_dataset",
    "header_key",
    "match_admin_unit",
    "normalize_admin_unit",
    "normalize_text",
    "owner",
    "parse_date",
    "parse_int",
    "parse_month",
    "parse_number",
    "t",
    "unit_multiplier_from_text",
]
