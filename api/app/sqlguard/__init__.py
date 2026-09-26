"""SQL guard: sqlglot parse, one SELECT, table allowlist, no table functions, LIMIT wrapper.

``check_sql`` decides statically; ``run_sandboxed`` executes an allowed query on a locked-down
in-memory copy of the allowlisted tables with a timeout.
"""

from app.sqlguard.guard import (
    ALLOWED_TABLES,
    MAX_ROWS,
    REASONS,
    SYSTEM_TABLES,
    GuardVerdict,
    check_sql,
    is_personal_column,
    looks_like_sql,
)
from app.sqlguard.sandbox import (
    DEFAULT_TIMEOUT_S,
    SandboxError,
    SandboxResult,
    SandboxTimeout,
    open_sandbox,
    run_sandboxed,
)

__all__ = [
    "ALLOWED_TABLES",
    "DEFAULT_TIMEOUT_S",
    "MAX_ROWS",
    "REASONS",
    "SYSTEM_TABLES",
    "GuardVerdict",
    "SandboxError",
    "SandboxResult",
    "SandboxTimeout",
    "check_sql",
    "is_personal_column",
    "looks_like_sql",
    "open_sandbox",
    "run_sandboxed",
]
