/**
 * REPLAY engine: an in-browser stand-in for the Sportel API, used only when the API is
 * unreachable or `NEXT_PUBLIC_USE_FIXTURES=1`, and always badged REPLAY in the header.
 *
 * It computes nothing. Every number, preview, receipt and answer is a response the live
 * API gave over the SYNTHETIC sample exports, recorded by `web/scripts/record-replay.mjs`
 * into `snapshot.ts`. The engine only keeps the demo state (which exports are loaded,
 * which recipes are saved, the pinned population basis) and picks the recorded response
 * that matches it, so the gap-to-proof loop (reset → gap → ingest → receipt → verified →
 * tile turns green) plays offline with the same numbers as the live API.
 */
import {
  ApiError,
  type AskAnswer,
  type AskBody,
  type AskEval,
  type AskExample,
  type CommitBody,
  type Coverage,
  type DatasetInfo,
  type DeleteRecipesResult,
  type Health,
  type IndicatorBoard,
  type IndicatorSummary,
  type IngestPreview,
  type LineageRows,
  type LlmCalls,
  type LoadReceipt,
  type Passport,
  type PopulationBasis,
  type ResetResult,
  type SampleFile,
  type SourceInfo,
} from "../api.ts";
import { routeQuestion } from "./ask.ts";
import { buildCoverage } from "./coverage.ts";
import { SNAPSHOT } from "./snapshot.ts";

// ---------------------------------------------------------------- state

type Recipe = { id: string; dataset: string; from: string };

export type ReplayState = {
  /** Loaded dataset key → the source that fed it. */
  loaded: Map<string, SourceInfo>;
  /** Saved mapping recipes by dataset. */
  recipes: Map<string, Recipe>;
  basis: PopulationBasis;
  previews: Map<string, { sample: string; preview: IngestPreview }>;
  seq: number;
};

const STORAGE_KEY = "sportel:replay-state:v2";
const CODES = Object.keys(SNAPSHOT.passports.full);

export function initialState(): ReplayState {
  return {
    loaded: new Map(SNAPSHOT.seeds.map((s) => [s.dataset, s])),
    recipes: new Map(),
    basis: "census_2023",
    previews: new Map(),
    seq: 0,
  };
}

let state: ReplayState | null = null;

function storage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.sessionStorage : null;
  } catch {
    return null;
  }
}

function load(): ReplayState {
  if (state) return state;
  const raw = storage()?.getItem(STORAGE_KEY);
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as {
        loaded: [string, SourceInfo][];
        recipes: [string, Recipe][];
        basis: PopulationBasis;
        seq: number;
      };
      state = {
        loaded: new Map(parsed.loaded),
        recipes: new Map(parsed.recipes),
        basis: parsed.basis,
        previews: new Map(),
        seq: parsed.seq,
      };
      return state;
    } catch {
      // Corrupt snapshot: fall through to a fresh start state.
    }
  }
  state = initialState();
  return state;
}

function save() {
  if (!state) return;
  try {
    storage()?.setItem(
      STORAGE_KEY,
      JSON.stringify({
        loaded: [...state.loaded.entries()],
        recipes: [...state.recipes.entries()],
        basis: state.basis,
        seq: state.seq,
      }),
    );
  } catch {
    // Storage blocked (private mode, previews): state lives in memory only.
  }
}

/** Test hook: start from a clean state without touching storage. */
export function __resetReplayForTests() {
  state = initialState();
}

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

/** Small artificial latency so loading states and step reveals behave like the API. */
const delay = (ms: number) =>
  typeof window === "undefined" ? Promise.resolve() : new Promise<void>((r) => setTimeout(r, ms));

function notFound(what: string): never {
  throw new ApiError(404, "not_found", `${what} not found`, {
    sq: `Nuk u gjet: ${what}`,
    en: `Not found: ${what}`,
  });
}

// ---------------------------------------------------------------- passports

const isComputable = (code: string, s: ReplayState) =>
  SNAPSHOT.passports.full[code].required_datasets.every((d) => s.loaded.has(d));

function computableCodes(s: ReplayState): Set<string> {
  return new Set(CODES.filter((code) => isComputable(code, s)));
}

const coverageOf = (s: ReplayState) => ({ computable: computableCodes(s).size, total: CODES.length });

