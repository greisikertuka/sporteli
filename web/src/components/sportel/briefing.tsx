"use client";

import { ArrowUpRight, Download, FileSpreadsheet, Printer } from "lucide-react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { Popover } from "radix-ui";
import { useMemo, useState } from "react";

import { useApi } from "@/hooks/use-api";
import type { IndicatorSummary, Passport } from "@/lib/api";
import { exportXlsxUrl, getPassport, openDataCsvUrl } from "@/lib/client";
import { formatDate, formatDateTime, formatIndicatorValue, formatPeriod, formatTarget, pick, summariseRanges } from "@/lib/format";
import { groupIndicatorsByArea, leadershipSummary } from "@/lib/labels";
import { downloadReplayCsv } from "@/lib/replay-export";

import { SportelMark } from "../app-sidebar";
import { useSystem } from "./system-context";
import { CodeChip, ErrorState, LoadingBlock, PageHeader, SyntheticMark } from "./ui";

type Note = { n: number; indicator: IndicatorSummary; passport: Passport | undefined };

/** First row ranges of a lineage entry, with "+N more" when the list is long. */
function rangeText(ranges: string, tp: (key: "rangesMore", values: { count: number }) => string) {
  const r = summariseRanges(ranges);
  return r.more > 0 ? `${r.text} ${tp("rangesMore", { count: r.more })}` : r.text;
}

