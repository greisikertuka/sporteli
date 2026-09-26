/**
 * REPLAY fixtures: the 13 core_kpi passports (contract §3) over SYNTHETIC data.
 * Values are computed here by code from base series, so per-capita passports follow
 * the pinned population basis and gap tiles turn computable when an envelope loads.
 */
import type {
  IndicatorBoard,
  IndicatorSummary,
  L10n,
  LineageRows,
  Owner,
  Passport,
  PopulationBasis,
  Signal,
} from "../api";
import { formatIndicatorValue, formatNumber, formatPeriod, formatTarget } from "../format.ts";
import { AREAS, DATASETS, OWNERS, POPULATION, SAMPLES, type DatasetKey } from "./catalog.ts";
import { datasetRows } from "./rows.ts";
import type { ReplayState } from "./state.ts";

export const MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"];
export const AS_OF = "2026-08-31";
const COMPUTED_AT = "2026-09-26T00:42:11Z";

type Series = { period: string; value: number | null }[];
type Direction = IndicatorSummary["direction"];
type PeriodKind = "month" | "ytd" | "snapshot";

export type IndicatorDef = {
  code: string;
  area: string;
  name: L10n;
  question: L10n;
  keywords: string[];
  formula: L10n;
  unit: string;
  unit_label: L10n;
  direction: Direction;
  target: number | null;
  datasets: DatasetKey[];
  owner: Owner;
  smp_ref: string | null;
  periodKind: PeriodKind;
  series: (basis: PopulationBasis) => Series;
  sql: string;
  answer: L10n;
  checks: string[];
  lineage: { dataset: DatasetKey; row_count: number; row_ranges: string }[];
  /** Extra, data-specific signals (e.g. one unit's placeholder value). */
  extraSignals?: Signal[];
};

const monthly = (values: number[]): Series => values.map((value, i) => ({ period: MONTHS[i], value }));
const snapshot = (value: number): Series => [{ period: "2026-08", value }];

const WASTE_TONNES = [3480, 3215, 3590, 3655, 3820, 3905, 3760, 3712];
const HEADCOUNT = 1046;
const HIRES = 71;
const LEAVERS = 58;

const round = (v: number, digits: number) => Number(v.toFixed(digits));

const U = {
  requests: { sq: "kërkesa", en: "requests" },
  percent: { sq: "%", en: "%" },
  days: { sq: "ditë", en: "days" },
  tonnes: { sq: "ton", en: "tonnes" },
  kg: { sq: "kg/banor/vit", en: "kg/resident/yr" },
  lekTon: { sq: "lekë/ton", en: "lek/tonne" },
  per1000: { sq: "punonjës për 1.000 banorë", en: "staff per 1,000 residents" },
};

