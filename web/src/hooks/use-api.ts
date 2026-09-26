"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { dataVersionStore, replayStore, type ReplayMode } from "@/lib/client";

/** Current REPLAY mode (live API vs fixtures), shared by every component. */
export function useReplayMode(): ReplayMode {
  return useSyncExternalStore(replayStore.subscribe, replayStore.getSnapshot, replayStore.getServerSnapshot);
}

/** Bumps whenever `broadcastRefresh()` runs in this tab or another one. */
export function useDataVersion(): number {
  return useSyncExternalStore(dataVersionStore.subscribe, dataVersionStore.getSnapshot, dataVersionStore.getServerSnapshot);
}

type Settled<T> = { request: string; data?: T; error?: unknown };

export type ApiState<T> = {
  data: T | undefined;
  error: unknown;
  /** True while the latest request has not settled; previous data stays visible. */
  loading: boolean;
  reload: () => void;
};

/**
 * Fetch with `loader` whenever `key` changes or the data version bumps. The last
 * good data is kept during refetches ("refetch keeps the frame"). Pass `null` as
 * the key to skip fetching.
 */
export function useApi<T>(key: string | null, loader: () => Promise<T>, opts: { live?: boolean } = {}): ApiState<T> {
  const version = useDataVersion();
  const [tick, setTick] = useState(0);
  const [settled, setSettled] = useState<Settled<T>>({ request: "" });
  const loaderRef = useRef(loader);
  useEffect(() => {
    loaderRef.current = loader;
  });

  const request = key == null ? "" : `${key}#${opts.live === false ? 0 : version}#${tick}`;

  useEffect(() => {
    if (!request) return;
    let active = true;
    loaderRef.current().then(
      (data) => {
        if (active) setSettled({ request, data });
      },
      (error: unknown) => {
        if (active) setSettled((prev) => ({ request, data: prev.data, error }));
      },
    );
    return () => {
      active = false;
    };
  }, [request]);

  const reload = useCallback(() => setTick((n) => n + 1), []);

  return {
    data: settled.data,
    error: settled.request === request ? settled.error : undefined,
    loading: Boolean(request) && settled.request !== request,
    reload,
  };
}

/** Poll a loader on an interval (used for /health). */
export function usePolling(reload: () => void, ms: number) {
  useEffect(() => {
    const id = setInterval(reload, ms);
    return () => clearInterval(id);
  }, [reload, ms]);
}

/** `prefers-reduced-motion`, reactive. */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(
    (fn) => {
      if (typeof window === "undefined" || !window.matchMedia) return () => {};
      const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
      mq.addEventListener("change", fn);
      return () => mq.removeEventListener("change", fn);
    },
    () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)").matches : false),
    () => false,
  );
}
