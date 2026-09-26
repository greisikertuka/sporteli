"use client";

import {
  ArrowRight,
  ArrowUpRight,
  Ban,
  CircleHelp,
  Compass,
  Cpu,
  FileSpreadsheet,
  Loader2,
  MessageSquareDashed,
  SearchCheck,
  Send,
  ShieldAlert,
  Sparkles,
  Upload,
} from "lucide-react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";

import { useApi, useReducedMotion } from "@/hooks/use-api";
import { type AskAnswer, type AskEval, type AskExample, type AskLabel } from "@/lib/api";
import { ask, getEval, getExamples, getPassport } from "@/lib/client";
import { asLocale, formatCell, formatDateTime, formatIndicatorValue, pick, summariseRanges } from "@/lib/format";
import { ASK_LABEL_TONE, ASK_LABELS } from "@/lib/labels";

import { useSystem } from "./system-context";
import { CodeChip, ErrorState, PageHeader, ReplayStamp, ToneChip } from "./ui";

const LABEL_ICON: Record<AskLabel, React.ComponentType<{ "aria-hidden"?: boolean }>> = {
  verified: SearchCheck,
  exploratory: Compass,
  not_answerable: CircleHelp,
  blocked: Ban,
};

const KIND_ICON: Record<AskExample["kind"], React.ComponentType<{ "aria-hidden"?: boolean }>> = {
  verified: SearchCheck,
  gap: CircleHelp,
  exploratory: Compass,
  blocked: ShieldAlert,
};

type Entry = { id: number; answer: AskAnswer; exampleId?: string };

/** A readable header for a column name chosen by a query: `admin_unit` → "Admin unit", `pct` → "%". */
function humaniseColumn(name: string): string {
  const text = name
    .split(/_+/)
    .filter(Boolean)
    .map((w) => (w.toLowerCase() === "pct" ? "%" : w))
    .join(" ");
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : name;
}

export function LabelStamp({ label, animate = false }: { label: AskLabel; animate?: boolean }) {
  const t = useTranslations("labels");
  const Icon = LABEL_ICON[label];
  return (
    <span className={`label-stamp tone-${ASK_LABEL_TONE[label]} ${animate ? "is-new" : ""}`}>
      <Icon aria-hidden />
      <span>{t(`${label}.stamp`)}</span>
    </span>
  );
}

