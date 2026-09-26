"""Copilot: deterministic routing, labels decided in code, gap cards, blocking, the AI path.

Data is inserted directly (no ingest pipeline). The AI path uses a fake SDK, so no network.
"""

import datetime as dt
import json
from types import SimpleNamespace

import pytest

from app.copilot import intent as intent_mod
from app.copilot.examples import EXPLORATORY_SQL, examples
from app.copilot.matcher import detect_blocked, detect_filters, match_passport, terms
from app.copilot.service import AskError, ask, topic_datasets
from app.llm.client import MODEL_SMART, LLMClient
from app.sqlguard import check_sql
from app.warehouse.db import insert_rows

D = dt.date

ANSWER_KEYS = {
    "label",
    "question",
    "interpreted_as",
    "answer",
    "value",
    "unit",
    "passport_code",
    "sql",
    "table",
    "sources",
    "gap",
    "blocked_reason",
    "llm",
    "method",
}


@pytest.fixture(autouse=True)
def _fresh_intent_cache():
    intent_mod.clear_cache()
    yield
    intent_mod.clear_cache()


def _source(con, sid, filename, dataset):
    con.execute(
        "INSERT INTO source (id, filename, file_hash, dataset, synthetic) "
        "VALUES (?, ?, ?, ?, true)",
        [sid, filename, "hash-" + sid, dataset],
    )


def load_start(con):
    """requests + budget + population, like the demo start state."""
    insert_rows(
        con,
        "request",
        [
            ("s-req", 4, "R1", D(2026, 1, 10), D(2026, 1, 15), "A", "PW", "Elbasan", "Online",
             "E mbyllur", 10),
            ("s-req", 5, "R2", D(2026, 1, 20), D(2026, 2, 10), "A", "PW", "Gjinar", "Online",
             "E mbyllur", 10),
            ("s-req", 6, "R3", D(2026, 2, 5), None, "A", "PW", "Gjinar", "Telefon",
             "Në proces", 10),
            ("s-req", 7, "R4", D(2026, 3, 1), D(2026, 3, 4), "B", "SS", "Elbasan", "Sportel",
             "E mbyllur", 5),
        ],
    )  # fmt: skip
    insert_rows(
        con,
        "budget_line",
        [
            ("s-bud", 4, D(2026, 1, 1), "05100", "Mbetjet", "current", 100_000.0, 90_000.0),
            ("s-bud", 5, D(2026, 1, 1), "05100", "Mbetjet", "capital", 50_000.0, 10_000.0),
        ],
    )
    insert_rows(
        con,
        "population",
        [("s-pop", 3, "Elbasan", "census_2023", 900), ("s-pop", 4, "Gjinar", "census_2023", 100)],
    )
    _source(con, "s-req", "kerkesat.xlsx", "requests")
    _source(con, "s-bud", "buxheti.xlsx", "budget")
    _source(con, "s-pop", "popullsia.csv", "population")


def load_waste(con):
    insert_rows(
        con,
        "waste_collection",
        [
            ("s-wst", 3, D(2026, 1, 1), "Elbasan", 1234.5, 10, 1000),
            ("s-wst", 4, D(2026, 1, 1), "Gjinar", 1000.0, 2, 50),
        ],
    )
    _source(con, "s-wst", "mbetjet.csv", "waste")


@pytest.fixture
def start(db):
    load_start(db)
    return db


# --------------------------------------------------------------------------------------------
# Matcher
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("question", "code"),
    [
        ("Sa përqind e kërkesave zgjidhen brenda afatit?", "REQ-02"),
        ("Sa perqind e kerkesave zgjidhen brenda afatit?", "REQ-02"),  # no diacritics
        ("SA PËRQIND E KËRKESAVE ZGJIDHEN NË KOHË?", "REQ-02"),
        ("What percentage of citizen requests were resolved on time?", "REQ-02"),
        ("How many open requests are overdue?", "REQ-03"),
        ("Sa kerkesa te pazgjidhura kane kaluar afatin?", "REQ-03"),
        ("Sa jane zbatuar investimet kapitale?", "FIN-02"),
        ("How much of the capital budget has been spent?", "FIN-02"),
        ("What is the budget execution rate so far?", "FIN-01"),
        ("Sa ton mbeturina jane mbledhur kete vit?", "WST-01"),
        ("How much waste per capita is collected per year?", "WST-02"),
        ("Sa kushton një ton mbetje?", "WST-03"),
        ("Does the cleaning fee cover the cost of waste management?", "REV-02"),
        ("Sa është arkëtuar nga taksat dhe tarifat vendore?", "REV-01"),
        ("How many employees per 1,000 residents does the municipality have?", "HR-01"),
        ("Sa punonjes per 1000 banore?", "HR-01"),
        ("Sa është shkalla e largimeve të punonjësve?", "HR-02"),
    ],
)
def test_matcher_routes_both_languages(question, code):
    res = match_passport(question)
    assert res.best is not None and res.best.code == code, res.candidates[:3]


