def test_health_reports_ok_and_db(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["db"] is True
    assert body["llm"] is False


def test_openapi_is_served(client):
    assert client.get("/openapi.json").status_code == 200
