"""Single entry point for LLM calls: provider, model choice, spend tracking, call log, fallback.

Two providers sit behind the same interface: Anthropic (Claude) and OpenAI (the organisers'
hackathon key). Callers pass a *role* (``MODEL_FAST`` for column mapping, ``MODEL_SMART`` for
reading questions); the client maps it to the provider's model.

Callers never see exceptions from the LLM layer; they get an ``LLMResult`` with ``ok=False``
and an error code, so the product keeps working (RULES mode) when AI is unavailable.

Every call that reaches the SDK (success or failure) is written to the ``llm_call`` table with
what was sent (a summary such as header/sample counts; never rows). Calls skipped because no
key is configured or the budget is exhausted are not logged. ``spent_usd`` is restored from the
log at startup, so the budget survives restarts.

Structured JSON uses ``output_config.format`` (JSON schema, constrained decoding): the first
text block is guaranteed to be valid JSON for the schema. Schemas must follow the structured
outputs subset (``additionalProperties: false`` on every object, all properties listed in
``required``; use ``"type": ["string", "null"]`` for optional values).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import anthropic
import duckdb
import openai

from app.config import get_settings

log = logging.getLogger(__name__)

MODEL_FAST = "claude-haiku-4-5"  # column mapping, classification
MODEL_SMART = "claude-sonnet-5"  # copilot intent / SQL

# USD per 1M tokens (input, output). Cache writes cost 1.25x input, cache reads 0.1x input.
PRICING: dict[str, tuple[float, float]] = {
    MODEL_FAST: (1.0, 5.0),
    MODEL_SMART: (2.0, 10.0),
    # OpenAI list prices (USD per 1M tokens), used to track spend against the team budget.
    "gpt-5": (1.25, 10.0),
    "gpt-5-mini": (0.25, 2.0),
    "gpt-5-nano": (0.05, 0.4),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4.1-mini": (0.4, 1.6),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
}

# Models that accept output_config.effort (Haiku 4.5 rejects it). Sonnet 5 runs adaptive
# thinking by default, billed as output, so we pin effort low for these short tasks.
_EFFORT_MODELS = {MODEL_SMART}

Mode = Literal["live", "rules"]
Provider = Literal["anthropic", "openai"]


def _is_reasoning_model(model: str) -> bool:
    """OpenAI reasoning models: max_completion_tokens also covers hidden reasoning tokens."""
    return model.startswith(("gpt-5", "o1", "o3", "o4"))


@dataclass(frozen=True)
class LLMResult:
    ok: bool
    text: str | None = None
    data: Any = None
    """Parsed JSON (``complete_json`` only)."""
    error: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int | None = None
    stop_reason: str | None = None
    call_id: str | None = None
    """``llm_call.id`` of the logged call (None when the call was skipped)."""

    @property
    def used(self) -> bool:
        """True when the SDK was actually called (the call is in the log)."""
        return self.call_id is not None

    def summary(self) -> dict:
        """The ``llm`` object used in API responses (IngestPreview/LoadReceipt/AskAnswer)."""
        return {
            "used": self.used,
            "model": self.model if self.used else None,
            "latency_ms": self.latency_ms,
            "cost_usd": round(self.cost_usd, 6) if self.used else None,
            "error": self.error,
        }


DbProvider = Callable[[], duckdb.DuckDBPyConnection]


@dataclass
class _Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write: int = 0
    cache_read: int = 0


def _usage(response: Any) -> _Usage:
    u = getattr(response, "usage", None)
    if u is None:
        return _Usage()
    return _Usage(
        input_tokens=int(getattr(u, "input_tokens", 0) or 0),
        output_tokens=int(getattr(u, "output_tokens", 0) or 0),
        cache_write=int(getattr(u, "cache_creation_input_tokens", 0) or 0),
        cache_read=int(getattr(u, "cache_read_input_tokens", 0) or 0),
    )


def _price(model: str) -> tuple[float, float]:
    if model in PRICING:
        return PRICING[model]
    # Dated snapshots such as "gpt-5-mini-2025-08-07": the longest known prefix wins.
    for known in sorted(PRICING, key=len, reverse=True):
        if model.startswith(known):
            return PRICING[known]
    return PRICING[MODEL_SMART]


def cost_of(model: str, usage: _Usage) -> float:
    in_price, out_price = _price(model)
    return (
        usage.input_tokens * in_price
        + usage.cache_write * in_price * 1.25
        + usage.cache_read * in_price * 0.1
        + usage.output_tokens * out_price
    ) / 1e6


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str | None,
        budget_usd: float,
        sdk: Any | None = None,
        db: DbProvider | None = None,
        provider: Provider = "anthropic",
        models: dict[str, str] | None = None,
        base_url: str | None = None,
    ):
        self._api_key = api_key
        self._budget_usd = budget_usd
        self.provider: Provider = provider
        self._models = dict(models or {})
        if sdk is None and api_key:
            if provider == "openai":
                sdk = openai.OpenAI(
                    api_key=api_key, base_url=base_url or None, timeout=45.0, max_retries=1
                )
            else:
                sdk = anthropic.Anthropic(api_key=api_key, timeout=45.0, max_retries=1)
        self._sdk = sdk
        self._db = db
        self._lock = threading.Lock()
        self.spent_usd = 0.0
        self.auth_failed = False
        """Set when the provider rejects the key (401/403): the client drops to RULES mode."""

    # ---- state -------------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._sdk is not None and not self.auth_failed

    def verify_key(self) -> bool:
        """List models (free, no tokens). A rejected key sets ``auth_failed``; network errors
        leave the mode unchanged. Returns True when the key is known to work."""
        if self._sdk is None:
            return False
        try:
            self._sdk.models.list()
        except (
            openai.AuthenticationError,
            openai.PermissionDeniedError,
            anthropic.AuthenticationError,
            anthropic.PermissionDeniedError,
        ):
            log.warning("The %s API rejected the configured key: RULES mode", self.provider)
            self.auth_failed = True
            return False
        except Exception:  # offline or transient: do not flip the mode
            log.warning("Could not verify the %s key (network?)", self.provider)
            return False
        return True

    def model_for(self, role: str) -> str:
        """Provider model id for a role constant (MODEL_FAST / MODEL_SMART)."""
        return self._models.get(role, role)

    @property
    def budget_usd(self) -> float:
        return self._budget_usd

    @property
    def mode(self) -> Mode:
        """``live`` when a key is configured and budget remains, otherwise ``rules``."""
        return "live" if self.available and self.spent_usd < self._budget_usd else "rules"

    def restore_spend(self) -> float:
        """Load the total spend from ``llm_call`` (called once at startup)."""
        if self._db is None:
            return self.spent_usd
        try:
            cur = self._db().cursor()
            try:
                row = cur.execute("SELECT coalesce(sum(cost_usd), 0) FROM llm_call").fetchone()
            finally:
                cur.close()
            with self._lock:
                self.spent_usd = float(row[0] or 0.0)
        except Exception:  # the LLM layer never crashes the app
            log.exception("Could not restore LLM spend from llm_call")
        return self.spent_usd

    def recent_calls(self, limit: int = 100) -> list[dict]:
        """Newest-first call log in the ``GET /llm/calls`` shape."""
        if self._db is None:
            return []
        cur = self._db().cursor()
        try:
            rows = cur.execute(
                "SELECT ts, purpose, model, input_tokens, output_tokens, cost_usd, latency_ms, "
                "ok, error, sent_json FROM llm_call ORDER BY ts DESC LIMIT ?",
                [limit],
            ).fetchall()
        finally:
            cur.close()
        out = []
        for ts, purpose, model, tin, tout, cost, lat, ok, err, sent in rows:
            out.append(
                {
                    "ts": ts.isoformat() if ts else None,
                    "purpose": purpose,
                    "model": model,
                    "input_tokens": tin or 0,
                    "output_tokens": tout or 0,
                    "cost_usd": cost or 0.0,
                    "latency_ms": lat or 0,
                    "ok": bool(ok),
                    "error": err,
                    "sent": json.loads(sent) if sent else None,
                }
            )
        return out

    # ---- calls -------------------------------------------------------------------------

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str = MODEL_FAST,
        max_tokens: int = 1024,
        purpose: str = "complete",
        sent: dict | None = None,
    ) -> LLMResult:
        """Free-text completion (never used for numbers shown to users)."""
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        if model in _EFFORT_MODELS:
            kwargs["output_config"] = {"effort": "low"}
        return self._call(kwargs, purpose=purpose, sent=sent or {}, parse_json=False)

    def complete_json(
        self,
        prompt: str,
        *,
        schema: dict,
        tool_name: str = "structured_output",
        system: str | None = None,
        model: str = MODEL_FAST,
        max_tokens: int = 2048,
        purpose: str,
        sent: dict,
    ) -> LLMResult:
        """Structured JSON output constrained to ``schema``; ``result.data`` holds the object.

        ``tool_name`` names the output in the call log. ``sent`` summarises what leaves the
        building (e.g. ``{"headers": 9, "samples_per_column": 5}``); ``rows_sent`` is forced
        to 0 because rows are never sent.
        """
        output_config: dict[str, Any] = {"format": {"type": "json_schema", "schema": schema}}
        if model in _EFFORT_MODELS:
            output_config["effort"] = "low"
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": output_config,
        }
        if system:
            kwargs["system"] = system
        summary = {**sent, "output": tool_name}
        return self._call(
            kwargs, purpose=purpose, sent=summary, parse_json=True, schema=schema, name=tool_name
        )

    def _call(
        self,
        kwargs: dict[str, Any],
        *,
        purpose: str,
        sent: dict,
        parse_json: bool,
        schema: dict | None = None,
        name: str | None = None,
    ) -> LLMResult:
        if not self.available:
            return LLMResult(ok=False, error="llm_unavailable")
        if self.spent_usd >= self._budget_usd:
            return LLMResult(ok=False, error="llm_budget_exhausted")
        if self.provider == "openai":
            return self._call_openai(
                kwargs, purpose=purpose, sent=sent, parse_json=parse_json, schema=schema, name=name
            )

        model = kwargs["model"]
        sent = {**sent, "rows_sent": 0}
        started = time.perf_counter()
        response = None
        error: str | None = None
        try:
            response = self._sdk.messages.create(**kwargs)
        except anthropic.RateLimitError:
            log.warning("LLM rate limited")
            error = "llm_error:rate_limited"
        except anthropic.APIStatusError as e:
            log.warning("LLM API error %s: %s", e.status_code, e.message)
            error = f"llm_error:{e.status_code}"
            if e.status_code in (401, 403):
                self.auth_failed = True
        except anthropic.APITimeoutError:
            log.warning("LLM timeout")
            error = "llm_error:timeout"
        except anthropic.APIConnectionError:
            log.warning("LLM connection error")
            error = "llm_error:connection"
        except Exception:  # contract: the LLM layer never crashes the app
            log.exception("Unexpected LLM failure")
            error = "llm_error:unexpected"
        latency_ms = int((time.perf_counter() - started) * 1000)

        usage = _usage(response)
        cost = cost_of(model, usage) if response is not None else 0.0
        stop_reason = getattr(response, "stop_reason", None)
        text: str | None = None
        data: Any = None

        if response is not None:
            text = "".join(
                getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text"
            )
            if stop_reason == "refusal":
                error = "llm_refusal"
            elif stop_reason == "max_tokens":
                error = "llm_max_tokens"
            elif parse_json:
                try:
                    data = json.loads(text)
                except (TypeError, ValueError):
                    error = "llm_invalid_json"

        with self._lock:
            self.spent_usd += cost
        call_id = self._record(
            purpose=purpose,
            model=model,
            usage=usage,
            cost=cost,
            latency_ms=latency_ms,
            ok=error is None,
            error=error,
            sent=sent,
        )
        return LLMResult(
            ok=error is None,
            text=text if error is None else None,
            data=data if error is None else None,
            error=error,
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            stop_reason=stop_reason,
            call_id=call_id,
        )

    def _call_openai(
        self,
        kwargs: dict[str, Any],
        *,
        purpose: str,
        sent: dict,
        parse_json: bool,
        schema: dict | None,
        name: str | None,
    ) -> LLMResult:
        """Same contract as the Anthropic path, via Chat Completions + structured outputs."""
        model = self.model_for(kwargs["model"])
        messages: list[dict[str, str]] = []
        if kwargs.get("system"):
            messages.append({"role": "system", "content": kwargs["system"]})
        messages.extend(kwargs["messages"])
        params: dict[str, Any] = {"model": model, "messages": messages}
        max_tokens = int(kwargs.get("max_tokens", 1024))
        if _is_reasoning_model(model):
            params["max_completion_tokens"] = max(max_tokens, 4096)
            # Column mapping is simple: minimal reasoning keeps it fast on stage. Reading a
            # question into SQL keeps "low" for better queries.
            params["reasoning_effort"] = "minimal" if kwargs["model"] == MODEL_FAST else "low"
        else:
            params["max_completion_tokens"] = max_tokens
        if parse_json and schema is not None:
            params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": _schema_name(name or "structured_output"),
                    "schema": schema,
                    "strict": True,
                },
            }

        sent = {**sent, "rows_sent": 0, "provider": "openai"}
        started = time.perf_counter()
        response = None
        error: str | None = None
        try:
            try:
                response = self._sdk.chat.completions.create(**params)
            except openai.BadRequestError as e:
                rf = params.get("response_format")
                if params.get("reasoning_effort") == "minimal" and "reasoning" in str(e).lower():
                    # This model does not accept "minimal": retry once with "low".
                    log.warning("reasoning_effort=minimal rejected (%s); retrying with low", e)
                    params["reasoning_effort"] = "low"
                elif rf is not None and rf["json_schema"].get("strict"):
                    # A schema outside the strict subset: retry once without constrained decoding.
                    log.warning("OpenAI rejected the strict schema (%s); retrying non-strict", e)
                    rf["json_schema"]["strict"] = False
                else:
                    raise
                response = self._sdk.chat.completions.create(**params)
        except openai.RateLimitError:
            log.warning("LLM rate limited")
            error = "llm_error:rate_limited"
        except openai.APIStatusError as e:
            log.warning("LLM API error %s: %s", e.status_code, e.message)
            error = f"llm_error:{e.status_code}"
            if e.status_code in (401, 403):
                self.auth_failed = True
        except openai.APITimeoutError:
            log.warning("LLM timeout")
            error = "llm_error:timeout"
        except openai.APIConnectionError:
            log.warning("LLM connection error")
            error = "llm_error:connection"
        except Exception:  # contract: the LLM layer never crashes the app
            log.exception("Unexpected LLM failure")
            error = "llm_error:unexpected"
        latency_ms = int((time.perf_counter() - started) * 1000)

        usage = _Usage()
        text: str | None = None
        data: Any = None
        stop_reason: str | None = None
        if response is not None:
            u = getattr(response, "usage", None)
            if u is not None:
                prompt_tokens = int(getattr(u, "prompt_tokens", 0) or 0)
                details = getattr(u, "prompt_tokens_details", None)
                cached = int(getattr(details, "cached_tokens", 0) or 0) if details else 0
                usage = _Usage(
                    input_tokens=max(prompt_tokens - cached, 0),
                    output_tokens=int(getattr(u, "completion_tokens", 0) or 0),
                    cache_read=cached,
                )
            choices = getattr(response, "choices", None) or []
            choice = choices[0] if choices else None
            message = getattr(choice, "message", None)
            finish = getattr(choice, "finish_reason", None)
            stop_reason = {"stop": "end_turn", "length": "max_tokens"}.get(finish, finish)
            text = getattr(message, "content", None) or ""
            if getattr(message, "refusal", None) or finish == "content_filter":
                error = "llm_refusal"
            elif finish == "length":
                error = "llm_max_tokens"
            elif parse_json:
                try:
                    data = json.loads(text)
                except (TypeError, ValueError):
                    error = "llm_invalid_json"
        cost = cost_of(model, usage) if response is not None else 0.0

        with self._lock:
            self.spent_usd += cost
        call_id = self._record(
            purpose=purpose,
            model=model,
            usage=usage,
            cost=cost,
            latency_ms=latency_ms,
            ok=error is None,
            error=error,
            sent=sent,
        )
        return LLMResult(
            ok=error is None,
            text=text if error is None else None,
            data=data if error is None else None,
            error=error,
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            stop_reason=stop_reason,
            call_id=call_id,
        )

    def _record(
        self,
        *,
        purpose: str,
        model: str,
        usage: _Usage,
        cost: float,
        latency_ms: int,
        ok: bool,
        error: str | None,
        sent: dict,
    ) -> str:
        call_id = uuid.uuid4().hex
        if self._db is None:
            return call_id
        try:
            cur = self._db().cursor()
            try:
                cur.execute(
                    "INSERT INTO llm_call (id, ts, purpose, model, input_tokens, output_tokens, "
                    "cost_usd, latency_ms, ok, error, sent_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        call_id,
                        dt.datetime.now(dt.UTC).replace(tzinfo=None),
                        purpose,
                        model,
                        usage.input_tokens,
                        usage.output_tokens,
                        cost,
                        latency_ms,
                        ok,
                        error,
                        json.dumps(sent, ensure_ascii=False, default=str),
                    ],
                )
            finally:
                cur.close()
        except Exception:  # logging must never break the caller
            log.exception("Could not persist llm_call")
        return call_id


def _schema_name(name: str) -> str:
    """OpenAI schema names allow [a-zA-Z0-9_-], at most 64 characters."""
    clean = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
    return clean[:64] or "structured_output"


def build_client(settings: Any, db: DbProvider | None = None) -> LLMClient:
    """Pick the provider: ``auto`` prefers the OpenAI key, then the Anthropic key."""
    provider = (settings.llm_provider or "auto").strip().lower()
    if provider == "auto":
        provider = "openai" if settings.openai_api_key else "anthropic"
    if provider == "openai":
        return LLMClient(
            api_key=settings.openai_api_key,
            budget_usd=settings.llm_budget_usd,
            db=db,
            provider="openai",
            models={
                MODEL_FAST: settings.openai_model_fast,
                MODEL_SMART: settings.openai_model_smart,
            },
            base_url=settings.openai_base_url,
        )
    return LLMClient(api_key=settings.anthropic_api_key, budget_usd=settings.llm_budget_usd, db=db)


_client: LLMClient | None = None
_client_lock = threading.Lock()


def get_llm() -> LLMClient:
    """Process-wide client so spend is tracked across requests (restored from ``llm_call``)."""
    global _client
    with _client_lock:
        if _client is None:
            from app.warehouse.db import get_db

            client = build_client(get_settings(), db=get_db)
            client.restore_spend()
            if client.available:
                # Free key check in the background, so a rejected key shows RULES, not AI LIVE.
                threading.Thread(target=client.verify_key, daemon=True).start()
            _client = client
        return _client


def reset_llm() -> None:
    """Forget the process-wide client (tests, settings changes)."""
    global _client
    with _client_lock:
        _client = None
