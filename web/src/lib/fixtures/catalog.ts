/**
 * REPLAY fixtures: catalog of owners, datasets and synthetic sample files.
 * Mirrors contract §1–§2. Every file here is SYNTHETIC ("SINTETIKE") and is only
 * served when the live API is unreachable or NEXT_PUBLIC_USE_FIXTURES=1, always
 * with a visible REPLAY badge.
 */
import type { DatasetInfo, L10n, Owner, SampleFile } from "../api";

export const OWNERS = {
  citizen_relations: {
    key: "citizen_relations",
    name: { sq: "Sektori i Marrëdhënieve me Qytetarët", en: "Citizen Relations Sector" },
  },
  finance: {
    key: "finance",
    name: { sq: "Drejtoria e Financës dhe Buxhetit", en: "Finance and Budget Directorate" },
  },
  public_services: {
    key: "public_services",
    name: { sq: "Drejtoria e Shërbimeve Publike", en: "Public Services Directorate" },
  },
  local_revenue: {
    key: "local_revenue",
    name: { sq: "Drejtoria e të Ardhurave Vendore", en: "Local Revenue Directorate" },
  },
  hr: {
    key: "hr",
    name: { sq: "Drejtoria e Burimeve Njerëzore", en: "Human Resources Directorate" },
  },
  statistics: {
    key: "statistics",
    name: { sq: "Sektori i Statistikës dhe Performancës", en: "Statistics and Performance Sector" },
  },
} satisfies Record<string, Owner>;

export type DatasetKey = "requests" | "budget" | "waste" | "revenue" | "staff" | "population";

export const AREAS: Record<string, L10n> = {
  requests: { sq: "Kërkesat e qytetarëve", en: "Citizen requests" },
  waste: { sq: "Mbetjet dhe pastrimi", en: "Waste and cleaning" },
  revenue: { sq: "Të ardhurat vendore", en: "Local revenue" },
  hr: { sq: "Burimet njerëzore", en: "Human resources" },
  finance: { sq: "Financat", en: "Finance" },
};

type DatasetDef = Omit<DatasetInfo, "loaded" | "sources" | "rows"> & {
  key: DatasetKey;
  /** Name used in gap messages ("Mungon eksporti · …"). */
  exportName: L10n;
  rows: number;
};

const f = (
  key: string,
  sq: string,
  en: string,
  type: "string" | "date" | "int" | "float",
  required = false,
) => ({ key, label: { sq, en }, type, required });

