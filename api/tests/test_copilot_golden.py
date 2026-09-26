"""The 24-question golden set, asked in RULES mode against the raw samples.

The warehouse is filled straight from the sample files (no ingest pipeline) and every expected
number is computed independently in Python (tests/golden/expected.py), not by the passports.
``scripts/run_eval.py`` runs the same set through the real ingest pipeline.
"""

from collections import Counter

import pytest

from app.copilot.service import ask
from tests.golden.expected import ENVELOPES, PRELOAD, expected_values, load_into, read_samples
from tests.golden.runner import LABELS, by_label, expected_label, load_golden, run_items


@pytest.fixture(scope="module")
def samples():
    return read_samples()


@pytest.fixture(scope="module")
def values(samples):
    return expected_values(samples)


def test_golden_set_shape(values):
    golden = load_golden()
    items = golden["items"]
    assert len(items) == 24
    assert Counter(i["locale"] for i in items) == {"sq": 12, "en": 12}
    assert {i["stage"] for i in items} == {"start", "full"}
    for mode in ("rules", "live"):
        labels = Counter(expected_label(i, mode) for i in items)
        assert set(labels) <= set(LABELS)
        assert labels["verified"] >= 8 and labels["blocked"] >= 3
    assert Counter(expected_label(i, "live") for i in items)["exploratory"] >= 3
    for i in items:
        exp = i["expect"]
        assert "label" in exp or {"rules", "live"} <= set(exp), i["id"]
        if exp.get("value"):
            assert exp["value"] in values, i["id"]
            assert expected_label(i, "rules") == "verified"
        if exp.get("gap"):
            assert i["stage"] == "start" and exp["gap"] in ENVELOPES


def test_independent_values_show_the_planted_patterns(values):
    assert values["requests_received"] == 2400
    assert 36.5 < values["capital_execution_pct"] < 37.5  # far from the 70% target
    assert 54.5 < values["cleaning_fee_coverage_pct"] < 55.5
    assert 78.5 < values["budget_execution_pct"] < 79.5
    assert values["waste_tonnes"] == pytest.approx(26_828.9)  # the file's TOTALI row
    assert 12 < values["staff_per_1000"] < 13  # 1,501 staff / 121,400 residents


def test_golden_set_in_rules_mode(db, samples, values):
    golden = load_golden()
    tol = golden["tolerance_pct"]
    cur = db.cursor()

    def asker(question, locale):
        return ask(cur, question, locale)

    load_into(db, samples, PRELOAD)
    start = [i for i in golden["items"] if i["stage"] == "start"]
    results = run_items(start, asker, values, "rules", tol)
    load_into(db, samples, ENVELOPES)
    full = [i for i in golden["items"] if i["stage"] == "full"]
    results += run_items(full, asker, values, "rules", tol)

    failures = [(r["id"], r["problems"]) for r in results if not r["ok"]]
    assert not failures
    summary = {row["label"]: (row["matched"], row["total"]) for row in by_label(results)}
    assert summary == {
        "verified": (11, 11),
        "exploratory": (0, 0),
        "blocked": (4, 4),
        "not_answerable": (9, 9),
    }
