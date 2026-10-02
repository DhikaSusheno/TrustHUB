"use client";

// components/LeftNav.tsx
// Sidebar for the Manufacturing Knowledge Hub.
//
// FE-1 @nabilfauzandafa
//
// The nine pages here are the Case Book's four data types plus the trust
// evidence around them, in the order an engineer actually meets them:
//
//   ask          the product - a question, a badge, the documents behind it
//   equipment    equipment-centric: every document and failure for one unit
//   documents    document-centric: the register with approval and revision
//   graph        the architecture - how those documents are joined
//   verification whether the documents agree with each other
//   maintenance  the workbook: 211 work orders, 31 breakdowns
//   overview     what this instance currently holds
//   audit        how the score is computed, and every question asked
//   dataset      provenance, gaps, and the LLM policy
//
// "Ask" is first because it is the only page where a number reaches a person.
// `NAV_PAGES` is derived from this list, so the URL guard cannot drift from
// what the sidebar can actually reach.

import Link from "next/link";
import { useBackendStatus, type BackendMode } from "@/hooks/useBackendStatus";
import { usePlatformSettings } from "@/lib/usePlatformSettings";
import LanguageSwitcher from "@/components/shared/LanguageSwitcher";
import LogoMark from "@/components/shared/LogoMark";
import ThemeSwitcher from "@/components/shared/ThemeSwitcher";
import { useI18n } from "@/lib/i18n/LocaleProvider";
import type { StringKey } from "@/lib/i18n/dictionary";

export type NavPage =
  | "ask"
  | "equipment"
  | "documents"
  | "graph"
  | "verification"
  | "maintenance"
  | "overview"
  | "audit"
  | "dataset";

interface Props {
  activePage: NavPage;
  onNavigate: (page: NavPage) => void;
  /** Unused by the plant nav; kept so the shell signature stays stable. */
  pendingApprovals?: number;
}

// 24x24 stroke icons, currentColor, one visual weight throughout. Kept from the
// previous nav because they were already consistent; only the set changed.
const NAV_ITEMS: { id: NavPage; labelKey: StringKey; d: string }[] = [
  // ask - a speech mark: the only input surface in the product
  {
    id: "ask",
    labelKey: "nav.ask",
    d: "M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z",
  },
  // equipment - a vessel with a level line
  {
    id: "equipment",
    labelKey: "nav.equipment",
    d: "M12 3v2.25m0 13.5V21M7.5 5.25h9M5.25 7.5v9a2.25 2.25 0 002.25 2.25h9a2.25 2.25 0 002.25-2.25v-9M5.25 12h13.5",
  },
  // documents - a sheet with a folded corner and rules
  {
    id: "documents",
    labelKey: "nav.documents",
    d: "M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9zM9 12.75h6m-6 3h6",
  },
  // graph - three nodes joined
  {
    id: "graph",
    labelKey: "nav.graph",
    d: "M6.75 4.5a2.25 2.25 0 100 4.5 2.25 2.25 0 000-4.5zM17.25 15a2.25 2.25 0 100 4.5 2.25 2.25 0 000-4.5zM9 16.5a2.25 2.25 0 100 4.5 2.25 2.25 0 000-4.5zM8.4 8.7l7.6 7.2m-1.35-9.6l-4.3 8.7",
  },
  // verification - a check inside a shield: documents agreeing
  {
    id: "verification",
    labelKey: "nav.verification",
    d: "M9 12.75L11.25 15 15 9.75M21 12c0 5.592-3.824 10.29-9 11.622-5.176-1.332-9-6.03-9-11.622 0-1.31.21-2.571.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z",
  },
  // maintenance - a wrench over a trend line
  {
    id: "maintenance",
    labelKey: "nav.maintenance",
    d: "M3 13.5l4.5-4.5 3 3 4.5-4.5M3 20.25h18M14.25 4.5l1.5 1.5 2.25-2.25-1.5-1.5z",
  },
  // overview - a gauge
  {
    id: "overview",
    labelKey: "nav.overview",
    d: "M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25a2.25 2.25 0 01-2.25-2.25v-2.25z",
  },
  // audit - a ledger with a clock
  {
    id: "audit",
    labelKey: "nav.audit",
    d: "M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z",
  },
  // dataset - a database drum with a licence tag
  {
    id: "dataset",
    labelKey: "nav.dataset",
    d: "M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75",
  },
];

// Valid page ids at runtime. `NavPage` is only a union type, so it cannot
// validate a `?page=` value from the URL on its own. Derived from NAV_ITEMS so
// the guard and the sidebar cannot fall out of sync.
export const NAV_PAGES: readonly NavPage[] = NAV_ITEMS.map((item) => item.id);

function NavIcon({ d }: { d: string }) {
  return (
    <svg aria-hidden="true" className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
      <path d={d} />
    </svg>
  );
}

const FOOTER_STATUS: Record<BackendMode, { dot: string; text: string }> = {
  live:     { dot: "bg-green-400",  text: "text-green-400" },
  empty:    { dot: "bg-yellow-400", text: "text-yellow-400" },
  checking: { dot: "bg-blue-400",   text: "text-blue-400" },
  offline:  { dot: "bg-red-400",    text: "text-red-400" },
};
const FOOTER_LABEL: Record<BackendMode, StringKey> = {
  live: "status.index_ready",
  empty: "status.index_absent",
  checking: "status.index_checking",
  offline: "status.backend_offline",
};

export default function LeftNav({ activePage, onNavigate }: Props) {
  const { mode } = useBackendStatus();
  const { settings } = usePlatformSettings();
  const { t } = useI18n();
  const platformName = settings?.platform_name || "TrustHUB";
  const environment = settings?.environment || "LLDPE Unit";
  const footer = FOOTER_STATUS[mode];

  return (
    <nav aria-label="Primary" className="w-52 shrink-0 flex flex-col bg-panel border-r border-slate-800/60 overflow-hidden">
      <div className="px-4 py-4 border-b border-slate-800/60 shrink-0">
        <Link href="/landing" className="flex items-center gap-2.5 rounded-lg group" aria-label={`${platformName} â€” about and demo guide`}>
          <div className="w-7 h-7 rounded-lg bg-blue-500/10 border border-blue-500/30 flex items-center justify-center shrink-0 group-hover:border-blue-400/60 transition-colors">
            <LogoMark />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-bold text-ink tracking-tight truncate">{platformName}</div>
            <div className="text-[10px] text-slate-500 leading-tight truncate">{environment} &middot; Set 01</div>
          </div>
        </Link>
      </div>

      <div className="flex-1 py-2 space-y-0.5 px-2 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive = activePage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              aria-current={isActive ? "page" : undefined}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors text-left ${
                isActive
                  ? "bg-blue-600/20 text-blue-400 font-medium"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              }`}
            >
              <NavIcon d={item.d} />
              <span className="flex-1 truncate">{t(item.labelKey)}</span>
            </button>
          );
        })}
      </div>

      <div className="px-4 py-3 border-t border-slate-800/60 space-y-1 shrink-0">
        <div className="text-xs text-slate-500 font-mono">v0.1.0 &middot; CALIBER 2026</div>
        <LanguageSwitcher />
        <ThemeSwitcher />
        <div className="flex items-center gap-1.5" role="status">
          <span className={`w-1.5 h-1.5 rounded-full inline-block shrink-0 ${footer.dot} ${mode === "checking" ? "animate-pulse" : ""}`} />
          <span className={`text-xs truncate ${footer.text}`}>{t(FOOTER_LABEL[mode])}</span>
        </div>
      </div>
    </nav>
  );
}
