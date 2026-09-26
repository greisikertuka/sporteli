/**
 * Locale-aware formatting for every number Sportel shows.
 *
 * Pure and dependency-free (type imports only) so it runs in the browser, on the
 * server and under `node --test`. Conventions are explicit instead of relying on
 * ICU data for "sq", which differs between runtimes and would break hydration.
 */
import type { L10n } from "./api";

export type Locale = "sq" | "en";

export const asLocale = (value: string | null | undefined): Locale => (value === "en" ? "en" : "sq");

/** Pick the string for the active locale from an API `L10n` object. */
export function pick(text: L10n | null | undefined, locale: string): string {
  if (!text) return "";
  return asLocale(locale) === "en" ? text.en || text.sq : text.sq || text.en;
}

/** Group thousands and set the decimal mark: sq `1.234,5`, en `1,234.5`. */
export function formatNumber(value: number, locale: string, digits = 0): string {
  if (!Number.isFinite(value)) return "–";
  const en = asLocale(locale) === "en";
  const negative = value < 0;
  const [integer, fraction] = Math.abs(value).toFixed(digits).split(".");
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, en ? "," : ".");
  const text = grouped + (fraction ? (en ? "." : ",") + fraction : "");
  // Avoid "-0" / "-0,0" after rounding.
  return negative && /[1-9]/.test(text) ? `−${text}` : text;
}

/** Decimal places used per indicator unit (contract §3 units). */
export function unitDigits(unit: string, value?: number | null): number {
  switch (unit) {
    case "count":
    case "lek_per_ton":
      return 0;
    case "percent":
    case "days":
    case "kg_per_resident":
      return 1;
    case "per_1000":
      return 2;
    default:
      return value != null && !Number.isInteger(value) ? 1 : 0;
  }
}

/** Units whose symbol attaches without a space. */
const TIGHT_UNITS = new Set(["percent"]);

export type FormattedValue = { number: string; unit: string; tight: boolean; text: string };

/**
 * Format an indicator value with its unit label. `unitLabel` comes from the API
 * (`IndicatorSummary.unit_label`) so the unit words stay bilingual server-side.
 */
export function formatIndicatorValue(
  value: number | null | undefined,
  unit: string,
  locale: string,
  unitLabel?: string,
  opts: { trimInteger?: boolean } = {},
): FormattedValue {
  const label = unit === "percent" ? "%" : (unitLabel ?? "");
  if (value == null || !Number.isFinite(value)) {
    return { number: "–", unit: label, tight: TIGHT_UNITS.has(unit), text: "–" };
  }
  const digits = opts.trimInteger && Number.isInteger(value) ? 0 : unitDigits(unit, value);
  const number = formatNumber(value, locale, digits);
  const tight = TIGHT_UNITS.has(unit);
  const text = label ? (tight ? `${number}${label}` : `${number} ${label}`) : number;
  return { number, unit: label, tight, text };
}

/** Targets are round policy numbers: "90%" rather than "90,0%". */
export function formatTarget(
  target: number | null | undefined,
  unit: string,
  locale: string,
  unitLabel?: string,
  direction?: string,
): string {
  if (target == null) return "–";
  const text = formatIndicatorValue(target, unit, locale, unitLabel, { trimInteger: true }).text;
  return direction === "lower_better" ? `≤ ${text}` : text;
}

/** A "nice" axis step (1, 2, 2.5, 5 × 10^n) for roughly four intervals over `range`. */
export function niceStep(range: number): number {
  const safe = Math.abs(range) || 1;
  const raw = safe / 4;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const n = raw / pow;
  const m = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return m * pow;
}

/** Axis bounds snapped to the nice step, never below zero for non-negative data. */
export function niceBounds(values: number[]): { min: number; max: number; step: number } {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const range = hi - lo || Math.abs(hi) * 0.2 || 1;
  const step = niceStep(range);
  let min = Math.floor((lo - range * 0.08) / step) * step;
  const max = Math.ceil((hi + range * 0.08) / step) * step;
  if (lo >= 0 && min < 0) min = 0;
  return { min: Number(min.toFixed(6)), max: Number(max.toFixed(6)), step };
}

/** Signed change between two values in the indicator's unit (no unit suffix). */
export function formatDelta(value: number | null, previous: number | null, unit: string, locale: string) {
  if (value == null || previous == null) return null;
  const diff = value - previous;
  const digits = unitDigits(unit, diff);
  const rounded = Number(diff.toFixed(digits));
  const sign = rounded > 0 ? "+" : rounded < 0 ? "−" : "±";
  return { diff: rounded, text: `${sign}${formatNumber(Math.abs(rounded), locale, digits)}` };
}

