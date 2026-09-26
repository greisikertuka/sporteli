/**
 * Typed client for the Sportel API (`/api/v1`).
 *
 * The types below are copied verbatim from the build contract
 * (docs/superpowers/specs/2026-09-26-gap-to-proof-build.md §7). Keep them in sync:
 * the backend's Pydantic models serialise to exactly these keys.
 *
 * This module only talks to the live API. The REPLAY fallback to fixtures lives in
 * `lib/client.ts`, so every call site decides nothing about fallbacks by itself.
 */

// ---------------------------------------------------------------- contract §7

export type L10n = { sq: string; en: string };
export type Owner = { key: string; name: L10n };

// GET /health
export type Health = {
  status: "ok";
  db: boolean;
  llm: boolean;
  mode: "live" | "rules";
  version: string;
  spent_usd: number;
  budget_usd: number;
  synthetic: boolean;
};

// GET /datasets
export type DatasetInfo = {
  key: string;
  name: L10n;
  owner: Owner;
  table: string;
  loaded: boolean;
  sources: number;
  rows: number;
  fields: { key: string; label: L10n; type: "string" | "date" | "int" | "float"; required: boolean }[];
  unlocks: string[];
};

// GET /samples ; POST /samples/{name}/preview  (server-side sample files, for the hosted demo)
export type SampleFile = {
  name: string;
  label: L10n;
  dataset_hint: string;
  envelope: number | null;
  preload: boolean;
  size_bytes: number;
  synthetic: boolean;
  loaded: boolean;
};

// POST /ingest/preview  (multipart field "file")
export type IngestStep = { code: string; status: "ok" | "warn" | "info"; message: L10n; ms?: number | null };
export type ColumnProfile = {
  index: number;
  name: string;
  inferred_type: "string" | "date" | "int" | "float" | "empty";
  samples: string[];
  null_pct: number;
  pii: null | "name" | "phone" | "email" | "personal_id" | "address";
  dropped: boolean;
};
export type MappingSuggestion = {
  column: string;
  field: string | null;
  confidence: number;
  reason: L10n;
  transform?: string | null;
  source: "recipe" | "ai" | "rules" | "user";
};
export type IngestPreview = {
  preview_id: string;
  filename: string;
  file_hash: string;
  size_bytes: number;
  synthetic: boolean;
  dataset: { key: string; name: L10n; confidence: number } | null;
  dataset_candidates: { key: string; score: number }[];
  sheet: string | null;
  header_row: number;
  data_rows: number;
  unit_multiplier: number;
  unit_note: L10n | null;
  excluded_rows: { row_no: number; reason: "total_row" | "blank" | "title" | "subtotal"; text: string }[];
  columns: ColumnProfile[];
  mapping: MappingSuggestion[];
  question: { column: string; text: L10n; options: { field: string | null; label: L10n }[] } | null;
  recipe: {
    hit: boolean;
    recipe_id: string | null;
    fingerprint: string;
    drift: { renamed: string[]; missing: string[]; added: string[] } | null;
  };
  llm: {
    used: boolean;
    model: string | null;
    latency_ms: number | null;
    cost_usd: number | null;
    error: string | null;
    sent: { headers: number; samples_per_column: number; rows_sent: 0 } | null;
  };
  steps: IngestStep[];
  warnings: L10n[];
};

// POST /ingest/commit
export type CommitBody = {
  preview_id: string;
  dataset: string;
  mapping: { column: string; field: string | null }[];
  save_recipe?: boolean;
};
export type LoadReceipt = {
  source_id: string;
  filename: string;
  file_hash: string;
  dataset: string;
  dataset_name: L10n;
  synthetic: boolean;
  rows_read: number;
  rows_loaded: number;
  rows_excluded: { reason: string; count: number; label: L10n }[];
  reconciliation: {
    field: string;
    label: L10n;
    file_total: number | null;
    loaded_sum: number;
    ok: boolean;
    note: L10n | null;
  }[];
  pii_dropped: string[];
  unit_multiplier: number;
  llm: { used: boolean; model: string | null; latency_ms: number | null; cost_usd: number | null };
  recipe: { saved: boolean; reused: boolean; recipe_id: string | null };
  indicators_unlocked: { code: string; name: L10n }[];
  coverage: { computable: number; total: number };
  loaded_at: string;
  duration_ms: number;
} & LoadAudit;

/**
 * Additive audit fields the API also returns on receipts and sources (contract §7,
 * "Additive fields"). Optional: no screen may depend on them, and REPLAY drops them.
 */
export type LoadAudit = {
  sheet?: string | null;
  header_row?: number;
  steps?: IngestStep[];
  column_errors?: { field: string; column: string; count: number; rows: string }[];
  superseded?: { source_id: string; filename: string; rows: number; source_removed: boolean }[];
  mapping?: { column: string; field: string | null }[];
};

// GET /sources -> SourceInfo[]
export type SourceInfo = LoadReceipt & { mapping: { column: string; field: string | null }[] };

