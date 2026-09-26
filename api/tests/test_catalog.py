import datetime as dt

import pytest

from app import catalog as c
from app.indicators.registry import load_pack


def test_normalize_text_and_header_key():
    assert c.normalize_text("  Njësia   Administrative (NJA) ") == "njesia administrative nja"
    assert c.normalize_text("Ç'ËSHTË_kjo?") == "c eshte kjo"
    assert c.normalize_text(None) == ""
    assert c.header_key("Numri i punonjësve (31.08.2026)") == "numri i punonjesve"
    assert c.header_key("Plani (000 lekë)") == "plani"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Shirgjani", "Shirgjan"),
        (" Tregani ", "Tregan"),
        ("labinot fushe", "Labinot-Fushë"),
        ("Labinot Fushe", "Labinot-Fushë"),
        ("LABINOT-MAL", "Labinot-Mal"),
        ("ELBASAN", "Elbasan"),
        ("Elbasan (qyteti)", "Elbasan"),
        ("Funare", "Funarë"),
        ("Papri", "Papër"),
        ("Zavalina", "Zavalinë"),
        ("Njësia administrative Gracen", "Gracen"),
        ("Gjinari", "Gjinar"),
    ],
)
def test_admin_unit_variants(raw, expected):
    assert c.normalize_admin_unit(raw) == expected


def test_admin_unit_unknown_is_kept_and_blank_is_none():
    assert c.match_admin_unit("Tiranë") is None
    assert c.normalize_admin_unit("  Tiranë ") == "Tiranë"
    assert c.normalize_admin_unit("   ") is None
    assert len(c.ADMIN_UNITS) == 13


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234,5", 1234.5),
        ("1,234.5", 1234.5),
        ("1.234", 1234.0),
        ("12.345.678", 12345678.0),
        ("1,5", 1.5),
        ("0.5", 0.5),
        ("1 234,5", 1234.5),
        ("1 234,5", 1234.5),
        ("85%", 85.0),
        ("12 lekë", 12.0),
        ("(1.234)", -1234.0),
        ("-1.234", -1234.0),
        (42, 42.0),
        (3.5, 3.5),
        ("-", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_number(raw, expected):
    assert c.parse_number(raw) == expected


def test_parse_number_rejects_text():
    with pytest.raises(ValueError):
        c.parse_number("Gjithsej")
    with pytest.raises(ValueError):
        c.parse_number("2026-01")
    assert c.parse_int("2.400") == 2400


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Janar 2026", dt.date(2026, 1, 1)),
        ("korrik 2026", dt.date(2026, 7, 1)),
        ("Gusht-2026", dt.date(2026, 8, 1)),
        ("Nëntor 2026", dt.date(2026, 11, 1)),
        ("Dhjetori 2025", dt.date(2025, 12, 1)),
        ("2026-01", dt.date(2026, 1, 1)),
        ("01.2026", dt.date(2026, 1, 1)),
        ("15.03.2026", dt.date(2026, 3, 1)),
        ("2026-08-31", dt.date(2026, 8, 1)),
        ("Aug 2026", dt.date(2026, 8, 1)),
        (dt.datetime(2026, 4, 15, 10, 0), dt.date(2026, 4, 1)),
        ("", None),
    ],
)
def test_parse_month(raw, expected):
    assert c.parse_month(raw) == expected


def test_parse_month_needs_year_for_bare_name():
    assert c.parse_month("Shkurt", default_year=2026) == dt.date(2026, 2, 1)
    with pytest.raises(ValueError):
        c.parse_month("Shkurt")
    with pytest.raises(ValueError):
        c.parse_month("TOTALI")


def test_parse_date():
    assert c.parse_date("05.01.2026") == dt.date(2026, 1, 5)
    assert c.parse_date("5/1/2026") == dt.date(2026, 1, 5)
    assert c.parse_date("2026-01-05") == dt.date(2026, 1, 5)
    assert c.parse_date(dt.datetime(2026, 2, 5, 0, 0)) == dt.date(2026, 2, 5)
    assert c.parse_date(None) is None
    with pytest.raises(ValueError):
        c.parse_date("dje")
    assert c.find_date_in_text("Numri i punonjësve (31.08.2026)") == dt.date(2026, 8, 31)
    assert c.find_date_in_text("Pranime 2026") is None


def test_unit_multiplier():
    assert c.unit_multiplier_from_text("Plani (000 lekë)") == 1000
    assert c.unit_multiplier_from_text("Vlera në mijë lekë") == 1000
    assert c.unit_multiplier_from_text("Fakti (mln lekë)") == 1_000_000
    assert c.unit_multiplier_from_text("Sasia (ton)") == 1


def test_coerce_value():
    assert c.coerce_value("budget", "programme_code", 5100) == "05100"
    assert c.coerce_value("budget", "programme_code", "05100") == "05100"
    assert c.coerce_value("budget", "planned_lek", "1.234,5", multiplier=1000) == 1234500.0
    assert c.coerce_value("waste", "tonnes", "2.562,4", multiplier=1000) == 2562.4  # not money
    assert c.coerce_value("budget", "line_type", "Kapitale") == "capital"
    assert c.coerce_value("budget", "line_type", "Korrente") == "current"
    assert c.coerce_value("budget", "month", "Janar 2026") == dt.date(2026, 1, 1)
    assert c.coerce_value("population", "basis", "Censusi 2023") == "census_2023"
    assert c.coerce_value("population", "basis", "civil_registry") == "civil_registry"
    assert c.coerce_value("requests", "status", "në proces") == "Në proces"
    assert c.coerce_value("requests", "admin_unit", "Shirgjani") == "Shirgjan"
    assert c.coerce_value("requests", "sla_days", "10") == 10
    assert c.coerce_value("requests", "created_at", "29.01.2026") == dt.date(2026, 1, 29)
    assert c.coerce_value("requests", "category", "  Ndriçimi  publik ") == "Ndriçimi publik"
    assert c.coerce_value("requests", "category", "") is None
    with pytest.raises(ValueError):
        c.coerce_value("requests", "created_at", "TOTALI")


def test_catalog_is_consistent_with_passports():
    pack = load_pack("core_kpi")
    for ds in c.DATASETS.values():
        requiring = {p.code for p in pack.passports if ds.key in p.required_datasets}
        assert set(ds.unlocks) == requiring, ds.key
        assert ds.owner in c.OWNERS
        assert ds.required_fields, ds.key
        for f in ds.fields:
            assert f.label["sq"] and f.label["en"]
            assert len(f.synonyms) >= 3, (ds.key, f.key)
    for p in pack.passports:
        assert p.owner in c.OWNERS
        assert p.area in c.AREAS
    info = c.get_dataset("revenue").api()
    assert info["owner"]["name"]["sq"] == "Drejtoria e të Ardhurave Vendore"
    assert {"key", "label", "type", "required"} <= set(info["fields"][0])


def test_topic_keywords():
    assert c.datasets_for_topic("Sa mbetje janë grumbulluar?") == ["waste"]
    assert "revenue" in c.datasets_for_topic("How much tax did we collect?")
    assert "staff" in c.datasets_for_topic("Sa punonjës ka bashkia?")
