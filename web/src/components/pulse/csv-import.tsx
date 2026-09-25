"use client";
import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import {
  Check,
  CheckCircle2,
  ChevronRight,
  FileSpreadsheet,
  FolderOpen,
  LockKeyhole,
  Upload,
} from "lucide-react";
import { useTranslations } from "next-intl";
import {
  parseCsv,
  validateMapping,
  MAX_CSV_BYTES,
  type CsvPreview,
  type ColumnMapping,
} from "@/lib/csv-preview";
import { SAMPLE_CSV } from "@/lib/pulse-data";

export function CsvImport() {
  const t = useTranslations("pulse");
  const input = useRef<HTMLInputElement>(null),
    generation = useRef(0),
    stepHeading = useRef<HTMLHeadingElement>(null);
  const [step, setStep] = useState(0),
    [preview, setPreview] = useState<CsvPreview | null>(null),
    [filename, setFilename] = useState("");
  const [mapping, setMapping] = useState<ColumnMapping>({
    id: -1,
    department: -1,
    status: -1,
  });
  const [error, setError] = useState(""),
    [dragging, setDragging] = useState(false),
    [reading, setReading] = useState(false);
  function goTo(next: number) {
    setStep(next);
    requestAnimationFrame(() => stepHeading.current?.focus());
  }
  function load(text: string, name: string) {
    try {
      const data = parseCsv(text);
      setPreview(data);
      setFilename(name);
      setMapping({
        id: data.headers.findIndex((h) => /^(request_?id|id)$/i.test(h)),
        department: data.headers.findIndex((h) =>
          /^(department|drejtoria)$/i.test(h),
        ),
        status: data.headers.findIndex((h) => /^(status|statusi)$/i.test(h)),
      });
      setError("");
      goTo(1);
    } catch (error) {
      const code = error instanceof Error ? error.message : "format";
      setError(
        code === "size"
          ? t("csvSize")
          : code === "empty"
            ? t("csvEmpty")
            : code === "headers"
              ? t("csvHeaders")
              : t("csvError"),
      );
    }
  }
  async function readFile(file?: File) {
    const token = ++generation.current;
    setReading(false);
    setError("");
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError(t("csvType"));
      return;
    }
    if (file.size > MAX_CSV_BYTES) {
      setError(t("csvSize"));
      return;
    }
    setReading(true);
    try {
      const text = await file.text();
      if (token === generation.current) load(text, file.name);
    } catch {
      if (token === generation.current) setError(t("csvError"));
    } finally {
      if (token === generation.current) setReading(false);
    }
  }
  function choose(event: ChangeEvent<HTMLInputElement>) {
    void readFile(event.target.files?.[0]);
    event.target.value = "";
  }
  function drop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    void readFile(event.dataTransfer.files[0]);
  }
  function sample() {
    generation.current++;
    setReading(false);
    load(SAMPLE_CSV, "pulse_sample.csv");
  }
  const fields = [
    { key: "id", label: "requestId" },
    { key: "department", label: "department" },
    { key: "status", label: "requestStatus" },
  ] as const;
  return (
    <section
      id="import-preview"
      className="panel import-panel"
      aria-labelledby="import-heading"
    >
      <div className="import-heading">
        <div>
          <h2 id="import-heading" ref={stepHeading} tabIndex={-1}>
            {t("importTitle")}
          </h2>
          <p className="section-subtitle">
            {step > 0 && step < 3 ? filename : t("importDescription")}
          </p>
        </div>
        <span className="sample-badge">{t("review")}</span>
      </div>
      {step < 3 && (
        <ol className="import-steps">
          {["chooseFile", "checkColumns", "review"].map((label, i) => (
            <li key={label} aria-current={step === i ? "step" : undefined}>
              <span className="step-number">
                {step > i ? <Check size={12} /> : i + 1}
              </span>
              {t(label)}
            </li>
          ))}
        </ol>
      )}
      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
      {step === 0 && (
        <>
          <div
            className={`drop-zone ${dragging ? "dragging" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={drop}
          >
            <Upload size={28} strokeWidth={1.5} />
            <h3>{reading ? t("loadingFile") : t("dropFile")}</h3>
            <p>{t("fileLimits")}</p>
            <div className="action-group">
              <button
                className="civic-button primary"
                onClick={() => input.current?.click()}
                disabled={reading}
              >
                <FolderOpen />
                {t("chooseFile")}
              </button>
              <button
                className="civic-button"
                onClick={sample}
                disabled={reading}
              >
                {t("useSample")}
              </button>
            </div>
            <input
              ref={input}
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              tabIndex={-1}
              aria-label={t("chooseFile")}
              onChange={choose}
            />
          </div>
          <p className="local-notice">
            <LockKeyhole size={13} />
            {t("importDescription")}
          </p>
        </>
      )}
      {step === 1 && preview && (
        <>
          <div className="mapping-grid">
            <div className="mapping-row mapping-header">
              <span>{t("field")}</span>
              <span>{t("column")}</span>
              <span>{t("sampleValue")}</span>
            </div>
            {fields.map(({ key, label }) => (
              <div className="mapping-row" key={key}>
                <label htmlFor={`mapping-${key}`}>{t(label)}</label>
                <select
                  id={`mapping-${key}`}
                  value={mapping[key]}
                  onChange={(e) => {
                    setMapping({ ...mapping, [key]: Number(e.target.value) });
                    setError("");
                  }}
                >
                  <option value={-1}>{t("unmapped")}</option>
                  {preview.headers.map((h, i) => (
                    <option value={i} key={h}>
                      {h}
                    </option>
                  ))}
                </select>
                <span className="mapping-sample">
                  {preview.rows[0][mapping[key]] || t("emptyValue")}
                </span>
              </div>
            ))}
          </div>
          <div className="import-actions">
            <button
              className="civic-button"
              onClick={() => {
                setError("");
                goTo(0);
              }}
            >
              {t("back")}
            </button>
            <button
              className="civic-button primary"
              onClick={() => {
                if (!validateMapping(mapping, preview.headers.length)) {
                  setError(t("mappingError"));
                  return;
                }
                setError("");
                goTo(2);
              }}
            >
              {t("continue")}
              <ChevronRight />
            </button>
          </div>
        </>
      )}
      {step === 2 && preview && (
        <>
          <div className="flex items-center gap-3 mb-5">
            <FileSpreadsheet className="text-primary" size={24} />
            <div>
              <h3 className="break-all">{filename}</h3>
              <p className="section-subtitle">
                {t("rowCount", { count: preview.rows.length })}
              </p>
            </div>
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <caption className="sr-only">
                {t("previewRows", { count: Math.min(5, preview.rows.length) })}
              </caption>
              <thead>
                <tr>
                  {fields.map((f) => (
                    <th key={f.key}>{t(f.label)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.slice(0, 5).map((row, i) => (
                  <tr key={i}>
                    {fields.map((f) => (
                      <td key={f.key} className="max-w-64 break-words">
                        {row[mapping[f.key]] || t("emptyValue")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="local-notice">
            <LockKeyhole size={13} />
            {t("importDescription")}
          </p>
          <div className="import-actions">
            <button className="civic-button" onClick={() => goTo(1)}>
              {t("back")}
            </button>
            <button className="civic-button primary" onClick={() => goTo(3)}>
              <Check size={16} />
              {t("finishPreview")}
            </button>
          </div>
        </>
      )}
      {step === 3 && preview && (
        <div className="import-success" role="status">
          <div className="success-mark">
            <CheckCircle2 size={27} />
          </div>
          <h2>{t("previewComplete")}</h2>
          <p>
            {t("previewCompleteDescription", { count: preview.rows.length })}
          </p>
          <button
            className="civic-button"
            onClick={() => {
              setPreview(null);
              setError("");
              goTo(0);
            }}
          >
            {t("previewAgain")}
          </button>
        </div>
      )}
    </section>
  );
}
