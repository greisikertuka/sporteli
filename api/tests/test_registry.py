"""Every passport's SQL checked against a small hand-built fixture with hand-computed values."""

import datetime as dt

import pytest

from app.indicators import registry as reg
from app.warehouse.db import insert_rows

D = dt.date


def _insert(con, table: str, rows: list[tuple]) -> None:
    insert_rows(con, table, rows)


def load_requests(con):
    # source_id, row_no, request_id, created_at, closed_at, category, department, admin_unit,
    # channel, status, sla_days
    _insert(
        con,
        "request",
        [
            ("s-req", 4, "R1", D(2026, 1, 10), D(2026, 1, 15), "A", "PW", "Elbasan", "Online",
             "E mbyllur", 10),  # 5 days, on time, closed Jan
            ("s-req", 5, "R2", D(2026, 1, 20), D(2026, 2, 10), "A", "PW", "Elbasan", "Online",
             "E mbyllur", 10),  # 21 days, late, closed Feb
            ("s-req", 6, "R3", D(2026, 2, 5), None, "A", "PW", "Gjinar", "Telefon",
             "Në proces", 10),  # open, overdue from Feb-end
            ("s-req", 7, "R4", D(2026, 3, 1), D(2026, 3, 4), "B", "SS", "Elbasan", "Sportel",
             "E mbyllur", 5),  # 3 days, on time, closed Mar
            ("s-req", 8, "R5", D(2026, 3, 25), None, "B", "SS", "Elbasan", "Sportel",
             "E re", 30),  # open, not overdue (6 days)
            ("s-req", 9, "R6", D(2025, 12, 15), D(2026, 1, 5), "A", "PW", "Elbasan", "Online",
             "E mbyllur", 10),  # created 2025 (not counted in REQ-01), 21 days, late, closed Jan
            ("s-req", 10, "R7", D(2026, 1, 3), None, "B", "SS", "Elbasan", "Online",
             "E refuzuar", 5),  # rejected without closing date: never "open overdue"
        ],
    )  # fmt: skip


def load_budget(con):
    _insert(
        con,
        "budget_line",
        [
            ("s-bud", 4, D(2026, 1, 1), "05100", "Mbetjet", "current", 100.0, 90.0),
            ("s-bud", 5, D(2026, 1, 1), "05100", "Mbetjet", "capital", 50.0, 10.0),
            ("s-bud", 6, D(2026, 2, 1), "05100", "Mbetjet", "current", 100.0, 150.0),
            ("s-bud", 7, D(2026, 2, 1), "01110", "Admin", "capital", 200.0, 60.0),
        ],
    )


def load_waste(con):
    _insert(
        con,
        "waste_collection",
        [
            ("s-wst", 3, D(2026, 1, 1), "Elbasan", 100.0, 10, 1000),
            ("s-wst", 4, D(2026, 1, 1), "Gjinar", 0.0, 2, 50),
            ("s-wst", 5, D(2026, 2, 1), "Elbasan", 50.0, 8, 1000),
        ],
    )


def load_population(con):
    _insert(
        con,
        "population",
        [
            ("s-pop", 3, "Elbasan", "census_2023", 900),
            ("s-pop", 4, "Gjinar", "census_2023", 100),
            ("s-pop", 5, "Elbasan", "civil_registry", 1500),
            ("s-pop", 6, "Gjinar", "civil_registry", 500),
        ],
    )


def load_revenue(con):
    _insert(
        con,
        "revenue",
        [
            ("s-rev", 4, D(2026, 1, 1), "Tarifa e pastrimit", "Familje", 100.0, 80.0),
            ("s-rev", 5, D(2026, 2, 1), "Tarifa e Pastrimit ", "Biznes", 100.0, 45.0),
            ("s-rev", 6, D(2026, 2, 1), "Taksa e ndërtesës", "Biznes", 200.0, 100.0),
        ],
    )


def load_staff(con):
    _insert(
        con,
        "staff",
        [
            ("s-hr", 4, "A", 10, 2, 1, D(2026, 8, 31)),
            ("s-hr", 5, "B", 30, 0, 3, D(2026, 8, 31)),
            ("s-hr-old", 4, "A", 50, 0, 0, D(2026, 6, 30)),  # older snapshot: ignored by value
        ],
    )


def load_sources(con):
    for sid, name in [
        ("s-req", "requests.xlsx"),
        ("s-bud", "budget.xlsx"),
        ("s-wst", "waste.csv"),
        ("s-pop", "population.csv"),
        ("s-rev", "revenue.xlsx"),
        ("s-hr", "staff.xlsx"),
    ]:
        con.execute(
            "INSERT INTO source (id, filename, file_hash, synthetic) VALUES (?, ?, ?, true)",
            [sid, name, "hash-" + sid],
        )


@pytest.fixture
def full(db):
    for loader in (
        load_requests,
        load_budget,
        load_waste,
        load_population,
        load_revenue,
        load_staff,
        load_sources,
    ):
        loader(db)
    return db


