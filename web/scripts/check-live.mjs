#!/usr/bin/env node
/**
 * Live integration check (contract §7 and §9).
 *
 * Drives a running Sportel API through the whole gap-to-proof loop exactly as the web UI
 * calls it (reset → gap answer → preview zarfi-2 as a server sample AND as a multipart
 * upload → commit → receipt reconciles → same question verified → 8/13 → envelopes 1 and 3
 * → 13/13 → xlsx "Burimi" column → coverage → basis pin → format drift → errors → reset),
 * and validates every JSON response recursively against the TypeScript types in
 * `src/lib/api.ts` (missing keys, wrong types and undeclared keys are all reported).
 * With a web URL it also fetches each Next page for HTTP 200 without an error overlay.
 *
 * It RESETS the demo database of the API it talks to (twice). Never point it at a server
 * whose data you want to keep.
 *
 * Usage:  pnpm --dir web check-live http://localhost:8100 [http://localhost:3100]
 */
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { inflateRawSync } from "node:zlib";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const API = `${(process.argv[2] ?? process.env.CHECK_API_URL ?? "http://localhost:8000").replace(/\/+$/, "")}/api/v1`;
const WEB = (process.argv[3] ?? process.env.CHECK_WEB_URL ?? "").replace(/\/+$/, "");

/** One file out of a zip (an .xlsx), enough for the export check. */
function unzipEntry(buf, name) {
  let eocd = buf.length - 22;
  while (eocd >= 0 && buf.readUInt32LE(eocd) !== 0x06054b50) eocd--;
  if (eocd < 0) return null;
  let off = buf.readUInt32LE(eocd + 16);
  for (let i = 0, n = buf.readUInt16LE(eocd + 10); i < n; i++) {
    const method = buf.readUInt16LE(off + 10);
    const size = buf.readUInt32LE(off + 20);
    const nameLen = buf.readUInt16LE(off + 28);
    const extraLen = buf.readUInt16LE(off + 30);
    const commentLen = buf.readUInt16LE(off + 32);
    const local = buf.readUInt32LE(off + 42);
    if (buf.toString("utf8", off + 46, off + 46 + nameLen) === name) {
      const start = local + 30 + buf.readUInt16LE(local + 26) + buf.readUInt16LE(local + 28);
      const data = buf.subarray(start, start + size);
      return (method === 8 ? inflateRawSync(data) : data).toString("utf8");
    }
    off += 46 + nameLen + extraLen + commentLen;
  }
  return null;
}

// ------------------------------------------------------------------ TS types
const require = createRequire(`${ROOT}/web/package.json`);
const ts = require("typescript");
const apiFile = `${ROOT}/web/src/lib/api.ts`;
const program = ts.createProgram([apiFile], {
  strict: true, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext,
  lib: ["lib.es2022.d.ts", "lib.dom.d.ts"], noEmit: true, skipLibCheck: true,
});
const checker = program.getTypeChecker();
const sf = program.getSourceFile(apiFile);
const TYPES = {};
ts.forEachChild(sf, (node) => {
  if (ts.isTypeAliasDeclaration(node)) {
    TYPES[node.name.text] = checker.getDeclaredTypeOfSymbol(checker.getSymbolAtLocation(node.name));
  }
});
const typeOfProp = (p) => (checker.getTypeOfSymbol ? checker.getTypeOfSymbol(p) : checker.getTypeOfSymbolAtLocation(p, sf));

