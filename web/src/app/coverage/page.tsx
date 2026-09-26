import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { CoverageScreen } from "@/components/sportel/coverage";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("nav");
  return { title: t("coverage") };
}

export default function CoveragePage() {
  return <CoverageScreen />;
}