def run(con, code, basis=None):
    return reg.compute(reg.get_passport(code), con, basis)


def series(res):
    return {p.period: p.value for p in res.series}


def lineage_count(res):
    return sum(s.row_count for s in res.lineage)


def test_pack_has_13_valid_passports():
    pack = reg.load_pack("core_kpi")
    assert pack.codes == [
        "REQ-01", "REQ-02", "REQ-03", "REQ-04", "FIN-01", "FIN-02", "WST-01", "WST-02",
        "WST-03", "REV-01", "REV-02", "HR-01", "HR-02",
    ]  # fmt: skip
    for p in pack.passports:
        assert p.formula_status == "draft"
        assert len(p.aliases.sq) >= 3 and len(p.aliases.en) >= 3
        for loc in ("sq", "en"):
            assert "{value}" in p.answer[loc] and "{period}" in p.answer[loc]
            if p.target is not None:
                assert "{target}" in p.answer[loc]
            if p.uses_basis:
                assert "{basis}" in p.answer[loc]
    assert {p.code for p in pack.passports if p.uses_basis} == {"WST-02", "HR-01"}


def test_req_01(full):
    r = run(full, "REQ-01")
    # created 2026-01-01..2026-03-31: R1, R2, R3, R4, R5, R7 (R6 was created in 2025)
    assert r.value == 6 and r.period == "2026-03"
    assert series(r) == {"2026-01": 3, "2026-02": 1, "2026-03": 2}
    assert r.previous == 1
    assert lineage_count(r) == 6
    assert r.lineage[0].filename == "requests.xlsx"
    assert r.lineage[0].row_ranges == "4–8, 10"


def test_req_02_on_time_rate(full):
    r = run(full, "REQ-02")
    # closed in 2026-01..03 with sla: R1 on time, R2 late, R4 on time, R6 late → 2/4
    assert r.value == pytest.approx(50.0)
    assert series(r) == pytest.approx({"2026-01": 50.0, "2026-02": 0.0, "2026-03": 100.0})
    assert lineage_count(r) == 4


def test_req_03_open_overdue(full):
    r = run(full, "REQ-03")
    # as of 2026-03-31: R3 open 54 days > 10 → 1; R5 open 6 days ≤ 30; R7 rejected
    assert r.value == 1 and r.period == "2026-03"
    # Jan-end: R2 open (closed 02-10), 11 days > 10 → 1; Feb-end: R3 → 1; Mar-end: R3 → 1
    assert series(r) == {"2026-01": 1, "2026-02": 1, "2026-03": 1}
    assert lineage_count(r) == 1


def test_req_04_average_days(full):
    r = run(full, "REQ-04")
    # closed in 2026: R1 5, R2 21, R4 3, R6 21 → 12.5
    assert r.value == pytest.approx(12.5)
    assert series(r) == pytest.approx({"2026-01": 13.0, "2026-02": 21.0, "2026-03": 3.0})


def test_fin_01_and_02(full):
    r = run(full, "FIN-01")
    assert r.value == pytest.approx(310 / 450 * 100)
    assert r.period == "2026-02"
    assert series(r) == pytest.approx({"2026-01": 100 / 150 * 100, "2026-02": 310 / 450 * 100})
    assert lineage_count(r) == 4
    r2 = run(full, "FIN-02")
    assert r2.value == pytest.approx(28.0)
    assert series(r2) == pytest.approx({"2026-01": 20.0, "2026-02": 28.0})
    assert lineage_count(r2) == 2


def test_wst_01_tonnes(full):
    r = run(full, "WST-01")
    assert r.value == 150 and r.period == "2026-02"
    assert series(r) == {"2026-01": 100, "2026-02": 50}
    assert lineage_count(r) == 3


def test_wst_02_per_resident_uses_basis(full):
    census = run(full, "WST-02", "census_2023")
    # 150 t × 1000 / 1000 residents × 12 / 2 months = 900 kg/resident/year
    assert census.value == pytest.approx(900.0)
    assert census.basis == "census_2023"
    assert series(census) == pytest.approx({"2026-01": 1200.0, "2026-02": 600.0})
    assert lineage_count(census) == 3 + 2
    civil = run(full, "WST-02", "civil_registry")
    assert civil.value == pytest.approx(450.0)


def test_wst_03_cost_per_tonne(full):
    r = run(full, "WST-03")
    # programme 05100 actual 90 + 10 + 150 = 250 lek / 150 t
    assert r.value == pytest.approx(250 / 150)
    assert series(r) == pytest.approx({"2026-01": 1.0, "2026-02": 3.0})
    assert lineage_count(r) == 3 + 3


def test_rev_01_collection(full):
    r = run(full, "REV-01")
    assert r.value == pytest.approx(225 / 400 * 100)
    assert series(r) == pytest.approx({"2026-01": 80.0, "2026-02": 56.25})


