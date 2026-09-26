"""Indicator endpoints on a small hand-built warehouse (no dependency on the ingest module).

The fixture ("mini municipality", January–June 2026) plants one pattern per signal rule:
Gjinar reports 0 t of waste in March (placeholder), programme 05100 spends 2.8x in April
(one cost-per-tonne swing), capital execution is 33% against a 70% target (off target), and the
overall budget execution sits just under its target (off target, info).
"""

import datetime as dt
import json

import pytest

from app.catalog import OWNERS
from app.warehouse.db import get_db, insert_rows

D = dt.date
MONTHS = range(1, 7)
ALL = ("requests", "budget", "population", "waste", "revenue", "staff")
START = ("requests", "budget", "population")

SOURCES = {
    "requests": ("s-req", "01_SINTETIKE_kerkesat.xlsx"),
    "budget": ("s-bud", "02_SINTETIKE_buxheti.xlsx"),
    "population": ("s-pop", "ref_SINTETIKE_popullsia.csv"),
    "waste": ("s-wst", "zarfi-1_SINTETIKE_mbetjet.csv"),
    "revenue": ("s-rev", "zarfi-2_SINTETIKE_taksat.xlsx"),
    "staff": ("s-hr", "zarfi-3_SINTETIKE_bnj.xlsx"),
}

SUMMARY_KEYS = {
    "code",
    "area",
    "name",
    "unit",
    "unit_label",
    "state",
    "value",
    "period",
    "previous",
    "target",
    "direction",
    "status",
    "owner",
    "missing",
    "signals",
    "sources",
    "smp_ref",
    "version",
    "formula_status",
    "basis",
    "sparkline",
    # additive: how to read the SMP chip, the period and the series
    "smp_kind",
    "smp_note",
    "period_kind",
    "series_kind",
}
PASSPORT_KEYS = SUMMARY_KEYS | {
    "formula",
    "question",
    "sql",
    "series",
    "lineage",
    "required_datasets",
    "checks",
    "computed_at",
}


# --------------------------------------------------------------------------------------------
# Fixture builders (rows go straight into the canonical tables)
# --------------------------------------------------------------------------------------------


def _requests() -> list[tuple]:
    rows, n = [], 4
    for m in MONTHS:
        for rid, closed, dept, status, sla in (
            ("A", D(2026, m, 8), "PW", "E mbyllur", 10),  # 5 days, on time
            ("B", D(2026, m, 20), "SS", "E mbyllur", 10),  # 17 days, late
            ("C", D(2026, m, 6), "PW", "E mbyllur", 10),  # 3 days, on time
            ("D", None, "SS", "Në proces", 30),  # open
        ):
            rows.append(
                ("s-req", n, f"R{m}{rid}", D(2026, m, 3), closed, "Rrugë", dept, "Elbasan",
                 "Online", status, sla)
            )  # fmt: skip
            n += 1
    return rows


def _budget() -> list[tuple]:
    rows, n = [], 4
    for m in MONTHS:
        waste_actual = 250_000.0 if m == 4 else 90_000.0  # April: programme 05100 spike
        for code, kind, planned, actual in (
            ("05100", "current", 100_000.0, waste_actual),
            ("05100", "capital", 20_000.0, 10_000.0),
            ("01110", "capital", 100_000.0, 30_000.0),
            ("01110", "current", 200_000.0, 190_000.0),
        ):
            rows.append(("s-bud", n, D(2026, m, 1), code, "Programi", kind, planned, actual))
            n += 1
    return rows


ELBASAN_TONNES = {1: 100.0, 2: 104.0, 3: 98.0, 4: 102.0, 5: 97.0, 6: 99.0}  # sum 600


def _waste() -> list[tuple]:
    rows, n = [], 3
    for m in MONTHS:
        rows.append(("s-wst", n, D(2026, m, 1), "Elbasan", ELBASAN_TONNES[m], 20, 5000))
        rows.append(("s-wst", n + 1, D(2026, m, 1), "Gjinar", 0.0 if m == 3 else 20.0, 4, 300))
        n += 2
    return rows


def _population() -> list[tuple]:
    return [
        ("s-pop", 3, "Elbasan", "census_2023", 900),
        ("s-pop", 4, "Gjinar", "census_2023", 100),
        ("s-pop", 5, "Elbasan", "civil_registry", 1500),
        ("s-pop", 6, "Gjinar", "civil_registry", 500),
    ]