export const INDICATORS: IndicatorDef[] = [
  {
    code: "REQ-01",
    area: "requests",
    name: { sq: "Kërkesa të pranuara", en: "Requests received" },
    question: { sq: "Sa kërkesa u pranuan në gusht?", en: "How many requests were received in August?" },
    keywords: ["pranuan", "pranuara", "regjistruan", "received", "how many requests"],
    formula: {
      sq: "Numri i kërkesave të regjistruara në muaj, sipas datës së regjistrimit.",
      en: "Number of requests registered in the month, by registration date.",
    },
    unit: "count",
    unit_label: U.requests,
    direction: "none",
    target: null,
    datasets: ["requests"],
    owner: OWNERS.citizen_relations,
    smp_ref: null,
    periodKind: "month",
    series: () => monthly([268, 281, 305, 298, 322, 309, 297, 312]),
    sql: `SELECT count(*) AS value
FROM request
WHERE date_trunc('month', created_at) = DATE '2026-08-01'`,
    answer: { sq: "Në {period} u regjistruan {value}.", en: "{value} were registered in {period}." },
    checks: ["placeholder_value", "swing"],
    lineage: [{ dataset: "requests", row_count: 312, row_ranges: "2084–2395" }],
  },
  {
    code: "REQ-02",
    area: "requests",
    name: { sq: "Zgjidhur brenda afatit", en: "Resolved on time" },
    question: {
      sq: "Sa përqind e kërkesave u zgjidhën brenda afatit në gusht?",
      en: "What share of requests was resolved on time in August?",
    },
    keywords: ["afatit", "brenda afatit", "on time", "within deadline", "resolved on time"],
    formula: {
      sq: "Kërkesat e mbyllura brenda afatit (data e mbylljes − data e regjistrimit ≤ afati në ditë) ÷ të gjitha kërkesat e mbyllura në muaj × 100.",
      en: "Requests closed within their deadline (closing date − registration date ≤ deadline in days) ÷ all requests closed in the month × 100.",
    },
    unit: "percent",
    unit_label: U.percent,
    direction: "higher_better",
    target: 90,
    datasets: ["requests"],
    owner: OWNERS.citizen_relations,
    smp_ref: null,
    periodKind: "month",
    series: () => monthly([88.4, 89.1, 90.2, 91.0, 90.6, 89.8, 84.7, 82.9]),
    sql: `SELECT round(100.0 * count(*) FILTER (WHERE closed_at - created_at <= sla_days)
             / nullif(count(*), 0), 1) AS value
FROM request
WHERE closed_at IS NOT NULL
  AND date_trunc('month', closed_at) = DATE '2026-08-01'`,
    answer: {
      sq: "Në {period}, {value} e kërkesave të mbyllura u zgjidhën brenda afatit (objektivi: {target}).",
      en: "In {period}, {value} of closed requests were resolved on time (target: {target}).",
    },
    checks: ["rate_bounds", "off_target", "swing"],
    lineage: [{ dataset: "requests", row_count: 291, row_ranges: "2071–2395" }],
  },
  {
    code: "REQ-03",
    area: "requests",
    name: { sq: "Kërkesa të hapura me afat të kaluar", en: "Open requests past deadline" },
    question: {
      sq: "Sa kërkesa të hapura e kanë kaluar afatin?",
      en: "How many open requests are past their deadline?",
    },
    keywords: ["kaluar", "vonuara", "overdue", "past deadline", "past their deadline"],
    formula: {
      sq: "Kërkesat pa datë mbylljeje, ku data e regjistrimit + afati është para datës së raportimit.",
      en: "Requests with no closing date whose registration date + deadline is before the reporting date.",
    },
    unit: "count",
    unit_label: U.requests,
    direction: "lower_better",
    target: null,
    datasets: ["requests"],
    owner: OWNERS.citizen_relations,
    smp_ref: null,
    periodKind: "month",
    series: () => monthly([21, 24, 19, 22, 26, 29, 38, 47]),
    sql: `SELECT count(*) AS value
FROM request
WHERE closed_at IS NULL
  AND created_at + sla_days * INTERVAL 1 DAY < DATE '2026-08-31'`,
    answer: {
      sq: "Në fund të {period}, {value} ishin të hapura me afat të kaluar.",
      en: "At the end of {period}, {value} were open past their deadline.",
    },
    checks: ["placeholder_value", "swing"],
    lineage: [{ dataset: "requests", row_count: 47, row_ranges: "1712, 1840–1843, 2204–2391" }],
  },
  {
    code: "REQ-04",
    area: "requests",
    name: { sq: "Koha mesatare e zgjidhjes", en: "Average resolution time" },
    question: {
      sq: "Sa ditë zgjat mesatarisht zgjidhja e një kërkese?",
      en: "How many days does it take on average to resolve a request?",
    },
    keywords: ["koha mesatare", "sa ditë", "average", "resolution time", "how many days"],
    formula: {
      sq: "Mesatarja e (data e mbylljes − data e regjistrimit) për kërkesat e mbyllura në muaj.",
      en: "Average of (closing date − registration date) for requests closed in the month.",
    },
    unit: "days",
    unit_label: U.days,
    direction: "lower_better",
    target: 10,
    datasets: ["requests"],
    owner: OWNERS.citizen_relations,
    smp_ref: null,
    periodKind: "month",
    series: () => monthly([7.4, 7.2, 6.9, 7.1, 7.3, 7.6, 8.4, 8.9]),
    sql: `SELECT round(avg(closed_at - created_at), 1) AS value
FROM request
WHERE date_trunc('month', closed_at) = DATE '2026-08-01'`,
    answer: {
      sq: "Në {period}, kërkesat u zgjidhën mesatarisht për {value} (objektivi: deri në {target}).",
      en: "In {period}, requests were resolved in {value} on average (target: at most {target}).",
    },
    checks: ["off_target", "swing"],
    lineage: [{ dataset: "requests", row_count: 291, row_ranges: "2071–2395" }],
  },
  {
    code: "FIN-01",
    area: "finance",
    name: {
      sq: "Zbatimi i buxhetit (fakt/plan) — pamje e brendshme",
      en: "Budget execution (actual/plan) — internal view",
    },
    question: {
      sq: "Sa është zbatimi i buxhetit deri në gusht?",
      en: "What is budget execution up to August?",
    },
    keywords: ["zbatimi i buxhetit", "buxhet", "budget execution", "budget"],
    formula: {
      sq: "Shpenzimet faktike ÷ shpenzimet e planifikuara për periudhën janar–gusht × 100, të gjitha programet.",
      en: "Actual spending ÷ planned spending for January–August × 100, all programmes.",
    },
    unit: "percent",
    unit_label: U.percent,
    direction: "higher_better",
    target: 90,
    datasets: ["budget"],
    owner: OWNERS.finance,
    smp_ref: "SMP-AL 2024 #47 · pamje e brendshme (vlera zyrtare nga AMVV)",
    periodKind: "ytd",
    series: () => monthly([88.1, 89.0, 90.4, 91.2, 91.0, 91.6, 92.0, 91.4]),
    sql: `SELECT round(100.0 * sum(actual_lek) / nullif(sum(planned_lek), 0), 1) AS value
FROM budget_line
WHERE month BETWEEN DATE '2026-01-01' AND DATE '2026-08-01'`,
    answer: {
      sq: "Për {period}, shpenzimet faktike janë {value} e planit (objektivi: {target}).",
      en: "For {period}, actual spending is {value} of plan (target: {target}).",
    },
    checks: ["rate_bounds", "off_target", "parts_vs_total"],
    lineage: [{ dataset: "budget", row_count: 144, row_ranges: "4–147" }],
  },
  {
    code: "FIN-02",
    area: "finance",
    name: { sq: "Zbatimi i investimeve (kapitale)", en: "Capital investment execution" },
    question: {
      sq: "Sa është zbatimi i buxhetit të investimeve deri në gusht?",
      en: "What is capital investment execution up to August?",
    },
    keywords: ["investim", "kapitale", "capital", "investment"],
    formula: {
      sq: "Shpenzimet kapitale faktike ÷ shpenzimet kapitale të planifikuara për janar–gusht × 100.",
      en: "Actual capital spending ÷ planned capital spending for January–August × 100.",
    },
    unit: "percent",
    unit_label: U.percent,
    direction: "higher_better",
    target: 70,
    datasets: ["budget"],
    owner: OWNERS.finance,
    smp_ref: null,
    periodKind: "ytd",
    series: () => monthly([12.4, 15.1, 19.8, 23.5, 27.2, 31.0, 34.6, 37.8]),
    sql: `SELECT round(100.0 * sum(actual_lek) / nullif(sum(planned_lek), 0), 1) AS value
FROM budget_line
WHERE line_type = 'capital'
  AND month BETWEEN DATE '2026-01-01' AND DATE '2026-08-01'`,
    answer: {
      sq: "Për {period}, investimet kapitale janë zbatuar në {value} të planit (objektivi: {target}).",
      en: "For {period}, capital investment execution is {value} of plan (target: {target}).",
    },
    checks: ["rate_bounds", "off_target", "parts_vs_total"],
    lineage: [{ dataset: "budget", row_count: 72, row_ranges: "5, 7, 9 … 147 (Kapitale)" }],
  },
  {
    code: "WST-01",
    area: "waste",
    name: { sq: "Mbetje të grumbulluara", en: "Waste collected" },
    question: { sq: "Sa ton mbetje u grumbulluan në gusht?", en: "How many tonnes of waste were collected in August?" },
    keywords: ["ton", "mbetje", "grumbulluan", "waste", "tonnes", "collected"],
    formula: {
      sq: "Shuma e sasisë së mbetjeve (ton) të grumbulluara në muaj, të gjitha njësitë administrative.",
      en: "Sum of waste collected (tonnes) in the month, all administrative units.",
    },
    unit: "count",
    unit_label: U.tonnes,
    direction: "none",
    target: null,
    datasets: ["waste"],
    owner: OWNERS.public_services,
    smp_ref: null,
    periodKind: "month",
    series: () => monthly(WASTE_TONNES),
    sql: `SELECT round(sum(tonnes), 0) AS value
FROM waste_collection
WHERE month = DATE '2026-08-01'`,
    answer: { sq: "Në {period} u grumbulluan {value} mbetje.", en: "{value} of waste were collected in {period}." },
    checks: ["placeholder_value", "swing", "parts_vs_total"],
    lineage: [{ dataset: "waste", row_count: 13, row_ranges: "93–105" }],
    extraSignals: [
      {
        rule: "placeholder_value",
        severity: "warn",
        period: "2026-07",
        message: {
          sq: "Gjinar raportoi 0 ton në korrik 2026, ndërsa muajt fqinjë kanë vlera të mëdha — kontrolloni sasinë ose njësinë.",
          en: "Gjinar reported 0 tonnes in July 2026 while neighbouring months are large — check the quantity or unit.",
        },
      },
    ],
  },
  {
    code: "WST-02",
    area: "waste",
    name: { sq: "Mbetje për banor (kg/banor/vit)", en: "Waste per resident (kg/resident/yr)" },
    question: { sq: "Sa kg mbetje prodhon një banor në vit?", en: "How many kg of waste per resident per year?" },
    keywords: ["për banor", "kg", "per resident", "per capita"],
    formula: {
      sq: "Mbetjet e grumbulluara janar–gusht (kg) ÷ popullsia (baza e fiksuar) × 12/8, për ta shprehur në vit.",
      en: "Waste collected January–August (kg) ÷ population (pinned basis) × 12/8, to express it per year.",
    },
    unit: "kg_per_resident",
    unit_label: U.kg,
    direction: "none",
    target: null,
    datasets: ["waste", "population"],
    owner: OWNERS.public_services,
    smp_ref: "SMP-AL 2024 #14",
    periodKind: "ytd",
    series: (basis) => {
      const pop = POPULATION[basis];
      let cumulative = 0;
      return WASTE_TONNES.map((t, i) => {
        cumulative += t;
        return { period: MONTHS[i], value: round(((cumulative * 1000) / pop) * (12 / (i + 1)), 1) };
      });
    },
    sql: `SELECT round(sum(w.tonnes) * 1000 / p.residents * 12 / 8, 1) AS value
FROM waste_collection w,
     (SELECT sum(residents) AS residents FROM population
      WHERE basis = '{basis}') p
WHERE w.month BETWEEN DATE '2026-01-01' AND DATE '2026-08-01'
GROUP BY p.residents`,
    answer: {
      sq: "Për {period}, mbetjet e grumbulluara janë {value} (e vjetëzuar).",
      en: "For {period}, waste collected is {value} (annualised).",
    },
    checks: ["placeholder_value", "swing"],
    lineage: [
      { dataset: "waste", row_count: 104, row_ranges: "2–105" },
      { dataset: "population", row_count: 13, row_ranges: "2–14" },
    ],
  },
  {
    code: "WST-03",
    area: "waste",
    name: { sq: "Kosto për ton", en: "Cost per tonne" },
    question: { sq: "Sa kushton grumbullimi i një toni mbetje?", en: "What does collecting one tonne of waste cost?" },
    keywords: ["kosto për ton", "kushton", "cost per tonne", "cost per ton"],
    formula: {
      sq: "Shpenzimet faktike të programit 05100 Menaxhimi i mbetjeve në muaj ÷ tonët e grumbulluar në muaj.",
      en: "Actual spending of programme 05100 Waste management in the month ÷ tonnes collected in the month.",
    },
    unit: "lek_per_ton",
    unit_label: U.lekTon,
    direction: "lower_better",
    target: null,
    datasets: ["waste", "budget"],
    owner: OWNERS.public_services,
    smp_ref: "SMP-AL 2024 #15",
    periodKind: "month",
    series: () => monthly([10850, 11420, 10960, 11180, 10740, 17260, 11050, 10920]),
    sql: `SELECT round(b.actual / w.tonnes, 0) AS value
FROM (SELECT sum(actual_lek) AS actual FROM budget_line
      WHERE programme_code = '05100' AND month = DATE '2026-08-01') b,
     (SELECT sum(tonnes) AS tonnes FROM waste_collection
      WHERE month = DATE '2026-08-01') w`,
    answer: { sq: "Në {period}, kostoja e shërbimit ishte {value}.", en: "In {period}, the service cost was {value}." },
    checks: ["placeholder_value", "swing"],
    lineage: [
      { dataset: "waste", row_count: 13, row_ranges: "93–105" },
      { dataset: "budget", row_count: 2, row_ranges: "136–137" },
    ],
  },
  {
    code: "REV-01",
    area: "revenue",
    name: { sq: "Arkëtimi i të ardhurave vendore", en: "Local revenue collection" },
    question: {
      sq: "Sa përqind e taksave dhe tarifave vendore është arkëtuar?",
      en: "What share of local taxes and fees has been collected?",
    },
    keywords: ["arkëtuar", "arkëtimi", "taksa", "tarifa", "collected", "taxes", "fees", "revenue"],
    formula: {
      sq: "Të ardhurat e arkëtuara ÷ të ardhurat e planifikuara për janar–gusht × 100, të gjitha llojet.",
      en: "Revenue collected ÷ planned revenue for January–August × 100, all types.",
    },
    unit: "percent",
    unit_label: U.percent,
    direction: "higher_better",
    target: 90,
    datasets: ["revenue"],
    owner: OWNERS.local_revenue,
    smp_ref: null,
    periodKind: "ytd",
    series: () => monthly([62.0, 66.4, 70.8, 74.1, 76.9, 78.8, 80.2, 81.3]),
    sql: `SELECT round(100.0 * sum(collected_lek) / nullif(sum(planned_lek), 0), 1) AS value
FROM revenue
WHERE month BETWEEN DATE '2026-01-01' AND DATE '2026-08-01'`,
    answer: {
      sq: "Për {period}, janë arkëtuar {value} e të ardhurave të planifikuara (objektivi: {target}).",
      en: "For {period}, {value} of planned revenue has been collected (target: {target}).",
    },
    checks: ["rate_bounds", "off_target", "parts_vs_total"],
    lineage: [{ dataset: "revenue", row_count: 96, row_ranges: "4–99" }],
  },
  {
    code: "REV-02",
    area: "revenue",
    name: { sq: "Mbulimi i kostos së mbetjeve nga tarifa", en: "Waste cost covered by the fee" },
    question: {
      sq: "Sa e mbulon tarifa e pastrimit koston e mbetjeve?",
      en: "How much of the waste cost does the cleaning fee cover?",
    },
    keywords: ["mbulon", "mbulimi", "tarifa e pastrimit", "cleaning fee", "cost coverage", "covers"],
    formula: {
      sq: "Tarifa e pastrimit e arkëtuar ÷ shpenzimet faktike të programit 05100 Menaxhimi i mbetjeve, janar–gusht × 100. Bashkon eksportet e dy drejtorive.",
      en: "Cleaning fee collected ÷ actual spending of programme 05100 Waste management, January–August × 100. Joins two directorates' exports.",
    },
    unit: "percent",
    unit_label: U.percent,
    direction: "higher_better",
    target: 100,
    datasets: ["revenue", "budget"],
    owner: OWNERS.local_revenue,
    smp_ref: "SMP-AL 2024 #13",
    periodKind: "ytd",
    series: () => monthly([41.2, 45.8, 49.0, 51.7, 53.9, 52.1, 55.3, 56.4]),
    sql: `SELECT round(100.0 * r.fee / b.cost, 1) AS value
FROM (SELECT sum(collected_lek) AS fee FROM revenue
      WHERE revenue_type = 'Tarifa e pastrimit') r,
     (SELECT sum(actual_lek) AS cost FROM budget_line
      WHERE programme_code = '05100') b`,
    answer: {
      sq: "Për {period}, tarifa e pastrimit mbulon {value} të kostos së mbetjeve (objektivi: {target}).",
      en: "For {period}, the cleaning fee covers {value} of waste cost (target: {target}).",
    },
    checks: ["rate_bounds", "off_target"],
    lineage: [
      { dataset: "revenue", row_count: 16, row_ranges: "6, 7, 18, 19 … 90, 91" },
      { dataset: "budget", row_count: 16, row_ranges: "10, 11, 28, 29 … 136, 137" },
    ],
  },
  {
    code: "HR-01",
    area: "hr",
    name: { sq: "Punonjës për 1.000 banorë", en: "Staff per 1,000 residents" },
    question: { sq: "Sa punonjës ka bashkia për 1.000 banorë?", en: "How many staff per 1,000 residents?" },
    keywords: ["punonjës", "1.000 banorë", "staff", "employees", "1,000 residents"],
    formula: {
      sq: "Numri i punonjësve më 31.08.2026 ÷ popullsia (baza e fiksuar) × 1.000.",
      en: "Headcount on 31.08.2026 ÷ population (pinned basis) × 1,000.",
    },
    unit: "per_1000",
    unit_label: U.per1000,
    direction: "none",
    target: null,
    datasets: ["staff", "population"],
    owner: OWNERS.hr,
    smp_ref: "SMP-AL 2024 #25",
    periodKind: "snapshot",
    series: (basis) => snapshot(round((HEADCOUNT / POPULATION[basis]) * 1000, 2)),
    sql: `SELECT round(1000.0 * s.headcount / p.residents, 2) AS value
FROM (SELECT sum(headcount) AS headcount FROM staff) s,
     (SELECT sum(residents) AS residents FROM population
      WHERE basis = '{basis}') p`,
    answer: { sq: "Në {period}, bashkia ka {value}.", en: "In {period}, the municipality has {value}." },
    checks: ["placeholder_value"],
    lineage: [
      { dataset: "staff", row_count: 9, row_ranges: "4–12" },
      { dataset: "population", row_count: 13, row_ranges: "2–14" },
    ],
  },
  {
    code: "HR-02",
    area: "hr",
    name: {
      sq: "Shkalla e rotacionit të punonjësve (largime / numri mesatar)",
      en: "Staff turnover rate (leavers / average headcount)",
    },
    question: { sq: "Sa është rotacioni i punonjësve?", en: "What is the staff turnover rate?" },
    keywords: ["rotacion", "largime", "turnover", "leavers"],
    formula: {
      sq: "Largimet 2026 ÷ numri mesatar i punonjësve ((fillimi + fundi) ÷ 2) × 100.",
      en: "Leavers 2026 ÷ average headcount ((start + end) ÷ 2) × 100.",
    },
    unit: "percent",
    unit_label: U.percent,
    direction: "lower_better",
    target: null,
    datasets: ["staff"],
    owner: OWNERS.hr,
    smp_ref: "SMP-AL 2024 #23",
    periodKind: "snapshot",
    series: () => {
      const start = HEADCOUNT - HIRES + LEAVERS;
      return snapshot(round((LEAVERS / ((start + HEADCOUNT) / 2)) * 100, 1));
    },
    sql: `SELECT round(100.0 * sum(leavers)
             / ((sum(headcount) - sum(hires) + sum(leavers) + sum(headcount)) / 2.0), 1) AS value
FROM staff`,
    answer: { sq: "Në {period}, shkalla e rotacionit është {value}.", en: "In {period}, staff turnover is {value}." },
    checks: ["rate_bounds"],
    lineage: [{ dataset: "staff", row_count: 9, row_ranges: "4–12" }],
  },
];

