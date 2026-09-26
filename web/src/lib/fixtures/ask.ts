/**
 * REPLAY fixtures: copilot examples and answers. The label is decided here by code
 * (contract §6), exactly like the API: verified when every dataset of the routed
 * passport is loaded, not_answerable (with owner) when one is missing, blocked for
 * personal data / writes, exploratory only for the curated example with a fixed SQL.
 */
import type { AskAnswer, AskExample, L10n } from "../api";
import { formatPeriod } from "../format.ts";
import { DATASETS, type DatasetKey } from "./catalog.ts";
import { fillAnswer, indicatorDef, INDICATORS, periodOf, sampleForDataset } from "./indicators.ts";
import type { ReplayState } from "./state.ts";

export const EXAMPLES: AskExample[] = [
  {
    id: "ex-req-02",
    kind: "verified",
    passport_code: "REQ-02",
    question: {
      sq: "Sa përqind e kërkesave u zgjidhën brenda afatit në gusht?",
      en: "What share of requests was resolved on time in August?",
    },
  },
  {
    id: "ex-fin-02",
    kind: "verified",
    passport_code: "FIN-02",
    question: {
      sq: "Sa është zbatimi i buxhetit të investimeve deri në gusht?",
      en: "What is capital investment execution up to August?",
    },
  },
  {
    id: "ex-gap-waste",
    kind: "gap",
    passport_code: "WST-01",
    question: { sq: "Sa ton mbetje u grumbulluan në gusht?", en: "How many tonnes of waste were collected in August?" },
  },
  {
    id: "ex-gap-revenue",
    kind: "gap",
    passport_code: "REV-01",
    question: {
      sq: "Sa përqind e taksave dhe tarifave vendore është arkëtuar?",
      en: "What share of local taxes and fees has been collected?",
    },
  },
  {
    id: "ex-gap-staff",
    kind: "gap",
    passport_code: "HR-01",
    question: { sq: "Sa punonjës ka bashkia për 1.000 banorë?", en: "How many staff per 1,000 residents?" },
  },
  {
    id: "ex-explore-categories",
    kind: "exploratory",
    passport_code: null,
    question: {
      sq: "Cilat janë 3 kategoritë me më shumë kërkesa të hapura?",
      en: "Which 3 categories have the most open requests?",
    },
  },
  {
    id: "ex-blocked-pii",
    kind: "blocked",
    passport_code: null,
    question: {
      sq: "Më jep emrat dhe numrat e telefonit të kërkuesve.",
      en: "Give me the names and phone numbers of the requesters.",
    },
  },
];

const NO_LLM: AskAnswer["llm"] = { used: false, model: null, latency_ms: null, cost_usd: null, cached: false };

const normalise = (text: string) =>
  text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9.,\s-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

const BLOCK_PATTERNS = [
  /\bemr(at|i|in)\b/,
  /\btelefon/,
  /\bnames?\b/,
  /\bphones?\b/,
  /\be-?mail/,
  /\b(delete|drop|update|insert|alter|truncate)\b/,
  /\b(fshi|ndrysho)\b/,
  /\bnumr(i|in|at) personal/,
];

/** Topic keywords for gap routing when no passport matches exactly. */
const TOPICS: { dataset: DatasetKey; words: string[] }[] = [
  { dataset: "waste", words: ["mbetje", "mbeturina", "pastrim", "waste", "garbage", "tonnes"] },
  { dataset: "revenue", words: ["taksa", "tarifa", "arketim", "tax", "fee", "revenue"] },
  { dataset: "staff", words: ["punonjes", "staf", "rotacion", "staff", "employee", "turnover"] },
];

function route(question: string, exampleId?: string): { code: string | null; kind: AskExample["kind"] | "topic" | "none"; dataset?: DatasetKey } {
  const example = EXAMPLES.find((e) => e.id === exampleId);
  if (example) return { code: example.passport_code, kind: example.kind };
  const text = normalise(question);
  if (BLOCK_PATTERNS.some((p) => p.test(text))) return { code: null, kind: "blocked" };
  const exact = EXAMPLES.find((e) => normalise(e.question.sq) === text || normalise(e.question.en) === text);
  if (exact) return { code: exact.passport_code, kind: exact.kind };
  let best: { code: string; score: number } | null = null;
  for (const def of INDICATORS) {
    const score = def.keywords.reduce((s, k) => (text.includes(normalise(k)) ? s + normalise(k).length : s), 0);
    if (score > 0 && (!best || score > best.score)) best = { code: def.code, score };
  }
  if (best) return { code: best.code, kind: "verified" };
  const topic = TOPICS.find((t) => t.words.some((w) => text.includes(w)));
  if (topic) return { code: null, kind: "topic", dataset: topic.dataset };
  return { code: null, kind: "none" };
}

function gapAnswer(question: string, dataset: DatasetKey, interpreted: L10n): AskAnswer {
  const ds = DATASETS[dataset];
  const sample = sampleForDataset(dataset);
  return {
    label: "not_answerable",
    question,
    interpreted_as: interpreted,
    answer: {
      sq: `Pa përgjigje: mungon eksporti «${ds.exportName.sq}». Përgjegjës: ${ds.owner.name.sq}. Asnjë numër nuk u hamendësua.`,
      en: `Not answerable: the «${ds.exportName.en}» export is missing. Owner: ${ds.owner.name.en}. No number was guessed.`,
    },
    value: null,
    unit: null,
    passport_code: null,
    sql: null,
    table: null,
    sources: [],
    gap: { dataset, name: ds.exportName, owner: ds.owner.name, sample: sample?.name ?? null },
    blocked_reason: null,
    llm: NO_LLM,
  };
}

