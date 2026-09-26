"""Steps 6–7 — which dataset is this file, and which column holds which canonical field?

Dataset detection scores every catalog dataset by how many of its fields find a header among
the file's (non-personal) columns. Mapping has two paths:

- **AI** (``get_llm().complete_json``, Claude Haiku 4.5): one call per file with headers,
  inferred types and at most 5 masked samples per non-personal column. The answer is checked by
  code: unknown fields are dropped, duplicate fields keep the most confident column, and a
  proposal whose type contradicts the column's values is capped at amber.
- **Rules** (no key, budget exhausted or the call failed): header synonyms from the catalog plus
  rapidfuzz similarity. Confidence is capped at 0.6 so every column shows amber and a person
  confirms it with one click.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz import fuzz

from app.catalog import DATASETS, Dataset, Field, get_dataset, header_key, normalize_text, t
from app.config import get_settings
from app.ingest.profile import ColumnProfile
from app.llm.client import MODEL_FAST, LLMResult, get_llm

RULES_CAP = 0.6
MATCH_THRESHOLD = 0.6
DATASET_THRESHOLD = 0.35
_STOP = {"i", "e", "te", "se", "ne", "per", "dhe", "nga", "me", "the", "of", "and", "in", "a", "nr"}
_NUM_TOKEN_RE = re.compile(r"^\d+$")


# --------------------------------------------------------------------------------------------
# Header ↔ field similarity
# --------------------------------------------------------------------------------------------


_PAREN_RE = re.compile(r"\(([^)]*)\)")
_UNIT_NOTE_RE = re.compile(
    r"\d|%|\b(ton|tone|tons|tonnes|kg|dite|dit|days|lek|leke|all|eur|muaj|vit)\b"
)


def synonym_key(synonym: str) -> str:
    """Comparable key of a synonym: unit notes in parentheses are dropped ("Sasia (ton)" →
    "sasia"), semantic ones are kept ("Programi (kodi)" → "programi kodi")."""
    notes = _PAREN_RE.findall(synonym)
    if notes and not all(_UNIT_NOTE_RE.search(normalize_text(n) or n) for n in notes):
        return normalize_text(synonym)
    return header_key(synonym)


@lru_cache(maxsize=512)
def _syn_keys(dataset: str, field_key: str) -> tuple[tuple[str, str], ...]:
    f = get_dataset(dataset).field(field_key)
    seen: dict[str, str] = {}
    for syn in (*f.synonyms, f.label["sq"], f.label["en"], f.key.replace("_", " ")):
        k = synonym_key(syn)
        if k and k not in seen:
            seen[k] = syn
    return tuple(seen.items())


def _content_tokens(text: str) -> set[str]:
    return {tok for tok in text.split() if tok not in _STOP and not _NUM_TOKEN_RE.match(tok)}


@dataclass(frozen=True)
class Match:
    score: float
    synonym: str
    kind: str
    """``exact`` | ``stripped`` | ``fuzzy`` | ``contains``."""


def match_field(header: str, dataset: str, field_key: str) -> Match | None:
    """Best similarity between a header and a field's synonyms (None below 0.5)."""
    h = header_key(header)
    if not h:
        return None
    h_stripped = " ".join(tok for tok in h.split() if not _NUM_TOKEN_RE.match(tok))
    h_tokens = _content_tokens(h_stripped or h)
    best: Match | None = None

    def keep(m: Match) -> None:
        nonlocal best
        if best is None or m.score > best.score:
            best = m

    for key, syn in _syn_keys(dataset, field_key):
        if h == key:
            return Match(1.0, syn, "exact")
        if h_stripped and h_stripped == key:
            keep(Match(0.95, syn, "stripped"))
            continue
        ratio = fuzz.ratio(h_stripped or h, key)
        if ratio >= 88:
            keep(Match(round(0.9 * ratio / 100, 3), syn, "fuzzy"))
        s_tokens = _content_tokens(key)
        if (
            s_tokens
            and h_tokens
            and s_tokens <= h_tokens
            and (len(s_tokens) >= 2 or len(next(iter(s_tokens))) >= 5)
        ):
            keep(Match(round(0.6 + 0.25 * len(s_tokens) / len(h_tokens), 3), syn, "contains"))
    return best if best and best.score >= 0.5 else None


