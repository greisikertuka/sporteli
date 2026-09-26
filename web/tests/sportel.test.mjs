import test from "node:test";
import assert from "node:assert/strict";

import {
  formatBytes,
  formatDelta,
  formatIndicatorValue,
  formatMs,
  formatNumber,
  formatPeriod,
  formatUsd,
  pick,
  unitDigits,
} from "../src/lib/format.ts";
import {
  ASK_LABELS,
  ASK_LABEL_TONE,
  confidenceTier,
  countCoverage,
  groupIndicatorsByArea,
  leadershipSummary,
  needsConfirmation,
  newlyComputable,
  pendingConfirmations,
  receiptBalance,
  stateSnapshot,
} from "../src/lib/labels.ts";
import * as replay from "../src/lib/fixtures/index.ts";
import { SNAPSHOT } from "../src/lib/fixtures/snapshot.ts";

// ---------------------------------------------------------------- formatting

test("numbers follow Albanian and English conventions deterministically", () => {
  assert.equal(formatNumber(1248, "sq"), "1.248");
  assert.equal(formatNumber(1248, "en"), "1,248");
  assert.equal(formatNumber(87.44, "sq", 1), "87,4");
  assert.equal(formatNumber(1284560000, "sq"), "1.284.560.000");
  assert.equal(formatNumber(-3.2, "en", 1), "−3.2");
  assert.equal(formatNumber(-0.01, "sq", 1), "0,0");
  assert.equal(formatNumber(Number.NaN, "sq"), "–");
});

test("indicator values are formatted by unit", () => {
  assert.equal(unitDigits("count"), 0);
  assert.equal(unitDigits("percent"), 1);
  assert.equal(unitDigits("per_1000"), 2);
  assert.equal(formatIndicatorValue(82.94, "percent", "sq").text, "82,9%");
  assert.equal(formatIndicatorValue(82.94, "percent", "en").text, "82.9%");
  assert.equal(formatIndicatorValue(3712, "count", "sq", "ton").text, "3.712 ton");
  assert.equal(formatIndicatorValue(10920, "lek_per_ton", "en", "lek/tonne").text, "10,920 lek/tonne");
  assert.equal(formatIndicatorValue(8.616, "per_1000", "sq", "për 1.000").number, "8,62");
  assert.equal(formatIndicatorValue(null, "percent", "sq").text, "–");
  assert.equal(formatIndicatorValue(5, "percent", "sq").tight, true);
});

test("deltas, periods, money, time and size", () => {
  assert.deepEqual(formatDelta(82.9, 84.7, "percent", "sq"), { diff: -1.8, text: "−1,8" });
  assert.equal(formatDelta(312, 297, "count", "en").text, "+15");
  assert.equal(formatDelta(1, 1, "count", "en").text, "±0");
  assert.equal(formatDelta(null, 1, "count", "en"), null);
  assert.equal(formatPeriod("2026-08", "sq"), "gusht 2026");
  assert.equal(formatPeriod("2026-08", "en"), "August 2026");
  assert.equal(formatPeriod("2026-01/2026-08", "sq"), "janar – gusht 2026");
  assert.equal(formatPeriod("2026-01..2026-08", "en", "short"), "Jan – Aug 2026");
  assert.equal(formatPeriod("2026-08-31", "sq"), "31 gusht 2026");
  assert.equal(formatPeriod(null, "sq"), "");
  assert.equal(formatUsd(0.009, "sq"), "$0,009");
  assert.equal(formatUsd(1.5, "en"), "$1.50");
  assert.equal(formatMs(3120, "sq"), "3,1 s");
  assert.equal(formatMs(842, "en"), "842 ms");
  assert.equal(formatBytes(18432, "sq"), "18,0 KB");
  assert.equal(pick({ sq: "Po", en: "Yes" }, "en"), "Yes");
  assert.equal(pick({ sq: "Po", en: "" }, "en"), "Po");
  assert.equal(pick(null, "sq"), "");
});

// ---------------------------------------------------------------- labels

