"""GET /coverage?pack=al_smp — SMP 2024 Annex A coverage map (52 indicators)."""

from app.catalog import OWNERS
from app.indicators.coverage import load_coverage_pack
from app.warehouse.db import get_db
from tests.test_indicators import ALL, START, load_mini

DOCUMENT = {5, 16, 22, 26, 27, 28, 30, 31, 35, 40}
NATIONAL = set(range(41, 53))
MANUAL = {29, 32, 33, 36, 37, 38, 39}
MAPPED = {13: "REV-02", 14: "WST-02", 15: "WST-03", 23: "HR-02", 25: "HR-01"}
MISSING = set(range(1, 53)) - DOCUMENT - NATIONAL - MANUAL - set(MAPPED)


def coverage(client, **params) -> dict:
    res = client.get("/api/v1/coverage", params=params)
    assert res.status_code == 200, res.text
    return res.json()


def by_number(body: dict) -> dict[int, dict]:
    return {i["number"]: i for i in body["items"]}


def test_pack_lists_the_52_annex_a_indicators_verbatim():
    pack = load_coverage_pack("al_smp")
    items = {it.number: it for _, it in pack.items}
    assert sorted(items) == list(range(1, 53))
    assert items[1].name_sq == "Shkalla e regjistrimit në çerdhe"
    assert items[13].name_sq == "Mbulimi kostos së menaxhimit të mbetjeve nga tarifa e shërbimit"
    assert items[19].name_sq == (
        "Numri i rasteve të trajtuara kundrejt rasteve të raportuara të dhunës në familje "
        "(sipas gjinisë, moshës dhe llojit të dhunës)"
    )
    assert items[25].name_sq == "Punonjës për 1'000 banorë"
    assert items[27].name_sq == "Publikimi i Planit Buxhetor Afatmesëm PBA 2024-2026"
    assert items[47].name_sq == "Shkalla e ekzekutimit të buxhetit: fakt përkundrejt plan"
    assert items[52].name_sq == "Pesha e shpenzimeve operacionale në buxhet"
    areas = [a.name["sq"] for a in pack.areas]
    assert areas == [
        "Arsimi", "Bujqësia", "Pyje dhe kullota", "Mbrojtja nga zjarri", "Menaxhimi i mbetjeve",
        "Shërbimet sociale", "Burimet njerëzore", "Mirëqeverisja", "Integrimi evropian",
        "Barazia gjinore", "Financa",
    ]  # fmt: skip
    assert pack.approval == "pending"


def test_start_state(client):
    load_mini(get_db(), START)
    body = coverage(client)
    assert set(body) == {"pack", "label", "approval", "counts", "total", "items"}
    assert body["pack"] == "al_smp" and body["approval"] == "pending"
    assert set(body["label"]) == {"sq", "en"}
    assert body["total"] == 52
    assert body["counts"] == {
        "computable": 0,
        "missing": len(MISSING) + len(MAPPED),
        "document": 10,
        "national": 12,
        "manual": 7,
    }
    items = by_number(body)
    for item in body["items"]:
        assert set(item) == {"number", "area", "name_sq", "state", "passport_code", "owner", "note"}
        assert item["note"] is None or set(item["note"]) == {"sq", "en"}
    assert {n for n, i in items.items() if i["state"] == "document"} == DOCUMENT
    assert {n for n, i in items.items() if i["state"] == "national"} == NATIONAL
    assert {n for n, i in items.items() if i["state"] == "manual"} == MANUAL

    rev2 = items[13]  # mapped to REV-02, whose revenue export is not loaded yet
    assert rev2["state"] == "missing" and rev2["passport_code"] == "REV-02"
    assert rev2["owner"] == OWNERS["local_revenue"]
    assert rev2["note"]["sq"] == (
        "Mungon: eksporti i arkëtimit të taksave dhe tarifave · do të llogaritet nga pasaporta "
        "REV-02."
    )
    assert items[14]["owner"] == OWNERS["public_services"]
    assert items[25]["owner"] == OWNERS["hr"] and items[23]["passport_code"] == "HR-02"
    assert items[1]["area"] == {"sq": "Arsimi", "en": "Education"}


def test_full_state_marks_the_mapped_indicators_computable(client):
    load_mini(get_db(), ALL)
    body = coverage(client)
    assert body["counts"] == {
        "computable": 5,
        "missing": 18,
        "document": 10,
        "national": 12,
        "manual": 7,
    }
    items = by_number(body)
    assert {n: i["passport_code"] for n, i in items.items() if i["state"] == "computable"} == MAPPED
    assert items[13]["owner"] == OWNERS["local_revenue"]
    assert items[13]["note"]["en"].startswith("Computed by passport REV-02")
    assert items[14]["note"]["sq"].endswith("Baza e popullsisë: Censusi 2023.")
    assert {n for n, i in items.items() if i["state"] == "missing"} == MISSING


def test_owners_and_notes(client):
    body = coverage(client)
    items = by_number(body)
    for n in NATIONAL:
        assert items[n]["owner"] is None
        assert items[n]["note"]["sq"].startswith(
            "Burimi: Ministria e Financave, llogaritur nga AMVV"
        )
    assert items[47]["passport_code"] == "FIN-01" and "FIN-01" in items[47]["note"]["en"]
    for n in MISSING | DOCUMENT | MANUAL:
        assert items[n]["owner"] and set(items[n]["owner"]) == {"sq", "en"}, n
        assert items[n]["note"], n
    assert items[33]["owner"] == OWNERS["statistics"]
    assert items[27]["owner"] == OWNERS["finance"]
    assert items[10]["owner"]["en"] == "Fire Protection and Rescue Service"
    assert "no personal data" in items[19]["note"]["en"]
    assert items[5]["note"]["en"].startswith("Document check")
    assert items[29]["note"]["en"].startswith("Manual value")


def test_unknown_coverage_pack(client):
    res = client.get("/api/v1/coverage", params={"pack": "core_kpi"})
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "unknown_pack"
    assert client.get("/api/v1/coverage", params={"pack": "nope"}).status_code == 404