def type_factor(field: Field, inferred: str) -> float:
    """Penalty when the column's values contradict the field type."""
    if inferred == "empty":
        return 0.8
    if field.type in ("float", "int"):
        if inferred in ("int", "float"):
            return 0.9 if field.type == "int" and inferred == "float" else 1.0
        return 0.3
    if field.type == "date":
        return 1.0 if inferred == "date" else 0.3
    # string fields
    if inferred == "date":
        return 0.5
    return 1.0


def type_compatible(field: Field, inferred: str) -> bool:
    return type_factor(field, inferred) >= 0.5


# --------------------------------------------------------------------------------------------
# Dataset detection
# --------------------------------------------------------------------------------------------


def detect_dataset(
    columns: list[ColumnProfile], filename: str = ""
) -> list[dict[str, float | str]]:
    """``[{key, score}]`` sorted by score (0..1), best first."""
    usable = [c for c in columns if not c.dropped]
    fname = f" {normalize_text(filename)} "
    out = []
    for ds in DATASETS.values():
        weights = 0.0
        covered = 0.0
        explained: set[int] = set()
        for f in ds.fields:
            w = 2.0 if f.required else 1.0
            weights += w
            best = 0.0
            for c in usable:
                m = match_field(c.name, ds.key, f.key)
                if m is None:
                    continue
                s = m.score * type_factor(f, c.inferred_type)
                if s > best:
                    best = s
                if s >= MATCH_THRESHOLD:
                    explained.add(c.index)
            covered += w * best
        coverage = covered / weights if weights else 0.0
        share = len(explained) / len(usable) if usable else 0.0
        score = 0.7 * coverage + 0.3 * share
        if any(f" {kw}" in fname for kw in ds.keywords):
            score += 0.1
        out.append({"key": ds.key, "score": round(min(score, 1.0), 3)})
    out.sort(key=lambda d: -float(d["score"]))
    return out


# --------------------------------------------------------------------------------------------
# Suggestions
# --------------------------------------------------------------------------------------------


@dataclass
class Suggestion:
    column: str
    field: str | None
    confidence: float
    reason: dict[str, str]
    source: str
    """``recipe`` | ``ai`` | ``rules`` | ``user``."""
    transform: str | None = None

    def api(self) -> dict:
        return {
            "column": self.column,
            "field": self.field,
            "confidence": round(float(self.confidence), 2),
            "reason": dict(self.reason),
            "transform": self.transform,
            "source": self.source,
        }


def transform_for(ds: Dataset, field_key: str | None, multiplier: int) -> str | None:
    """Short description of what code will do to the column on load (shown in the UI)."""
    if field_key is None:
        return None
    f = ds.field(field_key)
    if f.money and multiplier > 1:
        return f"×{multiplier:,}".replace(",", ".")
    return {
        "admin_unit": "admin_unit",
        "line_type": "line_type",
        "programme_code": "programme_code",
        "status": "status",
        "basis": "basis",
        "month": "month",
    }.get(f.normalizer or "")


def no_match_reason(column: str) -> dict[str, str]:
    return t(
        f"Kolona '{column}' nuk përputhet me asnjë fushë të këtij grupi të dhënash.",
        f"Column '{column}' does not match any field of this dataset.",
    )


