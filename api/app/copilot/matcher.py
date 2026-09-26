"""Deterministic question understanding: passport matching, filters, blocked intents, topics.

Everything here is plain code (no model): it runs in RULES mode and before any AI call.

Matching works on diacritic-insensitive tokens (``catalog.normalize_text``). Tokens are reduced
to *concepts* (e.g. "kërkesave", "requests" → REQUEST; "zbatimi", "zbatuar" → EXEC) or to a
5-character stem, then each passport is scored against the question with IDF weights computed
over the passports' own phrasings (question, aliases and name, both languages):

    score = 0.6 × coverage + 0.4 × best-phrasing Dice

``coverage`` is the weighted share of the question's terms found in the passport's vocabulary;
unknown words carry a high weight, so a question that asks for something the passport does not
describe ("... for street lighting") falls below the threshold instead of being over-answered.

``detect_filters`` finds what a fixed passport cannot answer — a specific month, unit,
directorate, category or year, a ranking ("which unit ... most"), or a breakdown ("by month").
``detect_blocked`` finds requests to change data or to reveal personal data.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import lru_cache

from app.catalog import ADMIN_UNIT_VARIANTS, normalize_text
from app.indicators.registry import load_pack

# --------------------------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------------------------


def _words(text: str) -> frozenset[str]:
    """Whitespace-separated word list → frozenset (keeps long vocabularies readable)."""
    return frozenset(text.split())


STOPWORDS: frozenset[str] = _words(
    """
    sa se e i te ne nga per dhe a me nje eshte jane ishte ishin ka kemi kane kishte kjo ky keto
    kete ketij kesaj ketyre deri tani u do si cfare qe po jo mund duhet bashkia bashkise bashkine
    bashki bashkiak bashkiake elbasan elbasani elbasanit ai ajo ato ata yne jone tona tane tuaj
    cili cila cilat cilet cilin cilen ciles cilit kush pse kur ku lutem ju na tregoni trego tregon
    tregom jepni jep dua di mu mua gjate brenda kundrejt ndaj mbi nen pa prej tek sipas cdo gjithe
    gjitha vetem akoma ende edhe apo ose por nese mire shume pak kaq aq qenka jeni jam je eshte
    si mesatarisht aktualisht sot momentin deri tani ne fund zakonisht perafersisht rreth
    how many much what which who whose where when why is are was were the a an of in on to for
    by with within from this that these those so far date ytd do does did we our us you your i
    me my it its there have has had be been being per each every all please tell show give can
    could would will let know at as and or versus vs against than up out get got municipality
    municipal city town elbasan currently now today take takes taking does doing overall
    approximately about around roughly exactly actually total
    """
)

# Concept classes: exact tokens and prefixes ("x*"). Longest prefix wins.
_CONCEPTS: dict[str, tuple[str, ...]] = {
    "REQUEST": ("kerkes*", "request*", "ankes*", "complain*", "ticket*"),
    "CITIZEN": ("qytetar*", "citizen*"),
    "RECEIVE": ("pranuar", "pranua*", "receiv*", "regjistr*", "register*", "submit*", "marre",
                "marrin", "marrim", "filed", "paraqit*"),
    "DEADLINE": ("afat*", "deadline*", "ontime", "sla"),
    "RESOLVE": ("zgjidh*", "resolv*", "resolut*", "mbyll*", "close*", "closing"),
    "OPEN": ("hapur", "open", "pazgjidh*", "unresolv*", "backlog*", "pres", "presin", "pending"),
    "LATE": ("vonu*", "vones*", "overdue", "late", "kaluar", "kalua*", "past", "jashte",
             "pertej"),
    "AVG": ("mesatar*", "average*", "mean"),
    "DAY": ("dit", "dite", "diteve", "ditet", "ditesh", "day", "days"),
    "DURATION": ("koha", "kohe", "kohes", "shpejt*", "fast*", "quick*", "long", "zgjat*",
                 "time"),
    "BUDGET": ("buxhet*", "budget*"),
    "EXEC": ("zbat*", "realiz*", "execut*", "implement*"),
    "PLAN": ("plan", "plani", "planit", "planin", "planifik*", "planned", "plans"),
    "SPEND": ("shpenz*", "spend*", "spent", "expenditur*"),
    "CAPITAL": ("kapital*", "capital*", "invest*"),
    "WASTE": ("mbetj*", "mbeturin*", "plehr*", "waste*", "garbag*", "rubbish*", "trash*"),
    "COLLECT": ("grumbull*", "mbledh*", "collect*", "arket*"),
    "TONNE": ("ton", "tone", "tonel*", "tonne*", "tons", "tonazh*"),
    "KG": ("kg", "kilogram*", "kilo"),
    "RESIDENT": ("banor*", "resident*", "inhabit*", "fryme", "frymes", "people", "person",
                 "popullsi*", "population*"),
    "YEAR": ("vit", "viti", "vitin", "vitit", "vjet*", "year*", "annual*", "annu*"),
    "COST": ("kosto*", "kusht*", "cost*"),
    "FEE": ("tarif*", "fee", "fees"),
    "CLEAN": ("pastr*", "clean*"),
    "TAX": ("taks*", "tax", "taxes"),
    "REVENUE": ("teardhura", "revenue*", "incom*"),
    "COVER": ("mbul*", "cover*", "paguhet", "paid"),
    "STAFF": ("punonj*", "staf*", "employ*", "personel*", "workforc*", "worker*"),
    "THOUSAND": ("mije", "thousand"),
    "TURNOVER": ("rotacion*", "turnover*", "qarkull*", "attrit*", "larg*", "leav*", "left"),
    "HIRE": ("pranim*", "hire*", "hiring", "punesim*"),
    "RATE": ("perqind*", "percent*", "share", "rate", "rates", "shkall*", "ratio", "raport*"),
    "COUNT": ("numr*", "number*", "count"),
    "AMOUNT": ("sasi*", "amount*", "quantit*"),
    "MANAGE": ("menaxh*", "manag*"),
    "SERVICE": ("sherbim*", "servic*"),
}  # fmt: skip


def _build_concepts() -> tuple[dict[str, str], list[tuple[str, str]]]:
    exact: dict[str, str] = {}
    prefixes: list[tuple[str, str]] = []
    for concept, entries in _CONCEPTS.items():
        for entry in entries:
            if entry.endswith("*"):
                prefixes.append((entry[:-1], concept))
            else:
                exact[entry] = concept
    prefixes.sort(key=lambda x: len(x[0]), reverse=True)
    return exact, prefixes


_EXACT, _PREFIXES = _build_concepts()

_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p), r)
    for p, r in (
        (r"\bper capita\b", " per resident "),
        (r"\bper fryme\b", " per banor "),
        (r"\bte ardhura\w*", " teardhura "),
        (r"\bne kohe\b", " ontime "),
        (r"\bon time\b", " ontime "),
        (r"\bburime\w* njerezore\b", " staff "),
        (r"\bhuman resources\b", " staff "),
        (r"\b1 ?000\b", " mije "),
        (r"\bnje mije\b", " mije "),
    )
]


def normalize(text: str) -> str:
    """``normalize_text`` plus phrase replacements (multi-word concepts, "1.000" → "mije")."""
    norm = f" {normalize_text(text)} "
    for pattern, repl in _REPLACEMENTS:
        norm = pattern.sub(repl, norm)
    return " ".join(norm.split())


def term(token: str) -> str:
    """Concept id for a token, else its 5-character stem."""
    if token in _EXACT:
        return _EXACT[token]
    for prefix, concept in _PREFIXES:
        if token.startswith(prefix):
            return concept
    return token[:5] if len(token) > 5 else token


def terms(text: str) -> list[str]:
    """Content terms of a text (stopwords and numbers removed), in order, de-duplicated."""
    out: list[str] = []
    for tok in normalize(text).split():
        if tok in STOPWORDS or tok.isdigit() or len(tok) < 2:
            continue
        tm = term(tok)
        if tm not in out:
            out.append(tm)
    return out


# --------------------------------------------------------------------------------------------
# Passport index and scoring
# --------------------------------------------------------------------------------------------

MATCH_THRESHOLD = 0.62
"""Minimum score to route to a passport."""
UNKNOWN_WEIGHT = 2.2
"""Weight of a question term that no passport phrasing uses (penalises unrelated detail)."""


@dataclass(frozen=True)
class _Entry:
    code: str
    phrasings: tuple[frozenset[str], ...]
    vocab: frozenset[str]


@dataclass(frozen=True)
class Index:
    entries: tuple[_Entry, ...]
    idf: dict[str, float]
    vocabulary: frozenset[str]


@lru_cache(maxsize=4)
def build_index(pack: str = "core_kpi") -> Index:
    passports = load_pack(pack).passports
    entries = []
    df: dict[str, int] = {}
    for p in passports:
        texts = [*p.phrasings(), p.name["sq"], p.name["en"]]
        phrasings = tuple(frozenset(terms(x)) for x in texts)
        vocab = frozenset().union(*phrasings)
        entries.append(_Entry(p.code, phrasings, vocab))
        for tm in vocab:
            df[tm] = df.get(tm, 0) + 1
    n = len(passports)
    idf = {tm: math.log(1.0 + n / count) for tm, count in df.items()}
    return Index(tuple(entries), idf, frozenset(df))


@dataclass(frozen=True)
class Match:
    code: str
    score: float
    coverage: float
    dice: float


@dataclass(frozen=True)
class MatchResult:
    best: Match | None
    """Best-scoring passport, if it clears ``MATCH_THRESHOLD``."""
    candidates: list[Match]
    """All passports with a positive score, best first (for suggestions)."""
    terms: list[str]
    unknown: list[str]
    """Question terms that no passport phrasing uses."""


def _weight(index: Index, tm: str) -> float:
    return index.idf.get(tm, UNKNOWN_WEIGHT)


def match_passport(question: str, pack: str = "core_kpi") -> MatchResult:
    """Score every passport against ``question`` (both languages, diacritic-insensitive)."""
    index = build_index(pack)
    q = terms(question)
    unknown = [tm for tm in q if tm not in index.vocabulary]
    if not q:
        return MatchResult(None, [], q, unknown)
    qset = set(q)
    wq = sum(_weight(index, tm) for tm in qset)
    scored: list[Match] = []
    for entry in index.entries:
        covered = sum(_weight(index, tm) for tm in qset if tm in entry.vocab)
        coverage = covered / wq if wq else 0.0
        dice = 0.0
        for phrase in entry.phrasings:
            common = sum(_weight(index, tm) for tm in qset & phrase)
            wp = sum(_weight(index, tm) for tm in phrase)
            if wq + wp:
                dice = max(dice, 2 * common / (wq + wp))
        score = 0.6 * coverage + 0.4 * dice
        if score > 0:
            scored.append(Match(entry.code, round(score, 4), round(coverage, 4), round(dice, 4)))
    scored.sort(key=lambda m: m.score, reverse=True)
    best = scored[0] if scored and scored[0].score >= MATCH_THRESHOLD else None
    return MatchResult(best, scored, q, unknown)


# --------------------------------------------------------------------------------------------
# Filters and breakdowns a fixed passport cannot answer
# --------------------------------------------------------------------------------------------

_SQ_MONTHS = (
    "janar",
    "shkurt",
    "mars",
    "prill",
    "maj",
    "qershor",
    "korrik",
    "gusht",
    "shtator",
    "tetor",
    "nentor",
    "dhjetor",
)
_MONTH_FORMS: frozenset[str] = frozenset(
    {m + suffix for m in _SQ_MONTHS for suffix in ("", "i", "it", "in", "u", "ut", "un")}
    | {
        "january",
        "february",
        "march",
        "april",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "jan",
        "feb",
        "aug",
        "sep",
        "sept",
        "oct",
        "nov",
        "dec",
    }
)
_MAY_RE = re.compile(r"\b(in|of|during|since|until|for|by|through) may\b|\bmay \d{4}\b")

_DIMENSION_PREFIXES = (
    "drejtori",
    "departament",
    "department",
    "directorat",
    "njesi",
    "unit",
    "zona",
    "zonat",
    "fshat",
    "village",
    "lagj",
    "neighbo",
    "kategori",
    "categor",
    "kanal",
    "channel",
    "program",
    "lloj",
    "type",
    "pagues",
    "payer",
    "muaj",
    "month",
    "tremujor",
    "quarter",
    "jav",
    "week",
    "daily",
    "sektor",
    "sector",
    "biznes",
    "business",
    "familj",
    "household",
    "korrent",
    "current",
    "operator",
)
_RANKING_WORDS = _words(
    """
    most least highest lowest largest smallest biggest top worst best maksimum maksimal minimum
    minimal
    """
)
"""Superlatives. Wh-words ("cila", "which") alone are not filters: "Cila është përqindja…"
means "What is the percentage…"; "which unit…" is caught by the dimension word."""
_RANKING_PREFIXES = ("renditj", "rendit", "krahas", "rank", "compar", "breakdown", "trend")
_RANKING_PHRASES = re.compile(
    r"\bme (shume|pak|i larte|e larte|te larte|i ulet|e ulet|te ulet|i madh|e madhe|te medha"
    r"|i vogel|e vogel|te vogla|mire|keq)\b"
)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


@dataclass(frozen=True)
class Filters:
    months: list[str] = field(default_factory=list)
    units: list[str] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    ranking: list[str] = field(default_factory=list)
    years: list[int] = field(default_factory=list)

    @property
    def any(self) -> bool:
        return bool(self.months or self.units or self.dimensions or self.ranking)


def detect_filters(question: str) -> Filters:
    """Specific months, units, dimensions, rankings and explicit years in a question."""
    norm = normalize_text(question)
    tokens = norm.split()
    months = [tok for tok in tokens if tok in _MONTH_FORMS]
    if _MAY_RE.search(norm):
        months.append("may")
    units: list[str] = []
    for i, tok in enumerate(tokens):
        for cand in (f"{tok} {tokens[i + 1]}" if i + 1 < len(tokens) else None, tok):
            if cand and cand in ADMIN_UNIT_VARIANTS:
                name = ADMIN_UNIT_VARIANTS[cand]
                if name != "Elbasan" and name not in units:  # Elbasan is also the municipality
                    units.append(name)
    dimensions = [tok for tok in tokens if tok.startswith(_DIMENSION_PREFIXES)]
    ranking = [tok for tok in tokens if tok in _RANKING_WORDS or tok.startswith(_RANKING_PREFIXES)]
    ranking += [m.group(0) for m in _RANKING_PHRASES.finditer(norm)]
    years = sorted({int(m.group(0)) for m in _YEAR_RE.finditer(norm)})
    return Filters(months, units, dimensions, ranking, years)


# --------------------------------------------------------------------------------------------
# Blocked intents: changing data, personal data
# --------------------------------------------------------------------------------------------

_WRITE_ALWAYS = _words(
    """
    fshi fshij fshije fshini fshih fshijeni fshijini ndrysho ndryshoni ndryshoje ndryshojini
    perditeso perditesoni perditesoje shto shtoni shtoje hiq hiqni hiqe hiqini zevendeso
    zevendesoni korrigjo korrigjoni rregullo rregulloni futni boshatis boshatisni
    delete truncate insert erase wipe overwrite
    """
)
"""Imperatives that always ask to change data (Albanian imperatives, unambiguous English)."""
_WRITE_AMBIGUOUS = _words("drop update remove edit replace reset rename alter modify")
"""English verbs that are also nouns or analytics words ("why did the rate drop in July?",
"the latest update"): write intent only as a command at the start or after a request phrase,
or when followed by a data object."""
_WRITE_LEADS = re.compile(
    r"\b(please|can you|could you|would you|will you|i want to|we want to|want to|need to|"
    r"lets|let us|go ahead and|kindly|i need you to)\s*$"
)
_WRITE_OBJECTS = _words(
    """
    all the every this these those table tables row rows record records data database column
    columns value values entries entry figures numbers
    """
)
_WRITE_PREFIXES = ("fshirj",)

_PERSONAL_ALWAYS = (
    "email",
    "e mail",
    "datelindj",
    "birth",
    "leternjoftim",
    "pasaport",
    "passport",
)
_PHONE_NUMBER = re.compile(
    r"\b(numr\w* (i |e |te )?telefon\w*|telefonat|telefonave|phone numbers?|mobile numbers?"
    r"|cell(phone)? numbers?|contact details|te dhenat e kontaktit)\b"
)
_NAME_LIKE = ("emr", "emer", "mbiemr", "mbiemer", "name", "surname", "fullname", "adres",
              "address", "kontakt", "contact")  # fmt: skip
_PHONE_LIKE = ("telefon", "phone", "mobile", "celular")
_PERSON_STRICT = (
    "kerkues",
    "requester",
    "applicant",
    "punonj",
    "employee",
    "staff",
    "worker",
    "person",
    "individ",
    "pergjegjes",
    "drejtues",
    "manager",
)
"""People nouns. "qytetar"/"citizen" are left out here: "kërkesa qytetare" is an adjective."""
_PERSON_BROAD = (*_PERSON_STRICT, "qytetar", "citizen", "banor", "resident", "people")
_WINDOW = 4
_WHO_ACTION = re.compile(
    r"\b(kush|who)\b.*\b(paraqit\w*|beri|bere|dergoi|ankua\w*|submitted|filed|complained|sent"
    r"|made|lodged)\b"
)
_LIST_PERSON = re.compile(
    r"\b(list\w*|listo\w*|individ\w*)\b.*\b(kerkues\w*|requester\w*|applicant\w*|"
    r"punonjes\w*|employee\w*|banor\w*|resident\w*)\b"
)
_WHICH_PERSON = re.compile(
    r"\b(which|cilet|cilat|cili|cila|cilin|cilen)\s+(punonjes\w*|kerkues\w*|employee\w*|"
    r"requester\w*|applicant\w*|citizen\w*|qytetar\w*|resident\w*|banor\w*|people|persons?)\b"
)
_PERSONAL_NUMBER = re.compile(r"\b(numr\w* personal\w*|personal (id|number)|id number|nid)\b")


@dataclass(frozen=True)
class Blocked:
    kind: str
    """``write`` or ``personal``."""
    matched: list[str]


def _near(tokens: list[str], words: tuple[str, ...], people: tuple[str, ...]) -> list[str]:
    """Tokens starting with ``words`` that have a people noun within ``_WINDOW`` tokens."""
    hits = []
    for i, tok in enumerate(tokens):
        if not tok.startswith(words):
            continue
        window = tokens[max(0, i - _WINDOW) : i + _WINDOW + 1]
        if any(w.startswith(people) for w in window):
            hits.append(tok)
    return hits


def _write_verbs(tokens: list[str]) -> list[str]:
    hits = []
    for i, tok in enumerate(tokens):
        if tok in _WRITE_ALWAYS or tok.startswith(_WRITE_PREFIXES):
            hits.append(tok)
        elif tok in _WRITE_AMBIGUOUS:
            before = " ".join(tokens[:i])
            after = tokens[i + 1 : i + 3]
            if i == 0 or _WRITE_LEADS.search(before) or any(a in _WRITE_OBJECTS for a in after):
                hits.append(tok)
    return hits


def detect_blocked(question: str) -> Blocked | None:
    """Requests to change data or to reveal personal data about individuals."""
    norm = normalize_text(question)
    tokens = norm.split()
    personal: list[str] = [tok for tok in tokens if tok.startswith(_PERSONAL_ALWAYS)]
    personal += [m.group(0) for m in _PHONE_NUMBER.finditer(norm)]
    personal += _near(tokens, _NAME_LIKE, _PERSON_BROAD)
    personal += _near(tokens, _PHONE_LIKE, _PERSON_STRICT)
    if _PERSONAL_NUMBER.search(norm):
        personal.append("personal_number")
    for pattern in (_WHO_ACTION, _LIST_PERSON, _WHICH_PERSON):
        m = pattern.search(norm)
        if m:
            personal.append(m.group(0))
    if personal:
        return Blocked("personal", personal)
    writes = _write_verbs(tokens)
    if writes:
        return Blocked("write", writes)
    return None
