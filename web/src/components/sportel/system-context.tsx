"use client";

import { createContext, useContext } from "react";

import { useApi, usePolling, useReplayMode, type ApiState } from "@/hooks/use-api";
import type { Health, IndicatorBoard } from "@/lib/api";
import { getBoard, getHealth, type ReplayMode } from "@/lib/client";

type SystemState = {
  health: ApiState<Health>;
  board: ApiState<IndicatorBoard>;
  replay: ReplayMode;
};

const SystemContext = createContext<SystemState | null>(null);

const HEALTH_POLL_MS = 20_000;

/**
 * Health (API status, AI mode, synthetic flag) and the core_kpi board, shared by the
 * header counters and the screens so they always agree. Both refetch when
 * `broadcastRefresh()` fires (ingest commit, demo reset, basis change).
 */
export function SystemProvider({ children }: { children: React.ReactNode }) {
  const health = useApi("health", getHealth);
  usePolling(health.reload, HEALTH_POLL_MS);
  const board = useApi("board:core_kpi", () => getBoard("core_kpi"));
  const replay = useReplayMode();
  return <SystemContext.Provider value={{ health, board, replay }}>{children}</SystemContext.Provider>;
}

export function useSystem(): SystemState {
  const ctx = useContext(SystemContext);
  if (!ctx) throw new Error("useSystem must be used inside <SystemProvider>");
  return ctx;
}
