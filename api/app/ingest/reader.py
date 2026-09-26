"""Step 1 — read a CSV/XLSX/XLS export into a grid of cells, exactly as the department sent it.

- CSV: decoded as UTF-8 (with or without BOM), falling back to cp1252 then latin-1; the delimiter
  comes from ``csv.Sniffer`` and is checked for a consistent column count (``;`` files with a
  decimal comma are the norm in Albanian exports).
- XLSX: openpyxl with ``data_only=True`` (cached formula values); merged cells are forward-filled
  so every cell of a merged range carries the top-left value.
- XLS: xlrd, with Excel date cells turned into datetimes and merged ranges forward-filled.

The first sheet that contains data is read. Row ``i`` of ``RawTable.rows`` is row ``i + 1`` of
the original file/sheet, which is what ``row_no`` records for lineage.
"""

from __future__ import annotations

import contextlib
import csv
import io
import re
import unicodedata
import zipfile
import zlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any
from xml.etree import ElementTree as ET

from app.ingest.errors import IngestError

MAX_BYTES = 15 * 1024 * 1024
"""Upload limit (15 MB)."""
MAX_UNZIPPED_BYTES = 250 * 1024 * 1024
"""Guard against zip bombs disguised as .xlsx."""
MAX_ROWS = 200_000
ALLOWED_EXTENSIONS = (".csv", ".xlsx", ".xls")
_DELIMITERS = ";,\t|"

Cell = Any


@dataclass
class RawTable:
    kind: str
    """``csv`` | ``xlsx`` | ``xls``."""
    rows: list[list[Cell]]
    ncols: int
    sheet: str | None = None
    sheets_with_data: list[str] = field(default_factory=list)
    merged: list[tuple[int, int, int, int]] = field(default_factory=list)
    """Merged ranges as 0-based inclusive ``(row0, col0, row1, col1)``."""
    encoding: str | None = None
    delimiter: str | None = None


# --------------------------------------------------------------------------------------------
# Filenames and limits
# --------------------------------------------------------------------------------------------

_UNSAFE_CHARS_RE = re.compile(r"[^\w.\- ()\[\]+,]", re.UNICODE)


def sanitize_filename(name: str | None) -> str:
    """Basename only, no control/path characters, at most 120 characters.

    >>> sanitize_filename("../../etc/pässwd.csv")
    'pässwd.csv'
    """
    raw = unicodedata.normalize("NFC", str(name or ""))
    raw = raw.replace("\\", "/")
    base = PurePath(raw).name if "/" in raw else raw
    base = "".join(ch for ch in base if unicodedata.category(ch)[0] != "C")
    base = _UNSAFE_CHARS_RE.sub("_", base).strip(" .")
    if not base:
        base = "skedar"
    if len(base) > 120:
        stem, dot, ext = base.rpartition(".")
        base = (stem[: 120 - len(ext) - 1] + dot + ext) if dot and len(ext) <= 5 else base[:120]
    return base


def extension_of(filename: str) -> str:
    return PurePath(filename).suffix.casefold()


