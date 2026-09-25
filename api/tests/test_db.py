from app.warehouse.db import connect


def test_connect_runs_query(tmp_path):
    con = connect(str(tmp_path / "x.duckdb"))
    try:
        assert con.execute("select 42").fetchone()[0] == 42
    finally:
        con.close()
