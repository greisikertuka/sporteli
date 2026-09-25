"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { apiGet, type Health } from "@/lib/api";

type State = { kind: "checking" } | { kind: "online"; health: Health } | { kind: "offline" };

const POLL_MS = 30_000;

export function ApiStatus() {
  const t = useTranslations("status");
  const [state, setState] = useState<State>({ kind: "checking" });

  useEffect(() => {
    let active = true;
    const check = () =>
      apiGet<Health>("/health", { cache: "no-store" })
        .then((health) => active && setState({ kind: "online", health }))
        .catch(() => active && setState({ kind: "offline" }));
    check();
    const id = setInterval(check, POLL_MS);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  if (state.kind === "checking") return <Badge variant="outline">{t("checking")}</Badge>;
  if (state.kind === "offline") return <Badge variant="destructive">{t("offline")}</Badge>;

  return (
    <div className="flex items-center gap-2">
      <Badge variant="outline" className="gap-1.5">
        <span className="size-1.5 rounded-full bg-emerald-500" aria-hidden />
        {t("online")}
      </Badge>
      <Badge variant={state.health.llm ? "outline" : "secondary"}>
        {state.health.llm ? t("aiOn") : t("aiOff")}
      </Badge>
    </div>
  );
}
