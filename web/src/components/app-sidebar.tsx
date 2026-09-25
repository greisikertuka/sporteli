"use client";
import {
  Building2,
  Database,
  FileText,
  LayoutDashboard,
  MessageSquareText,
  ArrowUpRight,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { PulseMark } from "@/components/pulse-mark";

export const NAV = [
  { href: "/", key: "overview", icon: LayoutDashboard },
  { href: "/ingest", key: "ingest", icon: Database },
  { href: "/ask", key: "ask", icon: MessageSquareText },
  { href: "/briefing", key: "briefing", icon: FileText },
] as const;

export function AppSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const t = useTranslations(),
    pathname = usePathname();
  return (
    <div className="civic-sidebar-inner">
      <Link
        href="/"
        className="brand-link"
        onClick={onNavigate}
        aria-label="Elbasan Pulse"
      >
        <PulseMark />
        <span className="brand-type">
          Elbasan Pulse<span>{t("app.municipality")}</span>
        </span>
      </Link>
      <div className="sidebar-section-label">{t("pulse.workspace")}</div>
      <nav aria-label={t("nav.section")} className="civic-nav">
        {NAV.map(({ href, key, icon: Icon }) => (
          <Link
            key={key}
            href={href}
            aria-current={pathname === href ? "page" : undefined}
            onClick={onNavigate}
          >
            <Icon aria-hidden />
            <span>{t(`nav.${key}`)}</span>
            <span className="nav-active-mark" aria-hidden />
          </Link>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <Link
          href="/ingest"
          className="sidebar-source-note"
          onClick={onNavigate}
        >
          <Database size={17} aria-hidden />
          <span>
            {t("pulse.sourceCount", { count: 4 })}
            <small>{t("pulse.sampleShort")}</small>
          </span>
          <ArrowUpRight size={15} aria-hidden />
        </Link>
        <div className="municipality-lockup">
          <Building2 size={19} aria-hidden />
          <span>
            Elbasan<small>Shqipëri</small>
          </span>
          <span className="municipality-dot" aria-hidden />
        </div>
      </div>
    </div>
  );
}