@pytest.mark.parametrize(
    "question",
    [
        "Si do jetë moti nesër?",
        "What is the weather tomorrow?",
        "Tell me a joke",
        "Sa kërkesa për ndriçimin publik janë pranuar?",  # detail no passport describes
        "How many requests about street lighting were received?",
    ],
)
def test_matcher_does_not_over_answer(question):
    assert match_passport(question).best is None


@pytest.mark.parametrize(
    "question", ["Sa punonjës ka bashkia?", "How many staff does the municipality have?"]
)
def test_matcher_does_not_guess_between_tied_passports(question):
    # "how many staff" fits staff per 1,000 residents and staff turnover equally well:
    # answering either would answer a different question.
    res = match_passport(question)
    assert res.best is None and res.ambiguous
    assert {m.code for m in res.candidates[:2]} == {"HR-01", "HR-02"}


def test_ambiguous_question_offline_names_both_indicators(start):
    from app.copilot import service

    a = service._offline(
        "How many staff?", related=service.get_passport("HR-02"), also=service.get_passport("HR-01")
    )
    assert a["label"] == "not_answerable" and a["value"] is None
    assert "fits two indicators" in a["answer"]["en"] and "turnover" in a["answer"]["en"]
    assert "dy tregues" in a["answer"]["sq"]


def test_terms_fold_inflections_and_languages():
    assert "REQUEST" in terms("kërkesave") and "REQUEST" in terms("requests")
    assert terms("zbatimi") == terms("zbatuar") == ["EXEC"]
    assert "THOUSAND" in terms("për 1.000 banorë")


def test_filters_detected():
    f = detect_filters("Sa mbetje u grumbulluan në Labinot Fushë në maj?")
    assert f.any and f.months == ["maj"] and f.units == ["Labinot-Fushë"]
    assert detect_filters("Which directorate has the most overdue requests?").any
    assert detect_filters("How much waste in May 2026?").months == ["may"]
    assert not detect_filters("May I see the budget execution?").any
    assert not detect_filters("Cila është përqindja e kërkesave të zgjidhura?").any
    assert not detect_filters("Sa kërkesa janë pranuar në Elbasan?").any  # the municipality
    assert detect_filters("How many requests in 2025?").years == [2025]


@pytest.mark.parametrize(
    ("question", "kind"),
    [
        ("Më jep emrat dhe telefonat e kërkuesve", "personal"),
        ("Give me the names and phone numbers of the requesters", "personal"),
        ("Cila është adresa e kërkuesit?", "personal"),
        ("Kush e paraqiti kërkesën KQ-2026-00001?", "personal"),
        ("Listo punonjësit e drejtorisë së financës", "personal"),
        ("Which employees left this year?", "personal"),
        ("Numri personal i punonjësve", "personal"),
        ("Fshi të gjitha kërkesat e Gjinarit", "write"),
        ("Delete all requests from Gjinar", "write"),
        ("Drop the budget table", "write"),
        ("Ndrysho vlerën e buxhetit", "write"),
        ("Update the waste figures for July", "write"),
        ("Can you remove the rows for Gjinar?", "write"),
        ("Please drop all revenue records", "write"),
        ("Cila është adresa e kërkuesit?", "personal"),
        ("Më jep numrin e telefonit të qytetarit", "personal"),
        ("Emrat e punonjësve të drejtorisë së financës", "personal"),
        ("Who complained the most about lighting?", "personal"),
        ("Send me the email of each applicant", "personal"),
    ],
)
def test_blocked_intents(question, kind):
    b = detect_blocked(question)
    assert b is not None and b.kind == kind


