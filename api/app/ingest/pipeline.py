"""The ingest pipeline: preview (steps 1–7), commit (step 8), ``ingest_path`` and the demo seed.

``preview(data, filename)`` reads a department export, finds its header, sets aside title, blank
and total rows, drops personal columns, profiles the rest, recognises the dataset, looks up a
mapping recipe and proposes a column mapping (AI or rules). The result is cached for 30 minutes
under ``preview_id``; nothing is written to the warehouse.

``commit(preview_id, dataset, mapping)`` coerces types, applies the unit multiplier to money
fields, normalises admin units, inserts the rows with ``source_id`` + ``row_no`` (the original
1-based file row), reconciles sums against the file's total row, optionally saves the recipe and
returns a Load Receipt with the indicators the load unlocked.

Every step returns a real result with a bilingual message and its duration.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import threading
import time
import uuid
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa

from app import catalog
from app.catalog import DATASETS, Dataset, get_dataset, t
from app.config import get_settings
from app.indicators import registry as reg
from app.ingest import mapper, recipes
from app.ingest.errors import IngestError
from app.ingest.layout import (
    ExcludedRow,
    Layout,
    analyse,
    display_cells,
    row_text,
    total_kind,
)
from app.ingest.mapper import Suggestion
from app.ingest.pii import PII_LABELS, PiiFinding, detect, mask_personal
from app.ingest.profile import ColumnProfile, profile_column
from app.ingest.reader import RawTable, read_table, sanitize_filename
from app.llm.client import get_llm
from app.warehouse.db import insert_rows, new_cursor
from app.warehouse.schema import clear_tables, ensure_schema, table_columns

PREVIEW_TTL_S = 30 * 60
PREVIEW_CACHE_MAX = 24
RECONCILE_HALF_UNIT = 0.5
"""Reconciliation tolerance in units of the column's multiplier: half a unit of the file's
precision (0.5 lek, or 500 lek for a column in thousands), i.e. rounding only. A dropped row
of any real size shows up as a mismatch."""
RECONCILE_EPSILON = 1e-9
"""Relative float epsilon added to the tolerance (summing doubles)."""
MAX_EXCLUDED_LISTED = 100

L10n = dict[str, str]
Cursor = duckdb.DuckDBPyConnection

_WRITE_LOCK = threading.RLock()

EXCLUDED_LABELS: dict[str, L10n] = {
    "title": t("Rreshta titulli ose shënime", "Title or note rows"),
    "blank": t("Rreshta bosh", "Blank rows"),
    "total_row": t("Rresht totali (përdoret për rakordim)", "Total row (used for reconciliation)"),
    "subtotal": t("Nëntotale", "Subtotals"),
    "invalid": t(
        "Fushë e detyrueshme bosh ose e pavlefshme", "Required field empty or not readable"
    ),
}

_KIND_LABELS = {
    "csv": t("CSV", "CSV"),
    "xlsx": t("Excel (.xlsx)", "Excel (.xlsx)"),
    "xls": t("Excel 97–2003 (.xls)", "Excel 97–2003 (.xls)"),
}

_FORMAT_LABELS = {
    "dmy": t("data dd.mm.vvvv", "dd.mm.yyyy dates"),
    "month_name": t("muaj me emër ('Janar 2026')", "month names ('Janar 2026')"),
    "iso_month": t("muaj VVVV-MM", "YYYY-MM months"),
    "decimal_comma": t("presje dhjetore (1.234,5)", "decimal commas (1.234,5)"),
    "excel_date": t("data Excel", "Excel dates"),
    "code": t("kode me zero në fillim", "codes with leading zeros"),
}

_REPLACE_KEY: dict[str, tuple[str, ...] | None] = {
    "requests": ("request_id",),
    "budget": ("month", "programme_code", "line_type"),
    "waste": ("month", "admin_unit"),
    "revenue": ("month", "revenue_type", "payer_type"),
    "population": ("basis", "admin_unit"),
    "staff": None,  # a staff export is a snapshot: the newest one replaces the previous
}
"""Composite natural key per dataset: a new load replaces earlier rows with the same key tuple
(no double counting when the same export, or a corrected one, is loaded again). A partial or
correction export only replaces the rows it carries: other units, programmes or revenue lines
of the same month stay. Key fields the new file does not map are left out of the match."""

_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_NUMBER_IN_TEXT_RE = re.compile(r"\d[\d.,  ]*")


# --------------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------------


def _n(value: float | int | None, locale: str, decimals: int = 0) -> str:
    return reg.format_number(value, decimals, locale)


def _q(names: Iterable[str]) -> str:
    return ", ".join(f"'{x}'" for x in names)


def _now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


class StepLog:
    """Collects ``IngestStep`` items; each step's ``ms`` is the time since the previous one."""

    def __init__(self) -> None:
        self.items: list[dict] = []
        self._t = time.perf_counter()

    def restart(self) -> None:
        self._t = time.perf_counter()

    def add(self, code: str, status: str, sq: str, en: str) -> None:
        now = time.perf_counter()
        self.items.append(
            {
                "code": code,
                "status": status,
                "message": t(sq, en),
                "ms": int((now - self._t) * 1000),
            }
        )
        self._t = now


def _multiplier_words(mult: int, locale: str) -> str:
    if mult >= 1_000_000:
        return "milionë lekë" if locale == "sq" else "millions of lek"
    return "mijë lekë" if locale == "sq" else "thousands of lek"


# --------------------------------------------------------------------------------------------
# Preview state and cache
# --------------------------------------------------------------------------------------------


@dataclass
class PreviewState:
    preview_id: str
    filename: str
    file_hash: str
    size_bytes: int
    synthetic: bool
    table: RawTable
    layout: Layout
    columns: list[ColumnProfile]
    pii: dict[int, PiiFinding]
    candidates: list[dict]
    read_steps: list[dict]
    use_llm: bool
    created: float = field(default_factory=time.monotonic)
    default_year: int | None = None
    # mapping phase (recomputed by ``remap``)
    dataset: str | None = None
    dataset_confidence: float = 0.0
    suggestions: list[Suggestion] = field(default_factory=list)
    question: dict | None = None
    fingerprint: str = ""
    recipe_hit: recipes.Recipe | None = None
    drift: recipes.Drift | None = None
    llm: dict = field(default_factory=dict)
    map_steps: list[dict] = field(default_factory=list)
    warnings: list[L10n] = field(default_factory=list)
    unit_multiplier: int = 1
    unit_note: L10n | None = None

    @property
    def usable(self) -> list[ColumnProfile]:
        return [c for c in self.columns if not c.dropped]

    @property
    def column_index(self) -> dict[str, int]:
        return {c.name: c.index for c in self.columns}

    def number_style(self, idx: int) -> str | None:
        """The number style (``sq``/``en``/None) profiled for column ``idx``."""
        return self.columns[idx].number_style if 0 <= idx < len(self.columns) else None

    def api(self) -> dict:
        ds = get_dataset(self.dataset) if self.dataset else None
        return {
            "preview_id": self.preview_id,
            "filename": self.filename,
            "file_hash": self.file_hash,
            "size_bytes": self.size_bytes,
            "synthetic": self.synthetic,
            "dataset": (
                {
                    "key": ds.key,
                    "name": dict(ds.name),
                    "confidence": round(self.dataset_confidence, 2),
                }
                if ds
                else None
            ),
            "dataset_candidates": [
                {"key": c["key"], "score": round(float(c["score"]), 2)}
                for c in self.candidates
                if float(c["score"]) > 0
            ][:4],
            "sheet": self.table.sheet,
            "header_row": self.layout.header_row,
            "data_rows": len(self.layout.data),
            "unit_multiplier": self.unit_multiplier,
            "unit_note": self.unit_note,
            "excluded_rows": [e.api() for e in self.layout.excluded][:MAX_EXCLUDED_LISTED],
            "columns": [c.api() for c in self.columns],
            "mapping": [s.api() for s in self.suggestions],
            "question": self.question,
            "recipe": {
                "hit": self.recipe_hit is not None,
                "recipe_id": self.recipe_hit.id if self.recipe_hit else None,
                "fingerprint": self.fingerprint,
                "drift": self.drift.api() if self.drift else None,
            },
            "llm": self.llm,
            "steps": [*self.read_steps, *self.map_steps],
            "warnings": list(self.warnings),
        }


_cache: dict[str, PreviewState] = {}
_cache_lock = threading.Lock()


def _cache_purge_locked() -> None:
    now = time.monotonic()
    for key in [k for k, s in _cache.items() if now - s.created > PREVIEW_TTL_S]:
        del _cache[key]
    while len(_cache) > PREVIEW_CACHE_MAX:
        oldest = min(_cache, key=lambda k: _cache[k].created)
        del _cache[oldest]


def _cache_put(state: PreviewState) -> None:
    with _cache_lock:
        _cache[state.preview_id] = state
        _cache_purge_locked()