export function AskScreen({ passport }: { passport: string | null }) {
  const t = useTranslations("ask");
  const tAll = useTranslations();
  const locale = useLocale();
  const examples = useApi("ask:examples", getExamples);
  const evaluation = useApi("ask:eval", getEval);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [history, setHistory] = useState<Entry[]>([]);
  const counter = useRef(0);
  const autoAsked = useRef(false);
  const inputId = useId();
  const reduced = useReducedMotion();
  const answerRef = useRef<HTMLElement | null>(null);
  const { board } = useSystem();
  const newestId = history[0]?.id;

  // A new answer lands below the example list: bring it into view and move focus to its
  // heading (projector at 1280×720 and phones alike), without animating under reduced motion.
  useEffect(() => {
    if (newestId == null) return;
    const el = answerRef.current;
    if (!el) return;
    el.querySelector<HTMLElement>("[data-answer-heading]")?.focus({ preventScroll: true });
    // a hidden page does not animate smooth scrolling (it would never arrive): jump instead
    const smooth = !reduced && document.visibilityState === "visible";
    // land just below the sticky header, whose height changes with the width (pills wrap)
    const header = document.querySelector(".civic-topbar");
    const offset = (header ? header.getBoundingClientRect().bottom : 0) + 12;
    window.scrollTo({ top: Math.max(0, window.scrollY + el.getBoundingClientRect().top - offset), behavior: smooth ? "smooth" : "auto" });
  }, [newestId, reduced]);

  /** The example's kind as it stands now: a gap example becomes "verified" once its export is
   * loaded (and the other way round after a reset), read from the live board. */
  const kindOf = (ex: AskExample): AskExample["kind"] => {
    if (!ex.passport_code || (ex.kind !== "verified" && ex.kind !== "gap")) return ex.kind;
    const indicator = board.data?.indicators.find((i) => i.code === ex.passport_code);
    if (!indicator) return ex.kind;
    return indicator.state === "computable" ? "verified" : "gap";
  };

  const run = async (text: string, exampleId?: string) => {
    const q = text.trim();
    if (!q && !exampleId) return;
    setBusy(true);
    setError(null);
    try {
      const answer = await ask({ question: q, locale: asLocale(locale), ...(exampleId ? { example_id: exampleId } : {}) });
      counter.current += 1;
      const id = counter.current;
      setHistory((h) => [{ id, answer, exampleId }, ...h].slice(0, 6));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  // `/ask?passport=REV-01` (from a load receipt or a passport): ask that passport's example
  // chip once, or, when it has none, the passport's own canonical question.
  useEffect(() => {
    if (!passport || autoAsked.current || !examples.data) return;
    const ex = examples.data.find((e) => e.passport_code === passport);
    let cancelled = false;
    const id = setTimeout(async () => {
      let text: string;
      try {
        text = ex ? pick(ex.question, locale) : pick((await getPassport(passport)).question, locale);
      } catch {
        return; // unknown passport: leave the page as it is
      }
      if (cancelled || autoAsked.current) return;
      autoAsked.current = true;
      setQuestion(text);
      void run(text, ex?.id);
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [passport, examples.data, locale]);

  const evalData = evaluation.data;
  const current = history[0];
  const earlier = history.slice(1);

  return (
    <>
      <PageHeader kicker={t("kicker")} title={t("title")} description={t("description")} />
      <div className="ask-grid">
        <div className="ask-main">
          <form
            className="panel ask-form"
            onSubmit={(e) => {
              e.preventDefault();
              void run(question);
            }}
          >
            <label htmlFor={inputId} className="ask-label">
              {t("label")}
            </label>
            <div className="ask-input-row">
              <textarea
                id={inputId}
                className="question-input"
                rows={2}
                value={question}
                placeholder={t("placeholder")}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void run(question);
                  }
                }}
              />
              <button type="submit" className="civic-button primary ask-submit" disabled={busy || !question.trim()}>
                {busy ? <Loader2 className="spin" aria-hidden /> : <Send aria-hidden />}
                {busy ? t("asking") : t("submit")}
              </button>
            </div>
            <div className="example-block">
              <p className="example-title">{t("examples")}</p>
              {examples.error ? <ErrorState error={examples.error} onRetry={examples.reload} /> : null}
              <ul className="example-chips">
                {(examples.data ?? []).map((ex) => {
                  const kind = kindOf(ex);
                  const Icon = KIND_ICON[kind];
                  const text = pick(ex.question, locale);
                  return (
                    <li key={ex.id}>
                      <button
                        type="button"
                        className={`example-chip kind-${kind}`}
                        disabled={busy}
                        onClick={() => {
                          setQuestion(text);
                          void run(text, ex.id);
                        }}
                      >
                        <Icon aria-hidden />
                        <span className="example-text">
                          <span className="sr-only">{t("askPrefix")} </span>
                          {text}
                        </span>
                        <span className="example-kind">
                          <span className="sr-only">· </span>
                          {t(`exampleKind.${kind}`)}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          </form>

          <p className="sr-only" aria-live="polite" aria-atomic>
            {busy
              ? t("asking")
              : current
                ? `${tAll(`labels.${current.answer.label}.name`)}: ${pick(current.answer.answer, locale)}`
                : ""}
          </p>
          <div className="answer-zone" aria-busy={busy}>
            {error ? <ErrorState error={error} /> : null}
            {!current && !busy && !error && (
              <div className="answer-empty">
                <MessageSquareDashed aria-hidden />
                <div>
                  <strong>{t("emptyTitle")}</strong>
                  <p>{t("empty")}</p>
                </div>
              </div>
            )}
            {busy && (
              <div className="panel answer-pending">
                <Loader2 className="spin" aria-hidden />
                <span>{t("asking")}</span>
              </div>
            )}
            {current && (
              <AnswerCard
                key={current.id}
                cardRef={answerRef}
                answer={current.answer}
                previous={earlier.find((e) => e.answer.question === current.answer.question)?.answer}
              />
            )}
            {earlier.length > 0 && (
              <section className="history" aria-labelledby="history-title">
                <h2 id="history-title">{t("history")}</h2>
                <ul>
                  {earlier.map((e) => (
                    <li key={e.id}>
                      <LabelStamp label={e.answer.label} />
                      <span className="history-q">{e.answer.question}</span>
                      <span className="history-a">{pick(e.answer.answer, locale)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        </div>

        <aside className="ask-aside" aria-labelledby="legend-title">
          <div className="panel legend-panel">
            <h2 id="legend-title">{t("legend")}</h2>
            <ul className="label-legend">
              {ASK_LABELS.map((label) => (
                <LegendItem key={label} label={label} evaluation={evalData} />
              ))}
            </ul>
            {evalData && (
              <p className="fine-print">
                {t("evalTitle", { total: evalData.by_label.reduce((s, r) => s + r.total, 0) })} ·{" "}
                {t("evalNote", { time: formatDateTime(evalData.run_at, locale) })}
              </p>
            )}
          </div>
        </aside>
      </div>
    </>
  );
}

function LegendItem({ label, evaluation }: { label: AskLabel; evaluation: AskEval | undefined }) {
  const t = useTranslations();
  const row = evaluation?.by_label.find((r) => r.label === label);
  const total = evaluation?.by_label.reduce((s, r) => s + r.total, 0) ?? 0;
  return (
    <li>
      <div className="legend-head">
        <LabelStamp label={label} />
        {row && (
          <span
            className="eval-chip"
            title={t("ask.evalTitle", { total })}
            aria-label={`${t("ask.evalChip", { matched: row.matched, total: row.total })} · ${t("ask.evalTitle", { total })}`}
          >
            {t("ask.evalChip", { matched: row.matched, total: row.total })}
          </span>
        )}
      </div>
      <p>{t(`labels.${label}.meaning`)}</p>
    </li>
  );
}

function AnswerCard({
  answer: a,
  previous,
  cardRef,
}: {
  answer: AskAnswer;
  previous?: AskAnswer;
  cardRef?: React.RefObject<HTMLElement | null>;
}) {
  const t = useTranslations();
  const locale = useLocale();
  const { board } = useSystem();
  const indicator = a.passport_code ? board.data?.indicators.find((i) => i.code === a.passport_code) : undefined;
  const value =
    a.value != null && a.unit
      ? formatIndicatorValue(a.value, a.unit, locale, indicator ? pick(indicator.unit_label, locale) : undefined)
      : null;
  const tone = ASK_LABEL_TONE[a.label];
  // Result columns are named by the query (e.g. `on_time_pct_last_2_months`): known ones get a
  // translated header, any other is made readable.
  const columnLabel = (name: string) => {
    const key = `ask.columns.${name}`;
    return /^[a-z0-9_]+$/i.test(name) && t.has(key) ? t(key) : humaniseColumn(name);
  };

  return (
    <article ref={cardRef} className={`panel answer-card label-${a.label}`}>
      <ReplayStamp />
      <header className="answer-head">
        <LabelStamp label={a.label} animate />
        <div className="answer-meaning">
          <h2 className="answer-title" data-answer-heading tabIndex={-1}>
            {t(`labels.${a.label}.name`)}
          </h2>
          <p>{t(`labels.${a.label}.meaning`)}</p>
        </div>
      </header>
      {previous && previous.label !== a.label && (
        <p className="answer-changed">
          {t("ask.changed", { from: t(`labels.${previous.label}.name`) })} <ArrowRight aria-hidden />{" "}
          <strong>{t(`labels.${a.label}.name`)}</strong>
        </p>
      )}
      <p className="answer-question">“{a.question}”</p>
      <p className="interpreted">
        <span>{t("ask.interpreted")}</span>
        <ToneChip tone="info">{pick(a.interpreted_as, locale)}</ToneChip>
      </p>

      {value && (
        <p className={`answer-figure tone-text-${tone}`}>
          <span className="figure-number">{value.number}</span>
          {value.unit && <span className={`figure-unit ${value.tight ? "tight" : ""}`}>{value.unit}</span>}
        </p>
      )}
      <p className="answer-text">{pick(a.answer, locale)}</p>

      {a.method && (
        <div className="answer-block">
          <h3>{t("ask.method")}</h3>
          <p>{pick(a.method, locale)}</p>
        </div>
      )}

      {a.gap && (
        <div className="gap-card">
          <FileSpreadsheet aria-hidden />
          <div>
            <span className="gap-kicker">{t("ask.gapTitle")}</span>
            <strong>{pick(a.gap.name, locale)}</strong>
            <span title={t("tile.ownerPlaceholder")}>
              {t("ask.gapOwner")}: {pick(a.gap.owner, locale)}
            </span>
            {a.gap.sample && <span className="gap-sample">{t("ask.gapSample", { name: a.gap.sample })}</span>}
          </div>
          <Link
            className="civic-button primary"
            href={`/ingest?dataset=${encodeURIComponent(a.gap.dataset)}${a.passport_code ? `&ask=${encodeURIComponent(a.passport_code)}` : ""}`}
          >
            <Upload aria-hidden />
            {t("ask.gapCta")}
          </Link>
        </div>
      )}

      {a.blocked_reason && (
        <div className="blocked-card" role="note">
          <ShieldAlert aria-hidden />
          <div>
            <strong>{t("ask.blockedTitle")}</strong>
            <p>{pick(a.blocked_reason, locale)}</p>
          </div>
        </div>
      )}

      {a.table && (
        <div className="answer-block">
          <h3>{t("ask.result")}</h3>
          <div className="table-scroll" tabIndex={0} role="region" aria-label={t("ask.result")}>
            <table className="data-table compact">
              <thead>
                <tr>
                  {a.table.columns.map((c, j) => (
                    <th key={c} scope="col" className={typeof a.table!.rows[0]?.[j] === "number" ? "numeric" : undefined}>
                      {columnLabel(c)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {a.table.rows.map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) => (
                      <td key={j} className={typeof cell === "number" ? "numeric" : ""}>
                        {formatCell(cell, locale)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {a.sources.length > 0 && (
        <div className="answer-block">
          <h3>{t("ask.sources")}</h3>
          <ul className="answer-sources">
            {a.sources.map((s) => {
              const ranges = summariseRanges(s.rows);
              return (
                <li key={`${s.source_id}-${s.rows}`}>
                  <FileSpreadsheet aria-hidden />
                  <span className="lineage-file">{s.filename}</span>
                  <span className="answer-rows" title={ranges.more > 0 ? s.rows : undefined}>
                    {t("ask.rows", { rows: ranges.text })}
                    {ranges.more > 0 && <> {t("passport.rangesMore", { count: ranges.more })}</>}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <footer className="answer-foot">
        <span className="llm-line">
          {a.llm.used ? <Sparkles aria-hidden /> : <Cpu aria-hidden />}
          {a.llm.used ? t("ask.llmUsed", { model: a.llm.model ?? "AI" }) : t("ask.llmRules")}
          {a.llm.cached && (
            <span className="cached-badge" title={t("ask.cachedHint")}>
              {t("ask.cached")}
            </span>
          )}
        </span>
        {a.passport_code && (
          <Link className="text-button" href={`/indicators/${encodeURIComponent(a.passport_code)}`}>
            <CodeChip>{a.passport_code}</CodeChip>
            {t("ask.passport", { code: a.passport_code })}
            <ArrowUpRight aria-hidden />
          </Link>
        )}
      </footer>
    </article>
  );
}
