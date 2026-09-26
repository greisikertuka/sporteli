"use client";

import {
  CheckCircle2,
  FileUp,
  History,
  Loader2,
  PackageOpen,
  RotateCcw,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { AlertDialog } from "radix-ui";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useId, useMemo, useRef, useState } from "react";

import { useApi, useReducedMotion } from "@/hooks/use-api";
import type { IngestPreview, LoadReceipt as Receipt, SampleFile, SourceInfo } from "@/lib/api";
import {
  commitIngest,
  deleteRecipes,
  getDatasets,
  getSamples,
  getSources,
  previewSample,
  previewUpload,
  resetDemo,
} from "@/lib/client";
import { formatBytes, formatDateTime, formatNumber, pick } from "@/lib/format";
import { receiptBalance, reconciliationOk } from "@/lib/labels";

import { initialRows, PreviewDetails, StepLog, type MappingRow } from "./ingest-preview";
import { LoadReceipt } from "./load-receipt";
import { CodeChip, ErrorState, PageHeader, Section, SyntheticMark, ToneChip } from "./ui";

const ACCEPT = ".csv,.xlsx,.xls";
/** Sample labels already read "Zarfi 1 · …"; the card prints the envelope number itself. */
const ENVELOPE_PREFIX = /^(zarfi|envelope)\s*\d+\s*[·:–-]\s*/i;
const OK_EXT = /\.(csv|xlsx|xls)$/i;

type Phase =
  | { kind: "idle" }
  | { kind: "reading"; file: string }
  | { kind: "preview"; preview: IngestPreview }
  | { kind: "done"; receipt: Receipt }
  | { kind: "error"; error: unknown; file?: string };

