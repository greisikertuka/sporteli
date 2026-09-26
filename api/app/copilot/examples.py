"""Example questions for the /ask screen (contract §6/§7).

Verified and gap examples route straight to their passport (no model call); the label is
still decided at run time from what is loaded, so a gap example turns verified after its
envelope is ingested — the demo's "same question, now proven" moment.

The exploratory example carries a hand-written SQL query. With AI live, the question goes to
the model like any free text; without AI, the prepared query is run instead — through the
same guard and sandbox — and the answer says it is a prepared query, not an AI one.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.catalog import L10n, t
from app.indicators.registry import load_pack


@dataclass(frozen=True)
class Example:
    id: str
    kind: str
    """``verified`` | ``gap`` | ``exploratory`` | ``blocked`` (what the example demonstrates)."""
    question: L10n
    passport_code: str | None = None
    prepared_sql: str | None = None
    """Exploratory only: the query used when AI is offline."""

    def api(self) -> dict:
        return {
            "id": self.id,
            "question": dict(self.question),
            "passport_code": self.passport_code,
            "kind": self.kind,
        }


def _passport_example(example_id: str, code: str, kind: str) -> Example:
    p = load_pack().get(code)
    return Example(example_id, kind, dict(p.question), code)


EXPLORATORY_SQL = """
WITH w AS (
  SELECT (date_trunc('month', max(closed_at)) - INTERVAL 1 MONTH)::DATE AS cut FROM request
), c AS (
  SELECT r.department, r.closed_at >= w.cut AS recent,
         datediff('day', r.created_at, r.closed_at) <= r.sla_days AS on_time
  FROM request r, w
  WHERE r.closed_at IS NOT NULL AND r.sla_days IS NOT NULL
)
SELECT coalesce(department, '—') AS department,
       round(100.0 * count(*) FILTER (WHERE NOT recent AND on_time)
             / nullif(count(*) FILTER (WHERE NOT recent), 0), 1) AS on_time_pct_earlier,
       round(100.0 * count(*) FILTER (WHERE recent AND on_time)
             / nullif(count(*) FILTER (WHERE recent), 0), 1) AS on_time_pct_last_2_months
FROM c
GROUP BY 1
ORDER BY on_time_pct_last_2_months - on_time_pct_earlier, 1
""".strip()


def examples() -> list[Example]:
    return [
        _passport_example("verified-req-02", "REQ-02", "verified"),
        _passport_example("verified-fin-02", "FIN-02", "verified"),
        _passport_example("gap-wst-02", "WST-02", "gap"),
        _passport_example("gap-rev-02", "REV-02", "gap"),
        _passport_example("gap-hr-01", "HR-01", "gap"),
        Example(
            "exploratory-directorates",
            "exploratory",
            t(
                "Si ka ndryshuar zgjidhja brenda afatit sipas drejtorive në dy muajt e fundit?",
                "How has on-time resolution changed by directorate in the last two months?",
            ),
            None,
            EXPLORATORY_SQL,
        ),
        Example(
            "blocked-personal",
            "blocked",
            t(
                "Më jep emrat dhe telefonat e kërkuesve",
                "Give me the names and phone numbers of the requesters",
            ),
        ),
    ]


def get_example(example_id: str) -> Example | None:
    return next((e for e in examples() if e.id == example_id), None)