export const indicatorDef = (code: string) => INDICATORS.find((i) => i.code === code) ?? null;

export function periodOf(def: IndicatorDef): string {
  return def.periodKind === "ytd" ? "2026-01/2026-08" : "2026-08";
}

function statusOf(def: IndicatorDef, value: number | null): IndicatorSummary["status"] {
  if (value == null) return null;
  if (def.target == null || def.direction === "none") return "no_target";
  const ok = def.direction === "higher_better" ? value >= def.target : value <= def.target;
  return ok ? "on_track" : "off_track";
}

const fmt = (def: IndicatorDef, value: number, locale: "sq" | "en") =>
  formatIndicatorValue(value, def.unit, locale, def.unit_label[locale]).text;

/** Generic plausibility rules (contract §5), evaluated by code over the series. */
function evaluateSignals(def: IndicatorDef, series: Series, value: number | null): Signal[] {
  const signals: Signal[] = [];
  if (value != null && def.target != null && statusOf(def, value) === "off_track") {
    const below = def.direction === "higher_better";
    signals.push({
      rule: "off_target",
      severity: "warn",
      period: series.at(-1)?.period ?? null,
      message: {
        sq: `Vlera e fundit (${fmt(def, value, "sq")}) është ${below ? "nën" : "mbi"} objektivin (${formatTarget(def.target, def.unit, "sq", def.unit_label.sq)}).`,
        en: `The latest value (${fmt(def, value, "en")}) is ${below ? "below" : "above"} the target (${formatTarget(def.target, def.unit, "en", def.unit_label.en)}).`,
      },
    });
  }
  if (def.checks.includes("swing") && def.periodKind === "month") {
    for (let i = 1; i < series.length; i++) {
      const prev = series[i - 1].value;
      const cur = series[i].value;
      if (prev == null || cur == null || Math.abs(prev) < 1) continue;
      const change = (cur - prev) / Math.abs(prev);
      if (Math.abs(change) > 0.5) {
        const pct = (locale: "sq" | "en") =>
          `${change > 0 ? "+" : "−"}${formatNumber(Math.abs(change) * 100, locale, 1)}%`;
        const from = (locale: "sq" | "en") => formatPeriod(series[i - 1].period, locale);
        const to = (locale: "sq" | "en") => formatPeriod(series[i].period, locale);
        signals.push({
          rule: "swing",
          severity: "warn",
          period: series[i].period,
          message: {
            sq: `Ndryshim ${pct("sq")} nga ${from("sq")} në ${to("sq")} — kontrolloni sasinë ose njësinë.`,
            en: `A ${pct("en")} change from ${from("en")} to ${to("en")} — check the quantity or unit.`,
          },
        });
      }
    }
  }
  return [...signals, ...(def.extraSignals ?? [])];
}