def check_upload(data: bytes, filename: str) -> str:
    """Validate size and extension; returns the lower-case extension."""
    ext = extension_of(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise IngestError(
            "unsupported_file_type",
            f"Lloji i skedarit '{ext or '?'}' nuk pranohet. Ngarkoni .csv, .xlsx ose .xls.",
            f"File type '{ext or '?'}' is not accepted. Upload a .csv, .xlsx or .xls file.",
            status_code=415,
        )
    if len(data) > MAX_BYTES:
        raise IngestError(
            "file_too_large",
            "Skedari është më i madh se 15 MB.",
            "The file is larger than 15 MB.",
            status_code=413,
        )
    if not data:
        raise IngestError("empty_file", "Skedari është bosh.", "The file is empty.")
    return ext


def _unreadable(detail: str) -> IngestError:
    return IngestError(
        "unreadable_file",
        f"Skedari nuk mund të lexohet ({detail}).",
        f"The file could not be read ({detail}).",
    )


# --------------------------------------------------------------------------------------------
# Cells
# --------------------------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")


def clean_cell(value: Cell) -> Cell:
    """Strings trimmed (``""`` → None); integral floats from Excel become ints."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.replace(" ", " ").strip()
        return text or None
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        if value != value:  # NaN
            return None
        if value.is_integer() and abs(value) < 1e15:
            return int(value)
    return value


def _finish(rows: list[list[Cell]]) -> tuple[list[list[Cell]], int]:
    """Trim trailing empty rows/columns and pad every row to the same width."""
    while rows and all(v is None for v in rows[-1]):
        rows.pop()
    ncols = 0
    for r in rows:
        for j in range(len(r) - 1, -1, -1):
            if r[j] is not None:
                ncols = max(ncols, j + 1)
                break
    out = [(r + [None] * ncols)[:ncols] for r in rows]
    return out, ncols


def _forward_fill(rows: list[list[Cell]], merged: list[tuple[int, int, int, int]]) -> None:
    for r0, c0, r1, c1 in merged:
        if r0 >= len(rows):
            continue
        value = rows[r0][c0] if c0 < len(rows[r0]) else None
        if value is None:
            continue
        for r in range(r0, min(r1, len(rows) - 1) + 1):
            row = rows[r]
            if len(row) <= c1:
                row.extend([None] * (c1 + 1 - len(row)))
            for c in range(c0, c1 + 1):
                row[c] = value


# --------------------------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------------------------


def _utf16_guess(data: bytes) -> str | None:
    """``utf-16`` for a UTF-16 BOM; ``utf-16-le``/``-be`` when many NUL bytes suggest UTF-16
    without a BOM (Excel "Unicode text" and some ERP exports)."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    head = data[:1000]
    if len(head) >= 4 and head.count(0) > len(head) // 10:
        even = head[0::2].count(0)
        odd = head[1::2].count(0)
        return "utf-16-le" if odd >= even else "utf-16-be"
    return None


def decode_text(data: bytes) -> tuple[str, str]:
    """Decode UTF-16 (BOM or NUL-byte heuristic), then utf-8-sig, then cp1252, then latin-1
    (never fails)."""
    candidates = ["utf-8-sig", "cp1252"]
    utf16 = _utf16_guess(data)
    if utf16:
        candidates.insert(0, utf16)
    for enc in candidates:
        try:
            text = data.decode(enc)
        except UnicodeDecodeError:
            continue
        if enc == "utf-16" and text.startswith("\ufeff"):
            text = text[1:]
        return text, enc
    return data.decode("latin-1"), "latin-1"


def _consistency(lines: list[str], delim: str) -> tuple[float, int]:
    """(share of lines with the modal field count, modal count) for ``delim``."""
    counts = [len(next(csv.reader([ln], delimiter=delim))) for ln in lines if ln.strip()]
    if not counts:
        return 0.0, 1
    modal, freq = Counter(counts).most_common(1)[0]
    return freq / len(counts), modal


def sniff_delimiter(text: str) -> str | None:
    lines = text.splitlines()[:60]
    sample = "\n".join(lines)
    candidates: list[str] = []
    with contextlib.suppress(csv.Error):
        candidates.append(csv.Sniffer().sniff(sample, delimiters=_DELIMITERS).delimiter)
    candidates.extend(d for d in _DELIMITERS if d not in candidates)
    best: tuple[float, int, str] | None = None
    for i, d in enumerate(candidates):
        share, modal = _consistency(lines, d)
        if modal < 2:
            continue
        if i == 0 and share >= 0.8:
            return d  # the sniffer's answer is consistent: trust it
        score = (share, modal, d)
        if best is None or score[:2] > best[:2]:
            best = score
    return best[2] if best else None


def read_csv(data: bytes) -> RawTable:
    text, encoding = decode_text(data)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    delimiter = sniff_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter or ",")
    rows: list[list[Cell]] = []
    try:
        for i, rec in enumerate(reader):
            if i >= MAX_ROWS:
                raise _unreadable(f"more than {MAX_ROWS:,} rows")
            rows.append([clean_cell(v) for v in rec])
    except csv.Error as exc:
        raise _unreadable(str(exc)) from exc
    rows, ncols = _finish(rows)
    return RawTable(
        kind="csv",
        rows=rows,
        ncols=ncols,
        encoding=encoding,
        delimiter=delimiter,
    )


# --------------------------------------------------------------------------------------------
# XLSX
# --------------------------------------------------------------------------------------------