def _revenue() -> list[tuple]:
    rows, n = [], 4
    for m in MONTHS:
        rows.append(
            ("s-rev", n, D(2026, m, 1), "Tarifa e pastrimit", "Familje", 60_000.0, 50_000.0)
        )
        rows.append(
            ("s-rev", n + 1, D(2026, m, 1), "Taksa e ndërtesës", "Biznes", 100_000.0, 80_000.0)
        )
        n += 2
    return rows  # fmt: skip


def _staff() -> list[tuple]:
    return [
        ("s-hr", 4, "Drejtoria A", 10, 2, 1, D(2026, 6, 30)),
        ("s-hr", 5, "Drejtoria B", 30, 0, 3, D(2026, 6, 30)),
    ]


BUILDERS = {
    "requests": ("request", _requests),
    "budget": ("budget_line", _budget),
    "population": ("population", _population),
    "waste": ("waste_collection", _waste),
    "revenue": ("revenue", _revenue),
    "staff": ("staff", _staff),
}


def load_mini(con, datasets=ALL) -> None:
    """Insert the mini-municipality rows and one ``source`` row per dataset."""
    for key in datasets:
        table, build = BUILDERS[key]
        insert_rows(con, table, build())
        sid, filename = SOURCES[key]
        con.execute(
            "INSERT INTO source (id, filename, file_hash, dataset, synthetic, rows_read, "
            "rows_loaded, loaded_at) VALUES (?, ?, ?, ?, true, ?, ?, ?)",
            [sid, filename, "sha-" + sid, key, len(build()) + 1, len(build()),
             dt.datetime(2026, 9, 26, 1, 0)],
        )  # fmt: skip


@pytest.fixture
def start(client):
    load_mini(get_db(), START)
    return client


@pytest.fixture
def full(client):
    load_mini(get_db(), ALL)
    return client


def board(c, **params) -> dict:
    res = c.get("/api/v1/indicators", params=params)
    assert res.status_code == 200, res.text
    return res.json()


def by_code(b: dict) -> dict:
    return {i["code"]: i for i in b["indicators"]}


def rules(summary: dict) -> list[str]:
    return [s["rule"] for s in summary["signals"]]


# --------------------------------------------------------------------------------------------
# Board
# --------------------------------------------------------------------------------------------


def test_board_start_state_shape_and_gaps(start):
    b = board(start)
    assert set(b) == {"pack", "as_of", "coverage", "basis", "indicators"}
    assert b["pack"] == "core_kpi"
    assert b["coverage"] == {
        "computable": 6,
        "missing": 7,
        "document": 0,
        "national": 0,
        "total": 13,
    }
    assert b["basis"] == {"population": "census_2023"}
    assert b["as_of"] == "2026-06"
    ind = by_code(b)
    assert list(ind) == [
        "REQ-01", "REQ-02", "REQ-03", "REQ-04", "FIN-01", "FIN-02", "WST-01", "WST-02",
        "WST-03", "REV-01", "REV-02", "HR-01", "HR-02",
    ]  # fmt: skip
    for s in b["indicators"]:
        assert set(s) == SUMMARY_KEYS
        assert set(s["name"]) == {"sq", "en"} and set(s["unit_label"]) == {"sq", "en"}
        assert s["formula_status"] == "draft" and s["version"] == "0.1.0"
    computable = {c for c, s in ind.items() if s["state"] == "computable"}
    assert computable == {"REQ-01", "REQ-02", "REQ-03", "REQ-04", "FIN-01", "FIN-02"}

    rev2 = ind["REV-02"]
    assert rev2["state"] == "missing"
    assert rev2["value"] is None and rev2["status"] is None and rev2["sparkline"] == []
    assert rev2["signals"] == [] and rev2["sources"] == []
    assert rev2["missing"] == [
        {
            "dataset": "revenue",
            "name": {"sq": "Taksat dhe tarifat — arkëtimi", "en": "Taxes and fees — collection"},
            "owner": OWNERS["local_revenue"],
        }
    ]
    assert rev2["owner"] == {"key": "local_revenue", "name": OWNERS["local_revenue"]}
    assert rev2["smp_ref"] == "SMP-AL 2024 #13"
    assert [m["dataset"] for m in ind["WST-03"]["missing"]] == ["waste"]
    assert [m["dataset"] for m in ind["HR-01"]["missing"]] == ["staff"]
    assert ind["WST-02"]["basis"] == "census_2023"  # per-capita passports state the basis
    assert ind["REQ-01"]["basis"] is None


