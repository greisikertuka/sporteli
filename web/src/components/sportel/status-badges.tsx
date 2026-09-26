"use client";

import { Cpu, FlaskConical, History, ListChecks } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { useSystem } from "@/components/sportel/system-context";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

function Hint({ label, children }: { label: string; children: React.ReactElement }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent className="max-w-72 text-pretty">{label}</TooltipContent>
    </Tooltip>
  );
}

/** Header status: proof counter, synthetic data, AI mode, REPLAY. */
export function StatusBadges() {
  const t = useTranslations("header");
  const ts = useTranslations("shell");
  const { health, board, replay } = useSystem();
  const h = health.data;
  const coverage = board.data?.coverage;

  return (
    <div className="status-badges" role="group" aria-label={ts("status")}>
      {coverage && (
        <Hint label={t("coverageHint")}>
          <Link href="/" className="status-pill proof" aria-live="polite">
            <ListChecks aria-hidden />
            <span>{t("coverage", { computable: coverage.computable, total: coverage.total })}</span>
          </Link>
        </Hint>
      )}
      {h?.synthetic && (
        <Hint label={t("syntheticHint")}>
          <span className="status-pill synthetic" tabIndex={0}>
            <FlaskConical aria-hidden />
            <span>{t("synthetic")}</span>
          </span>
        </Hint>
      )}
      {h && (
        <Hint label={h.mode === "live" ? t("aiLiveHint") : t("aiRulesHint")}>
          <span className={`status-pill ai ${h.mode === "live" ? "live" : "rules"}`} tabIndex={0}>
            {h.mode === "live" ? <span className="live-dot" aria-hidden /> : <Cpu aria-hidden />}
            <span>{h.mode === "live" ? t("aiLive") : t("aiRules")}</span>
          </span>
        </Hint>
      )}
      {replay.replay && (
        <Hint label={replay.reason === "forced" ? t("replayForcedHint") : t("replayOfflineHint")}>
          <span className="status-pill replay" tabIndex={0} role="status">
            <History aria-hidden />
            <span>{t("replay")}</span>
          </span>
        </Hint>
      )}
      <ApiStatus compact />
    </div>
  );
}

function useApiState() {
  const t = useTranslations();
  const { health, replay } = useSystem();
  const state = replay.reason === "forced" ? "forced" : replay.replay ? "offline" : health.data ? "online" : "checking";
  const label =
    state === "online"
      ? t("header.apiOnline")
      : state === "offline"
        ? t("header.apiOffline")
        : state === "forced"
          ? t("header.apiForced")
          : t("header.apiChecking");
  return { state, label, version: state === "online" ? health.data?.version : undefined };
}

/** API status (live / offline / REPLAY forced), in the header and the footer. */
export function ApiStatus({ compact = false }: { compact?: boolean }) {
  const t = useTranslations();
  const { state, label, version } = useApiState();
  return (
    <span className={`api-status ${state} ${compact ? "compact status-pill" : ""}`} role={compact ? undefined : "status"}>
      <span className="api-dot" aria-hidden />
      {label}
      {!compact && version && <span className="api-version">{t("shell.version", { version })}</span>}
    </span>
  );
}
