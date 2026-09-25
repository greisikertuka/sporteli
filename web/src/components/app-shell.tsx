"use client";
import { Menu, ChevronRight, FlaskConical, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import { useState, useRef } from "react";
import { AppSidebar, NAV } from "./app-sidebar";
import { ApiStatus } from "./api-status";
import { LocaleSwitcher } from "./locale-switcher";
import { ThemeToggle } from "./theme-toggle";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetDescription,
  SheetClose,
} from "./ui/sheet";

export function AppShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations(),
    pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const current = NAV.find((item) => item.href === pathname) ?? NAV[0];
  return (
    <div className="civic-app">
      <a href="#main-content" className="skip-link">
        {t("pulse.skip")}
      </a>
      <aside className="civic-sidebar">
        <AppSidebar />
      </aside>
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent
          side="left"
          className="mobile-nav-sheet"
          showCloseButton={false}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            menuButton.current?.focus();
          }}
        >
          <SheetTitle className="sr-only">{t("nav.section")}</SheetTitle>
          <SheetDescription className="sr-only">
            {t("app.name")}
          </SheetDescription>
          <SheetClose
            className="icon-button mobile-nav-close"
            aria-label={t("pulse.close")}
          >
            <X size={18} />
          </SheetClose>
          <AppSidebar onNavigate={() => setMenuOpen(false)} />
        </SheetContent>
      </Sheet>
      <div className="civic-workspace">
        <header className="civic-topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              ref={menuButton}
              onClick={() => setMenuOpen(true)}
              aria-label={t("pulse.menu")}
            >
              <Menu size={20} />
            </button>
            <span className="breadcrumb-city">Elbasan</span>
            <ChevronRight
              className="breadcrumb-chevron"
              size={14}
              aria-hidden
            />
            <span>{t(`nav.${current.key}`)}</span>
          </div>
          <div className="header-controls">
            <span className="sample-badge">
              <FlaskConical size={13} aria-hidden />
              <span>{t("pulse.sampleShort")}</span>
            </span>
            <span className="header-divider" />
            <LocaleSwitcher />
            <ThemeToggle />
          </div>
        </header>
        <main id="main-content" className="civic-main" key={pathname}>
          {children}
        </main>
        <footer className="workspace-footer">
          <span>{t("pulse.sampleNote")}</span>
          <ApiStatus />
        </footer>
      </div>
    </div>
  );
}
