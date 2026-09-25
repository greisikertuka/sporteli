"use client";
import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Database, Table2 } from "lucide-react";
import {
  getTrend,
  numberFormatter,
  monthLabel,
  type DepartmentFilter,
  type Period,
} from "@/lib/pulse-data";

export function TrendChart({
  department,
  period,
  onSources,
}: {
  department: DepartmentFilter;
  period: Period;
  onSources: () => void;
}) {
  const t = useTranslations("pulse"),
    locale = useLocale(),
    n = numberFormatter(locale);
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(600),
    [selected, setSelected] = useState<number | null>(null),
    [table, setTable] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver((entries) =>
      setWidth(entries[0].contentRect.width),
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  const data = getTrend(department, period),
    w = Math.max(220, width),
    h = 230,
    left = 39,
    right = 13,
    top = 25,
    bottom = 29;
  const max =
    Math.ceil(
      Math.max(...data.flatMap((d) => [d.received, d.resolved])) / 200,
    ) * 200;
  const x = (i: number) => left + (i * (w - left - right)) / (data.length - 1),
    y = (n: number) => top + (1 - n / max) * (h - top - bottom);
  const path = (key: "received" | "resolved") =>
    data
      .map((point, i) => `${i ? "L" : "M"}${x(i)},${y(point[key])}`)
      .join(" ");
  const month = (num: number) => monthLabel(num, locale);
  const active = selected !== null ? data[selected] : null;
  return (
    <section className="chart-panel">
      <h2>{t("chartTitle")}</h2>
      <p className="section-subtitle">{t("chartDescription")}</p>
      <div className="chart-legend">
        <span>
          <i className="line-key" />
          {t("chartReceived")}
        </span>
        <span>
          <i className="line-key dashed" />
          {t("chartResolved")}
        </span>
      </div>
      <div
        className="trend-wrap"
        ref={ref}
        onMouseLeave={() => setSelected(null)}
      >
        <svg
          className="trend-chart"
          viewBox={`0 0 ${w} ${h}`}
          role="img"
          aria-label={t("chartSummary")}
        >
          <title>{t("chartTitle")}</title>
          {[0, max / 2, max].map((value) => (
            <g key={value}>
              <line
                className="chart-gridline"
                x1={left}
                x2={w - right}
                y1={y(value)}
                y2={y(value)}
              />
              <text x={left - 9} y={y(value) + 4} textAnchor="end">
                {n.format(value)}
              </text>
            </g>
          ))}
          <path d={path("resolved")} className="trend-line secondary" />
          <path
            key={`${department}-${period}`}
            d={path("received")}
            className="trend-line primary"
            pathLength={1}
          />
          {data.map((d, i) => (
            <text
              key={d.month}
              x={x(i)}
              y={h - 5}
              textAnchor={
                i === 0 ? "start" : i === data.length - 1 ? "end" : "middle"
              }
            >
              {month(d.month)}
            </text>
          ))}
          {active && selected !== null && (
            <g>
              <line
                x1={x(selected)}
                x2={x(selected)}
                y1={top}
                y2={h - bottom}
                stroke="var(--border)"
              />
              <circle
                cx={x(selected)}
                cy={y(active.received)}
                r={4}
                fill="var(--chart-1)"
                stroke="var(--card)"
                strokeWidth={2}
              />
              <circle
                cx={x(selected)}
                cy={y(active.resolved)}
                r={3.5}
                fill="var(--chart-2)"
                stroke="var(--card)"
                strokeWidth={2}
              />
            </g>
          )}
        </svg>
        {data.map((point, i) => (
          <button
            key={point.month}
            className="chart-hit"
            style={{
              left: `${(x(i) / w) * 100}%`,
              top: `${(y(point.received) / h) * 100}%`,
            }}
            onMouseEnter={() => setSelected(i)}
            onFocus={() => setSelected(i)}
            onBlur={() => setSelected(null)}
            onClick={() => setSelected(selected === i ? null : i)}
            aria-label={`${month(point.month)}: ${t("chartReceived")} ${n.format(point.received)}, ${t("chartResolved")} ${n.format(point.resolved)}`}
          />
        ))}
        {active && (
          <div className="chart-tooltip" aria-hidden>
            <strong>{month(active.month)} 2026</strong>
            <span>
              {t("chartReceived")}: {n.format(active.received)}
            </span>
            <span>
              {t("chartResolved")}: {n.format(active.resolved)}
            </span>
          </div>
        )}
      </div>
      <div className="chart-footer">
        <button className="text-button muted" onClick={onSources}>
          <Database />
          {t("sourceCount", { count: department === "all" ? 4 : 1 })}
          <span aria-hidden>·</span>
          {t("viewLineage")}
        </button>
        <button
          className="text-button muted"
          aria-expanded={table}
          aria-controls="trend-data"
          onClick={() => setTable(!table)}
        >
          <Table2 />
          {t("chartTable")}
        </button>
      </div>
      {table && (
        <div id="trend-data" className="table-scroll mt-5">
          <table className="data-table">
            <caption className="sr-only">{t("chartTitle")}</caption>
            <thead>
              <tr>
                <th>{t("month")}</th>
                <th className="numeric">{t("chartReceived")}</th>
                <th className="numeric">{t("chartResolved")}</th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.month}>
                  <td>{month(d.month)}</td>
                  <td className="numeric">{n.format(d.received)}</td>
                  <td className="numeric">{n.format(d.resolved)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