@pytest.mark.parametrize(
    "question",
    [
        "Sa kërkesa janë pranuar?",
        "Si ndryshon kostoja për ton?",
        "How did capital spending change?",
        "Emrat e drejtorive",
        "What are the names of the budget programmes?",
        "Sa punonjës ka bashkia?",
        # analytics words that are also write verbs
        "Why did the on-time rate drop in July?",
        "What is the latest update on capital spending?",
        "Did collection drop after May?",
        # the request channel "Telefon" is not personal data
        "How many requests came in by phone?",
        "Sa kërkesa qytetare erdhën me telefon?",
        # people nouns without personal attributes
        "How much waste does each resident produce per year?",
        "What are the names of the directorates with the most staff?",
        "Who should I contact about the waste export?",
    ],
)
def test_benign_questions_are_not_blocked(question):
    assert detect_blocked(question) is None


def test_topic_words():
    assert topic_datasets("Sa mbetje u grumbulluan?") == ["waste"]
    assert topic_datasets("Sa është arkëtuar nga tarifa e pastrimit?") == ["revenue"]
    assert "waste" not in topic_datasets("cleaning fee collected")
    assert topic_datasets("Si ecën pastrimi i rrugëve?") == ["waste"]
    assert topic_datasets("Sa staf kemi?") == ["staff"]
    assert topic_datasets("Si do jetë moti?") == []


# --------------------------------------------------------------------------------------------
# Labels (rules mode: no API key in tests)
# --------------------------------------------------------------------------------------------


def test_verified_answer_is_code_formatted_with_sources(start):
    a = ask(start, "Sa përqind e kërkesave zgjidhen brenda afatit?", "sq")
    assert set(a) == ANSWER_KEYS
    assert a["label"] == "verified" and a["passport_code"] == "REQ-02"
    # closed with deadline: R1 on time, R2 late, R4 on time → 2/3
    assert a["value"] == pytest.approx(66.666667, abs=1e-5)
    assert "66,7%" in a["answer"]["sq"] and "mars 2026" in a["answer"]["sq"]
    assert "66.7%" in a["answer"]["en"] and "March 2026" in a["answer"]["en"]
    assert "90%" in a["answer"]["sq"]  # target, formatted by code
    assert a["unit"] == "percent" and a["sql"].lstrip().upper().startswith("WITH")
    assert a["sources"] == [{"source_id": "s-req", "filename": "kerkesat.xlsx", "rows": "4–5, 7"}]
    assert a["interpreted_as"]["sq"].startswith("Treguesi REQ-02")
    assert a["llm"] == {
        "used": False,
        "model": None,
        "latency_ms": None,
        "cost_usd": None,
        "cached": False,
    }
    assert a["gap"] is None and a["blocked_reason"] is None and a["table"] is None
    # plain-language method (the passport formula) replaces the SQL on the Ask screen
    assert a["method"]["sq"].startswith("Kërkesat e mbyllura brenda afatit")
    assert a["method"]["en"].startswith("Requests closed within their deadline")


def test_verified_answers_carry_a_plain_language_method(start):
    load_waste(start)
    from app.indicators.registry import get_passport

    for question, code in [
        ("Sa jane zbatuar investimet kapitale?", "FIN-02"),
        ("How much waste per capita is collected per year?", "WST-02"),
        ("Sa ton mbeturina jane mbledhur kete vit?", "WST-01"),
    ]:
        a = ask(start, question, "en")
        assert a["label"] == "verified" and a["passport_code"] == code
        assert a["method"] == get_passport(code).formula
        assert a["method"]["sq"].strip() and a["method"]["en"].strip()
        assert "SELECT" not in a["method"]["en"].upper()
    # no passport computed → no method
    assert ask(start, "Më jep emrat dhe telefonat e kërkuesve", "sq")["method"] is None
    assert ask(start, "Si do jetë moti nesër?", "sq")["method"] is None
    typed = ask(start, "SELECT admin_unit, count(*) AS n FROM request GROUP BY 1", "en")
    assert typed["label"] == "exploratory" and typed["method"] is None


