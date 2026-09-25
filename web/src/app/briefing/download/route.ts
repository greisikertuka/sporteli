import { getTranslations } from "next-intl/server";
import { getMetrics, numberFormatter, sources } from "@/lib/pulse-data";

export async function GET(request: Request) {
  const locale =
    new URL(request.url).searchParams.get("locale") === "en" ? "en" : "sq";
  const t = await getTranslations({ locale, namespace: "pulse" });
  const metrics = getMetrics("all", "september"),
    n = numberFormatter(locale),
    decimal = numberFormatter(locale, 1);
  const content = [
    `# Elbasan Pulse: ${t("briefingHeading")}`,
    `${t("draft")} | ${t("periodLabel", { month: t("months.september") })}`,
    `## ${t("executiveSummary")}`,
    t("briefingLead"),
    t("briefingIntro", {
      received: n.format(metrics.received),
      resolved: n.format(metrics.resolved),
      rate: decimal.format(metrics.onTimeRate),
    }),
    `- ${t("received")}: ${n.format(metrics.received)}\n- ${t("onTime")}: ${decimal.format(metrics.onTimeRate)}%\n- ${t("overdue")}: ${metrics.overdue}`,
    `## ${t("briefingPriority")}`,
    t("briefingPriorityBody"),
    `## ${t("briefingQuality")}`,
    t("briefingQualityBody"),
    `## ${t("connectedSources")}`,
    sources.map((source) => `- ${source.filename}`).join("\n"),
    t("briefingFooter"),
  ].join("\n\n");
  return new Response(content, {
    headers: {
      "Content-Type": "text/markdown; charset=utf-8",
      "Content-Disposition": `attachment; filename="elbasan-pulse-september-2026-${locale}.md"`,
      "X-Content-Type-Options": "nosniff",
    },
  });
}
