"use client";

import { Binary, Cpu, ScrollText, Sparkles } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { useApi } from "@/hooks/use-api";
import { ApiError, type AskLabel, type LlmCall } from "@/lib/api";
import { getEval, getLlmCalls } from "@/lib/client";
import { clampPct, formatDateTime, formatMs, formatNumber, formatUsd } from "@/lib/format";
import { ASK_LABEL_TONE, ASK_LABELS } from "@/lib/labels";

import { LabelStamp } from "./ask";
import { useSystem } from "./system-context";
import { ErrorState, PageHeader, Section } from "./ui";

/** Summarise the `sent` payload of an LLM call without ever printing row data. */
function sentSummary(sent: unknown): { headers: number; samples: number; rows: number } | null {
  if (!sent || typeof sent !== "object") return null;
  const s = sent as Record<string, unknown>;
  const num = (v: unknown) => (typeof v === "number" ? v : Array.isArray(v) ? v.length : null);
  const headers = num(s.headers) ?? num(s.columns);
  if (headers == null) return null;
  return { headers, samples: num(s.samples_per_column) ?? 0, rows: num(s.rows_sent) ?? 0 };
}

export function TrustScreen() {
  const t = useTranslations("trust");
  const locale = useLocale();
  const { health } = useSystem();
  const calls = useApi("llm:calls", getLlmCalls);
  const evaluation = useApi("ask:eval", getEval);
  const mode = calls.data?.mode ?? health.data?.mode ?? "rules";
  const spent = calls.data?.spent_usd ?? health.data?.spent_usd ?? 0;
  const budget = calls.data?.budget_usd ?? health.data?.budget_usd ?? 0;
  const pct = budget > 0 ? clampPct((spent / budget) * 100) : 0;
  const aiItems = t.raw("aiItems") as string[];
  const codeItems = t.raw("codeItems") as string[];
  const limits = t.raw("limits") as string[];
  const evalTotal = evaluation.data?.by_label.reduce((s, r) => s + r.total, 0) ?? 0;

  return (
    <>
      <PageHeader kicker={t("kicker")} title={t("title")} description={t("description")} />

      <section className="duty-split" aria-label={`${t("aiTitle")} / ${t("codeTitle")}`}>
        <div className="duty ai">
          <h2>
            <Sparkles aria-hidden />
            {t("aiTitle")}
          </h2>
          <ul>
            {aiItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="duty-divider" aria-hidden>
          <span>→</span>
        </div>
        <div className="duty code">
          <h2>
            <Binary aria-hidden />
            {t("codeTitle")}
          </h2>
          <ul>
            {codeItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </section>

      <div className="trust-row">
        <section className="panel mode-card" aria-labelledby="mode-title">
          <h2 id="mode-title">{t("modeTitle")}</h2>
          <p className={`mode-flag ${mode}`}>
            {mode === "live" ? <span className="live-dot" aria-hidden /> : <Cpu aria-hidden />}
            {mode === "live" ? "AI LIVE" : locale === "en" ? "RULES" : "RREGULLA"}
          </p>
          <p>{mode === "live" ? t("modeLive") : t("modeRules")}</p>
          <h3>{t("spendTitle")}</h3>
          <div className="spend-meter" role="meter" aria-valuemin={0} aria-valuemax={budget} aria-valuenow={spent} aria-label={t("spendTitle")}>
            <i style={{ width: `${pct}%` }} />
          </div>
          <p className="spend-text">{t("spend", { spent: formatUsd(spent, locale), budget: formatUsd(budget, locale) })}</p>
        </section>

        <section className="panel eval-card" aria-labelledby="eval-title">
          <h2 id="eval-title">{t("evalTitle")}</h2>
          {evaluation.data ? (
            <>
              <ul className="eval-bars">
                {ASK_LABELS.map((label: AskLabel) => {
                  const row = evaluation.data!.by_label.find((r) => r.label === label);
                  if (!row) return null;
                  const share = row.total ? (row.matched / row.total) * 100 : 0;
                  return (
                    <li key={label}>
                      <LabelStamp label={label} />
                      <span className={`eval-track tone-${ASK_LABEL_TONE[label]}`} aria-hidden>
                        <i style={{ width: `${share}%` }} />
                      </span>
                      <span className="eval-value">{t("evalRow", { matched: row.matched, total: row.total })}</span>
                    </li>
                  );
                })}
              </ul>
              <p className="fine-print">
                {t("evalNote", {
                  total: evalTotal,
                  time: formatDateTime(evaluation.data.run_at, locale),
                  mode: evaluation.data.mode,
                })}
              </p>
            </>
          ) : evaluation.error instanceof ApiError && evaluation.error.status === 404 ? (
            <p className="fine-print">{t("evalMissing")}</p>
          ) : evaluation.error ? (
            <ErrorState error={evaluation.error} onRetry={evaluation.reload} />
          ) : null}
        </section>
      </div>

      <Section title={t("logTitle")} description={t("logDescription")}>
        {calls.error ? <ErrorState error={calls.error} onRetry={calls.reload} /> : null}
        {calls.data && calls.data.calls.length === 0 ? (
          <div className="log-empty">
            <ScrollText aria-hidden />
            <p>{t("logEmpty")}</p>
          </div>
        ) : (
          <div className="table-scroll log-table" tabIndex={0} role="region" aria-label={t("logTitle")}>
            <table className="data-table compact">
              <thead>
                <tr>
                  <th scope="col">{t("col.time")}</th>
                  <th scope="col">{t("col.purpose")}</th>
                  <th scope="col">{t("col.model")}</th>
                  <th scope="col" className="numeric">
                    {t("col.tokens")}
                  </th>
                  <th scope="col" className="numeric">
                    {t("col.cost")}
                  </th>
                  <th scope="col" className="numeric">
                    {t("col.latency")}
                  </th>
                  <th scope="col">{t("col.ok")}</th>
                  <th scope="col">{t("col.sent")}</th>
                </tr>
              </thead>
              <tbody>
                {(calls.data?.calls ?? []).map((c: LlmCall, i) => {
                  const sent = sentSummary(c.sent);
                  return (
                    <tr key={`${c.ts}-${i}`}>
                      <td>{formatDateTime(c.ts, locale)}</td>
                      <td>{c.purpose}</td>
                      <td className="mono">{c.model}</td>
                      <td className="numeric">
                        {formatNumber(c.input_tokens, locale)} / {formatNumber(c.output_tokens, locale)}
                      </td>
                      <td className="numeric">{formatUsd(c.cost_usd, locale)}</td>
                      <td className="numeric">{formatMs(c.latency_ms, locale)}</td>
                      <td>
                        <span className={`tone-chip ${c.ok ? "tone-success" : "tone-danger"}`} title={c.error ?? undefined}>
                          {c.ok ? t("callOk") : t("callFailed")}
                        </span>
                      </td>
                      <td>
                        {sent
                          ? t("sentSummary", { headers: sent.headers, samples: sent.samples, rows: sent.rows })
                          : "–"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title={t("limitsTitle")}>
        <ol className="limits-list">
          {limits.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ol>
      </Section>
    </>
  );
}