def test_ask_texts_never_mention_sql_or_tables(start):
    """The Ask screen is for non-technical staff: its code-written texts are plain words."""
    answers = [
        ask(start, "", "en", "exploratory-directorates"),
        ask(start, "SELECT admin_unit, count(*) AS n FROM request GROUP BY 1", "en"),
        ask(start, "SELECT * FROM llm_call", "en"),
        ask(start, "Më jep emrat dhe telefonat e kërkuesve", "sq"),
        ask(start, "Sa kërkesa u pranuan në Gjinar?", "sq"),
        ask(start, "Sa jane zbatuar investimet kapitale?", "sq"),
    ]
    for a in answers:
        for field in ("interpreted_as", "answer", "method"):
            for text in (a[field] or {}).values():
                assert "SQL" not in text and "tables:" not in text and "tabela:" not in text, text
                assert "query" not in text.lower(), text
    blocked = answers[2]
    assert blocked["label"] == "blocked"
    assert blocked["interpreted_as"]["en"] == "A database command typed directly"
    assert blocked["answer"]["en"] == (
        "Blocked: nothing was looked up in the data and no number was given."
    )


def test_albanian_thousands_in_verified_answers(start):
    load_waste(start)
    a = ask(start, "Sa ton mbetje janë grumbulluar këtë vit?", "sq")
    assert a["label"] == "verified" and a["value"] == pytest.approx(2234.5)
    assert "2.235 ton" in a["answer"]["sq"]  # half-up, thousands dot
    assert "2,235 tonnes" in a["answer"]["en"]


def test_gap_names_missing_export_owner_and_sample(start):
    a = ask(start, "How much waste per resident per year?", "en")
    assert a["label"] == "not_answerable" and a["passport_code"] == "WST-02"
    assert a["value"] is None and a["sql"] is None
    assert a["gap"] == {
        "dataset": "waste",
        "name": {"sq": "Pastrimi dhe mbetjet", "en": "Cleaning and waste collection"},
        "owner": {"sq": "Drejtoria e Shërbimeve Publike", "en": "Public Services Directorate"},
        "sample": "zarfi-1_SINTETIKE_pastrimi_mbetjet_2026.csv",
    }
    assert "Drejtoria e Shërbimeve Publike" in a["answer"]["sq"]
    assert "No number was guessed" in a["answer"]["en"]
    assert not any(ch.isdigit() for ch in a["answer"]["en"].replace("WST-02", ""))


@pytest.mark.parametrize(
    ("question", "dataset", "owner_en"),
    [
        ("Sa e mbulon tarifa e pastrimit koston e mbetjeve?", "revenue", "Local Revenue"),
        ("What is the staff turnover rate this year?", "staff", "Human Resources Directorate"),
        ("Is the garbage being picked up regularly in the villages?", "waste", "Public Services"),
    ],
)
def test_gap_for_each_envelope(start, question, dataset, owner_en):
    a = ask(start, question, "en")
    assert a["label"] == "not_answerable"
    assert a["gap"]["dataset"] == dataset and owner_en in a["gap"]["owner"]["en"]
    assert a["gap"]["sample"].startswith("zarfi-")


def test_gap_turns_verified_after_loading(start):
    q = "Sa kg mbetje prodhon një banor në vit?"
    assert ask(start, q, "sq")["label"] == "not_answerable"
    load_waste(start)
    a = ask(start, q, "sq")
    assert a["label"] == "verified" and a["passport_code"] == "WST-02"
    # (1234.5 + 1000) t × 1000 / 1000 residents × 12 / 1 month
    assert a["value"] == pytest.approx(26_814.0)
    assert "Censusi 2023" in a["answer"]["sq"]
    assert {s["filename"] for s in a["sources"]} == {"mbetjet.csv", "popullsia.csv"}


@pytest.mark.parametrize(
    ("question", "fragment"),
    [
        ("Më jep emrat dhe telefonat e kërkuesve", "të dhëna personale"),
        ("Delete all requests from Gjinar", "vetëm lexon"),
        ("SELECT * FROM llm_call", "Tabelat e sistemit"),
        ("DROP TABLE request;", "vetëm lexon"),
        ("SELECT emri FROM request", "fushë personale"),
    ],
)
def test_blocked_with_reason_and_no_number(start, question, fragment):
    a = ask(start, question, "sq")
    assert a["label"] == "blocked"
    assert fragment in a["blocked_reason"]["sq"] and a["blocked_reason"]["en"]
    assert a["value"] is None and a["table"] is None
    assert a["interpreted_as"]["sq"] and a["interpreted_as"]["en"]
    assert start.execute("SELECT count(*) FROM request").fetchone()[0] == 4