/** Dataset of every recorded source id, to relink passports to the source loaded now. */
const DATASET_OF_SOURCE = new Map(
  [...SNAPSHOT.seeds, ...SNAPSHOT.sources_full, ...Object.values(SNAPSHOT.receipts)].map((s) => [s.source_id, s.dataset]),
);
const DATASET_OF_FILE = new Map(
  [...SNAPSHOT.seeds, ...SNAPSHOT.sources_full, ...Object.values(SNAPSHOT.receipts)].map((s) => [s.filename, s.dataset]),
);

/** Point a recorded passport's sources and lineage at the sources loaded in this state. */
function relink(p: Passport, s: ReplayState): Passport {
  const current = (sourceId: string) => {
    const dataset = DATASET_OF_SOURCE.get(sourceId);
    return dataset ? s.loaded.get(dataset) : undefined;
  };
  return {
    ...p,
    sources: p.sources.map((src) => {
      const now = current(src.source_id);
      return now ? { source_id: now.source_id, filename: now.filename, synthetic: now.synthetic } : src;
    }),
    lineage: p.lineage.map((l) => {
      const now = current(l.source_id);
      return now ? { ...l, source_id: now.source_id, filename: now.filename, file_hash: now.file_hash } : l;
    }),
  };
}

function passportFor(code: string, s: ReplayState): Passport {
  if (isComputable(code, s)) {
    const civil = s.basis === "civil_registry" ? SNAPSHOT.passports.civil_registry[code] : undefined;
    return relink(civil ?? SNAPSHOT.passports.full[code], s);
  }
  return SNAPSHOT.passports.start[code];
}

function summary(p: Passport): IndicatorSummary {
  const {
    formula: _formula,
    question: _question,
    sql: _sql,
    series: _series,
    lineage: _lineage,
    required_datasets: _required,
    checks: _checks,
    computed_at: _computedAt,
    ...rest
  } = p;
  void [_formula, _question, _sql, _series, _lineage, _required, _checks, _computedAt];
  return rest;
}

export function buildBoard(s: ReplayState): IndicatorBoard {
  const indicators = CODES.map((code) => summary(passportFor(code, s)));
  const computable = indicators.filter((i) => i.state === "computable").length;
  const anyEnvelope = [...s.loaded.values()].some((src) => !SNAPSHOT.seeds.some((seed) => seed.source_id === src.source_id));
  const meta = anyEnvelope ? SNAPSHOT.board.full : SNAPSHOT.board.start;
  return {
    pack: meta.pack,
    as_of: meta.as_of,
    coverage: { computable, missing: indicators.length - computable, document: 0, national: 0, total: indicators.length },
    basis: { population: s.basis },
    indicators,
  };
}

// ---------------------------------------------------------------- endpoints: indicators

export async function getHealth(): Promise<Health> {
  await delay(60);
  const s = load();
  // REPLAY never calls a model, whatever mode the recording API was in.
  return {
    ...SNAPSHOT.health,
    llm: false,
    mode: "rules",
    spent_usd: 0,
    synthetic: [...s.loaded.values()].some((src) => src.synthetic),
  };
}

export async function getBoard(pack = "core_kpi"): Promise<IndicatorBoard> {
  await delay(180);
  if (pack !== "core_kpi") notFound(`pack ${pack}`);
  return clone(buildBoard(load()));
}

export async function getPassport(code: string): Promise<Passport> {
  await delay(140);
  if (!SNAPSHOT.passports.full[code]) notFound(`indicator ${code}`);
  return clone(passportFor(code, load()));
}

export async function getLineage(code: string, limit = 50): Promise<LineageRows> {
  await delay(120);
  const recorded = SNAPSHOT.lineage[code] ?? notFound(`indicator ${code}`);
  const s = load();
  if (!isComputable(code, s)) return { code, columns: [], total: 0, rows: [] };
  const rows = recorded.rows.slice(0, Math.max(0, limit)).map((row) => {
    const dataset = DATASET_OF_FILE.get(row.source_file);
    const now = dataset ? s.loaded.get(dataset) : undefined;
    return now ? { ...row, source_file: now.filename } : row;
  });
  return clone({ ...recorded, rows });
}

export async function getCoverage(pack = "al_smp"): Promise<Coverage> {
  await delay(160);
  if (pack !== "al_smp") notFound(`pack ${pack}`);
  const s = load();
  return clone(buildCoverage((code) => isComputable(code, s), s.basis));
}

export async function setPopulationBasis(value: PopulationBasis): Promise<{ ok: true; basis: PopulationBasis }> {
  await delay(150);
  const s = load();
  s.basis = value;
  save();
  return { ok: true, basis: value };
}

// ---------------------------------------------------------------- endpoints: ingest

