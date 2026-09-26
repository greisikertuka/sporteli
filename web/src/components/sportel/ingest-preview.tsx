"use client";

import {
  AlertTriangle,
  BookmarkCheck,
  Check,
  CheckCircle2,
  CircleDot,
  Cpu,
  GitCompareArrows,
  Info,
  Loader2,
  Ruler,
  ShieldCheck,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { useReducedMotion } from "@/hooks/use-api";
import type { DatasetInfo, IngestPreview, IngestStep, MappingSuggestion } from "@/lib/api";
import { formatBytes, formatCell, formatMs, formatNumber, formatRowCells, formatUsd, pick } from "@/lib/format";
import { confidenceTier, needsConfirmation, pendingConfirmations } from "@/lib/labels";

import { CodeChip, ReplayStamp, SyntheticMark, ToneChip } from "./ui";

const STEP_MS = 280;

/** Reveals the preview's real steps one by one (all at once under reduced motion). */
export function StepLog({ steps, onDone }: { steps: IngestStep[]; onDone: () => void }) {
  const t = useTranslations("ingest");
  const locale = useLocale();
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(0);
  const visible = reduced ? steps.length : shown;

  useEffect(() => {
    if (reduced) {
      const id = setTimeout(onDone, 0);
      return () => clearTimeout(id);
    }
    if (shown >= steps.length) {
      const id = setTimeout(onDone, 120);
      return () => clearTimeout(id);
    }
    const id = setTimeout(() => setShown((n) => n + 1), shown === 0 ? 120 : STEP_MS);
    return () => clearTimeout(id);
  }, [shown, steps.length, reduced, onDone]);

  return (
    <ol className="step-log" aria-label={t("stepsTitle")}>
      {steps.map((s, i) => {
        const state = i < visible ? "done" : i === visible ? "running" : "waiting";
        const label = t.has(`steps.${s.code}`) ? t(`steps.${s.code}` as "steps.read") : s.code;
        return (
          <li key={`${s.code}-${i}`} className={`step ${state} status-${s.status}`} aria-hidden={state === "waiting"}>
            <span className="step-icon" aria-hidden>
              {state === "running" ? (
                <Loader2 className="spin" />
              ) : state === "waiting" ? (
                <CircleDot />
              ) : s.status === "warn" ? (
                <AlertTriangle />
              ) : s.status === "info" ? (
                <Info />
              ) : (
                <CheckCircle2 />
              )}
            </span>
            <span className="step-body">
              <span className="step-title">
                <span className="step-code">{String(i + 1).padStart(2, "0")}</span>
                {label}
                {s.ms != null && state === "done" && <span className="step-ms">{formatMs(s.ms, locale)}</span>}
              </span>
              {state === "done" && <span className="step-msg">{pick(s.message, locale)}</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export type MappingRow = { column: string; field: string | null; confirmed: boolean; suggestion: MappingSuggestion };

export function initialRows(preview: IngestPreview): MappingRow[] {
  const dropped = new Set(preview.columns.filter((c) => c.dropped).map((c) => c.name));
  return preview.mapping
    .filter((m) => !dropped.has(m.column))
    .map((m) => ({ column: m.column, field: m.field, confirmed: !needsConfirmation(m, dropped), suggestion: m }));
}

function ConfidenceChip({ value, source }: { value: number; source: MappingSuggestion["source"] }) {
  const t = useTranslations("ingest");
  const locale = useLocale();
  const tier = confidenceTier(value);
  return (
    <span className={`conf-chip ${tier}`}>
      <span className="conf-bar" aria-hidden>
        <i style={{ width: `${Math.round(value * 100)}%` }} />
      </span>
      <span className="conf-value">{formatNumber(value, locale, 2)}</span>
      <span className="conf-source">{t(`source.${source}`)}</span>
    </span>
  );
}

export function PreviewDetails({
  preview,
  datasets,
  dataset,
  onDataset,
  rows,
  onRows,
  saveRecipe,
  onSaveRecipe,
  committing,
  onCommit,
  onCancel,
}: {
  preview: IngestPreview;
  datasets: DatasetInfo[] | undefined;
  dataset: string | null;
  onDataset: (key: string) => void;
  rows: MappingRow[];
  onRows: (rows: MappingRow[]) => void;
  saveRecipe: boolean;
  onSaveRecipe: (v: boolean) => void;
  committing: boolean;
  onCommit: () => void;
  onCancel: () => void;
}) {
  const t = useTranslations("ingest");
  const locale = useLocale();
  const dropped = preview.columns.filter((c) => c.dropped);
  const droppedSet = useMemo(() => new Set(dropped.map((c) => c.name)), [dropped]);
  const confirmed = useMemo(() => new Set(rows.filter((r) => r.confirmed).map((r) => r.column)), [rows]);
  const pending = pendingConfirmations(
    rows.map((r) => r.suggestion),
    confirmed,
    droppedSet,
  );
  const info = datasets?.find((d) => d.key === dataset);
  const fields = info?.fields ?? [];
  const samplesByColumn = new Map(preview.columns.map((c) => [c.name, c]));

  const setRow = (column: string, patch: Partial<MappingRow>) =>
    onRows(rows.map((r) => (r.column === column ? { ...r, ...patch } : r)));

  return (
    <div className="preview-details">
      <ReplayStamp />
      <div className="preview-meta">
        <div className="preview-file">
          <CodeChip>{preview.filename}</CodeChip>
          {preview.synthetic && <SyntheticMark compact />}
        </div>
        <p className="preview-facts">
          {t("fileMeta", { shown: formatNumber(preview.data_rows, locale), rows: preview.data_rows, header: preview.header_row })}
          {preview.sheet && <> · {t("sheet", { sheet: preview.sheet })}</>} · {formatBytes(preview.size_bytes, locale)}
        </p>
        <div className="preview-dataset">
          {preview.dataset ? (
            <ToneChip tone="info">
              {t("datasetDetected", { name: pick(preview.dataset.name, locale) })} ·{" "}
              {t("datasetConfidence", { pct: `${Math.round(preview.dataset.confidence * 100)}%` })}
            </ToneChip>
          ) : (
            <ToneChip tone="warning">{t("unknownDataset")}</ToneChip>
          )}
          <label className="select-field compact">
            <span>{t("chooseDataset")}</span>
            <select value={dataset ?? ""} onChange={(e) => onDataset(e.target.value)}>
              <option value="" disabled>
                —
              </option>
              {(datasets ?? []).map((d) => (
                <option key={d.key} value={d.key}>
                  {pick(d.name, locale)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className={`pii-banner ${dropped.length ? "dropped" : "none"}`} role="status">
        <ShieldCheck aria-hidden />
        <div>
          <strong>{dropped.length ? t("piiDropped", { count: dropped.length }) : t("piiNone")}</strong>
          {dropped.length > 0 ? (
            <>
              <ul className="pii-list">
                {dropped.map((c) => (
                  <li key={c.name}>
                    <s>{c.name}</s>
                    {c.pii && <span className="pii-kind">{t(`piiKind.${c.pii}`)}</span>}
                  </li>
                ))}
              </ul>
              <p>{t("piiDetail")}</p>
            </>
          ) : (
            <p>{t("piiNoneDetail")}</p>
          )}
        </div>
      </div>

      <div className="preview-notes">
        {preview.unit_note && (
          <div className="note-card unit">
            <Ruler aria-hidden />
            <div>
              <strong>
                {t("unitTitle")} · × {formatNumber(preview.unit_multiplier, locale)}
              </strong>
              <p>{pick(preview.unit_note, locale)}</p>
            </div>
          </div>
        )}
        {preview.excluded_rows.length > 0 && (
          <div className="note-card excluded">
            <div>
              <strong>{t("excludedTitle")}</strong>
              <ul className="excluded-list">
                {preview.excluded_rows.map((e) => (
                  <li key={e.row_no}>
                    <span className="excluded-row">{t("row", { n: e.row_no })}</span>
                    <span className={`excluded-reason ${e.reason}`}>{t(`excludedReason.${e.reason}`)}</span>
                    <span className="excluded-text">{e.cells ? formatRowCells(e.cells, locale) : e.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
        {preview.recipe.hit && preview.recipe.recipe_id && (
          <div className="note-card recipe">
            <BookmarkCheck aria-hidden />
            <p>{t("recipeHit", { id: preview.recipe.recipe_id })}</p>
          </div>
        )}
        {preview.recipe.drift && (
          <div className="note-card drift">
            <GitCompareArrows aria-hidden />
            <div>
              <strong>{t("driftTitle")}</strong>
              <dl className="drift-list">
                {(["renamed", "missing", "added"] as const).map((k) =>
                  preview.recipe.drift![k].length ? (
                    <div key={k}>
                      <dt>{t(`drift${k[0].toUpperCase()}${k.slice(1)}` as "driftRenamed")}</dt>
                      <dd>{preview.recipe.drift![k].join(", ")}</dd>
                    </div>
                  ) : null,
                )}
              </dl>
            </div>
          </div>
        )}
        <div className="note-card llm">
          {preview.llm.used ? <Sparkles aria-hidden /> : <Cpu aria-hidden />}
          <div>
            <strong>
              {preview.llm.used
                ? t("llmUsed", {
                    model: preview.llm.model ?? "AI",
                    latency: formatMs(preview.llm.latency_ms, locale),
                    cost: formatUsd(preview.llm.cost_usd, locale),
                  })
                : t("llmRules")}
            </strong>
            {preview.llm.sent && (
              <p>
                {t("llmSent", { headers: preview.llm.sent.headers, samples: preview.llm.sent.samples_per_column })}
              </p>
            )}
            {/* "llm_unavailable" just means RULES mode (no key): the line above already says so. */}
            {preview.llm.error === "llm_budget_exhausted" ? (
              <p>{t("llmBudget")}</p>
            ) : preview.llm.error && preview.llm.error !== "llm_unavailable" ? (
              <p>{t("llmError", { error: preview.llm.error })}</p>
            ) : null}
            {preview.warnings.map((w, i) => (
              <p key={i}>{pick(w, locale)}</p>
            ))}
          </div>
        </div>
      </div>

      {preview.question && (
        <fieldset className="question-card">
          <legend>
            <UserCheck aria-hidden />
            {t("questionTitle")}
          </legend>
          <p>{pick(preview.question.text, locale)}</p>
          <div className="question-options">
            {preview.question.options.map((o) => {
              const row = rows.find((r) => r.column === preview.question!.column);
              const chosen = row?.confirmed && row.field === o.field;
              return (
                <button
                  key={String(o.field)}
                  type="button"
                  className={`option-button ${chosen ? "chosen" : ""}`}
                  aria-pressed={Boolean(chosen)}
                  onClick={() =>
                    setRow(preview.question!.column, {
                      field: o.field,
                      confirmed: true,
                      suggestion: { ...(row?.suggestion ?? { column: preview.question!.column, confidence: 1, reason: o.label }), field: o.field, source: "user" },
                    })
                  }
                >
                  {chosen && <Check aria-hidden />}
                  {pick(o.label, locale)}
                </button>
              );
            })}
          </div>
        </fieldset>
      )}

      <section className="mapping" aria-labelledby="mapping-title">
        <div className="mapping-head">
          <div>
            <h3 id="mapping-title">{t("mappingTitle")}</h3>
            <p className="fine-print">{t("mappingNote")}</p>
          </div>
          {pending.length > 1 && (
            <button
              type="button"
              className="civic-button"
              onClick={() => onRows(rows.map((r) => ({ ...r, confirmed: true })))}
            >
              <Check aria-hidden />
              {t("confirmAll", { count: pending.length })}
            </button>
          )}
        </div>
        <table className="mapping-table">
          <thead>
            <tr>
              <th scope="col">{t("colColumn")}</th>
              <th scope="col">{t("colField")}</th>
              <th scope="col">{t("colConfidence")}</th>
              <th scope="col">{t("colAction")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const profile = samplesByColumn.get(r.column);
              const tier = confidenceTier(r.suggestion.confidence);
              const needs = needsConfirmation(r.suggestion, droppedSet);
              return (
                <tr key={r.column} className={`${tier} ${r.confirmed ? "is-confirmed" : needs ? "is-pending" : ""}`}>
                  <td data-label={t("colColumn")}>
                    <span className="map-col">{r.column}</span>
                    {profile && profile.samples.length > 0 && (
                      <span className="map-samples" aria-label={t("colSamples")}>
                        {profile.samples.slice(0, 3).map((s, i) => {
                          // numbers read by the API, shown in the page's locale (masked ones stay masked)
                          const v = profile.sample_values?.[i];
                          return <code key={i}>{v != null ? formatCell(v, locale) : s || "∅"}</code>;
                        })}
                      </span>
                    )}
                    <span className="map-reason">{pick(r.suggestion.reason, locale)}</span>
                  </td>
                  <td data-label={t("colField")}>
                    <select
                      aria-label={t("fieldFor", { column: r.column })}
                      value={r.field ?? ""}
                      onChange={(e) =>
                        setRow(r.column, {
                          field: e.target.value || null,
                          confirmed: true,
                          suggestion: { ...r.suggestion, field: e.target.value || null, source: "user" },
                        })
                      }
                    >
                      <option value="">{t("ignore")}</option>
                      {fields.map((f) => (
                        <option key={f.key} value={f.key}>
                          {pick(f.label, locale)}
                          {f.required ? " *" : ""}
                        </option>
                      ))}
                      {r.field && !fields.some((f) => f.key === r.field) && <option value={r.field}>{r.field}</option>}
                    </select>
                  </td>
                  <td data-label={t("colConfidence")}>
                    <ConfidenceChip value={r.suggestion.confidence} source={r.suggestion.source} />
                  </td>
                  <td data-label={t("colAction")}>
                    {r.confirmed ? (
                      <span className="map-confirmed">
                        <Check aria-hidden />
                        {needs || r.suggestion.source === "user" ? t("confirmed") : t("auto")}
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="confirm-button"
                        onClick={() => setRow(r.column, { confirmed: true })}
                        aria-label={t("confirmColumn", { column: r.column })}
                      >
                        {t("confirm")}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <div className="commit-bar">
        <p className={`commit-status ${pending.length ? "pending" : "ready"}`} aria-live="polite">
          {pending.length ? t("pending", { count: pending.length }) : t("ready")}
        </p>
        {!preview.recipe.hit && (
          <label className="recipe-toggle">
            <input type="checkbox" checked={saveRecipe} onChange={(e) => onSaveRecipe(e.target.checked)} />
            <span>
              {t("saveRecipe")}
              <small>{t("saveRecipeHint")}</small>
            </span>
          </label>
        )}
        <div className="commit-actions">
          <button type="button" className="civic-button ghost" onClick={onCancel} disabled={committing}>
            {t("cancel")}
          </button>
          <button
            type="button"
            className="civic-button primary"
            onClick={onCommit}
            disabled={committing || pending.length > 0 || !dataset}
          >
            {committing ? <Loader2 className="spin" aria-hidden /> : <Check aria-hidden />}
            {committing ? t("committing") : t("commit")}
          </button>
        </div>
      </div>
    </div>
  );
}
