import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { IngestScreen } from "@/components/sportel/ingest";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("nav");
  return { title: t("ingest") };
}

export default async function IngestPage({ searchParams }: PageProps<"/ingest">) {
  const { dataset } = await searchParams;
  const wanted = typeof dataset === "string" && /^[a-z_]{1,40}$/.test(dataset) ? dataset : null;
  return <IngestScreen wanted={wanted} />;
}
