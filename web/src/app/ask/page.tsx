import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { AskScreen } from "@/components/sportel/ask";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("nav");
  return { title: t("ask") };
}

export default async function AskPage({ searchParams }: PageProps<"/ask">) {
  const { passport } = await searchParams;
  const code = typeof passport === "string" && /^[A-Z]{2,4}-\d{2}$/.test(passport) ? passport : null;
  return <AskScreen passport={code} />;
}