def rules_mapping(
    ds: Dataset, columns: list[ColumnProfile]
) -> tuple[list[Suggestion], dict[int, list[tuple[str, float]]]]:
    """Greedy one-to-one assignment by similarity; returns suggestions and per-column candidates."""
    usable = [c for c in columns if not c.dropped]
    pairs: list[tuple[float, int, int, str, Match]] = []
    candidates: dict[int, list[tuple[str, float]]] = {}
    for c in usable:
        for f in ds.fields:
            m = match_field(c.name, ds.key, f.key)
            if m is None:
                continue
            score = round(m.score * type_factor(f, c.inferred_type), 3)
            candidates.setdefault(c.index, []).append((f.key, score))
            if score >= MATCH_THRESHOLD:
                pairs.append((score, 0 if f.required else 1, c.index, f.key, m))
    for lst in candidates.values():
        lst.sort(key=lambda x: -x[1])
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
    by_col: dict[int, tuple[str, float, Match]] = {}
    used_fields: set[str] = set()
    for score, _req, col_idx, field_key, m in pairs:
        if col_idx in by_col or field_key in used_fields:
            continue
        by_col[col_idx] = (field_key, score, m)
        used_fields.add(field_key)

    out: list[Suggestion] = []
    for c in usable:
        if c.index not in by_col:
            out.append(Suggestion(c.name, None, 0.0, no_match_reason(c.name), "rules"))
            continue
        field_key, score, m = by_col[c.index]
        f = ds.field(field_key)
        conf = round(min(RULES_CAP, RULES_CAP * score), 2)
        if m.kind == "exact":
            reason = t(
                f"Koka '{c.name}' përputhet me emërtimin '{m.synonym}' të fushës "
                f"'{f.label['sq']}'.",
                f"Header '{c.name}' matches the name '{m.synonym}' of field '{f.label['en']}'.",
            )
        elif m.kind == "stripped":
            reason = t(
                f"Koka '{c.name}' (pa vitin/numrat) përputhet me '{m.synonym}' → "
                f"'{f.label['sq']}'.",
                f"Header '{c.name}' (without year/numbers) matches '{m.synonym}' → "
                f"'{f.label['en']}'.",
            )
        else:
            reason = t(
                f"Koka '{c.name}' i ngjan emërtimit '{m.synonym}' të fushës '{f.label['sq']}'.",
                f"Header '{c.name}' resembles '{m.synonym}' of field '{f.label['en']}'.",
            )
        out.append(Suggestion(c.name, field_key, conf, reason, "rules"))
    return out, candidates


# --------------------------------------------------------------------------------------------
# AI mapping (Claude Haiku, structured output)
# --------------------------------------------------------------------------------------------

MAPPING_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["columns", "question"],
    "properties": {
        "columns": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["column", "field", "confidence", "reason_sq", "reason_en"],
                "properties": {
                    "column": {"type": "string"},
                    "field": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                    "reason_sq": {"type": "string"},
                    "reason_en": {"type": "string"},
                },
            },
        },
        "question": {
            "type": "object",
            "additionalProperties": False,
            "required": ["column", "text_sq", "text_en", "options"],
            "properties": {
                "column": {"type": ["string", "null"]},
                "text_sq": {"type": "string"},
                "text_en": {"type": "string"},
                "options": {"type": "array", "items": {"type": ["string", "null"]}},
            },
        },
    },
}

MAPPING_SYSTEM = """\
You map the columns of a spreadsheet exported by a department of an Albanian municipality to \
the canonical fields of one dataset in a municipal data warehouse.

You see only column headers (mostly in Albanian), the type inferred by code and up to 5 masked \
sample values per column. Personal columns (names, phones, emails, addresses, personal numbers) \
were removed before this request; you never see rows.

Rules:
- For every column listed, return exactly one item with "field" set to one field key from the \
list, or null when no field fits (extra columns are normal).
- Never map two columns to the same field. Respect types: numbers to numeric fields, dates or \
months to date fields.
- "confidence" is between 0 and 1. Use 0.9 or more only when both the header and the samples \
clearly fit; use less when you are guessing.
- "reason_sq" (Albanian) and "reason_en" (English): one short sentence each about the header \
and samples. Do not repeat numbers from the samples.
- Money columns may be in thousands of lek ("000 lekë"); code applies the multiplier, so just \
map them.
- If a required field has no clear column, or one column could be two fields, ask ONE short \
clarifying question about one column in "question" (text in Albanian and English, "options" = \
2 or 3 field keys, may include null). Otherwise set question.column to null, both texts to "" \
and options to [].
"""


