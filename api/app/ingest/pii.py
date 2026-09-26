"""Step 4 — the personal-data gate. Runs before profiling samples are built and before any LLM call.

A column is personal when its header says so (name, phone, email, address, personal number)
or when its values do (Albanian mobile numbers ``+355 6x`` / ``06x``, emails, the Albanian
personal number ``[A-T]\\d{8}[A-W]``, "Firstname X." / "Firstname Lastname" person names).
Personal columns are dropped from the working copy of the file: their values are never
profiled, stored, shown as samples or sent to a model.

Samples of the remaining columns are masked: any identifier-like pattern that slipped into a
non-personal column is replaced, and long digit runs keep only their first and last digits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.catalog import header_key, normalize_text, t
from app.ingest.reader import Cell

PiiKind = Literal["name", "phone", "email", "personal_id", "address"]

PII_LABELS: dict[str, dict[str, str]] = {
    "name": t("emër", "name"),
    "phone": t("telefon", "phone"),
    "email": t("email", "email"),
    "personal_id": t("nr. personal", "personal number"),
    "address": t("adresë", "address"),
}

# ---- header keywords (compared on header_key tokens, so "(tel/online)" notes are ignored) ----

_NAME_WORDS = {"emri", "emer", "emrin", "emrat", "mbiemri", "mbiemer", "mbiemrin", "name"}
_PERSON_WORDS = {
    "kerkuesit",
    "kerkuesi",
    "qytetarit",
    "qytetari",
    "punonjesit",
    "personit",
    "aplikantit",
    "aplikanti",
    "perfituesit",
    "pronarit",
    "mbiemri",
    "mbiemer",
    "mbiemrin",
    "full",
    "first",
    "last",
    "applicant",
    "citizen",
    "employee",
    "person",
}
_WEAK_PERSON_HEADERS = {
    "kerkuesi",
    "kerkuesit",
    "qytetari",
    "pergjegjesi",
    "drejtuesi",
    "punonjesi",
    "personi",
    "kontakti",
    "kontakt",
    "contact",
    "responsible",
    "manager",
    "applicant",
}
_PHONE_WORDS = {"telefon", "telefoni", "telefonit", "tel", "cel", "celular", "mobile", "phone"}
_EMAIL_WORDS = {"email", "mail", "emaili", "e-mail"}
_EMAIL_PHRASES = ("e mail", "posta elektronike", "adresa elektronike")
_ADDRESS_WORDS = {"adresa", "adrese", "adresen", "adresat", "address", "vendbanimi"}
_ID_PHRASES = (
    "nr personal",
    "numri personal",
    "kodi personal",
    "nr i identifikimit",
    "numri i identifikimit",
    "numri i identitetit",
    "nr identiteti",
    "leternjoftimi",
    "leternjoftim",
    "id personale",
    "personal number",
    "personal id",
    "national id",
)
_ID_WORDS = {"nid", "nipt personal"}

# ---- value patterns ----

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(
    r"(?:(?:\+|00)\s?355[\s.\-/]?\(?0?\)?\s?6[6-9]|\b06[6-9])[\s.\-/]?\d{3}[\s.\-/]?\d{2}[\s.\-/]?\d{2}\b"
    r"|(?:\+|00)\s?355[\s.\-/]?\d{2}[\s.\-/]?\d{3}[\s.\-/]?\d{2}[\s.\-/]?\d{2}\b"
)
PERSONAL_ID_RE = re.compile(r"\b[A-T]\d{8}[A-W]\b")
_ADDRESS_VALUE_RE = re.compile(r"^(rr\.?|rruga|lagjja|lagja|lgj\.?|bulevardi|blv\.?)\s+\S", re.I)

_CAP = r"[A-ZÇËÁÉÍÓÚ][a-zçëáéíóú]+"
_NAME_INITIAL_RE = re.compile(rf"^({_CAP})(?:[- ]{_CAP})?\s+[A-ZÇË](\.)?$")
_NAME_FULL_RE = re.compile(rf"^({_CAP})(?:\s+{_CAP}){{1,2}}$")
MIN_DISTINCT_NAMES = 5
"""A person-name column has many different values ("Operatori A/B" is a category)."""

# Common Albanian first names (for "Firstname Lastname" values; initials need no list).
FIRST_NAMES = {
    n.casefold()
    for n in [
        "Adelina",
        "Adriana",
        "Afrim",
        "Agim",
        "Agron",
        "Albana",
        "Albert",
        "Alban",
        "Albi",
        "Alda",
        "Aldo",
        "Alketa",
        "Altin",
        "Amarildo",
        "Anila",
        "Anisa",
        "Ardit",
        "Arben",
        "Ardian",
        "Arjan",
        "Ariana",
        "Arlind",
        "Armand",
        "Armando",
        "Arta",
        "Artan",
        "Artur",
        "Astrit",
        "Aurel",
        "Bardh",
        "Bardhyl",
        "Behar",
        "Besa",
        "Besart",
        "Besiana",
        "Besnik",
        "Bledar",
        "Blerina",
        "Blerim",
        "Brikena",
        "Dafina",
        "Dea",
        "Denis",
        "Diana",
        "Dorina",
        "Dritan",
        "Drita",
        "Edi",
        "Edlira",
        "Edmond",
        "Eduart",
        "Egla",
        "Elda",
        "Eleni",
        "Elira",
        "Elona",
        "Elsa",
        "Elton",
        "Elvis",
        "Emirjeta",
        "Endrit",
        "Enea",
        "Engjëll",
        "Enkeleda",
        "Eno",
        "Entela",
        "Erald",
        "Erion",
        "Ermal",
        "Ervin",
        "Esmeralda",
        "Etleva",
        "Fatbardh",
        "Fatjon",
        "Fatmir",
        "Fitim",
        "Flora",
        "Florian",
        "Genc",
        "Gentian",
        "Gentiana",
        "Gëzim",
        "Gjergj",
        "Gjon",
        "Greta",
        "Hana",
        "Ilir",
        "Ilirjan",
        "Ina",
        "Iris",
        "Jonida",
        "Jonila",
        "Kaltrina",
        "Klajdi",
        "Klara",
        "Klaudia",
        "Kledi",
        "Klodian",
        "Kristi",
        "Lindita",
        "Liridon",
        "Lorena",
        "Luan",
        "Majlinda",
        "Manjola",
        "Marsela",
        "Marjana",
        "Mateo",
        "Merita",
        "Migena",
        "Mimoza",
        "Mirela",
        "Nertil",
        "Nevila",
        "Olsi",
        "Ornela",
        "Pranvera",
        "Redon",
        "Rezarta",
        "Rinor",
        "Rovena",
        "Sara",
        "Sokol",
        "Sonila",
        "Teuta",
        "Tomor",
        "Valbona",
        "Valentina",
        "Vjollca",
        "Xhesika",
        "Ylli",
        "Ylber",
        "Zamira",
        "Zana",
    ]
}


def _tokens(header: str) -> list[str]:
    return header_key(header).split()


def header_kind(header: str) -> tuple[PiiKind | None, bool]:
    """``(kind, strong)`` from the header text; ``strong`` means drop without looking at values."""
    hk = header_key(header)
    full = normalize_text(header)
    toks = set(hk.split())
    if any(p in hk for p in _ID_PHRASES) or toks & _ID_WORDS:
        return "personal_id", True
    if toks & _EMAIL_WORDS or any(p in full for p in _EMAIL_PHRASES):
        return "email", True
    if toks & _PHONE_WORDS:
        return "phone", True
    if toks & _ADDRESS_WORDS:
        return "address", True
    if toks & _NAME_WORDS:
        rest = toks - _NAME_WORDS - {"i", "e", "te", "se", "dhe", "and", "of", "the"}
        if not rest or rest & _PERSON_WORDS:
            return "name", True
        return "name", False  # "Emri i programit": check the values
    if toks & _WEAK_PERSON_HEADERS:
        return "name", False
    return None, False


def _looks_like_name(value: str) -> bool:
    """ "Arben K." (initial with a dot), or a known first name followed by a surname/initial."""
    m = _NAME_INITIAL_RE.match(value)
    if m and (m.group(2) or m.group(1).casefold() in FIRST_NAMES):
        return True
    m = _NAME_FULL_RE.match(value)
    return bool(m and m.group(1).casefold() in FIRST_NAMES)


def value_kind(values: list[Cell]) -> tuple[PiiKind | None, float]:
    """Kind suggested by the values of a column and the share of values that match it."""
    texts = [str(v).strip() for v in values if isinstance(v, str) and str(v).strip()]
    if not texts:
        return None, 0.0
    n = len(texts)
    names = [x for x in texts if _looks_like_name(x)]
    shares = {
        "personal_id": sum(bool(PERSONAL_ID_RE.search(x)) for x in texts) / n,
        "email": sum(bool(EMAIL_RE.search(x)) for x in texts) / n,
        "phone": sum(bool(PHONE_RE.search(x)) for x in texts) / n,
        "name": len(names) / n if len(set(names)) >= min(MIN_DISTINCT_NAMES, n) else 0.0,
        "address": sum(bool(_ADDRESS_VALUE_RE.match(x)) for x in texts) / n,
    }
    kind = max(shares, key=lambda k: shares[k])
    return (kind, shares[kind]) if shares[kind] > 0 else (None, 0.0)  # type: ignore[return-value]


@dataclass(frozen=True)
class PiiFinding:
    kind: PiiKind
    source: Literal["header", "values"]
    share: float


def detect_column(header: str, values: list[Cell]) -> PiiFinding | None:
    """Decide whether one column is personal. ``values`` are the column's data cells."""
    hkind, strong = header_kind(header)
    if hkind and strong:
        return PiiFinding(hkind, "header", 1.0)
    sample = [v for v in values if v is not None][:3000]
    vkind, share = value_kind(sample)
    if vkind is None:
        return None
    long_text = False
    texts = [v for v in sample if isinstance(v, str)]
    if texts:
        long_text = sum(len(x) for x in texts) / len(texts) > 25
    identifiers = vkind in ("personal_id", "email", "phone")
    if identifiers and (share >= 0.2 or (long_text and share > 0)):
        return PiiFinding(vkind, "values", share)
    if vkind == "name" and (share >= 0.6 or (hkind == "name" and share >= 0.3)):
        return PiiFinding("name", "values", share)
    if vkind == "address" and (share >= 0.6 or (hkind == "address" and share >= 0.3)):
        return PiiFinding("address", "values", share)
    return None


def detect(headers: list[str], columns: list[list[Cell]]) -> dict[int, PiiFinding]:
    """Column index → finding, for every personal column."""
    out: dict[int, PiiFinding] = {}
    for j, header in enumerate(headers):
        finding = detect_column(header, columns[j] if j < len(columns) else [])
        if finding:
            out[j] = finding
    return out


# --------------------------------------------------------------------------------------------
# Masking of sample values (non-personal columns)
# --------------------------------------------------------------------------------------------

_LONG_DIGITS_RE = re.compile(r"\d{6,}")


def _mask_digits(m: re.Match) -> str:
    s = m.group(0)
    return s[:2] + "•" * (len(s) - 4) + s[-2:]


def mask_sample(text: str, limit: int = 60) -> str:
    """Mask identifiers and long digit runs: "2526229.1" → "25•••29.1"."""
    text = EMAIL_RE.sub("[email]", text)
    text = PERSONAL_ID_RE.sub("[nr. personal]", text)
    text = PHONE_RE.sub("[telefon]", text)
    text = _LONG_DIGITS_RE.sub(_mask_digits, text)
    return text if len(text) <= limit else text[: limit - 1] + "…"
