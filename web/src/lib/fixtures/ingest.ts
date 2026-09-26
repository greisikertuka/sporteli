/**
 * REPLAY fixtures: ingest previews and load receipts for the SYNTHETIC sample files.
 * The API is in RULES mode on this machine (no key), so no AI call is ever shown:
 * rule mappings are capped at 0.6 confidence (amber, a person clicks), and recipes
 * return 1.0 once saved.
 */
import type { ColumnProfile, IngestPreview, IngestStep, L10n, LoadReceipt, MappingSuggestion, SourceInfo } from "../api";
import { formatNumber } from "../format.ts";
import { DATASETS, SAMPLES, type DatasetKey, type SampleDef } from "./catalog.ts";
import type { Recipe } from "./state.ts";

type Pii = ColumnProfile["pii"];
type ColSpec = {
  name: string;
  type: ColumnProfile["inferred_type"];
  samples: string[];
  field: string | null;
  pii?: Pii;
  null_pct?: number;
};
type ReconSpec = { field: string; file_total: number | null; loaded_sum: number; note?: L10n };

export type FileSpec = {
  sample: string;
  dataset: DatasetKey;
  format: "xlsx" | "csv";
  sheet: string | null;
  header_row: number;
  data_rows: number;
  excluded: IngestPreview["excluded_rows"];
  unit_multiplier: number;
  unit_columns: string[];
  columns: ColSpec[];
  reconcile: ReconSpec[];
  fingerprint: string;
  /** Recipe fingerprint of the format this file drifted from (drift file only). */
  drift_of?: { renamed: string[]; missing: string[]; added: string[]; question_column: string };
};

const NO_TOTAL = {
  sq: "Skedari nuk ka rresht totali: u kontrollua numri i rreshtave dhe shuma e ngarkuar.",
  en: "The file has no total row: the row count and the loaded sum were checked.",
};

const WASTE_COLUMNS: ColSpec[] = [
  { name: "Muaji", type: "date", samples: ["2026-01", "2026-01", "2026-01", "2026-01", "2026-01"], field: "month" },
  {
    name: "Njësia administrative",
    type: "string",
    samples: ["Elbasan", "Bradashesh", "Funarë", "Gjergjan", "Gjinar"],
    field: "admin_unit",
  },
  { name: "Sasia (ton)", type: "float", samples: ["2.304,6", "146,2", "40,1", "82,7", "31,4"], field: "tonnes" },
  { name: "Nr. i kursimeve", type: "int", samples: ["355", "23", "6", "13", "5"], field: "trips" },
  { name: "Familje të mbuluara", type: "int", samples: ["23694", "1532", "406", "865", "329"], field: "households_served" },
];

