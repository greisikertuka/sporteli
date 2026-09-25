"use client";
import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  ArrowUpRight,
  Blocks,
  FileSpreadsheet,
  Files,
  PanelTop,
  Plus,
} from "lucide-react";
import { sources, formatSourceDate, type Department } from "@/lib/pulse-data";
import { CsvImport } from "./csv-import";
import { DetailsSheet } from "./details-sheet";

export function Sources() {
  const t = useTranslations("pulse"),
    locale = useLocale();
  const [details, setDetails] = useState<Department | null>(null);
  function openImport() {
    const el = document.getElementById("import-heading");
    el?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
      block: "center",
    });
    el?.focus({ preventScroll: true });
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{t("sourcesTitle")}</h1>
          <p className="page-description">{t("sourcesDescription")}</p>
        </div>
        <button className="civic-button primary" onClick={openImport}>
          <Plus />
          {t("previewCsv")}
        </button>
      </div>
      <section className="panel integration-panel">
        <div>
          <h2>{t("integrationTitle")}</h2>
          <p>{t("integrationDescription")}</p>
        </div>
        <div
          className="integration-diagram"
          role="img"
          aria-label={`${t("files")} → ${t("mapping")} → ${t("sharedModel")}`}
        >
          <div className="integration-node">
            <span>
              <Files size={23} />
            </span>
            {t("files")}
          </div>
          <div className="integration-connector" />
          <div className="integration-node">
            <span>
              <Blocks size={22} />
            </span>
            {t("mapping")}
          </div>
          <div className="integration-connector" />
          <div className="integration-node">
            <span>
              <PanelTop size={23} />
            </span>
            {t("sharedModel")}
          </div>
        </div>
      </section>
      <div className="section-heading">
        <h2>{t("connectedSources")}</h2>
        <span>{t("sourceCount", { count: sources.length })}</span>
      </div>
      <div className="source-library">
        {sources.map((source) => (
          <button
            className="panel source-card"
            key={source.id}
            onClick={() => setDetails(source.department)}
          >
            <div className="source-card-top">
              <span className="source-file-icon">
                <FileSpreadsheet size={20} />
              </span>
              <span
                className={`status-label ${source.stale ? "warn" : "good"}`}
              >
                {source.stale ? t("stale") : t("fresh")}
              </span>
            </div>
            <h3>{t(`departments.${source.department}`)}</h3>
            <p className="filename">{source.filename}</p>
            <div className="source-card-footer">
              <span>{t("rowCount", { count: source.rows })}</span>
              <span className="flex items-center gap-2">
                {t("updated")} {formatSourceDate(source.updated, locale)}
                <ArrowUpRight size={14} />
              </span>
            </div>
          </button>
        ))}
      </div>
      <CsvImport />
      <DetailsSheet
        open={details !== null}
        onOpenChange={(open) => !open && setDetails(null)}
        department={details ?? undefined}
      />
    </>
  );
}
