"""Static SQL guard: one read-only SELECT over the canonical fact tables, nothing else.

The guard parses with sqlglot (DuckDB dialect) and rejects, with a bilingual reason:

- anything that is not exactly one statement;
- anything that is not a SELECT (``WITH ... SELECT`` and UNION/INTERSECT/EXCEPT of SELECTs
  are fine): no INSERT/UPDATE/DELETE/DDL, COPY, ATTACH, PRAGMA, SET, INSTALL, LOAD, EXPORT,
  CALL, DESCRIBE, SHOW, SUMMARIZE, EXPLAIN, USE, ...;
- ``SELECT ... INTO``;
- tables outside the allowlist (the canonical fact tables), qualified names such as
  ``information_schema.tables``, and the system tables (``source``, ``llm_call``, ...);
- table functions in FROM (``read_csv``, ``glob``, ``range``, ``duckdb_tables()``, ...) and
  file-reading or environment functions anywhere (``read_text``, ``getenv``, ...);
- columns whose names look personal (names, phones, addresses, emails, personal numbers).

An allowed query is re-generated from the AST with a row cap (``LIMIT 200``), so comments and
trailing statements never reach DuckDB. The sandbox (``app.sqlguard.sandbox``) is the second
line of defence: even a query that slipped past the guard cannot touch files or settings.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, SqlglotError

from app.catalog import FACT_TABLES, L10n, normalize_text, t

MAX_ROWS = 200
MAX_SQL_CHARS = 5_000

ALLOWED_TABLES: frozenset[str] = frozenset(FACT_TABLES)
"""request, budget_line, waste_collection, revenue, staff, population."""

SYSTEM_TABLES: frozenset[str] = frozenset(
    {"source", "llm_call", "mapping_recipe", "definition_pin", "signal_ack"}
)
_SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "system", "temp"}
_SYSTEM_PREFIXES = ("duckdb_", "pg_", "sqlite_", "pragma_")

# Functions that read files, reach the network, reveal the environment or the catalog.
_DENY_FUNCTION_PREFIXES = (
    "read_",
    "parquet_",
    "sniff_",
    "duckdb_",
    "pragma_",
    "sqlite_",
    "postgres_",
    "mysql_",
    "iceberg_",
    "delta_",
    "http",
    "load_",
    "install_",
)
_DENY_FUNCTIONS = {
    "glob",
    "getenv",
    "current_setting",
    "query",
    "query_table",
    "which_secret",
    "json_execute_serialized_sql",
    "from_substrait",
    "get_substrait",
    "sqlite_scan",
    "parquet_scan",
    "csv_scan",
    "checkpoint",
    "force_checkpoint",
    "enable_profiling",
    "set_variable",
    "getvariable",
}

# Statement classes that are never allowed (reported with a specific reason).
_WRITE_CLASSES = tuple(
    c
    for c in (
        getattr(exp, name, None)
        for name in (
            "Insert",
            "Update",
            "Delete",
            "Merge",
            "Create",
            "Drop",
            "Alter",
            "AlterColumn",
            "TruncateTable",
            "RenameTable",
            "Replace",
        )
    )
    if c is not None
)
_ADMIN_CLASSES = tuple(
    c
    for c in (
        getattr(exp, name, None)
        for name in (
            "Copy",
            "Attach",
            "Detach",
            "Pragma",
            "Set",
            "Install",
            "Use",
            "Command",
            "Describe",
            "Show",
            "Summarize",
            "Transaction",
            "Commit",
            "Rollback",
            "Export",
            "Analyze",
            "Grant",
            "Revoke",
        )
    )
    if c is not None
)
_SET_OPERATION = getattr(exp, "SetOperation", exp.Union)
_WRITE_VERBS = {"insert", "update", "delete", "merge", "create", "drop", "alter", "truncate"}
_ADMIN_VERBS = {
    "copy",
    "attach",
    "detach",
    "pragma",
    "set",
    "reset",
    "install",
    "force",
    "load",
    "export",
    "import",
    "call",
    "vacuum",
    "checkpoint",
    "use",
    "grant",
    "revoke",
    "begin",
    "commit",
    "rollback",
    "abort",
    "explain",
    "describe",
    "show",
    "summarize",
}

# Column-name tokens that indicate personal data (compared on normalised name tokens).
_PERSONAL_PREFIXES = (
    "emr",
    "emer",
    "mbiemr",
    "mbiemer",
    "name",
    "surname",
    "fullname",
    "telefon",
    "phone",
    "mobile",
    "celular",
    "adres",
    "address",
    "email",
    "mail",
    "personal",
    "kerkues",
    "requester",
    "applicant",
    "pergjegjes",
    "datelindj",
    "birth",
    "atesi",
)
_PERSONAL_EXACT = {"tel", "cel", "nid", "nr personal", "numri personal", "id number"}


@dataclass(frozen=True)
class GuardVerdict:
    """Result of ``check_sql``. ``sql`` is the guarded query to run (None when rejected)."""

    allowed: bool
    code: str
    """``ok`` or the rule that rejected the query (see ``REASONS``)."""
    reason: L10n | None
    sql: str | None = None
    tables: list[str] = field(default_factory=list)
    """Allowlisted tables the query reads (sorted)."""
    detail: str | None = None
    """The offending item (table, function or column name), for logs and tests."""

    def api(self) -> dict:
        return {
            "allowed": self.allowed,
            "code": self.code,
            "reason": self.reason,
            "sql": self.sql,
            "tables": self.tables,
        }


REASONS: dict[str, L10n] = {
    "empty": t("Pyetja SQL është bosh.", "The SQL query is empty."),
    "too_long": t("Pyetja SQL është shumë e gjatë.", "The SQL query is too long."),
    "parse_error": t(
        "SQL-ja nuk mund të lexohej (sintaksë e pavlefshme).",
        "The SQL could not be parsed (invalid syntax).",
    ),
    "multiple_statements": t(
        "Lejohet vetëm një pyetje SQL; u gjetën disa deklarata.",
        "Only one SQL statement is allowed; several were found.",
    ),
    "write_statement": t(
        "Sportel vetëm lexon të dhënat: shkrimi, fshirja ose ndryshimi i tabelave nuk lejohet.",
        "Sportel only reads data: writing, deleting or changing tables is not allowed.",
    ),
    "admin_statement": t(
        "Komandat e sistemit (COPY, ATTACH, PRAGMA, SET, INSTALL, LOAD, EXPORT…) nuk lejohen.",
        "System commands (COPY, ATTACH, PRAGMA, SET, INSTALL, LOAD, EXPORT…) are not allowed.",
    ),
    "not_select": t(
        "Lejohen vetëm pyetje SELECT për lexim.", "Only read-only SELECT queries are allowed."
    ),
    "select_into": t(
        "SELECT … INTO krijon një tabelë të re dhe nuk lejohet.",
        "SELECT … INTO creates a new table and is not allowed.",
    ),
    "table_function": t(
        "Funksionet që lexojnë skedarë ose gjenerojnë tabela nuk lejohen në FROM.",
        "Functions that read files or generate tables are not allowed in FROM.",
    ),
    "disallowed_function": t(
        "Ky funksion lexon skedarë, mjedisin ose katalogun e sistemit dhe nuk lejohet.",
        "This function reads files, the environment or the system catalog and is not allowed.",
    ),
    "system_table": t(
        "Tabelat e sistemit (burimet, regjistri i AI-së, recetat) nuk janë të arritshme nga "
        "pyetjet.",
        "System tables (sources, the AI call log, recipes) cannot be queried.",
    ),
    "table_not_allowed": t(
        "Lejohen vetëm tabelat kanonike: request, budget_line, waste_collection, revenue, "
        "staff, population.",
        "Only the canonical tables are allowed: request, budget_line, waste_collection, "
        "revenue, staff, population.",
    ),
    "personal_column": t(
        "Pyetja kërkon një fushë personale (emër, telefon, adresë, email). Kolonat personale "
        "hiqen gjatë ngarkimit dhe nuk jepen kurrë.",
        "The query asks for a personal field (name, phone, address, email). Personal columns "
        "are removed on load and never returned.",
    ),
}


def _reject(code: str, detail: str | None = None) -> GuardVerdict:
    return GuardVerdict(allowed=False, code=code, reason=dict(REASONS[code]), detail=detail)


def _function_name(node: exp.Func) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.name).lower()
    try:
        return node.sql_name().lower()
    except Exception:  # pragma: no cover - defensive
        return type(node).__name__.lower()


def _function_denied(name: str) -> bool:
    return name in _DENY_FUNCTIONS or name.startswith(_DENY_FUNCTION_PREFIXES)


def is_personal_column(name: str) -> bool:
    """True when a column name looks like personal data (name/phone/address/email/ID)."""
    norm = normalize_text(name)
    if not norm:
        return False
    if norm in _PERSONAL_EXACT:
        return True
    return any(tok.startswith(_PERSONAL_PREFIXES) or tok in _PERSONAL_EXACT for tok in norm.split())


def _cte_names(root: exp.Expression) -> set[str]:
    return {str(cte.alias_or_name).lower() for cte in root.find_all(exp.CTE)}


def _is_system_table(name: str, db: str) -> bool:
    return (
        name in SYSTEM_TABLES
        or db in _SYSTEM_SCHEMAS
        or name in _SYSTEM_SCHEMAS
        or name.startswith(_SYSTEM_PREFIXES)
    )


def _literal_limit(root: exp.Expression) -> int | None:
    limit = root.args.get("limit")
    if isinstance(limit, exp.Limit) and isinstance(limit.expression, exp.Literal):
        try:
            return int(limit.expression.this)
        except (TypeError, ValueError):
            return None
    return None


def _cap_rows(root: exp.Expression) -> exp.Expression:
    """Apply ``LIMIT 200`` (keeps a smaller literal limit; wraps set operations).

    A SELECT with DuckDB's ``USING SAMPLE`` is wrapped too, because sqlglot renders the sample
    after LIMIT, which DuckDB rejects; its own LIMIT/OFFSET move to the outer query."""
    if isinstance(root, exp.Select) and not root.args.get("sample"):
        current = _literal_limit(root)
        if current is not None and 0 <= current <= MAX_ROWS:
            return root
        return root.limit(MAX_ROWS, copy=True)
    inner = root.copy()
    limit, offset = None, None
    if isinstance(inner, exp.Select) and inner.args.get("sample"):
        limit, offset = inner.args.get("limit"), inner.args.get("offset")
        inner.set("limit", None)
        inner.set("offset", None)
    wrapped = exp.select("*").from_(exp.Subquery(this=inner, alias=exp.to_identifier("q")))
    if limit is not None or offset is not None:
        wrapped.set("limit", limit)
        wrapped.set("offset", offset)
        return _cap_rows(wrapped)
    return wrapped.limit(MAX_ROWS)


def check_sql(sql: str | None) -> GuardVerdict:
    """Decide whether ``sql`` may run in the sandbox; returns the guarded SQL when allowed."""
    text = (sql or "").strip()
    if not text:
        return _reject("empty")
    if len(text) > MAX_SQL_CHARS:
        return _reject("too_long")

    sqlglot_logger = logging.getLogger("sqlglot")
    previous_level = sqlglot_logger.level
    sqlglot_logger.setLevel(logging.ERROR)  # Command fallbacks are rejected below anyway
    try:
        statements = [s for s in sqlglot.parse(text, read="duckdb") if s is not None]
    except (ParseError, SqlglotError, ValueError) as exc:
        # Statements sqlglot cannot parse (e.g. EXPORT DATABASE) still get a precise reason.
        first = text.split(None, 1)[0].lower().lstrip("(")
        if first in _WRITE_VERBS:
            return _reject("write_statement", first)
        if first in _ADMIN_VERBS:
            return _reject("admin_statement", first)
        return _reject("parse_error", str(exc)[:200])
    finally:
        sqlglot_logger.setLevel(previous_level)

    if not statements:
        return _reject("empty")
    if len(statements) > 1:
        return _reject("multiple_statements", str(len(statements)))
    root = statements[0]

    # Statement kind: a SELECT or a set operation of SELECTs, and nothing else inside.
    for node in root.walk():
        if isinstance(node, _WRITE_CLASSES):
            return _reject("write_statement", type(node).__name__)
        if isinstance(node, _ADMIN_CLASSES):
            return _reject("admin_statement", type(node).__name__)
    if not isinstance(root, exp.Select | _SET_OPERATION):
        return _reject("not_select", type(root).__name__)
    for select in root.find_all(exp.Select):
        if select.args.get("into") is not None:
            return _reject("select_into")

    # Functions anywhere in the tree.
    for fn in root.find_all(exp.Func):
        name = _function_name(fn)
        if _function_denied(name):
            return _reject("disallowed_function", name)

    # Tables: allowlist only (CTE names are local and fine).
    ctes = _cte_names(root)
    used: set[str] = set()
    for table in root.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            return _reject("table_function", type(table.this).__name__.lower())
        name = str(table.name).lower()
        db = str(table.db or "").lower()
        catalog = str(table.catalog or "").lower()
        if _is_system_table(name, db):
            return _reject("system_table", f"{db + '.' if db else ''}{name}")
        if catalog or (db and db != "main"):
            return _reject("table_not_allowed", f"{catalog}.{db}.{name}".strip("."))
        if not db and name in ctes:
            continue
        if name not in ALLOWED_TABLES:
            return _reject("table_not_allowed", name)
        used.add(name)

    # Personal-looking columns (the canonical tables hold none; this names the reason).
    for column in root.find_all(exp.Column):
        if is_personal_column(str(column.name)):
            return _reject("personal_column", str(column.name))

    guarded = _cap_rows(root).sql(dialect="duckdb", pretty=True, comments=False)
    return GuardVerdict(allowed=True, code="ok", reason=None, sql=guarded, tables=sorted(used))


_ID = r"[\w.\"\[\]]+"
_SQL_SHAPES = [
    re.compile(p, re.IGNORECASE | re.DOTALL)
    for p in (
        r"^\(?\s*select\b.*(\bfrom\b|[*(;])",
        r"^with\s+(recursive\s+)?\w+\s*(\([^)]*\))?\s+as\s*(not\s+)?(materialized\s+)?\(",
        rf"^from\s+{_ID}(\s+(select|where|limit|order|group)\b.*)?\s*;?\s*$",
        rf"^delete\s+from\s+{_ID}",
        r"^drop\s+(table|view|schema|database|index|sequence|macro|function|type|secret)\b",
        r"^insert\s+(or\s+\w+\s+)?into\b",
        rf"^update\s+{_ID}\s+set\b",
        r"^create\s+(or\s+replace\s+)?(temp\w*\s+)?"
        r"(table|view|schema|index|sequence|macro|function|type|secret|database)\b",
        r"^alter\s+(table|view|sequence)\b",
        r"^truncate\b",
        r"^copy\s+[\w.\"(]",
        r"^(attach|detach)\b",
        r"^pragma\b",
        r"^(set|reset)\s+(global\s+|session\s+|local\s+)?[\w.]+\s*(=|\bto\b)",
        r"^(install|force\s+install)\s+\w+",
        r"^load\s+[\w'\"]+\s*;?\s*$",
        r"^(export|import)\s+database\b",
        r"^call\s+\w+\s*\(",
        rf"^(describe|summarize)\s+{_ID}\s*;?\s*$",
        r"^show\s+(all\s+)?(tables|databases)\b",
        r"^explain\s+(analyze\s+)?(select|with|from)\b",
        r"^use\s+\w+\s*;?\s*$",
        r"^(vacuum|checkpoint|force\s+checkpoint)\b",
        r"^(begin|commit|rollback|abort)(\s+transaction)?\s*;?\s*$",
        r"^(grant|revoke)\s+\w+",
    )
]


def looks_like_sql(text: str | None) -> bool:
    """True when free text is written as SQL, so it goes through the guard (not the matcher).

    Prose such as "Show me the budget" or "Delete all requests from Gjinar" is not SQL; it is
    handled by the copilot's intent checks instead.
    """
    if not text:
        return False
    stripped = text.strip()
    return any(p.match(stripped) for p in _SQL_SHAPES)
