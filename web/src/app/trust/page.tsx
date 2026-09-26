import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { TrustScreen } from "@/components/sportel/trust";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("nav");
  return { title: t("trust") };
}

export default function TrustPage() {
  return <TrustScreen />;
}
