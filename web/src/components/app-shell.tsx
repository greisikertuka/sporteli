"use client";

import { ChevronRight, Menu, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { AppSidebar, isActive, NAV } from "./app-sidebar";
import { LocaleSwitcher } from "./locale-switcher";
import { ApiStatus, StatusBadges } from "./sportel/status-badges";
import { SystemProvider } from "./sportel/system-context";
import { ThemeToggle } from "./theme-toggle";
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetTitle } from "./ui/sheet";

export function AppShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const current = NAV.find((item) => isActive(pathname, item.href)) ?? NAV[0];
  const onPassport = pathname.startsWith("/indicators/");

  return (
    <SystemProvider>
      <div className="civic-app">
        <a href="#main-content" className="skip-link">
          {t("shell.skip")}
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
            <SheetDescription className="sr-only">{t("app.tagline")}</SheetDescription>
            <SheetClose className="icon-button mobile-nav-close" aria-label={t("shell.close")}>
              <X size={18} />
            </SheetClose>
            <AppSidebar onNavigate={() => setMenuOpen(false)} />
          </SheetContent>
        </Sheet>
        <div className="civic-workspace">
          <header className="civic-topbar">
            <div className="topbar-row">
              <div className="breadcrumb">
                <button
                  className="icon-button mobile-menu"
                  ref={menuButton}
                  onClick={() => setMenuOpen(true)}
                  aria-label={t("shell.menu")}
                >
                  <Menu size={20} />
                </button>
                <span className="breadcrumb-city">{t("app.name")}</span>
                <ChevronRight className="breadcrumb-chevron" size={14} aria-hidden />
                <span>{t(`nav.${current.key}`)}</span>
                {onPassport && (
                  <>
                    <ChevronRight className="breadcrumb-chevron" size={14} aria-hidden />
                    <span className="breadcrumb-code">{decodeURIComponent(pathname.split("/")[2] ?? "")}</span>
                  </>
                )}
              </div>
              <div className="header-controls">
                <StatusBadges />
                <span className="header-divider" />
                <LocaleSwitcher />
                <ThemeToggle />
              </div>
            </div>
          </header>
          <main id="main-content" className="civic-main" tabIndex={-1}>
            {children}
          </main>
          <footer className="workspace-footer">
            <span>
              {t("shell.footer")} {t("shell.footerFormula")}
            </span>
            <ApiStatus />
          </footer>
        </div>
      </div>
    </SystemProvider>
  );
}
