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
import { formatIndicatorValue, formatPeriod, formatTarget, indicatorDelta, pick } from "@/lib/format";
import { statusTone } from "@/lib/labels";

import { CodeChip, Sparkline, SyntheticMark } from "./ui";

/** "SMP-AL 2024 #47" → "SMP #47" on the tile; the full reference stays in the title. */
const shortSmp = (ref: string) => ref.split("·")[0].replace(/^SMP-AL\s*\d{4}\s*/i, "SMP ").trim();

/** The SMP chip. An internal view (FIN-01 ≈ #47, computed officially by AMVV) reads "≈ SMP #47 ·
 * internal view" with a dashed border, so it never looks like an SMP value Sportel computes. */
export function SmpChip({ indicator: i }: { indicator: Pick<IndicatorSummary, "smp_ref" | "smp_kind" | "smp_note"> }) {
  const t = useTranslations("tile");
  const locale = useLocale();
  if (!i.smp_ref) return null;
  if (i.smp_kind === "internal_view") {
    const note = i.smp_note ? pick(i.smp_note, locale) : "";
    return (
      <span className="tile-smp internal" title={note ? `${i.smp_ref} · ${note}` : i.smp_ref}>
        ≈ {shortSmp(i.smp_ref)} · {t("smpInternal")}
      </span>
    );
  }
  return (
    <span className="tile-smp" title={i.smp_ref}>
      {shortSmp(i.smp_ref)}
    </span>
  );
}

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
          <SmpChip indicator={i} />
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
              <span className="tile-gap-owner" title={t("ownerPlaceholder")}>
                {t("owner", { owner: pick(m.owner, locale) })}
              </span>
            </div>
          ))}
        </div>
        <Link
          className="tile-cta"
          href={`/ingest?dataset=${encodeURIComponent(i.missing[0]?.dataset ?? "")}&ask=${encodeURIComponent(i.code)}`}
        >
          {t("upload")}
          <ArrowUpRight aria-hidden />
        </Link>
      </article>
    );
  }

  const unitLabel = pick(i.unit_label, locale);
  const value = formatIndicatorValue(i.value, i.unit, locale, unitLabel);
  const delta = indicatorDelta(i, locale);
  const deltaText = delta ? `${delta.text}${delta.points ? ` ${t("pp")}` : ""}` : null;
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
        <SmpChip indicator={i} />
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
      {delta && deltaText && (
        <p className="tile-delta">
          {delta.kind === "month" && delta.month
            ? t("inMonth", { delta: deltaText, month: delta.month })
            : t("vsPrevious", { delta: deltaText })}
        </p>
      )}
      <footer className="tile-foot">
        {synthetic && <SyntheticMark compact />}
        <span className="tile-period">{formatPeriod(i.period, locale, "short")}</span>
        {i.basis && <span className="tile-basis">{t("basis", { basis: tb(i.basis === "civil_registry" ? "civil_registry" : "census_2023") })}</span>}
        <span className="tile-draft">{t("draft")}</span>
      </footer>
    </article>
  );
}
