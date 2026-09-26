/**
 * REPLAY-only export. The live API serves `/export/core_kpi.xlsx` (sheet "Treguesit" with a
 * visible "Burimi" column); offline, the same columns are written as a CSV in the browser
 * from the REPLAY board so the report can still be handed over. Headers stay in Albanian,
 * like the API workbook. The filename says REPLAY and SINTETIKE.
 */
import type { IndicatorBoard } from "./api";
import { pick } from "./format.ts";

/** Excel opens UTF-8 CSV correctly only with a byte-order mark. */
const BOM = String.fromCharCode(0xfeff);
const HEADER = ["Kodi", "Treguesi", "Vlera", "Njësia", "Periudha", "Gjendja", "Objektivi", "Burimi", "Versioni", "Baza"];

export function replayCsv(board: IndicatorBoard, locale: string): string {
  const rows = board.indicators.map((i) => [
    i.code,
    pick(i.name, locale),
    i.value == null ? "" : String(i.value),
    pick(i.unit_label, locale),
    i.period ?? "",
    i.state,
    i.target == null ? "" : String(i.target),
    i.state === "computable"
      ? i.sources.map((s) => s.filename).join(" | ")
      : `MUNGON: ${i.missing.map((m) => `${pick(m.name, locale)} (${pick(m.owner, locale)})`).join(" | ")}`,
    i.version,
    i.basis ?? "",
  ]);
  const cell = (v: string) => (/[",;\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  return [HEADER, ...rows].map((r) => r.map(cell).join(",")).join("\n");
}

export function downloadReplayCsv(board: IndicatorBoard, locale: string) {
  const blob = new Blob([BOM + replayCsv(board, locale)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `sportel-${board.pack}-REPLAY-SINTETIKE.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