const CHECK_LABELS: Record<string, L10n> = {
  rate_bounds: { sq: "Përqindja brenda 0–100", en: "Percentage within 0–100" },
  off_target: { sq: "Vlera kundrejt objektivit", en: "Value against target" },
  swing: { sq: "Ndryshimi mujor nën 50%", en: "Month-on-month change under 50%" },
  placeholder_value: { sq: "Pa vlera zëvendësuese (0 ose 1)", en: "No placeholder values (0 or 1)" },
  parts_vs_total: { sq: "Pjesët përputhen me totalin e skedarit", en: "Parts match the file total" },
};

function sourceRef(state: ReplayState, dataset: DatasetKey) {
  const src = state.loaded.get(dataset);
  if (!src) return null;
  return { source_id: src.source_id, filename: src.filename, file_hash: src.file_hash, synthetic: src.synthetic };
}

function missingOf(def: IndicatorDef, state: ReplayState) {
  return def.datasets
    .filter((d) => !state.loaded.has(d))
    .map((d) => ({ dataset: d, name: DATASETS[d].exportName, owner: DATASETS[d].owner.name }));
}

export function buildSummary(def: IndicatorDef, state: ReplayState): IndicatorSummary {
  const missing = missingOf(def, state);
  const computable = missing.length === 0;
  const series = def.series(state.basis);
  const value = computable ? (series.at(-1)?.value ?? null) : null;
  const previous = computable && series.length > 1 ? (series.at(-2)?.value ?? null) : null;
  const usesBasis = def.datasets.includes("population");
  return {
    code: def.code,
    area: { key: def.area, name: AREAS[def.area] },
    name: def.name,
    unit: def.unit,
    unit_label: def.unit_label,
    state: computable ? "computable" : "missing",
    value,
    period: computable ? periodOf(def) : null,
    previous,
    target: def.target,
    direction: def.direction,
    status: computable ? statusOf(def, value) : null,
    owner: def.owner,
    missing,
    signals: computable ? evaluateSignals(def, series, value) : [],
    sources: computable
      ? def.datasets
          .map((d) => sourceRef(state, d))
          .filter((s): s is NonNullable<typeof s> => s !== null)
          .map(({ source_id, filename, synthetic }) => ({ source_id, filename, synthetic }))
      : [],
    smp_ref: def.smp_ref,
    version: "1.0.0",
    formula_status: "draft",
    basis: usesBasis ? state.basis : null,
    sparkline: computable ? series : [],
  };
}