test("copilot label metadata covers all four labels with fixed tones", () => {
  assert.deepEqual([...ASK_LABELS].sort(), ["blocked", "exploratory", "not_answerable", "verified"]);
  assert.equal(ASK_LABEL_TONE.verified, "success");
  assert.equal(ASK_LABEL_TONE.exploratory, "warning");
  assert.equal(ASK_LABEL_TONE.blocked, "danger");
  assert.equal(ASK_LABEL_TONE.not_answerable, "neutral");
});

test("amber mappings need an explicit confirmation before commit", () => {
  assert.equal(confidenceTier(0.8), "high");
  assert.equal(confidenceTier(0.79), "low");
  const rows = [
    { column: "Muaji", field: "month", confidence: 0.6, reason: { sq: "", en: "" }, source: "rules" },
    { column: "Plani", field: "planned_lek", confidence: 0.95, reason: { sq: "", en: "" }, source: "ai" },
    { column: "Emri", field: null, confidence: 0.2, reason: { sq: "", en: "" }, source: "rules" },
    { column: "Arkëtuar", field: "collected_lek", confidence: 0.4, reason: { sq: "", en: "" }, source: "user" },
  ];
  const dropped = new Set(["Emri"]);
  assert.equal(needsConfirmation(rows[0], dropped), true);
  assert.equal(needsConfirmation(rows[1], dropped), false);
  assert.equal(needsConfirmation(rows[2], dropped), false);
  assert.equal(needsConfirmation(rows[3], dropped), false);
  assert.deepEqual(pendingConfirmations(rows, new Set(), dropped), ["Muaji"]);
  assert.deepEqual(pendingConfirmations(rows, new Set(["Muaji"]), dropped), []);
});

test("coverage counting and receipt balance", () => {
  const { counts, total } = countCoverage([
    { state: "computable" },
    { state: "document" },
    { state: "national" },
    { state: "national" },
    { state: "missing" },
  ]);
  assert.equal(total, 5);
  assert.deepEqual(counts, { computable: 1, missing: 1, document: 1, national: 2, manual: 0 });
  const balance = receiptBalance({
    rows_read: 99,
    rows_loaded: 96,
    rows_excluded: [
      { reason: "title", count: 2, label: { sq: "", en: "" } },
      { reason: "total_row", count: 1, label: { sq: "", en: "" } },
    ],
  });
  assert.deepEqual(balance, { read: 99, loaded: 96, excluded: 3, balanced: true });
});

// ---------------------------------------------------------------- fixtures (REPLAY engine)
//
// REPLAY replays responses recorded from the live API (`scripts/record-replay.mjs`), so the
// expected numbers below are read from that recording, never typed by hand.

const ZARFI_1 = "zarfi-1_SINTETIKE_pastrimi_mbetjet_2026.csv";
const ZARFI_2 = "zarfi-2_SINTETIKE_taksat_tarifat_arketimi_2026.xlsx";
const ZARFI_3 = "zarfi-3_SINTETIKE_burimet_njerezore_2026.xlsx";
const REQUESTS = "01_SINTETIKE_kerkesat_qytetare_jan-gus_2026.xlsx";
const DRIFT = "drift_SINTETIKE_pastrimi_mbetjet_2026_v2.csv";

async function load(name, saveRecipe = true) {
  const preview = await replay.previewSample(name);
  const receipt = await replay.commitIngest({
    preview_id: preview.preview_id,
    dataset: preview.dataset.key,
    mapping: preview.mapping.map((m) => ({ column: m.column, field: m.field })),
    save_recipe: saveRecipe,
  });
  return { preview, receipt };
}

test("the recorded snapshot covers the contract: 13 passports, 4 example kinds, every sample", () => {
  assert.equal(Object.keys(SNAPSHOT.passports.full).length, 13);
  assert.ok(Object.values(SNAPSHOT.passports.full).every((p) => p.state === "computable" && p.value !== null));
  assert.ok(Object.values(SNAPSHOT.passports.full).every((p) => p.formula_status === "draft"));
  assert.deepEqual(Object.keys(SNAPSHOT.previews.fresh).sort(), SNAPSHOT.samples.map((s) => s.name).sort());
  assert.equal(new Set(SNAPSHOT.examples.map((e) => e.kind)).size, 4);
  assert.ok(SNAPSHOT.samples.every((s) => s.synthetic && /SINTETIKE/.test(s.name)));
});

