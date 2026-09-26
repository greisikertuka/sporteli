"""Run the copilot's 24-question golden set end to end and write ``api/eval_result.json``.

    cd api && uv run python scripts/run_eval.py            # mode follows ANTHROPIC_API_KEY
    cd api && uv run python scripts/run_eval.py --mode rules

Steps:
1. a fresh temporary DuckDB (the app's own database is never touched);
2. the preloaded samples are ingested with the real pipeline (``app.ingest.pipeline``), then
   the "start" questions are asked (gaps, verified, blocked, exploratory);
3. the three envelopes are ingested, then the "full" questions are asked;
4. each answer is compared with the golden set: label (per mode), passport, gap dataset, and
   for verified answers the value within 0.1 % of a number computed independently from the
   raw sample files (``tests/golden/expected.py``, plain Python, not the passports' SQL);
5. ``eval_result.json`` gets ``run_at``, ``commit``, ``mode`` and per-label matched/total
   (plus the per-question details and any AI spend of the run).

The figure is indicative: it is our own frozen set, not a benchmark.
"""

from __future__ import annotations

import argparse
import datetime as dt
import inspect
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=API_DIR, capture_output=True, text=True, timeout=10, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip()


def _load_ingest():
    try:
        from app.ingest.pipeline import ingest_path
    except ImportError as exc:
        raise SystemExit(
            "run_eval: the ingest pipeline is not available yet "
            f"(app.ingest.pipeline.ingest_path could not be imported: {exc}). "
            "The golden set still runs in the test suite with direct loads: "
            "uv run pytest tests/test_copilot_golden.py"
        ) from exc
    return ingest_path


def _ingest(ingest_path, path: Path, dataset: str, con) -> dict:
    params = inspect.signature(ingest_path).parameters
    kwargs = {}
    if "con" in params:
        kwargs["con"] = con
    if "use_llm" in params:
        kwargs["use_llm"] = False  # deterministic, free mapping; the eval measures the copilot
    receipt = ingest_path(path, dataset, **kwargs)
    if not isinstance(receipt, dict):
        receipt = receipt.model_dump() if hasattr(receipt, "model_dump") else dict(receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(API_DIR / "eval_result.json"), help="result file")
    ap.add_argument("--db", default=None, help="DuckDB file for the run (default: temp file)")
    ap.add_argument(
        "--mode",
        choices=("auto", "rules"),
        default="auto",
        help="rules: ignore any ANTHROPIC_API_KEY (default: live when a key is configured)",
    )
    ap.add_argument("--strict", action="store_true", help="exit 1 unless every question matches")
    args = ap.parse_args(argv)

    tmp = tempfile.TemporaryDirectory(prefix="sportel-eval-")
    os.environ["DUCKDB_PATH"] = args.db or str(Path(tmp.name) / "eval.duckdb")
    if args.mode == "rules":
        os.environ["ANTHROPIC_API_KEY"] = ""

    from app.config import get_settings

    get_settings.cache_clear()
    from app.copilot import intent as intent_mod
    from app.copilot.service import ask
    from app.llm.client import get_llm, reset_llm
    from app.warehouse.db import close_db, get_db
    from app.warehouse.schema import reset_schema
    from tests.golden.expected import expected_values, read_samples
    from tests.golden.runner import by_label, load_golden, run_items

    close_db()
    reset_llm()
    intent_mod.clear_cache()
    ingest_path = _load_ingest()

    settings = get_settings()
    samples_dir = settings.samples_path
    manifest = json.loads((samples_dir / "manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"] if isinstance(manifest, dict) else manifest
    preload = [f for f in files if f.get("preload")]
    envelopes = sorted(
        (f for f in files if f.get("envelope") is not None), key=lambda f: f["envelope"]
    )

    golden = load_golden()
    tol = float(golden.get("tolerance_pct", 0.1))
    values = expected_values(read_samples(samples_dir))

    con = get_db()
    reset_schema(con, keep=())
    cur = con.cursor()
    mode = get_llm().mode
    print(f"Sportel eval · mode {mode.upper()} · db {os.environ['DUCKDB_PATH']}")

    loads: list[dict] = []

    def load(entries: list[dict]) -> None:
        for f in entries:
            receipt = _ingest(ingest_path, samples_dir / f["name"], f["dataset_hint"], cur)
            loads.append(
                {
                    "file": f["name"],
                    "dataset": receipt.get("dataset", f["dataset_hint"]),
                    "rows_loaded": receipt.get("rows_loaded"),
                }
            )
            print(f"  ingested {f['name']}: {receipt.get('rows_loaded')} rows")

    def asker(question: str, locale: str) -> dict:
        return ask(cur, question, locale)

    try:
        load(preload)
        results = run_items(
            [i for i in golden["items"] if i["stage"] == "start"], asker, values, mode, tol
        )
        load(envelopes)
        results += run_items(
            [i for i in golden["items"] if i["stage"] == "full"], asker, values, mode, tol
        )
        calls, cost = con.execute(
            "SELECT count(*), coalesce(sum(cost_usd), 0) FROM llm_call"
        ).fetchone()
    finally:
        cur.close()
        close_db()

    summary = by_label(results)
    matched = sum(1 for r in results if r["ok"])
    commit = _git("rev-parse", "--short", "HEAD")
    dirty = bool(_git("status", "--porcelain", "--", "."))
    result = {
        "run_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "commit": commit,
        "dirty": dirty,
        "mode": mode,
        "by_label": summary,
        "total": {"matched": matched, "total": len(results)},
        "golden": {
            "version": golden.get("version"),
            "questions": len(results),
            "sq": sum(1 for r in results if r["locale"] == "sq"),
            "en": sum(1 for r in results if r["locale"] == "en"),
            "tolerance_pct": tol,
        },
        "ingest": loads,
        "llm": {"calls": int(calls), "cost_usd": round(float(cost), 6)},
        "items": results,
    }
    out = Path(args.out)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for r in results:
        mark = "ok " if r["ok"] else "MISS"
        extra = "" if r["ok"] else f"  {'; '.join(r['problems'])}"
        print(f"  {mark} {r['id']} [{r['locale']}] {r['expected']:<15} got {r['got']}{extra}")
    for row in summary:
        print(f"  {row['label']:<15} {row['matched']}/{row['total']}")
    print(f"matched {matched}/{len(results)} → {out}")
    tmp.cleanup()
    return 0 if (matched == len(results) or not args.strict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
