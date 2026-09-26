import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { IngestScreen } from "@/components/sportel/ingest";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("nav");
  return { title: t("ingest") };
}

export default async function IngestPage({ searchParams }: PageProps<"/ingest">) {
  const { dataset, ask } = await searchParams;
  const wanted = typeof dataset === "string" && /^[a-z_]{1,40}$/.test(dataset) ? dataset : null;
  const askCode = typeof ask === "string" && /^[A-Z]{2,4}-\d{2}$/.test(ask) ? ask : null;
  return <IngestScreen wanted={wanted} askCode={askCode} />;
}