def mapping_prompt(ds: Dataset, columns: list[ColumnProfile]) -> tuple[str, dict]:
    """The user prompt (JSON) and the ``sent`` summary for the call log."""
    usable = [c for c in columns if not c.dropped]
    # Cell values stay on the server unless LLM_SEND_SAMPLES is switched on explicitly.
    n_samples = 5 if get_settings().llm_send_samples else 0
    payload = {
        "dataset": {"key": ds.key, "name_sq": ds.name["sq"], "name_en": ds.name["en"]},
        "fields": [
            {
                "key": f.key,
                "type": f.type,
                "required": f.required,
                "label_sq": f.label["sq"],
                "label_en": f.label["en"],
                "typical_headers": list(f.synonyms[:5]),
            }
            for f in ds.fields
        ],
        "columns": [
            {"name": c.name, "inferred_type": c.inferred_type, "samples": c.samples[:n_samples]}
            for c in usable
        ],
    }
    prompt = "Map these columns. Answer with the JSON object only.\n\n" + json.dumps(
        payload, ensure_ascii=False, indent=1
    )
    sent = {
        "dataset": ds.key,
        "headers": len(usable),
        "samples_per_column": max((len(c.samples[:n_samples]) for c in usable), default=0),
        "pii_columns_withheld": sum(1 for c in columns if c.dropped),
    }
    return prompt, sent


@dataclass
class AiMapping:
    suggestions: dict[str, Suggestion]
    question: dict | None
    result: LLMResult
    sent: dict


def ai_mapping(ds: Dataset, columns: list[ColumnProfile]) -> AiMapping | None:
    """One Haiku call; returns None when AI is unavailable. Failed calls return an empty map."""
    llm = get_llm()
    if llm.mode != "live":
        return None
    prompt, sent = mapping_prompt(ds, columns)
    res = llm.complete_json(
        prompt,
        schema=MAPPING_SCHEMA,
        tool_name="column_mapping",
        system=MAPPING_SYSTEM,
        model=MODEL_FAST,
        max_tokens=2048,
        purpose="ingest_mapping",
        sent=sent,
    )
    if not res.ok or not isinstance(res.data, dict):
        return AiMapping({}, None, res, sent)
    return AiMapping(*_validate_ai(ds, columns, res.data), result=res, sent=sent)


def _validate_ai(
    ds: Dataset, columns: list[ColumnProfile], data: dict
) -> tuple[dict[str, Suggestion], dict | None]:
    usable = {c.name: c for c in columns if not c.dropped}
    by_norm = {normalize_text(n): n for n in usable}
    valid_fields = set(ds.field_keys)
    chosen: dict[str, Suggestion] = {}
    for item in data.get("columns") or []:
        if not isinstance(item, dict):
            continue
        raw_col = str(item.get("column") or "")
        col = raw_col if raw_col in usable else by_norm.get(normalize_text(raw_col))
        if col is None or col in chosen:
            continue
        field_key = item.get("field")
        if field_key not in valid_fields:
            field_key = None
        try:
            conf = float(item.get("confidence", 0))
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf if conf == conf else 0.0))
        reason = t(
            str(item.get("reason_sq") or "").strip()[:240] or "Propozim i AI.",
            str(item.get("reason_en") or "").strip()[:240] or "AI proposal.",
        )
        if field_key and not type_compatible(ds.field(field_key), usable[col].inferred_type):
            conf = min(conf, 0.5)
            reason = t(
                reason["sq"] + " (Kodi: lloji i vlerave nuk përputhet — kontrolloni.)",
                reason["en"] + " (Code check: value type does not match — please review.)",
            )
        if field_key is None:
            conf = conf if conf else 0.0
        chosen[col] = Suggestion(col, field_key, conf, reason, "ai")

    # one column per field: keep the most confident proposal
    by_field: dict[str, Suggestion] = {}
    for s in chosen.values():
        if s.field is None:
            continue
        other = by_field.get(s.field)
        if other is None or s.confidence > other.confidence:
            if other is not None:
                other.field, other.confidence = None, 0.0
                other.reason = _duplicate_reason(other.column, s.column)
            by_field[s.field] = s
        else:
            s.field, s.confidence = None, 0.0
            s.reason = _duplicate_reason(s.column, other.column)

    question = None
    q = data.get("question")
    if isinstance(q, dict):
        qcol = q.get("column")
        qcol = qcol if qcol in usable else by_norm.get(normalize_text(qcol or ""))
        options = [o for o in (q.get("options") or []) if o is None or o in valid_fields]
        options = list(dict.fromkeys(options))[:4]
        text_sq = str(q.get("text_sq") or "").strip()[:300]
        text_en = str(q.get("text_en") or "").strip()[:300]
        if qcol and len(options) >= 2 and text_sq and text_en:
            question = {
                "column": qcol,
                "text": t(text_sq, text_en),
                "options": [option(ds, o) for o in options],
            }
    return chosen, question


