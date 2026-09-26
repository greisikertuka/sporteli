"""Signal rules (contract §5): unit tests on hand-made series, then the committed samples.

On the synthetic samples exactly the planted patterns must fire, and nothing else:
Gjinar's 0 t in July (placeholder), one cost-per-tonne swing in May, the Public Works
on-time drop in July, and the off-target finance and revenue indicators.
"""

import json

import pytest

from app.indicators import registry as reg
from app.indicators import service as svc
from app.indicators import signals as sig
from tests.test_samples import load_all

P = sig.Point


def series(values, start=1):
    return [P(f"2026-{m:02d}", v) for m, v in enumerate(values, start=start)]


def passport(code):
    return reg.get_passport(code)


# --------------------------------------------------------------------------------------------
# placeholder_value
# --------------------------------------------------------------------------------------------


def test_placeholder_zero_between_large_neighbours():
    p = passport("WST-01")
    (s,) = sig.placeholder_signals(p, series([20.9, 22.7, 0.0, 24.9]), "Gjinar")
    assert s.rule == "placeholder_value" and s.severity == "warn" and s.period == "2026-03"
    assert s.message["sq"] == (
        "Gjinar: 0 ton në mars 2026, ndërsa muajt fqinjë kanë 22,7 dhe 24,9 ton. "
        "Kontrolloni sasinë ose njësinë; mund të jetë një vlerë e paplotësuar."
    )
    assert s.message["en"].startswith("Gjinar: 0 tonnes in March 2026, while the neighbouring")


def test_placeholder_one_in_the_latest_month_and_quiet_cases():
    p = passport("WST-01")
    (s,) = sig.placeholder_signals(p, series([30.0, 31.0, 1.0]))
    assert s.period == "2026-03" and "muaji fqinj ka 31" in s.message["sq"]
    assert sig.placeholder_signals(p, series([0.0, 0.5, 2.0])) == []  # small neighbours
    assert sig.placeholder_signals(p, series([None, 0.0, None])) == []
    # percentages: 0% and 1% are legitimate values
    assert sig.placeholder_signals(passport("REQ-02"), series([90.0, 0.0, 91.0])) == []


def test_placeholder_repeated_value_in_a_varying_series():
    p = passport("WST-01")
    (s,) = sig.placeholder_signals(p, series([21.3, 22.1, 22.0, 22.0, 22.0, 23.4]), "Tregan")
    assert s.period == "2026-05"
    assert (
        "Tregan: e njëjta vlerë, 22 ton, për 3 muaj radhazi (mars 2026 – maj 2026)"
        in s.message["sq"]
    )
    assert "the same value, 22 tonnes, for 3 consecutive months" in s.message["en"]
    # flat by nature (or flat apart from a placeholder) → quiet
    assert sig.placeholder_signals(p, series([50.0] * 6)) == []
    flat_with_zero = sig.placeholder_signals(p, series([20.0, 20.0, 0.0, 20.0, 20.0, 20.0]))
    assert [x.period for x in flat_with_zero] == ["2026-03"]


# --------------------------------------------------------------------------------------------
# swing
# --------------------------------------------------------------------------------------------


def test_one_spike_is_one_swing():
    p = passport("WST-03")
    pts = series([8964.5, 10382.1, 9226.6, 8947.6, 17404.5, 8581.0, 8487.9, 8465.1])
    (s,) = sig.swing_signals(p, pts)
    assert s.period == "2026-05" and s.severity == "warn"
    assert s.message["sq"].startswith(
        "17.405 lekë/ton në maj 2026, +95% kundrejt muajit prill 2026 (8.948 lekë/ton)."
    )
    assert s.message["sq"].endswith("Muaji pasardhës kthehet në 8.581 lekë/ton.")
    assert "+95% compared with April 2026" in s.message["en"]


def test_swing_ignores_small_bases_and_first_month_warm_up():
    # overdue backlog growing from a small base: no swing
    assert sig.swing_signals(passport("REQ-03"), series([2, 9, 12, 21, 26, 33, 40, 60])) == []
    # resolution days: January is short because the export starts in January
    days = series([5.3, 8.4, 8.1, 8.0, 8.2, 8.3, 9.1, 8.9])
    assert sig.swing_signals(passport("REQ-04"), days) == []
    assert sig.swing_signals(passport("WST-03"), series([900.0, 2000.0])) == []  # too short


