/** REPLAY fixtures: health, LLM call log and eval summary (RULES mode: no key on this machine). */
import type { AskEval, Health, LlmCalls } from "../api";

export const HEALTH: Health = {
  status: "ok",
  db: true,
  llm: false,
  mode: "rules",
  version: "0.2.0-replay",
  spent_usd: 0,
  budget_usd: 20,
  synthetic: true,
};

/** No key, no calls: the log is honestly empty in RULES mode. */
export const LLM_CALLS: LlmCalls = { spent_usd: 0, budget_usd: 20, mode: "rules", calls: [] };

/**
 * Shape of `api/eval_result.json` for a RULES-mode run of the 24-question golden set
 * (12 sq + 12 en). Shown only under the REPLAY badge; the live API serves the real file.
 */
export const EVAL: AskEval = {
  run_at: "2026-09-26T01:10:00Z",
  commit: null,
  mode: "rules",
  by_label: [
    { label: "verified", matched: 8, total: 8 },
    { label: "not_answerable", matched: 8, total: 8 },
    { label: "blocked", matched: 4, total: 4 },
    { label: "exploratory", matched: 0, total: 4 },
  ],
};