def test_rev_02_fee_coverage(full):
    r = run(full, "REV-02")
    # cleaning fee 80 + 45 = 125 (type matched case/diacritic-insensitively) / waste spend 250
    assert r.value == pytest.approx(50.0)
    assert series(r) == pytest.approx({"2026-01": 80.0, "2026-02": 50.0})
    assert lineage_count(r) == 2 + 3
    assert {s.filename for s in r.lineage} == {"revenue.xlsx", "budget.xlsx"}


def test_hr_01_staff_per_1000(full):
    r = run(full, "HR-01", "census_2023")
    assert r.value == pytest.approx(40.0) and r.period == "2026-08"
    assert run(full, "HR-01", "civil_registry").value == pytest.approx(20.0)
    assert series(r) == pytest.approx({"2026-06": 50.0, "2026-08": 40.0})
    assert r.previous == pytest.approx(50.0)
    assert lineage_count(r) == 2 + 2


def test_hr_02_turnover(full):
    r = run(full, "HR-02")
    # leavers 4 / ((40 + (40 - 2 + 4)) / 2 = 41) × 100
    assert r.value == pytest.approx(4 / 41 * 100)
    assert lineage_count(r) == 2


def test_basis_defaults_to_pin(full):
    assert reg.get_population_basis(full) == "census_2023"
    full.execute(
        "INSERT INTO definition_pin VALUES ('population_basis', 'civil_registry', now(), 'test')"
    )
    assert reg.get_population_basis(full) == "civil_registry"
    assert run(full, "HR-01").value == pytest.approx(20.0)


def test_states_coverage_and_unlocks(db):
    load_requests(db)
    load_budget(db)
    load_population(db)
    before = reg.states(db)
    assert reg.coverage(db) == {
        "computable": 6,
        "missing": 7,
        "document": 0,
        "national": 0,
        "total": 13,
    }
    p = reg.get_passport("REV-02")
    assert reg.state(p, db) == "missing"
    assert reg.missing_datasets(p, db) == ["revenue"]
    with pytest.raises(reg.NotComputable):
        reg.compute(p, db)
    load_revenue(db)
    after = reg.states(db)
    assert reg.newly_unlocked(before, after) == ["REV-01", "REV-02"]
    assert reg.newly_unlocked(set(), ["WST-01"]) == ["WST-01"]
    assert reg.describe_codes(["REV-02"])[0]["name"]["sq"].startswith("Mbulimi")
    assert reg.coverage(db)["computable"] == 8


def test_every_breakdown_sql_runs(full):
    for p in reg.load_pack().passports:
        if p.breakdown_sql:
            rows = full.execute(p.breakdown_sql).fetchall()
            assert rows and len(rows[0]) == 3
    gjinar = full.execute(reg.get_passport("WST-01").breakdown_sql).fetchall()
    assert ("2026-01", "Gjinar", 0.0) in gjinar


def test_formatting_and_answers():
    assert reg.format_number(1234.5, 1, "sq") == "1.234,5"
    assert reg.format_number(1234.5, 1, "en") == "1,234.5"
    assert reg.format_value(87.25, "percent", "sq") == "87,3%"
    assert reg.format_value(None, "percent", "en") == "—"
    assert reg.format_period("2026-08", "sq") == "gusht 2026"
    assert reg.format_period("2026-08", "en") == "August 2026"
    assert reg.format_period("2026-01/2026-08", "sq") == "janar – gusht 2026"
    assert reg.format_period("2025-11/2026-02", "en") == "November 2025 – February 2026"
    # year-to-date passports report a month range; stocks (period_kind: point) the month
    assert reg.get_passport("REQ-01").reported_period("2026-08") == "2026-01/2026-08"
    assert reg.get_passport("REQ-01").reported_period("2026-01") == "2026-01"
    assert reg.get_passport("REQ-01").reported_period(None) is None
    assert reg.get_passport("REQ-03").reported_period("2026-08") == "2026-08"
    assert reg.get_passport("HR-01").reported_period("2026-08") == "2026-08"
    assert reg.row_ranges([9, 4, 5, 6, 12, 13]) == "4–6, 9, 12–13"
    p = reg.get_passport("REV-02")
    ans = reg.render_answer(p, 55.04, "2026-08")
    assert "55,0%" in ans["sq"] and "gusht 2026" in ans["sq"] and "100%" in ans["sq"]
    assert "55.0%" in ans["en"] and "August 2026" in ans["en"]
    hr = reg.render_answer(reg.get_passport("HR-01"), 12.36, "2026-08", "census_2023")
    assert "12,4" in hr["sq"] and "Censusi 2023" in hr["sq"]
    assert reg.status_vs_target(p, 55.0) == "off_track"
    assert reg.status_vs_target(reg.get_passport("REQ-04"), 8.0) == "on_track"
    assert reg.status_vs_target(reg.get_passport("WST-01"), 8.0) == "no_target"
