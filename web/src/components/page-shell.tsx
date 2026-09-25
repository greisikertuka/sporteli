import { Inbox } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type PageKey = "overview" | "ingest" | "ask" | "briefing";

/** Placeholder page body; each feature replaces its own empty state on-site. */
export async function EmptyPage({ page }: { page: PageKey }) {
  const t = await getTranslations(`pages.${page}`);
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-muted-foreground">{t("description")}</p>
      </div>
      <Card className="border-dashed">
        <CardHeader className="items-center text-center">
          <Inbox className="mx-auto size-8 text-muted-foreground" aria-hidden />
          <CardTitle className="text-base">{t("title")}</CardTitle>
          <CardDescription>{t("empty")}</CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
    </div>
  );
}
