"use client";
import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Database, Download, Printer } from "lucide-react";
import { PulseMark } from "@/components/pulse-mark";
import { getMetrics, numberFormatter } from "@/lib/pulse-data";
import { DetailsSheet } from "./details-sheet";

export function Briefing() {
  const t = useTranslations("pulse"),
    locale = useLocale(),
    n = numberFormatter(locale),
    decimal = numberFormatter(locale, 1);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const metrics = getMetrics("all", "september");
  const period = t("periodLabel", { month: t("months.september") });
  const intro = t("briefingIntro", {
    received: n.format(metrics.received),
    resolved: n.format(metrics.resolved),
    rate: decimal.format(metrics.onTimeRate),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{t("briefingTitle")}</h1>
          <p className="page-description">{t("briefingDescription")}</p>
        </div>
        <div className="action-group">
          <button className="civic-button" onClick={() => window.print()}>
            <Printer />
            {t("print")}
          </button>
          <a
            className="civic-button primary"
            href={`/briefing/download?locale=${locale}`}
            download
          >
            <Download />
            {t("download")}
          </a>
        </div>
      </div>
      <div className="briefing-layout">
        <article className="report-paper">
          <div className="report-letterhead">
            <div className="report-brand">
              <PulseMark />
              <div>
                Elbasan Pulse
                <small>
                  {locale === "sq"
                    ? "Bashkia Elbasan"
                    : "Municipality of Elbasan"}
                </small>
              </div>
            </div>
            <span className="sample-badge">{t("draft")}</span>
          </div>
          <h2 className="report-title">{t("briefingHeading")}</h2>
          <p className="report-period">{period}</p>
          <h3>{t("executiveSummary")}</h3>
          <p className="report-lead">{t("briefingLead")}</p>
          <p className="report-paragraph">{intro}</p>
          <div className="report-summary">
            <div>
              <span>{t("received")}</span>
              <strong>{n.format(metrics.received)}</strong>
            </div>
            <div>
              <span>{t("onTime")}</span>
              <strong>{decimal.format(metrics.onTimeRate)}%</strong>
            </div>
            <div>
              <span>{t("overdue")}</span>
              <strong>{n.format(metrics.overdue)}</strong>
            </div>
          </div>
          <section className="report-section">
            <h3>{t("briefingPriority")}</h3>
            <p className="report-paragraph">{t("briefingPriorityBody")}</p>
          </section>
          <section className="report-section">
            <h3>{t("briefingQuality")}</h3>
            <p className="report-paragraph">{t("briefingQualityBody")}</p>
          </section>
          <p className="report-disclaimer">{t("briefingFooter")}</p>
        </article>
        <aside className="briefing-meta">
          <h2>{t("dataSnapshot")}</h2>
          <dl>
            <dt>{t("period")}</dt>
            <dd>{period}</dd>
            <dt>{t("connectedSources")}</dt>
            <dd>{t("sourceCount", { count: 4 })}</dd>
            <dt>{t("status")}</dt>
            <dd>
              <span className="status-label warn">{t("draft")}</span>
            </dd>
          </dl>
          <button
            className="text-button mt-6"
            onClick={() => setSourcesOpen(true)}
          >
            <Database />
            {t("viewLineage")}
          </button>
        </aside>
      </div>
      <DetailsSheet open={sourcesOpen} onOpenChange={setSourcesOpen} />
    </>
  );
}
