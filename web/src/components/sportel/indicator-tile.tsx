"use client";

import {
  AlertTriangle,
  ArrowUpRight,
  FileQuestion,
  Stamp,
} from "lucide-react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";

import type { IndicatorSummary } from "@/lib/api";
import { formatDelta, formatIndicatorValue, formatPeriod, formatTarget, pick } from "@/lib/format";
import { statusTone } from "@/lib/labels";

import { CodeChip, Sparkline, SyntheticMark } from "./ui";

/** "SMP-AL 2024 #47" → "SMP #47" on the tile; the full reference stays in the title. */
const shortSmp = (ref: string) => ref.split("·")[0].replace(/^SMP-AL\s*\d{4}\s*/i, "SMP ").trim();

export function IndicatorTile({
  indicator: i,
  fresh,
  onOpen,
  index,
}: {
  indicator: IndicatorSummary;
  fresh: boolean;
  onOpen: (code: string) => void;
  index: number;
}) {
  const t = useTranslations("tile");
  const tb = useTranslations("board.basis");
  const locale = useLocale();
  const name = pick(i.name, locale);
  const style = { "--i": index } as React.CSSProperties;

  if (i.state !== "computable") {
    return (
      <article className="tile tile-gap" style={style} data-state={i.state}>
        <div className="tile-top">
          <CodeChip>{i.code}</CodeChip>
          {i.smp_ref && (
            <span className="tile-smp" title={i.smp_ref}>
              {shortSmp(i.smp_ref)}
            </span>
          )}
          <FileQuestion className="tile-gap-icon" aria-hidden />
        </div>
        <h3 className="tile-name">
          <button type="button" className="tile-hit" onClick={() => onOpen(i.code)} aria-label={t("open", { name })}>
            {name}
          </button>
        </h3>
        <div className="tile-gap-body">
          {i.missing.map((m) => (
            <div key={m.dataset} className="tile-gap-item">
              <span className="tile-gap-label">{t("missing")}</span>
              <strong>{pick(m.name, locale)}</strong>
              <span className="tile-gap-owner">{t("owner", { owner: pick(m.owner, locale) })}</span>
            </div>
          ))}
        </div>
        <Link
          className="tile-cta"
          href={`/ingest?dataset=${encodeURIComponent(i.missing[0]?.dataset ?? "")}`}
        >
          {t("upload")}
          <ArrowUpRight aria-hidden />
        </Link>
      </article>
    );
  }

  const unitLabel = pick(i.unit_label, locale);
  const value = formatIndicatorValue(i.value, i.unit, locale, unitLabel);
  const delta = formatDelta(i.value, i.previous, i.unit, locale);
  const tone = statusTone(i.status);
  const targetText =
    i.target != null
      ? t(i.direction === "lower_better" ? "targetMax" : "target", { value: formatTarget(i.target, i.unit, locale, unitLabel) })
      : null;
  const warnSignals = i.signals.filter((s) => s.severity === "warn" && s.rule !== "off_target");
  const synthetic = i.sources.some((s) => s.synthetic);

  return (
    <article className={`tile tile-proof ${fresh ? "is-fresh" : ""}`} style={style} data-status={i.status ?? "none"}>
      <div className="tile-top">
        <CodeChip>{i.code}</CodeChip>
        {i.smp_ref && (
            <span className="tile-smp" title={i.smp_ref}>
              {shortSmp(i.smp_ref)}
            </span>
          )}
        {warnSignals.length > 0 && (
          <span className="tile-signal">
            <AlertTriangle aria-hidden />
            {t("signals", { count: warnSignals.length })}
          </span>
        )}
        <span className="tile-stamp" aria-hidden>
          <Stamp />
          {t("proven")}
        </span>
      </div>
      <h3 className="tile-name">
        <button type="button" className="tile-hit" onClick={() => onOpen(i.code)} aria-label={t("open", { name })}>
          {name}
        </button>
      </h3>
      <div className="tile-figure-row">
        <p className="tile-figure">
          <span className="figure-number">{value.number}</span>
          {value.unit && <span className={`figure-unit ${value.tight ? "tight" : ""}`}>{value.unit}</span>}
        </p>
        <Sparkline points={i.sparkline} target={i.target} tone={tone} />
      </div>
      <p className={`tile-status tone-text-${tone}`}>
        <span className="status-dot" aria-hidden />
        {t(i.status ?? "no_target")}
        {targetText && <span className="tile-target"> · {targetText}</span>}
      </p>
      {delta && <p className="tile-delta">{t("vsPrevious", { delta: delta.text })}</p>}
      <footer className="tile-foot">
        {synthetic && <SyntheticMark compact />}
        <span className="tile-period">{formatPeriod(i.period, locale, "short")}</span>
        {i.basis && <span className="tile-basis">{t("basis", { basis: tb(i.basis === "civil_registry" ? "civil_registry" : "census_2023") })}</span>}
        <span className="tile-draft">{t("draft")}</span>
      </footer>
    </article>
  );
}
