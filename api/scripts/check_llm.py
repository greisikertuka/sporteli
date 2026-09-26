"""Check that the configured AI key works, with one tiny structured call (costs < $0.001).

    cd api && uv run python scripts/check_llm.py

Reads the same settings as the API (api/.env). Never prints the key.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    # Log the test call to a throwaway database, not the demo database.
    tmp = tempfile.TemporaryDirectory(prefix="sportel-llm-check-")
    os.environ["DUCKDB_PATH"] = str(Path(tmp.name) / "check.duckdb")

    from app.config import get_settings
    from app.llm.client import MODEL_FAST, MODEL_SMART, build_client
    from app.warehouse.db import close_db, get_db

    s = get_settings()
    client = build_client(s, db=get_db)
    key = s.openai_api_key if client.provider == "openai" else s.anthropic_api_key
    print(f"provider: {client.provider}")
    print(f"key configured: {'yes' if key else 'no'} ({len(key or '')} characters)")
    if client.provider == "openai":
        print(f"base url: {s.openai_base_url or 'https://api.openai.com/v1'}")
    if not client.available:
        print("RESULT: no key -> the app runs in RULES mode")
        return 1

    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    status = 0
    for role in (MODEL_FAST, MODEL_SMART):
        res = client.complete_json(
            'Return {"ok": true}.',
            schema=schema,
            tool_name="health_check",
            model=role,
            max_tokens=200,
            purpose="key_check",
            sent={"headers": 0, "samples_per_column": 0},
        )
        model = client.model_for(role)
        if res.ok:
            print(f"OK   {model}: {res.latency_ms} ms, ${res.cost_usd:.6f}")
        else:
            print(f"FAIL {model}: {res.error}")
            status = 1
            if client.auth_failed:
                print("RESULT: the provider rejected the key (check it is complete and valid)")
                break
    close_db()
    if status == 0:
        print("RESULT: AI LIVE works")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