def get_preview(preview_id: str) -> PreviewState:
    with _cache_lock:
        _cache_purge_locked()
        state = _cache.get(preview_id)
    if state is None:
        raise IngestError(
            "preview_not_found",
            "Pamja paraprake nuk gjendet ose ka skaduar (30 min). Ngarkoni skedarin përsëri.",
            "The preview was not found or has expired (30 min). Upload the file again.",
            status_code=404,
        )
    return state


def _cache_drop(preview_id: str) -> None:
    with _cache_lock:
        _cache.pop(preview_id, None)


def clear_previews() -> None:
    with _cache_lock:
        _cache.clear()


# --------------------------------------------------------------------------------------------
# Preview: steps 1–5 (read, header, exclusions, PII gate, profile)
# --------------------------------------------------------------------------------------------


def _read_phase(data: bytes, filename: str, use_llm: bool) -> PreviewState:
    log = StepLog()
    table = read_table(data, filename)
    kind = _KIND_LABELS[table.kind]
    rows, cols = len(table.rows), table.ncols

    def read_msg(loc: str) -> str:
        sq = loc == "sq"
        head = f"U lexua {kind['sq']}" if sq else f"Read {kind['en']}"
        if table.sheet:
            head += f", fleta '{table.sheet}'" if sq else f", sheet '{table.sheet}'"
        size = (
            f"{_n(rows, loc)} rreshta × {_n(cols, loc)} kolona"
            if sq
            else f"{_n(rows, loc)} rows × {_n(cols, loc)} columns"
        )
        parts = [f"{head}: {size}"]
        if table.merged:
            parts.append(
                f"{len(table.merged)} zona qelizash të bashkuara u plotësuan"
                if sq
                else f"{len(table.merged)} merged cell ranges filled"
            )
        if table.kind == "csv":
            delim = {"\t": "TAB"}.get(table.delimiter or ",", table.delimiter or ",")
            parts.append(
                f"kodimi {table.encoding}, ndarësi '{delim}'"
                if sq
                else f"encoding {table.encoding}, delimiter '{delim}'"
            )
        return "; ".join(parts) + "."

    log.add("read", "ok", read_msg("sq"), read_msg("en"))

    layout = analyse(table)
    titles = [e for e in layout.excluded if e.row_no < layout.header_rows[0]]
    title_rows = sum(1 for e in titles if e.reason == "title")
    # prefer a column's own header ("Plani (000 lekë)") over a long title line
    unit_cols = sorted(
        layout.unit_sources,
        key=lambda j: (layout.unit_sources[j] != layout.raw_headers[j], j),
    )
    unit_src = layout.unit_sources[unit_cols[0]] if unit_cols else None
    if unit_src and len(unit_src) > 80:
        unit_src = unit_src[:79] + "…"
    unit_mult = layout.col_multiplier[unit_cols[0]] if unit_cols else 1

    def header_msg(loc: str) -> str:
        sq = loc == "sq"
        rows_txt = "–".join(str(r) for r in layout.header_rows)
        text = (
            f"Koka e tabelës u gjet në rreshtin {rows_txt}"
            if sq
            else f"Header found on row {rows_txt}"
        )
        if len(layout.header_rows) > 1:
            text += " (kokë me dy nivele)" if sq else " (two-level header)"
        if title_rows:
            text += (
                f"; {title_rows} rreshta titulli sipër saj"
                if sq
                else f"; {title_rows} title rows above it"
            )
        text += "."
        if unit_src:
            text += (
                f" Njësia u dallua nga '{unit_src}': vlerat monetare janë në "
                f"{_multiplier_words(unit_mult, 'sq')} (×{_n(unit_mult, 'sq')})."
                if sq
                else f" Unit detected from '{unit_src}': money values are in "
                f"{_multiplier_words(unit_mult, 'en')} (×{_n(unit_mult, 'en')})."
            )
        return text

    log.add("header", "ok", header_msg("sq"), header_msg("en"))

    after = [e for e in layout.excluded if e.row_no > layout.header_row]
    counts = Counter(e.reason for e in after)
    grand = layout.grand_total

    def exclude_msg(loc: str) -> str:
        sq = loc == "sq"
        if not after:
            return (
                "Asnjë rresht totali, nëntotali ose bosh pas kokës."
                if sq
                else "No total, subtotal or blank rows after the header."
            )
        parts = []
        if grand:
            label = mask_personal(next((v for v in grand.cells if isinstance(v, str)), "TOTALI"))
            parts.append(
                f"{counts['total_row']} total ('{label}', rreshti {grand.row_no}) — "
                "ruhet për rakordim"
                if sq
                else f"{counts['total_row']} total ('{label}', row {grand.row_no}) — "
                "kept for reconciliation"
            )
        if counts["subtotal"]:
            parts.append(f"{counts['subtotal']} " + ("nëntotal" if sq else "subtotal"))
        if counts["blank"]:
            parts.append(f"{counts['blank']} " + ("bosh" if sq else "blank"))
        if counts["title"]:
            parts.append(
                f"{counts['title']} " + ("shënim / kokë e përsëritur" if sq else "note/repeat")
            )
        head = (
            f"{len(after)} rreshta u veçuan nga të dhënat: "
            if sq
            else f"{len(after)} rows set aside from the data: "
        )
        return head + "; ".join(parts) + "."

    log.add("exclude", "ok" if after else "info", exclude_msg("sq"), exclude_msg("en"))

    # Step 4 — PII gate (before any sample is built and before any model call)
    ncols = len(layout.headers)
    values = [[row[j] if j < len(row) else None for _, row in layout.data] for j in range(ncols)]
    pii = detect(layout.headers, values)
    columns = [profile_column(j, layout.headers[j], values[j], pii.get(j)) for j in range(ncols)]
    for j in pii:  # the personal values leave the working copy here
        for _, row in layout.data:
            if j < len(row):
                row[j] = None
        for e in layout.excluded:
            if j < len(e.cells):
                e.cells[j] = None
    del values
    # The texts of set-aside rows were built before the gate: rebuild those below the header
    # from the cleaned cells, and mask e-mails, personal IDs and phones in every one of them
    # (a footer "Përgatiti: …, tel. 069 …" is not a column the gate can drop).
    first_header = layout.header_rows[0] if layout.header_rows else layout.header_row
    for e in layout.excluded:
        if not e.text:
            continue
        if pii and e.row_no > first_header:
            e.text = row_text(e.cells)
        e.text = mask_personal(e.text)
    layout.title_texts = [mask_personal(x) for x in layout.title_texts]

    def number_at(j: int, text: str) -> float | None:
        col = columns[j] if j < len(columns) else None
        if col is None or col.dropped or col.inferred_type not in ("int", "float"):
            return None
        try:
            return catalog.parse_number(text, col.number_style)
        except (ValueError, TypeError):
            return None

    for e in layout.excluded:
        if e.reason in ("total_row", "subtotal"):
            e.display = display_cells(e.cells, number_at)

    def pii_msg(loc: str) -> str:
        sq = loc == "sq"
        if not pii:
            return "Nuk u gjetën kolona personale." if sq else "No personal columns found."
        items = ", ".join(
            f"'{layout.headers[j]}' ({PII_LABELS[f.kind][loc]})" for j, f in pii.items()
        )
        one = len(pii) == 1
        if sq:
            head = "1 kolonë personale u hoq" if one else f"{len(pii)} kolona personale u hoqën"
            tail = "Vlerat e saj" if one else "Vlerat e tyre"
            return (
                f"{head} para profilizimit dhe para AI: {items}. "
                f"{tail} nuk ruhen dhe nuk dërgohen askund."
            )
        head = "1 personal column" if one else f"{len(pii)} personal columns"
        tail = "Its" if one else "Their"
        return (
            f"{head} removed before profiling and before AI: {items}. "
            f"{tail} values are not stored or sent anywhere."
        )

    log.add("pii", "ok", pii_msg("sq"), pii_msg("en"))

    usable = [c for c in columns if not c.dropped]
    types = Counter(c.inferred_type for c in usable)
    formats: list[str] = []
    for c in usable:
        for f in sorted(c.formats):
            if f in _FORMAT_LABELS and f not in formats:
                formats.append(f)

    def profile_msg(loc: str) -> str:
        sq = loc == "sq"
        numeric = types["int"] + types["float"]
        text = (
            f"{len(usable)} kolona u profilizuan: {types['date']} data, {numeric} numerike, "
            f"{types['string']} tekst"
            if sq
            else f"{len(usable)} columns profiled: {types['date']} date, {numeric} numeric, "
            f"{types['string']} text"
        )
        if types["empty"]:
            text += f", {types['empty']} " + ("bosh" if sq else "empty")
        if formats:
            text += ("; formate të njohura: " if sq else "; formats recognised: ") + ", ".join(
                _FORMAT_LABELS[f][loc] for f in formats
            )
        return text + "."

    log.add("profile", "ok", profile_msg("sq"), profile_msg("en"))

    synthetic = "SINTETIK" in filename.upper() or any(
        "SINTETIK" in x.upper() or "SYNTHETIC" in x.upper() for x in layout.title_texts
    )
    year = None
    for text in [*layout.title_texts, filename]:
        m = _YEAR_RE.search(text)
        if m:
            year = int(m.group(1))
            break

    return PreviewState(
        preview_id=uuid.uuid4().hex,
        filename=filename,
        file_hash=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        synthetic=synthetic,
        table=table,
        layout=layout,
        columns=columns,
        pii=pii,
        candidates=mapper.detect_dataset(columns, filename),
        read_steps=log.items,
        use_llm=use_llm,
        default_year=year,
    )


