"""Plausibility checks ("signals", contract §5), evaluated by code on computed series.

Rules (a passport lists the ones that apply in ``checks``):

- ``placeholder_value``: a 0 or 1 where the neighbouring months are large, or the same value
  repeated for 3+ months in a series that otherwise varies (an unfilled or copied cell).
- ``swing``: a month-on-month change above 50% (above 20 percentage points for percentages)
  that also stands out, in the same direction, against the median of the earlier months
  (at least two, placeholders excluded). The second condition keeps one spike from firing
  twice (up, then back down), still catches a level shift that persists, and skips the
  warm-up of the first months of an export. Relative changes need a non-trivial base.
- ``rate_bounds``: a percentage outside 0–100%.
- ``off_target``: the latest value on the wrong side of the target (``warn`` when the gap is
  more than 10% of the target, ``info`` otherwise).
- ``parts_vs_total``: a contributing file whose loaded sums did not reconcile with its own
  total row at ingest (``source.reconciliation_json``).

Series-based rules also run per dimension when the passport has ``breakdown_sql`` (e.g.
waste by administrative unit, on-time rate by directorate). Copy is neutral: it describes
what the numbers show and suggests what to check; it never says a number is wrong.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from statistics import median

from app.catalog import L10n, t
from app.indicators.registry import (
    LOCALES,
    UNIT_DECIMALS,
    Passport,
    format_number,
    format_period,
    format_value,
    status_vs_target,
)

SWING_RELATIVE = 0.5
"""Relative month-on-month change that counts as a swing (strictly greater than 50%)."""
SWING_POINTS = 20.0
"""Percentage indicators: change in percentage points that counts as a swing."""
MIN_BASE: dict[str, float] = {
    "count": 20.0,
    "days": 2.0,
    "kg_per_resident": 5.0,
    "lek_per_ton": 100.0,
    "per_1000": 0.5,
}
"""Smallest previous value for which a relative change is meaningful, per unit."""
PLACEHOLDER_MAX = 1.0
PLACEHOLDER_NEIGHBOUR_MIN = 10.0
REPEAT_RUN = 3
REPEAT_MIN_POINTS = 5
OFF_TARGET_WARN_GAP = 0.10
MAX_PER_RULE = 3

RULE_LABELS: dict[str, L10n] = {
    "placeholder_value": t(
        "Vlera që duken të paplotësuara (0, 1 ose të përsëritura)",
        "Values that look unfilled (0, 1 or repeated)",
    ),
    "swing": t("Ndryshime të mëdha nga muaji në muaj", "Large month-on-month changes"),
    "rate_bounds": t("Përqindjet brenda 0–100%", "Percentages within 0–100%"),
    "off_target": t("Vlera kundrejt objektivit", "Value against the target"),
    "parts_vs_total": t(
        "Pjesët përputhen me totalin e skedarit", "Parts match the file's total row"
    ),
    "compute_error": t("Llogaritja e treguesit", "Indicator computation"),
}

MINUS = "−"


@dataclass(frozen=True)
class Point:
    period: str
    value: float | None


@dataclass
class Signal:
    rule: str
    severity: str
    message: L10n
    period: str | None
    magnitude: float = 0.0
    dimension: str | None = field(default=None, compare=False)

    def api(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": dict(self.message),
            "period": self.period,
        }


@dataclass(frozen=True)
class Reconciliation:
    """One reconciled field of one contributing source file."""

    filename: str
    field: str
    label: L10n
    file_total: float | None
    loaded_sum: float | None
    ok: bool


# --------------------------------------------------------------------------------------------
# Formatting helpers (code formats every number)
# --------------------------------------------------------------------------------------------


def _decimals(p: Passport, value: float | None) -> int:
    """Display decimals; small non-integer quantities keep one decimal (22,7 ton, not 23)."""
    d = p.decimals if p.decimals is not None else UNIT_DECIMALS.get(p.unit, 1)
    if d == 0 and value is not None and abs(value) < 100 and not float(value).is_integer():
        return 1
    return d


def _num(p: Passport, value: float | None, loc: str, decimals: int | None = None) -> str:
    """Number as displayed ("87,3%" for percentages, "22,7" otherwise), without the unit."""
    d = _decimals(p, value) if decimals is None else decimals
    return format_value(value, p.unit, loc, d)


def _unit(p: Passport, loc: str) -> str:
    return "" if p.unit == "percent" else f" {p.label[loc]}"


def _fmt(p: Passport, value: float | None, loc: str, decimals: int | None = None) -> str:
    """Value with its unit: "87,3%", "22,7 ton", "17.405 lekë/ton"."""
    text = _num(p, value, loc, decimals)
    return text if value is None else f"{text}{_unit(p, loc)}"


def _signed(text: str, negative: bool) -> str:
    return f"{MINUS if negative else '+'}{text}"


def _change_text(p: Passport, new: float, old: float, loc: str) -> str:
    """ "+94%" for quantities, "−23,2 pikë përqindjeje" for percentages."""
    if p.unit == "percent":
        diff = new - old
        points = "pikë përqindjeje" if loc == "sq" else "percentage points"
        return f"{_signed(format_number(abs(diff), 1, loc), diff < 0)} {points}"
    rel = new / old - 1
    return _signed(format_number(abs(rel) * 100, 0, loc), rel < 0) + "%"


def _prefix(dimension: str | None) -> str:
    return f"{dimension}: " if dimension else ""


# --------------------------------------------------------------------------------------------
# Series rules
# --------------------------------------------------------------------------------------------


def _placeholder_indexes(points: Sequence[Point], unit: str) -> dict[int, list[float]]:
    """Index → neighbour values for 0/1 values surrounded by large values."""
    if unit == "percent":  # 0% and 1% are legitimate rates
        return {}
    vals = [pt.value for pt in points]
    out: dict[int, list[float]] = {}
    for i, v in enumerate(vals):
        if v is None or abs(v) > PLACEHOLDER_MAX:
            continue
        neighbours = [vals[j] for j in (i - 1, i + 1) if 0 <= j < len(vals) and vals[j] is not None]
        if neighbours and min(abs(x) for x in neighbours) >= PLACEHOLDER_NEIGHBOUR_MIN:
            out[i] = neighbours  # type: ignore[assignment]
    return out


def _repeat_runs(points: Sequence[Point], unit: str) -> list[tuple[int, int]]:
    """(start, end) index pairs of 3+ identical consecutive values in a varying series.

    "Varying" means the points outside the run (placeholders excluded) take at least two
    distinct values, so a series that is flat by nature (a fixed contract quantity) is quiet.
    """
    vals = [pt.value for pt in points]
    if unit == "percent" or sum(v is not None for v in vals) < REPEAT_MIN_POINTS:
        return []
    placeholders = set(_placeholder_indexes(points, unit))
    runs, start = [], 0
    for i in range(1, len(vals) + 1):
        if i < len(vals) and vals[i] is not None and vals[i] == vals[start]:
            continue
        v = vals[start]
        if i - start >= REPEAT_RUN and v is not None and abs(v) > PLACEHOLDER_MAX:
            outside = {
                x
                for j, x in enumerate(vals)
                if x is not None and not start <= j < i and j not in placeholders
            }
            if len(outside) >= 2:
                runs.append((start, i - 1))
        start = i
    return runs


def placeholder_signals(
    p: Passport, points: Sequence[Point], dimension: str | None = None
) -> list[Signal]:
    out: list[Signal] = []
    for i, neighbours in _placeholder_indexes(points, p.unit).items():
        pt = points[i]
        msg: dict[str, str] = {}
        for loc in LOCALES:
            nb = [_num(p, x, loc) for x in neighbours]
            u = _unit(p, loc)
            if len(nb) == 2:
                ctx = (
                    f"ndërsa muajt fqinjë kanë {nb[0]} dhe {nb[1]}{u}"
                    if loc == "sq"
                    else f"while the neighbouring months have {nb[0]} and {nb[1]}{u}"
                )
            else:
                ctx = (
                    f"ndërsa muaji fqinj ka {nb[0]}{u}"
                    if loc == "sq"
                    else f"while the neighbouring month has {nb[0]}{u}"
                )
            head = f"{_prefix(dimension)}{_fmt(p, pt.value, loc)}"
            if loc == "sq":
                msg[loc] = (
                    f"{head} në {format_period(pt.period, loc)}, {ctx}. Kontrolloni sasinë "
                    "ose njësinë; mund të jetë një vlerë e paplotësuar."
                )
            else:
                msg[loc] = (
                    f"{head} in {format_period(pt.period, loc)}, {ctx}. Check the quantity "
                    "or unit; it may be a value that was not filled in."
                )
        out.append(
            Signal(
                "placeholder_value",
                "warn",
                msg,
                pt.period,
                magnitude=min(neighbours),
                dimension=dimension,
            )
        )
    for start, end in _repeat_runs(points, p.unit):
        first, last = points[start], points[end]
        n = end - start + 1
        msg = {}
        for loc in LOCALES:
            value = _fmt(p, first.value, loc)
            span = f"{format_period(first.period, loc)} – {format_period(last.period, loc)}"
            if loc == "sq":
                msg[loc] = (
                    f"{_prefix(dimension)}e njëjta vlerë, {value}, për {n} muaj radhazi "
                    f"({span}). Kontrolloni nëse vlera është kopjuar nga muaji i mëparshëm."
                )
            else:
                msg[loc] = (
                    f"{_prefix(dimension)}the same value, {value}, for {n} consecutive months "
                    f"({span}). Check whether the value was carried over from the previous "
                    "month."
                )
        out.append(
            Signal(
                "placeholder_value",
                "warn",
                msg,
                last.period,
                magnitude=float(n),
                dimension=dimension,
            )
        )
    return out


def swing_signals(
    p: Passport, points: Sequence[Point], dimension: str | None = None
) -> list[Signal]:
    known = [(i, pt) for i, pt in enumerate(points) if pt.value is not None]
    if len(known) < 3:
        return []
    skip = set(_placeholder_indexes(points, p.unit))
    min_base = MIN_BASE.get(p.unit, 0.0)
    out: list[Signal] = []
    for k in range(1, len(known)):
        i, pt = known[k]
        j, prev = known[k - 1]
        if i in skip or j in skip:
            continue
        v, pv = float(pt.value), float(prev.value)  # type: ignore[arg-type]
        earlier = [x.value for idx, x in known[:k] if idx not in skip]
        if len(earlier) < 2:  # warm-up: no baseline yet
            continue
        base = float(median(earlier))  # type: ignore[type-var]
        if p.unit == "percent":
            d_prev, d_base = v - pv, v - base
            hit = abs(d_prev) > SWING_POINTS and abs(d_base) > SWING_POINTS
            magnitude = abs(d_prev)
        else:
            if abs(pv) < min_base or abs(base) < min_base:
                continue
            d_prev, d_base = v / pv - 1, v / base - 1
            hit = abs(d_prev) > SWING_RELATIVE and abs(d_base) > SWING_RELATIVE
            magnitude = abs(d_prev) * 100
        if not hit or (d_prev > 0) != (d_base > 0):
            continue
        nxt = known[k + 1][1] if k + 1 < len(known) else None
        spike_back = False
        if nxt is not None and nxt.value is not None:
            if p.unit == "percent":
                spike_back = abs(nxt.value - base) <= SWING_POINTS / 2
            elif base:
                spike_back = abs(nxt.value / base - 1) <= SWING_RELATIVE / 2
        latest = known[-1][1]
        msg: dict[str, str] = {}
        for loc in LOCALES:
            head = f"{_prefix(dimension)}{_fmt(p, v, loc)}"
            change = _change_text(p, v, pv, loc)
            prev_txt = f"{format_period(prev.period, loc)} ({_fmt(p, pv, loc)})"
            if loc == "sq":
                text = (
                    f"{head} në {format_period(pt.period, loc)}, {change} kundrejt muajit "
                    f"{prev_txt}. "
                    "Ndryshim i madh nga muaji në muaj: kontrolloni nëse pasqyron një "
                    "ndryshim real apo një ndryshim në mënyrën e regjistrimit."
                )
                if spike_back:
                    text += f" Muaji pasardhës kthehet në {_fmt(p, nxt.value, loc)}."  # type: ignore[union-attr]
                elif latest.period != pt.period:
                    text += (
                        f" Vlera e fundit: {_fmt(p, latest.value, loc)} "
                        f"({format_period(latest.period, loc)})."
                    )
            else:
                text = (
                    f"{head} in {format_period(pt.period, loc)}, {change} compared with "
                    f"{prev_txt}. A large month-on-month change: check whether it reflects a "
                    "real change or a change in how it was recorded."
                )
                if spike_back:
                    text += f" The following month returns to {_fmt(p, nxt.value, loc)}."  # type: ignore[union-attr]
                elif latest.period != pt.period:
                    text += (
                        f" Latest value: {_fmt(p, latest.value, loc)} "
                        f"({format_period(latest.period, loc)})."
                    )
            msg[loc] = text
        out.append(Signal("swing", "warn", msg, pt.period, magnitude, dimension))
    return out


def rate_bounds_signals(
    p: Passport, value: float | None, period: str | None, points: Sequence[Point]
) -> list[Signal]:
    if p.unit != "percent":
        return []
    pts = [pt for pt in points if pt.value is not None]
    if value is not None and period is not None and all(pt.period != period for pt in pts):
        pts.append(Point(period, value))
    elif value is not None and period is not None:
        pts = [Point(pt.period, value) if pt.period == period else pt for pt in pts]
    bad = [pt for pt in pts if pt.value < -1e-9 or pt.value > 100 + 1e-9]  # type: ignore[operator]
    if not bad:
        return []
    last = max(bad, key=lambda pt: pt.period)
    msg: dict[str, str] = {}
    for loc in LOCALES:
        v = _fmt(p, last.value, loc)
        if loc == "sq":
            text = (
                f"{v} në {format_period(last.period, loc)} është jashtë intervalit 0–100%. "
                "Kontrolloni planin, faktin ose njësinë e kolonave."
            )
            if len(bad) > 1:
                text += f" Gjithsej {len(bad)} muaj jashtë intervalit."
        else:
            text = (
                f"{v} in {format_period(last.period, loc)} is outside the 0–100% range. "
                "Check the plan, the actual figures or the column unit."
            )
            if len(bad) > 1:
                text += f" {len(bad)} months in total are outside the range."
        msg[loc] = text
    return [Signal("rate_bounds", "warn", msg, last.period, float(len(bad)))]


def off_target_signal(p: Passport, value: float | None, period: str | None) -> list[Signal]:
    if status_vs_target(p, value) != "off_track" or value is None or p.target is None:
        return []
    gap = value - p.target
    rel = abs(gap) / abs(p.target) if p.target else 1.0
    severity = "warn" if rel > OFF_TARGET_WARN_GAP else "info"
    msg: dict[str, str] = {}
    for loc in LOCALES:
        v, tgt = _fmt(p, value, loc), _fmt(p, p.target, loc, 0)
        diff = _change_text(p, value, p.target, loc) if p.unit == "percent" else None
        if diff is None:
            diff = _signed(_fmt(p, abs(gap), loc), gap < 0)
        when = format_period(period, loc)
        if loc == "sq":
            side = (
                "nën objektivin" if p.direction == "higher_better" else "mbi kufirin e objektivit"
            )
            msg[loc] = f"{v} në {when}, {side} {tgt} ({diff})."
        else:
            side = (
                "below the target of" if p.direction == "higher_better" else "above the target of"
            )
            msg[loc] = f"{v} in {when}, {side} {tgt} ({diff})."
    return [Signal("off_target", severity, msg, period, rel * 100)]


def parts_vs_total_signals(recons: Iterable[Reconciliation]) -> list[Signal]:
    out = []
    for r in recons:
        if r.ok or r.file_total is None:
            continue
        msg: dict[str, str] = {}
        for loc in LOCALES:
            loaded = format_number(r.loaded_sum, 2, loc) if r.loaded_sum is not None else "—"
            total = format_number(r.file_total, 2, loc)
            label = r.label.get(loc) or r.field
            if loc == "sq":
                msg[loc] = (
                    f"{r.filename}: shuma e ngarkuar e «{label}» është {loaded}, ndërsa rreshti "
                    f"i totalit në skedar jep {total}. Kontrolloni rreshtat e përjashtuar ose "
                    "njësinë."
                )
            else:
                msg[loc] = (
                    f"{r.filename}: the loaded sum of “{label}” is {loaded}, while the file's "
                    f"total row shows {total}. Check the excluded rows or the unit."
                )
        diff = abs((r.loaded_sum or 0.0) - r.file_total)
        out.append(Signal("parts_vs_total", "warn", msg, None, diff))
    return out


# --------------------------------------------------------------------------------------------
# Reconciliation records written by the ingest pipeline
# --------------------------------------------------------------------------------------------


def _as_float(v: object) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def parse_reconciliation(filename: str, raw: object) -> list[Reconciliation]:
    """Read ``source.reconciliation_json`` (a list of LoadReceipt reconciliation items).

    Tolerates a JSON string or a decoded object, a list of items, ``{"items": [...]}``, or a
    ``{field: {...}}`` mapping. Items without an explicit ``ok`` are compared with a small
    tolerance (0.5 or 0.01%).
    """
    if raw in (None, ""):
        return []
    try:
        data = json.loads(raw) if isinstance(raw, str | bytes) else raw
    except ValueError:
        return []
    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            data = data["items"]
        else:
            data = [
                {"field": k, **v} if isinstance(v, dict) else {"field": k} for k, v in data.items()
            ]
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        fld = str(item.get("field") or "")
        label = item.get("label")
        if isinstance(label, str):
            label = {"sq": label, "en": label}
        if not isinstance(label, dict):
            label = {"sq": fld, "en": fld}
        file_total = _as_float(item.get("file_total"))
        loaded = _as_float(item.get("loaded_sum"))
        ok = item.get("ok")
        if not isinstance(ok, bool):
            ok = (
                file_total is None
                or loaded is None
                or abs(file_total - loaded) <= max(0.5, abs(file_total) * 1e-4)
            )
        out.append(Reconciliation(filename, fld, label, file_total, loaded, ok))
    return out


# --------------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------------

_SEVERITY_ORDER = {"warn": 0, "info": 1}


def evaluate(
    p: Passport,
    *,
    value: float | None,
    period: str | None,
    series: Sequence[Point],
    breakdown: dict[str, list[Point]] | None = None,
    reconciliations: Iterable[Reconciliation] = (),
) -> list[Signal]:
    """All signals for one computed passport, strongest first, at most 3 per rule."""
    by_rule: dict[str, list[Signal]] = {}
    dims = breakdown or {}
    for rule in p.checks:
        found: list[Signal] = []
        if rule == "placeholder_value":
            found += placeholder_signals(p, series)
            for dim, pts in dims.items():
                found += placeholder_signals(p, pts, dim)
        elif rule == "swing":
            found += swing_signals(p, series)
            for dim, pts in dims.items():
                found += swing_signals(p, pts, dim)
        elif rule == "rate_bounds":
            found += rate_bounds_signals(p, value, period, series)
        elif rule == "off_target":
            found += off_target_signal(p, value, period)
        elif rule == "parts_vs_total":
            found += parts_vs_total_signals(reconciliations)
        found.sort(key=lambda s: (_SEVERITY_ORDER[s.severity], -s.magnitude, s.period or ""))
        by_rule[rule] = found[:MAX_PER_RULE]
    ordered = [s for rule in p.checks for s in by_rule.get(rule, [])]
    ordered.sort(key=lambda s: _SEVERITY_ORDER[s.severity])  # stable: keeps the rule order
    return ordered


@dataclass(frozen=True)
class Acceptance:
    """A signal rule accepted for one indicator, with the reason ("accept with reason")."""

    rule: str
    reason: str
    ts: str


def accepted_message(ack: Acceptance, signal: Signal) -> L10n:
    day = ack.ts[:10]
    return {
        "sq": f"Pranuar më {day}: {ack.reason} — {signal.message['sq']}",
        "en": f"Accepted on {day}: {ack.reason} — {signal.message['en']}",
    }


def check_results(
    p: Passport,
    signals: Sequence[Signal],
    accepted: Sequence[tuple[Signal, Acceptance]] = (),
) -> list[dict]:
    """``Passport.checks``: one entry per rule the passport declares.

    A rule whose signals were all accepted with a reason counts as passed; its message keeps
    the reason and the original observation, so the decision stays visible.
    """
    out = []
    for rule in p.checks:
        hits = [s for s in signals if s.rule == rule]
        acks = [(s, a) for s, a in accepted if s.rule == rule]
        if hits:
            message: L10n | None = dict(hits[0].message)
        elif acks:
            message = accepted_message(acks[0][1], acks[0][0])
        else:
            message = None
        out.append(
            {
                "rule": rule,
                "label": dict(RULE_LABELS.get(rule, t(rule, rule))),
                "passed": not hits,
                "message": message,
            }
        )
    return out
