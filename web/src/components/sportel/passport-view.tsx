"use client";

import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  CircleDashed,
  FileSpreadsheet,
  Fingerprint,
  Upload,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";

import { useApi } from "@/hooks/use-api";
import type { Passport } from "@/lib/api";
import { getDatasets, getLineage, getPassport } from "@/lib/client";
import {
  formatCell,
  formatDateTime,
  formatDelta,
  formatIndicatorValue,
  formatNumber,
  formatPeriod,
  formatTarget,
  pick,
  summariseRanges,
} from "@/lib/format";
import { statusTone } from "@/lib/labels";

import { TrendChart } from "./trend-chart";
import { CodeChip, ErrorState, LoadingBlock, SqlBlock, SyntheticMark, ToneChip } from "./ui";

function FormulaStatus({ status }: { status: Passport["formula_status"] }) {
  const t = useTranslations("passport");
  return (
    <ToneChip tone={status === "validated" ? "success" : status === "from_source" ? "info" : "warning"} className="formula-status">
      <CircleDashed aria-hidden />
      {status === "draft" ? t("draft") : t(status)}
    </ToneChip>
  );
}

export function PassportView({
  code,
  variant,
  onNavigate,
}: {
  code: string;
  variant: "drawer" | "page";
  onNavigate?: () => void;
}) {
  const t = useTranslations();
  const locale = useLocale();
  const passport = useApi(`passport:${code}`, () => getPassport(code));
  const p = passport.data?.code === code ? passport.data : undefined;
  const computable = p?.state === "computable";
  const lineage = useApi(computable ? `lineage:${code}` : null, () => getLineage(code, 12));
  const rows = lineage.data?.code === code ? lineage.data : undefined;
  const datasets = useApi("datasets", getDatasets);
  const datasetName = (key: string) => {
    const d = datasets.data?.find((x) => x.key === key);
    return d ? pick(d.name, locale) : key;
  };

  if (!p) {
    if (passport.error) return <ErrorState error={passport.error} onRetry={passport.reload} />;
    return <LoadingBlock label={t("common.loading")} rows={6} />;
  }

  const value = formatIndicatorValue(p.value, p.unit, locale, pick(p.unit_label, locale));
  const delta = formatDelta(p.value, p.previous, p.unit, locale);
  const tone = statusTone(p.status);
  const targetText =
    p.target != null
      ? formatTarget(p.target, p.unit, locale, pick(p.unit_label, locale), p.direction)
      : null;

  return (
    <article className={`passport passport-${variant}`} aria-busy={passport.loading}>
      <header className="passport-head">
        <p className="kicker">{t("passport.kicker", { version: p.version })}</p>
        <div className="passport-chips">
          <CodeChip>{p.code}</CodeChip>
          <span className="passport-area">{pick(p.area.name, locale)}</span>
          {p.smp_ref && <ToneChip tone="info">{p.smp_ref}</ToneChip>}
        </div>
        {variant === "page" ? (
          <h1 className="display-title passport-title">{pick(p.name, locale)}</h1>
        ) : (
          <h2 className="display-title passport-title">{pick(p.name, locale)}</h2>
        )}
        <div className="passport-status-row">
          <FormulaStatus status={p.formula_status} />
          <span className="passport-owner">
            <UserRound aria-hidden />
            {t("passport.owner")}: {pick(p.owner.name, locale)}
          </span>
        </div>
        {p.formula_status === "draft" && <p className="passport-hint">{t("passport.draftHint")}</p>}
      </header>

      {computable ? (
        <section className="passport-value" aria-label={t("passport.value")}>
          <div className="passport-figure">
            <span className="figure-number">{value.number}</span>
            {value.unit && <span className={`figure-unit ${value.tight ? "tight" : ""}`}>{value.unit}</span>}
          </div>
          <dl className="passport-facts">
            <div>
              <dt>{t("passport.period")}</dt>
              <dd>{formatPeriod(p.period, locale)}</dd>
            </div>
            <div>
              <dt>{t("passport.status")}</dt>
              <dd>
                <ToneChip tone={tone}>{t(`tile.${p.status ?? "no_target"}`)}</ToneChip>
              </dd>
            </div>
            {targetText && (
              <div>
                <dt>{t("passport.target")}</dt>
                <dd>{targetText}</dd>
              </div>
            )}
            {delta && (
              <div>
                <dt>{t("passport.previous")}</dt>
                <dd>
                  {formatIndicatorValue(p.previous, p.unit, locale, pick(p.unit_label, locale)).text}{" "}
                  <span className="muted">({delta.text})</span>
                </dd>
              </div>
            )}
            {p.basis && (
              <div>
                <dt>{t("passport.basis")}</dt>
                <dd>{t(`board.basis.${p.basis === "civil_registry" ? "civil_registry" : "census_2023"}`)}</dd>
              </div>
            )}
          </dl>
        </section>
      ) : (
        <section className="passport-missing" aria-label={t("passport.missingTitle")}>
          <h3>{t("passport.missingTitle")}</h3>
          {p.missing.map((m) => (
            <div key={m.dataset} className="passport-missing-item">
              <p>{t("passport.missingBody", { name: pick(m.name, locale), owner: pick(m.owner, locale) })}</p>
              <Link className="civic-button primary" href={`/ingest?dataset=${encodeURIComponent(m.dataset)}`} onClick={onNavigate}>
                <Upload aria-hidden />
                {t("tile.upload")}
              </Link>
            </div>
          ))}
        </section>
      )}

      {computable && p.series.length > 0 && (
        <section className="passport-block">
          <h3>{t("passport.series")}</h3>
          <TrendChart
            series={p.series}
            unit={p.unit}
            unitLabel={pick(p.unit_label, locale)}
            target={p.target}
            name={pick(p.name, locale)}
            height={variant === "page" ? 280 : 220}
          />
        </section>
      )}

      {p.signals.length > 0 && (
        <section className="passport-block">
          <h3>{t("board.signals.title")}</h3>
          <ul className="signal-list">
            {p.signals.map((s, i) => (
              <li key={`${s.rule}-${i}`}>
                <AlertTriangle aria-hidden />
                <span>
                  {pick(s.message, locale)}
                  <small>{s.rule}</small>
                </span>
              </li>
            ))}
          </ul>
          <p className="fine-print">{t("board.signals.note")}</p>
        </section>
      )}

      <section className="passport-block passport-formula">
        <h3>{t("passport.formula")}</h3>
        <p>{pick(p.formula, locale)}</p>
        <p className="passport-question">
          <span>{t("passport.question")}:</span> {pick(p.question, locale)}
        </p>
      </section>

      {p.sql && (
        <section className="passport-block">
          <SqlBlock sql={p.sql} title={t("passport.sql")} />
        </section>
      )}

      {p.lineage.length > 0 && (
        <section className="passport-block">
          <h3>{t("passport.lineage")}</h3>
          <ul className="lineage-list">
            {p.lineage.map((l) => {
              const synthetic = p.sources.find((s) => s.source_id === l.source_id)?.synthetic ?? /SINTETIKE/i.test(l.filename);
              const ranges = summariseRanges(l.row_ranges);
              return (
                <li key={`${l.source_id}-${l.row_ranges}`}>
                  <FileSpreadsheet aria-hidden />
                  <div>
                    <span className="lineage-file">{l.filename}</span>
                    <span className="lineage-rows">
                      {t("passport.lineageRows", { rows: formatNumber(l.row_count, locale), count: l.row_count, ranges: ranges.text })}
                      {ranges.more > 0 && <> {t("passport.rangesMore", { count: ranges.more })}</>}
                    </span>
                    {ranges.more > 0 && (
                      <details className="lineage-all">
                        <summary>{t("passport.rangesAll")}</summary>
                        <p>{ranges.all.join(", ")}</p>
                      </details>
                    )}
                    <span className="lineage-hash">
                      <Fingerprint aria-hidden />
                      {t("passport.hash")} {l.file_hash.slice(0, 12)}…
                    </span>
                  </div>
                  {synthetic && <SyntheticMark compact />}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {computable && (
        <section className="passport-block">
          <h3>{t("passport.sourceRows")}</h3>
          {!rows ? (
            lineage.error ? (
              <ErrorState error={lineage.error} onRetry={lineage.reload} />
            ) : (
              <LoadingBlock label={t("passport.loadingRows")} rows={3} />
            )
          ) : (
            <>
              <p className="fine-print">
                {t("passport.sourceRowsNote", { shown: formatNumber(rows.rows.length, locale), total: formatNumber(rows.total, locale) })}
              </p>
              <div className="table-scroll source-rows" tabIndex={0} role="region" aria-label={t("passport.sourceRows")}>
                <table className="data-table compact mono-table">
                  <thead>
                    <tr>
                      <th scope="col">{t("passport.rowNo")}</th>
                      {rows.columns.map((c) => (
                        <th scope="col" key={c} className={typeof rows.rows[0]?.values[c] === "number" ? "numeric" : undefined}>
                          {c}
                        </th>
                      ))}
                      <th scope="col">{t("passport.file")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.rows.map((r) => (
                      <tr key={`${r.source_file}-${r.row_no}`}>
                        <td className="row-no">{r.row_no}</td>
                        {rows.columns.map((c) => (
                          <td key={c} className={typeof r.values[c] === "number" ? "numeric" : ""}>
                            {formatCell(r.values[c], locale)}
                          </td>
                        ))}
                        <td className="file-cell">{r.source_file}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      <section className="passport-block">
        <h3>{t("passport.checks")}</h3>
        {p.checks.length === 0 ? (
          <p className="fine-print">{t("passport.noChecks")}</p>
        ) : (
          <ul className="check-list">
            {p.checks.map((c) => (
              <li key={c.rule} className={c.passed ? "passed" : "flagged"}>
                {c.passed ? <CheckCircle2 aria-hidden /> : <AlertTriangle aria-hidden />}
                <span>
                  <strong>{pick(c.label, locale)}</strong>
                  <em>{c.passed ? t("passport.passed") : t("passport.flagged")}</em>
                  {c.message && <small>{pick(c.message, locale)}</small>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <footer className="passport-foot">
        <dl>
          <div>
            <dt>{t("passport.required")}</dt>
            <dd>{p.required_datasets.map(datasetName).join(" · ")}</dd>
          </div>
          {p.computed_at && (
            <div>
              <dt>{t("passport.computed")}</dt>
              <dd>{formatDateTime(p.computed_at, locale)}</dd>
            </div>
          )}
        </dl>
        {variant === "drawer" ? (
          <Link className="civic-button" href={`/indicators/${encodeURIComponent(p.code)}`} onClick={onNavigate}>
            {t("passport.openPage")}
            <ArrowUpRight aria-hidden />
          </Link>
        ) : (
          <Link className="civic-button" href="/">
            {t("passport.backToBoard")}
          </Link>
        )}
      </footer>
    </article>
  );
}