# --------------------------------------------------------------------------------------------
# Preview: steps 6–7 (dataset, recipe, mapping)
# --------------------------------------------------------------------------------------------


def _check_dataset_key(key: str) -> Dataset:
    try:
        return get_dataset(key)
    except KeyError as exc:
        raise IngestError(
            "unknown_dataset",
            f"Grupi i të dhënave '{key}' nuk ekziston.",
            f"Dataset '{key}' does not exist.",
        ) from exc


def _llm_summary(res=None, sent: dict | None = None, error: str | None = None) -> dict:
    if res is None:
        return {
            "used": False,
            "model": None,
            "latency_ms": None,
            "cost_usd": None,
            "error": error,
            "sent": None,
        }
    summary = res.summary()
    summary["sent"] = (
        {
            "headers": int(sent.get("headers", 0)),
            "samples_per_column": int(sent.get("samples_per_column", 0)),
            "rows_sent": 0,
        }
        if res.used and sent
        else None
    )
    return summary


def _derive_as_of(
    ds: Dataset, state: PreviewState, fields: Mapping[str, int]
) -> tuple[dt.date, str] | None:
    """Staff exports carry the snapshot date in a header ("Numri i punonjësve (31.08.2026)")."""
    if "as_of" not in ds.field_keys or "as_of" in fields:
        return None
    texts: list[str] = []
    if "headcount" in fields:
        texts.append(state.layout.raw_headers[fields["headcount"]])
    texts.extend(state.layout.raw_headers)
    texts.extend(state.layout.title_texts)
    for text in texts:
        d = catalog.find_date_in_text(text)
        if d:
            return d, text
    return None


def _unit_info(
    ds: Dataset, state: PreviewState, fields: Mapping[str, int]
) -> tuple[int, L10n | None, list[int]]:
    """Multiplier applied to the mapped money columns, and the note shown in the preview."""
    money_cols = [idx for key, idx in fields.items() if ds.field(key).money]
    cols = [j for j in money_cols if state.layout.col_multiplier[j] > 1]
    if not cols:
        return 1, None, []
    mult = max(state.layout.col_multiplier[j] for j in cols)
    names = [state.layout.headers[j] for j in cols]
    note = t(
        f"Kolonat {_q(names)} janë në {_multiplier_words(mult, 'sq')}: vlerat shumëzohen me "
        f"{_n(mult, 'sq')} gjatë ngarkimit.",
        f"Columns {_q(names)} are in {_multiplier_words(mult, 'en')}: values are multiplied by "
        f"{_n(mult, 'en')} on load.",
    )
    return mult, note, cols