export async function getDatasets(): Promise<DatasetInfo[]> {
  await delay(80);
  const s = load();
  return clone(
    SNAPSHOT.datasets.map((d) => {
      const src = s.loaded.get(d.key);
      return { ...d, loaded: Boolean(src), sources: src ? 1 : 0, rows: src?.rows_loaded ?? 0 };
    }),
  );
}

export async function getSamples(): Promise<SampleFile[]> {
  await delay(90);
  const s = load();
  return clone(SNAPSHOT.samples.map((sample) => ({ ...sample, loaded: s.loaded.get(sample.dataset_hint)?.filename === sample.name })));
}

function recordedPreview(sample: string, s: ReplayState): IngestPreview {
  const fresh = SNAPSHOT.previews.fresh[sample] ?? notFound(`sample ${sample}`);
  const dataset = fresh.dataset?.key;
  const recipe = dataset ? s.recipes.get(dataset) : undefined;
  if (recipe?.from === sample && SNAPSHOT.previews.recipe_hit[sample]) {
    const hit = SNAPSHOT.previews.recipe_hit[sample];
    return { ...hit, recipe: { ...hit.recipe, recipe_id: recipe.id } };
  }
  const drift = SNAPSHOT.previews.drift;
  if (recipe && drift?.filename === sample) return drift;
  return fresh;
}

function preview(sample: string): IngestPreview {
  const s = load();
  const recorded = recordedPreview(sample, s);
  s.seq += 1;
  const previewId = `fx-${s.seq}-${recorded.recipe.fingerprint}`;
  const result = { ...clone(recorded), preview_id: previewId };
  s.previews.set(previewId, { preview: result, sample });
  save();
  return clone(result);
}

export async function previewSample(name: string): Promise<IngestPreview> {
  await delay(650);
  return preview(name);
}

/** Offline, only the synthetic sample files can be previewed; they are matched by file name. */
export async function previewUpload(file: File): Promise<IngestPreview> {
  await delay(750);
  const norm = file.name.toLowerCase();
  const sample =
    SNAPSHOT.samples.find((s) => s.name.toLowerCase() === norm) ??
    SNAPSHOT.samples.find((s) => {
      const stem = s.name.toLowerCase().split("_sintetike")[0];
      return stem.length > 2 && norm.startsWith(stem);
    });
  if (!sample) {
    throw new ApiError(422, "replay_unknown_file", "REPLAY can only preview the sample files", {
      sq: "API nuk është e arritshme. Në modalitetin REPLAY mund të përdoren vetëm skedarët shembull sintetikë.",
      en: "The API is unreachable. In REPLAY mode only the synthetic sample files can be used.",
    });
  }
  return preview(sample.name);
}

function receiptFor(sample: string): LoadReceipt | null {
  const recorded = SNAPSHOT.receipts[sample];
  if (recorded) return recorded;
  const seed = SNAPSHOT.seeds.find((s) => s.filename === sample);
  if (!seed) return null;
  const { mapping: _mapping, ...receipt } = seed;
  void _mapping;
  return receipt;
}

export async function commitIngest(body: CommitBody): Promise<LoadReceipt> {
  await delay(900);
  const s = load();
  const entry = s.previews.get(body.preview_id);
  if (!entry) {
    throw new ApiError(404, "preview_expired", "preview not found", {
      sq: "Parapamja nuk u gjet ose ka skaduar. Ngarkojeni skedarin përsëri.",
      en: "The preview was not found or has expired. Load the file again.",
    });
  }
  const expected = entry.preview.dataset?.key;
  const info = SNAPSHOT.datasets.find((d) => d.key === body.dataset);
  if (!info || body.dataset !== expected) {
    throw new ApiError(422, "dataset_mismatch", "dataset mismatch", {
      sq: `Ky skedar përputhet me grupin '${expected ?? "?"}', jo '${body.dataset}'.`,
      en: `This file matches the '${expected ?? "?"}' dataset, not '${body.dataset}'.`,
    });
  }
  const mapped = new Set(body.mapping.map((m) => m.field).filter(Boolean));
  const unmapped = info.fields.filter((f) => f.required && !mapped.has(f.key));
  if (unmapped.length > 0) {
    throw new ApiError(422, "required_fields_unmapped", "required fields unmapped", {
      sq: `Mungojnë fusha të detyrueshme: ${unmapped.map((f) => f.label.sq).join(", ")}. Zgjidhni kolonën për secilën.`,
      en: `Required fields are not mapped: ${unmapped.map((f) => f.label.en).join(", ")}. Choose a column for each.`,
    });
  }
  const recorded = receiptFor(entry.sample) ?? notFound(`receipt ${entry.sample}`);

  const before = computableCodes(s);
  const hit = entry.preview.recipe.hit;
  const saved = Boolean(body.save_recipe) && !hit;
  const recipeId = hit
    ? entry.preview.recipe.recipe_id
    : saved
      ? (recorded.recipe.recipe_id ?? `rcp-${body.dataset}-${s.seq}`)
      : null;
  if (saved && recipeId) s.recipes.set(body.dataset, { id: recipeId, dataset: body.dataset, from: entry.sample });

  const receipt: LoadReceipt = {
    ...clone(recorded),
    recipe: { saved, reused: hit, recipe_id: recipeId },
    loaded_at: new Date().toISOString(),
    indicators_unlocked: [],
    coverage: coverageOf(s),
  };
  s.loaded.set(body.dataset, { ...receipt, mapping: body.mapping });
  const after = computableCodes(s);
  receipt.indicators_unlocked = CODES.filter((code) => after.has(code) && !before.has(code)).map((code) => ({
    code,
    name: SNAPSHOT.passports.full[code].name,
  }));
  receipt.coverage = coverageOf(s);
  s.loaded.set(body.dataset, { ...receipt, mapping: body.mapping });
  s.previews.delete(body.preview_id);
  save();
  return clone(receipt);
}