export const DATASETS: Record<DatasetKey, DatasetDef> = {
  requests: {
    key: "requests",
    name: { sq: "Kërkesat e qytetarëve", en: "Citizen requests" },
    exportName: { sq: "Regjistri i kërkesave të qytetarëve", en: "Citizen requests register" },
    owner: OWNERS.citizen_relations,
    table: "request",
    rows: 2392,
    fields: [
      f("request_id", "Nr. i kërkesës", "Request no.", "string", true),
      f("created_at", "Data e regjistrimit", "Registered on", "date", true),
      f("closed_at", "Data e mbylljes", "Closed on", "date"),
      f("category", "Kategoria", "Category", "string", true),
      f("department", "Drejtoria", "Directorate", "string"),
      f("admin_unit", "Njësia administrative", "Administrative unit", "string"),
      f("channel", "Kanali", "Channel", "string"),
      f("status", "Statusi", "Status", "string", true),
      f("sla_days", "Afati (ditë)", "Deadline (days)", "int"),
    ],
    unlocks: ["REQ-01", "REQ-02", "REQ-03", "REQ-04"],
  },
  budget: {
    key: "budget",
    name: { sq: "Zbatimi i buxhetit", en: "Budget execution" },
    exportName: { sq: "Zbatimi i buxhetit sipas programeve", en: "Budget execution by programme" },
    owner: OWNERS.finance,
    table: "budget_line",
    rows: 144,
    fields: [
      f("month", "Muaji", "Month", "date", true),
      f("programme_code", "Kodi i programit", "Programme code", "string", true),
      f("programme", "Programi", "Programme", "string"),
      f("line_type", "Lloji i shpenzimit", "Spending type", "string"),
      f("planned_lek", "Plani (lekë)", "Planned (lek)", "float", true),
      f("actual_lek", "Fakti (lekë)", "Actual (lek)", "float", true),
    ],
    unlocks: ["FIN-01", "FIN-02", "WST-03", "REV-02"],
  },
  waste: {
    key: "waste",
    name: { sq: "Pastrimi dhe mbetjet", en: "Cleaning and waste" },
    exportName: { sq: "Grumbullimi i mbetjeve sipas njësive", en: "Waste collection by unit" },
    owner: OWNERS.public_services,
    table: "waste_collection",
    rows: 104,
    fields: [
      f("month", "Muaji", "Month", "date", true),
      f("admin_unit", "Njësia administrative", "Administrative unit", "string", true),
      f("tonnes", "Sasia (ton)", "Quantity (tonnes)", "float", true),
      f("trips", "Nr. i kursimeve", "Trips", "int"),
      f("households_served", "Familje të mbuluara", "Households served", "int"),
    ],
    unlocks: ["WST-01", "WST-02", "WST-03"],
  },
  revenue: {
    key: "revenue",
    name: { sq: "Taksat dhe tarifat vendore", en: "Local taxes and fees" },
    exportName: { sq: "Arkëtimi i taksave dhe tarifave vendore", en: "Local tax and fee collection" },
    owner: OWNERS.local_revenue,
    table: "revenue",
    rows: 96,
    fields: [
      f("month", "Muaji", "Month", "date", true),
      f("revenue_type", "Lloji i të ardhurës", "Revenue type", "string", true),
      f("payer_type", "Kategoria e paguesit", "Payer category", "string"),
      f("planned_lek", "Plani (lekë)", "Planned (lek)", "float"),
      f("collected_lek", "Arkëtuar (lekë)", "Collected (lek)", "float", true),
    ],
    unlocks: ["REV-01", "REV-02"],
  },
  staff: {
    key: "staff",
    name: { sq: "Burimet njerëzore", en: "Human resources" },
    exportName: { sq: "Numri i punonjësve sipas drejtorive", en: "Staff numbers by directorate" },
    owner: OWNERS.hr,
    table: "staff",
    rows: 9,
    fields: [
      f("department", "Drejtoria", "Directorate", "string", true),
      f("headcount", "Numri i punonjësve", "Headcount", "int", true),
      f("hires", "Pranime", "Hires", "int"),
      f("leavers", "Largime", "Leavers", "int"),
      f("as_of", "Më datë", "As of", "date"),
    ],
    unlocks: ["HR-01", "HR-02"],
  },
  population: {
    key: "population",
    name: { sq: "Popullsia sipas njësive (referencë)", en: "Population by unit (reference)" },
    exportName: { sq: "Popullsia sipas njësive administrative", en: "Population by administrative unit" },
    owner: OWNERS.statistics,
    table: "population",
    rows: 26,
    fields: [
      f("admin_unit", "Njësia administrative", "Administrative unit", "string", true),
      f("basis", "Baza", "Basis", "string", true),
      f("residents", "Banorë", "Residents", "int", true),
    ],
    unlocks: ["WST-02", "HR-01"],
  },
};

/** Synthetic population totals (deliberately NOT the official figures). */
export const POPULATION = { census_2023: 121_400, civil_registry: 208_700 } as const;

export type SampleDef = Omit<SampleFile, "loaded"> & { dataset: DatasetKey; hash: string };

