"use client";
import { useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import {
  ArrowDownLeft,
  ArrowUp,
  ArrowUpRight,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Clock3,
  FileText,
  Building2,
  HardHat,
  HeartHandshake,
  Landmark,
  SlidersHorizontal,
  TriangleAlert,
} from "lucide-react";
import {
  departments,
  getMetrics,
  numberFormatter,
  type Department,
  type DepartmentFilter,
  type Period,
} from "@/lib/pulse-data";
import { DetailsSheet } from "./details-sheet";
import { TrendChart } from "./trend-chart";
const icons = {
  public: HardHat,
  urban: Building2,
  social: HeartHandshake,
  finance: Landmark,
};

export function Overview() {
  const t = useTranslations("pulse"),
    locale = useLocale(),
    n = numberFormatter(locale),
    decimal = numberFormatter(locale, 1);
  const [department, setDepartment] = useState<DepartmentFilter>("all"),
    [period, setPeriod] = useState<Period>("september"),
    [details, setDetails] = useState<Department | "all" | null>(null);
  const metrics = getMetrics(department, period),
    previous = getMetrics(department, "august"),
    publicMetrics = getMetrics("public", period);
  const filtered = departments.filter(
    (d) => department === "all" || d === department,
  );
  const showQueue = department === "all" || department === "public",
    showStale =
      period === "september" &&
      (department === "all" || department === "urban");
  const onTimeDiff = metrics.onTimeRate - previous.onTimeRate,
    receivedDiff = (metrics.received / previous.received - 1) * 100;
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{t("overviewTitle")}</h1>
          <p className="page-description">{t("overviewDescription")}</p>
        </div>
        <Link className="civic-button primary" href="/briefing">
          <FileText />
          {t("viewReport")}
        </Link>
      </div>
      <div className="filters">
        <div className="filter-group">
          <label className="select-field">
            <CalendarDays size={15} />
            <span className="sr-only">{t("period")}</span>
            <select
              aria-label={t("period")}
              value={period}
              onChange={(event) => setPeriod(event.target.value as Period)}
            >
              {(["september", "august"] as const).map((p) => (
                <option key={p} value={p}>
                  {t("periodLabel", { month: t(`months.${p}`) })}
                </option>
              ))}
            </select>
          </label>
          <label className="select-field">
            <SlidersHorizontal size={14} />
            <span className="sr-only">{t("department")}</span>
            <select
              aria-label={t("department")}
              value={department}
              onChange={(event) =>
                setDepartment(event.target.value as DepartmentFilter)
              }
            >
              <option value="all">{t("allDepartments")}</option>
              {departments.map((d) => (
                <option key={d} value={d}>
                  {t(`departments.${d}`)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <span className="filter-note">{t("comparisonNote")}</span>
      </div>
      <div className="metrics-band" aria-live="polite">
        <section className="metric">
          <div className="metric-label">
            {t("received")}
            <ArrowDownLeft aria-hidden />
          </div>
          <div className="metric-value">{n.format(metrics.received)}</div>
          <div className="metric-context">
            {period === "september" ? (
              <>
                <ArrowUpRight size={13} />
                <span>
                  {receivedDiff >= 0 ? "+" : ""}
                  {decimal.format(receivedDiff)}%
                </span>{" "}
                {t("vsPrevious")}
              </>
            ) : (
              t("previousPeriod")
            )}
          </div>
        </section>
        <section className="metric">
          <div className="metric-label">
            {t("onTime")}
            <CheckCircle2 aria-hidden />
          </div>
          <div className="metric-value">
            {decimal.format(metrics.onTimeRate)}
            <small>%</small>
          </div>
          <div
            className={`metric-context ${onTimeDiff >= 0 ? "good" : "warn"}`}
          >
            {period === "september" ? (
              <>
                <ArrowUp size={12} />
                {onTimeDiff >= 0 ? "+" : ""}
                {decimal.format(onTimeDiff)} {t("percentagePoints")}
              </>
            ) : (
              t("goal")
            )}
          </div>
        </section>
        <section className="metric">
          <div className="metric-label">
            {t("overdue")}
            <Clock3 aria-hidden />
          </div>
          <div className="metric-value">{n.format(metrics.overdue)}</div>
          <div className="metric-context warn">
            {department === "all"
              ? t("overdueContext", { count: publicMetrics.overdue })
              : t("ofReceived")}
          </div>
        </section>
      </div>
      <div className="dashboard-middle">
        <TrendChart
          department={department}
          period={period}
          onSources={() => setDetails(department)}
        />
        <section className="attention-panel">
          <div className="attention-title">
            <h2>{t("attention")}</h2>
            {(showQueue || showStale) && (
              <span className="count-badge">
                {Number(showQueue) + Number(showStale)}
              </span>
            )}
          </div>
          {showQueue && (
            <article className="attention-item">
              <h3>
                <Clock3 aria-hidden />
                {t("overdueTitle", { count: publicMetrics.overdue })}
              </h3>
              <p>{t("overdueDescription")}</p>
              <button
                className="text-button"
                onClick={() => setDetails("public")}
              >
                {t("viewRequests")}
                <ChevronRight />
              </button>
            </article>
          )}
          {showStale && (
            <article className="attention-item">
              <h3>
                <TriangleAlert aria-hidden />
                {t("staleTitle")}
              </h3>
              <p>{t("staleDescription")}</p>
              <button
                className="text-button"
                onClick={() => setDetails("urban")}
              >
                {t("checkSource")}
                <ChevronRight />
              </button>
            </article>
          )}
          {!showQueue && !showStale && (
            <div className="empty-attention">
              <CheckCircle2 size={24} />
              <h3>
                {metrics.onTimeRate >= 90 ? t("noAlerts") : t("belowTarget")}
              </h3>
              <p>
                {metrics.onTimeRate >= 90
                  ? t("noAlertsDescription")
                  : t("goal")}
              </p>
            </div>
          )}
        </section>
      </div>
      <section className="department-section">
        <div className="section-heading">
          <div>
            <h2>{t("performance")}</h2>
            <p className="section-subtitle">{t("performanceDescription")}</p>
          </div>
          <span>{t("goal")}</span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">{t("department")}</th>
              <th scope="col" className="numeric">
                {t("requests")}
              </th>
              <th scope="col" className="numeric">
                {t("onTime")}
              </th>
              <th scope="col">{t("status")}</th>
              <th className="table-chevron">
                <span className="sr-only">{t("detailTitle")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((d) => {
              const m = getMetrics(d, period),
                Icon = icons[d],
                stale = d === "urban" && period === "september";
              return (
                <tr key={d}>
                  <td>
                    <button
                      className="department-name"
                      onClick={() => setDetails(d)}
                    >
                      <span className="department-icon">
                        <Icon size={16} />
                      </span>
                      {t(`departments.${d}`)}
                    </button>
                  </td>
                  <td className="numeric">{n.format(m.received)}</td>
                  <td className="numeric">
                    <span className="rate-cell">
                      <span className="rate-track" aria-hidden>
                        <i style={{ width: `${m.onTimeRate}%` }} />
                      </span>
                      {decimal.format(m.onTimeRate)}%
                    </span>
                  </td>
                  <td>
                    <span
                      className={`status-label ${stale || m.onTimeRate < 90 ? "warn" : "good"}`}
                    >
                      {stale
                        ? t("stale")
                        : m.onTimeRate >= 90
                          ? t("onTarget")
                          : t("belowTarget")}
                    </span>
                  </td>
                  <td className="table-chevron">
                    <button
                      className="row-action"
                      onClick={() => setDetails(d)}
                      aria-label={t("openDepartment", {
                        department: t(`departments.${d}`),
                      })}
                    >
                      <ChevronRight size={16} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="table-note">{t("comparisonNote")}</p>
      </section>
      <DetailsSheet
        open={details !== null}
        onOpenChange={(open) => !open && setDetails(null)}
        department={details && details !== "all" ? details : undefined}
        period={period}
      />
    </>
  );
}
