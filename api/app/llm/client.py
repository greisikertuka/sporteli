"""Single entry point for Claude calls: model choice, spend tracking, graceful failure.

Callers never see exceptions from the LLM layer; they get an LLMResult with ok=False
and an error code, so the dashboard keeps working when AI is unavailable.
"""

import logging
from dataclasses import dataclass
from typing import Any

import anthropic

from app.config import get_settings

log = logging.getLogger(__name__)

MODEL_FAST = "claude-haiku-4-5"  # column mapping, classification
MODEL_SMART = "claude-sonnet-5"  # copilot SQL, briefings

# USD per 1M tokens (input, output)
PRICING: dict[str, tuple[float, float]] = {
    MODEL_FAST: (1.0, 5.0),
    MODEL_SMART: (2.0, 10.0),
}


@dataclass(frozen=True)
class LLMResult:
    ok: bool
    text: str | None = None
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient:
    def __init__(self, *, api_key: str | None, budget_usd: float, sdk: Any | None = None):
        self._api_key = api_key
        self._budget_usd = budget_usd
        self._sdk = (
            sdk if sdk is not None else (anthropic.Anthropic(api_key=api_key) if api_key else None)
        )
        self.spent_usd = 0.0

    @property
    def available(self) -> bool:
        return self._sdk is not None

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str = MODEL_FAST,
        max_tokens: int = 1024,
    ) -> LLMResult:
        if not self.available:
            return LLMResult(ok=False, error="llm_unavailable")
        if self.spent_usd >= self._budget_usd:
            return LLMResult(ok=False, error="llm_budget_exhausted")

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        try:
            response = self._sdk.messages.create(**kwargs)
        except anthropic.RateLimitError:
            log.warning("LLM rate limited")
            return LLMResult(ok=False, error="llm_error:rate_limited")
        except anthropic.APIStatusError as e:
            log.warning("LLM API error %s: %s", e.status_code, e.message)
            return LLMResult(ok=False, error=f"llm_error:{e.status_code}")
        except anthropic.APIConnectionError:
            log.warning("LLM connection error")
            return LLMResult(ok=False, error="llm_error:connection")
        except Exception:  # contract: the LLM layer never crashes the app
            log.exception("Unexpected LLM failure")
            return LLMResult(ok=False, error="llm_error:unexpected")

        usage = response.usage
        in_price, out_price = PRICING.get(model, PRICING[MODEL_SMART])
        self.spent_usd += (usage.input_tokens * in_price + usage.output_tokens * out_price) / 1e6

        if getattr(response, "stop_reason", None) == "refusal":
            return LLMResult(ok=False, error="llm_refusal")

        text = "".join(b.text for b in response.content if b.type == "text")
        return LLMResult(
            ok=True,
            text=text,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    """Process-wide client so spend is tracked across requests."""
    global _client
    if _client is None:
        s = get_settings()
        _client = LLMClient(api_key=s.anthropic_api_key, budget_usd=s.llm_budget_usd)
    return _client
