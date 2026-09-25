"use client";
import { Database, X, ArrowUpRight } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useRef } from "react";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetDescription,
  SheetClose,
} from "@/components/ui/sheet";
import {
  getMetrics,
  sources,
  numberFormatter,
  formatSourceDate,
  type Department,
  type Period,
} from "@/lib/pulse-data";

export function DetailsSheet({
  open,
  onOpenChange,
  department,
  period = "september",
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  department?: Department;
  period?: Period;
}) {
  const opener = useRef<HTMLElement | null>(null);
  const t = useTranslations("pulse"),
    locale = useLocale(),
    n = numberFormatter(locale),
    decimal = numberFormatter(locale, 1);
  const metrics = getMetrics(department ?? "all", period);
  const files = sources.filter(
    (source) => !department || source.department === department,
  );
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        className="detail-sheet"
        showCloseButton={false}
        onOpenAutoFocus={() => {
          opener.current = document.activeElement as HTMLElement;
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (opener.current?.isConnected) opener.current.focus();
        }}
      >
        <SheetClose
          className="icon-button detail-close"
          aria-label={t("close")}
        >
          <X size={19} />
        </SheetClose>
        <div>
          <div className="sample-badge mb-5">{t("sampleShort")}</div>
          <SheetTitle>
            {department ? t(`departments.${department}`) : t("detailTitle")}
          </SheetTitle>
          <SheetDescription>{t("detailDescription")}</SheetDescription>
        </div>
        <span className="text-sm text-muted-foreground">
          {t("periodLabel", { month: t(`months.${period}`) })}
        </span>
        <dl className="detail-metrics">
          {[
            [t("received"), n.format(metrics.received)],
            [t("resolved"), n.format(metrics.resolved)],
            [t("onTime"), `${decimal.format(metrics.onTimeRate)}%`],
            [t("overdue"), n.format(metrics.overdue)],
          ].map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        <section className="detail-section">
          <h3>{t("calculation")}</h3>
          <p>{t("rateFormula")}</p>
          <p className="mt-3! tabular-nums">
            {n.format(metrics.onTime)} / {n.format(metrics.resolved)} × 100 ={" "}
            {decimal.format(metrics.onTimeRate)}%
          </p>
        </section>
        <section className="detail-section">
          <h3 className="flex items-center gap-2">
            <Database size={16} />
            {t("connectedSources")}
          </h3>
          {files.map((source) => (
            <div className="source-entry" key={source.id}>
              <h3>{t(`departments.${source.department}`)}</h3>
              <p className="filename">{source.filename}</p>
              <div className="source-meta">
                <span>{t("rowCount", { count: source.rows })}</span>
                <span className={source.stale ? "warn" : ""}>
                  {t("updated")} {formatSourceDate(source.updated, locale)}
                </span>
              </div>
            </div>
          ))}
          <p className="mt-4! text-xs!">{t("sourceFreshnessNote")}</p>
        </section>
        <Link
          href="/ingest"
          className="civic-button"
          onClick={() => onOpenChange(false)}
        >
          {t("viewSourceList")}
          <ArrowUpRight size={16} />
        </Link>
      </SheetContent>
    </Sheet>
  );
}