export function IngestScreen({ wanted, askCode = null }: { wanted: string | null; askCode?: string | null }) {
  const t = useTranslations("ingest");
  const locale = useLocale();
  const datasets = useApi("datasets", getDatasets);
  const samples = useApi("samples", getSamples);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [rows, setRows] = useState<MappingRow[]>([]);
  const [dataset, setDataset] = useState<string | null>(null);
  const [saveRecipe, setSaveRecipe] = useState(true);
  const [committing, setCommitting] = useState(false);
  const [stepsDoneFor, setStepsDoneFor] = useState<string | null>(null);
  const workRef = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const scrollToWork = useCallback(() => {
    requestAnimationFrame(() => workRef.current?.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" }));
  }, [reduced]);

  const wantedInfo = datasets.data?.find((d) => d.key === wanted);

  const begin = useCallback(async (label: string, run: () => Promise<IngestPreview>) => {
    setPhase({ kind: "reading", file: label });
    setStepsDoneFor(null);
    scrollToWork();
    try {
      const preview = await run();
      setRows(initialRows(preview));
      setDataset(preview.dataset?.key ?? null);
      setSaveRecipe(!preview.recipe.hit);
      setPhase({ kind: "preview", preview });
    } catch (error) {
      setPhase({ kind: "error", error, file: label });
    }
  }, [scrollToWork]);

  const commit = async () => {
    if (phase.kind !== "preview" || !dataset) return;
    setCommitting(true);
    try {
      const receipt = await commitIngest({
        preview_id: phase.preview.preview_id,
        dataset,
        mapping: rows.map((r) => ({ column: r.column, field: r.field })),
        save_recipe: saveRecipe,
      });
      setPhase({ kind: "done", receipt });
      scrollToWork();
    } catch (error) {
      setPhase({ kind: "error", error, file: phase.preview.filename });
    } finally {
      setCommitting(false);
    }
  };

  const onStepsDone = useCallback(() => {
    if (phase.kind === "preview") setStepsDoneFor(phase.preview.preview_id);
  }, [phase]);

  return (
    <>
      <PageHeader kicker={t("kicker")} title={t("title")} description={t("description")} />

      {wantedInfo && !wantedInfo.loaded && (
        <div className="wanted-banner" role="status">
          <PackageOpen aria-hidden />
          <div>
            <strong>{t("wanted", { dataset: pick(wantedInfo.name, locale) })}</strong>
            <span>{t("wantedOwner", { owner: pick(wantedInfo.owner.name, locale) })}</span>
          </div>
        </div>
      )}

      <div className="ingest-intake">
        <Dropzone
          disabled={phase.kind === "reading" || committing}
          onFile={(file) => begin(file.name, () => previewUpload(file))}
        />
        <SampleShelf
          samples={samples.data}
          error={samples.error}
          wanted={wanted}
          busy={phase.kind === "reading" || committing}
          onPick={(s) => begin(s.name, () => previewSample(s.name))}
        />
      </div>

      <p className="sr-only" aria-live="polite" aria-atomic>
        {phase.kind === "reading"
          ? t("reading", { file: phase.file })
          : phase.kind === "preview" && stepsDoneFor === phase.preview.preview_id
            ? t("liveReady", { steps: phase.preview.steps.length })
            : phase.kind === "done"
              ? t("liveDone", {
                  rows: formatNumber(phase.receipt.rows_loaded, locale),
                  computable: phase.receipt.coverage.computable,
                  total: phase.receipt.coverage.total,
                })
              : ""}
      </p>
      <div ref={workRef} className="ingest-work" aria-busy={phase.kind === "reading" || committing}>
        {phase.kind === "reading" && (
          <div className="panel reading-panel">
            <Loader2 className="spin" aria-hidden />
            <p>{t("reading", { file: phase.file })}</p>
          </div>
        )}
        {phase.kind === "error" && (
          <ErrorState error={phase.error} onRetry={() => setPhase({ kind: "idle" })} />
        )}
        {phase.kind === "preview" && (
          <div className="panel pipeline">
            <div className="pipeline-steps">
              <h2>{t("stepsTitle")}</h2>
              <StepLog key={phase.preview.preview_id} steps={phase.preview.steps} onDone={onStepsDone} />
            </div>
            <div className={`pipeline-detail ${stepsDoneFor === phase.preview.preview_id ? "is-ready" : "is-waiting"}`}>
              {stepsDoneFor === phase.preview.preview_id && (
                <PreviewDetails
                  preview={phase.preview}
                  datasets={datasets.data}
                  dataset={dataset}
                  onDataset={setDataset}
                  rows={rows}
                  onRows={setRows}
                  saveRecipe={saveRecipe}
                  onSaveRecipe={setSaveRecipe}
                  committing={committing}
                  onCommit={commit}
                  onCancel={() => setPhase({ kind: "idle" })}
                />
              )}
            </div>
          </div>
        )}
        {phase.kind === "done" && (
          <div className="receipt-stage">
            <LoadReceipt receipt={phase.receipt} animate askCode={askCode} />
            <button type="button" className="text-button" onClick={() => setPhase({ kind: "idle" })}>
              <FileUp aria-hidden />
              {t("another")}
            </button>
          </div>
        )}
      </div>

      <SourcesSection />
    </>
  );
}

function Dropzone({ onFile, disabled }: { onFile: (file: File) => void; disabled: boolean }) {
  const t = useTranslations("ingest");
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputId = useId();

  const accept = (file: File | undefined) => {
    if (!file) return;
    if (!OK_EXT.test(file.name)) {
      setError(t("badType"));
      return;
    }
    setError(null);
    onFile(file);
  };

  return (
    <div
      className={`dropzone ${dragging ? "dragging" : ""} ${disabled ? "disabled" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (!disabled) accept(e.dataTransfer.files?.[0]);
      }}
    >
      <div className="dropzone-art" aria-hidden>
        <UploadCloud />
      </div>
      <h2>{dragging ? t("dropActive") : t("dropTitle")}</h2>
      <p>{t("dropBody")}</p>
      <input
        ref={input}
        id={inputId}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        disabled={disabled}
        onChange={(e) => {
          accept(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      <label htmlFor={inputId} className={`civic-button primary ${disabled ? "is-disabled" : ""}`}>
        <FileUp aria-hidden />
        {t("choose")}
      </label>
      <p className="dropzone-types">.csv · .xlsx · .xls</p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

function SampleShelf({
  samples,
  error,
  wanted,
  busy,
  onPick,
}: {
  samples: SampleFile[] | undefined;
  error: unknown;
  wanted: string | null;
  busy: boolean;
  onPick: (s: SampleFile) => void;
}) {
  const t = useTranslations("ingest");
  const locale = useLocale();
  const envelopes = (samples ?? []).filter((s) => s.envelope != null).sort((a, b) => (a.envelope ?? 0) - (b.envelope ?? 0));
  const others = (samples ?? []).filter((s) => s.envelope == null);

  return (
    <section className="sample-shelf" aria-labelledby="samples-title">
      <h2 id="samples-title">{t("samplesTitle")}</h2>
      <p className="fine-print">{t("samplesNote")}</p>
      {error ? <ErrorState error={error} /> : null}
      <ul className="envelopes">
        {envelopes.map((s) => {
          const isWanted = s.dataset_hint === wanted && !s.loaded;
          return (
            <li key={s.name}>
              <button
                type="button"
                className={`envelope ${s.loaded ? "is-loaded" : ""} ${isWanted ? "is-wanted" : ""}`}
                onClick={() => onPick(s)}
                disabled={busy}
                aria-describedby={`env-${s.envelope}`}
              >
                <span className="envelope-flap" aria-hidden />
                <span className="envelope-seal" aria-hidden>
                  {s.envelope}
                </span>
                <span className="envelope-body">
                  <span className="envelope-kicker">{t("envelope", { n: s.envelope ?? 0 })}</span>
                  <span className="envelope-label">{pick(s.label, locale).replace(ENVELOPE_PREFIX, "")}</span>
                  <span className="envelope-file" id={`env-${s.envelope}`}>
                    {s.name}
                  </span>
                  <span className="envelope-foot">
                    {s.synthetic && <SyntheticMark compact />}
                    <span>{formatBytes(s.size_bytes, locale)}</span>
                    {s.loaded && (
                      <span className="envelope-state loaded">
                        <CheckCircle2 aria-hidden />
                        {t("loaded")}
                      </span>
                    )}
                    {isWanted && <span className="envelope-state wanted">{t("wantedBadge")}</span>}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {others.length > 0 && (
        <ul className="sample-list">
          {others.map((s) => (
            <li key={s.name}>
              <button type="button" onClick={() => onPick(s)} disabled={busy}>
                <span className="sample-name">{pick(s.label, locale)}</span>
                <span className="sample-file">{s.name}</span>
                <span className="sample-tags">
                  {s.preload && <ToneChip tone="neutral">{t("preloaded")}</ToneChip>}
                  {!s.preload && s.envelope == null && <ToneChip tone="warning">{t("drift")}</ToneChip>}
                  {s.loaded && (
                    <ToneChip tone="success" icon={<CheckCircle2 aria-hidden />}>
                      {t("loaded")}
                    </ToneChip>
                  )}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SourcesSection() {
  const t = useTranslations("ingest");
  const locale = useLocale();
  const sources = useApi("sources", getSources);
  const [open, setOpen] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const recipeIds = useMemo(
    () => new Set((sources.data ?? []).filter((s) => s.recipe.saved && s.recipe.recipe_id).map((s) => s.recipe.recipe_id!)),
    [sources.data],
  );

  return (
    <Section
      title={t("sourcesTitle")}
      description={t("sourcesNote")}
      className="sources-section"
      actions={
        <div className="sources-actions">
          <span className="recipe-count">
            <History aria-hidden />
            {t("recipes", { count: recipeIds.size })}
          </span>
          <button
            type="button"
            className="civic-button ghost"
            onClick={async () => {
              try {
                const r = await deleteRecipes();
                setNotice(t("recipesDeleted", { count: r.deleted }));
              } catch {
                setNotice(t("actionError"));
              }
            }}
          >
            <Trash2 aria-hidden />
            {t("deleteRecipes")}
          </button>
          <ResetDemo onDone={(msg) => setNotice(msg)} />
        </div>
      }
    >
      <p className="sr-only" aria-live="polite">
        {notice}
      </p>
      {notice && <p className="inline-notice">{notice}</p>}
      {sources.error ? <ErrorState error={sources.error} onRetry={sources.reload} /> : null}
      {sources.data && sources.data.length === 0 && <p className="fine-print">{t("emptySources")}</p>}
      <ul className="source-cards">
        {(sources.data ?? []).map((s: SourceInfo) => {
          const b = receiptBalance(s);
          const ok = reconciliationOk(s) && b.balanced;
          const isOpen = open === s.source_id;
          return (
            <li key={s.source_id} className="source-card-row">
              <div className="source-row-main">
                <div className="source-row-title">
                  <strong>{pick(s.dataset_name, locale)}</strong>
                  <CodeChip>{s.filename}</CodeChip>
                  {s.synthetic && <SyntheticMark compact />}
                </div>
                <p className="source-row-meta">
                  {t("rowsSummary", { loaded: formatNumber(b.loaded, locale), excluded: formatNumber(b.excluded, locale) })} ·{" "}
                  {formatDateTime(s.loaded_at, locale)}
                  {s.pii_dropped.length > 0 && <> · {t("piiDropped", { count: s.pii_dropped.length })}</>}
                </p>
              </div>
              <ToneChip tone={ok ? "success" : "warning"}>{ok ? t("reconciled") : t("notReconciled")}</ToneChip>
              <button
                type="button"
                className="text-button"
                aria-expanded={isOpen}
                onClick={() => setOpen(isOpen ? null : s.source_id)}
              >
                {isOpen ? t("hideReceipt") : t("viewReceipt")}
              </button>
              {isOpen && (
                <div className="source-receipt">
                  <LoadReceipt receipt={s} compact />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </Section>
  );
}

function ResetDemo({ onDone }: { onDone: (message: string) => void }) {
  const t = useTranslations("ingest");
  const tc = useTranslations("common");
  const [busy, setBusy] = useState(false);
  return (
    <AlertDialog.Root>
      <AlertDialog.Trigger asChild>
        <button type="button" className="civic-button">
          <RotateCcw aria-hidden />
          {t("reset")}
        </button>
      </AlertDialog.Trigger>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="dialog-overlay" />
        <AlertDialog.Content className="dialog-content">
          <AlertDialog.Title className="dialog-title">{t("resetTitle")}</AlertDialog.Title>
          <AlertDialog.Description className="dialog-description">{t("resetBody")}</AlertDialog.Description>
          <div className="dialog-actions">
            <AlertDialog.Cancel asChild>
              <button type="button" className="civic-button">
                {tc("cancel")}
              </button>
            </AlertDialog.Cancel>
            <AlertDialog.Action asChild>
              <button
                type="button"
                className="civic-button primary"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    const r = await resetDemo();
                    onDone(t("resetDone", { computable: r.coverage.computable, total: r.coverage.total }));
                  } catch {
                    onDone(t("actionError"));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {t("resetConfirm")}
              </button>
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