export function buildBoard(state: ReplayState): IndicatorBoard {
  const indicators = INDICATORS.map((def) => buildSummary(def, state));
  const computable = indicators.filter((i) => i.state === "computable").length;
  return {
    pack: "core_kpi",
    as_of: AS_OF,
    coverage: {
      computable,
      missing: indicators.length - computable,
      document: 0,
      national: 0,
      total: indicators.length,
    },
    basis: { population: state.basis },
    indicators,
  };
}

export function buildPassport(code: string, state: ReplayState): Passport | null {
  const def = indicatorDef(code);
  if (!def) return null;
  const summary = buildSummary(def, state);
  const computable = summary.state === "computable";
  const series = def.series(state.basis);
  const signalsByRule = new Map(summary.signals.map((s) => [s.rule, s]));
  return {
    ...summary,
    formula: def.formula,
    question: def.question,
    sql: def.sql.replaceAll("{basis}", state.basis),
    series: computable ? series : [],
    lineage: computable
      ? def.lineage.map((l) => {
          const ref = sourceRef(state, l.dataset);
          return {
            source_id: ref?.source_id ?? "",
            filename: ref?.filename ?? "",
            file_hash: ref?.file_hash ?? "",
            row_count: l.row_count,
            row_ranges: l.row_ranges,
          };
        })
      : [],
    required_datasets: def.datasets,
    checks: computable
      ? def.checks.map((rule) => {
          const signal = signalsByRule.get(rule);
          return {
            rule,
            label: CHECK_LABELS[rule] ?? { sq: rule, en: rule },
            passed: !signal,
            message: signal?.message ?? null,
          };
        })
      : [],
    computed_at: computable ? COMPUTED_AT : null,
  };
}