def test_board_values_previous_and_sources(full):
    b = board(full)
    assert b["coverage"]["computable"] == 13 and b["coverage"]["missing"] == 0
    ind = by_code(b)

    req1 = ind["REQ-01"]
    # year-to-date values report their period as an ISO month range; stocks the month
    assert req1["value"] == 24 and req1["period"] == "2026-01/2026-06"
    assert req1["previous"] == 20  # year to date as of the end of May, comparable with value
    assert req1["status"] == "no_target"
    assert req1["sparkline"] == [{"period": f"2026-0{m}", "value": 4.0} for m in MONTHS]
    assert req1["sources"] == [
        {"source_id": "s-req", "filename": "01_SINTETIKE_kerkesat.xlsx", "synthetic": True}
    ]
    assert ind["REQ-02"]["value"] == pytest.approx(200 / 3)
    assert ind["REQ-02"]["previous"] == pytest.approx(200 / 3)
    assert ind["REQ-03"]["value"] == 5 and ind["REQ-03"]["previous"] == 4
    assert ind["REQ-03"]["period"] == "2026-06"
    assert ind["REQ-04"]["value"] == pytest.approx(25 / 3)
    assert ind["REQ-04"]["status"] == "on_track"

    assert ind["FIN-01"]["value"] == pytest.approx(2_080 / 2_520 * 100)
    assert ind["FIN-02"]["value"] == pytest.approx(40 / 120 * 100)
    assert ind["FIN-02"]["status"] == "off_track"
    assert ind["WST-01"]["value"] == 700 and ind["WST-01"]["previous"] == 581
    assert ind["WST-02"]["value"] == pytest.approx(1400.0)
    assert ind["WST-03"]["value"] == pytest.approx(760_000 / 700)
    assert ind["REV-01"]["value"] == pytest.approx(81.25)
    assert ind["REV-02"]["value"] == pytest.approx(300_000 / 760_000 * 100)
    assert ind["HR-01"]["value"] == pytest.approx(40.0)
    assert ind["HR-01"]["previous"] is None  # only one headcount snapshot
    assert ind["HR-02"]["value"] == pytest.approx(4 / 41 * 100)
    assert {s["filename"] for s in ind["WST-03"]["sources"]} == {
        "zarfi-1_SINTETIKE_mbetjet.csv",
        "02_SINTETIKE_buxheti.xlsx",
    }


def test_signals_fire_on_planted_patterns(full):
    ind = by_code(board(full))
    fired = {(c, s["rule"]) for c, i in ind.items() for s in i["signals"]}
    assert fired == {
        ("REQ-02", "off_target"),
        ("FIN-01", "off_target"),
        ("FIN-02", "off_target"),
        ("WST-01", "placeholder_value"),
        ("WST-03", "swing"),
        ("REV-01", "off_target"),
        ("REV-02", "off_target"),
    }
    (ph,) = ind["WST-01"]["signals"]
    assert ph["severity"] == "warn" and ph["period"] == "2026-03"
    assert ph["message"]["sq"].startswith("Gjinar: 0 ton në mars 2026")
    assert "20 dhe 20 ton" in ph["message"]["sq"]
    assert "Kontrolloni sasinë ose njësinë" in ph["message"]["sq"]
    assert "Check the quantity or unit" in ph["message"]["en"]
    (sw,) = ind["WST-03"]["signals"]  # one swing: April up, May back is not a second swing
    assert sw["period"] == "2026-04" and sw["severity"] == "warn"
    assert "+109%" in sw["message"]["en"] and "returns to" in sw["message"]["en"]
    fin2 = ind["FIN-02"]["signals"][0]
    assert fin2["severity"] == "warn" and "33,3%" in fin2["message"]["sq"]
    assert "70%" in fin2["message"]["sq"] and "−36,7 pikë përqindjeje" in fin2["message"]["sq"]
    assert ind["FIN-01"]["signals"][0]["severity"] == "info"  # 82.5% against 90%: near
    for s in (s for i in ind.values() for s in i["signals"]):
        assert set(s) == {"rule", "severity", "message", "period"}
        for word in ("gabim", "wrong", "error", "manual"):
            assert word not in s["message"]["sq"].lower() + s["message"]["en"].lower()


