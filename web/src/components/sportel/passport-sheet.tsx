"use client";

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef } from "react";

import { Sheet, SheetClose, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";

import { PassportView } from "./passport-view";

/** The passport drawer opened from a tile, the proof meter, a signal or the leadership callout. */
export function PassportSheet({ code, onClose }: { code: string | null; onClose: () => void }) {
  const t = useTranslations();
  const opener = useRef<HTMLElement | null>(null);
  return (
    <Sheet open={code !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        className="passport-sheet"
        showCloseButton={false}
        onOpenAutoFocus={() => {
          opener.current = document.activeElement as HTMLElement | null;
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (opener.current?.isConnected) opener.current.focus();
        }}
      >
        <SheetTitle className="sr-only">
          {t("nav.indicator")} {code}
        </SheetTitle>
        <SheetDescription className="sr-only">{t("passport.draftHint")}</SheetDescription>
        <SheetClose className="icon-button sheet-close" aria-label={t("common.close")}>
          <X size={19} />
        </SheetClose>
        {code && <PassportView key={code} code={code} variant="drawer" onNavigate={onClose} />}
      </SheetContent>
    </Sheet>
  );
}
