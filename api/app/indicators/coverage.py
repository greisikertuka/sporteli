"""Coverage packs: how far the engine reaches a national indicator list (contract §3, §7).

``al_smp.yaml`` lists the 52 indicators of SMP 2024 Annex A with a base state. Items mapped
to a core passport are reported ``computable`` only while that passport is computable from
the loaded exports; otherwise they are ``missing`` and name the owner of the missing export.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

import duckdb
import yaml
from pydantic import BaseModel, ConfigDict

from app.catalog import OWNERS, POPULATION_BASES, get_dataset
from app.indicators import registry as reg

PackState = Literal["computable", "missing", "document", "national", "manual"]
STATES: tuple[PackState, ...] = ("computable", "missing", "document", "national", "manual")


class CoverageItemDef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    number: int
    name_sq: str
    base_state: PackState
    passport_code: str | None = None
    owner: str | None = None
    note: dict[str, str] | None = None


class CoverageAreaDef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str
    name: dict[str, str]
    items: list[CoverageItemDef]


class CoveragePack(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    pack: str
    version: str
    source: str
    label: dict[str, str]
    approval: Literal["pending", "approved"]
    owners: dict[str, dict[str, str]] = {}
    notes: dict[str, dict[str, str]] = {}
    areas: list[CoverageAreaDef]

    @property
    def items(self) -> list[tuple[CoverageAreaDef, CoverageItemDef]]:
        return [(a, it) for a in self.areas for it in a.items]

    def owner_name(self, key: str | None) -> dict[str, str] | None:
        if key is None:
            return None
        if key in OWNERS:
            return dict(OWNERS[key])
        return dict(self.owners[key])


@lru_cache
def load_coverage_pack(name: str = "al_smp") -> CoveragePack:
    """Load and validate ``packs/{name}.yaml`` (cached). ``KeyError`` if it is not one."""
    path = reg.PACKS_DIR / f"{name}.yaml"
    if not path.is_file():
        raise KeyError(f"unknown coverage pack: {name}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "areas" not in raw:
        raise KeyError(f"not a coverage pack: {name}")
    pack = CoveragePack.model_validate(raw)
    numbers = [it.number for _, it in pack.items]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError(f"{name}: item numbers must run 1..N in order")
    core = reg.load_pack("core_kpi")
    for _, it in pack.items:
        if it.passport_code is not None:
            core.get(it.passport_code)  # raises on unknown codes
        if it.base_state == "computable" and it.passport_code is None:
            raise ValueError(f"{name} #{it.number}: computable items need a passport_code")
        if it.owner is not None and it.owner not in OWNERS and it.owner not in pack.owners:
            raise ValueError(f"{name} #{it.number}: unknown owner {it.owner!r}")
    return pack


def _missing_note(code: str, datasets: list[str]) -> dict[str, str]:
    names_sq = ", ".join(get_dataset(d).export_name["sq"] for d in datasets)
    names_en = ", ".join(get_dataset(d).export_name["en"] for d in datasets)
    return {
        "sq": f"Mungon: {names_sq} · do të llogaritet nga pasaporta {code}.",
        "en": f"Missing: {names_en} · will be computed by passport {code}.",
    }


def coverage(con: duckdb.DuckDBPyConnection, name: str = "al_smp") -> dict:
    """``Coverage``: every item with its live state, owner and note, plus counts."""
    pack = load_coverage_pack(name)
    core = reg.load_pack("core_kpi")
    states = reg.states(con, "core_kpi")
    basis = reg.get_population_basis(con)
    items = []
    for area_def, it in pack.items:
        state: PackState = it.base_state
        owner = pack.owner_name(it.owner)
        note = dict(it.note) if it.note else None
        if it.base_state == "computable":
            p = core.get(it.passport_code)  # type: ignore[arg-type]
            if states[p.code] == "computable":
                owner = dict(OWNERS[p.owner])
                if p.uses_basis and note:
                    b = POPULATION_BASES[basis]
                    note = {
                        "sq": f"{note['sq']} Baza e popullsisë: {b['sq']}.",
                        "en": f"{note['en']} Population basis: {b['en']}.",
                    }
            else:
                state = "missing"
                gaps = reg.missing_datasets(p, con)
                owner = dict(OWNERS[get_dataset(gaps[0]).owner]) if gaps else dict(OWNERS[p.owner])
                note = _missing_note(p.code, gaps)
        if note is None and state in pack.notes:
            note = dict(pack.notes[state])
        items.append(
            {
                "number": it.number,
                "area": dict(area_def.name),
                "name_sq": it.name_sq,
                "state": state,
                "passport_code": it.passport_code,
                "owner": owner,
                "note": note,
            }
        )
    counts = {s: sum(1 for i in items if i["state"] == s) for s in STATES}
    return {
        "pack": pack.pack,
        "label": dict(pack.label),
        "approval": pack.approval,
        "counts": counts,
        "total": len(items),
        "items": items,
    }
