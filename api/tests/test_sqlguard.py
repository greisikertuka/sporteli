"""SQL guard (static) and sandbox (runtime) — the two walls around model-written SQL."""

import datetime as dt

import duckdb
import pytest

from app.sqlguard import (
    ALLOWED_TABLES,
    MAX_ROWS,
    SandboxError,
    SandboxTimeout,
    check_sql,
    is_personal_column,
    looks_like_sql,
    open_sandbox,
    run_sandboxed,
)
from app.warehouse.db import insert_rows

# --------------------------------------------------------------------------------------------
# Static guard
# --------------------------------------------------------------------------------------------

ALLOWED = [
    "SELECT count(*) FROM request",
    "select department, count(*) as n from request group by 1 order by 2 desc",
    "WITH x AS (SELECT * FROM request) SELECT count(*) FROM x",
    "SELECT r.admin_unit, sum(p.residents) FROM request r JOIN population p "
    "ON r.admin_unit = p.admin_unit GROUP BY 1",
    "SELECT month, sum(tonnes) FROM waste_collection GROUP BY 1",
    "SELECT * FROM budget_line UNION ALL SELECT * FROM budget_line",
    "FROM revenue",
    "SELECT sum(headcount) FROM staff;",
    "SELECT * FROM main.request",
    "SELECT 1 + 1",
    "SELECT strftime(month, '%Y-%m') AS m, sum(actual_lek) FROM budget_line GROUP BY 1",
]