test("start state: 6/13 computable, 3 gap groups, synthetic sources", async () => {
  replay.__resetReplayForTests();
  const board = await replay.getBoard("core_kpi");
  assert.equal(board.coverage.computable, 6);
  assert.equal(board.coverage.total, 13);
  assert.equal(board.indicators.length, 13);
  const gaps = new Set(board.indicators.flatMap((i) => i.missing.map((m) => m.dataset)));
  assert.deepEqual([...gaps].sort(), ["revenue", "staff", "waste"]);
  for (const i of board.indicators) {
    if (i.state === "computable") {
      assert.ok(i.value !== null, `${i.code} has a value`);
      assert.ok(i.sources.length > 0 && i.sources.every((s) => s.synthetic), `${i.code} sources are synthetic`);
      assert.equal(i.formula_status, "draft");
    } else {
      assert.equal(i.value, null, `${i.code} has no number while missing`);
      assert.ok(i.missing.length > 0);
      assert.ok(i.missing.every((m) => m.owner.sq && m.name.sq));
    }
  }
  const areas = groupIndicatorsByArea(board.indicators).map((g) => g.key);
  assert.deepEqual(areas, ["requests", "finance", "waste", "revenue", "hr"]);
  const lead = leadershipSummary(board);
  assert.equal(lead.owed.length, 3);
  const health = await replay.getHealth();
  assert.equal(health.mode, "rules");
  assert.equal(health.llm, false);
  assert.equal(health.synthetic, true);
});

test("REQ-02 passport and lineage replay the recorded API response", async () => {
  replay.__resetReplayForTests();
  const recorded = SNAPSHOT.passports.full["REQ-02"];
  const passport = await replay.getPassport("REQ-02");
  assert.equal(passport.value, recorded.value);
  assert.equal(passport.status, recorded.status);
  assert.ok(passport.sql.includes("FROM request"));
  assert.equal(passport.series.length, recorded.series.length);
  assert.equal(passport.lineage[0].filename, REQUESTS);
  const lineage = await replay.getLineage("REQ-02", 10);
  assert.equal(lineage.code, "REQ-02");
  assert.ok(lineage.rows.length > 0 && lineage.rows.length <= 10);
  assert.ok(lineage.columns.includes("closed_at"));
  assert.equal(lineage.total, SNAPSHOT.lineage["REQ-02"].total);
  const missing = await replay.getLineage("REV-01", 10);
  assert.deepEqual(missing.rows, []);
});

test("gap-to-proof loop: not answerable → ingest zarfi-2 → receipt reconciles → verified", async () => {
  replay.__resetReplayForTests();
  const gapExample = SNAPSHOT.examples.find((e) => e.kind === "gap" && e.passport_code === "REV-02");
  const before = await replay.ask({ question: gapExample.question.sq, locale: "sq", example_id: gapExample.id });
  assert.equal(before.label, "not_answerable");
  assert.equal(before.value, null);
  assert.equal(before.gap.dataset, "revenue");
  assert.equal(before.gap.owner.sq, "Drejtoria e të Ardhurave Vendore");
  assert.equal(before.question, gapExample.question.sq);

  const { preview, receipt } = await load(ZARFI_2);
  assert.equal(preview.unit_multiplier, 1000);
  assert.ok(preview.excluded_rows.some((r) => r.reason === "total_row" && r.text.startsWith("Gjithsej")));
  assert.equal(preview.columns.filter((c) => c.dropped).length, 0);
  assert.equal(preview.llm.used, false);
  assert.ok(preview.mapping.every((m) => m.confidence <= 0.6 && m.source === "rules"));
  assert.ok(preview.preview_id.startsWith("fx-"));

  assert.ok(receiptBalance(receipt).balanced);
  assert.ok(receipt.reconciliation.length > 0 && receipt.reconciliation.every((r) => r.ok));
  assert.deepEqual(receipt.indicators_unlocked.map((i) => i.code), ["REV-01", "REV-02"]);
  assert.deepEqual(receipt.coverage, { computable: 8, total: 13 });
  assert.equal(receipt.recipe.saved, true);

  const after = await replay.ask({ question: gapExample.question.sq, locale: "sq", example_id: gapExample.id });
  assert.equal(after.label, "verified");
  assert.equal(after.value, SNAPSHOT.passports.full["REV-02"].value);
  assert.ok(after.sources.some((s) => s.filename === ZARFI_2));

  const board = await replay.getBoard();
  assert.deepEqual(newlyComputable(stateSnapshot((await replay.getBoard()).indicators), board.indicators), []);
  const rev2 = board.indicators.find((i) => i.code === "REV-02");
  assert.equal(rev2.state, "computable");
  assert.equal(rev2.value, SNAPSHOT.passports.full["REV-02"].value);

  const again = await replay.previewSample(ZARFI_2);
  assert.equal(again.recipe.hit, true);
  assert.equal(again.recipe.recipe_id, receipt.recipe.recipe_id);
  assert.ok(again.mapping.every((m) => m.source === "recipe"));
  const reused = await replay.commitIngest({
    preview_id: again.preview_id,
    dataset: "revenue",
    mapping: again.mapping.map((m) => ({ column: m.column, field: m.field })),
  });
  assert.equal(reused.recipe.reused, true);
  assert.deepEqual(reused.indicators_unlocked, []);
});

