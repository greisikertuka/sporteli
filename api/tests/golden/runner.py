"""Scoring the copilot against the golden set (shared by the tests and scripts/run_eval.py)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

import yaml

GOLDEN = Path(__file__).resolve().parent / "golden_set.yaml"
LABELS = ("verified", "exploratory", "blocked", "not_answerable")


def load_golden(path: Path = GOLDEN) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    items = data["items"]
    ids = [i["id"] for i in items]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate golden ids")
    return data


def expected_label(item: dict, mode: str) -> str:
    exp = item["expect"]
    return exp.get("label") or exp[mode]


def check(
    item: dict, answer: dict, values: dict[str, float], mode: str, tolerance_pct: float
) -> tuple[bool, list[str]]:
    """Compare one answer with its expectation; returns (ok, problems)."""
    exp = item["expect"]
    label = expected_label(item, mode)
    problems: list[str] = []
    if answer["label"] != label:
        problems.append(f"label {answer['label']} != {label}")
    passport_label = label in ("verified", "not_answerable")
    if passport_label and exp.get("passport") and answer.get("passport_code") != exp["passport"]:
        problems.append(f"passport {answer.get('passport_code')} != {exp['passport']}")
    if label == "not_answerable" and exp.get("gap"):
        gap = answer.get("gap") or {}
        if gap.get("dataset") != exp["gap"]:
            problems.append(f"gap {gap.get('dataset')} != {exp['gap']}")
        if exp.get("gap") and not (gap.get("owner") or {}).get("sq"):
            problems.append("gap without owner")
    if label == "verified" and exp.get("value"):
        want = values.get(exp["value"])
        got = answer.get("value")
        if want is None:
            problems.append(f"no independent value for {exp['value']}")
        elif got is None:
            problems.append("no value")
        else:
            tol = abs(want) * tolerance_pct / 100.0 or 1e-9
            if abs(got - want) > tol:
                problems.append(f"value {got} != {want} (±{tolerance_pct}%)")
    if label in ("verified", "not_answerable", "blocked", "exploratory"):
        interp = answer.get("interpreted_as") or {}
        if not (interp.get("sq") and interp.get("en")):
            problems.append("interpreted_as missing")
    if label == "blocked" and not answer.get("blocked_reason"):
        problems.append("blocked without reason")
    return (not problems, problems)


AskFn = Callable[[str, str], dict]


def run_items(
    items: Iterable[dict],
    ask: AskFn,
    values: dict[str, float],
    mode: str,
    tolerance_pct: float,
) -> list[dict]:
    results = []
    for item in items:
        answer = ask(item["question"], item["locale"])
        ok, problems = check(item, answer, values, mode, tolerance_pct)
        exp_value = values.get(item["expect"].get("value") or "")
        results.append(
            {
                "id": item["id"],
                "locale": item["locale"],
                "stage": item["stage"],
                "question": item["question"],
                "expected": expected_label(item, mode),
                "got": answer["label"],
                "passport_code": answer.get("passport_code"),
                "value": answer.get("value"),
                "expected_value": exp_value,
                "ok": ok,
                "problems": problems,
            }
        )
    return results


def by_label(results: list[dict]) -> list[dict]:
    """``[{label, matched, total}]`` grouped by the expected label.

    Labels with no question in this mode are left out (in RULES mode no answer is expected
    to be exploratory, so a "0 of 0" chip would say nothing).
    """
    out = []
    for label in LABELS:
        rows = [r for r in results if r["expected"] == label]
        if rows:
            matched = sum(1 for r in rows if r["ok"])
            out.append({"label": label, "matched": matched, "total": len(rows)})
    return out
