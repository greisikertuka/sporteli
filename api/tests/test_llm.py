from types import SimpleNamespace

from app.llm.client import MODEL_FAST, LLMClient


class FakeMessages:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("boom")
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hello")],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
        )


def fake_sdk(**kw):
    return SimpleNamespace(messages=FakeMessages(**kw))


def test_without_key_is_unavailable():
    llm = LLMClient(api_key=None, budget_usd=5)
    assert llm.available is False
    res = llm.complete("hi")
    assert res.ok is False
    assert res.error == "llm_unavailable"


def test_success_tracks_spend():
    sdk = fake_sdk()
    llm = LLMClient(api_key="k", budget_usd=5, sdk=sdk)
    res = llm.complete("hi", system="be brief")
    assert res.ok and res.text == "hello"
    assert (res.input_tokens, res.output_tokens) == (1000, 500)
    assert llm.spent_usd > 0
    assert sdk.messages.calls[0]["model"] == MODEL_FAST
    assert sdk.messages.calls[0]["system"] == "be brief"


def test_sdk_error_is_caught():
    llm = LLMClient(api_key="k", budget_usd=5, sdk=fake_sdk(fail=True))
    res = llm.complete("hi")
    assert res.ok is False
    assert res.error.startswith("llm_error")


def test_budget_exhausted_blocks_calls():
    sdk = fake_sdk()
    llm = LLMClient(api_key="k", budget_usd=0.0, sdk=sdk)
    res = llm.complete("hi")
    assert res.error == "llm_budget_exhausted"
    assert sdk.messages.calls == []
