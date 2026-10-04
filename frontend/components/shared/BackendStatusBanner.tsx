"use client";

// components/shared/BackendStatusBanner.tsx
// Says whether the pages behind it are showing real indexed data.
//
// This banner exists because "why is this page empty?" is the first question a
// viewer asks, and the honest answer needs to be visible before they ask it.
// Three states, all distinguishable:
//
//   live      no banner. Real data, nothing to warn about.
//   empty     the backend is up but the plant index is not built. The exact
//             command to build it is shown, not a generic error.
//   offline   the backend is not reachable at all.
//
// `empty` and `offline` were previously collapsed into one "DEMO DATA" state,
// which was worse than useless: the backend working is good news, and telling
// someone it is not while their pages are about to load correctly loses their
// trust in everything else on screen.

import { useBackendStatus } from "@/hooks/useBackendStatus";
import { STATIC_BANNER_TEXT, STATIC_DEMO } from "@/lib/staticDemo";

const ICONS = {
  live: "●",
  empty: "▲",
  checking: "◌",
  offline: "✕",
} as const;

const COLORS = {
  live: "bg-green-500/20 text-green-400 border-green-500/30",
  empty: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  checking: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  offline: "bg-red-500/20 text-red-400 border-red-500/30",
} as const;

const LABELS = {
  live: "LIVE DATA",
  empty: "INDEX NOT BUILT",
  checking: "CHECKING",
  offline: "BACKEND OFFLINE",
} as const;

const MESSAGES = {
  live: "",
  empty:
    "The backend is running, but no plant documents are indexed yet. Everything below will stay empty until the index exists.",
  checking: "Checking whether the plant index is available…",
  offline:
    "The backend is not reachable. Start it, then reload. If it runs on another port, set NEXT_PUBLIC_BACKEND_URL.",
} as const;

export default function BackendStatusBanner() {
  const { mode, problem } = useBackendStatus();

  // Static demo build: always say so, never imply a live backend.
  if (STATIC_DEMO) {
    return (
      <div
        className="shrink-0 px-4 py-2.5 bg-blue-500/20 text-blue-300 border-blue-500/30 border-b border-solid"
        role="status"
      >
        <div className="max-w-7xl mx-auto flex items-center gap-2.5 min-w-0">
          <span className="text-xs font-semibold uppercase tracking-wide shrink-0">
            STATIC DEMO
          </span>
          <span className="text-xs text-slate-300/80">{STATIC_BANNER_TEXT}</span>
        </div>
      </div>
    );
  }

  // Nothing to warn about when the index is live.
  if (mode === "live") return null;

  return (
    <div
      className={`shrink-0 px-4 py-2.5 ${COLORS[mode]} border-b border-solid`}
      role="status"
      aria-live="polite"
    >
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-2.5 min-w-0">
          <span
            aria-hidden="true"
            className={`text-sm leading-none shrink-0 ${
              mode === "checking" ? "animate-pulse" : ""
            }`}
          >
            {ICONS[mode]}
          </span>
          <span className="text-xs font-semibold uppercase tracking-wide shrink-0">
            {LABELS[mode]}
          </span>
          <span className="text-xs text-slate-300/80 truncate">{MESSAGES[mode]}</span>
        </div>

        {mode === "empty" ? (
          <code className="text-[11px] font-mono text-slate-200 bg-slate-900/60 border border-slate-700/60 rounded px-2 py-1 whitespace-nowrap shrink-0">
            {problem?.match(/python -m [\w.]+/)?.[0] ?? "python -m plant.fetch_dataset"}
          </code>
        ) : (
          (mode === "offline" || mode === "checking") && (
            <button
              onClick={() => window.location.reload()}
              className="text-xs px-3 py-1.5 bg-slate-900/50 border border-slate-700/50 rounded-lg hover:bg-slate-800/50 transition-colors whitespace-nowrap shrink-0"
            >
              Retry
            </button>
          )
        )}
      </div>
    </div>
  );
}