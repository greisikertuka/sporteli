/**
 * Shape of the REPLAY snapshot recorded by `web/scripts/record-replay.mjs`. Every field is
 * a real API response (contract §7 keys only), captured in one of three demo states:
 *   start – after `POST /demo/reset` (requests + budget + population, 6/13);
 *   full  – after envelopes 1–3 are committed with recipes (13/13, census basis);
 *   civil_registry – the full state with the population basis pinned to the civil registry.
 */
import type {
  AskAnswer,
  AskEval,
  AskExample,
  Coverage,
  CoverageItem,
  DatasetInfo,
  Health,
  IndicatorBoard,
  IngestPreview,
  LineageRows,
  LlmCalls,
  LoadReceipt,
  Passport,
  SampleFile,
  SourceInfo,
} from "../api";

type ByCode<T> = Record<string, T>;
type BoardMeta = Pick<IndicatorBoard, "pack" | "as_of" | "basis">;

export type ReplaySnapshot = {
  recorded_at: string;
  api_version: string;
  health: Health;
  datasets: DatasetInfo[];
  samples: SampleFile[];
  examples: AskExample[];
  /** `null` when the golden-set evaluation had not been run (the API answers 404). */
  eval: AskEval | null;
  llm_calls: LlmCalls;
  board: { start: BoardMeta; full: BoardMeta };
  passports: {
    start: ByCode<Passport>;
    full: ByCode<Passport>;
    /** Only the passports that use the pinned population basis. */
    civil_registry: ByCode<Passport>;
  };
  /** `GET /indicators/{code}/lineage?limit=20` in the full state. */
  lineage: ByCode<LineageRows>;
  /**
   * `GET /coverage?pack=al_smp` after a reset, then only the items that change in the full
   * state (the SMP items mapped to a passport) and again with the civil-registry basis.
   */
  coverage: { start: Coverage; full: CoverageItem[]; civil_registry: CoverageItem[] };
  /** The preloaded sources after a reset (`GET /sources`). */
  seeds: SourceInfo[];
  sources_full: SourceInfo[];
  previews: {
    /** Before any recipe exists, per sample file name (`preview_id` blanked). */
    fresh: Record<string, IngestPreview>;
    /** Envelope files previewed again after their recipe was saved. */
    recipe_hit: Record<string, IngestPreview>;
    /** The format-drift file previewed while the envelope-1 recipe exists. */
    drift: IngestPreview | null;
  };
  /** Commit receipts per sample file name (envelopes with `save_recipe`, drift without). */
  receipts: Record<string, LoadReceipt>;
  ask: {
    /** Each passport's canonical question, per state. */
    start: ByCode<AskAnswer>;
    full: ByCode<AskAnswer>;
    civil_registry: ByCode<AskAnswer>;
    /** The example chips, per state. */
    examples_start: Record<string, AskAnswer>;
    examples_full: Record<string, AskAnswer>;
    free_text: { unknown: AskAnswer; write: AskAnswer };
  };
};