def _map_phase(state: PreviewState, con: Cursor, dataset: str | None) -> None:
    log = StepLog()
    warnings: list[L10n] = []
    scores = {c["key"]: float(c["score"]) for c in state.candidates}
    chosen_by_user = dataset is not None
    if dataset is None and state.candidates:
        best = state.candidates[0]
        if float(best["score"]) >= mapper.DATASET_THRESHOLD:
            dataset = str(best["key"])
    ds = _check_dataset_key(dataset) if dataset else None
    state.dataset = ds.key if ds else None
    state.dataset_confidence = scores.get(ds.key, 0.0) if ds else 0.0
    state.suggestions, state.question = [], None
    state.recipe_hit, state.drift = None, None
    state.unit_multiplier, state.unit_note = 1, None

    if ds is None:
        log.add(
            "dataset",
            "warn",
            "Lloji i të dhënave nuk u dallua me siguri — zgjidhni grupin e të dhënave.",
            "The dataset could not be recognised with confidence — please choose one.",
        )
        state.fingerprint = recipes.fingerprint("", state.layout.headers)
        state.llm = _llm_summary()
        log.add(
            "mapping",
            "info",
            "Hartëzimi pret zgjedhjen e grupit të të dhënave.",
            "Mapping waits for the dataset choice.",
        )
        state.map_steps = log.items
        state.warnings = [
            t(
                "Zgjidhni grupin e të dhënave për të vazhduar.",
                "Choose the dataset to continue.",
            )
        ]
        return

    pct = round(state.dataset_confidence * 100)
    how_sq = "zgjedhur nga përdoruesi" if chosen_by_user else f"përputhja e kokave {pct}%"
    how_en = "chosen by the user" if chosen_by_user else f"header match {pct}%"
    log.add(
        "dataset",
        "ok" if chosen_by_user or state.dataset_confidence >= 0.6 else "warn",
        f"Grupi i të dhënave: {ds.name['sq']} ({how_sq}).",
        f"Dataset: {ds.name['en']} ({how_en}).",
    )

    # Step 6 — recipe
    headers = state.layout.headers
    state.fingerprint = recipes.fingerprint(ds.key, headers)
    exact = recipes.find_exact(con, ds.key, state.fingerprint)
    partial = None if exact else recipes.find_partial(con, ds.key, headers)
    if exact:
        state.recipe_hit = exact
        log.add(
            "recipe",
            "ok",
            f"Receta e ruajtur u gjet (nga '{exact.from_filename}', gjurma {exact.fingerprint}) "
            "— formati është i njohur.",
            f"Saved recipe found (from '{exact.from_filename}', fingerprint {exact.fingerprint}) "
            "— the format is known.",
        )
    elif not partial:
        log.add(
            "recipe",
            "info",
            f"Asnjë recetë për këtë format (gjurma {state.fingerprint}): hartëzimi propozohet.",
            f"No recipe for this format (fingerprint {state.fingerprint}): mapping is proposed.",
        )

    # Step 7 — mapping
    usable = state.usable
    if exact:
        valid = set(ds.field_keys)
        sugg = []
        for c in usable:
            f = exact.mapping.get(c.name)
            f = f if f in valid else None
            sugg.append(
                Suggestion(
                    c.name,
                    f,
                    1.0,
                    t(
                        f"Nga receta e konfirmuar më parë ('{exact.from_filename}').",
                        f"From the previously confirmed recipe ('{exact.from_filename}').",
                    ),
                    "recipe",
                )
            )
        state.suggestions = sugg
        state.llm = _llm_summary()
        mapped = sum(1 for s in sugg if s.field)
        log.add(
            "mapping",
            "ok",
            f"Hartëzimi nga receta: {mapped} nga {len(sugg)} kolona, pa thirrje AI.",
            f"Mapping from the recipe: {mapped} of {len(sugg)} columns, no AI call.",
        )
    else:
        rules, candidates = mapper.rules_mapping(ds, state.columns)
        ai = mapper.ai_mapping(ds, state.columns) if state.use_llm else None
        if ai is not None and ai.result.ok:
            by_col = {s.column: s for s in rules}
            # columns the model left out fall back to rules (never a duplicate field)
            ai_fields = {s.field for s in ai.suggestions.values() if s.field}
            state.suggestions = []
            for c in usable:
                s = ai.suggestions.get(c.name)
                if s is None:
                    r = by_col[c.name]
                    s = (
                        r
                        if r.field not in ai_fields
                        else Suggestion(c.name, None, 0.0, mapper.no_match_reason(c.name), "rules")
                    )
                state.suggestions.append(s)
            state.question = ai.question or mapper.rules_question(
                ds, state.columns, state.suggestions, candidates
            )
            state.llm = _llm_summary(ai.result, ai.sent)
            res = ai.result
            n_ai = sum(1 for s in state.suggestions if s.source == "ai" and s.field)
            log.add(
                "mapping",
                "ok",
                f"{res.model or 'AI'} propozoi hartëzimin ({n_ai} kolona) në "
                f"{_n((res.latency_ms or 0) / 1000, 'sq', 1)} s · ${_n(res.cost_usd, 'sq', 4)}. "
                f"U dërguan vetëm {ai.sent['headers']} koka dhe ≤{ai.sent['samples_per_column']} "
                "shembuj të maskuar për kolonë — 0 rreshta.",
                f"{res.model or 'AI'} proposed the mapping ({n_ai} columns) in "
                f"{_n((res.latency_ms or 0) / 1000, 'en', 1)} s · ${_n(res.cost_usd, 'en', 4)}. "
                f"Only {ai.sent['headers']} headers and ≤{ai.sent['samples_per_column']} masked "
                "samples per column were sent — 0 rows.",
            )
        else:
            state.suggestions = rules
            state.question = mapper.rules_question(ds, state.columns, rules, candidates)
            mapped = sum(1 for s in rules if s.field)
            if ai is not None:  # the call was attempted and failed
                state.llm = _llm_summary(ai.result, ai.sent)
                err = ai.result.error or "llm_error"
                log.add(
                    "mapping",
                    "warn",
                    f"Thirrja AI nuk u krye ({err}); u përdorën rregullat: {mapped} nga "
                    f"{len(rules)} kolona u hartëzuan — konfirmoni secilën.",
                    f"The AI call did not succeed ({err}); rules were used: {mapped} of "
                    f"{len(rules)} columns mapped — confirm each one.",
                )
            else:
                llm = get_llm()
                reason = None
                if state.use_llm:
                    reason = "llm_unavailable" if not llm.available else "llm_budget_exhausted"
                state.llm = _llm_summary(error=reason)
                log.add(
                    "mapping",
                    "info",
                    f"Modaliteti RREGULLA (pa AI): {mapped} nga {len(rules)} kolona u hartëzuan "
                    "me sinonime dhe ngjashmëri; besueshmëria kufizohet në 60% — konfirmoni "
                    "secilën kolonë.",
                    f"RULES mode (no AI): {mapped} of {len(rules)} columns mapped with synonyms "
                    "and similarity; confidence is capped at 60% — confirm each column.",
                )

        if partial:
            proposed = {s.column: s.field for s in state.suggestions}
            drift = recipes.drift(partial, headers, proposed)
            state.drift = drift
            valid = set(ds.field_keys)
            renamed_new = {new for _, new, _ in drift.renamed}
            added = set(drift.added) | renamed_new
            taken: set[str] = set()
            for i, s in enumerate(state.suggestions):
                if s.column in added or s.column not in partial.mapping:
                    continue
                f = partial.mapping.get(s.column)
                f = f if f in valid else None
                state.suggestions[i] = Suggestion(
                    s.column,
                    f,
                    1.0,
                    t(
                        f"Kolonë e pandryshuar nga receta ('{partial.from_filename}').",
                        f"Unchanged column from the recipe ('{partial.from_filename}').",
                    ),
                    "recipe",
                )
                if f:
                    taken.add(f)
            for s in state.suggestions:  # a changed column may not steal a recipe field
                if s.source != "recipe" and s.field in taken:
                    s.field, s.confidence = None, 0.0
            renamed_q = next(((o, n, f) for o, n, f in drift.renamed if f in valid), None)
            if renamed_q:
                state.question = mapper.drift_question(ds, renamed_q[1], renamed_q[0], renamed_q[2])
            parts_sq, parts_en = [], []
            if drift.renamed:
                pairs = ", ".join(f"'{o}' → '{n}'" for o, n, _ in drift.renamed)
                parts_sq.append(f"{len(drift.renamed)} e riemërtuar ({pairs})")
                parts_en.append(f"{len(drift.renamed)} renamed ({pairs})")
            if drift.missing:
                parts_sq.append(f"{len(drift.missing)} mungon ({_q(drift.missing)})")
                parts_en.append(f"{len(drift.missing)} missing ({_q(drift.missing)})")
            if drift.added:
                parts_sq.append(f"{len(drift.added)} e re ({_q(drift.added)})")
                parts_en.append(f"{len(drift.added)} new ({_q(drift.added)})")
            log.items.insert(  # the recipe step goes between the dataset and mapping steps
                1,
                {
                    "code": "recipe",
                    "status": "warn",
                    "message": t(
                        f"Formati ka ndryshuar krahasuar me recetën e '{partial.from_filename}' "
                        f"(gjurma {state.fingerprint} ≠ {partial.fingerprint}): "
                        + "; ".join(parts_sq)
                        + ". Kolonat e ndryshuara nuk hartëzohen në heshtje — konfirmoni ato.",
                        f"The format changed compared with the recipe from "
                        f"'{partial.from_filename}' (fingerprint {state.fingerprint} ≠ "
                        f"{partial.fingerprint}): "
                        + "; ".join(parts_en)
                        + ". Changed columns are not mapped silently — please confirm them.",
                    ),
                    "ms": 0,
                },
            )

    fields = {s.field: state.column_index[s.column] for s in state.suggestions if s.field}
    state.unit_multiplier, state.unit_note, _ = _unit_info(ds, state, fields)
    for s in state.suggestions:
        idx = state.column_index[s.column]
        s.transform = mapper.transform_for(ds, s.field, state.layout.col_multiplier[idx])

    # warnings
    missing = [f for f in ds.fields if f.required and f.key not in fields]
    if missing:
        warnings.append(
            t(
                "Fusha të detyrueshme pa kolonë: "
                + ", ".join(f"'{f.label['sq']}'" for f in missing)
                + ".",
                "Required fields without a column: "
                + ", ".join(f"'{f.label['en']}'" for f in missing)
                + ".",
            )
        )
    derived = _derive_as_of(ds, state, fields)
    if derived:
        d, src = derived
        warnings.append(
            t(
                f"Data e gjendjes {d:%d.%m.%Y} do të merret nga '{src}'.",
                f"The as-of date {d:%d.%m.%Y} will be taken from '{src}'.",
            )
        )
    if "admin_unit" in fields:
        idx = fields["admin_unit"]
        raw = {row[idx] for _, row in state.layout.data if row[idx] is not None}
        unknown = sorted(str(v) for v in raw if catalog.match_admin_unit(v) is None)
        variants = sorted(
            str(v)
            for v in raw
            if catalog.match_admin_unit(v) and catalog.match_admin_unit(v) != str(v).strip()
        )
        if variants:
            examples = ", ".join(f"'{v}' → '{catalog.match_admin_unit(v)}'" for v in variants[:3])
            warnings.append(
                t(
                    f"{len(variants)} shkrime të ndryshme të njësive administrative do të "
                    f"njësohen: {examples}.",
                    f"{len(variants)} alternative spellings of administrative units will be "
                    f"normalised: {examples}.",
                )
            )
        if unknown:
            warnings.append(
                t(
                    f"{len(unknown)} vlera të njësisë administrative nuk u njohën dhe ruhen "
                    f"siç janë: {_q(unknown[:5])}.",
                    f"{len(unknown)} administrative-unit values were not recognised and are "
                    f"kept as they are: {_q(unknown[:5])}.",
                )
            )
    for c in state.usable:
        s_field = next((s.field for s in state.suggestions if s.column == c.name), None)
        if s_field and ds.field(s_field).required and c.null_pct >= 20:
            warnings.append(
                t(
                    f"Kolona '{c.name}' ka {_n(c.null_pct, 'sq', 1)}% qeliza bosh; rreshtat pa "
                    "vlerë në një fushë të detyrueshme nuk ngarkohen.",
                    f"Column '{c.name}' has {_n(c.null_pct, 'en', 1)}% empty cells; rows without "
                    "a value in a required field are not loaded.",
                )
            )
    if len(state.table.sheets_with_data) > 1:
        warnings.append(
            t(
                f"Skedari ka {len(state.table.sheets_with_data)} fleta me të dhëna; u lexua e "
                f"para ('{state.table.sheet}').",
                f"The workbook has {len(state.table.sheets_with_data)} sheets with data; the "
                f"first one ('{state.table.sheet}') was read.",
            )
        )
    if not state.layout.data:
        warnings.append(t("Nuk u gjetën rreshta të dhënash.", "No data rows were found."))
    state.warnings = warnings
    state.map_steps = log.items


# --------------------------------------------------------------------------------------------
# Public preview API
# --------------------------------------------------------------------------------------------


@contextmanager
def _with_cursor(con: Cursor | None) -> Iterator[Cursor]:
    """Use the caller's cursor, or open (and close) a fresh one."""
    if con is not None:
        yield con
        return
    cur = new_cursor()
    try:
        yield cur
    finally:
        cur.close()


def prepare(
    data: bytes,
    filename: str,
    *,
    dataset: str | None = None,
    con: Cursor | None = None,
    use_llm: bool = True,
) -> PreviewState:
    """Run steps 1–7 and return the (uncached) preview state."""
    name = sanitize_filename(filename)
    if dataset is not None:
        _check_dataset_key(dataset)
    state = _read_phase(data, name, use_llm)
    with _with_cursor(con) as cur:
        _map_phase(state, cur, dataset)
    return state


def preview(
    data: bytes,
    filename: str,
    *,
    dataset: str | None = None,
    con: Cursor | None = None,
    use_llm: bool = True,
) -> dict:
    """``IngestPreview`` for an uploaded file; the state is cached for 30 minutes."""
    state = prepare(data, filename, dataset=dataset, con=con, use_llm=use_llm)
    _cache_put(state)
    return state.api()


