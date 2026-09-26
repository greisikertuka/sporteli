"""scripts/seed_demo.py: the command-line twin of POST /demo/reset."""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "seed_demo.py"


def load_script():
    spec = importlib.util.spec_from_file_location("seed_demo", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_seed_then_seed_all(settings_env, capsys):
    seed = load_script()
    assert seed.main(["--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and out["coverage"] == {"computable": 6, "total": 13}
    assert [x["dataset"] for x in out["loaded"]] == ["requests", "budget", "population"]
    assert all(x["reconciled"] for x in out["loaded"])

    assert seed.main(["--all"]) == 0
    text = capsys.readouterr().out
    assert "Coverage: 13/13" in text
    assert text.count("[ok]") == 6

    from app.warehouse.db import get_db

    con = get_db()
    assert con.execute("SELECT count(*) FROM source").fetchone()[0] == 6
    assert con.execute("SELECT count(*) FROM mapping_recipe").fetchone()[0] == 0
