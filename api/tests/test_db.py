import threading

from app.catalog import DATASETS
from app.warehouse import db as dbmod
from app.warehouse.schema import (
    FACT_TABLES,
    SYSTEM_TABLES,
    init_schema,
    reset_schema,
    table_columns,
)


def test_connect_runs_query(tmp_path):
    con = dbmod.connect(str(tmp_path / "x.duckdb"))
    try:
        assert con.execute("select 42").fetchone()[0] == 42
    finally:
        con.close()


def test_get_db_is_a_singleton_with_schema(db):
    assert dbmod.get_db() is db
    tables = {
        r[0] for r in db.execute("SELECT table_name FROM information_schema.tables").fetchall()
    }
    assert set(FACT_TABLES) | set(SYSTEM_TABLES) <= tables


def test_fact_tables_match_catalog_fields(db):
    for ds in DATASETS.values():
        cols = table_columns(db, ds.table)
        assert cols[:2] == ["source_id", "row_no"], ds.table
        assert cols[2:] == ds.field_keys, ds.table


def test_init_schema_is_idempotent_and_reset_keeps_llm_log(db):
    init_schema(db)
    db.execute("INSERT INTO request (source_id, row_no, request_id) VALUES ('s', 1, 'R1')")
    db.execute("INSERT INTO llm_call (id, cost_usd, ok) VALUES ('c1', 0.01, true)")
    reset_schema(db)
    assert db.execute("SELECT count(*) FROM request").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM llm_call").fetchone()[0] == 1
    reset_schema(db, keep=())
    assert db.execute("SELECT count(*) FROM llm_call").fetchone()[0] == 0


def test_cursors_share_data_across_threads(db):
    db.execute(
        "INSERT INTO staff (source_id, row_no, department, headcount) VALUES ('s', 1, 'A', 5)"
    )
    results = []

    def worker():
        gen = dbmod.get_cursor()
        cur = next(gen)
        results.append(cur.execute("SELECT sum(headcount) FROM staff").fetchone()[0])
        gen.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [5, 5, 5, 5]


def test_path_change_reopens(tmp_path, monkeypatch, db):
    from app.config import get_settings

    first = dbmod.get_db()
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "other.duckdb"))
    get_settings.cache_clear()
    second = dbmod.get_db()
    assert second is not first
    assert dbmod.get_connection is dbmod.get_cursor


def test_insert_rows_bulk_converts_types(db):
    import datetime as dt

    n = dbmod.insert_rows(
        db,
        "waste_collection",
        [("s", 3, dt.datetime(2026, 1, 1, 0, 0), "Elbasan", 12, 5.0, None)],
    )
    assert n == 1
    n = dbmod.insert_rows(
        db,
        "waste_collection",
        [{"source_id": "s", "row_no": 4, "month": dt.date(2026, 2, 1), "tonnes": 1.5}],
        columns=["source_id", "row_no", "month", "tonnes"],
    )
    assert n == 1
    rows = db.execute(
        "SELECT row_no, month, admin_unit, tonnes, trips, households_served "
        "FROM waste_collection ORDER BY row_no"
    ).fetchall()
    assert rows == [
        (3, dt.date(2026, 1, 1), "Elbasan", 12.0, 5, None),
        (4, dt.date(2026, 2, 1), None, 1.5, None, None),
    ]
    assert dbmod.insert_rows(db, "waste_collection", []) == 0
