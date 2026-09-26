#!/usr/bin/env node
/**
 * Record the REPLAY snapshot from a running Sportel API.
 *
 * REPLAY (offline mode, always badged in the header) must never show a number that code
 * did not compute. This script drives a live API through the demo states and records its
 * real responses into `src/lib/fixtures/snapshot.ts`:
 *   reset → start state (6/13) → envelopes 1–3 committed with recipes → full state (13/13)
 *   → civil-registry basis for the per-capita passports → reset.
 *
 * Usage (API running, e.g. `make api`):
 *   pnpm --dir web record-replay                 # http://localhost:8000
 *   pnpm --dir web record-replay http://localhost:8117
 *
 * It resets the demo before and after recording. Re-run it whenever the passports, the
 * samples or the ingest pipeline change, then run `pnpm --dir web test`.
 */
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const API = `${(process.argv[2] ?? process.env.REPLAY_API_URL ?? "http://localhost:8000").replace(/\/+$/, "")}/api/v1`;
const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "lib", "fixtures", "snapshot.ts");
const LINEAGE_ROWS = 20;

async function call(method, path, body) {
  const res = await fetch(API + path, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status}: ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : null;
}
const get = (path) => call("GET", path);
const post = (path, body) => call("POST", path, body);

/** Keep only the keys of contract §7 (the API may add extra diagnostics). */
const only = (obj, keys) => Object.fromEntries(keys.filter((k) => k in obj).map((k) => [k, obj[k]]));
const RECEIPT_KEYS = [
  "source_id", "filename", "file_hash", "dataset", "dataset_name", "synthetic", "rows_read", "rows_loaded",
  "rows_excluded", "reconciliation", "pii_dropped", "unit_multiplier", "llm", "recipe", "indicators_unlocked",
  "coverage", "loaded_at", "duration_ms",
];
const SOURCE_KEYS = [...RECEIPT_KEYS, "mapping"];
const PREVIEW_KEYS = [
  "preview_id", "filename", "file_hash", "size_bytes", "synthetic", "dataset", "dataset_candidates", "sheet",
  "header_row", "data_rows", "unit_multiplier", "unit_note", "excluded_rows", "columns", "mapping", "question",
  "recipe", "llm", "steps", "warnings",
];
const EVAL_KEYS = ["run_at", "commit", "mode", "by_label"];
const source = (s) => only(s, SOURCE_KEYS);
const preview = (p) => ({ ...only(p, PREVIEW_KEYS), preview_id: "" });
const commitBody = (p, saveRecipe) => ({
  preview_id: p.preview_id,
  dataset: p.dataset.key,
  mapping: p.mapping.map((m) => ({ column: m.column, field: m.field })),
  save_recipe: saveRecipe,
});

/** Coverage items that differ from `base` (the SMP items mapped to a passport). */
const changedItems = (base, next) =>
  next.items.filter((item) => JSON.stringify(item) !== JSON.stringify(base.items.find((b) => b.number === item.number)));

async function passports(codes) {
  const out = {};
  for (const code of codes) out[code] = await get(`/indicators/${encodeURIComponent(code)}`);
  return out;
}

