import json
from types import SimpleNamespace

import httpx
import openai

from app.config import Settings
from app.llm.client import MODEL_FAST, MODEL_SMART, LLMClient, build_client, cost_of

SCHEMA = {
    "type": "object",
    "properties": {"field": {"type": ["string", "null"]}, "confidence": {"type": "number"}},
    "required": ["field", "confidence"],
    "additionalProperties": False,
}

MODELS = {MODEL_FAST: "gpt-5-mini", MODEL_SMART: "gpt-5"}


class FakeCompletions:
    def __init__(self, *, content="{}", finish="stop", refusal=None, raise_status=None):
        self.content = content
        self.finish = finish
        self.refusal = refusal
        self.raise_status = raise_status
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.raise_status:
            request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            response = httpx.Response(self.raise_status, request=request)
            raise openai.APIStatusError("error", response=response, body=None)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason=self.finish,
                    message=SimpleNamespace(content=self.content, refusal=self.refusal),
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=1200,
                completion_tokens=300,
                prompt_tokens_details=SimpleNamespace(cached_tokens=200),
            ),
        )


def make(db=None, **kw):
    completions = FakeCompletions(**kw)
    sdk = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = (lambda: db) if db is not None else None
    client = LLMClient(
        api_key="k", budget_usd=5.0, sdk=sdk, db=provider, provider="openai", models=MODELS
    )
    return client, completions


def test_json_call_maps_role_to_openai_model_and_uses_strict_schema(db):
    client, completions = make(db, content=json.dumps({"field": "month", "confidence": 0.9}))
    res = client.complete_json(
        "map",
        schema=SCHEMA,
        tool_name="column mapping",
        system="sys",
        model=MODEL_FAST,
        purpose="ingest_mapping",
        sent={"headers": 5, "samples_per_column": 5},
    )
    assert res.ok and res.data == {"field": "month", "confidence": 0.9}
    assert res.model == "gpt-5-mini" and res.used
    call = completions.calls[0]
    assert call["model"] == "gpt-5-mini"
    assert call["messages"][0] == {"role": "system", "content": "sys"}
    assert call["response_format"]["json_schema"]["strict"] is True
    assert call["response_format"]["json_schema"]["name"] == "column_mapping"
    assert call["reasoning_effort"] == "minimal" and call["max_completion_tokens"] >= 4096
    # 1000 uncached + 200 cached input, 300 output at gpt-5-mini prices
    assert abs(res.cost_usd - (1000 * 0.25 + 200 * 0.025 + 300 * 2.0) / 1e6) < 1e-12
    row = db.execute("SELECT model, ok, sent_json FROM llm_call").fetchone()
    assert row[0] == "gpt-5-mini" and row[1] is True
    assert json.loads(row[2])["rows_sent"] == 0


def test_invalid_json_length_and_refusal_are_errors(db):
    client, _ = make(db, content="not json")
    assert (
        client.complete_json("q", schema=SCHEMA, purpose="p", sent={}).error == "llm_invalid_json"
    )
    client, _ = make(db, content="{", finish="length")
    assert client.complete_json("q", schema=SCHEMA, purpose="p", sent={}).error == "llm_max_tokens"
    client, _ = make(db, content="", refusal="no")
    assert client.complete_json("q", schema=SCHEMA, purpose="p", sent={}).error == "llm_refusal"


def test_rejected_key_switches_to_rules_mode(db):
    client, completions = make(db, raise_status=401)
    assert client.mode == "live"
    res = client.complete_json("q", schema=SCHEMA, purpose="p", sent={})
    assert res.error == "llm_error:401" and res.used
    assert client.auth_failed and client.mode == "rules"
    # Later calls are skipped without reaching the provider again.
    assert client.complete_json("q", schema=SCHEMA, purpose="p", sent={}).error == (
        "llm_unavailable"
    )
    assert len(completions.calls) == 1


def test_build_client_prefers_openai_key(monkeypatch):
    s = Settings(openai_api_key="sk-test", anthropic_api_key=None, llm_provider="auto")
    client = build_client(s)
    assert client.provider == "openai" and client.available
    assert client.model_for(MODEL_SMART) == s.openai_model_smart
    s = Settings(openai_api_key="", anthropic_api_key="", llm_provider="auto")
    client = build_client(s)
    assert client.provider == "anthropic" and not client.available and client.mode == "rules"


def test_dated_model_snapshot_is_priced_by_prefix():
    from app.llm.client import _Usage

    assert cost_of("gpt-5-mini-2025-08-07", _Usage(input_tokens=1_000_000)) == 0.25


def test_verify_key_flags_rejected_key_without_spending():
    request = httpx.Request("GET", "https://api.openai.com/v1/models")

    def reject():
        raise openai.AuthenticationError(
            "bad key", response=httpx.Response(401, request=request), body=None
        )

    sdk = SimpleNamespace(models=SimpleNamespace(list=reject))
    client = LLMClient(api_key="k", budget_usd=5.0, sdk=sdk, provider="openai", models=MODELS)
    assert client.mode == "live"
    assert client.verify_key() is False
    assert client.auth_failed and client.mode == "rules" and client.spent_usd == 0

    ok_sdk = SimpleNamespace(models=SimpleNamespace(list=lambda: []))
    client = LLMClient(api_key="k", budget_usd=5.0, sdk=ok_sdk, provider="openai", models=MODELS)
    assert client.verify_key() is True and client.mode == "live"
