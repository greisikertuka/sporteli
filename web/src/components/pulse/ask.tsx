"use client";
import { useState, type FormEvent } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  ArrowUpRight,
  CheckCircle2,
  Database,
  MessageSquareText,
  Send,
} from "lucide-react";
import { getMetrics, numberFormatter } from "@/lib/pulse-data";
import { PulseMark } from "@/components/pulse-mark";
import { DetailsSheet } from "./details-sheet";

type Question = "overdue" | "performance" | "volume";
const keys = {
  overdue: "qOverdue",
  performance: "qPerformance",
  volume: "qVolume",
} as const;
const sql = {
  overdue:
    "SELECT department, overdue\nFROM sample_department_metrics\nWHERE period = '2026-09-01/24'\nORDER BY overdue DESC\nLIMIT 1;",
  performance:
    "SELECT 100.0 * SUM(on_time) / NULLIF(SUM(resolved), 0)\n  AS on_time_percent\nFROM sample_department_metrics\nWHERE period = '2026-09-01/24';",
  volume:
    "SELECT SUM(received) AS total_requests\nFROM sample_department_metrics\nWHERE period = '2026-09-01/24';",
};

export function Ask() {
  const t = useTranslations("pulse"),
    locale = useLocale(),
    n = numberFormatter(locale),
    decimal = numberFormatter(locale, 1);
  const [question, setQuestion] = useState(""),
    [answer, setAnswer] = useState<Question | null>(null),
    [error, setError] = useState(""),
    [sourcesOpen, setSourcesOpen] = useState(false);
  const metrics = getMetrics("all", "september"),
    publicMetrics = getMetrics("public", "september");
  const normalize = (text: string) =>
    text
      .trim()
      .toLocaleLowerCase()
      .replace(/[?!.]+$/, "");
  function choose(key: Question) {
    setQuestion(t(keys[key]));
    setAnswer(key);
    setError("");
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!question.trim()) {
      setError(t("emptyQuestion"));
      return;
    }
    const key = (Object.keys(keys) as Question[]).find(
      (key) => normalize(question) === normalize(t(keys[key])),
    );
    if (key) {
      setAnswer(key);
      setError("");
    } else {
      setAnswer(null);
      setError(t("unsupportedQuestion"));
    }
  }
  const answerTitle =
    answer === "overdue"
      ? t("answerOverdue", { count: publicMetrics.overdue })
      : answer === "performance"
        ? t("answerPerformance", { rate: decimal.format(metrics.onTimeRate) })
        : t("answerVolume", { count: n.format(metrics.received) });
  const answerBody =
    answer === "overdue"
      ? t("answerOverdueBody", {
          share: decimal.format(
            (publicMetrics.overdue / metrics.overdue) * 100,
          ),
          total: metrics.overdue,
        })
      : answer === "performance"
        ? t("answerPerformanceBody", {
            onTime: n.format(metrics.onTime),
            resolved: n.format(metrics.resolved),
          })
        : t("answerVolumeBody");
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{t("askTitle")}</h1>
          <p className="page-description">{t("askDescription")}</p>
        </div>
      </div>
      <div className="ask-layout">
        <div>
          <section className="panel ask-panel">
            <form onSubmit={submit}>
              <label htmlFor="question" className="question-label">
                {t("askLabel")}
              </label>
              <textarea
                id="question"
                className="question-input"
                placeholder={t("askPlaceholder")}
                value={question}
                onChange={(e) => {
                  setQuestion(e.target.value);
                  setError("");
                }}
                maxLength={600}
                aria-describedby={error ? "question-error" : undefined}
                aria-invalid={Boolean(error)}
              />
              {error && (
                <div id="question-error" className="form-error" role="alert">
                  {error}
                </div>
              )}
              <div className="question-actions">
                <button type="submit" className="civic-button primary">
                  <Send size={15} />
                  {t("askButton")}
                </button>
              </div>
            </form>
            <div className="question-examples">
              <p>{t("askExamples")}</p>
              {(Object.keys(keys) as Question[]).map((key) => (
                <button
                  className="question-example"
                  key={key}
                  onClick={() => choose(key)}
                >
                  {t(keys[key])}
                  <ArrowUpRight size={16} />
                </button>
              ))}
            </div>
          </section>
          <div aria-live="polite">
            {answer && (
              <section
                className="panel answer-panel"
                key={`${answer}-${locale}`}
              >
                <div className="answer-label">
                  <CheckCircle2 size={14} />
                  {t("sampleAnswer")}
                </div>
                <p className="mb-3! text-xs!">{t(keys[answer])}</p>
                <h2>{answerTitle}</h2>
                <p>{answerBody}</p>
                <div className="mt-5 flex gap-3 flex-wrap">
                  <span className="sample-badge">
                    {t("periodLabel", { month: t("months.september") })}
                  </span>
                  <button
                    className="text-button"
                    onClick={() => setSourcesOpen(true)}
                  >
                    <Database />
                    {t("viewLineage")}
                  </button>
                </div>
                <details className="query-disclosure">
                  <summary>{t("sql")}</summary>
                  <p className="section-subtitle">{t("queryNote")}</p>
                  <pre>
                    <code>{sql[answer]}</code>
                  </pre>
                </details>
              </section>
            )}
          </div>
        </div>
        <aside className="ask-context">
          <PulseMark />
          <h2>{t("answerEvidence")}</h2>
          <p>{t("answerEvidenceDescription")}</p>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <MessageSquareText size={15} />
            {t("sampleAnswer")}
          </div>
        </aside>
      </div>
      <DetailsSheet open={sourcesOpen} onOpenChange={setSourcesOpen} />
    </>
  );
}
