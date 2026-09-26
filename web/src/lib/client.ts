/**
 * Data access for every screen.
 *
 * Each call goes to the live API first. If the API cannot be reached at all (a
 * network error, never an HTTP error) the call is answered by the REPLAY engine in
 * `lib/fixtures`, and the replay store flips so the header shows a REPLAY badge.
 * Nothing falls back silently. `NEXT_PUBLIC_USE_FIXTURES=1` forces REPLAY.
 *
 * After an ingest commit, a demo reset or a basis change, `broadcastRefresh()` bumps
 * a data version (in this tab and, via BroadcastChannel, in other open tabs) so the
 * board, header counters and lists refetch.
 */
import * as live from "./api";
import {
  NetworkError,
  type AskBody,
  type CommitBody,
  type PopulationBasis,
} from "./api";

export const FORCE_FIXTURES = process.env.NEXT_PUBLIC_USE_FIXTURES === "1";

type Fixtures = typeof import("./fixtures/index.ts");
let fixturesModule: Promise<Fixtures> | null = null;
const fixtures = () => (fixturesModule ??= import("./fixtures/index.ts"));

// ---------------------------------------------------------------- replay store

export type ReplayMode = { replay: boolean; reason: "forced" | "offline" | null };

const FORCED: ReplayMode = { replay: true, reason: "forced" };
const LIVE: ReplayMode = { replay: false, reason: null };
const OFFLINE: ReplayMode = { replay: true, reason: "offline" };

let mode: ReplayMode = FORCE_FIXTURES ? FORCED : LIVE;
const modeListeners = new Set<() => void>();

function setMode(next: ReplayMode) {
  if (FORCE_FIXTURES || next === mode) return;
  const flipped = next.replay !== mode.replay;
  mode = next;
  modeListeners.forEach((fn) => fn());
  // Live ⇄ REPLAY: refetch everything so no screen keeps data from the other source.
  if (flipped) bump();
}

export const replayStore = {
  subscribe(fn: () => void) {
    modeListeners.add(fn);
    return () => modeListeners.delete(fn);
  },
  getSnapshot: (): ReplayMode => mode,
  getServerSnapshot: (): ReplayMode => (FORCE_FIXTURES ? FORCED : LIVE),
};

/** While the API was unreachable recently, skip straight to REPLAY (health re-probes). */
const OFFLINE_GRACE_MS = 8_000;
let offlineSince = 0;

async function withFallback<T>(liveCall: () => Promise<T>, replayCall: (fx: Fixtures) => Promise<T>, probe = false): Promise<T> {
  if (FORCE_FIXTURES) return replayCall(await fixtures());
  if (!probe && mode.replay && Date.now() - offlineSince < OFFLINE_GRACE_MS) {
    return replayCall(await fixtures());
  }
  try {
    const result = await liveCall();
    setMode(LIVE);
    return result;
  } catch (error) {
    if (error instanceof NetworkError) {
      offlineSince = Date.now();
      setMode(OFFLINE);
      return replayCall(await fixtures());
    }
    throw error;
  }
}

// ---------------------------------------------------------------- refresh bus

let dataVersion = 0;
const versionListeners = new Set<() => void>();
let channel: BroadcastChannel | null = null;

function bump() {
  dataVersion += 1;
  versionListeners.forEach((fn) => fn());
}

function ensureChannel() {
  if (channel || typeof window === "undefined" || typeof BroadcastChannel === "undefined") return;
  try {
    channel = new BroadcastChannel("sportel-data");
    channel.onmessage = () => bump();
  } catch {
    channel = null;
  }
}

export const dataVersionStore = {
  subscribe(fn: () => void) {
    ensureChannel();
    versionListeners.add(fn);
    return () => versionListeners.delete(fn);
  },
  getSnapshot: () => dataVersion,
  getServerSnapshot: () => 0,
};

/** Tell every screen (and other tabs) that the data changed. */
export function broadcastRefresh(reason: "ingest" | "reset" | "basis" | "recipes") {
  bump();
  try {
    ensureChannel();
    channel?.postMessage({ reason, at: Date.now() });
  } catch {
    // Other tabs will refresh on their next poll.
  }
}

// ---------------------------------------------------------------- endpoints

export const getHealth = () =>
  withFallback(
    () => live.getHealth(),
    (fx) => fx.getHealth(),
    true,
  );
export const getBoard = (pack = "core_kpi") => withFallback(() => live.getBoard(pack), (fx) => fx.getBoard(pack));
export const getPassport = (code: string) => withFallback(() => live.getPassport(code), (fx) => fx.getPassport(code));
export const getLineage = (code: string, limit = 50) =>
  withFallback(() => live.getLineage(code, limit), (fx) => fx.getLineage(code, limit));
export const getDatasets = () => withFallback(() => live.getDatasets(), (fx) => fx.getDatasets());
export const getSamples = () => withFallback(() => live.getSamples(), (fx) => fx.getSamples());
export const previewUpload = (file: File) =>
  withFallback(() => live.previewUpload(file), (fx) => fx.previewUpload(file));
export const previewSample = (name: string) =>
  withFallback(() => live.previewSample(name), (fx) => fx.previewSample(name));

/** A preview produced by REPLAY (`fx-` id) is always committed by REPLAY. */
export async function commitIngest(body: CommitBody) {
  const receipt = body.preview_id.startsWith("fx-")
    ? await (await fixtures()).commitIngest(body)
    : await withFallback(() => live.commitIngest(body), (fx) => fx.commitIngest(body));
  broadcastRefresh("ingest");
  return receipt;
}
export const getSources = () => withFallback(() => live.getSources(), (fx) => fx.getSources());
export async function resetDemo() {
  const result = await withFallback(() => live.resetDemo(), (fx) => fx.resetDemo());
  broadcastRefresh("reset");
  return result;
}
export async function deleteRecipes() {
  const result = await withFallback(() => live.deleteRecipes(), (fx) => fx.deleteRecipes());
  broadcastRefresh("recipes");
  return result;
}
export const getCoverage = (pack = "al_smp") => withFallback(() => live.getCoverage(pack), (fx) => fx.getCoverage(pack));
export async function setPopulationBasis(value: PopulationBasis, reason?: string) {
  const result = await withFallback(
    () => live.setPopulationBasis(value, reason),
    (fx) => fx.setPopulationBasis(value),
  );
  broadcastRefresh("basis");
  return result;
}
export const ask = (body: AskBody) => withFallback(() => live.ask(body), (fx) => fx.ask(body));
export const getExamples = () => withFallback(() => live.getExamples(), (fx) => fx.getExamples());
export const getEval = () => withFallback(() => live.getEval(), (fx) => fx.getEval());
export const getLlmCalls = () => withFallback(() => live.getLlmCalls(), (fx) => fx.getLlmCalls());

/** REPLAY-only recipe count (the live API exposes recipes through source receipts). */
export async function replayRecipeCount() {
  return (await fixtures()).recipeCount();
}

export { exportXlsxUrl, openDataCsvUrl } from "./api";
