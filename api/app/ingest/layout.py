"""Steps 2–3 — find the header row, the unit hints and the rows that are not data.

Municipal exports put title rows (often merged across the sheet) above the header, may use a
two-level header (a merged group cell over sub-columns), write units in headers ("Plani (000
lekë)") or in a title line ("Vlerat në mijë lekë"), and close with a blank row plus a TOTALI /
Gjithsej row. Total rows are excluded from the data and kept for reconciliation.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from app.catalog import normalize_text, strip_diacritics, unit_multiplier_from_text
from app.ingest.reader import Cell, RawTable

HEADER_SCAN_ROWS = 30

_TOTAL_FIRST_WORDS = {"totali", "total", "totale", "gjithsej", "gjithesej", "shuma", "grand"}
_SUBTOTAL_PREFIXES = ("nentotal", "nen total", "subtotal", "sub total", "shuma e pjesshme")
_NUMERIC_TEXT_RE = re.compile(
    r"[\s(+\-−]*[\d][\d.,\s ']*%?\)?\s*(lek[eë]?|all|eur|€|\$)?\s*", re.IGNORECASE
)
_DATE_TEXT_RE = re.compile(r"\d{1,4}[./-]\d{1,2}(?:[./-]\d{1,4})?")
_EXPLICIT_LEK_RE = re.compile(r"\b(lek|leke|all)\b")


def is_numeric_text(value: str) -> bool:
    return bool(_NUMERIC_TEXT_RE.fullmatch(value))


def is_label(value: Cell) -> bool:
    """A cell that reads like a column label (text that is not a number or a date)."""
    if not isinstance(value, str):
        return False
    return not is_numeric_text(value) and not _DATE_TEXT_RE.fullmatch(value)


def cell_text(value: Cell) -> str:
    if value is None:
        return ""
    if isinstance(value, dt.datetime):
        return value.date().isoformat() if value.time() == dt.time(0) else value.isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return re.sub(r"\s+", " ", str(value)).strip()


def row_text(row: list[Cell], limit: int = 160) -> str:
    seen: list[str] = []
    for v in row:
        t = cell_text(v)
        if t and t not in seen:
            seen.append(t)
    text = " · ".join(seen)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def total_kind(row: list[Cell]) -> str | None:
    """``total_row`` / ``subtotal`` when one of the first two filled cells is a total label."""
    labels = [v for v in row if v is not None][:2]
    for v in labels:
        if not isinstance(v, str):
            continue
        n = normalize_text(v)
        if not n:
            continue
        if n.startswith(_SUBTOTAL_PREFIXES):
            return "subtotal"
        first = n.split()[0]
        if first in _TOTAL_FIRST_WORDS:
            if first == "grand" and "total" not in n:
                continue
            return "total_row"
    return None


@dataclass
class ExcludedRow:
    row_no: int
    reason: str
    """``title`` | ``blank`` | ``total_row`` | ``subtotal``."""
    text: str
    cells: list[Cell]
    display: list[str | int | float | None] | None = None
    """Cells for display (see ``display_cells``); set by the pipeline after the PII gate."""

    def api(self) -> dict:
        return {
            "row_no": self.row_no,
            "reason": self.reason,
            "text": self.text,
            # additive: the cells for display, numbers as numbers so the client formats them in
            # its locale (text is masked; personal columns are already empty)
            "cells": self.display if self.display is not None else display_cells(self.cells),
        }


def display_cells(
    row: list[Cell],
    number_at: Callable[[int, str], float | None] | None = None,
    limit: int = 40,
) -> list[str | int | float | None]:
    """JSON-safe cells of a set-aside row: numbers stay numbers, dates become ISO text, text is
    masked (e-mails, personal IDs, phones); trailing empty cells are dropped. ``number_at``
    reads a text cell of a number column as a number (the column's own number style)."""
    from app.ingest.pii import mask_personal

    out: list[str | int | float | None] = []
    for j, v in enumerate(row[:limit]):
        if isinstance(v, str) and number_at is not None:
            num = number_at(j, v)
            if num is not None:
                out.append(round(num, 6))
                continue
        if v is None or isinstance(v, bool):
            out.append(None if v is None else str(v))
        elif isinstance(v, int):
            out.append(v)
        elif isinstance(v, float):
            out.append(None if math.isnan(v) or math.isinf(v) else round(v, 6))
        else:
            text = cell_text(v)
            out.append(mask_personal(text)[:160] if text else None)
    while out and out[-1] is None:
        out.pop()
    return out


@dataclass
class Layout:
    header_row: int
    """1-based row number of the (last) header row."""
    header_rows: list[int]
    headers: list[str]
    """Unique, display-ready column names (empty headers become "Kolona N")."""
    raw_headers: list[str]
    data: list[tuple[int, list[Cell]]]
    """``(row_no, cells)`` for every data row, ``row_no`` 1-based in the original file."""
    excluded: list[ExcludedRow]
    title_texts: list[str]
    col_multiplier: list[int]
    unit_sources: dict[int, str] = field(default_factory=dict)
    """Column index → the text the multiplier came from (header or title)."""

    @property
    def rows_read(self) -> int:
        return len(self.data) + len(self.excluded)

    @property
    def grand_total(self) -> ExcludedRow | None:
        totals = [e for e in self.excluded if e.reason == "total_row"]
        return totals[-1] if totals else None


def _width(rows: list[list[Cell]]) -> int:
    return max((sum(v is not None for v in r) for r in rows[:500]), default=0)


def detect_header(rows: list[list[Cell]]) -> int:
    """0-based index of the header row: the first row (after titles) that is mostly labels.

    Title rows are skipped because they hold one distinct value (merged titles are
    forward-filled, so they repeat the same text across the row).
    """
    width = max(_width(rows), 1)
    need = max(2, math.ceil(0.5 * width))
    fallback, fallback_distinct = 0, 0
    for i, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        filled = [v for v in row if v is not None]
        distinct = {cell_text(v) for v in filled}
        if len(distinct) < 2:
            continue
        labels = sum(is_label(v) for v in filled)
        if len(distinct) > fallback_distinct:
            fallback, fallback_distinct = i, len(distinct)
        if len(distinct) >= need and labels / len(filled) >= 0.7 and i + 1 < len(rows):
            return i
    return fallback


def _header_merged(table: RawTable, idx: int) -> bool:
    return any(r0 <= idx <= r1 and c1 > c0 for r0, c0, r1, c1 in table.merged)


def _unique(names: list[str]) -> list[str]:
    out: list[str] = []
    seen: dict[str, int] = {}
    for i, name in enumerate(names):
        base = name or f"Kolona {i + 1}"
        key = base.casefold()
        if key in seen:
            seen[key] += 1
            base = f"{base} ({seen[key]})"
        else:
            seen[key] = 1
        out.append(base)
    return out


def _is_note(row: list[Cell], width: int) -> bool:
    filled = [v for v in row if v is not None]
    return (
        width >= 3
        and len(filled) == 1
        and isinstance(filled[0], str)
        and len(filled[0].split()) >= 4
        and not is_numeric_text(filled[0])
    )


def analyse(table: RawTable) -> Layout:
    rows = table.rows
    h = detect_header(rows)
    header_idx = [h]
    header_cells = [cell_text(v) for v in rows[h]]

    # Two-level header: a merged group row over a row of sub-labels.
    if h + 1 < len(rows) and _header_merged(table, h):
        nxt = rows[h + 1]
        filled = [v for v in nxt if v is not None]
        if filled and sum(is_label(v) for v in filled) / len(filled) >= 0.7 and len(filled) >= 2:
            combined = []
            for top, sub in zip(header_cells, (cell_text(v) for v in nxt), strict=False):
                if top and sub and normalize_text(top) != normalize_text(sub):
                    combined.append(f"{top} {sub}")
                else:
                    combined.append(sub or top)
            header_cells = combined
            header_idx.append(h + 1)

    raw_headers = header_cells
    headers = _unique(raw_headers)
    last_header = header_idx[-1]
    width = max(_width(rows), 1)

    excluded: list[ExcludedRow] = []
    title_texts: list[str] = []
    title_rows: list[list[Cell]] = []
    for i in range(h):
        row = rows[i]
        if all(v is None for v in row):
            excluded.append(ExcludedRow(i + 1, "blank", "", row))
            continue
        text = row_text(row)
        title_texts.append(text)
        title_rows.append(row)
        excluded.append(ExcludedRow(i + 1, "title", text, row))

    header_norm = [normalize_text(x) for x in raw_headers]
    first_idx = next((j for j, x in enumerate(header_norm) if x), 0)
    data: list[tuple[int, list[Cell]]] = []
    for i in range(last_header + 1, len(rows)):
        row = rows[i]
        row_no = i + 1
        if all(v is None for v in row):
            excluded.append(ExcludedRow(row_no, "blank", "", row))
            continue
        kind = total_kind(row)
        if kind:
            excluded.append(ExcludedRow(row_no, kind, row_text(row), row))
            continue
        first = row[first_idx] if first_idx < len(row) else None
        if (
            isinstance(first, str)
            and normalize_text(first) == header_norm[first_idx]
            and [normalize_text(cell_text(v)) for v in row] == header_norm
        ):
            excluded.append(ExcludedRow(row_no, "title", row_text(row), row))  # repeated header
            continue
        if _is_note(row, width):
            excluded.append(ExcludedRow(row_no, "title", row_text(row), row))
            continue
        data.append((row_no, row))

    # Units: the column header wins; an explicit "lek" header means ×1; otherwise a title
    # cell above the column ("Vlerat në mijë lekë", a merged group "(000 lekë)") applies.
    col_multiplier: list[int] = []
    unit_sources: dict[int, str] = {}
    for j, name in enumerate(raw_headers):
        mult = unit_multiplier_from_text(name)
        source = name
        if mult == 1 and not _EXPLICIT_LEK_RE.search(strip_diacritics(name).casefold()):
            for row in reversed(title_rows):
                cell = row[j] if j < len(row) else None
                m = unit_multiplier_from_text(cell) if cell is not None else 1
                if m > 1:
                    mult, source = m, cell_text(cell)
                    break
        col_multiplier.append(mult)
        if mult > 1:
            unit_sources[j] = source

    excluded.sort(key=lambda e: e.row_no)
    return Layout(
        header_row=last_header + 1,
        header_rows=[i + 1 for i in header_idx],
        headers=headers,
        raw_headers=raw_headers,
        data=data,
        excluded=excluded,
        title_texts=title_texts,
        col_multiplier=col_multiplier,
        unit_sources=unit_sources,
    )