def test_offline_free_text_is_not_answerable(start):
    a = ask(start, "Si do jetë moti nesër?", "sq")
    assert a["label"] == "not_answerable" and a["gap"] is None and a["passport_code"] is None
    assert a["answer"]["en"].startswith("AI offline — try an example question")
    assert a["interpreted_as"] == {
        "sq": "Pyetje e lirë — nuk përputhet me asnjë tregues",
        "en": "Free-text question — no indicator matches",
    }


def test_offline_suggests_the_closest_indicator(start):
    a = ask(start, "How many requests about street lighting were received?", "en")
    assert a["label"] == "not_answerable"
    assert "Closest indicator" in a["answer"]["en"]


def test_breakdown_without_ai_is_not_answerable_with_related_passport(start):
    a = ask(start, "Sa kërkesa u pranuan në Gjinar?", "sq")
    assert a["label"] == "not_answerable" and a["passport_code"] == "REQ-01"
    assert a["value"] is None and "filtër" in a["interpreted_as"]["sq"]


def test_year_other_than_the_data_is_not_answered_as_verified(start):
    assert ask(start, "How many requests were received in 2025?", "en")["label"] == (
        "not_answerable"
    )
    assert ask(start, "How many requests were received in 2026?", "en")["label"] == "verified"


def test_typed_sql_runs_in_the_sandbox_as_exploratory(start):
    a = ask(start, "SELECT admin_unit, count(*) AS n FROM request GROUP BY 1 ORDER BY 1", "en")
    assert a["label"] == "exploratory"
    assert a["table"] == {"columns": ["admin_unit", "n"], "rows": [["Elbasan", 2], ["Gjinar", 2]]}
    assert "LIMIT 200" in a["sql"]
    assert a["sources"] == [{"source_id": "s-req", "filename": "kerkesat.xlsx", "rows": "4–7"}]
    assert "Not a verified indicator" in a["answer"]["en"]
    assert a["llm"]["used"] is False


def test_exploratory_single_number_is_formatted_by_code(start):
    a = ask(start, "SELECT sum(planned_lek) FROM budget_line", "sq")
    assert a["label"] == "exploratory" and a["value"] == 150_000.0
    assert "150.000" in a["answer"]["sq"] and "150,000" in a["answer"]["en"]


def test_typed_sql_on_an_empty_table_is_a_gap(start):
    a = ask(start, "SELECT sum(tonnes) FROM waste_collection", "en")
    assert a["label"] == "not_answerable" and a["gap"]["dataset"] == "waste"


# --------------------------------------------------------------------------------------------
# Examples
# --------------------------------------------------------------------------------------------


def test_examples_cover_every_kind():
    ex = [e.api() for e in examples()]
    kinds = [e["kind"] for e in ex]
    assert kinds.count("verified") == 2 and kinds.count("gap") == 3
    assert kinds.count("exploratory") == 1 and kinds.count("blocked") == 1
    assert {e["passport_code"] for e in ex if e["kind"] == "gap"} == {"WST-02", "REV-02", "HR-01"}
    for e in ex:
        assert e["question"]["sq"] and e["question"]["en"]
    assert check_sql(EXPLORATORY_SQL).allowed


def test_example_ids_route_without_the_matcher(start):
    assert ask(start, "", "en", "verified-fin-02")["label"] == "verified"
    gap = ask(start, "", "sq", "gap-hr-01")
    assert gap["label"] == "not_answerable" and gap["gap"]["dataset"] == "staff"
    assert gap["question"] == "Sa punonjës ka bashkia për 1.000 banorë?"
    assert ask(start, "", "sq", "blocked-personal")["label"] == "blocked"


def test_exploratory_example_uses_the_prepared_query_without_ai(start):
    a = ask(start, "", "en", "exploratory-directorates")
    assert a["label"] == "exploratory"
    assert a["table"]["columns"] == [
        "department",
        "on_time_pct_earlier",
        "on_time_pct_last_2_months",
    ]
    assert a["interpreted_as"] == {
        "sq": "Vështrim i shpejtë në të dhënat · shembull i përgatitur · nga: Kërkesat qytetare",
        "en": "Quick look at the data · prepared example · from: Citizen requests",
    }
    assert a["method"] is None