test("REPLAY after zarfi-2 alone matches the API's recorded state, indicator by indicator", async () => {
  assert.ok(SNAPSHOT.mid, "the recording keeps the after-envelope-2 state");
  assert.equal(SNAPSHOT.mid.after, ZARFI_2);
  replay.__resetReplayForTests();
  await load(ZARFI_2);

  const shape = (i) => ({
    code: i.code,
    state: i.state,
    value: i.value,
    period: i.period,
    previous: i.previous,
    status: i.status,
    basis: i.basis,
    signals: i.signals,
    sparkline: i.sparkline,
    missing: i.missing,
    files: i.sources.map((s) => s.filename),
  });
  const board = await replay.getBoard();
  assert.deepEqual(board.indicators.map(shape), SNAPSHOT.mid.board.indicators.map(shape));
  assert.deepEqual(board.coverage, SNAPSHOT.mid.board.coverage);
  assert.equal(board.as_of, SNAPSHOT.mid.board.as_of);

  const detail = (p) => ({
    ...shape(p),
    sql: p.sql,
    series: p.series,
    checks: p.checks,
    lineage: p.lineage.map((l) => [l.filename, l.row_count, l.row_ranges]),
  });
  assert.deepEqual(Object.keys(SNAPSHOT.mid.passports).sort(), ["REV-01", "REV-02"]);
  for (const [code, recorded] of Object.entries(SNAPSHOT.mid.passports)) {
    assert.deepEqual(detail(await replay.getPassport(code)), detail(recorded), code);
  }

  const coverage = await replay.getCoverage();
  for (const item of SNAPSHOT.mid.coverage) {
    assert.deepEqual(coverage.items.find((i) => i.number === item.number), item, `SMP #${item.number}`);
  }

  for (const ex of SNAPSHOT.examples) {
    const got = await replay.ask({ question: ex.question.sq, locale: "sq", example_id: ex.id });
    const want = SNAPSHOT.mid.examples[ex.id];
    const key = (a) => [a.label, a.value, a.passport_code, a.answer, a.gap?.dataset ?? null];
    assert.deepEqual(key(got), key(want), ex.id);
  }
});

test("year-to-date values carry a month range; stocks carry the month", () => {
  const full = SNAPSHOT.passports.full;
  assert.match(full["REV-02"].period, /^\d{4}-01\/\d{4}-\d{2}$/);
  assert.match(full["REQ-03"].period, /^\d{4}-\d{2}$/);
  assert.match(full["HR-01"].period, /^\d{4}-\d{2}$/);
  assert.equal(formatPeriod(full["REV-02"].period, "sq", "short"), "jan – gush 2026");
  assert.equal(formatPeriod(full["REV-02"].period, "en"), "January – August 2026");
  assert.equal(full["REV-02"].sparkline.at(-1).period, full["REV-02"].period.split("/")[1]);
});

