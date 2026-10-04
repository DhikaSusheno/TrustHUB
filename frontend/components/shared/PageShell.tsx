// components/shared/PageShell.tsx
// Layout primitives shared by every Manufacturing Knowledge Hub page, plus the
// three states a data-backed page can be in.
//
// The error state is the interesting one. When the plant index has not been
// built, the backend returns 503 with the exact command that fixes it. Showing
// that command as the error body is the difference between a visitor who can
// proceed and one who has to ask what went wrong.

"use client";

import type { ReactNode } from "react";
import { PlantApiError } from "@/lib/plantApi";
import { useI18n } from "@/lib/i18n/LocaleProvider";
import { STRINGS, type StringKey } from "@/lib/i18n/dictionary";
import { STATIC_DEMO } from "@/lib/staticDemo";

/** A dictionary key for static chrome, or a literal for computed text. */
type Chrome = string | StringKey;

function resolve(value: Chrome, t: (key: StringKey) => string): string {
  return typeof value === "string" && value in STRINGS ? t(value as StringKey) : value;
}

interface ShellProps {
  title: Chrome;
  subtitle?: Chrome;
  /** Rendered on the right of the title row: filters, buttons, totals. */
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function PageShell({ title, subtitle, actions, children, className = "" }: ShellProps) {
  const { t } = useI18n();
  return (
    <div className={`flex flex-col h-full overflow-hidden ${className}`}>
      {/* Google Stitch clean top header bar with subtle border bottom */}
      <header className="px-4 sm:px-6 py-4 border-b border-slate-800/80 bg-surface/80 backdrop-blur-sm flex flex-wrap items-center justify-between gap-x-4 gap-y-3 shrink-0">
        <div className="min-w-0 flex items-center gap-3">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.6)]" />
          <div>
            <h1 className="text-lg font-bold text-ink tracking-tight">{resolve(title, t)}</h1>
            {subtitle && <p className="mt-0.5 text-xs text-slate-400 leading-relaxed">{resolve(subtitle, t)}</p>}
          </div>
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </header>
      <div className="flex-1 overflow-y-auto">{children}</div>
    </div>
  );
}

export function Loading({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center justify-center h-64" role="status" aria-live="polite">
      <div className="flex items-center gap-3 text-sm text-slate-400 font-medium">
        <span className="w-4 h-4 rounded-full border-2 border-slate-700 border-t-blue-400 animate-spin" />
        {label ?? t("state.loading")}&hellip;
      </div>
    </div>
  );
}

/** Headline figures from the verified number table, each with its scope. */
const STATIC_FIGURES: { label: string; value: string }[] = [
  { label: "Documents indexed", value: "95" },
  { label: "Work orders", value: "211" },
  { label: "Breakdowns", value: "31" },
  { label: "Knowledge graph (full)", value: "134 nodes, 126 links" },
  { label: "Locked evaluation", value: "63 / 63" },
];

/** Shown instead of an error when this build is the static demo snapshot. */
function StaticLivePanel() {
  return (
    <div className="p-6">
      <div className="max-w-2xl rounded-xl border border-slate-700/80 bg-panel-2/80 p-5 shadow-lg">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-400" />
          <h2 className="text-sm font-semibold text-ink">Live system only</h2>
        </div>
        <p className="mt-2.5 text-sm text-slate-300 leading-relaxed">
          This view reads the indexed dataset, which is not included in this static snapshot.
          The live system is shown in the demo video. The Ask and Overview views work here
          with captured results.
        </p>
        <dl className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 border-t border-slate-800/80 pt-4">
          {STATIC_FIGURES.map((f) => (
            <div key={f.label} className="flex items-baseline justify-between gap-3">
              <dt className="text-xs text-slate-400">{f.label}</dt>
              <dd className="text-xs font-mono text-slate-200">{f.value}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-[11px] text-slate-500">
          Figures from the official CALIBER-provided dataset, labelled sample data.
        </p>
      </div>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  if (STATIC_DEMO) return <StaticLivePanel />;
  const isApi = error instanceof PlantApiError;
  const needsIndex = isApi && error.needsIndex;
  const detail = isApi ? (error as PlantApiError).detail : String(error);

  return (
    <div className="p-6">
      <div
        className={`max-w-2xl rounded-xl border p-5 ${
          needsIndex ? "border-amber-500/40 bg-amber-500/10 shadow-lg" : "border-red-500/40 bg-red-500/10 shadow-lg"
        }`}
      >
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${needsIndex ? "bg-amber-400 animate-pulse" : "bg-red-400 animate-pulse"}`} />
          <h2 className="text-sm font-semibold text-ink">
            {needsIndex ? t("state.no_index") : t("state.load_failed")}
          </h2>
        </div>
        <p className="mt-2.5 text-xs sm:text-sm text-slate-200 leading-relaxed whitespace-pre-line font-mono bg-slate-950/40 p-3 rounded-lg border border-slate-800">{detail}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-4 text-xs font-semibold px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors"
          >
            {t("state.try_again")}
          </button>
        )}
      </div>
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="p-10 text-center">
      <p className="text-sm font-medium text-slate-400">{title}</p>
      {hint && <p className="mt-1 text-xs text-slate-500 max-w-md mx-auto">{hint}</p>}
    </div>
  );
}

interface PanelProps {
  title?: string;
  hint?: ReactNode;
  /** Rendered on the right of the header, after the hint. Controls. */
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  /** Removes the body padding, for tables that manage their own spacing. */
  flush?: boolean;
}

export function Panel({ title, hint, actions, children, className = "", flush = false }: PanelProps) {
  return (
    <section className={`rounded-xl border border-slate-800/80 bg-panel-2/90 shadow-sm transition-all hover:border-slate-700/80 ${className}`}>
      {title && (
        <div className="px-4 py-3 border-b border-slate-800/80 flex items-center justify-between gap-3 bg-slate-900/40">
          <div className="min-w-0 flex items-baseline gap-3">
            <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider whitespace-nowrap">
              {title}
            </h2>
            {hint && <span className="text-[11px] text-slate-400 truncate">{hint}</span>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </div>
      )}
      <div className={flush ? "" : "p-4"}>{children}</div>
    </section>
  );
}

export function Stat({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: "default" | "good" | "warn" | "bad";
}) {
  const toneClass = {
    default: "text-ink",
    good: "text-green-400",
    warn: "text-amber-400",
    bad: "text-red-400",
  }[tone];

  const toneBar = {
    default: "bg-blue-500/60",
    good: "bg-green-500",
    warn: "bg-amber-500",
    bad: "bg-red-500",
  }[tone];

  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-800/80 bg-panel-2/70 p-4 shadow-sm transition-all hover:border-slate-700/80 hover:bg-panel-2">
      <div className={`absolute top-0 left-0 h-1 w-full ${toneBar}`} />
      <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400">{label}</div>
      <div className={`mt-2 text-2xl sm:text-3xl font-bold tabular-nums leading-none tracking-tight ${toneClass}`}>{value}</div>
      {sub && <div className="mt-2.5 text-xs text-slate-400 leading-snug">{sub}</div>}
    </div>
  );
}

export function Tag({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "blue" | "green" | "amber" }) {
  const tones = {
    slate: "bg-slate-800/80 text-slate-300 border-slate-700/80",
    blue: "bg-blue-500/15 text-blue-300 border-blue-500/40",
    green: "bg-green-500/15 text-green-300 border-green-500/40",
    amber: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-mono border ${tones[tone]}`}>
      {children}
    </span>
  );
}