def test_unknown_example_and_empty_question(start):
    with pytest.raises(AskError) as info:
        ask(start, "", "sq", "nope")
    assert info.value.status == 404
    with pytest.raises(AskError) as info:
        ask(start, "   ", "sq")
    assert info.value.code == "empty_question"


# --------------------------------------------------------------------------------------------
# AI path (fake SDK)
# --------------------------------------------------------------------------------------------


class FakeMessages:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outputs.pop(0) if self.outputs else {}
        if isinstance(out, Exception):
            raise out
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(out))],
            stop_reason="end_turn",
            usage=SimpleNamespace(
                input_tokens=2000,
                output_tokens=100,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
        )


def live(db, *outputs):
    messages = FakeMessages(outputs)
    client = LLMClient(
        api_key="k", budget_usd=5.0, sdk=SimpleNamespace(messages=messages), db=lambda: db
    )
    return client, messages


def intent(kind, *, code="none", sql="", reason="none", sq="Lexim", en="Reading"):
    return {
        "kind": kind,
        "passport_code": code,
        "sql": sql,
        "refuse_reason": reason,
        "interpreted_as": {"sq": sq, "en": en},
    }


SQL_BY_UNIT = "SELECT admin_unit, count(*) AS requests FROM request GROUP BY 1 ORDER BY 2 DESC, 1"


def test_ai_sql_becomes_exploratory_and_is_logged(start):
    llm, messages = live(
        start, intent("sql", sql=SQL_BY_UNIT, sq="Kërkesat sipas njësisë", en="Requests by unit")
    )
    a = ask(start, "Which administrative unit had the most requests in July?", "en", llm=llm)
    assert a["label"] == "exploratory"
    assert a["interpreted_as"] == {"sq": "Kërkesat sipas njësisë", "en": "Requests by unit"}
    assert a["table"]["columns"] == ["admin_unit", "requests"]
    assert a["llm"]["used"] is True and a["llm"]["model"] == MODEL_SMART
    assert a["llm"]["cost_usd"] == pytest.approx((2000 * 2.0 + 100 * 10.0) / 1e6)
    assert a["llm"]["cached"] is False
    call = messages.calls[0]
    assert call["model"] == MODEL_SMART
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert "request(" in call["system"] and "Gjinar" not in call["system"]  # schema, no rows
    purpose, sent = start.execute("SELECT purpose, sent_json FROM llm_call").fetchone()
    sent = json.loads(sent)
    assert purpose == "copilot_intent" and sent["rows_sent"] == 0 and sent["schema_only"]


def test_ai_intent_is_cached_honestly(start):
    llm, messages = live(start, intent("sql", sql=SQL_BY_UNIT))
    q = "Which administrative unit had the most requests?"
    first = ask(start, q, "en", llm=llm)
    second = ask(start, q.upper(), "en", llm=llm)
    assert len(messages.calls) == 1
    assert first["llm"]["cached"] is False
    assert second["llm"] == {
        "used": True,
        "model": MODEL_SMART,
        "latency_ms": 0,
        "cost_usd": 0.0,
        "cached": True,
    }
    assert second["table"] == first["table"]


def test_ai_passport_intent_is_verified(start):
    llm, _ = live(start, intent("passport", code="FIN-02"))
    a = ask(start, "Si shkon me projektet e reja të ndërtimit?", "sq", llm=llm)
    assert a["label"] == "verified" and a["passport_code"] == "FIN-02"
    assert a["value"] == pytest.approx(20.0) and "20,0%" in a["answer"]["sq"]
    assert a["llm"]["used"] is True


def test_ai_sql_is_still_guarded(start):
    llm, _ = live(start, intent("sql", sql="SELECT * FROM llm_call"))
    a = ask(start, "Show everything the AI was sent", "en", llm=llm)
    assert a["label"] == "blocked" and a["llm"]["used"] is True
    assert "System tables" in a["blocked_reason"]["en"]


