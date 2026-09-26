"""HTTP contract of the ingest endpoints (contract §7)."""

from pathlib import Path

import pytest

from app.config import get_settings

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
REVENUE = "zarfi-2_SINTETIKE_taksat_tarifat_arketimi_2026.xlsx"
WASTE = "zarfi-1_SINTETIKE_pastrimi_mbetjet_2026.csv"
API = "/api/v1"

PREVIEW_KEYS = {
    "preview_id",
    "filename",
    "file_hash",
    "size_bytes",
    "synthetic",
    "dataset",
    "dataset_candidates",
    "sheet",
    "header_row",
    "data_rows",
    "unit_multiplier",
    "unit_note",
    "excluded_rows",
    "columns",
    "mapping",
    "question",
    "recipe",
    "llm",
    "steps",
    "warnings",
}
RECEIPT_KEYS = {
    "source_id",
    "filename",
    "file_hash",
    "dataset",
    "dataset_name",
    "synthetic",
    "rows_read",
    "rows_loaded",
    "rows_excluded",
    "reconciliation",
    "pii_dropped",
    "unit_multiplier",
    "llm",
    "recipe",
    "indicators_unlocked",
    "coverage",
    "loaded_at",
    "duration_ms",
}


def upload(client, name: str, content: bytes | None = None, **form):
    body = content if content is not None else (SAMPLES / name).read_bytes()
    return client.post(
        f"{API}/ingest/preview", files={"file": (name, body, "application/octet-stream")}, data=form
    )


def commit_body(preview: dict, save_recipe: bool = False) -> dict:
    return {
        "preview_id": preview["preview_id"],
        "dataset": preview["dataset"]["key"],
        "mapping": [{"column": m["column"], "field": m["field"]} for m in preview["mapping"]],
        "save_recipe": save_recipe,
    }


def assert_error(res, status: int, code: str):
    assert res.status_code == status, res.text
    detail = res.json()["detail"]
    assert detail["code"] == code
    assert detail["message"]["sq"] and detail["message"]["en"]


def test_gap_to_proof_loop_over_http(client):
    res = client.post(f"{API}/demo/reset")
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["coverage"] == {"computable": 6, "total": 13}

    res = upload(client, REVENUE)
    assert res.status_code == 200, res.text
    preview = res.json()
    assert set(preview) == PREVIEW_KEYS
    assert preview["dataset"]["key"] == "revenue"
    col = preview["columns"][0]
    assert set(col) == {"index", "name", "inferred_type", "samples", "null_pct", "pii", "dropped"}
    m = preview["mapping"][0]
    assert set(m) == {"column", "field", "confidence", "reason", "transform", "source"}
    assert set(preview["recipe"]) == {"hit", "recipe_id", "fingerprint", "drift"}
    assert set(preview["llm"]) == {"used", "model", "latency_ms", "cost_usd", "error", "sent"}

    res = client.post(f"{API}/ingest/commit", json=commit_body(preview, save_recipe=True))
    assert res.status_code == 200, res.text
    receipt = res.json()
    assert set(receipt) >= RECEIPT_KEYS
    assert all(r["ok"] for r in receipt["reconciliation"])
    assert [u["code"] for u in receipt["indicators_unlocked"]] == ["REV-01", "REV-02"]
    assert receipt["coverage"] == {"computable": 8, "total": 13}
    assert receipt["recipe"]["saved"] is True

    sources = client.get(f"{API}/sources").json()
    assert sources[0]["source_id"] == receipt["source_id"]
    assert sources[0]["mapping"] and set(sources[0]) >= RECEIPT_KEYS
    assert len(sources) == 4

    recipes = client.get(f"{API}/ingest/recipes").json()
    assert len(recipes) == 1 and recipes[0]["dataset"] == "revenue"
    res = client.delete(f"{API}/ingest/recipes")
    assert res.json() == {"ok": True, "deleted": 1}

    health = client.get(f"{API}/health").json()
    assert health["synthetic"] is True


def test_samples_listing_preview_and_download(client):
    listing = client.get(f"{API}/samples").json()
    assert len(listing) == 7
    first = listing[0]
    assert set(first) == {
        "name",
        "label",
        "dataset_hint",
        "envelope",
        "preload",
        "size_bytes",
        "synthetic",
        "loaded",
    }
    assert all(s["size_bytes"] > 0 and s["synthetic"] for s in listing)
    assert not any(s["loaded"] for s in listing)
    assert sorted(s["envelope"] for s in listing if s["envelope"]) == [1, 2, 3]

    res = client.post(f"{API}/samples/{WASTE}/preview")
    assert res.status_code == 200
    assert res.json()["dataset"]["key"] == "waste"
    res = client.post(f"{API}/ingest/commit", json=commit_body(res.json()))
    assert res.status_code == 200
    loaded = {s["name"]: s["loaded"] for s in client.get(f"{API}/samples").json()}
    assert loaded[WASTE] is True

    res = client.get(f"{API}/samples/{WASTE}/file")
    assert res.status_code == 200 and res.content == (SAMPLES / WASTE).read_bytes()


@pytest.mark.parametrize(
    "name",
    ["manifest.json", "..%2Fapp%2Fconfig.py", "..%5C..%5Capp%5Cconfig.py", "nope.csv", "%2e%2e"],
)
def test_samples_reject_unknown_names(client, name):
    res = client.post(f"{API}/samples/{name}/preview")
    assert res.status_code == 404
    res = client.get(f"{API}/samples/{name}/file")
    assert res.status_code == 404


def test_upload_limits_and_errors(client, monkeypatch):
    assert_error(upload(client, "notes.txt", b"hello"), 415, "unsupported_file_type")
    assert_error(upload(client, "broken.xlsx", b"not a zip"), 422, "unreadable_file")
    monkeypatch.setattr("app.ingest.router.MAX_BYTES", 10)
    assert_error(upload(client, "big.csv", b"a;b\n1;2\n3;4\n"), 413, "file_too_large")


def test_preview_with_explicit_dataset_and_remap(client):
    res = upload(client, REVENUE, dataset="budget")
    assert res.status_code == 200
    preview = res.json()
    assert preview["dataset"]["key"] == "budget"
    step = next(s for s in preview["steps"] if s["code"] == "dataset")
    assert "përdoruesi" in step["message"]["sq"]
    res = client.post(
        f"{API}/ingest/remap", json={"preview_id": preview["preview_id"], "dataset": "revenue"}
    )
    assert res.status_code == 200 and res.json()["dataset"]["key"] == "revenue"
    assert_error(upload(client, REVENUE, dataset="nope"), 422, "unknown_dataset")


def test_commit_errors(client):
    body = {"preview_id": "missing", "dataset": "waste", "mapping": []}
    assert_error(client.post(f"{API}/ingest/commit", json=body), 404, "preview_not_found")
    preview = upload(client, WASTE).json()
    body = commit_body(preview)
    body["mapping"] = [m for m in body["mapping"] if m["field"] != "tonnes"]
    assert_error(client.post(f"{API}/ingest/commit", json=body), 422, "missing_required_fields")


def test_demo_endpoints_can_be_disabled(client, monkeypatch):
    monkeypatch.setenv("DEMO_RESET_ENABLED", "false")
    get_settings.cache_clear()
    assert_error(client.post(f"{API}/demo/reset"), 403, "demo_reset_disabled")
    assert_error(client.delete(f"{API}/ingest/recipes"), 403, "demo_reset_disabled")
    get_settings.cache_clear()
