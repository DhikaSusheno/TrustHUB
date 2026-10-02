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
      <header className="px-6 py-4 border-b border-slate-800/60 flex items-start justify-between gap-4 shrink-0">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-ink tracking-tight">{resolve(title, t)}</h1>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{resolve(subtitle, t)}</p>}
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
      <div className="flex items-center gap-3 text-sm text-slate-500">
        <span className="w-3 h-3 rounded-full border-2 border-slate-600 border-t-blue-400 animate-spin" />
        {label ?? t("state.loading")}&hellip;
      </div>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  const isApi = error instanceof PlantApiError;
  const needsIndex = isApi && error.needsIndex;
  const detail = isApi ? (error as PlantApiError).detail : String(error);

  return (
    <div className="p-6">
      <div
        className={`max-w-2xl rounded-lg border p-5 ${
          needsIndex ? "border-amber-500/30 bg-amber-500/5" : "border-red-500/30 bg-red-500/5"
        }`}
      >
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${needsIndex ? "bg-amber-400" : "bg-red-400"}`} />
          <h2 className="text-sm font-semibold text-ink">
            {needsIndex ? t("state.no_index") : t("state.load_failed")}
          </h2>
        </div>
        <p className="mt-2 text-sm text-slate-300 leading-relaxed whitespace-pre-line">{detail}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-4 text-xs px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
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
      <p className="text-sm text-slate-400">{title}</p>
      {hint && <p className="mt-1 text-xs text-slate-600 max-w-md mx-auto">{hint}</p>}
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
    <section className={`rounded-lg border border-slate-800/60 bg-panel-2 ${className}`}>
      {title && (
        <div className="px-4 py-3 border-b border-slate-800/60 flex items-center justify-between gap-3">
          <div className="min-w-0 flex items-baseline gap-3">
            <h2 className="text-xs font-semibold text-slate-300 uppercase tracking-wide whitespace-nowrap">
              {title}
            </h2>
            {hint && <span className="text-[11px] text-slate-600 truncate">{hint}</span>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </div>
      )}
      <div className={flush ? "" : "p-4"}>{children}</div>
    </section>
  );
}

/** A labelled number. Used for every count shown on the overview. */
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
    good: "text-green-300",
    warn: "text-amber-300",
    bad: "text-red-300",
  }[tone];
  return (
    <div className="rounded-lg border border-slate-800/60 bg-panel-2 px-4 py-3">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-xl font-semibold tabular-nums ${toneClass}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-slate-600">{sub}</div>}
    </div>
  );
}

/** Small monospace tag, e.g. an equipment tag or a document number. */
export function Tag({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "blue" | "green" | "amber" }) {
  const tones = {
    slate: "bg-slate-800/60 text-slate-300 border-slate-700",
    blue: "bg-blue-500/10 text-blue-300 border-blue-500/30",
    green: "bg-green-500/10 text-green-300 border-green-500/30",
    amber: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  };
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-mono border ${tones[tone]}`}>
      {children}
    </span>
  );
}
