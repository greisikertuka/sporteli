"use client";

import {
  Building2,
  DatabaseZap,
  FileText,
  LayoutDashboard,
  MessageSquareText,
  ShieldCheck,
  Map as MapIcon,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";

import { useSystem } from "@/components/sportel/system-context";

export const NAV = [
  { href: "/", key: "overview", icon: LayoutDashboard },
  { href: "/ingest", key: "ingest", icon: DatabaseZap },
  { href: "/ask", key: "ask", icon: MessageSquareText },
  { href: "/coverage", key: "coverage", icon: MapIcon },
  { href: "/briefing", key: "briefing", icon: FileText },
  { href: "/trust", key: "trust", icon: ShieldCheck },
] as const;

export function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/" || pathname.startsWith("/indicators");
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SportelMark({ size = 40 }: { size?: number }) {
  return (
    <span className="sportel-mark" style={{ width: size, height: size }} aria-hidden>
      <Image src="/sportel-icon.png" alt="" width={size} height={size} priority />
    </span>
  );
}

export function AppSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const t = useTranslations();
  const pathname = usePathname();
  const { board } = useSystem();
  const coverage = board.data?.coverage;

  return (
    <div className="civic-sidebar-inner">
      <Link href="/" className="brand-link" onClick={onNavigate} aria-label={`${t("app.name")} · ${t("app.tagline")}`}>
        <SportelMark />
        <span className="brand-type">
          {t("app.name")}
          <span>{t("app.tagline")}</span>
        </span>
      </Link>
      <div className="sidebar-section-label">{t("shell.workspace")}</div>
      <nav aria-label={t("nav.section")} className="civic-nav">
        {NAV.map(({ href, key, icon: Icon }) => (
          <Link
            key={key}
            href={href}
            aria-current={isActive(pathname, href) ? "page" : undefined}
            onClick={onNavigate}
          >
            <Icon aria-hidden />
            <span>{t(`nav.${key}`)}</span>
            <span className="nav-active-mark" aria-hidden />
          </Link>
        ))}
      </nav>
      <div className="sidebar-bottom">
        {coverage && (
          <Link href="/" className="sidebar-proof" onClick={onNavigate}>
            <span className="sidebar-proof-count">
              <strong>{coverage.computable}</strong>/{coverage.total}
            </span>
            <span className="sidebar-proof-label">{t("board.counterLabel")}</span>
            <span className="sidebar-proof-meter" aria-hidden>
              {Array.from({ length: coverage.total }, (_, i) => (
                <i key={i} data-on={i < coverage.computable ? "" : undefined} />
              ))}
            </span>
          </Link>
        )}
        <div className="municipality-lockup">
          <Building2 size={19} aria-hidden />
          <span>
            {t("app.municipality")}
            <small>{t("app.country")}</small>
          </span>
          <span className="municipality-dot" aria-hidden />
        </div>
      </div>
    </div>
  );
}