def test_level_shift_that_stays_is_reported_with_the_latest_value():
    p = passport("WST-01")
    (s,) = sig.swing_signals(p, series([100.0, 104.0, 98.0, 40.0, 41.0, 39.0, 42.0]), "Papër")
    assert s.period == "2026-04"
    assert "−59%" in s.message["en"]
    assert s.message["en"].endswith("Latest value: 42 tonnes (July 2026).")


def test_percentage_swing_uses_points_and_the_series_median():
    p = passport("REQ-02")
    pw = series([100.0, 93.2, 85.8, 90.2, 92.0, 93.1, 69.9, 52.0])
    (s,) = sig.swing_signals(p, pw, "Drejtoria e Punëve Publike")
    assert s.period == "2026-07"
    assert "−23,2 pikë përqindjeje kundrejt muajit qershor 2026 (93,1%)" in s.message["sq"]
    assert s.message["sq"].endswith("Vlera e fundit: 52,0% (gusht 2026).")
    noisy = series([100.0, 85.7, 100.0, 94.4, 93.3, 83.3, 94.4, 100.0])
    assert sig.swing_signals(p, noisy, "Transport") == []


# --------------------------------------------------------------------------------------------
# rate_bounds, off_target, parts_vs_total
# --------------------------------------------------------------------------------------------


def test_rate_bounds():
    p = passport("FIN-01")
    (s,) = sig.rate_bounds_signals(p, 104.0, "2026-03", series([98.0, 101.5, 104.0]))
    assert s.period == "2026-03" and "104,0%" in s.message["sq"]
    assert "2 muaj" in s.message["sq"] and "0–100%" in s.message["en"]
    assert sig.rate_bounds_signals(p, 99.0, "2026-02", series([98.0, 99.0])) == []
    assert sig.rate_bounds_signals(passport("REQ-01"), 500.0, "2026-01", []) == []


def test_off_target_severity_and_direction():
    (far,) = sig.off_target_signal(passport("FIN-02"), 37.0, "2026-08")
    assert far.severity == "warn"
    assert far.message["sq"] == (
        "37,0% nga janari deri në gusht 2026, nën objektivin 70% (−33,0 pikë përqindjeje)."
    )
    assert far.period == "2026-08"  # signals keep the latest month (chart anchor)
    (near,) = sig.off_target_signal(passport("REQ-02"), 88.5, "2026-08")
    assert near.severity == "info"
    (days,) = sig.off_target_signal(passport("REQ-04"), 12.5, "2026-08")
    assert (
        days.message["en"]
        == "12.5 days from January to August 2026, above the target of 10 days (+2.5 days)."
    )
    assert sig.off_target_signal(passport("REQ-04"), 8.0, "2026-08") == []
    assert sig.off_target_signal(passport("WST-01"), 8.0, "2026-08") == []  # no target


def test_parse_reconciliation_shapes():
    items = [
        {"field": "tonnes", "label": {"sq": "Sasia", "en": "Quantity"}, "file_total": 10.0,
         "loaded_sum": 9.0, "ok": False, "note": None},
        {"field": "trips", "label": "Kurse", "file_total": 5, "loaded_sum": 5},
        {"field": "x", "file_total": None, "loaded_sum": 3.0},
    ]  # fmt: skip
    recs = sig.parse_reconciliation("f.csv", json.dumps(items))
    assert [(r.field, r.ok) for r in recs] == [("tonnes", False), ("trips", True), ("x", True)]
    assert recs[1].label == {"sq": "Kurse", "en": "Kurse"}
    mapping = sig.parse_reconciliation("f.csv", {"tonnes": {"file_total": 10, "loaded_sum": 12}})
    assert mapping[0].field == "tonnes" and mapping[0].ok is False
    assert sig.parse_reconciliation("f.csv", {"items": items})[0].field == "tonnes"
    assert sig.parse_reconciliation("f.csv", "not json") == []
    assert sig.parse_reconciliation("f.csv", None) == []
    (s,) = sig.parts_vs_total_signals(recs)
    assert s.rule == "parts_vs_total" and s.period is None
    assert s.message["en"] == (
        "f.csv: the loaded sum of “Quantity” is 9.00, while the file's total row shows 10.00. "
        "Check the excluded rows or the unit."
    )