export const FILE_SPECS: FileSpec[] = [
  {
    sample: "01_SINTETIKE_kerkesat_qytetare_jan-gus_2026.xlsx",
    dataset: "requests",
    format: "xlsx",
    sheet: "Kërkesat 2026",
    header_row: 3,
    data_rows: 2392,
    excluded: [
      { row_no: 1, reason: "title", text: "BASHKIA ELBASAN — TË DHËNA SINTETIKE" },
      { row_no: 2, reason: "title", text: "Regjistri i kërkesave të qytetarëve, janar–gusht 2026" },
    ],
    unit_multiplier: 1,
    unit_columns: [],
    columns: [
      { name: "Nr.", type: "int", samples: ["1", "2", "3", "4", "5"], field: "request_id" },
      {
        name: "Data e regjistrimit",
        type: "date",
        samples: ["03.01.2026", "03.01.2026", "04.01.2026", "05.01.2026", "05.01.2026"],
        field: "created_at",
      },
      {
        name: "Kategoria",
        type: "string",
        samples: ["Ndriçim publik", "Rrugë dhe trotuare", "Pastrim", "Gjelbërim", "Ujë dhe kanalizime"],
        field: "category",
      },
      {
        name: "Drejtoria përgjegjëse",
        type: "string",
        samples: ["Shërbimet Publike", "Punët Publike", "Shërbimet Publike", "Planifikimi Urban", "Shërbimet Sociale"],
        field: "department",
      },
      {
        name: "Njësia administrative",
        type: "string",
        samples: ["Elbasan", "Shirgjani", "Bradashesh", "Tregani", "Papër"],
        field: "admin_unit",
      },
      { name: "Kanali", type: "string", samples: ["Sportel", "Telefon", "Online", "Sportel", "E-mail"], field: "channel" },
      { name: "Statusi", type: "string", samples: ["Mbyllur", "Mbyllur", "Në proces", "Mbyllur", "Hapur"], field: "status" },
      {
        name: "Data e mbylljes",
        type: "date",
        samples: ["08.01.2026", "12.01.2026", "09.01.2026", "15.01.2026", "11.01.2026"],
        field: "closed_at",
        null_pct: 6.2,
      },
      { name: "Afati (ditë)", type: "int", samples: ["10", "15", "10", "5", "20"], field: "sla_days" },
      { name: "Emri i kërkuesit", type: "string", samples: [], field: null, pii: "name" },
      { name: "Nr. telefoni", type: "string", samples: [], field: null, pii: "phone" },
    ],
    reconcile: [{ field: "request_id", file_total: null, loaded_sum: 2392, note: NO_TOTAL }],
    fingerprint: "fp_3a91c07e",
  },
  {
    sample: "02_SINTETIKE_zbatimi_buxhetit_jan-gus_2026.xlsx",
    dataset: "budget",
    format: "xlsx",
    sheet: "Zbatimi 2026",
    header_row: 3,
    data_rows: 144,
    excluded: [
      { row_no: 1, reason: "title", text: "BASHKIA ELBASAN — TË DHËNA SINTETIKE" },
      { row_no: 2, reason: "title", text: "Zbatimi i buxhetit sipas programeve, janar–gusht 2026 (000 lekë)" },
      { row_no: 148, reason: "total_row", text: "TOTALI" },
    ],
    unit_multiplier: 1000,
    unit_columns: ["Plani (000 lekë)", "Fakti (000 lekë)"],
    columns: [
      { name: "Muaji", type: "date", samples: ["Janar 2026", "Janar 2026", "Janar 2026", "Janar 2026", "Janar 2026"], field: "month" },
      { name: "Kodi i programit", type: "string", samples: ["01110", "01110", "03140", "03140", "04520"], field: "programme_code" },
      {
        name: "Programi",
        type: "string",
        samples: [
          "Planifikim, menaxhim dhe administrim",
          "Planifikim, menaxhim dhe administrim",
          "Mbrojtja civile",
          "Mbrojtja civile",
          "Rrugët rurale",
        ],
        field: "programme",
      },
      { name: "Lloji i shpenzimit", type: "string", samples: ["Korrente", "Kapitale", "Korrente", "Kapitale", "Korrente"], field: "line_type" },
      { name: "Plani (000 lekë)", type: "float", samples: ["21.450,0", "6.800,0", "3.120,5", "1.900,0", "8.245,0"], field: "planned_lek" },
      { name: "Fakti (000 lekë)", type: "float", samples: ["19.872,4", "1.204,0", "2.986,1", "310,0", "7.402,9"], field: "actual_lek" },
    ],
    reconcile: [
      { field: "planned_lek", file_total: 2_146_320_000, loaded_sum: 2_146_320_000 },
      { field: "actual_lek", file_total: 1_961_736_000, loaded_sum: 1_961_736_000 },
    ],
    fingerprint: "fp_b40d2e19",
  },
  {
    sample: "ref_SINTETIKE_popullsia_njesite.csv",
    dataset: "population",
    format: "csv",
    sheet: null,
    header_row: 1,
    data_rows: 26,
    excluded: [],
    unit_multiplier: 1,
    unit_columns: [],
    columns: [
      {
        name: "Njësia administrative",
        type: "string",
        samples: ["Elbasan", "Bradashesh", "Funarë", "Gjergjan", "Gjinar"],
        field: "admin_unit",
      },
      { name: "Baza", type: "string", samples: ["census_2023", "census_2023", "census_2023", "census_2023", "census_2023"], field: "basis" },
      { name: "Banorë", type: "int", samples: ["80560", "5210", "1380", "2940", "1120"], field: "residents" },
    ],
    reconcile: [{ field: "residents", file_total: null, loaded_sum: 330_100, note: NO_TOTAL }],
    fingerprint: "fp_07c55e2a",
  },
  {
    sample: "zarfi-1_SINTETIKE_pastrimi_mbetjet_2026.csv",
    dataset: "waste",
    format: "csv",
    sheet: null,
    header_row: 1,
    data_rows: 104,
    excluded: [],
    unit_multiplier: 1,
    unit_columns: [],
    columns: WASTE_COLUMNS,
    reconcile: [{ field: "tonnes", file_total: null, loaded_sum: 29_137, note: NO_TOTAL }],
    fingerprint: "fp_5d2f8b0e",
  },
  {
    sample: "zarfi-2_SINTETIKE_taksat_tarifat_arketimi_2026.xlsx",
    dataset: "revenue",
    format: "xlsx",
    sheet: "Arkëtimi 2026",
    header_row: 3,
    data_rows: 96,
    excluded: [
      { row_no: 1, reason: "title", text: "BASHKIA ELBASAN — TË DHËNA SINTETIKE" },
      { row_no: 2, reason: "title", text: "Arkëtimi i taksave dhe tarifave vendore, janar–gusht 2026 (000 lekë)" },
      { row_no: 100, reason: "total_row", text: "Gjithsej" },
    ],
    unit_multiplier: 1000,
    unit_columns: ["Plani (000 lekë)", "Arkëtuar (000 lekë)"],
    columns: [
      { name: "Muaji", type: "date", samples: ["Janar 2026", "Janar 2026", "Janar 2026", "Janar 2026", "Janar 2026"], field: "month" },
      {
        name: "Lloji i të ardhurës",
        type: "string",
        samples: ["Taksa e ndërtesës", "Taksa e ndërtesës", "Tarifa e pastrimit", "Tarifa e pastrimit", "Taksa e truallit"],
        field: "revenue_type",
      },
      { name: "Kategoria e paguesit", type: "string", samples: ["Familje", "Biznes", "Familje", "Biznes", "Familje"], field: "payer_type" },
      { name: "Plani (000 lekë)", type: "float", samples: ["9.840,0", "14.210,0", "6.120,0", "8.905,5", "2.310,0"], field: "planned_lek" },
      { name: "Arkëtuar (000 lekë)", type: "float", samples: ["6.102,3", "12.480,9", "3.371,8", "6.950,2", "1.644,0"], field: "collected_lek" },
    ],
    reconcile: [
      { field: "planned_lek", file_total: 1_284_560_000, loaded_sum: 1_284_560_000 },
      { field: "collected_lek", file_total: 1_044_347_000, loaded_sum: 1_044_347_000 },
    ],
    fingerprint: "fp_e8a4c2f6",
  },
  {
    sample: "zarfi-3_SINTETIKE_burimet_njerezore_2026.xlsx",
    dataset: "staff",
    format: "xlsx",
    sheet: "Punonjësit",
    header_row: 3,
    data_rows: 9,
    excluded: [
      { row_no: 1, reason: "title", text: "BASHKIA ELBASAN — TË DHËNA SINTETIKE" },
      { row_no: 2, reason: "title", text: "Burimet njerëzore sipas drejtorive, 31.08.2026" },
      { row_no: 13, reason: "total_row", text: "Gjithsej" },
    ],
    unit_multiplier: 1,
    unit_columns: [],
    columns: [
      {
        name: "Drejtoria",
        type: "string",
        samples: ["Shërbimet Publike", "Financa dhe Buxheti", "Të Ardhurat Vendore", "Burimet Njerëzore", "Planifikimi Urban"],
        field: "department",
      },
      { name: "Numri i punonjësve (31.08.2026)", type: "int", samples: ["312", "64", "58", "41", "97"], field: "headcount" },
      { name: "Pranime 2026", type: "int", samples: ["21", "4", "5", "2", "7"], field: "hires" },
      { name: "Largime 2026", type: "int", samples: ["17", "3", "4", "2", "6"], field: "leavers" },
      { name: "Përgjegjësi i drejtorisë", type: "string", samples: [], field: null, pii: "name" },
    ],
    reconcile: [
      { field: "headcount", file_total: 1046, loaded_sum: 1046 },
      { field: "hires", file_total: 71, loaded_sum: 71 },
      { field: "leavers", file_total: 58, loaded_sum: 58 },
    ],
    fingerprint: "fp_b3f7d1a9",
  },
  {
    sample: "drift_SINTETIKE_pastrimi_mbetjet_2026_v2.csv",
    dataset: "waste",
    format: "csv",
    sheet: null,
    header_row: 1,
    data_rows: 104,
    excluded: [],
    unit_multiplier: 1,
    unit_columns: [],
    columns: [
      ...WASTE_COLUMNS.slice(0, 2),
      { name: "Tonazhi", type: "float", samples: ["2.304,6", "146,2", "40,1", "82,7", "31,4"], field: "tonnes" },
      ...WASTE_COLUMNS.slice(3),
      { name: "Shënime", type: "string", samples: ["", "rrugë e bllokuar", "", "", ""], field: null, null_pct: 91.3 },
    ],
    reconcile: [{ field: "tonnes", file_total: null, loaded_sum: 29_137, note: NO_TOTAL }],
    fingerprint: "fp_9c1e70b4",
    drift_of: { renamed: ["Sasia (ton) → Tonazhi"], missing: [], added: ["Shënime"], question_column: "Tonazhi" },
  },
];

