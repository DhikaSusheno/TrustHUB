"use client";

// app/page.tsx
// Application shell: sidebar plus one page at a time.
//
// FE-1 @nabilfauzandafa · FE-2 @ShannWasHere
//
// This file is deliberately thin. It owns two things and nothing else:
//
//   1. Which page is showing, and
//   2. Translating a NavPage id into a component.
//
// Every page owns its own data, so switching pages is a component swap with no
// shared fetch, no shared store, and no cross-page state to invalidate. The
// previous shell carried a live operations feed, an SSE stream, and a right-hand
// approval panel that three different pages depended on; removing them is what
// let the pages be independent.
//
// `?page=` is honoured on first paint so a URL can be shared at a specific
// view. An unrecognised value falls back to "ask" rather than erroring, because
// a stale bookmark should land on a working page, not a blank one.
//
// All pages are dynamically imported with SSR off. They read a protected API
// through the same-origin proxy at app/backend/[...path], and rendering them on
// the server would mean the fetch happens without the injected token.

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { NAV_PAGES, type NavPage } from "@/components/LeftNav";

function PageLoading() {
  return (
    <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
      <span className="animate-pulse">Loading&hellip;</span>
    </div>
  );
}

const LeftNav = dynamic(() => import("@/components/LeftNav"), { ssr: false });

const AskPage           = dynamic(() => import("@/components/pages/AskPage"),           { ssr: false, loading: PageLoading });
const OverviewPage      = dynamic(() => import("@/components/pages/OverviewPage"),      { ssr: false, loading: PageLoading });
const EquipmentPage     = dynamic(() => import("@/components/pages/EquipmentPage"),     { ssr: false, loading: PageLoading });
const DocumentsPage     = dynamic(() => import("@/components/pages/DocumentsPage"),     { ssr: false, loading: PageLoading });
const KnowledgeGraphPage = dynamic(() => import("@/components/pages/KnowledgeGraphPage"), { ssr: false, loading: PageLoading });
const VerificationPage  = dynamic(() => import("@/components/pages/VerificationPage"),  { ssr: false, loading: PageLoading });
const MaintenancePage   = dynamic(() => import("@/components/pages/MaintenancePage"),   { ssr: false, loading: PageLoading });
const AuditPage         = dynamic(() => import("@/components/pages/AuditPage"),         { ssr: false, loading: PageLoading });
const PlantSettingsPage = dynamic(() => import("@/components/pages/PlantSettingsPage"), { ssr: false, loading: PageLoading });

/** First page on a cold load. Ask, because it is the only page that
 *  demonstrates the product end to end. */
const DEFAULT_PAGE: NavPage = "ask";

export default function HomePage() {
  const [activePage, setActivePage] = useState<NavPage>(DEFAULT_PAGE);

  // Read the query string after mount rather than during the initialiser.
  // window does not exist while the client component is being created on the
  // server, and a lazy initialiser that touches it produces a hydration
  // mismatch: the server rendered one page and the client renders another.
  useEffect(() => {
    const fromQuery = new URLSearchParams(window.location.search).get("page");
    if ((NAV_PAGES as readonly string[]).includes(fromQuery ?? "")) {
      setActivePage(fromQuery as NavPage);
    }
  }, []);

  return (
    <div className="flex h-full overflow-hidden bg-[#080d14]">
      <LeftNav activePage={activePage} onNavigate={setActivePage} />

      <main className="flex-1 min-w-0 overflow-hidden">
        {activePage === "ask"          && <AskPage />}
        {activePage === "equipment"    && <EquipmentPage />}
        {activePage === "documents"    && <DocumentsPage />}
        {activePage === "graph"        && <KnowledgeGraphPage />}
        {activePage === "verification" && <VerificationPage />}
        {activePage === "maintenance"  && <MaintenancePage />}
        {activePage === "overview"     && <OverviewPage />}
        {activePage === "audit"        && <AuditPage />}
        {activePage === "dataset"      && <PlantSettingsPage />}
      </main>
    </div>
  );
}