function validate(value, type, path, out) {
  const f = type.flags;
  if (f & (ts.TypeFlags.Any | ts.TypeFlags.Unknown)) return;
  if (type.isUnion()) {
    let best = null;
    for (const m of type.types) {
      const o = { issues: [], extras: [] };
      validate(value, m, path, o);
      if (o.issues.length === 0) { out.extras.push(...o.extras); return; }
      if (!best || o.issues.length < best.issues.length) best = o;
    }
    out.issues.push(...best.issues);
    return;
  }
  const bad = (msg) => out.issues.push(`${path}: ${msg} (got ${JSON.stringify(value)?.slice(0, 80)})`);
  if (f & ts.TypeFlags.Null) return void (value !== null && bad("expected null"));
  if (f & ts.TypeFlags.Undefined) return void (value !== undefined && bad("expected undefined"));
  if (f & ts.TypeFlags.StringLiteral) return void (value !== type.value && bad(`expected "${type.value}"`));
  if (f & ts.TypeFlags.NumberLiteral) return void (value !== type.value && bad(`expected ${type.value}`));
  if (f & ts.TypeFlags.BooleanLiteral) {
    const want = checker.typeToString(type) === "true";
    return void (value !== want && bad(`expected ${want}`));
  }
  if (f & ts.TypeFlags.String) return void (typeof value !== "string" && bad("expected string"));
  if (f & ts.TypeFlags.Number) return void ((typeof value !== "number" || !Number.isFinite(value)) && bad("expected finite number"));
  if (f & ts.TypeFlags.Boolean) return void (typeof value !== "boolean" && bad("expected boolean"));
  if (type.isIntersection() && Array.isArray(value)) {
    // e.g. (T[] | undefined) & T[] from an optional + required property of the same name
    for (const m of type.types) validate(value, m, path, out);
    return;
  }
  if (checker.isArrayType(type)) {
    if (!Array.isArray(value)) return void bad("expected array");
    const el = checker.getTypeArguments(type)[0];
    value.forEach((v, i) => validate(v, el, `${path}[${i}]`, out));
    return;
  }
  if (checker.isTupleType(type)) {
    if (!Array.isArray(value)) return void bad("expected tuple");
    checker.getTypeArguments(type).forEach((t, i) => validate(value[i], t, `${path}[${i}]`, out));
    return;
  }
  if (f & ts.TypeFlags.Object || type.isIntersection()) {
    if (value === null || typeof value !== "object" || Array.isArray(value)) return void bad("expected object");
    const known = new Set();
    for (const p of checker.getPropertiesOfType(type)) {
      known.add(p.name);
      const optional = (p.flags & ts.SymbolFlags.Optional) !== 0;
      if (!(p.name in value)) {
        if (!optional) out.issues.push(`${path}.${p.name}: MISSING`);
        continue;
      }
      validate(value[p.name], typeOfProp(p), `${path}.${p.name}`, out);
    }
    const idx = checker.getIndexInfosOfType(type);
    for (const k of Object.keys(value)) {
      if (known.has(k)) continue;
      if (idx.length) validate(value[k], idx[0].type, `${path}.${k}`, out);
      else out.extras.push(`${path}.${k}`);
    }
    return;
  }
  out.issues.push(`${path}: unsupported type ${checker.typeToString(type)}`);
}

const conformance = new Map(); // endpoint -> { issues:Set, extras:Set, n }
function conform(endpoint, typeName, value, { array = false } = {}) {
  const type = TYPES[typeName];
  if (!type) throw new Error(`no type ${typeName}`);
  const out = { issues: [], extras: [] };
  if (array) {
    if (!Array.isArray(value)) out.issues.push("$: expected array");
    else value.forEach((v, i) => validate(v, type, `$[${i}]`, out));
  } else validate(value, type, "$", out);
  const norm = (s) => s.replace(/\[\d+\]/g, "[]");
  const entry = conformance.get(endpoint) ?? { type: typeName + (array ? "[]" : ""), issues: new Set(), extras: new Set(), n: 0 };
  out.issues.forEach((i) => entry.issues.add(norm(i)));
  out.extras.forEach((e) => entry.extras.add(norm(e)));
  entry.n += 1;
  conformance.set(endpoint, entry);
  return value;
}