test("requests file drops 2 personal columns before profiling", async () => {
  replay.__resetReplayForTests();
  const preview = await replay.previewSample(REQUESTS);
  const dropped = preview.columns.filter((c) => c.dropped);
  assert.equal(dropped.length, 2);
  assert.deepEqual(dropped.map((c) => c.pii).sort(), ["name", "phone"]);
  assert.ok(dropped.every((c) => c.samples.length === 0));
});

test("format drift: a renamed column is reported against the saved recipe", async () => {
  replay.__resetReplayForTests();
  assert.equal((await replay.previewSample(DRIFT)).recipe.drift, null);
  await load(ZARFI_1);
  const drift = await replay.previewSample(DRIFT);
  assert.equal(drift.recipe.hit, false);
  assert.ok(drift.recipe.drift.renamed.length + drift.recipe.drift.added.length > 0);
});

test("commit refuses a mapping that leaves a required field empty", async () => {
  replay.__resetReplayForTests();
  const preview = await replay.previewSample(ZARFI_2);
  await assert.rejects(
    replay.commitIngest({
      preview_id: preview.preview_id,
      dataset: "revenue",
      mapping: preview.mapping.map((m) => ({ column: m.column, field: null })),
    }),
    (error) => error.status === 422 && error.code === "required_fields_unmapped",
  );
});

test("ask: examples cover all four labels; free text is routed, refused or declined", async () => {
  replay.__resetReplayForTests();
  const labels = new Set();
  for (const ex of await replay.getExamples()) {
    const a = await replay.ask({ question: ex.question.sq, locale: "sq", example_id: ex.id });
    labels.add(a.label);
    if (a.label === "blocked") assert.ok(a.blocked_reason);
    if (a.label === "exploratory") assert.ok(a.table && a.sql);
    if (a.label === "not_answerable" && ex.passport_code) assert.ok(a.gap?.owner.sq);
  }
  assert.deepEqual([...labels].sort(), ["blocked", "exploratory", "not_answerable", "verified"]);
  const weather = await replay.ask({ question: "Cili është moti nesër?", locale: "sq" });
  assert.equal(weather.label, "not_answerable");
  assert.equal(weather.gap, null);
  assert.equal(weather.question, "Cili është moti nesër?");
  const write = await replay.ask({ question: "DROP TABLE request", locale: "sq" });
  assert.equal(write.label, "blocked");
  assert.equal(write.sql, "DROP TABLE request");
  const personal = await replay.ask({ question: "Më jep telefonat e kërkuesve", locale: "sq" });
  assert.equal(personal.label, "blocked");
  const routed = await replay.ask({ question: "What is the average resolution time?", locale: "en" });
  assert.equal(routed.passport_code, "REQ-04");
  assert.equal(routed.label, "verified");
  const gap = await replay.ask({ question: "Sa është rotacioni i punonjësve?", locale: "sq" });
  assert.equal(gap.passport_code, "HR-02");
  assert.equal(gap.label, "not_answerable");
});

test("coverage: 52 Annex A items; mapped items wait for their exports at the start", async () => {
  replay.__resetReplayForTests();
  const coverage = await replay.getCoverage("al_smp");
  assert.equal(coverage.total, 52);
  assert.equal(coverage.items.length, 52);
  assert.deepEqual(coverage.counts, { computable: 0, missing: 23, document: 10, national: 12, manual: 7 });
  assert.equal(coverage.approval, "pending");
  assert.deepEqual(countCoverage(coverage.items).counts, coverage.counts);
  const rev2 = coverage.items.find((i) => i.number === 13);
  assert.equal(rev2.passport_code, "REV-02");
  assert.equal(rev2.state, "missing");
  assert.equal(rev2.owner.sq, "Drejtoria e të Ardhurave Vendore");
  assert.ok(rev2.note.sq.includes("REV-02"));
  assert.deepEqual(coverage.items[0].area, { sq: "Arsimi", en: "Education" });
});