def remap(preview_id: str, dataset: str, *, con: Cursor | None = None) -> dict:
    """Re-run dataset/recipe/mapping for a cached preview with another dataset."""
    state = get_preview(preview_id)
    _check_dataset_key(dataset)
    with _with_cursor(con) as cur:
        _map_phase(state, cur, dataset)
    return state.api()


# --------------------------------------------------------------------------------------------
# Commit (step 8)
# --------------------------------------------------------------------------------------------


def _ensure_receipt_column(con: Cursor) -> None:
    """Add ``source.receipt_json`` to a warehouse created before it existed. Only a read unless
    the column is missing (an ALTER on every read would conflict with an open reset)."""
    if "receipt_json" not in table_columns(con, "source"):
        con.execute("ALTER TABLE source ADD COLUMN IF NOT EXISTS receipt_json VARCHAR")


def _normalise_mapping(mapping: Iterable[Any]) -> list[tuple[str, str | None]]:
    out: list[tuple[str, str | None]] = []
    for m in mapping:
        if isinstance(m, Mapping):
            col, f = m.get("column"), m.get("field")
        else:
            col, f = getattr(m, "column", None), getattr(m, "field", None)
        out.append((str(col), f if f else None))
    return out


def _validate_mapping(
    state: PreviewState, ds: Dataset, mapping: list[tuple[str, str | None]]
) -> dict[str, int]:
    index = state.column_index
    fields: dict[str, int] = {}
    for col, f in mapping:
        if col not in index:
            raise IngestError(
                "unknown_column",
                f"Kolona '{col}' nuk ekziston në skedar.",
                f"Column '{col}' does not exist in the file.",
            )
        if f is None:
            continue
        if f not in ds.field_keys:
            raise IngestError(
                "unknown_field",
                f"Fusha '{f}' nuk i përket grupit '{ds.name['sq']}'.",
                f"Field '{f}' does not belong to dataset '{ds.name['en']}'.",
            )
        if index[col] in state.pii:
            raise IngestError(
                "personal_column",
                f"Kolona '{col}' është personale dhe u hoq; nuk mund të ngarkohet.",
                f"Column '{col}' is personal and was removed; it cannot be loaded.",
            )
        if f in fields:
            raise IngestError(
                "duplicate_field",
                f"Fusha '{ds.field(f).label['sq']}' është zgjedhur për më shumë se një kolonë.",
                f"Field '{ds.field(f).label['en']}' is chosen for more than one column.",
            )
        fields[f] = index[col]
    missing = [f for f in ds.fields if f.required and f.key not in fields]
    if missing:
        raise IngestError(
            "missing_required_fields",
            "Mungojnë fushat e detyrueshme: "
            + ", ".join(f"'{f.label['sq']}'" for f in missing)
            + ".",
            "Missing required fields: " + ", ".join(f"'{f.label['en']}'" for f in missing) + ".",
        )
    return fields


def _coerce(
    ds: Dataset,
    key: str,
    raw: Any,
    mult: int,
    default_year: int | None,
    style: str | None = None,
) -> Any:
    f = ds.field(key)
    try:
        return catalog.coerce_value(
            ds.key, key, raw, multiplier=mult if f.money else 1, number_style=style
        )
    except (ValueError, TypeError, OverflowError):
        if f.normalizer == "month" and default_year:
            return catalog.parse_month(raw, default_year=default_year)  # may raise again
        raise


def _replace_keys(ds: Dataset, mapped: Iterable[str]) -> tuple[str, ...] | None:
    """The key fields used to replace earlier rows: the dataset's natural key restricted to the
    fields this file maps (``None`` = snapshot, replace everything; ``()`` = replace nothing)."""
    spec = _REPLACE_KEY.get(ds.key, ())
    if spec is None:
        return None
    present = set(mapped)
    return tuple(k for k in spec if k in present)


def _mark_partly_replaced(
    con: Cursor, sid: str, rows_replaced: int, remaining: int, by: str
) -> None:
    """An earlier source lost some (not all) of its rows to a newer load: its reconciliation
    against its own total row no longer describes the stored rows, so mark it stale."""
    row = con.execute(
        "SELECT reconciliation_json, receipt_json FROM source WHERE id = ?", [sid]
    ).fetchone()
    if not row:
        return
    note = t(
        f"{_n(rows_replaced, 'sq')} rreshta të këtij skedari u zëvendësuan nga një ngarkim i "
        f"mëvonshëm ({by}); rakordimi me totalin e skedarit nuk vlen më për rreshtat e ruajtur.",
        f"{_n(rows_replaced, 'en')} rows of this file were replaced by a later load ({by}); the "
        "reconciliation with the file's total no longer describes the stored rows.",
    )
    recon = _json(row[0], [])
    if isinstance(recon, list):
        for item in recon:
            if isinstance(item, dict):
                item["stale"] = True
                item["note"] = note
    receipt = _json(row[1], None)
    receipt_json = row[1]
    if isinstance(receipt, dict):
        receipt["reconciliation"] = recon
        receipt["rows_current"] = remaining
        receipt.setdefault("superseded_by", []).append({"source_id": by, "rows": rows_replaced})
        receipt_json = json.dumps(receipt, ensure_ascii=False, default=str)
    con.execute(
        "UPDATE source SET reconciliation_json = ?, receipt_json = ? WHERE id = ?",
        [json.dumps(recon, ensure_ascii=False), receipt_json, sid],
    )


def _supersede(
    con: Cursor,
    ds: Dataset,
    records: list[dict],
    mapped: Iterable[str],
    new_source_id: str,
) -> list[dict]:
    """Delete earlier rows with the same natural key tuple; report what was replaced."""
    keys = _replace_keys(ds, mapped)
    if keys == ():
        return []
    view = f"_supersede_keys_{threading.get_ident()}"
    registered = False
    if keys is None:
        where = "TRUE"
    else:
        tuples = list(
            dict.fromkeys(
                tuple(r.get(k) for k in keys)
                for r in records
                if any(r.get(k) is not None for k in keys)
            )
        )
        if not tuples:
            return []
        # an Arrow table of key tuples, not list parameters: DuckDB inspects every list element
        arrays = {
            f"k{i}": pa.array(
                [tup[i] for tup in tuples],
                type=pa.date32() if ds.field(k).type == "date" else pa.string(),
            )
            for i, k in enumerate(keys)
        }
        con.register(view, pa.table(arrays))
        registered = True
        cond = " AND ".join(
            f"{ds.table}.{k} IS NOT DISTINCT FROM v.k{i}" for i, k in enumerate(keys)
        )
        where = f"EXISTS (SELECT 1 FROM {view} AS v WHERE {cond})"
    try:
        hits = con.execute(
            f"SELECT source_id, count(*) FROM {ds.table} WHERE {where} GROUP BY 1 ORDER BY 1"
        ).fetchall()
        if hits:
            con.execute(f"DELETE FROM {ds.table} WHERE {where}")
    finally:
        if registered:
            con.unregister(view)
    if not hits:
        return []
    out = []
    for sid, n in hits:
        remaining = con.execute(
            f"SELECT count(*) FROM {ds.table} WHERE source_id = ?", [sid]
        ).fetchone()[0]
        meta = con.execute("SELECT filename FROM source WHERE id = ?", [sid]).fetchone()
        if remaining == 0:
            con.execute("DELETE FROM source WHERE id = ?", [sid])
        else:
            _mark_partly_replaced(con, sid, int(n), int(remaining), new_source_id)
        out.append(
            {
                "source_id": sid,
                "filename": meta[0] if meta else sid,
                "rows": int(n),
                "source_removed": remaining == 0,
                "rows_remaining": int(remaining),
                "key": list(keys) if keys else [],
            }
        )
    return out


def _first_number(cells: list[Any]) -> float | None:
    for v in cells:
        if v is None or isinstance(v, bool):
            continue
        if isinstance(v, int | float):
            return float(v)
        if isinstance(v, str) and total_kind([v]) is None:
            m = _NUMBER_IN_TEXT_RE.search(v)
            if m:
                try:
                    return catalog.parse_number(m.group(0).strip())
                except ValueError:
                    continue
    return None


def _excluded_sum(
    ds: Dataset, state: PreviewState, key: str, idx: int, invalid: list[list[Any]]
) -> float:
    """Sum of the readable values of ``key`` in data rows that were not loaded (invalid)."""
    total = 0.0
    for cells in invalid:
        raw = cells[idx] if idx < len(cells) else None
        try:
            v = _coerce(
                ds, key, raw, state.layout.col_multiplier[idx], None, state.number_style(idx)
            )
        except (ValueError, TypeError, OverflowError):
            continue
        if isinstance(v, int | float) and not isinstance(v, bool):
            total += float(v)
    return round(total, 6)