def _duplicate_reason(column: str, winner: str) -> dict[str, str]:
    return t(
        f"AI propozoi të njëjtën fushë edhe për '{winner}'; u mbajt propozimi më i sigurt.",
        f"AI proposed the same field for '{winner}' as well; the more confident one was kept.",
    )


# --------------------------------------------------------------------------------------------
# Clarifying question
# --------------------------------------------------------------------------------------------

_IGNORE = t("Asnjë — injoroje kolonën", "None — ignore the column")


def option(ds: Dataset, field_key: str | None) -> dict:
    if field_key is None:
        return {"field": None, "label": dict(_IGNORE)}
    return {"field": field_key, "label": dict(ds.field(field_key).label)}


def drift_question(ds: Dataset, new_col: str, old_col: str, field_key: str) -> dict:
    label = ds.field(field_key).label
    return {
        "column": new_col,
        "text": t(
            f"Kolona '{new_col}' zëvendëson '{old_col}' të recetës së ruajtur. "
            f"A përmban të njëjtën fushë ({label['sq']})?",
            f"Column '{new_col}' replaces '{old_col}' from the saved recipe. "
            f"Does it hold the same field ({label['en']})?",
        ),
        "options": [option(ds, field_key), option(ds, None)],
    }


def rules_question(
    ds: Dataset,
    columns: list[ColumnProfile],
    suggestions: list[Suggestion],
    candidates: dict[int, list[tuple[str, float]]],
) -> dict | None:
    """At most one question: an ambiguous column, else a required field with no column."""
    mapped = {s.field for s in suggestions if s.field}
    by_name = {c.name: c for c in columns}
    for s in suggestions:
        c = by_name[s.column]
        cands = [x for x in candidates.get(c.index, []) if x[1] >= MATCH_THRESHOLD]
        if s.field and len(cands) >= 2 and cands[0][1] - cands[1][1] <= 0.05:
            a, b = cands[0][0], cands[1][0]
            la, lb = ds.field(a).label, ds.field(b).label
            return {
                "column": s.column,
                "text": t(
                    f"Kolona '{s.column}' mund të jetë '{la['sq']}' ose '{lb['sq']}'. Cila është?",
                    f"Column '{s.column}' could be '{la['en']}' or '{lb['en']}'. Which is it?",
                ),
                "options": [option(ds, a), option(ds, b), option(ds, None)],
            }
    for f in ds.fields:
        if not f.required or f.key in mapped:
            continue
        best: tuple[float, str] | None = None
        for s in suggestions:
            if s.field is not None:
                continue
            c = by_name[s.column]
            score = dict(candidates.get(c.index, [])).get(f.key, 0.0)
            if not type_compatible(f, c.inferred_type):
                continue
            score = max(score, 0.1)
            if best is None or score > best[0]:
                best = (score, s.column)
        if best:
            col = best[1]
            return {
                "column": col,
                "text": t(
                    f"Nuk u gjet kolonë për fushën e detyrueshme '{f.label['sq']}'. "
                    f"A e përmban kolona '{col}'?",
                    f"No column was found for the required field '{f.label['en']}'. "
                    f"Does column '{col}' hold it?",
                ),
                "options": [option(ds, f.key), option(ds, None)],
            }
    return None