export const SAMPLES: SampleDef[] = [
  {
    name: "01_SINTETIKE_kerkesat_qytetare_jan-gus_2026.xlsx",
    label: { sq: "Kërkesat e qytetarëve, jan–gus 2026", en: "Citizen requests, Jan–Aug 2026" },
    dataset_hint: "requests",
    dataset: "requests",
    envelope: null,
    preload: true,
    size_bytes: 214_880,
    synthetic: true,
    hash: "4be1c0d27a9e3f5518c6d2e0a7b94f13c85d6e2a9f0b7c41d3e8a5f6b2c9d017",
  },
  {
    name: "02_SINTETIKE_zbatimi_buxhetit_jan-gus_2026.xlsx",
    label: { sq: "Zbatimi i buxhetit, jan–gus 2026", en: "Budget execution, Jan–Aug 2026" },
    dataset_hint: "budget",
    dataset: "budget",
    envelope: null,
    preload: true,
    size_bytes: 19_456,
    synthetic: true,
    hash: "a91d3e7c0b5f2846e1d9c3a7f05b8e24d6c1a9e3b7f0d52c8e4a1b6f9d3c7e20",
  },
  {
    name: "ref_SINTETIKE_popullsia_njesite.csv",
    label: { sq: "Popullsia sipas njësive (referencë)", en: "Population by unit (reference)" },
    dataset_hint: "population",
    dataset: "population",
    envelope: null,
    preload: true,
    size_bytes: 1_184,
    synthetic: true,
    hash: "c07e5a1f9d3b2c8e46a0f7d1b9e3c5a2f8d6b0e4c1a7f9d3e5b2c8a0f6d4e1b3",
  },
  {
    name: "zarfi-1_SINTETIKE_pastrimi_mbetjet_2026.csv",
    label: { sq: "Zarfi 1 · Pastrimi dhe mbetjet 2026", en: "Envelope 1 · Cleaning and waste 2026" },
    dataset_hint: "waste",
    dataset: "waste",
    envelope: 1,
    preload: false,
    size_bytes: 5_632,
    synthetic: true,
    hash: "5d2f8b0e3a7c1d9f4e6b2a8c0d5f7e1b3a9c6d2e8f0b4a7c1e5d9f3b6a2c8e04",
  },
  {
    name: "zarfi-2_SINTETIKE_taksat_tarifat_arketimi_2026.xlsx",
    label: {
      sq: "Zarfi 2 · Taksat dhe tarifat, arkëtimi 2026",
      en: "Envelope 2 · Taxes and fees, collection 2026",
    },
    dataset_hint: "revenue",
    dataset: "revenue",
    envelope: 2,
    preload: false,
    size_bytes: 18_432,
    synthetic: true,
    hash: "e8a4c2f6b0d9e1a3c7f5b2d8e0a6c4f1b9d3e7a5c0f2b8d6e4a1c9f3b7d5e2a0",
  },
  {
    name: "zarfi-3_SINTETIKE_burimet_njerezore_2026.xlsx",
    label: { sq: "Zarfi 3 · Burimet njerëzore 2026", en: "Envelope 3 · Human resources 2026" },
    dataset_hint: "staff",
    dataset: "staff",
    envelope: 3,
    preload: false,
    size_bytes: 9_216,
    synthetic: true,
    hash: "b3f7d1a9e5c2f0b8d4a6e2c9f1b7d3a5e0c8f4b2d6a9e1c3f7b5d0a8e2c6f4b1",
  },
  {
    name: "drift_SINTETIKE_pastrimi_mbetjet_2026_v2.csv",
    label: {
      sq: "Formati i ri · Pastrimi dhe mbetjet (v2)",
      en: "New format · Cleaning and waste (v2)",
    },
    dataset_hint: "waste",
    dataset: "waste",
    envelope: null,
    preload: false,
    size_bytes: 6_016,
    synthetic: true,
    hash: "0f6c2a8e4b1d7f3a9c5e0b6d2f8a4c1e7b3d9f5a0c6e2b8d4f1a7c3e9b5d0f2a",
  },
];

export const PRELOADED: DatasetKey[] = ["requests", "budget", "population"];