def test_parts_vs_total_signal_from_reconciliation(full):
    recon = [
        {
            "field": "tonnes",
            "label": {"sq": "Sasia (ton)", "en": "Quantity (tonnes)"},
            "file_total": 710.0,
            "loaded_sum": 700.0,
            "ok": False,
            "note": None,
        },
        {"field": "trips", "label": {"sq": "Kurse", "en": "Trips"}, "file_total": 144,
         "loaded_sum": 144, "ok": True, "note": None},
    ]  # fmt: skip
    get_db().execute(
        "UPDATE source SET reconciliation_json = ? WHERE id = 's-wst'", [json.dumps(recon)]
    )
    ind = by_code(board(full))
    for code in ("WST-01", "WST-02", "WST-03"):
        pvt = [s for s in ind[code]["signals"] if s["rule"] == "parts_vs_total"]
        assert len(pvt) == 1, code
        assert pvt[0]["period"] is None
        assert "zarfi-1_SINTETIKE_mbetjet.csv" in pvt[0]["message"]["sq"]
        assert "710,00" in pvt[0]["message"]["sq"] and "700,00" in pvt[0]["message"]["sq"]
    assert "parts_vs_total" not in rules(ind["REV-01"])
    passport = full.get("/api/v1/indicators/WST-01").json()
    check = {c["rule"]: c for c in passport["checks"]}["parts_vs_total"]
    assert check["passed"] is False and "710" in check["message"]["en"]


def test_unknown_pack_and_indicator_use_the_error_shape(full):
    res = full.get("/api/v1/indicators", params={"pack": "nope"})
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "unknown_pack"
    res = full.get("/api/v1/indicators", params={"pack": "al_smp"})  # coverage, not passports
    assert res.status_code == 404
    res = full.get("/api/v1/indicators/XYZ-99")
    assert res.status_code == 404
    detail = res.json()["detail"]
    assert detail["code"] == "unknown_indicator"
    assert set(detail["message"]) == {"sq", "en"} and "XYZ-99" in detail["message"]["en"]
    assert full.get("/api/v1/indicators/XYZ-99/lineage").status_code == 404


# --------------------------------------------------------------------------------------------
# Passport
# --------------------------------------------------------------------------------------------


def test_passport_detail(full):
    res = full.get("/api/v1/indicators/wst-03")  # codes are case-insensitive
    assert res.status_code == 200
    p = res.json()
    assert set(p) == PASSPORT_KEYS
    assert p["code"] == "WST-03" and p["state"] == "computable"
    assert p["formula"]["sq"].startswith("Shpenzimet faktike") and p["question"]["en"]
    assert "05100" in p["sql"] and p["sql"].lstrip().startswith("WITH")
    assert p["required_datasets"] == ["waste", "budget"]
    assert [s["period"] for s in p["series"]] == [f"2026-0{m}" for m in MONTHS]
    assert p["series"] == p["sparkline"]
    lineage = {s["filename"]: s for s in p["lineage"]}
    waste = lineage["zarfi-1_SINTETIKE_mbetjet.csv"]
    assert waste == {
        "source_id": "s-wst",
        "filename": "zarfi-1_SINTETIKE_mbetjet.csv",
        "file_hash": "sha-s-wst",
        "row_count": 12,
        "row_ranges": "3–14",
    }
    budget = lineage["02_SINTETIKE_buxheti.xlsx"]
    assert budget["row_count"] == 12  # two 05100 lines per month
    assert budget["row_ranges"] == "4–5, 8–9, 12–13, 16–17, 20–21, 24–25"
    checks = {c["rule"]: c for c in p["checks"]}
    assert list(checks) == ["placeholder_value", "swing", "parts_vs_total"]
    assert checks["swing"]["passed"] is False and checks["swing"]["message"]["sq"]
    assert checks["placeholder_value"] == {
        "rule": "placeholder_value",
        "label": checks["placeholder_value"]["label"],
        "passed": True,
        "message": None,
    }
    assert dt.datetime.fromisoformat(p["computed_at"]).tzinfo is not None


def test_passport_for_missing_indicator(start):
    p = start.get("/api/v1/indicators/HR-01").json()
    assert p["state"] == "missing"
    assert p["missing"][0]["dataset"] == "staff"
    assert p["lineage"] == [] and p["series"] == [] and p["checks"] == []
    assert p["computed_at"] is None and p["value"] is None
    assert "'census_2023'" in p["sql"] and "$basis" not in p["sql"]
    assert p["basis"] == "census_2023"