def _check_zip(data: bytes) -> None:
    """Refuse archives that expand past ``MAX_UNZIPPED_BYTES``: the declared sizes first, then
    the bytes actually decompressed (declared sizes in a zip header can lie)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if sum(i.file_size for i in infos) > MAX_UNZIPPED_BYTES:
                raise _unreadable("the workbook expands to more than 250 MB")
            total = 0
            for info in infos:
                with zf.open(info) as fh:
                    while chunk := fh.read(1 << 20):
                        total += len(chunk)
                        if total > MAX_UNZIPPED_BYTES:
                            raise _unreadable("the workbook expands to more than 250 MB")
    except (zipfile.BadZipFile, zlib.error, EOFError) as exc:
        raise _unreadable("not a valid .xlsx archive") from exc


def _merged_ranges(ws: Any) -> list[tuple[int, int, int, int]]:
    """Merged ranges of a read-only sheet, streamed from its XML (read-only sheets do not
    expose ``merged_cells``)."""
    from openpyxl.utils.cell import range_boundaries

    out: list[tuple[int, int, int, int]] = []
    try:
        with ws._get_source() as src:
            for _event, el in ET.iterparse(src, events=("end",)):
                tag = el.tag.rsplit("}", 1)[-1]
                if tag == "mergeCell":
                    ref = el.get("ref")
                    if ref and ":" in ref:
                        c0, r0, c1, r1 = range_boundaries(ref)
                        out.append((r0 - 1, c0 - 1, r1 - 1, c1 - 1))
                el.clear()
    except (ET.ParseError, ValueError, TypeError, AttributeError, KeyError):
        return out
    return out


def read_xlsx(data: bytes) -> RawTable:
    """Read the first visible sheet with data, streaming (openpyxl read-only mode) and stopping
    at ``MAX_ROWS``, so a large workbook never becomes a grid of Cell objects in memory."""
    from openpyxl import load_workbook

    _check_zip(data)
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises many types for corrupt files
        raise _unreadable(type(exc).__name__) from exc
    try:
        chosen = None
        with_data: list[str] = []
        for ws in wb.worksheets:
            if getattr(ws, "sheet_state", "visible") != "visible":
                continue
            ws.reset_dimensions()  # the <dimension> tag of some exporters is wrong ("A1")
            has_data = any(
                v is not None and str(v).strip() != ""
                for row in ws.iter_rows(values_only=True, max_row=200)
                for v in row
            )
            if has_data:
                with_data.append(ws.title)
                chosen = chosen or ws
        if chosen is None:
            raise _unreadable("no sheet contains data")
        rows: list[list[Cell]] = []
        for i, row in enumerate(chosen.iter_rows(values_only=True)):
            if i >= MAX_ROWS:
                raise _unreadable(f"more than {MAX_ROWS:,} rows")
            rows.append([clean_cell(v) for v in row])
        merged = _merged_ranges(chosen)
        title = chosen.title
    except IngestError:
        raise
    except Exception as exc:  # corrupt sheet XML
        raise _unreadable(type(exc).__name__) from exc
    finally:
        wb.close()
    _forward_fill(rows, merged)
    rows, ncols = _finish(rows)
    return RawTable(
        kind="xlsx",
        rows=rows,
        ncols=ncols,
        sheet=title,
        sheets_with_data=with_data,
        merged=merged,
    )


# --------------------------------------------------------------------------------------------
# XLS (legacy)
# --------------------------------------------------------------------------------------------


def _xls_value(cell, datemode: int) -> Cell:
    import xlrd

    ctype = cell.ctype
    if ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK, xlrd.XL_CELL_ERROR):
        return None
    if ctype == xlrd.XL_CELL_DATE:
        try:
            return xlrd.xldate_as_datetime(cell.value, datemode)
        except Exception:
            return clean_cell(cell.value)
    if ctype == xlrd.XL_CELL_BOOLEAN:
        return bool(cell.value)
    return clean_cell(cell.value)


def read_xls(data: bytes) -> RawTable:
    import xlrd

    try:
        try:
            book = xlrd.open_workbook(file_contents=data, formatting_info=True)
        except Exception:
            book = xlrd.open_workbook(file_contents=data)
    except Exception as exc:
        raise _unreadable(type(exc).__name__) from exc
    chosen = None
    with_data: list[str] = []
    for sh in book.sheets():
        if sh.nrows and any(
            sh.cell_value(r, c) not in ("", None)
            for r in range(min(sh.nrows, 200))
            for c in range(sh.ncols)
        ):
            with_data.append(sh.name)
            chosen = chosen or sh
    if chosen is None:
        raise _unreadable("no sheet contains data")
    if chosen.nrows > MAX_ROWS:
        raise _unreadable(f"more than {MAX_ROWS:,} rows")
    rows = [
        [_xls_value(chosen.cell(r, c), book.datemode) for c in range(chosen.ncols)]
        for r in range(chosen.nrows)
    ]
    merged = [(r0, c0, r1 - 1, c1 - 1) for r0, r1, c0, c1 in getattr(chosen, "merged_cells", [])]
    _forward_fill(rows, merged)
    rows, ncols = _finish(rows)
    return RawTable(
        kind="xls",
        rows=rows,
        ncols=ncols,
        sheet=chosen.name,
        sheets_with_data=with_data,
        merged=merged,
    )


def read_table(data: bytes, filename: str) -> RawTable:
    """Read an upload after ``check_upload``; dispatches on extension, then on content."""
    ext = check_upload(data, filename)
    if ext == ".xlsx" or (ext == ".xls" and data[:2] == b"PK"):
        table = read_xlsx(data)
    elif ext == ".xls":
        table = read_xls(data)
    else:
        table = read_csv(data)
    if not table.rows:
        raise _unreadable("no rows")
    return table