def test_ai_refusals(start):
    llm, _ = live(
        start,
        intent("refuse", reason="personal_data"),
        intent("refuse", reason="out_of_scope"),
    )
    assert ask(start, "Kush ankohet më shpesh?", "sq", llm=llm)["label"] == "blocked"
    a = ask(start, "Kush fitoi ndeshjen e djeshme?", "sq", llm=llm)
    assert a["label"] == "not_answerable" and "nuk lidhet" in a["answer"]["sq"]


def test_ai_digits_in_interpretation_are_replaced_by_code_text(start):
    llm, _ = live(start, intent("sql", sql=SQL_BY_UNIT, sq="Korrik 2026", en="July 2026"))
    a = ask(start, "Which unit had the most requests?", "en", llm=llm)
    assert a["label"] == "exploratory"
    assert a["interpreted_as"]["en"] == (
        "Quick look at the data · prepared with AI help · from: Citizen requests"
    )


def test_ai_failure_falls_back_honestly(start):
    llm, _ = live(start, RuntimeError("boom"))
    a = ask(start, "Which unit had the most requests?", "en", llm=llm)
    assert a["label"] == "not_answerable"
    assert a["llm"]["used"] is True
    assert "did not return a valid interpretation" in a["answer"]["en"]


def test_ai_breakdown_route_for_filtered_passport_questions(start):
    llm, messages = live(start, intent("sql", sql=SQL_BY_UNIT))
    a = ask(start, "Sa kërkesa u pranuan në Gjinar?", "sq", llm=llm)
    assert a["label"] == "exploratory" and len(messages.calls) == 1


def test_ai_is_not_called_for_blocked_gap_or_verified_questions(start):
    llm, messages = live(start)
    assert ask(start, "Më jep emrat dhe telefonat e kërkuesve", "sq", llm=llm)["label"] == "blocked"
    assert ask(start, "How much waste per resident per year?", "en", llm=llm)["label"] == (
        "not_answerable"
    )
    assert ask(start, "Sa jane zbatuar investimet kapitale?", "sq", llm=llm)["label"] == "verified"
    assert messages.calls == []
    assert start.execute("SELECT count(*) FROM llm_call").fetchone()[0] == 0


def test_exploratory_example_uses_ai_when_live_and_falls_back(start):
    llm, messages = live(start, RuntimeError("boom"))
    a = ask(start, "", "en", "exploratory-directorates", llm=llm)
    assert len(messages.calls) == 1
    assert a["label"] == "exploratory" and a["llm"]["used"] is True
    assert "prepared example" in a["interpreted_as"]["en"]


def test_parse_intent_rejects_malformed_output():
    assert intent_mod.parse_intent({"kind": "passport", "passport_code": "XYZ-99"}) is None
    assert intent_mod.parse_intent({"kind": "sql", "sql": "  "}) is None
    assert intent_mod.parse_intent("nope") is None
    ok = intent_mod.parse_intent(intent("passport", code="REQ-01"))
    assert ok.kind == "passport" and ok.passport_code == "REQ-01"


def test_intent_schema_follows_the_structured_output_subset():
    schema = intent_mod.intent_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert "REQ-01" in schema["properties"]["passport_code"]["enum"]
    prompt = intent_mod.system_prompt()
    for table in ("request", "budget_line", "waste_collection", "revenue", "staff", "population"):
        assert f"- {table}(" in prompt
    assert "source(" not in prompt and "llm_call" not in prompt
    assert "REQ-01" in prompt and "HR-02" in prompt


# --------------------------------------------------------------------------------------------
# HTTP endpoints
# --------------------------------------------------------------------------------------------


def test_post_ask_contract_shape(client):
    from app.warehouse.db import get_db

    load_start(get_db())
    res = client.post(
        "/api/v1/ask",
        json={"question": "Sa jane zbatuar investimet kapitale?", "locale": "sq"},
    )
    assert res.status_code == 200
    body = res.json()
    assert set(body) == ANSWER_KEYS
    assert set(body["llm"]) == {"used", "model", "latency_ms", "cost_usd", "cached"}
    assert body["label"] == "verified" and body["value"] == pytest.approx(20.0)
    assert set(body["sources"][0]) == {"source_id", "filename", "rows"}