def _reconcile(
    ds: Dataset,
    state: PreviewState,
    fields: Mapping[str, int],
    records: list[dict],
    rows_loaded: int,
    invalid: list[list[Any]] | None = None,
) -> list[dict]:
    """Loaded sums against the file's total row, to rounding precision.

    The tolerance is half a unit of the column's precision (``RECONCILE_HALF_UNIT`` times the
    column multiplier) plus a float epsilon, so only rounding passes. Rows that were not loaded
    (invalid) but carry a value in the field make the check fail and are named in the note."""
    grand: ExcludedRow | None = state.layout.grand_total
    out: list[dict] = []
    for f in ds.fields:
        if not f.reconcile or f.key not in fields:
            continue
        idx = fields[f.key]
        loaded = sum(float(r[f.key]) for r in records if r.get(f.key) is not None)
        loaded = round(loaded, 6)
        left_out = _excluded_sum(ds, state, f.key, idx, invalid or [])
        unit = state.layout.col_multiplier[idx] if f.money else 1
        file_total = None
        note = None
        if grand is None:
            note = t(
                "Skedari nuk ka rresht totali; shuma e ngarkuar u regjistrua për kontrolle "
                "të mëvonshme.",
                "The file has no total row; the loaded sum is recorded for later checks.",
            )
        else:
            raw = grand.cells[idx] if idx < len(grand.cells) else None
            try:
                v = _coerce(
                    ds,
                    f.key,
                    raw,
                    state.layout.col_multiplier[idx],
                    None,
                    state.number_style(idx),
                )
                file_total = float(v) if v is not None else None
            except (ValueError, TypeError):
                file_total = None
            if file_total is None:
                note = t(
                    "Rreshti i totalit nuk ka vlerë për këtë kolonë.",
                    "The total row has no value for this column.",
                )
        ok = True
        tolerance = RECONCILE_HALF_UNIT * unit
        if file_total is not None:
            diff = abs(loaded - file_total)
            tolerance += RECONCILE_EPSILON * max(abs(file_total), 1.0)
            ok = diff <= tolerance
            if not ok:
                pct = 100 * diff / abs(file_total) if file_total else 100.0
                note = t(
                    f"Shuma e ngarkuar ndryshon nga totali i skedarit me {_n(diff, 'sq', 2)} "
                    f"({_n(pct, 'sq', 2)}%). Kontrolloni rreshtat e përjashtuar ose njësinë.",
                    f"The loaded sum differs from the file's total by {_n(diff, 'en', 2)} "
                    f"({_n(pct, 'en', 2)}%). Check the excluded rows or the unit.",
                )
        if left_out:
            ok = False
            carried_sq = (
                f"Rreshtat e përjashtuar si të pavlefshëm mbajnë {_n(left_out, 'sq', 2)} në "
                "këtë fushë; kjo shumë nuk u ngarkua."
            )
            carried_en = (
                f"Excluded (invalid) rows carry {_n(left_out, 'en', 2)} in this field; that "
                "amount was not loaded."
            )
            note = (
                t(f"{note['sq']} {carried_sq}", f"{note['en']} {carried_en}")
                if note
                else t(carried_sq, carried_en)
            )
        out.append(
            {
                "field": f.key,
                "label": dict(f.label),
                "file_total": round(file_total, 6) if file_total is not None else None,
                "loaded_sum": loaded,
                "ok": ok,
                "note": note,
                # additive: what was left out, and the rounding tolerance that was applied
                "excluded_sum": left_out,
                "tolerance": round(tolerance, 6),
            }
        )
    if grand is not None and not out:  # no summable field: compare the row count ("2400 …")
        count = _first_number(grand.cells)
        if count is not None and float(count).is_integer():
            ok = int(count) == rows_loaded
            out.append(
                {
                    "field": "row_count",
                    "label": t("Numri i rreshtave", "Number of rows"),
                    "file_total": float(count),
                    "loaded_sum": float(rows_loaded),
                    "ok": ok,
                    "note": None
                    if ok
                    else t(
                        "Numri i rreshtave të ngarkuar ndryshon nga ai i rreshtit të totalit. "
                        "Kontrolloni rreshtat e përjashtuar.",
                        "The number of loaded rows differs from the total row. "
                        "Check the excluded rows.",
                    ),
                }
            )
    return out


