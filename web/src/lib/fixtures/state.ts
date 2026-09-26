/** Mutable REPLAY state shared by the fixture modules (reset on page reload or demo reset). */
import type { IngestPreview, PopulationBasis, SourceInfo } from "../api";
import type { DatasetKey } from "./catalog.ts";

export type Recipe = { id: string; dataset: DatasetKey; fingerprint: string; from_filename: string; columns: string[] };

export type PreviewEntry = { preview: IngestPreview; sample: string };

export type ReplayState = {
  /** Currently loaded datasets and the receipt of the source that fed each. */
  loaded: Map<DatasetKey, SourceInfo>;
  /** Saved mapping recipes by dataset. */
  recipes: Map<DatasetKey, Recipe>;
  basis: PopulationBasis;
  previews: Map<string, PreviewEntry>;
  seq: number;
};