// POST /demo/reset ; DELETE /ingest/recipes
export type ResetResult = {
  ok: true;
  coverage: { computable: number; total: number };
  /** Additive: one line per preloaded file. */
  loaded?: { source_id: string; filename: string; dataset: string; rows_loaded: number; reconciled: boolean }[];
};
export type DeleteRecipesResult = { ok: true; deleted: number };

// GET /indicators?pack=core_kpi
export type IndicatorState = "computable" | "missing" | "document" | "national" | "manual";
export type Signal = { rule: string; severity: "info" | "warn"; message: L10n; period: string | null };
export type IndicatorSummary = {
  code: string;
  area: { key: string; name: L10n };
  name: L10n;
  unit: string;
  unit_label: L10n;
  state: IndicatorState;
  value: number | null;
  period: string | null;
  previous: number | null;
  target: number | null;
  direction: "higher_better" | "lower_better" | "none";
  status: "on_track" | "off_track" | "no_target" | null;
  owner: Owner;
  missing: { dataset: string; name: L10n; owner: L10n }[];
  signals: Signal[];
  sources: { source_id: string; filename: string; synthetic: boolean }[];
  smp_ref: string | null;
  version: string;
  formula_status: "draft" | "from_source" | "validated";
  basis: string | null;
  sparkline: { period: string; value: number | null }[];
};
export type PopulationBasis = "census_2023" | "civil_registry";
export type IndicatorBoard = {
  pack: string;
  as_of: string | null;
  coverage: { computable: number; missing: number; document: number; national: number; total: number };
  basis: { population: PopulationBasis };
  indicators: IndicatorSummary[];
};

// GET /indicators/{code}
export type Passport = IndicatorSummary & {
  formula: L10n;
  question: L10n;
  sql: string | null;
  series: { period: string; value: number | null }[];
  lineage: { source_id: string; filename: string; file_hash: string; row_count: number; row_ranges: string }[];
  required_datasets: string[];
  checks: { rule: string; label: L10n; passed: boolean; message: L10n | null }[];
  computed_at: string | null;
};

// GET /indicators/{code}/lineage?limit=50
export type LineageRows = {
  code: string;
  columns: string[];
  total: number;
  rows: { source_file: string; row_no: number; values: Record<string, string | number | null> }[];
};

// GET|POST /definitions/population_basis
export type PopulationBasisBody = { value: PopulationBasis; reason?: string };
export type PopulationBasisPin = {
  ok: true;
  key: "population_basis";
  value: PopulationBasis;
  label: L10n;
  reason: string | null;
  pinned_at: string | null;
  options: { value: PopulationBasis; label: L10n; residents: number | null }[];
  indicators: { code: string; name: L10n; value: number | null; period: string | null; basis: PopulationBasis }[];
};

// GET /coverage?pack=al_smp
export type CoverageItem = {
  number: number;
  area: L10n;
  name_sq: string;
  state: IndicatorState;
  passport_code: string | null;
  owner: L10n | null;
  note: L10n | null;
};
export type Coverage = {
  pack: "al_smp";
  label: L10n;
  approval: "pending" | "approved";
  counts: Record<IndicatorState, number>;
  total: number;
  items: CoverageItem[];
};

// POST /ask
export type AskBody = { question: string; locale: "sq" | "en"; example_id?: string };
export type AskLabel = "verified" | "exploratory" | "blocked" | "not_answerable";
export type AskAnswer = {
  label: AskLabel;
  question: string;
  interpreted_as: L10n;
  answer: L10n;
  value: number | null;
  unit: string | null;
  passport_code: string | null;
  sql: string | null;
  table: { columns: string[]; rows: (string | number | null)[][] } | null;
  sources: { source_id: string; filename: string; rows: string }[];
  gap: { dataset: string; name: L10n; owner: L10n; sample: string | null } | null;
  blocked_reason: L10n | null;
  llm: { used: boolean; model: string | null; latency_ms: number | null; cost_usd: number | null; cached: boolean };
};
// GET /ask/examples
export type AskExample = {
  id: string;
  question: L10n;
  passport_code: string | null;
  kind: "verified" | "gap" | "exploratory" | "blocked";
};
// GET /ask/eval (404 if never run)
export type AskEval = {
  run_at: string;
  commit: string | null;
  mode: "live" | "rules";
  by_label: { label: AskLabel; matched: number; total: number }[];
  /** Additive detail written by `api/scripts/run_eval.py` (optional for clients). */
  dirty?: boolean;
  total?: { matched: number; total: number };
  golden?: { version: number; questions: number; sq: number; en: number; tolerance_pct: number };
  ingest?: { file: string; dataset: string; rows_loaded: number }[];
  llm?: { calls: number; cost_usd: number };
  items?: {
    id: string;
    locale: string;
    stage: string;
    question: string;
    expected: AskLabel;
    got: AskLabel;
    passport_code: string | null;
    value: number | null;
    expected_value: number | null;
    ok: boolean;
    problems: string[];
  }[];
};

// GET /llm/calls
export type LlmCall = {
  ts: string;
  purpose: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
  ok: boolean;
  error: string | null;
  sent: unknown;
};
export type LlmCalls = { spent_usd: number; budget_usd: number; mode: "live" | "rules"; calls: LlmCall[] };

