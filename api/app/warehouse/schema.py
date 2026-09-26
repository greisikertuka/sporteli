"""Canonical DuckDB schema (contract §2).

Every fact row carries ``source_id`` (the ``source.id`` of the load) and ``row_no`` (1-based row
number in the original file/sheet) so any number can be traced back to its source rows.
JSON payloads are stored as VARCHAR (no extension needed).
"""

import duckdb

FACT_DDL: dict[str, str] = {
    "request": """
        CREATE TABLE IF NOT EXISTS request (
            source_id VARCHAR,
            row_no INTEGER,
            request_id VARCHAR,
            created_at DATE,
            closed_at DATE,
            category VARCHAR,
            department VARCHAR,
            admin_unit VARCHAR,
            channel VARCHAR,
            status VARCHAR,
            sla_days INTEGER
        )""",
    "budget_line": """
        CREATE TABLE IF NOT EXISTS budget_line (
            source_id VARCHAR,
            row_no INTEGER,
            month DATE,
            programme_code VARCHAR,
            programme VARCHAR,
            line_type VARCHAR,
            planned_lek DOUBLE,
            actual_lek DOUBLE
        )""",
    "waste_collection": """
        CREATE TABLE IF NOT EXISTS waste_collection (
            source_id VARCHAR,
            row_no INTEGER,
            month DATE,
            admin_unit VARCHAR,
            tonnes DOUBLE,
            trips INTEGER,
            households_served INTEGER
        )""",
    "revenue": """
        CREATE TABLE IF NOT EXISTS revenue (
            source_id VARCHAR,
            row_no INTEGER,
            month DATE,
            revenue_type VARCHAR,
            payer_type VARCHAR,
            planned_lek DOUBLE,
            collected_lek DOUBLE
        )""",
    "staff": """
        CREATE TABLE IF NOT EXISTS staff (
            source_id VARCHAR,
            row_no INTEGER,
            department VARCHAR,
            headcount INTEGER,
            hires INTEGER,
            leavers INTEGER,
            as_of DATE
        )""",
    "population": """
        CREATE TABLE IF NOT EXISTS population (
            source_id VARCHAR,
            row_no INTEGER,
            admin_unit VARCHAR,
            basis VARCHAR,
            residents INTEGER
        )""",
}

SYSTEM_DDL: dict[str, str] = {
    "source": """
        CREATE TABLE IF NOT EXISTS source (
            id VARCHAR PRIMARY KEY,
            filename VARCHAR,
            file_hash VARCHAR,
            dataset VARCHAR,
            sheet VARCHAR,
            header_row INTEGER,
            header_fingerprint VARCHAR,
            synthetic BOOLEAN,
            rows_read INTEGER,
            rows_loaded INTEGER,
            rows_excluded_json VARCHAR,
            reconciliation_json VARCHAR,
            pii_dropped_json VARCHAR,
            unit_multiplier DOUBLE,
            mapping_json VARCHAR,
            recipe_id VARCHAR,
            recipe_reused BOOLEAN,
            llm_json VARCHAR,
            loaded_at TIMESTAMP,
            duration_ms INTEGER,
            receipt_json VARCHAR
        )""",
    "mapping_recipe": """
        CREATE TABLE IF NOT EXISTS mapping_recipe (
            id VARCHAR PRIMARY KEY,
            dataset VARCHAR,
            header_fingerprint VARCHAR,
            mapping_json VARCHAR,
            created_at TIMESTAMP,
            from_filename VARCHAR
        )""",
    "llm_call": """
        CREATE TABLE IF NOT EXISTS llm_call (
            id VARCHAR PRIMARY KEY,
            ts TIMESTAMP,
            purpose VARCHAR,
            model VARCHAR,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cost_usd DOUBLE,
            latency_ms INTEGER,
            ok BOOLEAN,
            error VARCHAR,
            sent_json VARCHAR
        )""",
    "definition_pin": """
        CREATE TABLE IF NOT EXISTS definition_pin (
            key VARCHAR PRIMARY KEY,
            value VARCHAR,
            pinned_at TIMESTAMP,
            reason VARCHAR
        )""",
    "signal_ack": """
        CREATE TABLE IF NOT EXISTS signal_ack (
            indicator_code VARCHAR,
            rule VARCHAR,
            status VARCHAR,
            reason VARCHAR,
            ts TIMESTAMP
        )""",
}

FACT_TABLES: tuple[str, ...] = tuple(FACT_DDL)
SYSTEM_TABLES: tuple[str, ...] = tuple(SYSTEM_DDL)
ALL_TABLES: tuple[str, ...] = FACT_TABLES + SYSTEM_TABLES

KEEP_ON_RESET: tuple[str, ...] = ("llm_call",)
"""Tables that survive ``reset_schema`` by default: the LLM spend log protects the budget."""


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create every table that does not exist yet (idempotent)."""
    for ddl in (*FACT_DDL.values(), *SYSTEM_DDL.values()):
        con.execute(ddl)


def reset_schema(con: duckdb.DuckDBPyConnection, *, keep: tuple[str, ...] = KEEP_ON_RESET) -> None:
    """Drop and recreate all tables except those in ``keep`` (default: the LLM call log)."""
    for table in ALL_TABLES:
        if table not in keep:
            con.execute(f"DROP TABLE IF EXISTS {table}")
    init_schema(con)


def table_columns(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    """Column names of ``table`` in declaration order."""
    rows = con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = ? ORDER BY ordinal_position",
        [table],
    ).fetchall()
    return [r[0] for r in rows]
