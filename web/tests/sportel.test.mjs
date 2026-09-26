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
    }
  }
  const areas = groupIndicatorsByArea(board.indicators).map((g) => g.key);
  assert.deepEqual(areas, ["requests", "waste", "revenue", "hr", "finance"]);
  const lead = leadershipSummary(board);
  assert.equal(lead.owed.length, 3);
  assert.ok(lead.offTrack.some((o) => o.code === "FIN-02"));
  const health = await replay.getHealth();
  assert.equal(health.mode, "rules");
  assert.equal(health.llm, false);
  assert.equal(health.synthetic, true);
});

test("REQ-02 passport and lineage match the contract shapes", async () => {
  replay.__resetReplayForTests();
  const passport = await replay.getPassport("REQ-02");
  assert.equal(passport.code, "REQ-02");
  assert.equal(passport.value, 82.9);
  assert.equal(passport.status, "off_track");
  assert.ok(passport.sql.includes("FROM request"));
  assert.equal(passport.series.length, 8);
  assert.equal(passport.lineage[0].filename, "01_SINTETIKE_kerkesat_qytetare_jan-gus_2026.xlsx");
  assert.ok(passport.checks.some((c) => c.rule === "off_target" && !c.passed));
  const lineage = await replay.getLineage("REQ-02", 10);
  assert.equal(lineage.code, "REQ-02");
  assert.ok(lineage.rows.length > 0 && lineage.rows.length <= 10);
  assert.ok(lineage.columns.includes("closed_at"));
  assert.equal(lineage.total, 291);
});

test("gap-to-proof loop: not answerable → ingest zarfi-2 → receipt reconciles → verified", async () => {
  replay.__resetReplayForTests();
  const before = await replay.ask({ question: "", locale: "sq", example_id: "ex-gap-revenue" });
  assert.equal(before.label, "not_answerable");
  assert.equal(before.value, null);
  assert.equal(before.gap.dataset, "revenue");
  assert.equal(before.gap.owner.sq, "Drejtoria e të Ardhurave Vendore");

  const preview = await replay.previewSample("zarfi-2_SINTETIKE_taksat_tarifat_arketimi_2026.xlsx");
  assert.equal(preview.unit_multiplier, 1000);
  assert.equal(preview.header_row, 3);
  assert.ok(preview.excluded_rows.some((r) => r.reason === "total_row" && r.text === "Gjithsej"));
  assert.equal(preview.excluded_rows.filter((r) => r.reason === "title").length, 2);
  assert.equal(preview.columns.filter((c) => c.dropped).length, 0);
  assert.equal(preview.llm.used, false);
  assert.ok(preview.mapping.every((m) => m.confidence <= 0.6 && m.source === "rules"));
  assert.equal(preview.steps.length, 8);

  const receipt = await replay.commitIngest({
    preview_id: preview.preview_id,
    dataset: "revenue",
    mapping: preview.mapping.map((m) => ({ column: m.column, field: m.field })),
    save_recipe: true,
  });
  assert.ok(receiptBalance(receipt).balanced);
  assert.ok(receipt.reconciliation.every((r) => r.ok));
  assert.equal(receipt.reconciliation[0].file_total, receipt.reconciliation[0].loaded_sum);
  assert.deepEqual(receipt.indicators_unlocked.map((i) => i.code), ["REV-01", "REV-02"]);
  assert.deepEqual(receipt.coverage, { computable: 8, total: 13 });
  assert.equal(receipt.recipe.saved, true);

  const after = await replay.ask({ question: "", locale: "sq", example_id: "ex-gap-revenue" });
  assert.equal(after.label, "verified");
  assert.equal(after.value, 81.3);
  assert.ok(after.sources[0].filename.startsWith("zarfi-2"));

  const board = await replay.getBoard();
  assert.deepEqual(newlyComputable(stateSnapshot((await replay.getBoard()).indicators), board.indicators), []);
  assert.equal(board.indicators.find((i) => i.code === "REV-02").state, "computable");

  const again = await replay.previewSample("zarfi-2_SINTETIKE_taksat_tarifat_arketimi_2026.xlsx");
  assert.equal(again.recipe.hit, true);
  assert.ok(again.mapping.every((m) => m.confidence === 1 && m.source === "recipe"));
});

test("requests file drops 2 personal columns before profiling", async () => {
  replay.__resetReplayForTests();
  const preview = await replay.previewSample("01_SINTETIKE_kerkesat_qytetare_jan-gus_2026.xlsx");
  const dropped = preview.columns.filter((c) => c.dropped);
  assert.equal(dropped.length, 2);
  assert.deepEqual(dropped.map((c) => c.pii).sort(), ["name", "phone"]);
  assert.ok(dropped.every((c) => c.samples.length === 0));
  assert.ok(!preview.mapping.some((m) => dropped.some((d) => d.name === m.column)));
});

test("ask answers cover all four labels; coverage has 52 items", async () => {
  replay.__resetReplayForTests();
  const labels = new Set();
  for (const ex of await replay.getExamples()) {
    const a = await replay.ask({ question: ex.question.sq, locale: "sq", example_id: ex.id });
    labels.add(a.label);
    if (a.label === "blocked") assert.ok(a.blocked_reason);
    if (a.label === "exploratory") assert.ok(a.table && a.sql);
  }
  assert.deepEqual([...labels].sort(), ["blocked", "exploratory", "not_answerable", "verified"]);
  const free = await replay.ask({ question: "Cili është moti nesër?", locale: "sq" });
  assert.equal(free.label, "not_answerable");
  assert.equal(free.gap, null);

  const coverage = await replay.getCoverage("al_smp");
  assert.equal(coverage.total, 52);
  assert.equal(coverage.items.length, 52);
  assert.deepEqual(coverage.counts, { computable: 5, missing: 25, document: 10, national: 12, manual: 0 });
  assert.equal(coverage.approval, "pending");
  assert.deepEqual(countCoverage(coverage.items).counts, coverage.counts);
});

test("population basis changes per-capita values and reset restores the start state", async () => {
  replay.__resetReplayForTests();
  const p = await replay.previewSample("zarfi-3_SINTETIKE_burimet_njerezore_2026.xlsx");
  await replay.commitIngest({
    preview_id: p.preview_id,
    dataset: "staff",
    mapping: p.mapping.map((m) => ({ column: m.column, field: m.field })),
  });
  const census = (await replay.getBoard()).indicators.find((i) => i.code === "HR-01");
  assert.equal(census.value, 8.62);
  assert.equal(census.basis, "census_2023");
  await replay.setPopulationBasis("civil_registry");
  const registry = (await replay.getBoard()).indicators.find((i) => i.code === "HR-01");
  assert.equal(registry.value, 5.01);
  assert.equal(registry.basis, "civil_registry");
  const reset = await replay.resetDemo();
  assert.deepEqual(reset.coverage, { computable: 6, total: 13 });
  const calls = await replay.getLlmCalls();
  assert.equal(calls.mode, "rules");
  assert.equal(calls.calls.length, 0);
  const evaluation = await replay.getEval();
  assert.equal(evaluation.by_label.reduce((s, r) => s + r.total, 0), 24);
});
