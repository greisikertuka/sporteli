"use client";

import { LineChart } from "echarts/charts";
import { GridComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import ReactEChartsCore from "echarts-for-react/esm/core";
import { Table2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useId, useMemo, useState } from "react";

import { useReducedMotion } from "@/hooks/use-api";
import { formatIndicatorValue, formatNumber, formatPeriod, formatTarget, monthLabel, niceBounds, periodTick } from "@/lib/format";

echarts.use([LineChart, GridComponent, TooltipComponent, MarkLineComponent, SVGRenderer]);

/** Mirrors the chart tokens in globals.css (light / dark are separate, validated steps). */
const PALETTE = {
  light: {
    line: "#2454ad",
    area: "rgba(36, 84, 173, 0.10)",
    target: "#a07812",
    grid: "#e6e8eb",
    axis: "#606d7e",
    surface: "#ffffff",
    ink: "#192d50",
    border: "#e0e3e7",
  },
  dark: {
    line: "#82a9e0",
    area: "rgba(130, 169, 224, 0.12)",
    target: "#c9a45b",
    grid: "#2c3440",
    axis: "#a4aeba",
    surface: "#1d232b",
    ink: "#e7e9ee",
    border: "#313946",
  },
};

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

export type TrendSeries = { period: string; value: number | null }[];

function buildOption(a: {
  series: TrendSeries;
  unit: string;
  unitLabel: string;
  target: number | null;
  name: string;
  locale: string;
  dark: boolean;
  reduced: boolean;
  targetWord: string;
}) {
  const { series, unit, unitLabel, target, name, locale, reduced, targetWord } = a;
  const c = PALETTE[a.dark ? "dark" : "light"];
  const values = series.map((p) => p.value);
  const numeric = values.filter((v): v is number => v != null);
  const bounds = target != null ? [...numeric, target] : numeric;
  const axis = niceBounds(bounds.length ? bounds : [0, 1]);
  const fmt = (v: number) => formatIndicatorValue(v, unit, locale, unitLabel).text;

  return {
    animationDuration: reduced ? 0 : 650,
    animationDurationUpdate: reduced ? 0 : 450,
    textStyle: { fontFamily: "var(--font-civic), system-ui, sans-serif" },
    // ECharts 6: the documented replacement for the deprecated `containLabel: true`.
    grid: { left: 6, right: 104, top: 28, bottom: 6, outerBoundsMode: "same", outerBoundsContain: "axisLabel" },
    xAxis: {
      type: "category",
      data: series.map((p) => periodTick(p.period, locale)),
      boundaryGap: series.length === 1,
      axisLine: { lineStyle: { color: c.grid } },
      axisTick: { show: false },
      axisLabel: { color: c.axis, fontSize: 12 },
    },
    yAxis: {
      type: "value",
      min: axis.min,
      max: axis.max,
      interval: axis.step,
      splitLine: { lineStyle: { color: c.grid } },
      axisLabel: { color: c.axis, fontSize: 12, formatter: (v: number) => formatNumber(v, locale, Number.isInteger(v) ? 0 : 1) },
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: c.surface,
      borderColor: c.border,
      textStyle: { color: c.ink, fontSize: 12 },
      axisPointer: { type: "line", lineStyle: { color: c.axis, width: 1 } },
      formatter: (params: { dataIndex: number }[]) => {
        const i = params[0]?.dataIndex ?? 0;
        const p = series[i];
        const v = p?.value;
        return `<div style="min-width:120px"><strong style="font-size:14px">${esc(v == null ? "–" : fmt(v))}</strong><br/><span style="color:${c.axis}">${esc(formatPeriod(p?.period, locale))}</span>${
          target != null ? `<br/><span style="color:${c.axis}">${esc(targetWord)} ${esc(formatTarget(target, unit, locale, unitLabel))}</span>` : ""
        }</div>`;
      },
    },
    series: [
      {
        type: "line",
        name,
        data: values,
        symbol: "circle",
        symbolSize: 8,
        showSymbol: series.length <= 12,
        lineStyle: { width: 2, color: c.line, cap: "round", join: "round" },
        itemStyle: { color: c.line, borderColor: c.surface, borderWidth: 2 },
        areaStyle: { color: c.area },
        emphasis: { scale: 1.4 },
        endLabel: {
          show: true,
          color: c.ink,
          fontWeight: 600,
          fontSize: 12,
          // "80,7% · gusht": the month is always named so the end of a monthly series is never
          // read as the tile's year-to-date value
          formatter: (p: { value: number | null; dataIndex?: number }) => {
            if (p.value == null) return "";
            const at = series[p.dataIndex ?? series.length - 1]?.period;
            const ym = at ? /^(\d{4})-(\d{2})/.exec(at) : null;
            return ym ? `${fmt(p.value)} · ${monthLabel(Number(ym[2]), locale, "long")}` : fmt(p.value);
          },
        },
        markLine:
          target != null
            ? {
                silent: true,
                symbol: "none",
                lineStyle: { type: "dashed", color: c.target, width: 1.5 },
                label: { formatter: `${targetWord} ${formatTarget(target, unit, locale, unitLabel)}`, position: "insideStartTop", color: c.axis, fontSize: 11 },
                data: [{ yAxis: target }],
              }
            : undefined,
      },
    ],
  };
}

export function TrendChart({
  series,
  unit,
  unitLabel,
  target,
  name,
  seriesKind = "monthly",
  height = 260,
}: {
  series: TrendSeries;
  unit: string;
  unitLabel: string;
  target: number | null;
  name: string;
  /** What a point means: that month alone, or the running value from January (API `series_kind`). */
  seriesKind?: "monthly" | "ytd_running";
  height?: number;
}) {
  const t = useTranslations("board.trend");
  const locale = useLocale();
  const { resolvedTheme } = useTheme();
  const reduced = useReducedMotion();
  const [showTable, setShowTable] = useState(false);
  const tableId = useId();

  const seriesKey = JSON.stringify(series);
  const targetWord = t("target");
  const dark = resolvedTheme === "dark";
  const option = useMemo(
    () => buildOption({ series: JSON.parse(seriesKey) as TrendSeries, unit, unitLabel, target, name, locale, dark, reduced, targetWord }),
    [seriesKey, unit, unitLabel, target, name, locale, dark, reduced, targetWord],
  );
  const rangeText = series.length ? formatPeriod(`${series[0].period}/${series.at(-1)!.period}`, locale) : "";
  const fmt = (v: number) => formatIndicatorValue(v, unit, locale, unitLabel).text;

  return (
    <div className="trend-figure">
      <p className="trend-kind">{seriesKind === "ytd_running" ? t("kindYtd") : t("kindMonthly")}</p>
      <div
        role="img"
        aria-label={t("summary", {
          name,
          period: rangeText,
          kind: seriesKind === "ytd_running" ? t("kindWordYtd") : t("kindWordMonthly"),
        })}
        className="trend-canvas"
        style={{ height }}
      >
        <ReactEChartsCore
          echarts={echarts}
          option={option}
          notMerge
          lazyUpdate
          opts={{ renderer: "svg" }}
          style={{ height, width: "100%" }}
          aria-hidden
        />
      </div>
      <button
        type="button"
        className="text-button muted"
        aria-expanded={showTable}
        aria-controls={tableId}
        onClick={() => setShowTable((v) => !v)}
      >
        <Table2 aria-hidden />
        {showTable ? t("hideTable") : t("table")}
      </button>
      {showTable && (
        <div id={tableId} className="table-scroll">
          <table className="data-table compact">
            <caption className="sr-only">{name}</caption>
            <thead>
              <tr>
                <th scope="col">{t("period")}</th>
                <th scope="col" className="numeric">
                  {t("value")}
                </th>
              </tr>
            </thead>
            <tbody>
              {series.map((p) => (
                <tr key={p.period}>
                  <td>{formatPeriod(p.period, locale)}</td>
                  <td className="numeric">{p.value == null ? "–" : fmt(p.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