def test_lineage_rows_share_the_limit_across_files(full):
    res = full.get("/api/v1/indicators/WST-03/lineage", params={"limit": 10})
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"code", "columns", "total", "rows"}
    assert body["code"] == "WST-03" and body["total"] == 24
    files = [r["source_file"] for r in body["rows"]]
    assert files.count("zarfi-1_SINTETIKE_mbetjet.csv") == 5
    assert files.count("02_SINTETIKE_buxheti.xlsx") == 5
    assert body["columns"][:5] == ["month", "admin_unit", "tonnes", "trips", "households_served"]
    assert "actual_lek" in body["columns"] and "source_id" not in body["columns"]
    first = body["rows"][0]
    assert first == {
        "source_file": "zarfi-1_SINTETIKE_mbetjet.csv",
        "row_no": 3,
        "values": {
            "month": "2026-01-01",
            "admin_unit": "Elbasan",
            "tonnes": 100.0,
            "trips": 20,
            "households_served": 5000,
        },
    }
    budget_row = next(r for r in body["rows"] if r["source_file"].startswith("02_"))
    assert budget_row["values"]["programme_code"] == "05100"

    req = full.get("/api/v1/indicators/REQ-01/lineage").json()
    assert req["total"] == 24 and len(req["rows"]) == 24
    assert full.get("/api/v1/indicators/REQ-01/lineage", params={"limit": 0}).status_code == 422


def test_lineage_rows_for_missing_indicator_are_empty(start):
    body = start.get("/api/v1/indicators/REV-01/lineage").json()
    assert body == {"code": "REV-01", "columns": [], "total": 0, "rows": []}


# --------------------------------------------------------------------------------------------
# Population basis pin
# --------------------------------------------------------------------------------------------


def test_population_basis_pin_changes_per_capita_values(full):
    res = full.get("/api/v1/definitions/population_basis")
    assert res.status_code == 200
    body = res.json()
    assert body["value"] == "census_2023" and body["pinned_at"] is None
    assert {o["value"]: o["residents"] for o in body["options"]} == {
        "census_2023": 1000,
        "civil_registry": 2000,
    }
    assert {i["code"]: i["value"] for i in body["indicators"]} == {
        "WST-02": pytest.approx(1400.0),
        "HR-01": pytest.approx(40.0),
    }

    res = full.post(
        "/api/v1/definitions/population_basis",
        json={"value": "civil_registry", "reason": "PBA uses the civil registry"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True and body["value"] == "civil_registry"
    assert body["label"] == {"sq": "Regjistri civil", "en": "Civil registry"}
    assert body["reason"] == "PBA uses the civil registry" and body["pinned_at"]
    assert {i["code"]: i["value"] for i in body["indicators"]} == {
        "WST-02": pytest.approx(700.0),
        "HR-01": pytest.approx(20.0),
    }

    b = board(full)
    assert b["basis"] == {"population": "civil_registry"}
    ind = by_code(b)
    assert ind["WST-02"]["value"] == pytest.approx(700.0)
    assert ind["WST-02"]["basis"] == "civil_registry" and ind["HR-01"]["basis"] == "civil_registry"
    assert ind["WST-01"]["value"] == 700  # not per capita: unchanged
    p = full.get("/api/v1/indicators/HR-01").json()
    assert "'civil_registry'" in p["sql"] and p["value"] == pytest.approx(20.0)

    back = full.post("/api/v1/definitions/population_basis", json={"value": "census_2023"})
    assert back.json()["value"] == "census_2023" and back.json()["reason"] is None
    assert by_code(board(full))["HR-01"]["value"] == pytest.approx(40.0)


def test_population_basis_rejects_unknown_values(full):
    res = full.post("/api/v1/definitions/population_basis", json={"value": "guess"})
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail["code"] == "invalid_basis" and "census_2023" in detail["message"]["en"]
    assert board(full)["basis"] == {"population": "census_2023"}


def test_board_serial_and_parallel_evaluation_agree(full):
    from app.indicators import service as svc

    con = get_db()
    serial = svc.board_from(svc.evaluate_pack(con, workers=1), con, "core_kpi")
    parallel = svc.board_from(svc.evaluate_pack(con, workers=4), con, "core_kpi")
    assert serial["indicators"] == parallel["indicators"]
    assert serial["as_of"] == parallel["as_of"] == "2026-06"