function ValueChip({ note, children }: { note: Note; children: React.ReactNode }) {
  const t = useTranslations("briefing");
  const tp = useTranslations("passport");
  const locale = useLocale();
  const p = note.passport;
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button type="button" className="value-chip" aria-label={t("chipOpen", { value: String(children) })}>
          <span className="value-chip-number">{children}</span>
          <sup aria-hidden>{note.n}</sup>
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="source-popover" sideOffset={6} collisionPadding={12}>
          <p className="popover-kicker">{t("chipVersion", { code: note.indicator.code, version: note.indicator.version })}</p>
          <dl>
            {(p?.lineage.length ? p.lineage : note.indicator.sources.map((s) => ({ ...s, row_ranges: "–", row_count: 0, file_hash: "" }))).map((l) => (
              <div key={`${l.source_id}-${l.row_ranges}`}>
                <dt>{t("chipSource")}</dt>
                <dd className="mono">{l.filename}</dd>
                <dt>{t("chipRows")}</dt>
                <dd className="mono">{rangeText(l.row_ranges, tp)}</dd>
              </div>
            ))}
          </dl>
          <p className="popover-formula">{t("chipFormula")}</p>
          {p && <p className="popover-formula-text">{pick(p.formula, locale)}</p>}
          <Link href={`/indicators/${encodeURIComponent(note.indicator.code)}`} className="text-button">
            {note.indicator.code}
            <ArrowUpRight aria-hidden />
          </Link>
          <Popover.Arrow className="popover-arrow" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function BriefingScreen() {
  const t = useTranslations("briefing");
  const tc = useTranslations("common");
  const tb = useTranslations("board");
  const tp = useTranslations("passport");
  const locale = useLocale();
  const { board, replay } = useSystem();
  const [generatedAt] = useState(() => new Date().toISOString());
  const data = board.data;
  const computable = useMemo(() => (data?.indicators ?? []).filter((i) => i.state === "computable"), [data]);
  const codesKey = computable.map((i) => i.code).join(",");
  const passports = useApi(codesKey ? `briefing:${codesKey}` : null, () =>
    Promise.all(computable.map((i) => getPassport(i.code))),
  );

  const notes = useMemo(() => {
    const map = new Map<string, Note>();
    const groups = data ? groupIndicatorsByArea(data.indicators) : [];
    let n = 0;
    for (const g of groups) {
      for (const i of g.items) {
        if (i.state !== "computable") continue;
        n += 1;
        map.set(i.code, { n, indicator: i, passport: passports.data?.find((p) => p.code === i.code) });
      }
    }
    return map;
  }, [data, passports.data]);

  if (!data) {
    return (
      <>
        <PageHeader kicker={t("kicker")} title={t("title")} description={t("description")} />
        {board.error ? <ErrorState error={board.error} onRetry={board.reload} /> : <LoadingBlock label={t("noData")} rows={6} />}
      </>
    );
  }

  const lead = leadershipSummary(data);
  const groups = groupIndicatorsByArea(data.indicators);
  const period = formatPeriod(data.as_of?.slice(0, 7) ?? null, locale);
  const blockedIndicators = new Set(lead.owed.flatMap((o) => o.indicators.map((i) => i.code))).size;
  const signals = data.indicators.flatMap((i) => i.signals.map((s) => ({ ...s, code: i.code })));
  const files = new Map<string, boolean>();
  for (const i of computable) for (const s of i.sources) files.set(s.filename, s.synthetic);

  const sentence = (i: IndicatorSummary) => {
    const note = notes.get(i.code);
    const unitLabel = pick(i.unit_label, locale);
    const value = formatIndicatorValue(i.value, i.unit, locale, unitLabel).text;
    const v = (chunks: React.ReactNode) => (note ? <ValueChip note={note}>{chunks}</ValueChip> : <strong>{chunks}</strong>);
    const periodText = formatPeriod(i.period, locale);
    if (i.target != null && i.status && i.status !== "no_target") {
      return t.rich("sentenceTarget", {
        name: pick(i.name, locale),
        value,
        period: periodText,
        status: i.status === "on_track" ? t("statusOn") : t("statusOff"),
        target: formatTarget(i.target, i.unit, locale, unitLabel, i.direction),
        v,
      });
    }
    return t.rich("sentenceNoTarget", { name: pick(i.name, locale), value, period: periodText, v });
  };

  return (
    <>
      <PageHeader
        kicker={t("kicker")}
        title={t("title")}
        description={t("description")}
        actions={
          <>
            <button type="button" className="civic-button primary" onClick={() => window.print()}>
              <Printer aria-hidden />
              {tc("print")}
            </button>
            {replay.replay ? (
              <button type="button" className="civic-button" onClick={() => downloadReplayCsv(data, locale)} title={tb("downloadReplayHint")}>
                <Download aria-hidden />
                {tb("downloadReplayCsv")}
              </button>
            ) : (
              <>
                <a className="civic-button" href={exportXlsxUrl(data.pack)} download>
                  <FileSpreadsheet aria-hidden />
                  {t("downloadXlsx")}
                </a>
                <a className="civic-button" href={openDataCsvUrl()} download>
                  <Download aria-hidden />
                  {t("openData")}
                </a>
              </>
            )}
          </>
        }
      />

      <article className="report-sheet" aria-labelledby="report-heading">
        <header className="report-letter">
          <div className="report-brand">
            <SportelMark size={46} />
            <div>
              <strong>{t("letterhead")}</strong>
              <small>{t("product")}</small>
            </div>
          </div>
          <div className="report-flags">
            {computable.some((i) => i.sources.some((s) => s.synthetic)) && <SyntheticMark />}
            <span className="report-draft">{t("draft")}</span>
          </div>
        </header>

        <h2 id="report-heading" className="report-heading">
          {t("heading")}
        </h2>
        <p className="report-period">{t("period", { period, date: formatDate(data.as_of, locale) })}</p>

        <section className="report-block report-summary-block">
          <h3>{t("summary")}</h3>
          <p className="report-lede">
            {t.rich("summaryCoverage", {
              computable: data.coverage.computable,
              total: data.coverage.total,
              v: (chunks) => <strong className="lede-count">{chunks}</strong>,
            })}
          </p>
          <p>{t("summaryOff", { count: lead.offTrack.length })}</p>
          {lead.offTrack.length > 0 && (
            <ul className="report-list">
              {lead.offTrack.map((o) => {
                const i = data.indicators.find((x) => x.code === o.code)!;
                return <li key={o.code}>{sentence(i)}</li>;
              })}
            </ul>
          )}
          <p>{t("summaryGaps", { count: lead.owed.reduce((s, o) => s + o.datasets.length, 0), indicators: blockedIndicators })}</p>
          {lead.owed.length > 0 && (
            <ul className="report-list">
              {lead.owed.flatMap((o) =>
                o.datasets.map((d) => (
                  <li key={`${o.ownerKey}-${d.key}`}>{t("gapItem", { dataset: pick(d.name, locale), owner: pick(o.owner, locale) })}</li>
                )),
              )}
            </ul>
          )}
        </section>

        {groups.map((g) => (
          <section key={g.key} className="report-block">
            <h3>{pick(g.name, locale)}</h3>
            <ul className="report-list">
              {g.items.map((i) =>
                i.state === "computable" ? (
                  <li key={i.code}>
                    <CodeChip>{i.code}</CodeChip> {sentence(i)}
                  </li>
                ) : (
                  <li key={i.code} className="report-missing">
                    <CodeChip>{i.code}</CodeChip>{" "}
                    {t("sentenceMissing", {
                      name: pick(i.name, locale),
                      dataset: pick(i.missing[0]?.name, locale),
                      owner: pick(i.missing[0]?.owner, locale),
                    })}
                  </li>
                ),
              )}
            </ul>
          </section>
        ))}

        {signals.length > 0 && (
          <section className="report-block">
            <h3>{t("signalsTitle")}</h3>
            <ul className="report-list">
              {signals.map((s, index) => (
                <li key={`${s.code}-${s.rule}-${index}`}>
                  <CodeChip>{s.code}</CodeChip> {pick(s.message, locale)}
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="report-block report-sources">
          <h3>{t("sourcesTitle")}</h3>
          {passports.error ? <ErrorState error={passports.error} onRetry={passports.reload} /> : null}
          <ol className="footnotes">
            {[...notes.values()].map((note) => (
              <li key={note.indicator.code} value={note.n}>
                <span className="fn-code">{note.indicator.code}</span>{" "}
                {(note.passport?.lineage ?? []).map((l) => `${l.filename} · ${rangeText(l.row_ranges, tp)}`).join(" ; ") ||
                  note.indicator.sources.map((s) => s.filename).join(" ; ")}{" "}
                <span className="fn-version">v{note.indicator.version}</span>
              </li>
            ))}
          </ol>
          <p className="fine-print">
            {[...files.entries()].map(([f, synthetic]) => `${f}${synthetic ? ` (${tc("synthetic")})` : ""}`).join(" · ")}
          </p>
        </section>

        <footer className="report-footer">
          <p>{t("footer")}</p>
          <p>{t("generatedAt", { time: formatDateTime(generatedAt, locale) })}</p>
        </footer>
      </article>
    </>
  );
}
