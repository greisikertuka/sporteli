import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { BriefingScreen } from "@/components/sportel/briefing";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("nav");
  return { title: t("briefing") };
}

export default function BriefingPage() {
  return <BriefingScreen />;
}
