"use client";

import { ArrowRight, Check, MessageSquareText, X } from "lucide-react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";

import type { LoadReceipt as Receipt } from "@/lib/api";
import { formatDateTime, formatLek, formatMs, formatNumber, formatUsd, pick } from "@/lib/format";
import { receiptBalance, reconciliationOk } from "@/lib/labels";

/** Deterministic "barcode" drawn from the file hash: decoration, the hash itself is printed below. */
function HashBars({ hash }: { hash: string }) {
  const hex = hash.replace(/[^0-9a-f]/gi, "").slice(0, 40).padEnd(40, "0");
  let x = 0;
  const bars: { x: number; w: number }[] = [];
  for (const ch of hex) {
    const v = parseInt(ch, 16);
    const w = 1 + (v % 3);
    bars.push({ x, w });
    x += w + 1 + ((v >> 2) % 3);
  }
  return (
    <svg className="receipt-bars" viewBox={`0 0 ${x} 28`} preserveAspectRatio="none" aria-hidden>
      {bars.map((b, i) => (
        <rect key={i} x={b.x} y={0} width={b.w} height={28} />
      ))}
    </svg>
  );
}

function Line({ label, value, strong = false, indent = 0 }: { label: string; value: React.ReactNode; strong?: boolean; indent?: number }) {
  return (
    <div className={`receipt-line ${strong ? "strong" : ""}`} style={{ paddingLeft: indent * 14 }}>
      <span className="receipt-label">{label}</span>
      <span className="receipt-leader" aria-hidden />
      <span className="receipt-value">{value}</span>
    </div>
  );
}

const isMoney = (field: string) => field.endsWith("_lek");

export function LoadReceipt({
  receipt: r,
  compact = false,
  animate = false,
}: {
  receipt: Receipt;
  compact?: boolean;
  animate?: boolean;
}) {
  const t = useTranslations("receipt");
  const tc = useTranslations("common");
  const tApp = useTranslations("app");
  const locale = useLocale();
  const n = (v: number) => formatNumber(v, locale);
  const balance = receiptBalance(r);
  const recOk = reconciliationOk(r) && balance.balanced;

  return (
    <div className={`receipt-wrap ${animate ? "is-printing" : ""} ${compact ? "compact" : ""}`}>
      <article className="receipt" aria-label={t("title")}>
        <header className="receipt-head">
          <p className="receipt-brand">{tApp("name")}</p>
          <h3>{t("title")}</h3>
          <p className="receipt-sub">{pick(r.dataset_name, locale)}</p>
          {r.synthetic && <p className="receipt-synthetic">{t("synthetic")}</p>}
        </header>

        <div className="receipt-section">
          <Line label={t("source")} value={<span className="receipt-file">{r.filename}</span>} />
          <Line label={t("dataset")} value={r.dataset} />
          <Line label={t("hash")} value={`${r.file_hash.slice(0, 16)}…`} />
          <Line label={t("loadedAt")} value={formatDateTime(r.loaded_at, locale)} />
          <Line label={t("duration")} value={formatMs(r.duration_ms, locale)} />
        </div>

        <div className="receipt-section">
          <Line label={t("rowsRead")} value={n(balance.read)} strong />
          <Line label={t("rowsLoaded")} value={n(balance.loaded)} indent={1} />
          <Line label={t("rowsExcluded")} value={n(balance.excluded)} indent={1} />
          {r.rows_excluded.map((e) => (
            <Line key={e.reason} label={pick(e.label, locale)} value={n(e.count)} indent={2} />
          ))}
          <p className={`receipt-check ${balance.balanced ? "ok" : "fail"}`}>
            {balance.balanced ? <Check aria-hidden /> : <X aria-hidden />}
            {t("balance")} · {n(balance.read)} = {n(balance.loaded)} + {n(balance.excluded)}
            <span className="sr-only">{balance.balanced ? t("ok") : t("fail")}</span>
          </p>
        </div>

        {r.reconciliation.length > 0 && (
          <div className="receipt-section">
            <p className="receipt-caption">{t("reconciliation")}</p>
            {r.reconciliation.map((rec) => {
              const fmt = (v: number) => (isMoney(rec.field) ? formatLek(v, locale) : n(v));
              return (
                <div key={rec.field} className="receipt-rec">
                  <p className="receipt-rec-name">
                    {rec.ok ? <Check aria-hidden className="ok" /> : <X aria-hidden className="fail" />}
                    {pick(rec.label, locale)}
                    <span className="sr-only">{rec.ok ? t("ok") : t("fail")}</span>
                  </p>
                  <Line label={t("fileTotal")} value={rec.file_total == null ? t("noFileTotal") : fmt(rec.file_total)} indent={1} />
                  <Line label={t("loadedSum")} value={fmt(rec.loaded_sum)} indent={1} />
                  {rec.note && <p className="receipt-note">{pick(rec.note, locale)}</p>}
                </div>
              );
            })}
          </div>
        )}

        <div className="receipt-section">
          <Line label={t("pii")} value={r.pii_dropped.length ? r.pii_dropped.join(", ") : tc("none")} />
          <Line label={t("multiplier")} value={`× ${n(r.unit_multiplier)}`} />
          <Line
            label={t("ai")}
            value={
              r.llm.used
                ? `${r.llm.model ?? "AI"} · ${formatMs(r.llm.latency_ms, locale)} · ${formatUsd(r.llm.cost_usd, locale)}`
                : t("aiRules")
            }
          />
          <Line
            label={t("recipe")}
            value={
              r.recipe.reused
                ? t("recipeReused", { id: r.recipe.recipe_id ?? "–" })
                : r.recipe.saved
                  ? t("recipeSaved", { id: r.recipe.recipe_id ?? "–" })
                  : t("recipeNone")
            }
          />
        </div>

        {!compact && (
          <div className="receipt-section receipt-unlocked">
            <p className="receipt-caption">{t("unlocked")}</p>
            {r.indicators_unlocked.length === 0 ? (
              <p className="receipt-note">{t("unlockedNone")}</p>
            ) : (
              <ul>
                {r.indicators_unlocked.map((u) => (
                  <li key={u.code}>
                    <Link href="/" className="unlocked-chip">
                      <span className="code">{u.code}</span>
                      {pick(u.name, locale)}
                      <ArrowRight aria-hidden />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <p className="receipt-coverage">{t("coverage", { computable: r.coverage.computable, total: r.coverage.total })}</p>
          </div>
        )}

        <footer className="receipt-foot">
          <span className={`receipt-stamp ${recOk ? "ok" : "fail"}`} aria-hidden>
            {recOk ? t("stamp") : t("stampFail")}
          </span>
          <HashBars hash={r.file_hash} />
          <p>{t("footer")}</p>
        </footer>
      </article>
      {!compact && (
        <div className="receipt-actions">
          <Link href="/" className="civic-button primary">
            {t("toBoard")}
            <ArrowRight aria-hidden />
          </Link>
          <Link
            href={r.indicators_unlocked[0] ? `/ask?passport=${encodeURIComponent(r.indicators_unlocked[0].code)}` : "/ask"}
            className="civic-button"
          >
            <MessageSquareText aria-hidden />
            {t("askAgain")}
          </Link>
        </div>
      )}
    </div>
  );
}
