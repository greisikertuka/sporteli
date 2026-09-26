from app.config import Settings


def test_health_reports_contract_shape(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {
        "status",
        "db",
        "llm",
        "mode",
        "version",
        "spent_usd",
        "budget_usd",
        "synthetic",
    }
    assert body["status"] == "ok"
    assert body["db"] is True
    assert body["llm"] is False
    assert body["mode"] == "rules"
    assert body["synthetic"] is False
    assert body["spent_usd"] == 0


def test_health_synthetic_flag_follows_sources(client):
    from app.warehouse.db import get_db

    get_db().execute("INSERT INTO source (id, filename, synthetic) VALUES ('s1', 'x.csv', true)")
    assert client.get("/api/v1/health").json()["synthetic"] is True


def test_openapi_is_served_with_title(client):
    res = client.get("/openapi.json")
    assert res.status_code == 200
    assert res.json()["info"]["title"] == "Sportel API"


def test_datasets_endpoint(client):
    from app.warehouse.db import get_db

    get_db().execute(
        "INSERT INTO waste_collection (source_id, row_no, tonnes) VALUES ('s1', 3, 1.0), "
        "('s1', 4, 2.0)"
    )
    res = client.get("/api/v1/datasets")
    assert res.status_code == 200
    items = {d["key"]: d for d in res.json()}
    assert list(items) == ["requests", "budget", "waste", "revenue", "staff", "population"]
    waste = items["waste"]
    assert waste["loaded"] is True and waste["rows"] == 2 and waste["sources"] == 1
    assert waste["table"] == "waste_collection"
    assert waste["owner"] == {
        "key": "public_services",
        "name": {"sq": "Drejtoria e Shërbimeve Publike", "en": "Public Services Directorate"},
    }
    assert waste["unlocks"] == ["WST-01", "WST-02", "WST-03"]
    assert items["revenue"]["loaded"] is False
    field = waste["fields"][0]
    assert set(field) == {"key", "label", "type", "required"}


def test_settings_parse_cors_origins(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    assert Settings().cors_origins == ["http://a.test", "http://b.test"]
    monkeypatch.setenv("CORS_ORIGINS", '["http://c.test"]')
    assert Settings().cors_origins == ["http://c.test"]
    monkeypatch.delenv("CORS_ORIGINS")
    s = Settings()
    assert "http://localhost:3100" in s.cors_origins
    assert s.demo_reset_enabled is True
    assert s.samples_path.name == "samples" and s.samples_path.is_absolute()


def _assert_contract_error(res, status: int, code: str) -> dict:
    assert res.status_code == status, res.text
    detail = res.json()["detail"]
    assert detail["code"] == code
    assert set(detail["message"]) == {"sq", "en"} and all(detail["message"].values())
    return detail


def test_validation_errors_use_the_contract_shape(client):
    detail = _assert_contract_error(
        client.post("/api/v1/ingest/commit", json={}), 422, "invalid_request"
    )
    assert "preview_id" in detail["message"]["en"]
    assert {tuple(e["loc"]) for e in detail["errors"]} >= {("body", "preview_id")}
    _assert_contract_error(client.post("/api/v1/ingest/preview"), 422, "invalid_request")
    _assert_contract_error(
        client.get("/api/v1/indicators/REQ-01/lineage", params={"limit": 0}), 422, "invalid_request"
    )


def test_routing_errors_use_the_contract_shape(client):
    _assert_contract_error(client.get("/api/v1/no-such-endpoint"), 404, "not_found")
    _assert_contract_error(client.put("/api/v1/health"), 405, "method_not_allowed")
    # errors raised by the app keep their own code
    _assert_contract_error(client.get("/api/v1/indicators/NOPE"), 404, "unknown_indicator")