export const fileSpec = (sample: string) => FILE_SPECS.find((s) => s.sample === sample) ?? null;
export const sampleDef = (name: string): SampleDef | null => SAMPLES.find((s) => s.name === name) ?? null;

const PII_LABEL: Record<NonNullable<Pii>, L10n> = {
  name: { sq: "emër", en: "name" },
  phone: { sq: "telefon", en: "phone" },
  email: { sq: "e-mail", en: "email" },
  personal_id: { sq: "numër personal", en: "personal number" },
  address: { sq: "adresë", en: "address" },
};

const EXCLUDED_LABEL: Record<string, L10n> = {
  title: { sq: "rreshta titulli", en: "title rows" },
  total_row: { sq: "rresht totali (për barazim)", en: "total row (kept for reconciliation)" },
  blank: { sq: "rreshta bosh", en: "blank rows" },
  subtotal: { sq: "nëntotale", en: "subtotals" },
};

const fieldLabel = (dataset: DatasetKey, field: string): L10n =>
  DATASETS[dataset].fields.find((f) => f.key === field)?.label ?? { sq: field, en: field };

const both = (build: (locale: "sq" | "en") => string): L10n => ({ sq: build("sq"), en: build("en") });
const n = (value: number, locale: "sq" | "en", digits = 0) => formatNumber(value, locale, digits);