// Errors: { "detail": { "code": string, "message": L10n } } with 4xx status.
// Request-validation failures (422 invalid_request) also list the offending fields.
export type ApiErrorBody = {
  detail: { code: string; message: L10n; errors?: { loc: (string | number)[]; type: string; msg: string }[] };
};

// ---------------------------------------------------------------- transport

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
export const API_BASE = `${API_URL}/api/v1`;

/** An HTTP error returned by the API (4xx/5xx). Network failures are `NetworkError`. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: L10n | null;

  constructor(status: number, code: string, message: string, detail: L10n | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

/** The API could not be reached at all (server down, DNS, CORS, offline). */
export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

function isL10n(value: unknown): value is L10n {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as L10n).sq === "string" &&
    typeof (value as L10n).en === "string"
  );
}

async function toApiError(res: Response, label: string): Promise<ApiError> {
  let code = `http_${res.status}`;
  let detail: L10n | null = null;
  try {
    const body = (await res.json()) as Partial<ApiErrorBody> | { detail?: unknown };
    const d = (body as { detail?: unknown }).detail;
    if (d && typeof d === "object" && "code" in d) {
      const typed = d as ApiErrorBody["detail"];
      code = typed.code ?? code;
      detail = isL10n(typed.message) ? typed.message : null;
    } else if (typeof d === "string") {
      detail = { sq: d, en: d };
    }
  } catch {
    // Non-JSON error body: keep the status code only.
  }
  return new ApiError(res.status, code, `${label} failed: ${res.status}`, detail);
}

async function request<T>(method: string, path: string, init?: RequestInit): Promise<T> {
  const label = `${method} ${path}`;
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...init, method });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new NetworkError(`${label}: ${(error as Error)?.message ?? "network error"}`);
  }
  if (!res.ok) throw await toApiError(res, label);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>("GET", path, init);
}

export function apiPost<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
  return request<T>("POST", path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function apiPostForm<T>(path: string, form: FormData, init?: RequestInit): Promise<T> {
  // No Content-Type header: the browser sets the multipart boundary.
  return request<T>("POST", path, { ...init, body: form });
}

export function apiDelete<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>("DELETE", path, init);
}

// ---------------------------------------------------------------- endpoints

const q = (value: string | number) => encodeURIComponent(String(value));

export const getHealth = (init?: RequestInit) => apiGet<Health>("/health", init);
export const getBoard = (pack = "core_kpi", init?: RequestInit) =>
  apiGet<IndicatorBoard>(`/indicators?pack=${q(pack)}`, init);
export const getPassport = (code: string, init?: RequestInit) =>
  apiGet<Passport>(`/indicators/${q(code)}`, init);
export const getLineage = (code: string, limit = 50, init?: RequestInit) =>
  apiGet<LineageRows>(`/indicators/${q(code)}/lineage?limit=${q(limit)}`, init);
export const getDatasets = (init?: RequestInit) => apiGet<DatasetInfo[]>("/datasets", init);
export const getSamples = (init?: RequestInit) => apiGet<SampleFile[]>("/samples", init);
export function previewUpload(file: File, init?: RequestInit) {
  const form = new FormData();
  form.append("file", file, file.name);
  return apiPostForm<IngestPreview>("/ingest/preview", form, init);
}
export const previewSample = (name: string, init?: RequestInit) =>
  apiPost<IngestPreview>(`/samples/${q(name)}/preview`, undefined, init);
export const commitIngest = (body: CommitBody, init?: RequestInit) =>
  apiPost<LoadReceipt>("/ingest/commit", body, init);
export const getSources = (init?: RequestInit) => apiGet<SourceInfo[]>("/sources", init);
export const resetDemo = (init?: RequestInit) => apiPost<ResetResult>("/demo/reset", undefined, init);
export const deleteRecipes = (init?: RequestInit) =>
  apiDelete<DeleteRecipesResult>("/ingest/recipes", init);
export const getCoverage = (pack = "al_smp", init?: RequestInit) =>
  apiGet<Coverage>(`/coverage?pack=${q(pack)}`, init);
export const getPopulationBasis = (init?: RequestInit) =>
  apiGet<PopulationBasisPin>("/definitions/population_basis", init);
export const setPopulationBasis = (value: PopulationBasis, reason?: string, init?: RequestInit) =>
  apiPost<PopulationBasisPin>(
    "/definitions/population_basis",
    { value, ...(reason ? { reason } : {}) } satisfies PopulationBasisBody,
    init,
  );
export const ask = (body: AskBody, init?: RequestInit) => apiPost<AskAnswer>("/ask", body, init);
export const getExamples = (init?: RequestInit) => apiGet<AskExample[]>("/ask/examples", init);
export const getEval = (init?: RequestInit) => apiGet<AskEval>("/ask/eval", init);
export const getLlmCalls = (init?: RequestInit) => apiGet<LlmCalls>("/llm/calls", init);

/** Direct download links (plain anchors; the browser handles the file). */
export const exportXlsxUrl = (pack = "core_kpi") => `${API_BASE}/export/${q(pack)}.xlsx`;
export const openDataCsvUrl = () => `${API_BASE}/open-data/indicators.csv`;