async function main() {
  console.log(`Recording REPLAY snapshot from ${API}`);
  await post("/demo/reset");

  // ---------------------------------------------------------------- start state
  const health = await get("/health");
  const datasets = await get("/datasets");
  const samples = await get("/samples");
  const examples = await get("/ask/examples");
  let evaluation = null;
  try {
    evaluation = only(await get("/ask/eval"), EVAL_KEYS);
  } catch {
    console.log("  /ask/eval: not run yet (REPLAY answers 404 too)");
  }
  const llmCalls = await get("/llm/calls");
  const boardStart = await get("/indicators?pack=core_kpi");
  const codes = boardStart.indicators.map((i) => i.code);
  const passportsStart = await passports(codes);
  const seeds = (await get("/sources")).map(source);
  const coverageStart = await get("/coverage?pack=al_smp");
  const ask = async (question, exampleId) =>
    post("/ask", { question, locale: "sq", ...(exampleId ? { example_id: exampleId } : {}) });
  const askStart = {};
  for (const code of codes) askStart[code] = await ask(passportsStart[code].question.sq);
  const examplesStart = {};
  for (const ex of examples) examplesStart[ex.id] = await ask(ex.question.sq, ex.id);
  const freeText = {
    unknown: await ask("Cili është moti nesër në Elbasan?"),
    write: await ask("DELETE FROM request"),
  };

  // ---------------------------------------------------------------- previews before any recipe
  const fresh = {};
  for (const s of samples) fresh[s.name] = preview(await post(`/samples/${encodeURIComponent(s.name)}/preview`));

  // ---------------------------------------------------------------- envelopes 1–3 with recipes
  const envelopes = samples.filter((s) => s.envelope != null).sort((a, b) => a.envelope - b.envelope);
  const receipts = {};
  for (const s of envelopes) {
    const p = await post(`/samples/${encodeURIComponent(s.name)}/preview`);
    receipts[s.name] = only(await post("/ingest/commit", commitBody(p, true)), RECEIPT_KEYS);
    console.log(`  committed ${s.name}: ${receipts[s.name].rows_loaded} rows`);
  }
  const recipeHit = {};
  for (const s of envelopes) recipeHit[s.name] = preview(await post(`/samples/${encodeURIComponent(s.name)}/preview`));
  const drift = samples.find((s) => s.envelope == null && !s.preload);
  const driftPreview = drift ? preview(await post(`/samples/${encodeURIComponent(drift.name)}/preview`)) : null;

  // ---------------------------------------------------------------- full state (census basis)
  const boardFull = await get("/indicators?pack=core_kpi");
  const passportsFull = await passports(codes);
  const lineage = {};
  for (const code of codes) lineage[code] = await get(`/indicators/${encodeURIComponent(code)}/lineage?limit=${LINEAGE_ROWS}`);
  const sourcesFull = (await get("/sources")).map(source);
  const coverageFull = await get("/coverage?pack=al_smp");
  const askFull = {};
  for (const code of codes) askFull[code] = await ask(passportsFull[code].question.sq);
  const examplesFull = {};
  for (const ex of examples) examplesFull[ex.id] = await ask(ex.question.sq, ex.id);

  // ---------------------------------------------------------------- civil-registry basis
  const basisCodes = codes.filter((c) => passportsFull[c].basis != null);
  await post("/definitions/population_basis", { value: "civil_registry", reason: "REPLAY recording" });
  const passportsCivil = await passports(basisCodes);
  const coverageCivil = await get("/coverage?pack=al_smp");
  const askCivil = {};
  for (const code of basisCodes) askCivil[code] = await ask(passportsFull[code].question.sq);
  await post("/definitions/population_basis", { value: "census_2023", reason: "REPLAY recording" });

  // ---------------------------------------------------------------- drift commit (last: it replaces waste)
  let driftReceipt = null;
  if (drift) {
    const p = await post(`/samples/${encodeURIComponent(drift.name)}/preview`);
    try {
      driftReceipt = only(await post("/ingest/commit", commitBody(p, false)), RECEIPT_KEYS);
    } catch (error) {
      console.log(`  drift commit not recorded: ${error.message.slice(0, 120)}`);
    }
  }
  await post("/demo/reset");

  const snapshot = {
    recorded_at: new Date().toISOString(),
    api_version: health.version,
    health,
    datasets,
    samples,
    examples,
    eval: evaluation,
    llm_calls: llmCalls,
    board: { start: only(boardStart, ["pack", "as_of", "basis"]), full: only(boardFull, ["pack", "as_of", "basis"]) },
    passports: { start: passportsStart, full: passportsFull, civil_registry: passportsCivil },
    lineage,
    coverage: {
      start: coverageStart,
      full: changedItems(coverageStart, coverageFull),
      civil_registry: changedItems(coverageFull, coverageCivil),
    },
    seeds,
    sources_full: sourcesFull,
    previews: { fresh, recipe_hit: recipeHit, drift: driftPreview },
    receipts: { ...receipts, ...(drift && driftReceipt ? { [drift.name]: driftReceipt } : {}) },
    ask: { start: askStart, full: askFull, civil_registry: askCivil, examples_start: examplesStart, examples_full: examplesFull, free_text: freeText },
  };

  const header = `/**
 * GENERATED by \`web/scripts/record-replay.mjs\` from a live Sportel API (${API.replace(/\/api\/v1$/, "")},
 * version ${health.version}) on ${snapshot.recorded_at}. Do not edit by hand: re-record instead.
 *
 * Every value here was computed by the API's code over the SYNTHETIC sample exports; the
 * REPLAY engine (\`./index.ts\`) only replays these responses and is always badged REPLAY.
 */
import type { ReplaySnapshot } from "./snapshot-types.ts";

export const SNAPSHOT: ReplaySnapshot = `;
  writeFileSync(OUT, `${header}${JSON.stringify(snapshot, null, 1)};\n`, "utf8");
  console.log(`Wrote ${OUT} (${Math.round(JSON.stringify(snapshot).length / 1024)} KB)`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
