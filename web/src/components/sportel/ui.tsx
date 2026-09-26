"use client";

import { AlertTriangle, Check, Copy, FlaskConical, RotateCw } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useId, useState } from "react";

import { ApiError } from "@/lib/api";
import { pick } from "@/lib/format";
import type { Tone } from "@/lib/labels";

// ---------------------------------------------------------------- page header

export function PageHeader({
  kicker,
  title,
  description,
  actions,
}: {
  kicker: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="page-header-text">
        <p className="kicker">{kicker}</p>
        <h1 className="display-title">{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </header>
  );
}

// ---------------------------------------------------------------- chips

export function ToneChip({
  tone = "neutral",
  children,
  className = "",
  icon,
  ...rest
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
  icon?: React.ReactNode;
} & React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={`tone-chip tone-${tone} ${className}`} {...rest}>
      {icon}
      {children}
    </span>
  );
}

export function CodeChip({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <span className={`code-chip ${className}`}>{children}</span>;
}

export function SyntheticMark({ compact = false }: { compact?: boolean }) {
  const t = useTranslations("common");
  return (
    <span className={`synthetic-mark ${compact ? "compact" : ""}`}>
      <FlaskConical aria-hidden />
      {t("synthetic")}
    </span>
  );
}

// ---------------------------------------------------------------- copy + SQL

export function CopyButton({ text, label, className = "" }: { text: string; label?: string; className?: string }) {
  const t = useTranslations("common");
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const id = setTimeout(() => setCopied(false), 1800);
    return () => clearTimeout(id);
  }, [copied]);
  return (
    <button
      type="button"
      className={`copy-button ${copied ? "is-copied" : ""} ${className}`}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
        } catch {
          setCopied(false);
        }
      }}
    >
      {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
      <span aria-live="polite">{copied ? t("copied") : (label ?? t("copy"))}</span>
    </button>
  );
}

const SQL_KEYWORDS =
  /\b(SELECT|FROM|WHERE|AND|OR|NOT|GROUP BY|ORDER BY|LIMIT|AS|IS|NULL|BETWEEN|DATE|INTERVAL|DAY|FILTER|COUNT|SUM|AVG|ROUND|NULLIF|DATE_TRUNC|DESC|ASC|IN|ON|JOIN|LEFT|WITH|CASE|WHEN|THEN|ELSE|END)\b/gi;

/** Minimal, safe SQL highlighting: tokens are React text nodes, never HTML. */
function highlight(sql: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  const pattern = new RegExp(`('(?:[^']|'')*')|(--[^\\n]*)|(\\b\\d+(?:\\.\\d+)?\\b)|${SQL_KEYWORDS.source}`, "gi");
  let last = 0;
  let key = 0;
  for (const match of sql.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > last) out.push(sql.slice(last, index));
    const [token, str, comment, num] = match;
    const cls = str ? "sql-str" : comment ? "sql-comment" : num ? "sql-num" : "sql-kw";
    out.push(
      <span key={key++} className={cls}>
        {token}
      </span>,
    );
    last = index + token.length;
  }
  if (last < sql.length) out.push(sql.slice(last));
  return out;
}

export function SqlBlock({ sql, title }: { sql: string; title?: string }) {
  const t = useTranslations("passport");
  const id = useId();
  return (
    <figure className="sql-block" aria-labelledby={title ? id : undefined}>
      <figcaption>
        {title && <span id={id}>{title}</span>}
        <CopyButton text={sql} label={t("copySql")} />
      </figcaption>
      <pre tabIndex={0}>
        <code>{highlight(sql)}</code>
      </pre>
    </figure>
  );
}

// ---------------------------------------------------------------- sparkline

/** Tiny inline trend: one 2px line, end dot, target hairline. Decorative (values are in text). */
export function Sparkline({
  points,
  target,
  tone = "neutral",
  width = 112,
  height = 34,
}: {
  points: { period: string; value: number | null }[];
  target?: number | null;
  tone?: Tone;
  width?: number;
  height?: number;
}) {
  const values = points.map((p) => p.value).filter((v): v is number => v != null);
  if (values.length === 0) return null;
  const all = target != null ? [...values, target] : values;
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || Math.abs(max) || 1;
  const pad = 4;
  const x = (i: number) => (points.length === 1 ? width / 2 : pad + (i * (width - pad * 2)) / (points.length - 1));
  const y = (v: number) => pad + (1 - (v - min) / span) * (height - pad * 2);
  let d = "";
  points.forEach((p, i) => {
    if (p.value == null) return;
    d += `${d ? "L" : "M"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`;
  });
  const lastIndex = points.map((p) => p.value).lastIndexOf(values.at(-1)!);
  return (
    <svg className={`sparkline tone-${tone}`} width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      {target != null && <line className="spark-target" x1={pad} x2={width - pad} y1={y(target)} y2={y(target)} />}
      {points.length > 1 && <path className="spark-line" d={d} pathLength={1} />}
      <circle className="spark-dot" cx={x(lastIndex)} cy={y(values.at(-1)!)} r={3.2} />
    </svg>
  );
}

// ---------------------------------------------------------------- states

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const t = useTranslations("common");
  const locale = useLocale();
  const code = error instanceof ApiError ? error.code : error instanceof Error ? error.name : "error";
  const detail = error instanceof ApiError && error.detail ? pick(error.detail, locale) : null;
  return (
    <div className="error-state" role="alert">
      <AlertTriangle aria-hidden />
      <div>
        <strong>{t("errorTitle")}</strong>
        <p>{detail ?? t("errorBody", { code })}</p>
      </div>
      {onRetry && (
        <button type="button" className="civic-button" onClick={onRetry}>
          <RotateCw aria-hidden />
          {t("retry")}
        </button>
      )}
    </div>
  );
}

export function LoadingBlock({ label, rows = 3 }: { label: string; rows?: number }) {
  return (
    <div className="loading-block" role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, i) => (
        <i key={i} style={{ width: `${92 - i * 17}%` }} />
      ))}
    </div>
  );
}

export function Section({
  title,
  description,
  actions,
  children,
  className = "",
  id,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  id?: string;
}) {
  const headingId = useId();
  return (
    <section className={`sp-section ${className}`} aria-labelledby={headingId} id={id}>
      <div className="sp-section-head">
        <div>
          <h2 id={headingId}>{title}</h2>
          {description && <p className="section-subtitle">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}
