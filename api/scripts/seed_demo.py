"""Seed the demo database: the same as ``POST /api/v1/demo/reset``, from the command line.

Drops all data (the LLM call log survives, so the spend budget is kept), clears mapping recipes,
then loads the preload files listed in ``samples/manifest.json`` (requests, budget, population)
through the real ingest pipeline with rules mapping: 6 of 13 indicators become computable.
``--all`` also loads envelopes 1–3 (waste, revenue, staff): 13 of 13.

The target database is ``DUCKDB_PATH`` (default ``api/data/pulse.duckdb``). Stop any server that
holds the file first: DuckDB allows one writer process.

Usage:
    cd api && uv run python scripts/seed_demo.py [--all] [--db PATH] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Reset and seed the Sportel demo database.")
    ap.add_argument("--all", action="store_true", help="also load envelopes 1-3 (13/13)")
    ap.add_argument("--db", default=None, help="DuckDB file (default: DUCKDB_PATH or settings)")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    args = ap.parse_args(argv)

    if args.db:
        os.environ["DUCKDB_PATH"] = args.db
    from app.config import get_settings

    get_settings.cache_clear()
    from app.ingest.pipeline import reset_demo
    from app.warehouse.db import close_db, get_db

    close_db()
    started = time.perf_counter()
    try:
        con = get_db().cursor()
        try:
            result = reset_demo(con, envelopes=args.all)
        finally:
            con.close()
    finally:
        close_db()
    elapsed = time.perf_counter() - started

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        cov = result["coverage"]
        print(f"Sportel demo seeded in {elapsed:.1f} s -> {get_settings().duckdb_file}")
        for r in result["loaded"]:
            mark = "ok" if r["reconciled"] else "CHECK"
            print(f"  [{mark}] {r['dataset']:<10} {r['rows_loaded']:>5} rows  {r['filename']}")
        print(f"Coverage: {cov['computable']}/{cov['total']} indicators computable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