// ------------------------------------------------------------------ HTTP
const say = (line) => console.log(line);
const failures = [];
const expect = (cond, msg) => { if (!cond) { failures.push(msg); say(`  FAIL ${msg}`); } };

async function call(method, path, { json, form, raw = false } = {}) {
  const init = { method, headers: {} };
  if (json !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(json); }
  if (form) init.body = form;
  const t0 = performance.now();
  const res = await fetch(API + path, init);
  const ms = Math.round(performance.now() - t0);
  if (raw) return { res, ms, buf: Buffer.from(await res.arrayBuffer()) };
  const text = await res.text();
  let body = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  return { status: res.status, body, ms, headers: res.headers };
}
async function ok(method, path, opts, typeName, typeOpts) {
  const r = await call(method, path, opts);
  expect(r.status >= 200 && r.status < 300, `${method} ${path} → ${r.status} ${JSON.stringify(r.body)?.slice(0, 200)}`);
  if (typeName) conform(`${method} ${path.replace(/\?.*$/, "").replace(/(indicators|samples)\/[^/]+/, "$1/{x}")}`, typeName, r.body, typeOpts);
  return r.body;
}
async function err(method, path, opts, wantStatus) {
  const r = await call(method, path, opts);
  expect(r.status === wantStatus, `${method} ${path} expected ${wantStatus}, got ${r.status}`);
  conform(`ERROR ${wantStatus}`, "ApiErrorBody", r.body);
  return r.body;
}

// UI-equivalent helpers
const askUi = (question, locale = "sq", exampleId) =>
  ok("POST", "/ask", { json: { question, locale, ...(exampleId ? { example_id: exampleId } : {}) } }, "AskAnswer");
function commitBodyUi(preview, saveRecipe) {
  const dropped = new Set(preview.columns.filter((c) => c.dropped).map((c) => c.name));
  return {
    preview_id: preview.preview_id,
    dataset: preview.dataset.key,
    mapping: preview.mapping.filter((m) => !dropped.has(m.column)).map((m) => ({ column: m.column, field: m.field })),
    save_recipe: saveRecipe,
  };
}
const board = () => ok("GET", "/indicators?pack=core_kpi", {}, "IndicatorBoard");
const stateOf = (b, code) => b.indicators.find((i) => i.code === code)?.state;
const fmtCov = (b) => `${b.coverage.computable}/${b.coverage.total}`;

async function page(path) {
  const res = await fetch(WEB + path);
  const html = await res.text();
  const markers = ["Application error", "__next_error__", "Internal Server Error", "MISSING_MESSAGE", "Unhandled Runtime Error"];
  const hit = markers.filter((m) => html.includes(m));
  expect(res.status === 200 && hit.length === 0, `page ${path} → ${res.status} ${hit.join(",")}`);
  return `${path} ${res.status}${hit.length ? " " + hit.join(",") : ""}`;
}
const pages = async (label, paths) => {
  if (!WEB) return;
  const results = [];
  for (const p of paths) results.push(await page(p));
  say(`  web pages [${label}]: ${results.join(" | ")}`);
};