DENIED = [
    ("", "empty"),
    ("   ", "empty"),
    ("SELECT 1; DROP TABLE request", "multiple_statements"),
    ("SELECT 1; SELECT 2", "multiple_statements"),
    ("DROP TABLE request", "write_statement"),
    ("DELETE FROM request", "write_statement"),
    ("UPDATE request SET status = 'x'", "write_statement"),
    ("INSERT INTO request (request_id) VALUES ('x')", "write_statement"),
    ("CREATE TABLE x AS SELECT * FROM request", "write_statement"),
    ("ALTER TABLE request ADD COLUMN x INT", "write_statement"),
    ("COPY request TO 'out.csv'", "admin_statement"),
    ("ATTACH 'other.duckdb' AS other", "admin_statement"),
    ("PRAGMA table_info('request')", "admin_statement"),
    ("SET enable_external_access = true", "admin_statement"),
    ("INSTALL httpfs", "admin_statement"),
    ("LOAD httpfs", "admin_statement"),
    ("EXPORT DATABASE 'dump'", "admin_statement"),
    ("DESCRIBE request", "admin_statement"),
    ("SELECT * INTO copy_of FROM request", "select_into"),
    ("SELECT * FROM read_csv('C:/secrets.csv')", "disallowed_function"),
    ("SELECT * FROM read_csv_auto('x.csv')", "disallowed_function"),
    ("SELECT * FROM glob('*')", "disallowed_function"),
    ("SELECT read_text('pyproject.toml')", "disallowed_function"),
    ("SELECT getenv('ANTHROPIC_API_KEY')", "disallowed_function"),
    ("SELECT current_setting('threads')", "disallowed_function"),
    ("SELECT * FROM duckdb_tables()", "disallowed_function"),
    ("SELECT * FROM query('SELECT 1')", "disallowed_function"),
    ("SELECT * FROM range(10)", "table_function"),
    ("SELECT * FROM 'data.csv'", "table_not_allowed"),
    ("SELECT * FROM source", "system_table"),
    ("SELECT * FROM llm_call", "system_table"),
    ("SELECT * FROM mapping_recipe", "system_table"),
    ("SELECT (SELECT count(*) FROM definition_pin)", "system_table"),
    ("SELECT * FROM information_schema.tables", "system_table"),
    ("SELECT * FROM pg_catalog.pg_class", "system_table"),
    ("SELECT * FROM other_db.main.request", "table_not_allowed"),
    ("SELECT * FROM citizens", "table_not_allowed"),
    ("SELECT emri, telefoni FROM request", "personal_column"),
    ("SELECT phone FROM request", "personal_column"),
    ("SELECT adresa FROM request WHERE status = 'E re'", "personal_column"),
    ("SELEKT * FRM request", "not_select"),
    ("foo bar baz", "parse_error"),
    ("SELECT " + "1 + " * 3000 + "1", "too_long"),
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_guard_allows_read_only_selects_on_canonical_tables(sql):
    v = check_sql(sql)
    assert v.allowed, (sql, v.code, v.detail)
    assert v.code == "ok" and v.reason is None
    assert set(v.tables) <= ALLOWED_TABLES
    assert "LIMIT" in v.sql.upper()


@pytest.mark.parametrize(("sql", "code"), DENIED)
def test_guard_denies_with_a_bilingual_reason(sql, code):
    v = check_sql(sql)
    assert not v.allowed
    assert v.code == code, (sql, v.code, v.detail)
    assert v.sql is None
    assert v.reason["sq"] and v.reason["en"]


def test_guard_reports_tables_without_cte_names():
    v = check_sql(
        "WITH a AS (SELECT * FROM request), b AS (SELECT * FROM staff) SELECT 1 FROM a, b"
    )
    assert v.allowed and v.tables == ["request", "staff"]


def test_guard_caps_rows_but_keeps_a_smaller_limit():
    assert "LIMIT 200" in check_sql("SELECT * FROM request").sql
    assert "LIMIT 200" in check_sql("SELECT * FROM request LIMIT 100000").sql
    assert "LIMIT 5" in check_sql("SELECT * FROM request LIMIT 5").sql
    union = check_sql("SELECT 1 AS x FROM request UNION SELECT 2 FROM request").sql
    assert union.upper().startswith("SELECT") and "LIMIT 200" in union


def test_guard_regenerates_sql_from_the_tree():
    v = check_sql("SELECT count(*) FROM request -- ; DROP TABLE request")
    assert v.allowed and "DROP" not in v.sql.upper()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("SELECT count(*) FROM request", True),
        ("select * from staff", True),
        ("WITH x AS (SELECT 1) SELECT * FROM x", True),
        ("DROP TABLE request;", True),
        ("DELETE FROM request", True),
        ("COPY request TO 'x.csv'", True),
        ("PRAGMA version", True),
        ("SET threads = 1", True),
        ("Show me the budget", False),
        ("Delete all requests from Gjinar", False),
        ("Select the biggest unit", False),
        ("Update me on the budget", False),
        ("Sa kërkesa janë pranuar?", False),
        ("With the census basis, how many staff?", False),
    ],
)
def test_looks_like_sql(text, expected):
    assert looks_like_sql(text) is expected


@pytest.mark.parametrize(
    ("name", "personal"),
    [
        ("emri", True),
        ("Emri i kërkuesit", True),
        ("nr_telefoni", True),
        ("email", True),
        ("adresa", True),
        ("numri_personal", True),
        ("department", False),
        ("admin_unit", False),
        ("programme", False),
        ("request_id", False),
        ("planned_lek", False),
    ],
)
def test_personal_column_names(name, personal):
    assert is_personal_column(name) is personal


# --------------------------------------------------------------------------------------------
# Sandbox
# --------------------------------------------------------------------------------------------


@pytest.fixture
def warehouse(db):
    rows = [
        ("s1", i, f"KQ-{i:05d}", dt.date(2026, 1, 1 + i % 28), None, "A", "D", "Elbasan",
         "Online", "E re", 10)
        for i in range(1, 301)
    ]  # fmt: skip
    insert_rows(db, "request", rows)
    db.execute("INSERT INTO source (id, filename, synthetic) VALUES ('s1', 'secret.xlsx', true)")
    db.execute(
        "INSERT INTO llm_call (id, ts, purpose, model, ok, sent_json) "
        "VALUES ('c1', now(), 'x', 'm', true, '{}')"
    )
    return db


