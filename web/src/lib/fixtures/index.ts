/**
 * REPLAY engine: an in-browser stand-in for the Sportel API built from SYNTHETIC
 * fixtures. It implements the same functions as `lib/api.ts` so the gap-to-proof
 * loop (reset → gap → ingest → receipt → verified → tile turns green) can be shown
 * offline. It is only used when the API is unreachable or NEXT_PUBLIC_USE_FIXTURES=1,
 * and the UI always shows a REPLAY badge while it is.
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
import { answer, EXAMPLES } from "./ask.ts";
import { DATASETS, PRELOADED, SAMPLES, type DatasetKey } from "./catalog.ts";
import { buildCoverage } from "./coverage.ts";
import { buildBoard, buildLineage, buildPassport, INDICATORS } from "./indicators.ts";
import { buildPreview, buildReceipt, defaultMapping, fileSpec, recipeMatch } from "./ingest.ts";
import type { ReplayState } from "./state.ts";
import { EVAL, HEALTH, LLM_CALLS } from "./system.ts";

const STORAGE_KEY = "sportel:replay-state:v1";
const SEED_TIME = "2026-09-26T00:30:00Z";

function computableCodes(state: ReplayState): Set<string> {
  return new Set(
    INDICATORS.filter((def) => def.datasets.every((d) => state.loaded.has(d))).map((def) => def.code),
  );
}

function coverageOf(state: ReplayState) {
  return { computable: computableCodes(state).size, total: INDICATORS.length };
}

function unlockedBetween(before: Set<string>, after: Set<string>): LoadReceipt["indicators_unlocked"] {
  return INDICATORS.filter((def) => after.has(def.code) && !before.has(def.code)).map((def) => ({
    code: def.code,
    name: def.name,
  }));
}

/** Start state after `POST /demo/reset`: requests + budget + population → 6/13. */
export function initialState(): ReplayState {
  const state: ReplayState = { loaded: new Map(), recipes: new Map(), basis: "census_2023", previews: new Map(), seq: 0 };
  PRELOADED.forEach((dataset, i) => {
    const sample = SAMPLES.find((s) => s.dataset === dataset && s.preload)!;
    const spec = fileSpec(sample.name)!;
    const before = computableCodes(state);
    state.loaded.set(dataset, buildReceipt(spec, {
      sourceId: `src_seed_${String(i + 1).padStart(2, "0")}`,
      mapping: defaultMapping(spec),
      recipe: { saved: false, reused: false, recipe_id: null },
      unlocked: [],
      coverage: { computable: 0, total: INDICATORS.length },
      loadedAt: SEED_TIME,
    }));
    const after = computableCodes(state);
    const receipt = state.loaded.get(dataset)!;
    receipt.indicators_unlocked = unlockedBetween(before, after);
    receipt.coverage = coverageOf(state);
  });
  return state;
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
        loaded: [DatasetKey, SourceInfo][];
        recipes: [DatasetKey, ReplayState["recipes"] extends Map<DatasetKey, infer R> ? R : never][];
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

// ---------------------------------------------------------------- endpoints

export async function getHealth(): Promise<Health> {
  await delay(60);
  const s = load();
  return { ...HEALTH, synthetic: [...s.loaded.values()].some((src) => src.synthetic) };
}

export async function getBoard(pack = "core_kpi"): Promise<IndicatorBoard> {
  await delay(180);
  if (pack !== "core_kpi") notFound(`pack ${pack}`);
  return clone(buildBoard(load()));
}

export async function getPassport(code: string): Promise<Passport> {
  await delay(140);
  return clone(buildPassport(code, load()) ?? notFound(`indicator ${code}`));
}

export async function getLineage(code: string, limit = 50): Promise<LineageRows> {
  await delay(120);
  return clone(buildLineage(code, limit, load()) ?? notFound(`indicator ${code}`));
}

export async function getDatasets(): Promise<DatasetInfo[]> {
  await delay(80);
  const s = load();
  return (Object.keys(DATASETS) as DatasetKey[]).map((key) => {
    const { exportName: _exportName, rows, ...info } = DATASETS[key];
    void _exportName;
    const src = s.loaded.get(key);
    return clone({ ...info, loaded: Boolean(src), sources: src ? 1 : 0, rows: src ? rows : 0 });
  });
}

export async function getSamples(): Promise<SampleFile[]> {
  await delay(90);
  const s = load();
  return SAMPLES.map(({ dataset, hash: _hash, ...sample }) => {
    void _hash;
    return { ...sample, loaded: s.loaded.get(dataset)?.filename === sample.name };
  });
}

function preview(sampleName: string): IngestPreview {
  const s = load();
  const spec = fileSpec(sampleName) ?? notFound(`sample ${sampleName}`);
  s.seq += 1;
  const previewId = `fx-${s.seq}-${spec.fingerprint}`;
  const result = buildPreview(spec, previewId, recipeMatch(spec, s.recipes.get(spec.dataset)));
  s.previews.set(previewId, { preview: result, sample: sampleName });
  save();
  return clone(result);
}

export async function previewSample(name: string): Promise<IngestPreview> {
  await delay(650);
  return preview(name);
}

/** Only the synthetic sample files can be previewed offline; match by file name. */
export async function previewUpload(file: File): Promise<IngestPreview> {
  await delay(750);
  const norm = file.name.toLowerCase();
  const sample =
    SAMPLES.find((s) => s.name.toLowerCase() === norm) ??
    SAMPLES.find((s) => {
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
  const spec = fileSpec(entry.sample) ?? notFound(`sample ${entry.sample}`);
  if (body.dataset !== spec.dataset) {
    throw new ApiError(422, "dataset_mismatch", "dataset mismatch", {
      sq: `Ky skedar përputhet me grupin '${spec.dataset}', jo '${body.dataset}'.`,
      en: `This file matches the '${spec.dataset}' dataset, not '${body.dataset}'.`,
    });
  }
  const before = computableCodes(s);
  const reused = entry.preview.recipe.hit;
  let recipeId = entry.preview.recipe.recipe_id;
  let saved = false;
  if (body.save_recipe && !reused) {
    recipeId = `rcp_${spec.dataset}_${String(s.seq).padStart(2, "0")}`;
    s.recipes.set(spec.dataset, {
      id: recipeId,
      dataset: spec.dataset,
      fingerprint: spec.fingerprint,
      from_filename: spec.sample,
      columns: body.mapping.map((m) => m.column),
    });
    saved = true;
  }
  s.seq += 1;
  const receipt = buildReceipt(spec, {
    sourceId: `src_${spec.dataset}_${String(s.seq).padStart(2, "0")}`,
    mapping: body.mapping,
    recipe: { saved, reused, recipe_id: saved || reused ? recipeId : null },
    unlocked: [],
    coverage: coverageOf(s),
    loadedAt: new Date().toISOString(),
  });
  s.loaded.set(spec.dataset, receipt);
  receipt.indicators_unlocked = unlockedBetween(before, computableCodes(s));
  receipt.coverage = coverageOf(s);
  s.previews.delete(body.preview_id);
  save();
  const { mapping: _mapping, ...loadReceipt } = receipt;
  void _mapping;
  return clone(loadReceipt);
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

export async function getCoverage(pack = "al_smp"): Promise<Coverage> {
  await delay(160);
  if (pack !== "al_smp") notFound(`pack ${pack}`);
  return buildCoverage();
}

export async function setPopulationBasis(value: PopulationBasis): Promise<{ ok: true; basis: PopulationBasis }> {
  await delay(150);
  const s = load();
  s.basis = value;
  save();
  return { ok: true, basis: value };
}

export async function ask(body: AskBody): Promise<AskAnswer> {
  await delay(body.example_id ? 350 : 600);
  return clone(answer(load(), body.question, body.example_id));
}

export async function getExamples(): Promise<AskExample[]> {
  await delay(80);
  return clone(EXAMPLES);
}

export async function getEval(): Promise<AskEval> {
  await delay(80);
  return clone(EVAL);
}

export async function getLlmCalls(): Promise<LlmCalls> {
  await delay(90);
  return clone(LLM_CALLS);
}
