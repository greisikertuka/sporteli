import type { Metadata } from "next";

import { PassportView } from "@/components/sportel/passport-view";

export async function generateMetadata({ params }: PageProps<"/indicators/[code]">): Promise<Metadata> {
  const { code } = await params;
  return { title: decodeURIComponent(code) };
}

export default async function IndicatorPage({ params }: PageProps<"/indicators/[code]">) {
  const { code } = await params;
  return (
    <div className="passport-page">
      <PassportView code={decodeURIComponent(code)} variant="page" />
    </div>
  );
}
