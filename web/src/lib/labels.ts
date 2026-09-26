/**
 * Pure presentation logic shared by the screens: copilot label metadata, mapping
 * confidence tiers, coverage counting, the leadership callout and receipt maths.
 * Type-only imports keep it runnable under `node --test`.
 */
import type {
  AskLabel,
  CoverageItem,
  IndicatorBoard,
  IndicatorState,
  IndicatorSummary,
  L10n,
  LoadReceipt,
  MappingSuggestion,
} from "./api";

// ---------------------------------------------------------------- copilot labels

export type Tone = "success" | "warning" | "danger" | "neutral" | "info";

/** Order used in the legend, eval chips and trust page. */
export const ASK_LABELS: readonly AskLabel[] = ["verified", "exploratory", "not_answerable", "blocked"];

/** Visual tone per label; the label itself is always decided by API code, never here. */
export const ASK_LABEL_TONE: Record<AskLabel, Tone> = {
  verified: "success",
  exploratory: "warning",
  blocked: "danger",
  not_answerable: "neutral",
};

// ---------------------------------------------------------------- mapping confidence

export const HIGH_CONFIDENCE = 0.8;

export type ConfidenceTier = "high" | "low";

export const confidenceTier = (confidence: number): ConfidenceTier =>
  confidence >= HIGH_CONFIDENCE ? "high" : "low";

/**
 * A mapping row needs an explicit human click when its confidence is amber and a
 * person has not already chosen it. Dropped personal columns never need a click.
 */
export function needsConfirmation(row: MappingSuggestion, droppedColumns: ReadonlySet<string> = new Set()) {
  if (droppedColumns.has(row.column)) return false;
  if (row.source === "user") return false;
  return confidenceTier(row.confidence) === "low";
}

/** Commit is allowed once every amber row is confirmed (by column name). */
export function pendingConfirmations(
  mapping: readonly MappingSuggestion[],
  confirmed: ReadonlySet<string>,
  droppedColumns: ReadonlySet<string> = new Set(),
): string[] {
  return mapping
    .filter((row) => needsConfirmation(row, droppedColumns) && !confirmed.has(row.column))
    .map((row) => row.column);
}

// ---------------------------------------------------------------- coverage

export function countCoverage(items: readonly Pick<CoverageItem, "state">[]) {
  const counts: Record<IndicatorState, number> = {
    computable: 0,
    missing: 0,
    document: 0,
    national: 0,
    manual: 0,
  };
  for (const item of items) counts[item.state] += 1;
  return { counts, total: items.length };
}

/** Group while preserving first-seen order of the keys. */
export function groupBy<T>(items: readonly T[], key: (item: T) => string): { key: string; items: T[] }[] {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const k = key(item);
    const list = groups.get(k);
    if (list) list.push(item);
    else groups.set(k, [item]);
  }
  return [...groups.entries()].map(([k, list]) => ({ key: k, items: list }));
}

/** Contract §3 order: the start state (requests + finance) fills the proof meter from the left. */
export const AREA_ORDER = ["requests", "finance", "waste", "revenue", "hr"];

export function groupIndicatorsByArea(indicators: readonly IndicatorSummary[]) {
  const groups = groupBy(indicators, (i) => i.area.key).map((g) => ({
    key: g.key,
    name: g.items[0].area.name,
    items: g.items,
  }));
  const rank = (k: string) => {
    const i = AREA_ORDER.indexOf(k);
    return i === -1 ? AREA_ORDER.length : i;
  };
  return groups.sort((a, b) => rank(a.key) - rank(b.key));
}

// ---------------------------------------------------------------- status

export function statusTone(status: IndicatorSummary["status"]): Tone {
  if (status === "on_track") return "success";
  if (status === "off_track") return "warning";
  return "neutral";
}

/** Codes that are computable now but were not in a previous snapshot. */
export function newlyComputable(
  previous: Record<string, IndicatorState> | null | undefined,
  indicators: readonly Pick<IndicatorSummary, "code" | "state">[],
): string[] {
  if (!previous) return [];
  return indicators
    .filter((i) => i.state === "computable" && previous[i.code] && previous[i.code] !== "computable")
    .map((i) => i.code);
}

export function stateSnapshot(indicators: readonly Pick<IndicatorSummary, "code" | "state">[]) {
  return Object.fromEntries(indicators.map((i) => [i.code, i.state])) as Record<string, IndicatorState>;
}

// ---------------------------------------------------------------- leadership callout

export type OwedData = {
  ownerKey: string;
  owner: L10n;
  datasets: { key: string; name: L10n }[];
  indicators: { code: string; name: L10n }[];
};

export type OffTrack = {
  code: string;
  name: L10n;
  value: number;
  target: number;
  unit: string;
  unit_label: L10n;
  direction: IndicatorSummary["direction"];
  gap: number;
};

/**
 * Derive the two leadership questions from the board, with neutral wording left to
 * the UI: which directorate owes an export this month (the one blocking the most
 * indicators first) and which indicators are off track (largest relative gap first).
 */
export function leadershipSummary(board: Pick<IndicatorBoard, "indicators">) {
  const owed = new Map<string, OwedData>();
  for (const indicator of board.indicators) {
    if (indicator.state !== "missing") continue;
    for (const gap of indicator.missing) {
      const ownerKey = gap.owner.sq;
      let entry = owed.get(ownerKey);
      if (!entry) {
        entry = { ownerKey, owner: gap.owner, datasets: [], indicators: [] };
        owed.set(ownerKey, entry);
      }
      if (!entry.datasets.some((d) => d.key === gap.dataset)) {
        entry.datasets.push({ key: gap.dataset, name: gap.name });
      }
      if (!entry.indicators.some((i) => i.code === indicator.code)) {
        entry.indicators.push({ code: indicator.code, name: indicator.name });
      }
    }
  }
  const owedList = [...owed.values()].sort((a, b) => b.indicators.length - a.indicators.length);

  const offTrack: OffTrack[] = board.indicators
    .filter(
      (i): i is IndicatorSummary & { value: number; target: number } =>
        i.state === "computable" && i.status === "off_track" && i.value != null && i.target != null,
    )
    .map((i) => ({
      code: i.code,
      name: i.name,
      value: i.value,
      target: i.target,
      unit: i.unit,
      unit_label: i.unit_label,
      direction: i.direction,
      gap: i.target !== 0 ? Math.abs(i.value - i.target) / Math.abs(i.target) : Math.abs(i.value),
    }))
    .sort((a, b) => b.gap - a.gap);

  return { owed: owedList, offTrack };
}

// ---------------------------------------------------------------- receipts

/** rows read = rows loaded + rows excluded; returns the parts and whether they balance. */
export function receiptBalance(receipt: Pick<LoadReceipt, "rows_read" | "rows_loaded" | "rows_excluded">) {
  const excluded = receipt.rows_excluded.reduce((sum, r) => sum + r.count, 0);
  return {
    read: receipt.rows_read,
    loaded: receipt.rows_loaded,
    excluded,
    balanced: receipt.rows_read === receipt.rows_loaded + excluded,
  };
}

export const reconciliationOk = (receipt: Pick<LoadReceipt, "reconciliation">) =>
  receipt.reconciliation.every((r) => r.ok);