def test_evaluate_orders_warn_first_and_caps_each_rule():
    p = passport("WST-01")
    dims = {f"U{i}": series([30.0, 0.0, 30.0]) for i in range(5)}
    out = sig.evaluate(
        p, value=150.0, period="2026-03", series=series([150.0, 120.0, 150.0]), breakdown=dims
    )
    assert [s.rule for s in out] == ["placeholder_value"] * sig.MAX_PER_RULE
    checks = sig.check_results(p, out)
    assert [c["rule"] for c in checks] == p.checks
    assert checks[0]["passed"] is False and checks[1]["passed"] is True
    assert checks[1]["message"] is None and checks[1]["label"]["en"]


# --------------------------------------------------------------------------------------------
# The committed synthetic samples
# --------------------------------------------------------------------------------------------


@pytest.fixture
def samples(db):
    load_all(db)
    for sid, name in {
        "req": "01_SINTETIKE_kerkesat_qytetare_jan-gus_2026.xlsx",
        "bud": "02_SINTETIKE_zbatimi_buxhetit_jan-gus_2026.xlsx",
        "pop": "ref_SINTETIKE_popullsia_njesite.csv",
        "wst": "zarfi-1_SINTETIKE_pastrimi_mbetjet_2026.csv",
        "rev": "zarfi-2_SINTETIKE_taksat_tarifat_arketimi_2026.xlsx",
        "hr": "zarfi-3_SINTETIKE_burimet_njerezore_2026.xlsx",
    }.items():
        db.execute(
            "INSERT INTO source (id, filename, file_hash, synthetic) VALUES (?, ?, ?, true)",
            [sid, name, "hash-" + sid],
        )
    return db


def test_samples_fire_exactly_the_planted_signals(samples):
    b = svc.board(samples)
    ind = {i["code"]: i for i in b["indicators"]}
    fired = {(c, s["rule"], s["period"]) for c, i in ind.items() for s in i["signals"]}
    assert fired == {
        ("REQ-02", "swing", "2026-07"),
        ("REQ-02", "off_target", "2026-08"),
        ("FIN-01", "off_target", "2026-08"),
        ("FIN-02", "off_target", "2026-08"),
        ("WST-01", "placeholder_value", "2026-07"),
        ("WST-03", "swing", "2026-05"),
        ("REV-01", "off_target", "2026-08"),
        ("REV-02", "off_target", "2026-08"),
    }
    assert ind["WST-01"]["signals"][0]["message"]["sq"].startswith("Gjinar: 0 ton në korrik 2026")
    assert ind["REQ-02"]["signals"][0]["message"]["sq"].startswith(
        "Drejtoria e Punëve Publike: 69,9% në korrik 2026"
    )
    fin2 = ind["FIN-02"]["signals"][0]
    assert fin2["severity"] == "warn" and "37,0%" in fin2["message"]["sq"]
    req2_target = next(s for s in ind["REQ-02"]["signals"] if s["rule"] == "off_target")
    assert req2_target["severity"] == "info"  # 88.5% against 90%


def test_samples_board_values_and_previous(samples):
    ind = {i["code"]: i for i in svc.board(samples)["indicators"]}
    assert ind["REQ-01"]["value"] == 2400
    assert ind["REQ-01"]["previous"] == 2400 - 337  # year to date at the end of July
    assert ind["FIN-02"]["previous"] == pytest.approx(35.2995, abs=1e-3)
    assert ind["WST-03"]["value"] > ind["WST-03"]["sparkline"][-1]["value"]
    assert ind["HR-01"]["previous"] is None
    assert all(i["sources"] and i["sources"][0]["synthetic"] for i in ind.values())