const MONTHS: Record<Locale, { short: string[]; long: string[] }> = {
  sq: {
    short: ["jan", "shk", "mar", "pri", "maj", "qer", "korr", "gush", "sht", "tet", "nën", "dhj"],
    long: [
      "janar",
      "shkurt",
      "mars",
      "prill",
      "maj",
      "qershor",
      "korrik",
      "gusht",
      "shtator",
      "tetor",
      "nëntor",
      "dhjetor",
    ],
  },
  en: {
    short: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    long: [
      "January",
      "February",
      "March",
      "April",
      "May",
      "June",
      "July",
      "August",
      "September",
      "October",
      "November",
      "December",
    ],
  },
};

export function monthLabel(month: number, locale: string, style: "short" | "long" = "short"): string {
  return MONTHS[asLocale(locale)][style][month - 1] ?? String(month);
}

function formatOnePeriod(part: string, locale: string, style: "short" | "long"): string {
  const trimmed = part.trim();
  const ym = /^(\d{4})-(\d{2})(?:-(\d{2}))?$/.exec(trimmed);
  if (ym) {
    const [, year, month, day] = ym;
    const m = monthLabel(Number(month), locale, style);
    return day && style === "long" ? `${Number(day)} ${m} ${year}` : `${m} ${year}`;
  }
  return trimmed;
}

/**
 * Human period label: `2026-08` → "gusht 2026" / "August 2026";
 * ranges (`2026-01/2026-08` or `2026-01..2026-08`) → "janar – gusht 2026".
 */
export function formatPeriod(period: string | null | undefined, locale: string, style: "short" | "long" = "long") {
  if (!period) return "";
  const parts = period.split(/\s*(?:\/|\.\.|–|—)\s*/).filter(Boolean);
  if (parts.length === 2) {
    const [a, b] = parts.map((p) => formatOnePeriod(p, locale, style));
    const yearA = a.slice(-4);
    const yearB = b.slice(-4);
    return yearA === yearB && /^\d{4}$/.test(yearA) ? `${a.slice(0, -5)} – ${b}` : `${a} – ${b}`;
  }
  return formatOnePeriod(period, locale, style);
}

/** Short month axis label for chart ticks: `2026-08` → "gush" / "Aug". */
export function periodTick(period: string, locale: string): string {
  const ym = /^(\d{4})-(\d{2})/.exec(period);
  return ym ? monthLabel(Number(ym[2]), locale, "short") : period;
}

export function formatUsd(value: number | null | undefined, locale: string): string {
  if (value == null || !Number.isFinite(value)) return "–";
  const digits = value !== 0 && Math.abs(value) < 0.1 ? 3 : 2;
  return `$${formatNumber(value, locale, digits)}`;
}

export function formatMs(ms: number | null | undefined, locale: string): string {
  if (ms == null || !Number.isFinite(ms)) return "–";
  if (ms < 1000) return `${formatNumber(ms, locale, 0)} ms`;
  return `${formatNumber(ms / 1000, locale, 1)} s`;
}

export function formatBytes(bytes: number | null | undefined, locale: string): string {
  if (bytes == null || !Number.isFinite(bytes)) return "–";
  if (bytes < 1024) return `${formatNumber(bytes, locale, 0)} B`;
  if (bytes < 1024 * 1024) return `${formatNumber(bytes / 1024, locale, 1)} KB`;
  return `${formatNumber(bytes / (1024 * 1024), locale, 1)} MB`;
}

export function formatLek(value: number | null | undefined, locale: string): string {
  if (value == null || !Number.isFinite(value)) return "–";
  return `${formatNumber(value, locale, 0)} ${asLocale(locale) === "en" ? "lek" : "lekë"}`;
}

/** `2026-09-26T00:42:11Z` → "26 sht 2026, 02:42" (viewer's local time). */
export function formatDateTime(iso: string | null | undefined, locale: string): string {
  if (!iso) return "–";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  const m = monthLabel(date.getMonth() + 1, locale, "short");
  return `${date.getDate()} ${m} ${date.getFullYear()}, ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function formatDate(iso: string | null | undefined, locale: string): string {
  if (!iso) return "–";
  const ymd = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!ymd) return iso;
  return `${Number(ymd[3])} ${monthLabel(Number(ymd[2]), locale, "long")} ${ymd[1]}`;
}

/** Percentage 0–100 → share of a bar, clamped. */
export const clampPct = (value: number) => Math.max(0, Math.min(100, value));
