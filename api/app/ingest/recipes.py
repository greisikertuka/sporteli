"""Step 6 — mapping recipes keyed by header fingerprint, with format-drift detection.

A recipe remembers the confirmed column→field mapping of one export format. The fingerprint is
``sha1(dataset | normalised header list)``: the same export next month maps without AI. When a
file of the same dataset shares at least half of its headers with a recipe but the fingerprint
differs, the format has drifted: renamed / missing / added columns are reported and the changed
columns go back through mapping (and a question), instead of being mapped silently.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from dataclasses import dataclass

import duckdb
from rapidfuzz import fuzz

from app.catalog import normalize_text

PARTIAL_OVERLAP = 0.5


def fingerprint(dataset: str, headers: list[str]) -> str:
    """Stable fingerprint of an export format (dataset + normalised header list, in order)."""
    norm = "|".join(normalize_text(h) for h in headers)
    return hashlib.sha1(f"{dataset}|{norm}".encode()).hexdigest()[:16]


@dataclass
class Recipe:
    id: str
    dataset: str
    fingerprint: str
    headers: list[str]
    mapping: dict[str, str | None]
    """Column name → field key (None = ignored)."""
    created_at: str | None
    from_filename: str | None

    def api(self) -> dict:
        return {
            "id": self.id,
            "dataset": self.dataset,
            "fingerprint": self.fingerprint,
            "columns": len(self.headers),
            "mapping": [{"column": c, "field": f} for c, f in self.mapping.items()],
            "created_at": self.created_at,
            "from_filename": self.from_filename,
        }


def _row_to_recipe(row: tuple) -> Recipe:
    rid, dataset, fp, mapping_json, created_at, from_filename = row
    try:
        payload = json.loads(mapping_json or "{}")
    except ValueError:
        payload = {}
    if isinstance(payload, list):  # tolerate a bare mapping list
        payload = {"mapping": payload}
    items = payload.get("mapping") or []
    mapping = {str(m.get("column")): m.get("field") for m in items if isinstance(m, dict)}
    headers = payload.get("headers") or list(mapping)
    return Recipe(
        id=rid,
        dataset=dataset,
        fingerprint=fp,
        headers=[str(h) for h in headers],
        mapping=mapping,
        created_at=created_at.isoformat() if isinstance(created_at, dt.datetime) else None,
        from_filename=from_filename,
    )


_SELECT = (
    "SELECT id, dataset, header_fingerprint, mapping_json, created_at, from_filename "
    "FROM mapping_recipe"
)


def find_exact(con: duckdb.DuckDBPyConnection, dataset: str, fp: str) -> Recipe | None:
    row = con.execute(
        f"{_SELECT} WHERE dataset = ? AND header_fingerprint = ? ORDER BY created_at DESC LIMIT 1",
        [dataset, fp],
    ).fetchone()
    return _row_to_recipe(row) if row else None


def overlap(a: list[str], b: list[str]) -> float:
    sa, sb = {normalize_text(x) for x in a}, {normalize_text(x) for x in b}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(len(sa), len(sb))


def find_partial(con: duckdb.DuckDBPyConnection, dataset: str, headers: list[str]) -> Recipe | None:
    """The recipe of ``dataset`` sharing the most headers (at least half) with ``headers``."""
    rows = con.execute(
        f"{_SELECT} WHERE dataset = ? ORDER BY created_at DESC", [dataset]
    ).fetchall()
    best: tuple[float, Recipe] | None = None
    for row in rows:
        r = _row_to_recipe(row)
        score = overlap(r.headers, headers)
        if score >= PARTIAL_OVERLAP and (best is None or score > best[0]):
            best = (score, r)
    return best[1] if best else None


@dataclass
class Drift:
    renamed: list[tuple[str, str, str | None]]
    """``(old header, new header, field)``."""
    missing: list[str]
    added: list[str]

    def api(self) -> dict:
        return {
            "renamed": [f"{old} → {new}" for old, new, _ in self.renamed],
            "missing": list(self.missing),
            "added": list(self.added),
        }

    @property
    def empty(self) -> bool:
        return not (self.renamed or self.missing or self.added)


def drift(recipe: Recipe, headers: list[str], proposed: dict[str, str | None]) -> Drift:
    """Compare a recipe's headers with a new file's headers.

    A header that disappeared is paired with a new header when the new one is proposed for the
    same field (or, failing that, when the names are very similar): that is a rename.
    """
    old_norm = {normalize_text(h): h for h in recipe.headers}
    new_norm = {normalize_text(h): h for h in headers}
    missing = [h for n, h in old_norm.items() if n not in new_norm]
    added = [h for n, h in new_norm.items() if n not in old_norm]
    renamed: list[tuple[str, str, str | None]] = []
    for old in list(missing):
        field = recipe.mapping.get(old)
        partner = None
        if field:
            partner = next((new for new in added if proposed.get(new) == field), None)
        if partner is None:
            scored = [(fuzz.ratio(normalize_text(old), normalize_text(new)), new) for new in added]
            scored = [s for s in scored if s[0] >= 80]
            if scored:
                partner = max(scored)[1]
        if partner is not None:
            renamed.append((old, partner, field))
            missing.remove(old)
            added.remove(partner)
    return Drift(renamed=renamed, missing=missing, added=added)


def save(
    con: duckdb.DuckDBPyConnection,
    *,
    dataset: str,
    fp: str,
    headers: list[str],
    mapping: dict[str, str | None],
    from_filename: str,
) -> str:
    """Insert or replace the recipe for ``(dataset, fingerprint)``; returns its id."""
    rid = f"rcp-{uuid.uuid4().hex[:10]}"
    payload = {
        "headers": list(headers),
        "mapping": [{"column": c, "field": f} for c, f in mapping.items()],
    }
    con.execute(
        "DELETE FROM mapping_recipe WHERE dataset = ? AND header_fingerprint = ?", [dataset, fp]
    )
    con.execute(
        "INSERT INTO mapping_recipe (id, dataset, header_fingerprint, mapping_json, created_at, "
        "from_filename) VALUES (?, ?, ?, ?, ?, ?)",
        [
            rid,
            dataset,
            fp,
            json.dumps(payload, ensure_ascii=False),
            dt.datetime.now(dt.UTC).replace(tzinfo=None),
            from_filename,
        ],
    )
    return rid


def list_all(con: duckdb.DuckDBPyConnection) -> list[Recipe]:
    return [
        _row_to_recipe(r) for r in con.execute(f"{_SELECT} ORDER BY created_at DESC").fetchall()
    ]


def delete_all(con: duckdb.DuckDBPyConnection) -> int:
    n = con.execute("SELECT count(*) FROM mapping_recipe").fetchone()[0]
    con.execute("DELETE FROM mapping_recipe")
    return int(n)