def test_sandbox_runs_a_guarded_query_on_a_copy(warehouse):
    v = check_sql("SELECT count(*) AS n, min(created_at) AS first FROM request")
    res = run_sandboxed(warehouse, v.sql, v.tables)
    assert res.columns == ["n", "first"]
    assert res.rows == [[300, "2026-01-01"]]  # dates come back as ISO strings
    assert not res.truncated


def test_sandbox_cells_are_json_friendly(warehouse):
    res = run_sandboxed(
        warehouse,
        "SELECT true AS flag, 1.5::DECIMAL(4, 2) AS d, NULL AS n, 'x' AS s, 2 AS i",
        ["request"],
    )
    assert res.rows == [["true", 1.5, None, "x", 2]]


def test_sandbox_caps_rows(warehouse):
    res = run_sandboxed(warehouse, "SELECT * FROM request", ["request"])
    assert len(res.rows) == MAX_ROWS and res.truncated


def test_sandbox_cannot_read_or_write_files(warehouse, tmp_path):
    target = tmp_path / "leak.csv"
    secret = tmp_path / "secret.csv"
    secret.write_text("a,b\n1,2\n", encoding="utf-8")
    attempts = [
        f"COPY request TO '{target.as_posix()}'",
        f"SELECT * FROM read_csv('{secret.as_posix()}')",
        f"SELECT * FROM read_text('{secret.as_posix()}')",
        f"SELECT * FROM '{secret.as_posix()}'",
        f"ATTACH '{(tmp_path / 'x.duckdb').as_posix()}' AS x",
        "INSTALL httpfs",
        "SELECT * FROM glob('*')",
    ]
    for sql in attempts:
        with pytest.raises(SandboxError):
            run_sandboxed(warehouse, sql, ["request"])
    assert not target.exists()
    assert not (tmp_path / "x.duckdb").exists()


def test_sandbox_configuration_is_locked(warehouse):
    for sql in ("SET enable_external_access = true", "SET lock_configuration = false"):
        with pytest.raises(SandboxError):
            run_sandboxed(warehouse, sql, ["request"])


def test_sandbox_holds_only_the_requested_allowlisted_tables(warehouse):
    for sql in ("SELECT * FROM source", "SELECT * FROM llm_call", "SELECT * FROM staff"):
        with pytest.raises(SandboxError):
            run_sandboxed(warehouse, sql, ["request"])
    with pytest.raises(SandboxError):
        open_sandbox(warehouse, ["source"])


def test_sandbox_cannot_see_python_variables(warehouse):
    secret_frame = warehouse.execute("SELECT * FROM source").to_arrow_table()  # noqa: F841
    with pytest.raises(SandboxError):
        run_sandboxed(warehouse, "SELECT * FROM secret_frame", ["request"])


def test_sandbox_changes_never_reach_the_warehouse(warehouse):
    run_sandboxed(warehouse, "DELETE FROM request", ["request"])
    run_sandboxed(warehouse, "CREATE TABLE extra AS SELECT 1", ["request"])
    assert warehouse.execute("SELECT count(*) FROM request").fetchone()[0] == 300
    tables = {r[0] for r in warehouse.execute("SHOW TABLES").fetchall()}
    assert "extra" not in tables


def test_sandbox_timeout_interrupts_long_queries(warehouse):
    slow = (
        "SELECT sum(a.row_no * b.row_no + c.row_no) FROM request a, request b, request c, request d"
    )
    with pytest.raises(SandboxTimeout):
        run_sandboxed(warehouse, slow, ["request"], timeout_s=0.3)


def test_sandbox_error_is_reported_not_raised_raw(warehouse):
    with pytest.raises(SandboxError) as info:
        run_sandboxed(warehouse, "SELECT no_such_column FROM request", ["request"])
    assert not isinstance(info.value, SandboxTimeout)
    assert isinstance(info.value.__cause__, duckdb.Error)