export type RecipeMatch = { kind: "none" } | { kind: "hit"; recipe: Recipe } | { kind: "drift"; recipe: Recipe };

export function recipeMatch(spec: FileSpec, recipe: Recipe | undefined): RecipeMatch {
  if (!recipe) return { kind: "none" };
  if (recipe.fingerprint === spec.fingerprint) return { kind: "hit", recipe };
  if (spec.drift_of) return { kind: "drift", recipe };
  return { kind: "none" };
}

/** Build the IngestPreview a rules-mode API would return for this synthetic file. */
export function buildPreview(spec: FileSpec, previewId: string, match: RecipeMatch): IngestPreview {
  const sample = sampleDef(spec.sample);
  const dataset = DATASETS[spec.dataset];
  const columns: ColumnProfile[] = spec.columns.map((c, index) => ({
    index,
    name: c.name,
    inferred_type: c.type,
    samples: c.pii ? [] : c.samples,
    null_pct: c.null_pct ?? 0,
    pii: c.pii ?? null,
    dropped: Boolean(c.pii),
  }));
  const dropped = spec.columns.filter((c) => c.pii);
  const kept = spec.columns.filter((c) => !c.pii);

  const mapping: MappingSuggestion[] = kept.map((c) => {
    if (match.kind === "hit") {
      return {
        column: c.name,
        field: c.field,
        confidence: 1,
        reason: { sq: `Nga receta e ruajtur ${match.recipe.id}`, en: `From saved recipe ${match.recipe.id}` },
        source: "recipe",
      };
    }
    if (match.kind === "drift" && match.recipe.columns.includes(c.name)) {
      return {
        column: c.name,
        field: c.field,
        confidence: 1,
        reason: { sq: `E pandryshuar nga receta ${match.recipe.id}`, en: `Unchanged from recipe ${match.recipe.id}` },
        source: "recipe",
      };
    }
    if (c.field === null) {
      return {
        column: c.name,
        field: null,
        confidence: 0.3,
        reason: { sq: "Nuk përputhet me asnjë fushë: do të injorohet", en: "Matches no field: it will be ignored" },
        source: "rules",
      };
    }
    if (match.kind === "drift" && c.name === spec.drift_of?.question_column) {
      return {
        column: c.name,
        field: c.field,
        confidence: 0.55,
        reason: {
          sq: "Kolonë e riemërtuar: vlerat ngjajnë me 'Sasia (ton)' të recetës",
          en: "Renamed column: values resemble the recipe's 'Sasia (ton)'",
        },
        source: "rules",
      };
    }
    const label = fieldLabel(spec.dataset, c.field);
    return {
      column: c.name,
      field: c.field,
      confidence: 0.6,
      reason: {
        sq: `Sinonim i njohur për fushën '${label.sq}' (rregull; pa AI)`,
        en: `Known synonym for the field '${label.en}' (rule; no AI)`,
      },
      source: "rules",
    };
  });

  const titles = spec.excluded.filter((e) => e.reason === "title").length;
  const totals = spec.excluded.filter((e) => e.reason === "total_row");
  const types = kept.reduce<Record<string, number>>((acc, c) => ({ ...acc, [c.type]: (acc[c.type] ?? 0) + 1 }), {});
  const typeText = (locale: "sq" | "en") => {
    const names: Record<string, L10n> = {
      date: { sq: "datë", en: "date" },
      string: { sq: "tekst", en: "text" },
      int: { sq: "numër i plotë", en: "integer" },
      float: { sq: "numër dhjetor", en: "decimal" },
      empty: { sq: "bosh", en: "empty" },
    };
    return Object.entries(types)
      .map(([t, count]) => `${count} ${names[t]?.[locale] ?? t}`)
      .join(", ");
  };
  const allRows = spec.data_rows + spec.excluded.length + 1;

  const steps: IngestStep[] = [
    {
      code: "read",
      status: "ok",
      ms: spec.format === "xlsx" ? 184 : 22,
      message:
        spec.format === "xlsx"
          ? both((l) =>
              l === "sq"
                ? `U lexua fleta '${spec.sheet}' (xlsx): ${n(allRows, l)} rreshta, ${n(spec.columns.length, l)} kolona; qelizat e bashkuara u plotësuan.`
                : `Read sheet '${spec.sheet}' (xlsx): ${n(allRows, l)} rows, ${n(spec.columns.length, l)} columns; merged cells forward-filled.`,
            )
          : both((l) =>
              l === "sq"
                ? `U lexua CSV (UTF-8 me BOM, ndarës ';', presje dhjetore): ${n(allRows, l)} rreshta, ${n(spec.columns.length, l)} kolona.`
                : `Read CSV (UTF-8 with BOM, ';' delimiter, decimal comma): ${n(allRows, l)} rows, ${n(spec.columns.length, l)} columns.`,
            ),
    },
    {
      code: "header",
      status: "ok",
      ms: 3,
      message: both((l) =>
        l === "sq"
          ? `Rreshti i titujve u gjet në rreshtin ${spec.header_row}${titles ? ` (pas ${titles} rreshtave të titullit)` : ""}.`
          : `Header row found at row ${spec.header_row}${titles ? ` (after ${titles} title rows)` : ""}.`,
      ),
    },
    {
      code: "units",
      status: "info",
      ms: 1,
      message:
        spec.unit_multiplier !== 1
          ? both((l) =>
              l === "sq"
                ? `U gjet njësia '(000 lekë)' në ${spec.unit_columns.length} kolona: vlerat shumëzohen me ${n(spec.unit_multiplier, l)}.`
                : `Found the unit '(000 lekë)' in ${spec.unit_columns.length} columns: values are multiplied by ${n(spec.unit_multiplier, l)}.`,
            )
          : { sq: "Nuk u gjet njësi shumëzuese në tituj.", en: "No unit multiplier found in the headers." },
    },
    {
      code: "exclude",
      status: "ok",
      ms: 2,
      message: spec.excluded.length
        ? both((l) => {
            const parts = [
              titles ? (l === "sq" ? `${titles} titull` : `${titles} title`) : null,
              totals.length ? (l === "sq" ? `${totals.length} total ('${totals[0].text}')` : `${totals.length} total ('${totals[0].text}')`) : null,
            ].filter(Boolean);
            return l === "sq"
              ? `U përjashtuan ${spec.excluded.length} rreshta: ${parts.join(", ")}.${totals.length ? " Totali ruhet për barazim." : ""}`
              : `Excluded ${spec.excluded.length} rows: ${parts.join(", ")}.${totals.length ? " The total is kept for reconciliation." : ""}`;
          })
        : { sq: "Nuk ka rreshta titulli, bosh ose totali për të përjashtuar.", en: "No title, blank or total rows to exclude." },
    },
    {
      code: "pii",
      status: "ok",
      ms: 9,
      message: dropped.length
        ? both((l) =>
            l === "sq"
              ? `${dropped.length} kolona personale u hoqën para profilizimit dhe para AI: ${dropped.map((d) => `${d.name} (${PII_LABEL[d.pii!].sq})`).join(", ")}.`
              : `${dropped.length} personal columns removed before profiling and before AI: ${dropped.map((d) => `${d.name} (${PII_LABEL[d.pii!].en})`).join(", ")}.`,
          )
        : { sq: "Nuk u gjetën kolona personale.", en: "No personal columns found." },
    },
    {
      code: "profile",
      status: "ok",
      ms: 14,
      message: both((l) =>
        l === "sq"
          ? `${kept.length} kolona u profilizuan: ${typeText(l)}.`
          : `Profiled ${kept.length} columns: ${typeText(l)}.`,
      ),
    },
    {
      code: "recipe",
      status: match.kind === "drift" ? "warn" : match.kind === "hit" ? "ok" : "info",
      ms: 1,
      message:
        match.kind === "hit"
          ? {
              sq: `U gjet receta ${match.recipe.id} për këtë format: përputhja rikthehet pa AI.`,
              en: `Found recipe ${match.recipe.id} for this format: the mapping is reused without AI.`,
            }
          : match.kind === "drift"
            ? {
                sq: `Formati ka ndryshuar krahasuar me recetën ${match.recipe.id}: 1 kolonë e riemërtuar, 1 e shtuar. Kërkohet konfirmim.`,
                en: `The format changed compared with recipe ${match.recipe.id}: 1 renamed column, 1 added. Confirmation needed.`,
              }
            : {
                sq: `Nuk ka recetë të ruajtur për këtë format (gjurma ${spec.fingerprint}).`,
                en: `No saved recipe for this format (fingerprint ${spec.fingerprint}).`,
              },
    },
    {
      code: "mapping",
      status: match.kind === "hit" ? "ok" : "warn",
      ms: match.kind === "hit" ? 1 : 6,
      message:
        match.kind === "hit"
          ? both((l) =>
              l === "sq"
                ? `Përputhja nga receta: ${kept.length} kolona me besueshmëri 1,0.`
                : `Mapping from the recipe: ${kept.length} columns at confidence 1.0.`,
            )
          : {
              sq: "AI nuk është aktive: përputhje me rregulla (sinonime dhe ngjashmëri). Besueshmëria kufizohet në 0,6, ndaj çdo kolonë kërkon një klikim.",
              en: "AI is not active: rule-based mapping (synonyms and similarity). Confidence is capped at 0.6, so every column needs a click.",
            },
    },
  ];

  const question: IngestPreview["question"] =
    match.kind === "drift" && spec.drift_of
      ? {
          column: spec.drift_of.question_column,
          text: {
            sq: `Kolona '${spec.drift_of.question_column}' zëvendëson 'Sasia (ton)' të recetës së ruajtur? Zgjidhni kuptimin e saj.`,
            en: `Does the column '${spec.drift_of.question_column}' replace the saved recipe's 'Sasia (ton)'? Choose its meaning.`,
          },
          options: [
            { field: "tonnes", label: fieldLabel("waste", "tonnes") },
            { field: null, label: { sq: "Injoro kolonën", en: "Ignore the column" } },
          ],
        }
      : null;

  const warnings: L10n[] = [];
  if (match.kind !== "hit") {
    warnings.push({
      sq: "Mënyra RREGULLA: asnjë e dhënë nuk u dërgua te një model AI.",
      en: "RULES mode: nothing was sent to an AI model.",
    });
  }

  return {
    preview_id: previewId,
    filename: spec.sample,
    file_hash: sample?.hash ?? spec.fingerprint,
    size_bytes: sample?.size_bytes ?? 0,
    synthetic: sample?.synthetic ?? true,
    dataset: { key: dataset.key, name: dataset.name, confidence: 0.92 },
    dataset_candidates: [
      { key: dataset.key, score: 0.92 },
      ...(Object.keys(DATASETS) as DatasetKey[])
        .filter((k) => k !== dataset.key)
        .slice(0, 2)
        .map((k, i) => ({ key: k, score: 0.31 - i * 0.08 })),
    ],
    sheet: spec.sheet,
    header_row: spec.header_row,
    data_rows: spec.data_rows,
    unit_multiplier: spec.unit_multiplier,
    unit_note:
      spec.unit_multiplier !== 1
        ? {
            sq: `Kolonat ${spec.unit_columns.map((c) => `'${c}'`).join(" dhe ")} janë në mijë lekë: gjatë ngarkimit shumëzohen me 1.000.`,
            en: `Columns ${spec.unit_columns.map((c) => `'${c}'`).join(" and ")} are in thousands of lek: they are multiplied by 1,000 on load.`,
          }
        : null,
    excluded_rows: spec.excluded,
    columns,
    mapping,
    question,
    recipe: {
      hit: match.kind === "hit",
      recipe_id: match.kind === "none" ? null : match.recipe.id,
      fingerprint: spec.fingerprint,
      drift:
        match.kind === "drift" && spec.drift_of
          ? { renamed: spec.drift_of.renamed, missing: spec.drift_of.missing, added: spec.drift_of.added }
          : null,
    },
    llm: { used: false, model: null, latency_ms: null, cost_usd: null, error: null, sent: null },
    steps,
    warnings,
  };
}