def test_post_ask_with_example_and_errors(client):
    res = client.post(
        "/api/v1/ask", json={"question": "", "locale": "en", "example_id": "gap-rev-02"}
    )
    assert res.status_code == 200 and res.json()["gap"]["dataset"] == "revenue"
    bad = client.post("/api/v1/ask", json={"question": "", "locale": "en", "example_id": "zzz"})
    assert bad.status_code == 404 and bad.json()["detail"]["code"] == "unknown_example"
    empty = client.post("/api/v1/ask", json={"question": " ", "locale": "sq"})
    assert empty.status_code == 422
    assert empty.json()["detail"]["message"]["en"] == "Please type a question."
    long = client.post("/api/v1/ask", json={"question": "x" * 2001, "locale": "fr"})
    assert long.status_code == 422 and long.json()["detail"]["code"] == "question_too_long"
    odd_locale = client.post("/api/v1/ask", json={"question": "Tell me a joke", "locale": "fr"})
    assert odd_locale.status_code == 200 and odd_locale.json()["label"] == "not_answerable"


def test_get_examples(client):
    res = client.get("/api/v1/ask/examples")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 7
    assert set(body[0]) == {"id", "question", "passport_code", "kind"}


def test_get_eval_404_then_file(client, tmp_path, monkeypatch):
    from app.copilot import router

    monkeypatch.setattr(router, "EVAL_RESULT_PATH", tmp_path / "eval_result.json")
    res = client.get("/api/v1/ask/eval")
    assert res.status_code == 404 and res.json()["detail"]["code"] == "eval_not_run"
    payload = {
        "run_at": "2026-09-26T05:00:00+00:00",
        "commit": "abc1234",
        "mode": "rules",
        "by_label": [{"label": "verified", "matched": 11, "total": 11}],
        "total": {"matched": 24, "total": 24},
    }
    (tmp_path / "eval_result.json").write_text(json.dumps(payload), encoding="utf-8")
    body = client.get("/api/v1/ask/eval").json()
    assert body["by_label"] == payload["by_label"] and body["commit"] == "abc1234"
    assert body["total"] == {"matched": 24, "total": 24}


def test_get_llm_calls(client, monkeypatch):
    from app.llm import client as llm_client
    from app.warehouse.db import get_db

    db = get_db()
    load_start(db)
    fake, _ = live(db, intent("sql", sql=SQL_BY_UNIT))
    monkeypatch.setattr(llm_client, "_client", fake)
    client.post("/api/v1/ask", json={"question": "Which unit had the most requests?"})
    body = client.get("/api/v1/llm/calls").json()
    assert body["mode"] == "live" and body["budget_usd"] == 5.0
    assert body["spent_usd"] > 0
    assert len(body["calls"]) == 1
    call = body["calls"][0]
    assert call["purpose"] == "copilot_intent" and call["ok"] is True
    assert call["sent"]["rows_sent"] == 0


def test_ai_sql_error_is_repaired_once(start):
    bad = "SELECT department, count(*) AS n FROM request WHERE no_such_column > 1 GROUP BY 1"
    good = "SELECT department, count(*) AS n FROM request GROUP BY 1 ORDER BY 2 DESC, 1"
    llm, messages = live(start, intent("sql", sql=bad), intent("sql", sql=good))
    q = "Which directorate has the most requests?"
    a = ask(start, q, "en", llm=llm)
    assert a["label"] == "exploratory" and a["table"]["columns"] == ["department", "n"]
    assert len(messages.calls) == 2
    repair_prompt = messages.calls[1]["messages"][0]["content"]
    assert "no_such_column" in repair_prompt and "<error>" in repair_prompt
    assert a["llm"]["cost_usd"] == pytest.approx(2 * (2000 * 2.0 + 100 * 10.0) / 1e6)
    # The repaired intent is what the cache serves next time.
    again = ask(start, q, "en", llm=llm)
    assert again["llm"]["cached"] is True and again["label"] == "exploratory"
    assert len(messages.calls) == 2


def test_ai_sql_error_after_failed_repair_gives_no_number(start):
    bad = "SELECT department FROM request WHERE no_such_column > 1"
    llm, messages = live(start, intent("sql", sql=bad), intent("sql", sql=bad))
    a = ask(start, "Which directorate has the most requests?", "en", llm=llm)
    assert a["label"] == "not_answerable" and a["value"] is None
    assert len(messages.calls) == 2  # exactly one repair attempt, no loop