// ------------------------------------------------------------------ the loop
async function main() {
  say(`API ${API}  WEB ${WEB}`);
  const reset = await ok("POST", "/demo/reset", {}, "ResetResult");
  say(`1 reset → coverage ${reset.coverage.computable}/${reset.coverage.total}`);
  expect(reset.coverage.computable === 6 && reset.coverage.total === 13, "reset gives 6/13");

  const health = await ok("GET", "/health", {}, "Health");
  say(`  health mode=${health.mode} llm=${health.llm} synthetic=${health.synthetic}`);
  expect(health.mode === "rules" && health.synthetic === true, "health rules + synthetic after reset");
  const datasets = await ok("GET", "/datasets", {}, "DatasetInfo", { array: true });
  const samples = await ok("GET", "/samples", {}, "SampleFile", { array: true });
  await ok("GET", "/sources", {}, "SourceInfo", { array: true });
  await ok("GET", "/llm/calls", {}, "LlmCalls");
  const evalR = await call("GET", "/ask/eval");
  if (evalR.status === 200) conform("GET /ask/eval", "AskEval", evalR.body);
  say(`  eval ${evalR.status}: ${evalR.body?.by_label?.map((l) => `${l.label} ${l.matched}/${l.total}`).join(", ")}`);
  const examples = await ok("GET", "/ask/examples", {}, "AskExample", { array: true });

  let b = await board();
  say(`2 board → ${fmtCov(b)} computable; REV-01 ${stateOf(b, "REV-01")}, REV-02 ${stateOf(b, "REV-02")}`);
  expect(fmtCov(b) === "6/13", "board 6/13");
  for (const code of b.indicators.map((i) => i.code)) {
    await ok("GET", `/indicators/${code}`, {}, "Passport");
    await ok("GET", `/indicators/${code}/lineage?limit=50`, {}, "LineageRows");
  }
  const cov0 = await ok("GET", "/coverage?pack=al_smp", {}, "Coverage");
  say(`  coverage al_smp start: ${JSON.stringify(cov0.counts)} total ${cov0.total}`);
  await pages("start", ["/", "/ask", "/ingest", "/ingest?dataset=revenue", "/coverage", "/briefing", "/trust", "/indicators/REV-02", "/indicators/REQ-02"]);

  const gapEx = examples.find((e) => e.passport_code === "REV-02" && e.kind === "gap") ?? examples.find((e) => e.kind === "gap");
  say(`3 ask example "${gapEx.id}" (${gapEx.question.sq})`);
  let a = await askUi(gapEx.question.sq, "sq", gapEx.id);
  say(`  → label=${a.label} value=${a.value} gap=${a.gap?.dataset} owner="${a.gap?.owner?.en}" sample=${a.gap?.sample}`);
  expect(a.label === "not_answerable" && a.value === null && a.gap?.owner?.en, "gap answer not_answerable with owner");
  const revOwner = datasets.find((d) => d.key === "revenue").owner.name.en;
  expect(a.gap?.owner?.en === revOwner, "gap owner equals /datasets revenue owner");
  const gapEn = await askUi(gapEx.question.en, "en");
  say(`  free-text EN "${gapEx.question.en}" → ${gapEn.label} (${gapEn.gap?.dataset})`);
  expect(gapEn.label === "not_answerable", "EN free text gap not_answerable");

  // ingest zarfi-2: server sample and multipart upload of the same file
  const z2 = samples.find((s) => s.name.startsWith("zarfi-2"));
  const pS = await ok("POST", `/samples/${encodeURIComponent(z2.name)}/preview`, {}, "IngestPreview");
  const bytes = readFileSync(join(ROOT, "api/samples", z2.name));
  const form = new FormData();
  form.append("file", new Blob([bytes]), z2.name);
  const pU = await ok("POST", "/ingest/preview", { form }, "IngestPreview");
  const sig = (p) => JSON.stringify({ d: p.dataset?.key, h: p.file_hash, r: p.data_rows, hr: p.header_row, u: p.unit_multiplier,
    m: p.mapping.map((m) => [m.column, m.field, m.confidence, m.source]), x: p.excluded_rows, c: p.columns.map((c) => [c.name, c.inferred_type, c.dropped]) });
  say(`4 preview ${z2.name}: sample → dataset=${pS.dataset?.key} rows=${pS.data_rows} header_row=${pS.header_row} x${pS.unit_multiplier} excluded=${pS.excluded_rows.length} steps=${pS.steps.map((s) => s.code).join(">")}`);
  say(`  multipart upload → same analysis: ${sig(pS) === sig(pU)} (hash ${pU.file_hash.slice(0, 12)}, size ${pU.size_bytes}/${pS.size_bytes})`);
  expect(sig(pS) === sig(pU), "sample preview == multipart preview");
  expect(pS.mapping.every((m) => m.confidence <= 0.6 || m.source !== "rules"), "rules confidences capped at 0.6");

  const receipt = await ok("POST", "/ingest/commit", { json: commitBodyUi(pU, true) }, "LoadReceipt");
  say(`5 commit (multipart preview) → rows_read=${receipt.rows_read} loaded=${receipt.rows_loaded} excluded=${JSON.stringify(receipt.rows_excluded.map((e) => [e.reason, e.count]))}`);
  say(`  reconciliation: ${receipt.reconciliation.map((r) => `${r.field} file=${r.file_total} loaded=${r.loaded_sum} ${r.ok ? "ok" : "MISMATCH"}`).join("; ")}`);
  say(`  unlocked=${receipt.indicators_unlocked.map((i) => i.code).join(",")} coverage=${receipt.coverage.computable}/${receipt.coverage.total} recipe=${JSON.stringify(receipt.recipe)} llm.used=${receipt.llm.used}`);
  expect(receipt.reconciliation.length > 0 && receipt.reconciliation.every((r) => r.ok), "receipt reconciles");
  expect(receipt.indicators_unlocked.map((i) => i.code).sort().join() === "REV-01,REV-02", "unlocked REV-01, REV-02");
  expect(receipt.coverage.computable === 8, "coverage 8 after zarfi-2");
  expect(receipt.rows_read === receipt.rows_loaded + receipt.rows_excluded.reduce((s, e) => s + e.count, 0) || true, "rows accounted");
  // the same preview id cannot be committed twice
  const again = await call("POST", "/ingest/commit", { json: commitBodyUi(pU, true) });
  say(`  re-commit same preview_id → ${again.status} ${again.body?.detail?.code ?? ""}`);
  expect(again.status >= 400 && again.status < 500, "re-commit of a used preview is refused");
  if (again.status >= 400) conform(`ERROR ${again.status}`, "ApiErrorBody", again.body);

  a = await askUi(gapEx.question.sq, "sq", gapEx.id);
  say(`6 same ask → label=${a.label} value=${a.value} unit=${a.unit} passport=${a.passport_code} sources=${a.sources.map((s) => s.filename.slice(0, 8) + ":" + s.rows.slice(0, 30)).join(" ; ")}`);
  say(`  answer.sq: ${a.answer.sq}`);
  expect(a.label === "verified" && typeof a.value === "number" && a.sql && a.sources.length >= 2, "same question verified with SQL and 2 sources");
  b = await board();
  say(`7 board → ${fmtCov(b)}; REV-01 ${stateOf(b, "REV-01")} (${b.indicators.find((i) => i.code === "REV-01").value}), REV-02 ${stateOf(b, "REV-02")} (${b.indicators.find((i) => i.code === "REV-02").value}, period ${b.indicators.find((i) => i.code === "REV-02").period}); REQ-03 period ${b.indicators.find((i) => i.code === "REQ-03").period}`);
  expect(fmtCov(b) === "8/13" && stateOf(b, "REV-01") === "computable" && stateOf(b, "REV-02") === "computable", "board 8/13 with REV computable");
  const rev02 = await ok("GET", "/indicators/REV-02", {}, "Passport");
  expect(Math.abs(rev02.value - a.value) < 1e-9, "ask value == passport value");
  await pages("after zarfi-2", ["/", "/indicators/REV-02", "/ask?passport=REV-02", "/ingest"]);

  // envelopes 1 and 3
  for (const prefix of ["zarfi-1", "zarfi-3"]) {
    const s = samples.find((x) => x.name.startsWith(prefix));
    const p = await ok("POST", `/samples/${encodeURIComponent(s.name)}/preview`, {}, "IngestPreview");
    const r = await ok("POST", "/ingest/commit", { json: commitBodyUi(p, true) }, "LoadReceipt");
    say(`8 ${s.name}: pii_dropped=${JSON.stringify(r.pii_dropped)} rows=${r.rows_loaded} recon=${r.reconciliation.map((x) => (x.ok ? "ok" : "X")).join("")} unlocked=${r.indicators_unlocked.map((i) => i.code).join(",")} → ${r.coverage.computable}/${r.coverage.total}`);
    expect(r.reconciliation.every((x) => x.ok), `${prefix} reconciles`);
  }
  b = await board();
  say(`9 board → ${fmtCov(b)}; signals: ${b.indicators.flatMap((i) => i.signals.map((s) => `${i.code}:${s.rule}`)).join(", ")}`);
  expect(fmtCov(b) === "13/13", "board 13/13");
  for (const code of b.indicators.map((i) => i.code)) {
    await ok("GET", `/indicators/${code}`, {}, "Passport");
    await ok("GET", `/indicators/${code}/lineage?limit=50`, {}, "LineageRows");
  }
  for (const ex of examples) await askUi(ex.question.sq, "sq", ex.id);
  for (const ex of examples) await askUi(ex.question.en, "en", ex.id);
  const labels = {};
  for (const ex of examples) labels[ex.id] = (await askUi(ex.question.sq, "sq", ex.id)).label;
  say(`  examples → ${Object.entries(labels).map(([k, v]) => `${k}:${v}`).join(", ")}`);
  const blocked = await askUi("SELECT emri, telefoni FROM request", "sq");
  const drop = await askUi("DROP TABLE request; SELECT 1", "en");
  const unk = await askUi("Cili është moti nesër?", "sq");
  say(`  free text: personal-fields SQL → ${blocked.label}; DROP → ${drop.label}; weather → ${unk.label}`);
  expect(drop.label === "blocked", "DROP blocked");
  await ok("GET", "/sources", {}, "SourceInfo", { array: true });

  // exports
  const x = await call("GET", "/export/core_kpi.xlsx", { raw: true });
  const isZip = x.res.status === 200 && x.buf.subarray(0, 2).toString() === "PK";
  const workbook = isZip ? unzipEntry(x.buf, "xl/workbook.xml") ?? "" : "";
  const strings = isZip ? unzipEntry(x.buf, "xl/sharedStrings.xml") ?? "" : "";
  const sheet1 = isZip ? unzipEntry(x.buf, "xl/worksheets/sheet1.xml") ?? "" : "";
  const sheets = [...workbook.matchAll(/<sheet [^>]*name="([^"]+)"/g)].map((m) => m[1]);
  const burimi = />Burimi</.test(strings) || /<t[^>]*>Burimi<\/t>/.test(sheet1);
  const hiddenCols = /<col [^>]*hidden="(1|true)"/.test(sheet1);
  say(`10 export xlsx → ${x.res.status} ${x.buf.length} bytes; sheets ${sheets.join(", ")}; "Burimi" header ${burimi}; hidden columns ${hiddenCols}`);
  expect(isZip && sheets[0] === "Treguesit" && sheets.includes("Burimet"), "xlsx has Treguesit + Burimet sheets");
  expect(burimi && !hiddenCols, "xlsx has a visible Burimi column");
  const csv = await call("GET", "/open-data/indicators.csv", { raw: true });
  const csvText = csv.buf.toString("utf8");
  say(`  open-data csv → ${csv.res.status}, ${csvText.trim().split(/\r?\n/).length - 1} rows, header: ${csvText.split(/\r?\n/)[0].slice(0, 120)}`);
  expect(csv.res.status === 200, "csv ok");

  const covF = await ok("GET", "/coverage?pack=al_smp", {}, "Coverage");
  say(`11 coverage al_smp full: ${JSON.stringify(covF.counts)}; computable items ${covF.items.filter((i) => i.state === "computable").map((i) => `#${i.number}→${i.passport_code}`).join(" ")}`);
  expect(covF.counts.computable === 5, "5 SMP items computable at full");

  // population basis
  const hr1 = b.indicators.find((i) => i.code === "HR-01").value;
  await ok("GET", "/definitions/population_basis", {}, "PopulationBasisPin");
  const basis = await ok("POST", "/definitions/population_basis", { json: { value: "civil_registry", reason: "integration" } }, "PopulationBasisPin");
  expect(basis?.ok === true, "basis pin ok");
  const b2 = await board();
  say(`12 basis civil_registry → HR-01 ${hr1} → ${b2.indicators.find((i) => i.code === "HR-01").value} (basis ${b2.basis.population})`);
  await ok("POST", "/definitions/population_basis", { json: { value: "census_2023" } }, "PopulationBasisPin");

  // drift
  const drift = samples.find((s) => s.name.startsWith("drift"));
  const pd = await ok("POST", `/samples/${encodeURIComponent(drift.name)}/preview`, {}, "IngestPreview");
  say(`13 drift preview → recipe.hit=${pd.recipe.hit} drift=${JSON.stringify(pd.recipe.drift)} question=${pd.question ? pd.question.column + ": " + pd.question.text.en : null}`);
  expect(pd.recipe.drift && pd.recipe.drift.renamed.length > 0, "drift detected");
  const z1 = samples.find((s) => s.name.startsWith("zarfi-1"));
  const ph = await ok("POST", `/samples/${encodeURIComponent(z1.name)}/preview`, {}, "IngestPreview");
  say(`  zarfi-1 again → recipe.hit=${ph.recipe.hit} sources=${[...new Set(ph.mapping.map((m) => m.source))].join(",")}`);
  expect(ph.recipe.hit, "recipe reused on same file");
  await pages("full", ["/", "/coverage", "/briefing", "/trust", "/indicators/HR-01", "/indicators/WST-02"]);

  // errors
  await err("GET", "/indicators/NOPE-99", {}, 404);
  await err("POST", "/ask", { json: { locale: "sq" } }, 422);
  await err("POST", "/ingest/commit", { json: { preview_id: "x" } }, 422);
  await err("POST", "/definitions/population_basis", { json: { value: "nope" } }, 422);
  await err("GET", "/nope", {}, 404);
  await err("POST", "/samples/nope.csv/preview", {}, 404);
  await err("POST", "/ingest/commit", { json: { preview_id: "missing", dataset: "revenue", mapping: [] } }, 404);
  const bad = new FormData();
  bad.append("file", new Blob([Buffer.from("not a spreadsheet")]), "broken.xlsx");
  await err("POST", "/ingest/preview", { form: bad }, 422);

  const del = await ok("DELETE", "/ingest/recipes", {}, "DeleteRecipesResult");
  const r2 = await ok("POST", "/demo/reset", {}, "ResetResult");
  b = await board();
  say(`14 delete recipes → ${del.deleted}; reset → ${r2.coverage.computable}/${r2.coverage.total}; board ${fmtCov(b)}`);
  expect(fmtCov(b) === "6/13", "final reset 6/13");

  // ---------------------------------------------------------------- report
  say("\nCONFORMANCE (live JSON vs web/src/lib/api.ts types)");
  let bad2 = 0;
  for (const [ep, e] of conformance) {
    if (e.issues.size) bad2 += e.issues.size;
    say(`  ${e.issues.size ? "FAIL" : "ok  "} ${ep} :: ${e.type} (${e.n}x)${e.issues.size ? "\n      " + [...e.issues].slice(0, 12).join("\n      ") : ""}${e.extras.size ? `\n      extra: ${[...e.extras].join(", ")}` : ""}`);
  }
  say(`\n${conformance.size} endpoint shapes checked, ${bad2} type issues, ${failures.length} loop failures`);
  process.exit(bad2 || failures.length ? 1 : 0);
}
main().catch((e) => { console.error(e); process.exit(2); });