test("coverage marks the mapped SMP items computable once every export is loaded", async () => {
  replay.__resetReplayForTests();
  for (const name of [ZARFI_1, ZARFI_2, ZARFI_3]) await load(name);
  const coverage = await replay.getCoverage("al_smp");
  assert.deepEqual(coverage.counts, { computable: 5, missing: 18, document: 10, national: 12, manual: 7 });
  const computable = coverage.items.filter((i) => i.state === "computable").map((i) => i.passport_code);
  assert.deepEqual(computable, ["REV-02", "WST-02", "WST-03", "HR-02", "HR-01"]);
  assert.ok(coverage.items.find((i) => i.number === 14).note.sq.endsWith("Baza e popullsisë: Censusi 2023."));
  assert.equal((await replay.getBoard()).coverage.computable, 13);
});

test("population basis switches per-capita values to the recorded civil-registry run; reset restores", async () => {
  replay.__resetReplayForTests();
  await load(ZARFI_3);
  const census = (await replay.getBoard()).indicators.find((i) => i.code === "HR-01");
  assert.equal(census.value, SNAPSHOT.passports.full["HR-01"].value);
  assert.equal(census.basis, "census_2023");
  const pin = await replay.setPopulationBasis("civil_registry", "test");
  assert.equal(pin.ok, true);
  assert.equal(pin.value, "civil_registry");
  assert.equal(pin.reason, "test");
  assert.deepEqual(pin.options, SNAPSHOT.basis_pin.civil_registry.options);
  assert.equal(pin.indicators.find((i) => i.code === "HR-01").value, SNAPSHOT.passports.civil_registry["HR-01"].value);
  assert.equal(pin.indicators.find((i) => i.code === "WST-02").value, null); // waste not loaded
  const registry = (await replay.getBoard()).indicators.find((i) => i.code === "HR-01");
  assert.equal(registry.value, SNAPSHOT.passports.civil_registry["HR-01"].value);
  assert.equal(registry.basis, "civil_registry");
  assert.notEqual(registry.value, census.value);
  const reset = await replay.resetDemo();
  assert.deepEqual(reset.coverage, { computable: 6, total: 13 });
  const calls = await replay.getLlmCalls();
  assert.equal(calls.mode, "rules");
  assert.equal(calls.calls.length, 0);
});

test("REPLAY CSV export keeps a Burimi column and names the missing exports", async () => {
  const { replayCsv } = await import("../src/lib/replay-export.ts");
  replay.__resetReplayForTests();
  const board = await replay.getBoard();
  const lines = replayCsv(board, "sq").split("\n");
  assert.equal(lines.length, 14);
  assert.ok(lines[0].split(",").includes("Burimi"));
  assert.ok(lines.find((l) => l.startsWith("REQ-01,")).includes("01_SINTETIKE_kerkesat"));
  assert.ok(lines.find((l) => l.startsWith("WST-01,")).includes("MUNGON"));
});

test("dates by month and long row-range lists are summarised for display", async () => {
  const { formatDate, summariseRanges } = await import("../src/lib/format.ts");
  assert.equal(formatDate("2026-08", "sq"), "31 gusht 2026");
  assert.equal(formatDate("2026-02", "en"), "28 February 2026");
  assert.equal(formatDate("2026-08-15", "sq"), "15 gusht 2026");
  const r = summariseRanges("4, 6–12, 14–287, 289–330, 332–359, 361–365");
  assert.equal(r.text, "4, 6–12, 14–287, 289–330");
  assert.equal(r.more, 2);
  assert.equal(r.all.length, 6);
  assert.deepEqual(summariseRanges("4–2403"), { text: "4–2403", more: 0, all: ["4–2403"] });
  assert.deepEqual(summariseRanges(null), { text: "", more: 0, all: [] });
});

test("result-table cells keep their precision in the locale's number format", async () => {
  const { formatCell } = await import("../src/lib/format.ts");
  assert.equal(formatCell(91.9, "sq"), "91,9");
  assert.equal(formatCell(2562.4, "sq"), "2.562,4");
  assert.equal(formatCell(2562.4, "en"), "2,562.4");
  assert.equal(formatCell(61, "en"), "61");
  assert.equal(formatCell("Drejtoria e Punëve Publike", "sq"), "Drejtoria e Punëve Publike");
  assert.equal(formatCell(null, "sq"), "–");
});
