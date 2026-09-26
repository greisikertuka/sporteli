import json
from types import SimpleNamespace

import pytest

from app.llm.client import MODEL_FAST, MODEL_SMART, LLMClient, get_llm, reset_llm


class FakeMessages:
    def __init__(self, *, fail: bool = False, text: str = "hello", stop_reason: str = "end_turn"):
        self.fail = fail
        self.text = text
        self.stop_reason = stop_reason
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("boom")
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text=self.text),
            ],
            stop_reason=self.stop_reason,
            usage=SimpleNamespace(
                input_tokens=1000,
                output_tokens=500,
                cache_creation_input_tokens=None,
                cache_read_input_tokens=0,
            ),
        )


def fake_sdk(**kw):
    return SimpleNamespace(messages=FakeMessages(**kw))


SCHEMA = {
    "type": "object",
    "properties": {"field": {"type": ["string", "null"]}, "confidence": {"type": "number"}},
    "required": ["field", "confidence"],
    "additionalProperties": False,
}


def calls_in_db(db) -> list[tuple]:
    return db.execute(
        "SELECT purpose, model, ok, error, input_tokens, output_tokens, cost_usd, sent_json "
        "FROM llm_call ORDER BY ts"
    ).fetchall()


def make(db=None, budget=5.0, **kw):
    sdk = fake_sdk(**kw)
    provider = (lambda: db) if db is not None else None
    return LLMClient(api_key="k", budget_usd=budget, sdk=sdk, db=provider), sdk


def test_without_key_is_unavailable_and_not_logged(db):
    llm = LLMClient(api_key=None, budget_usd=5, db=lambda: db)
    assert llm.available is False
    assert llm.mode == "rules"
    res = llm.complete_json("hi", schema=SCHEMA, purpose="mapping", sent={"headers": 3})
    assert res.ok is False and res.error == "llm_unavailable"
    assert res.used is False
    assert calls_in_db(db) == []


def test_success_tracks_spend():
    llm, sdk = make()
    res = llm.complete("hi", system="be brief")
    assert res.ok and res.text == "hello"
    assert (res.input_tokens, res.output_tokens) == (1000, 500)
    assert llm.spent_usd == pytest.approx((1000 * 1.0 + 500 * 5.0) / 1e6)
    assert sdk.messages.calls[0]["model"] == MODEL_FAST
    assert sdk.messages.calls[0]["system"] == "be brief"
    assert "output_config" not in sdk.messages.calls[0]  # Haiku: no effort parameter
    assert llm.mode == "live"


def test_complete_json_uses_output_config_and_parses(db):
    payload = {"field": "tonnes", "confidence": 0.9}
    llm, sdk = make(db, text=json.dumps(payload))
    res = llm.complete_json(
        "map these headers",
        schema=SCHEMA,
        tool_name="column_mapping",
        purpose="mapping",
        sent={"headers": 5, "samples_per_column": 5},
    )
    assert res.ok and res.data == payload
    assert res.used and res.model == MODEL_FAST and res.latency_ms is not None
    call = sdk.messages.calls[0]
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": SCHEMA}
    assert "effort" not in call["output_config"]
    rows = calls_in_db(db)
    assert len(rows) == 1
    purpose, model, ok, error, tin, tout, cost, sent = rows[0]
    assert (purpose, model, ok, error, tin, tout) == ("mapping", MODEL_FAST, True, None, 1000, 500)
    assert cost == pytest.approx(res.cost_usd)
    assert json.loads(sent) == {
        "headers": 5,
        "samples_per_column": 5,
        "output": "column_mapping",
        "rows_sent": 0,
    }
    summary = res.summary()
    assert summary["used"] is True and summary["cost_usd"] > 0


def test_sonnet_gets_low_effort():
    llm, sdk = make(text="{}")
    llm.complete_json("q", schema=SCHEMA, model=MODEL_SMART, purpose="ask", sent={})
    assert sdk.messages.calls[0]["output_config"]["effort"] == "low"


@pytest.mark.parametrize(
    ("kw", "error"),
    [
        ({"stop_reason": "max_tokens", "text": '{"field": '}, "llm_max_tokens"),
        ({"stop_reason": "refusal", "text": ""}, "llm_refusal"),
        ({"text": "not json"}, "llm_invalid_json"),
    ],
)
def test_bad_stop_reasons_are_errors_and_logged(db, kw, error):
    llm, _ = make(db, **kw)
    res = llm.complete_json("q", schema=SCHEMA, purpose="mapping", sent={"headers": 1})
    assert res.ok is False and res.error == error and res.data is None
    assert res.used  # the call happened and was billed
    rows = calls_in_db(db)
    assert len(rows) == 1 and rows[0][2] is False and rows[0][3] == error
    assert llm.spent_usd > 0


def test_sdk_error_is_caught_and_logged(db):
    llm, _ = make(db, fail=True)
    res = llm.complete("hi", purpose="test")
    assert res.ok is False
    assert res.error.startswith("llm_error")
    rows = calls_in_db(db)
    assert len(rows) == 1 and rows[0][3] == "llm_error:unexpected" and rows[0][6] == 0


def test_budget_exhausted_blocks_calls():
    llm, sdk = make(budget=0.0)
    res = llm.complete("hi")
    assert res.error == "llm_budget_exhausted"
    assert sdk.messages.calls == []
    assert llm.mode == "rules"


def test_spend_is_restored_from_the_log(db):
    llm, _ = make(db, text="{}")
    llm.complete_json("q", schema=SCHEMA, purpose="mapping", sent={})
    llm.complete_json("q", schema=SCHEMA, purpose="mapping", sent={})
    fresh = LLMClient(api_key=None, budget_usd=5, db=lambda: db)
    assert fresh.restore_spend() == pytest.approx(llm.spent_usd)
    calls = fresh.recent_calls()
    assert len(calls) == 2
    assert set(calls[0]) == {
        "ts",
        "purpose",
        "model",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "latency_ms",
        "ok",
        "error",
        "sent",
    }
    assert calls[0]["sent"]["rows_sent"] == 0


def test_get_llm_singleton_restores_spend(db):
    db.execute("INSERT INTO llm_call (id, ts, cost_usd, ok) VALUES ('x', now(), 1.25, true)")
    reset_llm()
    llm = get_llm()
    assert llm is get_llm()
    assert llm.spent_usd == pytest.approx(1.25)
    assert llm.mode == "rules"  # no API key in tests
