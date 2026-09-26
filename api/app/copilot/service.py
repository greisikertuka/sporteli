"""The honest copilot: code decides every label, code computes every number.

Routing order for ``ask()``:

1. an example id with a passport → that passport (no model call);
2. text written as SQL → the guard; allowed SQL runs in the sandbox (exploratory), rejected
   SQL is blocked with the guard's reason;
3. requests to change data or for personal data → blocked (before any model call);
4. the exploratory example → the model when live, otherwise its prepared query (guarded);
5. the deterministic matcher (both languages, diacritic-insensitive) → a passport:
   - its datasets are missing → ``not_answerable`` with a gap card (export, owner, sample);
   - the question adds a filter or breakdown the passport cannot give (or another year) →
     the model (if live) or ``not_answerable`` with that reason;
   - otherwise → ``verified``: the passport's fixed SQL, its template, its source rows;
6. topic words for a dataset that is not loaded → ``not_answerable`` with a gap card;
7. AI live → one structured intent call → passport (verified), guarded SQL (exploratory) or
   a refusal (blocked / not answerable);
8. AI offline → ``not_answerable``: "AI offline — try an example question".

Gaps and blocks never reach the model; neither do questions a passport answers exactly.

Answer text is always a template filled by code. The model never writes a number.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

import duckdb

from app.catalog import OWNERS, L10n, dataset_for_table, get_dataset, normalize_text, t
from app.config import get_settings
from app.copilot import intent as intent_mod
from app.copilot.examples import get_example
from app.copilot.matcher import (
    MATCH_THRESHOLD,
    detect_blocked,
    detect_filters,
    match_passport,
)
from app.indicators.registry import (
    Passport,
    compute,
    dataset_loaded,
    format_number,
    get_passport,
    missing_datasets,
    render_answer,
    row_ranges,
)
from app.llm.client import LLMClient, get_llm
from app.sqlguard import (
    SandboxError,
    SandboxTimeout,
    check_sql,
    looks_like_sql,
    run_sandboxed,
)

log = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 2000

SUGGEST_THRESHOLD = 0.4
"""Below the match threshold but above this, the closest passport is suggested."""


class AskError(Exception):
    """Invalid request (unknown example id, empty question)."""

    def __init__(self, code: str, message: L10n, status: int = 422):
        super().__init__(code)
        self.code = code
        self.message = message
        self.status = status


# --------------------------------------------------------------------------------------------
# Texts (all code-written)
# --------------------------------------------------------------------------------------------

BLOCKED_REASONS: dict[str, L10n] = {
    "personal": t(
        "Pyetja kërkon të dhëna personale (emra, telefona, adresa ose të dhëna për individë). "
        "Kolonat personale hiqen gjatë ngarkimit dhe copilot-i nuk jep të dhëna për persona.",
        "The question asks for personal data (names, phones, addresses or data about "
        "individuals). Personal columns are removed on load and the copilot never returns "
        "data about people.",
    ),
    "write": t(
        "Sportel vetëm lexon të dhënat: kërkesat për të fshirë, shtuar ose ndryshuar të dhëna "
        "nuk ekzekutohen. Të dhënat ndryshojnë vetëm duke ngarkuar një eksport të ri.",
        "Sportel only reads data: requests to delete, add or change data are not executed. "
        "Data changes only by loading a new export.",
    ),
}
BLOCKED_INTERPRETED: dict[str, L10n] = {
    "personal": t("Kërkesë për të dhëna personale", "Request for personal data"),
    "write": t("Kërkesë për të ndryshuar të dhënat", "Request to change data"),
    "sql": t("Pyetje SQL e shkruar drejtpërdrejt", "SQL written directly"),
}
BLOCKED_ANSWER = t(
    "E bllokuar: nuk u ekzekutua asnjë pyetje dhe nuk u dha asnjë numër.",
    "Blocked: no query was run and no number was returned.",
)
FREE_TEXT = t(
    "Pyetje e lirë — nuk përputhet me asnjë tregues", "Free-text question — no indicator matches"
)
OFFLINE = t("AI jashtë linje — provo një pyetje shembull.", "AI offline — try an example question.")
LLM_FAILED = t(
    "AI nuk dha një interpretim të vlefshëm këtë herë — provo një pyetje shembull.",
    "AI did not return a valid interpretation this time — try an example question.",
)
OUT_OF_SCOPE = t(
    "Pyetja nuk lidhet me të dhënat e ngarkuara të bashkisë.",
    "The question is not about the municipality's loaded data.",
)


def _interpreted_passport(p: Passport) -> L10n:
    return {
        "sq": f"Treguesi {p.code} · {p.name['sq']}",
        "en": f"Indicator {p.code} · {p.name['en']}",
    }


def _suggestion(p: Passport | None, also: Passport | None = None) -> L10n:
    if p is None:
        return {"sq": "", "en": ""}
    if also is not None:
        return {
            "sq": f" Pyetja përshtatet me dy tregues: «{p.question['sq']}» "
            f"ose «{also.question['sq']}»",
            "en": f" The question fits two indicators: “{p.question['en']}” "
            f"or “{also.question['en']}”",
        }
    return {
        "sq": f" Treguesi më i afërt: «{p.question['sq']}»",
        "en": f" Closest indicator: “{p.question['en']}”",
    }


def _no_llm() -> dict:
    return intent_mod.no_llm()


def _base(question: str, **fields) -> dict:
    out = {
        "label": "not_answerable",
        "question": question,
        "interpreted_as": dict(FREE_TEXT),
        "answer": dict(OFFLINE),
        "value": None,
        "unit": None,
        "passport_code": None,
        "sql": None,
        "table": None,
        "sources": [],
        "gap": None,
        "blocked_reason": None,
        "llm": _no_llm(),
    }
    out.update(fields)
    return out


# --------------------------------------------------------------------------------------------
# Gap cards
# --------------------------------------------------------------------------------------------


@lru_cache(maxsize=4)
def _manifest_files(path: str, mtime: float) -> tuple[dict, ...]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    files = data.get("files", []) if isinstance(data, dict) else data
    return tuple(f for f in files if isinstance(f, dict))


def sample_for(dataset: str) -> str | None:
    """The server sample file that fills a dataset: its envelope, else the preloaded file."""
    path = get_settings().samples_path / "manifest.json"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    files = [f for f in _manifest_files(str(path), mtime) if f.get("dataset_hint") == dataset]
    for f in files:
        if f.get("envelope") is not None:
            return f.get("name")
    for f in files:
        if f.get("preload"):
            return f.get("name")
    return None


def gap_card(dataset: str) -> dict:
    ds = get_dataset(dataset)
    return {
        "dataset": ds.key,
        "name": dict(ds.name),
        "owner": dict(OWNERS[ds.owner]),
        "sample": sample_for(ds.key),
    }


def _join(items: list[str], locale: str) -> str:
    if len(items) <= 1:
        return "".join(items)
    word = " dhe " if locale == "sq" else " and "
    return ", ".join(items[:-1]) + word + items[-1]


def _gap_answer(
    question: str,
    missing: list[str],
    passport: Passport | None = None,
    *,
    llm: dict | None = None,
    sql: str | None = None,
    interpreted: L10n | None = None,
) -> dict:
    first = get_dataset(missing[0])
    owner = OWNERS[first.owner]
    exports = {
        loc: _join([get_dataset(d).export_name[loc] for d in missing], loc) for loc in ("sq", "en")
    }
    verb_sq = "mungon" if len(missing) == 1 else "mungojnë"
    verb_en = "is" if len(missing) == 1 else "are"
    lead_sq = (
        f"Treguesi {passport.code} nuk llogaritet ende: "
        if passport
        else "Nuk mund të përgjigjem ende: "
    )
    lead_en = (
        f"Indicator {passport.code} cannot be computed yet: "
        if passport
        else "Not answerable yet: "
    )
    answer = {
        "sq": f"{lead_sq}{verb_sq} {exports['sq']}. Përgjegjës: {owner['sq']}. "
        "Asnjë numër nuk u hamendësua.",
        "en": f"{lead_en}the {exports['en']} {verb_en} missing. Owner: {owner['en']}. "
        "No number was guessed.",
    }
    if interpreted is None:
        if passport is not None:
            interpreted = _interpreted_passport(passport)
        else:
            interpreted = {
                "sq": f"Pyetje për {first.name['sq'].lower()}",
                "en": f"Question about {first.name['en'].lower()}",
            }
    return _base(
        question,
        label="not_answerable",
        interpreted_as=interpreted,
        answer=answer,
        unit=passport.unit if passport else None,
        passport_code=passport.code if passport else None,
        sql=sql,
        gap=gap_card(first.key),
        llm=llm or _no_llm(),
    )


# --------------------------------------------------------------------------------------------
# Verified (passport)
# --------------------------------------------------------------------------------------------


def _passport_answer(
    con: duckdb.DuckDBPyConnection, question: str, p: Passport, *, llm: dict | None = None
) -> dict:
    missing = missing_datasets(p, con)
    if missing:
        return _gap_answer(question, missing, p, llm=llm)
    res = compute(p, con)
    sources = [
        {"source_id": s.source_id, "filename": s.filename, "rows": s.row_ranges}
        for s in res.lineage
    ]
    if res.value is None:
        return _base(
            question,
            label="not_answerable",
            interpreted_as=_interpreted_passport(p),
            answer=t(
                f"Të dhënat për {p.code} janë ngarkuar, por asnjë rresht nuk plotëson formulën "
                "për periudhën e fundit; nuk jepet asnjë numër.",
                f"The data for {p.code} are loaded, but no row meets the formula for the latest "
                "period; no number is given.",
            ),
            unit=p.unit,
            passport_code=p.code,
            sql=res.sql,
            sources=sources,
            llm=llm or _no_llm(),
        )
    return _base(
        question,
        label="verified",
        interpreted_as=_interpreted_passport(p),
        answer=render_answer(p, res.value, res.period, res.basis),
        value=res.value,
        unit=p.unit,
        passport_code=p.code,
        sql=res.sql,
        sources=sources,
        llm=llm or _no_llm(),
    )


# --------------------------------------------------------------------------------------------
# Exploratory (guarded SQL in the sandbox)
# --------------------------------------------------------------------------------------------


def _table_sources(con: duckdb.DuckDBPyConnection, tables: list[str]) -> list[dict]:
    out = []
    for table in tables:
        rows = con.execute(
            f"SELECT x.source_id, any_value(s.filename), list(x.row_no) "
            f"FROM {table} x LEFT JOIN source s ON s.id = x.source_id "
            f"GROUP BY x.source_id ORDER BY x.source_id"
        ).fetchall()
        for sid, filename, nums in rows:
            out.append(
                {
                    "source_id": sid or "—",
                    "filename": filename or sid or "—",
                    "rows": row_ranges(n for n in nums if n is not None),
                }
            )
    return out


def _single_number(columns: list[str], rows: list[list]) -> float | None:
    if len(columns) == 1 and len(rows) == 1:
        v = rows[0][0]
        if isinstance(v, int | float) and not isinstance(v, bool):
            return float(v)
    return None


def _fmt_plain(value: float, locale: str) -> str:
    decimals = 0 if float(value).is_integer() else 2
    return format_number(value, decimals, locale)


def _sql_answer(
    con: duckdb.DuckDBPyConnection,
    question: str,
    sql: str,
    *,
    origin: str,
    llm: dict | None = None,
    interpreted: L10n | None = None,
) -> dict:
    """Guard → gap check → sandbox → exploratory table. ``origin``: user | ai | prepared."""
    llm = llm or _no_llm()
    verdict = check_sql(sql)
    if not verdict.allowed:
        return _base(
            question,
            label="blocked",
            interpreted_as=interpreted or dict(BLOCKED_INTERPRETED["sql"]),
            answer=dict(BLOCKED_ANSWER),
            sql=sql.strip(),
            blocked_reason=verdict.reason,
            llm=llm,
        )
    tables = verdict.tables
    if interpreted is None:
        origin_text = {
            "user": t("SQL e shkruar nga përdoruesi", "SQL written by the user"),
            "ai": t("SQL e propozuar nga AI", "SQL proposed by AI"),
            "prepared": t(
                "SQL e përgatitur për shembullin (AI jashtë linje)",
                "Prepared SQL for this example (AI offline)",
            ),
        }[origin]
        on = ", ".join(tables) or "—"
        interpreted = {
            "sq": f"Pyetje eksploruese · {origin_text['sq']} · tabela: {on}",
            "en": f"Exploratory query · {origin_text['en']} · tables: {on}",
        }
    missing = [
        dataset_for_table(tb).key
        for tb in tables
        if not dataset_loaded(con, dataset_for_table(tb).key)
    ]
    if missing:
        return _gap_answer(
            question, missing, None, llm=llm, sql=verdict.sql, interpreted=interpreted
        )
    try:
        result = run_sandboxed(con, verdict.sql, tables)
    except SandboxTimeout:
        return _base(
            question,
            interpreted_as=interpreted,
            answer=t(
                "Pyetja eksploruese zgjati më shumë se kufiri i kohës dhe u ndërpre; nuk jepet "
                "asnjë numër.",
                "The exploratory query ran longer than the time limit and was stopped; no number "
                "is given.",
            ),
            sql=verdict.sql,
            llm=llm,
        )
    except SandboxError as exc:
        log.info("sandbox error: %s", exc)
        return _base(
            question,
            interpreted_as=interpreted,
            answer=t(
                "Pyetja eksploruese nuk u ekzekutua dot (gabim në SQL); nuk jepet asnjë numër.",
                "The exploratory query could not run (SQL error); no number is given.",
            ),
            sql=verdict.sql,
            llm=llm,
        )

    value = _single_number(result.columns, result.rows)
    caveat = t(
        " Nuk është tregues i verifikuar: kontrolloni SQL-në para se ta përdorni.",
        " Not a verified indicator: check the SQL before relying on it.",
    )
    if value is not None:
        answer = {
            loc: (
                ("Rezultati i pyetjes eksploruese: " if loc == "sq" else "Exploratory result: ")
                + _fmt_plain(value, loc)
                + "."
                + caveat[loc]
            )
            for loc in ("sq", "en")
        }
    else:
        n = len(result.rows)
        more = (
            {"sq": " (shfaqen të parët)", "en": " (first rows shown)"}
            if result.truncated
            else {"sq": "", "en": ""}
        )
        rows_sq, rows_en = format_number(n, 0, "sq"), format_number(n, 0, "en")
        answer = {
            "sq": f"Rezultati i pyetjes eksploruese: {rows_sq} rreshta{more['sq']}." + caveat["sq"],
            "en": f"Exploratory result: {rows_en} rows{more['en']}." + caveat["en"],
        }
    return _base(
        question,
        label="exploratory",
        interpreted_as=interpreted,
        answer=answer,
        value=value,
        sql=verdict.sql,
        table={"columns": result.columns, "rows": result.rows},
        sources=_table_sources(con, tables),
        llm=llm,
    )


# --------------------------------------------------------------------------------------------
# Blocked / offline
# --------------------------------------------------------------------------------------------


def _blocked(question: str, kind: str, *, llm: dict | None = None) -> dict:
    return _base(
        question,
        label="blocked",
        interpreted_as=dict(BLOCKED_INTERPRETED[kind]),
        answer=dict(BLOCKED_ANSWER),
        blocked_reason=dict(BLOCKED_REASONS[kind]),
        llm=llm or _no_llm(),
    )


def _offline(
    question: str,
    *,
    related: Passport | None = None,
    reason: str = "offline",
    llm: dict | None = None,
    also: Passport | None = None,
) -> dict:
    """``not_answerable`` without a gap: AI offline/failed, a breakdown, or out of scope."""
    tip = _suggestion(related, also)
    if reason == "breakdown" and related is not None:
        answer = {
            "sq": "Kjo pyetje kërkon një ndarje ose filtër (p.sh. sipas muajit, njësisë ose "
            f"drejtorisë) që treguesi {related.code} nuk e jep. Pa AI nuk ndërtohet pyetje e re "
            "— provo një pyetje shembull ose pyet për treguesin e plotë.",
            "en": "This question asks for a breakdown or filter (e.g. by month, unit or "
            f"directorate) that indicator {related.code} does not provide. Without AI no new "
            "query is built — try an example question or ask for the whole indicator.",
        }
        interpreted = {
            "sq": f"Treguesi {related.code} · {related.name['sq']} + filtër ose ndarje",
            "en": f"Indicator {related.code} · {related.name['en']} + filter or breakdown",
        }
        return _base(
            question,
            interpreted_as=interpreted,
            answer=answer,
            unit=related.unit,
            passport_code=related.code,
            llm=llm or _no_llm(),
        )
    base = {"offline": OFFLINE, "llm_failed": LLM_FAILED, "out_of_scope": OUT_OF_SCOPE}[reason]
    answer = {
        loc: base[loc] + (tip[loc] if reason != "out_of_scope" else "") for loc in ("sq", "en")
    }
    return _base(
        question,
        interpreted_as=dict(FREE_TEXT),
        answer=answer,
        llm=llm or _no_llm(),
    )


# --------------------------------------------------------------------------------------------
# Model route
# --------------------------------------------------------------------------------------------


def _llm_route(
    con: duckdb.DuckDBPyConnection,
    question: str,
    llm: LLMClient,
    *,
    related: Passport | None = None,
    fallback_sql: str | None = None,
) -> dict:
    outcome = intent_mod.interpret(question, llm)
    info = outcome.llm
    it = outcome.intent
    if it is None:
        if fallback_sql:
            return _sql_answer(con, question, fallback_sql, origin="prepared", llm=info)
        reason = "llm_failed" if info.get("used") else "offline"
        return _offline(question, related=related, reason=reason, llm=info)
    if it.kind == "passport" and it.passport_code:
        return _passport_answer(con, question, get_passport(it.passport_code), llm=info)
    if it.kind == "sql" and it.sql:
        return _sql_answer(
            con, question, it.sql, origin="ai", llm=info, interpreted=it.interpreted_as
        )
    if it.refuse_reason == "personal_data":
        return _blocked(question, "personal", llm=info)
    if it.refuse_reason == "write":
        return _blocked(question, "write", llm=info)
    return _offline(question, reason="out_of_scope", llm=info)


# --------------------------------------------------------------------------------------------
# Topic gaps
# --------------------------------------------------------------------------------------------

_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "requests": ("kerkes", "ankes", "request", "complaint", "ticket", "afat", "deadline"),
    "budget": ("buxhet", "shpenzim", "investim", "kapital", "budget", "spending", "capital",
               "invest"),
    "waste": ("mbetje", "mbeturin", "plehra", "grumbullim", "waste", "garbage", "rubbish",
              "trash", "tonne", "tonelat"),
    "revenue": ("taks", "tarif", "arketim", "arketuar", "te ardhura", "pagues", "tax", "fee",
                "revenue"),
    "staff": ("punonjes", "staf", "personel", "burime njerezore", "rotacion", "largime", "staff",
              "employee", "headcount", "turnover", "workforce"),
    "population": ("popullsi", "banore", "population", "resident", "census", "censusi"),
}  # fmt: skip


def topic_datasets(question: str) -> list[str]:
    """Datasets a question is about, from topic words (both languages, no diacritics).

    "pastrim" (cleaning) alone means the waste service; next to "tarif" (fee) it is revenue.
    """
    norm = f" {normalize_text(question)} "
    hits = [ds for ds, words in _TOPIC_KEYWORDS.items() if any(f" {w}" in norm for w in words)]
    if " pastrim" in norm or " clean" in norm:
        target = "revenue" if (" tarif" in norm or " fee" in norm) else "waste"
        if target not in hits:
            hits.append(target)
    return hits


# --------------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------------

_YEAR_RE = re.compile(r"^\d{4}")


def ask(
    con: duckdb.DuckDBPyConnection,
    question: str | None,
    locale: str = "sq",
    example_id: str | None = None,
    *,
    llm: LLMClient | None = None,
) -> dict:
    """Answer a question as an ``AskAnswer`` dict. Raises ``AskError`` for invalid input."""
    q = (question or "").strip()
    locale = locale if locale in ("sq", "en") else "sq"
    example = None
    if example_id:
        example = get_example(example_id)
        if example is None:
            raise AskError(
                "unknown_example",
                t(f"Shembulli «{example_id}» nuk ekziston.", f"Unknown example “{example_id}”."),
                404,
            )
        if not q:
            q = example.question.get(locale) or example.question["sq"]
    if not q:
        raise AskError("empty_question", t("Shkruani një pyetje.", "Please type a question."))
    if len(q) > MAX_QUESTION_CHARS:
        raise AskError(
            "question_too_long",
            t(
                "Pyetja është shumë e gjatë (deri në 2.000 shenja).",
                "The question is too long (up to 2,000 characters).",
            ),
        )
    client = llm or get_llm()

    # 1. Example routed straight to its passport.
    if example is not None and example.passport_code:
        return _passport_answer(con, q, get_passport(example.passport_code))

    # 2. SQL typed directly goes through the guard (works without AI).
    if looks_like_sql(q):
        return _sql_answer(con, q, q, origin="user")

    # 3. Change requests and personal data are blocked before anything else runs.
    blocked = detect_blocked(q)
    if blocked is not None:
        return _blocked(q, blocked.kind)

    # 4. The exploratory example: AI when live, the prepared query otherwise.
    if example is not None and example.prepared_sql:
        if client.mode == "live":
            return _llm_route(con, q, client, fallback_sql=example.prepared_sql)
        return _sql_answer(con, q, example.prepared_sql, origin="prepared")

    # 5. Deterministic matcher.
    match = match_passport(q)
    filters = detect_filters(q)
    if match.best is not None:
        p = get_passport(match.best.code)
        missing = missing_datasets(p, con)
        if missing:
            return _gap_answer(q, missing, p)
        needs_more = filters.any
        if not needs_more and filters.years:
            res_year = _data_year(con, p)
            needs_more = res_year is not None and any(y != res_year for y in filters.years)
        if needs_more:
            if client.mode == "live":
                return _llm_route(con, q, client, related=p)
            return _offline(q, related=p, reason="breakdown")
        return _passport_answer(con, q, p)

    # 6. Topic words for a dataset that is not loaded → gap card.
    for ds in topic_datasets(q):
        if not dataset_loaded(con, ds):
            return _gap_answer(q, [ds])

    related = also = None
    if match.candidates and match.candidates[0].score >= SUGGEST_THRESHOLD:
        related = get_passport(match.candidates[0].code)
        if match.ambiguous:
            also = get_passport(match.candidates[1].code)

    # 7. The model, if live.
    if client.mode == "live":
        return _llm_route(con, q, client, related=related)

    # 8. Offline.
    return _offline(q, related=related, reason="offline", also=also)


def _data_year(con: duckdb.DuckDBPyConnection, p: Passport) -> int | None:
    try:
        period = compute(p, con).period
    except Exception:  # pragma: no cover - defensive
        return None
    if period and _YEAR_RE.match(period):
        return int(period[:4])
    return None


__all__ = ["MATCH_THRESHOLD", "AskError", "ask", "gap_card", "sample_for", "topic_datasets"]