export function buildLineage(code: string, limit: number, state: ReplayState): LineageRows | null {
  const def = indicatorDef(code);
  if (!def) return null;
  if (def.datasets.some((d) => !state.loaded.has(d))) {
    return { code, columns: [], total: 0, rows: [] };
  }
  const rows: LineageRows["rows"] = [];
  const columns: string[] = [];
  let total = 0;
  for (const l of def.lineage) {
    total += l.row_count;
    const src = state.loaded.get(l.dataset);
    const perSource = Math.max(1, Math.floor(limit / def.lineage.length));
    const startRow = Number(/\d+/.exec(l.row_ranges)?.[0] ?? 4);
    for (const row of datasetRows(l.dataset, Math.min(perSource, l.row_count), { startRow })) {
      for (const key of Object.keys(row.values)) if (!columns.includes(key)) columns.push(key);
      rows.push({ source_file: src?.filename ?? l.dataset, row_no: row.row_no, values: row.values });
    }
  }
  return { code, columns, total, rows: rows.slice(0, limit) };
}

export function fillAnswer(def: IndicatorDef, value: number, locale: "sq" | "en", periodText: string) {
  return def.answer[locale]
    .replace("{value}", fmt(def, value, locale))
    .replace("{period}", periodText)
    .replace("{target}", def.target != null ? formatTarget(def.target, def.unit, locale, def.unit_label[locale]) : "–");
}

export const sampleForDataset = (dataset: DatasetKey) =>
  SAMPLES.find((s) => s.dataset === dataset && s.envelope != null) ??
  SAMPLES.find((s) => s.dataset === dataset) ??
  null;