def commit_state(
    state: PreviewState,
    dataset: str,
    mapping: Iterable[Any],
    save_recipe: bool = False,
    *,
    con: Cursor,
    in_transaction: bool = False,
) -> dict:
    """Load a prepared file (step 8). ``in_transaction=True`` joins the caller's open
    transaction (the demo reset) instead of opening and committing its own."""
    started = time.perf_counter()
    log = StepLog()
    ds = _check_dataset_key(dataset)
    pairs = _normalise_mapping(mapping)
    fields = _validate_mapping(state, ds, pairs)
    source_id = f"src-{uuid.uuid4().hex[:12]}"
    derived = _derive_as_of(ds, state, fields)

    # --- coerce ---------------------------------------------------------------------------
    col_errors: dict[str, list[int]] = {}
    invalid_rows: list[int] = []
    unit_changes: Counter = Counter()
    unknown_units: set[str] = set()
    records: list[dict] = []
    mults = state.layout.col_multiplier
    for row_no, cells in state.layout.data:
        rec: dict[str, Any] = {"source_id": source_id, "row_no": row_no}
        bad = False
        for key, idx in fields.items():
            raw = cells[idx] if idx < len(cells) else None
            try:
                value = _coerce(
                    ds, key, raw, mults[idx], state.default_year, state.number_style(idx)
                )
            except (ValueError, TypeError, OverflowError):
                value = None
                col_errors.setdefault(key, []).append(row_no)
            if key == "admin_unit" and raw is not None and value is not None:
                canonical = catalog.match_admin_unit(raw)
                if canonical is None:
                    unknown_units.add(str(raw))
                elif canonical != str(raw).strip():
                    unit_changes[(str(raw).strip(), canonical)] += 1
            if value is None and ds.field(key).required:
                bad = True
            rec[key] = value
        if derived and "as_of" not in fields:
            rec["as_of"] = derived[0]
        if bad:
            invalid_rows.append(row_no)
            continue
        records.append(rec)

    n_err = sum(len(v) for v in col_errors.values())
    if n_err:
        details_sq = "; ".join(
            f"'{ds.field(k).label['sq']}': {len(v)} (rreshtat {reg.row_ranges(v[:50])})"
            for k, v in col_errors.items()
        )
        details_en = "; ".join(
            f"'{ds.field(k).label['en']}': {len(v)} (rows {reg.row_ranges(v[:50])})"
            for k, v in col_errors.items()
        )
        log.add(
            "coerce",
            "warn",
            f"{_n(len(records), 'sq')} rreshta u kthyen në tipat kanonikë; {n_err} vlera nuk u "
            f"lexuan dhe u lanë bosh — {details_sq}.",
            f"{_n(len(records), 'en')} rows converted to canonical types; {n_err} values could "
            f"not be read and were left empty — {details_en}.",
        )
    else:
        log.add(
            "coerce",
            "ok",
            f"{_n(len(records), 'sq')} rreshta u kthyen në tipat kanonikë (data, numra, kode) "
            "pa asnjë gabim.",
            f"{_n(len(records), 'en')} rows converted to canonical types (dates, numbers, codes) "
            "without errors.",
        )
    if invalid_rows:
        log.add(
            "invalid",
            "warn",
            f"{len(invalid_rows)} rreshta nuk u ngarkuan: fushë e detyrueshme bosh ose e "
            f"palexueshme (rreshtat {reg.row_ranges(invalid_rows[:200])}).",
            f"{len(invalid_rows)} rows not loaded: a required field is empty or unreadable "
            f"(rows {reg.row_ranges(invalid_rows[:200])}).",
        )

    mult, _note, mult_cols = _unit_info(ds, state, fields)
    if mult > 1:
        names = [state.layout.headers[j] for j in mult_cols]
        log.add(
            "units",
            "ok",
            f"Kolonat monetare {_q(names)} u shumëzuan me {_n(mult, 'sq')} "
            f"({_multiplier_words(mult, 'sq')} → lekë).",
            f"Money columns {_q(names)} multiplied by {_n(mult, 'en')} "
            f"({_multiplier_words(mult, 'en')} → lek).",
        )
    if "admin_unit" in fields:
        changed = sum(unit_changes.values())
        examples = ", ".join(f"'{a}' → '{b}'" for (a, b), _ in unit_changes.most_common(3))
        log.add(
            "admin_units",
            "warn" if unknown_units else "ok",
            f"Njësitë administrative u njësuan: {_n(changed, 'sq')} vlera me shkrim tjetër"
            + (f" ({examples})" if examples else "")
            + f"; {len(unknown_units)} të panjohura"
            + (f" ({_q(sorted(unknown_units)[:5])}), të ruajtura siç janë" if unknown_units else "")
            + ".",
            f"Administrative units normalised: {_n(changed, 'en')} values with another spelling"
            + (f" ({examples})" if examples else "")
            + f"; {len(unknown_units)} unknown"
            + (f" ({_q(sorted(unknown_units)[:5])}), kept as they are" if unknown_units else "")
            + ".",
        )
    if derived and "as_of" not in fields:
        d, src = derived
        log.add(
            "derived",
            "info",
            f"Data e gjendjes {d:%d.%m.%Y} u mor nga '{src}'.",
            f"The as-of date {d:%d.%m.%Y} was taken from '{src}'.",
        )

    if not records:
        raise IngestError(
            "no_valid_rows",
            "Asnjë rresht nuk ka vlera të lexueshme në të gjitha fushat e detyrueshme. "
            "Kontrolloni hartëzimin e kolonave.",
            "No row has readable values in every required field. Check the column mapping.",
        )

    # --- insert, reconcile, recipe (one transaction) ----------------------------------------
    columns = ["source_id", "row_no", *fields]
    if derived and "as_of" not in fields:
        columns.append("as_of")
    invalid_set = set(invalid_rows)
    invalid_cells = [cells for row_no, cells in state.layout.data if row_no in invalid_set]
    reconciliation = _reconcile(ds, state, fields, records, len(records), invalid_cells)
    with _WRITE_LOCK:
        if not in_transaction:
            _ensure_receipt_column(con)
        before = reg.states(con)
        if not in_transaction:
            con.execute("BEGIN TRANSACTION")
        try:
            superseded = _supersede(con, ds, records, fields, source_id)
            inserted = insert_rows(con, ds.table, records, columns) if records else 0

            mapping_all = {c.name: None for c in state.usable}
            mapping_all.update({col: f for col, f in pairs if col in mapping_all})
            fp = recipes.fingerprint(ds.key, state.layout.headers)
            existing = recipes.find_exact(con, ds.key, fp)
            same_as_recipe = existing is not None and all(
                existing.mapping.get(col) == f for col, f in mapping_all.items()
            )
            recipe_saved, recipe_id = False, existing.id if same_as_recipe else None
            if save_recipe and not same_as_recipe:
                recipe_id = recipes.save(
                    con,
                    dataset=ds.key,
                    fp=fp,
                    headers=state.layout.headers,
                    mapping=mapping_all,
                    from_filename=state.filename,
                )
                recipe_saved = True
            recipe_reused = bool(same_as_recipe)

            after = reg.states(con)
            unlocked = reg.describe_codes(reg.newly_unlocked(before, after))
            cov = reg.coverage(con)

            excluded_counts = Counter(e.reason for e in state.layout.excluded)
            if invalid_rows:
                excluded_counts["invalid"] = len(invalid_rows)
            rows_excluded = [
                {"reason": r, "count": int(n), "label": dict(EXCLUDED_LABELS[r])}
                for r, n in excluded_counts.items()
                if n
            ]
            llm_info = {k: state.llm.get(k) for k in ("used", "model", "latency_ms", "cost_usd")}
            if not llm_info.get("used"):
                llm_info = {"used": False, "model": None, "latency_ms": None, "cost_usd": None}
            loaded_at = dt.datetime.now(dt.UTC)
            pii_dropped = [state.layout.headers[j] for j in sorted(state.pii)]
            mapping_list = [{"column": c, "field": f} for c, f in mapping_all.items()]

            # remaining steps (messages need the numbers above)
            if superseded:
                total_old = sum(s["rows"] for s in superseded)
                files = _q(sorted({s["filename"] for s in superseded}))
                key_fields = superseded[0]["key"]
                if key_fields:
                    same_sq = (
                        "me të njëjtin çelës ("
                        + " + ".join(ds.field(k).label["sq"].lower() for k in key_fields)
                        + ")"
                    )
                    same_en = (
                        "with the same key ("
                        + " + ".join(ds.field(k).label["en"].lower() for k in key_fields)
                        + ")"
                    )
                else:
                    same_sq, same_en = "(gjendje e plotë)", "(a full snapshot)"
                kept = sum(s["rows_remaining"] for s in superseded)
                kept_sq = f"; {_n(kept, 'sq')} rreshta të tjerë të tyre mbeten" if kept else ""
                kept_en = f"; {_n(kept, 'en')} of their other rows stay" if kept else ""
                log.add(
                    "supersede",
                    "info",
                    f"{_n(total_old, 'sq')} rreshta të një ngarkimi të mëparshëm ({files}) "
                    f"{same_sq} u zëvendësuan — pa numërim të dyfishtë{kept_sq}.",
                    f"{_n(total_old, 'en')} rows from an earlier load ({files}) {same_en} were "
                    f"replaced — no double counting{kept_en}.",
                )
            log.add(
                "insert",
                "ok",
                f"{_n(inserted, 'sq')} rreshta u ngarkuan në tabelën '{ds.table}', secili me "
                f"burimin ({source_id}) dhe numrin e rreshtit origjinal.",
                f"{_n(inserted, 'en')} rows loaded into table '{ds.table}', each with its source "
                f"({source_id}) and original row number.",
            )
            checked = [r for r in reconciliation if r["file_total"] is not None]
            passed = [r for r in checked if r["ok"]]
            label = "TOTALI"
            if state.layout.grand_total is not None:
                label = mask_personal(
                    next((v for v in state.layout.grand_total.cells if isinstance(v, str)), label)
                )
            if len(checked) == 1 and checked[0]["field"] == "row_count":
                rc = checked[0]
                log.add(
                    "reconcile",
                    "ok" if rc["ok"] else "warn",
                    f"Rakordimi me rreshtin '{label}': numri i rreshtave "
                    f"({_n(rc['loaded_sum'], 'sq')} / {_n(rc['file_total'], 'sq')}) "
                    + ("përputhet." if rc["ok"] else "nuk përputhet."),
                    f"Reconciliation with the '{label}' row: the row count "
                    f"({_n(rc['loaded_sum'], 'en')} / {_n(rc['file_total'], 'en')}) "
                    + ("matches." if rc["ok"] else "does not match."),
                )
            elif checked:
                log.add(
                    "reconcile",
                    "ok" if len(passed) == len(checked) else "warn",
                    f"Rakordimi me rreshtin '{label}': {len(passed)} nga {len(checked)} shuma "
                    "përputhen (toleranca: vetëm rrumbullakimi).",
                    f"Reconciliation with the '{label}' row: {len(passed)} of {len(checked)} "
                    "sums match (tolerance: rounding only).",
                )
            else:
                log.add(
                    "reconcile",
                    "info",
                    "Skedari nuk ka rresht totali për rakordim; shumat u regjistruan.",
                    "The file has no total row to reconcile against; sums were recorded.",
                )
            if recipe_saved:
                log.add(
                    "recipe",
                    "ok",
                    f"Receta u ruajt ({recipe_id}): herën tjetër ky format hartëzohet pa AI.",
                    f"Recipe saved ({recipe_id}): next time this format maps without AI.",
                )
            elif recipe_reused:
                log.add(
                    "recipe",
                    "ok",
                    f"Receta u ripërdor ({recipe_id}).",
                    f"Recipe reused ({recipe_id}).",
                )
            codes = [u["code"] for u in unlocked]
            log.add(
                "unlock",
                "ok" if codes else "info",
                (
                    f"U zhbllokuan {len(codes)} tregues: {', '.join(codes)}"
                    if codes
                    else "Asnjë tregues i ri"
                )
                + f" · mbulimi {cov['computable']}/{cov['total']}.",
                (
                    f"{len(codes)} indicators unlocked: {', '.join(codes)}"
                    if codes
                    else "No new indicators"
                )
                + f" · coverage {cov['computable']}/{cov['total']}.",
            )

            duration_ms = int((time.perf_counter() - started) * 1000)
            receipt = {
                "source_id": source_id,
                "filename": state.filename,
                "file_hash": state.file_hash,
                "dataset": ds.key,
                "dataset_name": dict(ds.name),
                "synthetic": state.synthetic,
                "rows_read": state.layout.rows_read,
                "rows_loaded": inserted,
                "rows_excluded": rows_excluded,
                "reconciliation": reconciliation,
                "pii_dropped": pii_dropped,
                "unit_multiplier": mult,
                "llm": llm_info,
                "recipe": {"saved": recipe_saved, "reused": recipe_reused, "recipe_id": recipe_id},
                "indicators_unlocked": unlocked,
                "coverage": {"computable": cov["computable"], "total": cov["total"]},
                "loaded_at": loaded_at.isoformat(timespec="seconds"),
                "duration_ms": duration_ms,
                # additive (not in the contract's minimum shape)
                "sheet": state.table.sheet,
                "header_row": state.layout.header_row,
                "steps": log.items,
                "column_errors": [
                    {
                        "field": k,
                        "column": state.layout.headers[fields[k]],
                        "count": len(v),
                        "rows": reg.row_ranges(v[:200]),
                    }
                    for k, v in col_errors.items()
                ],
                "superseded": superseded,
                "mapping": mapping_list,
            }
            con.execute(
                "INSERT INTO source (id, filename, file_hash, dataset, sheet, header_row, "
                "header_fingerprint, synthetic, rows_read, rows_loaded, rows_excluded_json, "
                "reconciliation_json, pii_dropped_json, unit_multiplier, mapping_json, recipe_id, "
                "recipe_reused, llm_json, loaded_at, duration_ms, receipt_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    source_id,
                    state.filename,
                    state.file_hash,
                    ds.key,
                    state.table.sheet,
                    state.layout.header_row,
                    fp,
                    state.synthetic,
                    state.layout.rows_read,
                    inserted,
                    json.dumps(rows_excluded, ensure_ascii=False),
                    json.dumps(reconciliation, ensure_ascii=False),
                    json.dumps(pii_dropped, ensure_ascii=False),
                    float(mult),
                    json.dumps(mapping_list, ensure_ascii=False),
                    recipe_id,
                    recipe_reused,
                    json.dumps(state.llm, ensure_ascii=False),
                    loaded_at.replace(tzinfo=None),
                    duration_ms,
                    json.dumps(receipt, ensure_ascii=False, default=str),
                ],
            )
            if not in_transaction:
                con.execute("COMMIT")
        except Exception:
            if not in_transaction:
                con.execute("ROLLBACK")
            raise
    return receipt


