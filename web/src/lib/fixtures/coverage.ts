/**
 * REPLAY for the SMP 2024 Annex A coverage pack (al_smp, contract §3).
 *
 * Composed from recorded API responses only: every item comes from `GET /coverage` after a
 * reset; an item mapped to a core passport is swapped for its full-state recording (state
 * `computable`, the passport owner, the population basis in the note) while that passport
 * is computable in the replay state, and for the civil-registry recording when that basis
 * is pinned. Counts are recounted over the composed items.
 */
import type { Coverage, CoverageItem, PopulationBasis } from "../api.ts";
import { countCoverage } from "../labels.ts";
import { SNAPSHOT } from "./snapshot.ts";

const byNumber = (items: CoverageItem[]) => new Map(items.map((i) => [i.number, i]));
const FULL = byNumber(SNAPSHOT.coverage.full);
const CIVIL = byNumber(SNAPSHOT.coverage.civil_registry);

export function buildCoverage(computable: (code: string) => boolean, basis: PopulationBasis): Coverage {
  const start = SNAPSHOT.coverage.start;
  const items = start.items.map((item) => {
    const full = FULL.get(item.number);
    if (!full?.passport_code || !computable(full.passport_code)) return item;
    return (basis === "civil_registry" ? CIVIL.get(item.number) : undefined) ?? full;
  });
  const { counts, total } = countCoverage(items);
  return { ...start, counts, total, items };
}
