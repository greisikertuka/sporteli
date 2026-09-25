import test from "node:test";
import assert from "node:assert/strict";
import { departments, getMetrics, getTrend } from "../src/lib/pulse-data.ts";
import { parseCsv, validateMapping } from "../src/lib/csv-preview.ts";

test("city metrics reconcile with department totals and weighted on-time rate", () => {
  const total = getMetrics("all", "september");
  const parts = departments.map((id) => getMetrics(id, "september"));
  assert.equal(total.received, 1248);
  assert.equal(total.resolved, 1136);
  assert.equal(total.overdue, 42);
  assert.equal(
    parts.reduce((sum, d) => sum + d.received, 0),
    total.received,
  );
  assert.equal(total.onTimeRate, (993 / 1136) * 100);
});
test("filters change the dataset consistently", () => {
  assert.equal(getMetrics("public", "september").overdue, 28);
  assert.equal(getMetrics("all", "august").received, 1182);
  const series = getTrend("public", "september");
  assert.equal(
    series.at(-1).received,
    getMetrics("public", "september").received,
  );
  assert.equal(getTrend("all", "august").at(-1).received, 1182);
});
test("CSV parses quoted delimiters, escaped quotes, BOM and CRLF", () => {
  const result = parseCsv(
    '\uFEFFid,name,status\r\n1,"Road, west",open\r\n2,"A ""quoted"" name",closed\r\n',
  );
  assert.deepEqual(result.headers, ["id", "name", "status"]);
  assert.equal(result.rows[0][1], "Road, west");
  assert.equal(result.rows[1][1], 'A "quoted" name');
  assert.equal(result.rows.length, 2);
});
test("CSV preserves multiline quoted cells and rejects ambiguous or malformed files", () => {
  assert.equal(
    parseCsv('id,note\n1,"line one\nline two"').rows[0][1],
    "line one\nline two",
  );
  for (const csv of [
    "",
    "id,status",
    "id,id\n1,2",
    'id,name\n1,"unclosed',
    "id,status\n1,open,extra",
  ]) {
    assert.throws(() => parseCsv(csv));
  }
});
test("mapping requires unique columns for all required fields", () => {
  assert.equal(validateMapping({ id: 0, department: 1, status: 2 }, 3), true);
  assert.equal(validateMapping({ id: 0, department: 0, status: 2 }, 3), false);
  assert.equal(validateMapping({ id: 0, department: 1, status: -1 }, 3), false);
  assert.equal(validateMapping({ id: 0, department: 1, status: 5 }, 3), false);
});

test("locale formatting is deterministic for Albanian across server and browser runtimes", async () => {
  const { numberFormatter, formatSourceDate, monthLabel } = await import(
    "../src/lib/pulse-data.ts"
  );
  assert.equal(numberFormatter("sq").format(1248), "1.248");
  assert.equal(numberFormatter("sq", 1).format(87.4), "87,4");
  assert.equal(numberFormatter("en").format(1248), "1,248");
  assert.equal(formatSourceDate("2026-09-18", "sq"), "18 sht");
  assert.equal(monthLabel(4, "en"), "Apr");
});

test("historical city trend reconciles with all departments in every month", () => {
  for (const period of ["august", "september"]) {
    const total = getTrend("all", period);
    total.forEach((point, index) => {
      for (const measure of ["received", "resolved"]) {
        assert.equal(
          departments.reduce(
            (sum, id) => sum + getTrend(id, period)[index][measure],
            0,
          ),
          point[measure],
        );
      }
    });
  }
});

test("CSV does not silently discard malformed empty-field records", () => {
  assert.throws(() => parseCsv("id,status\n,,,,\n1,open"));
  assert.deepEqual(parseCsv("id,status\n,\n1,open").rows, [
    ["", ""],
    ["1", "open"],
  ]);
});
test("CSV enforces byte, row, and column limits", () => {
  assert.throws(() => parseCsv("id,note\n1," + "x".repeat(1_000_000)), /size/);
  assert.throws(
    () =>
      parseCsv(
        "id,status\n" +
          Array.from({ length: 10001 }, (_, i) => `${i},open`).join("\n"),
      ),
    /size/,
  );
  assert.throws(
    () =>
      parseCsv(
        Array.from({ length: 51 }, (_, i) => `h${i}`).join(",") +
          "\n" +
          Array(51).fill("x").join(","),
      ),
    /size/,
  );
});
