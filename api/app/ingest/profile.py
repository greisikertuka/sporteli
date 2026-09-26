"""Step 5 — profile each non-personal column: inferred type, null share, masked samples.

Type inference understands the formats of Albanian exports: ``dd.mm.yyyy`` dates, month names
("Janar 2026"), ``YYYY-MM`` months, decimal commas ("2.562,4") and thousands dots ("23.944").
Codes with leading zeros ("01110") stay text.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from app.catalog import parse_date, parse_month, parse_number
from app.ingest.layout import cell_text, is_numeric_text
from app.ingest.pii import PII_LABELS, PiiFinding, mask_sample
from app.ingest.reader import Cell

TYPE_SAMPLE = 600
MAX_SAMPLES = 5

_DMY_RE = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{2,4}$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}")
_ISO_MONTH_RE = re.compile(r"^\d{4}[-/.]\d{1,2}$")
_DECIMAL_COMMA_RE = re.compile(r"^-?[\d.]*\d,\d+$")
_LEADING_ZERO_RE = re.compile(r"^0\d+$")


@dataclass
class ColumnProfile:
    index: int
    name: str
    inferred_type: str
    samples: list[str]
    null_pct: float
    pii: str | None
    dropped: bool
    formats: set[str] = field(default_factory=set)
    """Formats recognised in the values: dmy, month_name, iso_month, decimal_comma, excel_date."""

    def api(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "inferred_type": self.inferred_type,
            "samples": list(self.samples),
            "null_pct": self.null_pct,
            "pii": self.pii,
            "dropped": self.dropped,
        }


def classify(value: Cell) -> tuple[str, str | None]:
    """``(kind, format)`` for one non-empty cell: kind is date/int/float/string."""
    if isinstance(value, bool):
        return "string", None
    if isinstance(value, dt.datetime | dt.date):
        return "date", "excel_date"
    if isinstance(value, int):
        return "int", None
    if isinstance(value, float):
        return ("int" if value.is_integer() else "float"), None
    text = str(value).strip()
    if _DMY_RE.match(text):
        try:
            parse_date(text)
            return "date", "dmy"
        except ValueError:
            pass
    if _ISO_DATE_RE.match(text):
        try:
            parse_date(text)
            return "date", None
        except ValueError:
            pass
    if _ISO_MONTH_RE.match(text):
        try:
            parse_month(text)
            return "date", "iso_month"
        except ValueError:
            pass
    if is_numeric_text(text):
        if _LEADING_ZERO_RE.match(text):
            return "string", "code"
        try:
            num = parse_number(text)
        except ValueError:
            num = None
        if num is not None:
            fmt = "decimal_comma" if _DECIMAL_COMMA_RE.match(text.replace(" ", "")) else None
            return ("int" if float(num).is_integer() else "float"), fmt
    if any(ch.isalpha() for ch in text) and any(ch.isdigit() for ch in text):
        try:
            parse_month(text)
            return "date", "month_name"
        except ValueError:
            pass
    return "string", None


def infer_type(values: list[Cell]) -> tuple[str, set[str]]:
    filled = [v for v in values if v is not None][:TYPE_SAMPLE]
    if not filled:
        return "empty", set()
    kinds: dict[str, int] = {}
    formats: set[str] = set()
    for v in filled:
        kind, fmt = classify(v)
        kinds[kind] = kinds.get(kind, 0) + 1
        if fmt:
            formats.add(fmt)
    n = len(filled)
    if kinds.get("date", 0) / n >= 0.9:
        return "date", formats
    numeric = kinds.get("int", 0) + kinds.get("float", 0)
    if numeric / n >= 0.9:
        return ("float" if kinds.get("float") else "int"), formats
    return "string", formats - {"decimal_comma"}


def sample_text(value: Cell) -> str:
    return mask_sample(cell_text(value))


def profile_column(
    index: int, name: str, values: list[Cell], finding: PiiFinding | None
) -> ColumnProfile:
    total = len(values)
    nulls = sum(v is None for v in values)
    null_pct = round(100.0 * nulls / total, 1) if total else 100.0
    inferred, formats = infer_type(values)
    samples: list[str] = []
    if finding is None:
        seen: set[str] = set()
        for v in values:
            if v is None:
                continue
            s = sample_text(v)
            if s and s not in seen:
                seen.add(s)
                samples.append(s)
                if len(samples) >= MAX_SAMPLES:
                    break
    return ColumnProfile(
        index=index,
        name=name,
        inferred_type=inferred,
        samples=samples,
        null_pct=null_pct,
        pii=finding.kind if finding else None,
        dropped=finding is not None,
        formats=formats if finding is None else set(),
    )


def pii_label(kind: str, locale: str) -> str:
    return PII_LABELS[kind][locale]