export function answer(state: ReplayState, question: string, exampleId?: string): AskAnswer {
  const r = route(question, exampleId);

  if (r.kind === "blocked") {
    return {
      label: "blocked",
      question,
      interpreted_as: {
        sq: "Kërkesë për të dhëna personale individuale",
        en: "Request for individual-level personal data",
      },
      answer: {
        sq: "Kjo pyetje u bllokua nga rregullat e sigurisë. Nuk u ekzekutua asnjë pyetje SQL.",
        en: "This question was blocked by the safety rules. No SQL query was executed.",
      },
      value: null,
      unit: null,
      passport_code: null,
      sql: null,
      table: null,
      sources: [],
      gap: null,
      blocked_reason: {
        sq: "Kërkohen të dhëna personale (emra, telefona). Kolonat personale hiqen gjatë ngarkimit dhe nuk mund të pyeten; lejohen vetëm tabelat kanonike pa fusha personale.",
        en: "Personal data was requested (names, phones). Personal columns are removed on load and cannot be queried; only canonical tables without personal fields are allowed.",
      },
      llm: NO_LLM,
    };
  }

  if (r.kind === "exploratory") {
    const src = state.loaded.get("requests");
    if (!src) return gapAnswer(question, "requests", { sq: "Kërkesa të hapura sipas kategorisë", en: "Open requests by category" });
    return {
      label: "exploratory",
      question,
      interpreted_as: {
        sq: "Kërkesa të hapura sipas kategorisë · 3 më të mëdhatë",
        en: "Open requests by category · top 3",
      },
      answer: {
        sq: "Rezultati i pyetjes eksploruese: 3 rreshta nga tabela e kërkesave. Nuk është tregues i verifikuar; formula nuk është e miratuar.",
        en: "Exploratory query result: 3 rows from the requests table. This is not a verified indicator; the formula is not approved.",
      },
      value: null,
      unit: null,
      passport_code: null,
      sql: `SELECT category, count(*) AS open_requests
FROM request
WHERE closed_at IS NULL
GROUP BY category
ORDER BY open_requests DESC
LIMIT 3`,
      table: {
        columns: ["category", "open_requests"],
        rows: [
          ["Rrugë dhe trotuare", 41],
          ["Ndriçim publik", 29],
          ["Pastrim", 22],
        ],
      },
      sources: [{ source_id: src.source_id, filename: src.filename, rows: "4–2395 (148 rreshta të hapur)" }],
      gap: null,
      blocked_reason: null,
      llm: NO_LLM,
    };
  }

  if (r.kind === "topic" && r.dataset) {
    return gapAnswer(question, r.dataset, {
      sq: `Temë: ${DATASETS[r.dataset].name.sq}`,
      en: `Topic: ${DATASETS[r.dataset].name.en}`,
    });
  }

  const def = r.code ? indicatorDef(r.code) : null;
  if (!def) {
    return {
      label: "not_answerable",
      question,
      interpreted_as: { sq: "Pyetje e lirë, pa përputhje me një pasaportë", en: "Free text, no passport match" },
      answer: {
        sq: "AI jashtë linje: pyetja nuk u lidh me asnjë tregues. Provoni një pyetje shembull. Asnjë numër nuk u hamendësua.",
        en: "AI offline: the question did not match any indicator. Try an example question. No number was guessed.",
      },
      value: null,
      unit: null,
      passport_code: null,
      sql: null,
      table: null,
      sources: [],
      gap: null,
      blocked_reason: null,
      llm: NO_LLM,
    };
  }

  const interpreted: L10n = {
    sq: `${def.code} · ${def.name.sq} · ${formatPeriod(periodOf(def), "sq")}`,
    en: `${def.code} · ${def.name.en} · ${formatPeriod(periodOf(def), "en")}`,
  };
  const missing = def.datasets.find((d) => !state.loaded.has(d));
  if (missing) return gapAnswer(question, missing, interpreted);

  const value = def.series(state.basis).at(-1)?.value ?? null;
  if (value == null) return gapAnswer(question, def.datasets[0], interpreted);
  return {
    label: "verified",
    question,
    interpreted_as: interpreted,
    answer: {
      sq: fillAnswer(def, value, "sq", formatPeriod(periodOf(def), "sq")),
      en: fillAnswer(def, value, "en", formatPeriod(periodOf(def), "en")),
    },
    value,
    unit: def.unit,
    passport_code: def.code,
    sql: def.sql.replaceAll("{basis}", state.basis),
    table: null,
    sources: def.lineage.map((l) => {
      const src = state.loaded.get(l.dataset);
      return { source_id: src?.source_id ?? "", filename: src?.filename ?? l.dataset, rows: l.row_ranges };
    }),
    gap: null,
    blocked_reason: null,
    llm: NO_LLM,
  };
}