def commit(
    preview_id: str,
    dataset: str,
    mapping: Iterable[Any],
    save_recipe: bool = False,
    *,
    con: Cursor | None = None,
) -> dict:
    """``LoadReceipt`` for a cached preview; the preview is discarded after a successful load."""
    state = get_preview(preview_id)
    with _with_cursor(con) as cur:
        receipt = commit_state(state, dataset, mapping, save_recipe, con=cur)
    _cache_drop(preview_id)
    return receipt


def ingest_path(
    path: str | Path,
    dataset: str | None = None,
    *,
    save_recipe: bool = False,
    use_llm: bool = False,
    con: Cursor | None = None,
    in_transaction: bool = False,
) -> dict:
    """Preview + commit a file on disk with the proposed mapping (seed, CLI, tests).

    Uses rules (or a saved recipe) unless ``use_llm`` is true. Raises ``IngestError`` when the
    dataset is not recognised or a required field has no column.
    """
    p = Path(path)
    data = p.read_bytes()
    with _with_cursor(con) as cur:
        state = prepare(data, p.name, dataset=dataset, con=cur, use_llm=use_llm)
        if state.dataset is None:
            raise IngestError(
                "dataset_not_recognised",
                f"Grupi i të dhënave për '{p.name}' nuk u dallua.",
                f"The dataset of '{p.name}' was not recognised.",
            )
        mapping = [{"column": s.column, "field": s.field} for s in state.suggestions]
        return commit_state(
            state, state.dataset, mapping, save_recipe, con=cur, in_transaction=in_transaction
        )


# --------------------------------------------------------------------------------------------
# Sources, samples, demo reset
# --------------------------------------------------------------------------------------------


def _json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except ValueError:
        return default


def list_sources(con: Cursor) -> list[dict]:
    """``SourceInfo[]``, newest first."""
    _ensure_receipt_column(con)
    rows = con.execute(
        "SELECT id, filename, file_hash, dataset, synthetic, rows_read, rows_loaded, "
        "rows_excluded_json, reconciliation_json, pii_dropped_json, unit_multiplier, "
        "mapping_json, recipe_id, recipe_reused, llm_json, loaded_at, duration_ms, receipt_json "
        "FROM source ORDER BY loaded_at DESC, id"
    ).fetchall()
    out = []
    for r in rows:
        (sid, filename, fhash, dsk, synth, rread, rloaded, rexc, rec, pii, mult, mjson, rid,
         reused, ljson, loaded_at, dur, receipt_json) = r  # fmt: skip
        receipt = _json(receipt_json, None)
        if isinstance(receipt, dict):
            receipt.setdefault("mapping", _json(mjson, []))
            out.append(receipt)
            continue
        ds = DATASETS.get(dsk)
        llm = _json(ljson, {}) or {}
        out.append(
            {
                "source_id": sid,
                "filename": filename,
                "file_hash": fhash,
                "dataset": dsk,
                "dataset_name": dict(ds.name) if ds else t(dsk or "", dsk or ""),
                "synthetic": bool(synth),
                "rows_read": int(rread or 0),
                "rows_loaded": int(rloaded or 0),
                "rows_excluded": _json(rexc, []),
                "reconciliation": _json(rec, []),
                "pii_dropped": _json(pii, []),
                "unit_multiplier": int(mult or 1),
                "llm": {
                    "used": bool(llm.get("used")),
                    "model": llm.get("model"),
                    "latency_ms": llm.get("latency_ms"),
                    "cost_usd": llm.get("cost_usd"),
                },
                "recipe": {
                    "saved": bool(rid) and not reused,
                    "reused": bool(reused),
                    "recipe_id": rid,
                },
                "indicators_unlocked": [],
                "coverage": {"computable": 0, "total": 0},
                "loaded_at": loaded_at.isoformat() if loaded_at else None,
                "duration_ms": int(dur or 0),
                "mapping": _json(mjson, []),
            }
        )
    return out


def samples_dir() -> Path:
    return get_settings().samples_path


def load_manifest() -> dict:
    path = samples_dir() / "manifest.json"
    if not path.is_file():
        return {"files": []}
    return json.loads(path.read_text(encoding="utf-8"))


def sample_path(name: str) -> Path:
    """Path of a manifest-listed sample (exact name match only; no path traversal)."""
    names = {f["name"] for f in load_manifest().get("files", [])}
    if name not in names:
        raise IngestError(
            "sample_not_found",
            f"Skedari shembull '{name}' nuk ekziston.",
            f"Sample file '{name}' does not exist.",
            status_code=404,
        )
    base = samples_dir().resolve()
    path = (base / name).resolve()
    if path.parent != base or not path.is_file():
        raise IngestError(
            "sample_not_found",
            f"Skedari shembull '{name}' nuk ekziston.",
            f"Sample file '{name}' does not exist.",
            status_code=404,
        )
    return path


def sample_files(con: Cursor) -> list[dict]:
    """``SampleFile[]`` with size and whether a source with that filename is loaded."""
    loaded = {r[0] for r in con.execute("SELECT DISTINCT filename FROM source").fetchall()}
    out = []
    base = samples_dir()
    for f in load_manifest().get("files", []):
        path = base / f["name"]
        out.append(
            {
                "name": f["name"],
                "label": f.get("label") or t(f["name"], f["name"]),
                "dataset_hint": f.get("dataset_hint"),
                "envelope": f.get("envelope"),
                "preload": bool(f.get("preload")),
                "size_bytes": path.stat().st_size if path.is_file() else 0,
                "synthetic": bool(f.get("synthetic", True)),
                "loaded": f["name"] in loaded,
            }
        )
    return out


def reset_demo(con: Cursor | None = None, *, envelopes: bool = False) -> dict:
    """Drop all data (the LLM call log survives), clear recipes and previews, load the preload
    files from the manifest with rules mapping; ``envelopes=True`` also loads envelopes 1–3."""
    files = load_manifest().get("files", [])
    wanted = [f for f in files if f.get("preload")]
    if envelopes:
        wanted += sorted(
            (f for f in files if f.get("envelope") and not f.get("preload")),
            key=lambda f: f["envelope"],
        )
    receipts = []
    paths = [(sample_path(f["name"]), f.get("dataset_hint")) for f in wanted]
    with _WRITE_LOCK, _with_cursor(con) as cur:
        ensure_schema(cur)
        _ensure_receipt_column(cur)
        # One transaction: readers on other cursors see either the old data or the new, never
        # a missing table or half-loaded coverage (DuckDB MVCC).
        cur.execute("BEGIN TRANSACTION")
        try:
            clear_tables(cur)
            for path, hint in paths:
                receipts.append(
                    ingest_path(path, hint, use_llm=False, con=cur, in_transaction=True)
                )
            cov = reg.coverage(cur)
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
        clear_previews()
    return {
        "ok": True,
        "coverage": {"computable": cov["computable"], "total": cov["total"]},
        "loaded": [
            {
                "source_id": r["source_id"],
                "filename": r["filename"],
                "dataset": r["dataset"],
                "rows_loaded": r["rows_loaded"],
                "reconciled": all(x["ok"] for x in r["reconciliation"]),
            }
            for r in receipts
        ],
    }


def delete_recipes(con: Cursor) -> int:
    with _WRITE_LOCK:
        return recipes.delete_all(con)
