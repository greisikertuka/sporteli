"use client";

import { ArrowUpRight, Stamp } from "lucide-react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { useApi } from "@/hooks/use-api";
import type { CoverageItem, IndicatorState } from "@/lib/api";
import { getCoverage } from "@/lib/client";
import { pick } from "@/lib/format";
import { groupBy } from "@/lib/labels";

import { CodeChip, ErrorState, LoadingBlock, PageHeader } from "./ui";

const ORDER: IndicatorState[] = ["computable", "document", "national", "missing", "manual"];
const TONE: Record<IndicatorState, string> = {
  computable: "success",
  document: "info",
  national: "neutral",
  missing: "gap",
  manual: "warning",
};

export function CoverageScreen() {
  const t = useTranslations("coverage");
  const locale = useLocale();
  const coverage = useApi("coverage:al_smp", () => getCoverage("al_smp"));
  const [filter, setFilter] = useState<IndicatorState | "all">("all");
  const data = coverage.data;

  if (!data) {
    return (
      <>
        <PageHeader kicker={t("kicker", { total: 52 })} title={t("title")} description={t("description")} />
        {coverage.error ? <ErrorState error={coverage.error} onRetry={coverage.reload} /> : <LoadingBlock label={t("waffle")} rows={5} />}
      </>
    );
  }

  // "computable" stays visible at 0: it is the number this pilot is meant to move.
  const states = ORDER.filter((s) => s === "computable" || data.counts[s] > 0);
  const visible = data.items.filter((i) => filter === "all" || i.state === filter);
  const groups = groupBy(visible, (i) => i.area.sq);
  const mapped = data.items.filter((i) => i.passport_code && i.state !== "national").length;

  return (
    <>
      <PageHeader kicker={t("kicker", { total: data.total })} title={t("title")} description={t("description")} />

      <div className={`approval-banner ${data.approval}`} role="note">
        <Stamp aria-hidden />
        <div>
          <strong>{data.approval === "pending" ? t("banner") : pick(data.label, locale)}</strong>
          <p>{t("bannerBody")}</p>
        </div>
      </div>

      <section className="coverage-overview" aria-label={t("waffle")} aria-busy={coverage.loading}>
        <div className="coverage-stats">
          {states.map((s) => (
            <button
              key={s}
              type="button"
              className={`coverage-stat tone-${TONE[s]} ${filter === s ? "active" : ""}`}
              aria-pressed={filter === s}
              onClick={() => setFilter(filter === s ? "all" : s)}
            >
              <span className="stat-count">{data.counts[s]}</span>
              <span className="stat-label">{t(`state.${s}`)}</span>
              <span className="stat-hint">{t(`stateHint.${s}`)}</span>
              {s === "computable" && <span className="stat-live">{t("mapped", { count: mapped })}</span>}
            </button>
          ))}
        </div>
        <figure className="waffle-figure">
          <figcaption>
            <strong>{t("waffle")}</strong> · {t("waffleHint")}
          </figcaption>
          <ol className="waffle">
            {data.items.map((item) => {
              return (
                <li
                  key={item.number}
                  data-state={item.state}
                  data-mapped={item.passport_code && item.state === "missing" ? "" : undefined}
                  className={filter !== "all" && item.state !== filter ? "dim" : ""}
                >
                  <a href={`#smp-${item.number}`} aria-label={`${t("number", { n: item.number })} · ${item.name_sq} · ${t(`state.${item.state}`)}`}>
                    {item.number}
                  </a>
                </li>
              );
            })}
          </ol>
          {mapped > 0 && (
            <p className="waffle-legend">
              <i aria-hidden />
              {t("waffleMapped")}
            </p>
          )}
        </figure>
      </section>

      <div className="coverage-filter" role="group" aria-label={t("filterLabel")}>
        <button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>
          {t("filterAll")} <span>{data.total}</span>
        </button>
        {states.map((s) => (
          <button key={s} type="button" aria-pressed={filter === s} onClick={() => setFilter(s)}>
            <i className={`state-dot tone-${TONE[s]}`} aria-hidden />
            {t(`state.${s}`)} <span>{data.counts[s]}</span>
          </button>
        ))}
      </div>

      {groups.map((g) => (
        <section key={g.key} className="coverage-group" aria-labelledby={`cov-${g.items[0].number}`}>
          <h2 id={`cov-${g.items[0].number}`}>
            {pick(g.items[0].area, locale)}
            <span>{t("count", { count: g.items.length })}</span>
          </h2>
          <ul className="coverage-list">
            {g.items.map((item) => (
              <CoverageRow key={item.number} item={item} />
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}

function CoverageRow({ item }: { item: CoverageItem }) {
  const t = useTranslations("coverage");
  const locale = useLocale();
  return (
    <li id={`smp-${item.number}`} className={`coverage-row state-${item.state}`}>
      <span className="coverage-number">#{item.number}</span>
      <div className="coverage-main">
        <span className="coverage-name" lang="sq">
          {item.name_sq}
        </span>
        {item.note && <span className="coverage-note">{pick(item.note, locale)}</span>}
        <span className="coverage-owner">{item.owner ? pick(item.owner, locale) : item.state === "missing" ? t("ownerTbd") : null}</span>
      </div>
      <div className="coverage-side">
        <span className={`state-chip tone-${TONE[item.state]}`}>{t(`state.${item.state}`)}</span>
        {item.passport_code && (
          <Link className="coverage-passport" href={`/indicators/${encodeURIComponent(item.passport_code)}`}>
            <CodeChip>{item.passport_code}</CodeChip>
            {item.state !== "national" && (
              <span className={item.state === "computable" ? "live-yes" : "live-no"}>
                {item.state === "computable" ? t("live") : t("liveMissing")}
              </span>
            )}
            <ArrowUpRight aria-hidden />
          </Link>
        )}
      </div>
    </li>
  );
}
