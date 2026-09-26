"use client";

import {
  AlertTriangle,
  Building,
  ChevronRight,
  Coins,
  DatabaseZap,
  Download,
  FileSpreadsheet,
  Inbox,
  Landmark,
  Scale,
  Trash2,
  TrendingDown,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { useReducedMotion } from "@/hooks/use-api";
import type { IndicatorBoard, IndicatorState, IndicatorSummary, PopulationBasis } from "@/lib/api";
import { exportXlsxUrl, openDataCsvUrl, setPopulationBasis } from "@/lib/client";
import { downloadReplayCsv } from "@/lib/replay-export";
import { formatDate, formatIndicatorValue, formatTarget, pick } from "@/lib/format";
import {
  groupIndicatorsByArea,
  leadershipSummary,
  newlyComputable,
  stateSnapshot,
} from "@/lib/labels";

import { IndicatorTile } from "./indicator-tile";
import { PassportSheet } from "./passport-sheet";
import { useSystem } from "./system-context";
import { TrendChart } from "./trend-chart";
import { CodeChip, ErrorState, LoadingBlock, PageHeader } from "./ui";

const AREA_ICONS: Record<string, React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>> = {
  requests: Inbox,
  finance: Landmark,
  waste: Trash2,
  revenue: Coins,
  hr: Users,
};

const SNAPSHOT_KEY = "sportel:board-states:v1";

function readSnapshot(): { states: Record<string, IndicatorState>; computable: number } | null {
  try {
    const raw = typeof window !== "undefined" ? window.sessionStorage.getItem(SNAPSHOT_KEY) : null;
    return raw ? (JSON.parse(raw) as { states: Record<string, IndicatorState>; computable: number }) : null;
  } catch {
    return null;
  }
}

function writeSnapshot(board: IndicatorBoard) {
  try {
    window.sessionStorage.setItem(
      SNAPSHOT_KEY,
      JSON.stringify({ states: stateSnapshot(board.indicators), computable: board.coverage.computable }),
    );
  } catch {
    // Storage blocked: the grey→green animation simply does not replay.
  }
}

/** Counts up from `from` to `to` (instant under reduced motion). */
function CountUp({ from, to }: { from: number; to: number }) {
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(from);
  useEffect(() => {
    if (reduced || from === to) {
      const id = requestAnimationFrame(() => setShown(to));
      return () => cancelAnimationFrame(id);
    }
    let raf = 0;
    const start = performance.now();
    const duration = 900;
    const step = (now: number) => {
      const k = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - k, 3);
      setShown(Math.round(from + (to - from) * eased));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [from, to, reduced]);
  return <>{shown}</>;
}

export function Board() {
  const t = useTranslations();
  const locale = useLocale();
  const { board, replay } = useSystem();
  const data = board.data;
  const [openCode, setOpenCode] = useState<string | null>(null);

  // Grey → green: compare with the last snapshot this browser saw.
  const previous = useMemo(() => (data ? readSnapshot() : null), [data]);
  const fresh = useMemo(
    () => new Set(data ? newlyComputable(previous?.states, data.indicators) : []),
    [data, previous],
  );
  useEffect(() => {
    if (data) writeSnapshot(data);
  }, [data]);

  const groups = useMemo(() => (data ? groupIndicatorsByArea(data.indicators) : []), [data]);
  const ordered = useMemo(() => groups.flatMap((g) => g.items), [groups]);
  const lead = useMemo(() => (data ? leadershipSummary(data) : null), [data]);

  if (!data) {
    return (
      <>
        <PageHeader kicker={t("nav.overview")} title={t("board.title")} description={t("board.description")} />
        {board.error ? <ErrorState error={board.error} onRetry={board.reload} /> : <LoadingBlock label={t("board.loading")} rows={5} />}
      </>
    );
  }

  const { computable, total } = data.coverage;
  const fromCount = previous && previous.computable < computable ? previous.computable : computable;

  return (
    <>
      <PageHeader
        kicker={t("board.kicker", { date: formatDate(data.as_of, locale) })}
        title={t("board.title")}
        description={t("board.description")}
        actions={
          <>
            {replay.replay ? (
              <button type="button" className="civic-button primary" onClick={() => downloadReplayCsv(data, locale)} title={t("board.downloadReplayHint")}>
                <Download aria-hidden />
                {t("board.downloadReplayCsv")}
              </button>
            ) : (
              <a className="civic-button primary" href={exportXlsxUrl(data.pack)} download>
                <FileSpreadsheet aria-hidden />
                {t("board.downloadXlsx")}
              </a>
            )}
            {!replay.replay && (
              <a className="civic-button" href={openDataCsvUrl()} download>
                <Download aria-hidden />
                {t("board.openData")}
              </a>
            )}
          </>
        }
      />
      {replay.replay && <p className="replay-note">{t("board.downloadReplayHint")}</p>}

      <section className="proof-hero" aria-label={t("board.counterAria", { computable, total })}>
        <div className="proof-counter">
          <p className="proof-count" aria-live="polite" aria-atomic>
            <span className="sr-only">{t("board.counterAria", { computable, total })}</span>
            <span aria-hidden>
              <strong>
                <CountUp from={fromCount} to={computable} />
              </strong>
              <span className="proof-total">/{total}</span>
            </span>
          </p>
          <p className="proof-label">{t("board.counterLabel")}</p>
          <ol className="proof-meter" aria-label={t("board.meterAria", { total })}>
            {ordered.map((i, index) => (
              <li
                key={i.code}
                data-state={i.state}
                className={fresh.has(i.code) ? "is-fresh" : ""}
                style={{ "--i": index } as React.CSSProperties}
              >
                <button type="button" onClick={() => setOpenCode(i.code)} aria-label={`${i.code} · ${pick(i.name, locale)} · ${i.state === "computable" ? t("tile.proven") : t("tile.missing")}`}>
                  <span>{i.code}</span>
                </button>
              </li>
            ))}
          </ol>
          <p className="proof-note">{t("board.counterNote", { missing: total - computable })}</p>
          {fresh.size > 0 && (
            <p className="proof-fresh" role="status">
              {t("board.newlyProven", { count: fresh.size })}
            </p>
          )}
          <BasisPin basis={data.basis.population} />
        </div>
        {lead && <LeadershipCallout lead={lead} onOpen={setOpenCode} />}
      </section>

      <TrendAndSignals board={data} onOpen={setOpenCode} />

      {groups.map((g) => {
        const Icon = AREA_ICONS[g.key] ?? Building;
        const done = g.items.filter((i) => i.state === "computable").length;
        return (
          <section key={g.key} className="area-section" aria-labelledby={`area-${g.key}`}>
            <div className="area-head">
              <h2 id={`area-${g.key}`}>
                <Icon aria-hidden />
                {pick(g.name, locale)}
              </h2>
              <span className={`area-count ${done === g.items.length ? "complete" : ""}`}>
                {t("board.areaCount", { computable: done, total: g.items.length })}
              </span>
            </div>
            <div className="tile-grid">
              {g.items.map((i) => (
                <IndicatorTile
                  key={i.code}
                  indicator={i}
                  fresh={fresh.has(i.code)}
                  onOpen={setOpenCode}
                  index={ordered.indexOf(i)}
                />
              ))}
            </div>
          </section>
        );
      })}

      <PassportSheet code={openCode} onClose={() => setOpenCode(null)} />
    </>
  );
}

function BasisPin({ basis }: { basis: PopulationBasis }) {
  const t = useTranslations("board.basis");
  const [pending, setPending] = useState<PopulationBasis | null>(null);
  const [announce, setAnnounce] = useState("");
  const choose = async (value: PopulationBasis) => {
    if (value === basis || pending) return;
    setPending(value);
    try {
      await setPopulationBasis(value, "UI: board definition pin");
      setAnnounce(t("changed", { basis: t(value) }));
    } finally {
      setPending(null);
    }
  };
  return (
    <div className="basis-pin">
      <span className="basis-label">
        <Scale aria-hidden />
        {t("label")}
      </span>
      <div className="segmented" role="radiogroup" aria-label={t("label")}>
        {(["census_2023", "civil_registry"] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={basis === value}
            disabled={pending !== null}
            onClick={() => choose(value)}
          >
            {t(value)}
          </button>
        ))}
      </div>
      <span className="basis-hint">{t("hint")}</span>
      <span className="sr-only" aria-live="polite">
        {announce}
      </span>
    </div>
  );
}

function LeadershipCallout({
  lead,
  onOpen,
}: {
  lead: ReturnType<typeof leadershipSummary>;
  onOpen: (code: string) => void;
}) {
  const t = useTranslations("board.lead");
  const tTile = useTranslations("tile");
  const locale = useLocale();
  return (
    <aside className="lead-callout" aria-labelledby="lead-title">
      <h2 id="lead-title">{t("title")}</h2>
      <div className="lead-block">
        <h3>
          <DatabaseZap aria-hidden />
          {t("owedTitle")}
        </h3>
        {lead.owed.length === 0 ? (
          <p className="lead-empty">{t("owedNone")}</p>
        ) : (
          <ol className="lead-list">
            {lead.owed.map((o) => (
              <li key={o.ownerKey}>
                <Link href={`/ingest?dataset=${encodeURIComponent(o.datasets[0]?.key ?? "")}`}>
                  <strong title={tTile("ownerPlaceholder")}>{pick(o.owner, locale)}</strong>
                  <span>
                    {t("owedDetail", {
                      datasets: o.datasets.map((d) => pick(d.name, locale)).join(", "),
                      count: o.indicators.length,
                    })}
                  </span>
                  <ChevronRight aria-hidden />
                </Link>
              </li>
            ))}
          </ol>
        )}
      </div>
      <div className="lead-block">
        <h3>
          <TrendingDown aria-hidden />
          {t("offTitle")}
        </h3>
        {lead.offTrack.length === 0 ? (
          <p className="lead-empty">{t("offNone")}</p>
        ) : (
          <ol className="lead-list">
            {lead.offTrack.map((o) => {
              const unitLabel = pick(o.unit_label, locale);
              return (
                <li key={o.code}>
                  <button type="button" onClick={() => onOpen(o.code)}>
                    <strong>
                      <CodeChip>{o.code}</CodeChip> {pick(o.name, locale)}
                    </strong>
                    <span>
                      {t("offDetail", {
                        value: formatIndicatorValue(o.value, o.unit, locale, unitLabel).text,
                        target: formatTarget(o.target, o.unit, locale, unitLabel, o.direction),
                      })}
                    </span>
                    <ChevronRight aria-hidden />
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </div>
      <p className="fine-print">{t("note")}</p>
    </aside>
  );
}

function TrendAndSignals({ board, onOpen }: { board: IndicatorBoard; onOpen: (code: string) => void }) {
  const t = useTranslations("board");
  const locale = useLocale();
  const candidates = board.indicators.filter((i) => i.state === "computable" && i.sparkline.length > 1);
  const preferred = candidates.find((i) => i.status === "off_track") ?? candidates[0];
  const [selected, setSelected] = useState<string | null>(null);
  const current: IndicatorSummary | undefined = candidates.find((i) => i.code === selected) ?? preferred;
  const signals = board.indicators.flatMap((i) => i.signals.map((s) => ({ ...s, code: i.code })));

  return (
    <div className="trend-row">
      <section className="panel trend-panel" aria-labelledby="trend-title">
        <div className="trend-head">
          <div>
            <h2 id="trend-title">{t("trend.title")}</h2>
            {current && <p className="section-subtitle">{pick(current.name, locale)}</p>}
          </div>
          {candidates.length > 0 && (
            <label className="select-field">
              <span className="sr-only">{t("trend.select")}</span>
              <select value={current?.code ?? ""} onChange={(e) => setSelected(e.target.value)} aria-label={t("trend.select")}>
                {candidates.map((i) => (
                  <option key={i.code} value={i.code}>
                    {i.code} · {pick(i.name, locale)}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {current ? (
          <TrendChart
            key={current.code}
            series={current.sparkline}
            unit={current.unit}
            unitLabel={pick(current.unit_label, locale)}
            target={current.target}
            name={pick(current.name, locale)}
            seriesKind={current.series_kind}
          />
        ) : (
          <p className="fine-print">{t("trend.empty")}</p>
        )}
      </section>
      <section className="panel signals-panel" aria-labelledby="signals-title">
        <h2 id="signals-title">
          {t("signals.title")}
          {signals.length > 0 && <span className="count-badge">{signals.length}</span>}
        </h2>
        {signals.length === 0 ? (
          <p className="fine-print">{t("signals.none")}</p>
        ) : (
          <ul className="signal-feed">
            {signals.map((s, index) => (
              <li key={`${s.code}-${s.rule}-${index}`}>
                <button type="button" onClick={() => onOpen(s.code)}>
                  <AlertTriangle aria-hidden />
                  <span>
                    <CodeChip>{s.code}</CodeChip>
                    <span className="signal-text">{pick(s.message, locale)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="fine-print">{t("signals.note")}</p>
        <Link className="text-button" href="/ingest">
          {t("ingestCta")}
          <ChevronRight aria-hidden />
        </Link>
      </section>
    </div>
  );
}