/** Build the LoadReceipt for a committed preview. `unlocked`/`coverage` come from the engine. */
export function buildReceipt(
  spec: FileSpec,
  opts: {
    sourceId: string;
    mapping: { column: string; field: string | null }[];
    recipe: LoadReceipt["recipe"];
    unlocked: LoadReceipt["indicators_unlocked"];
    coverage: LoadReceipt["coverage"];
    loadedAt: string;
  },
): SourceInfo {
  const sample = sampleDef(spec.sample);
  const byReason = new Map<string, number>();
  for (const e of spec.excluded) byReason.set(e.reason, (byReason.get(e.reason) ?? 0) + 1);
  return {
    source_id: opts.sourceId,
    filename: spec.sample,
    file_hash: sample?.hash ?? spec.fingerprint,
    dataset: spec.dataset,
    dataset_name: DATASETS[spec.dataset].name,
    synthetic: sample?.synthetic ?? true,
    rows_read: spec.data_rows + spec.excluded.length,
    rows_loaded: spec.data_rows,
    rows_excluded: [...byReason.entries()].map(([reason, count]) => ({
      reason,
      count,
      label: EXCLUDED_LABEL[reason] ?? { sq: reason, en: reason },
    })),
    reconciliation: spec.reconcile.map((r) => ({
      field: r.field,
      label: fieldLabel(spec.dataset, r.field),
      file_total: r.file_total,
      loaded_sum: r.loaded_sum,
      ok: r.file_total == null || r.file_total === r.loaded_sum,
      note: r.note ?? null,
    })),
    pii_dropped: spec.columns.filter((c) => c.pii).map((c) => c.name),
    unit_multiplier: spec.unit_multiplier,
    llm: { used: false, model: null, latency_ms: null, cost_usd: null },
    recipe: opts.recipe,
    indicators_unlocked: opts.unlocked,
    coverage: opts.coverage,
    loaded_at: opts.loadedAt,
    duration_ms: spec.format === "xlsx" ? Math.round(642 + spec.data_rows / 8) : 118,
    mapping: opts.mapping,
  };
}

/** Default mapping the seed used for preloaded files (rules, confirmed by the seed script). */
export const defaultMapping = (spec: FileSpec) =>
  spec.columns.filter((c) => !c.pii).map((c) => ({ column: c.name, field: c.field }));