export async function getSources(): Promise<SourceInfo[]> {
  await delay(100);
  return clone(
    [...load().loaded.values()].sort((a, b) => b.loaded_at.localeCompare(a.loaded_at) || b.source_id.localeCompare(a.source_id)),
  );
}

export async function resetDemo(): Promise<ResetResult> {
  await delay(400);
  state = initialState();
  save();
  return { ok: true, coverage: coverageOf(state) };
}

export async function deleteRecipes(): Promise<DeleteRecipesResult> {
  await delay(150);
  const s = load();
  const deleted = s.recipes.size;
  s.recipes.clear();
  save();
  return { ok: true, deleted };
}

/** Number of saved recipes (REPLAY only; the live API reports it via /sources receipts). */
export function recipeCount(): number {
  return load().recipes.size;
}

// ---------------------------------------------------------------- endpoints: ask + system

function answerFor(code: string, s: ReplayState, exampleId?: string): AskAnswer {
  if (!isComputable(code, s)) {
    return (exampleId && SNAPSHOT.ask.examples_start[exampleId]) || SNAPSHOT.ask.start[code];
  }
  if (s.basis === "civil_registry" && SNAPSHOT.ask.civil_registry[code]) return SNAPSHOT.ask.civil_registry[code];
  return (exampleId && SNAPSHOT.ask.examples_full[exampleId]) || SNAPSHOT.ask.full[code];
}

export function answer(s: ReplayState, question: string, exampleId?: string): AskAnswer {
  const example = SNAPSHOT.examples.find((e) => e.id === exampleId);
  let recorded: AskAnswer;
  if (example?.passport_code) recorded = answerFor(example.passport_code, s, example.id);
  else if (example) recorded = SNAPSHOT.ask.examples_start[example.id];
  else {
    const route = routeQuestion(question);
    if (route.kind === "passport") recorded = answerFor(route.code, s);
    else if (route.kind === "blocked") {
      const blocked = SNAPSHOT.examples.find((e) => e.kind === "blocked");
      recorded = (blocked && SNAPSHOT.ask.examples_start[blocked.id]) || SNAPSHOT.ask.free_text.write;
    } else if (route.kind === "write") recorded = SNAPSHOT.ask.free_text.write;
    else recorded = SNAPSHOT.ask.free_text.unknown;
  }
  const text = question.trim() || recorded.question;
  return { ...clone(recorded), question: text, ...(recorded.sql === recorded.question ? { sql: text } : {}) };
}

export async function ask(body: AskBody): Promise<AskAnswer> {
  await delay(body.example_id ? 350 : 600);
  return clone(answer(load(), body.question, body.example_id));
}

export async function getExamples(): Promise<AskExample[]> {
  await delay(80);
  return clone(SNAPSHOT.examples);
}

export async function getEval(): Promise<AskEval> {
  await delay(80);
  if (!SNAPSHOT.eval) notFound("evaluation");
  return clone(SNAPSHOT.eval);
}

export async function getLlmCalls(): Promise<LlmCalls> {
  await delay(90);
  return { spent_usd: 0, budget_usd: SNAPSHOT.llm_calls.budget_usd, mode: "rules", calls: [] };
}
