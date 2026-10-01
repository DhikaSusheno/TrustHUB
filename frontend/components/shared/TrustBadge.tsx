// components/shared/TrustBadge.tsx
// The trust badge, plus the score that produced it.
//
// The badge is the whole point of the product, so it is rendered from one
// component and never from a locally recomputed colour: `TRUSTED`,
// `VERIFY`, and `DO NOT EXECUTE` are decided in one place on the backend
// (`trust.badge_for`) and arrive here as a string. A second place that maps
// score to colour would drift from the thresholds, and the drift would show
// up as a green badge on an answer the backend is willing to refuse.

import type { Badge } from "@/lib/plantApi";

const STYLES: Record<Badge, string> = {
  TRUSTED: "bg-green-500/20 text-green-300 border-green-500/40",
  VERIFY: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  "DO NOT EXECUTE": "bg-red-500/20 text-red-300 border-red-500/40",
};

const DOTS: Record<Badge, string> = {
  TRUSTED: "bg-green-400",
  VERIFY: "bg-amber-400",
  "DO NOT EXECUTE": "bg-red-400",
};

/** One line of what the badge means in practice. Shown on hover. */
const GLOSS: Record<Badge, string> = {
  TRUSTED: "Approved, revisioned, and corroborated by several documents.",
  VERIFY: "Usable, but confirm against the cited document before acting.",
  "DO NOT EXECUTE": "No trustworthy source. Do not act on this answer.",
};

interface Props {
  badge: Badge;
  score?: number;
  size?: "sm" | "md";
  showScore?: boolean;
}

export default function TrustBadge({ badge, score, size = "sm", showScore = true }: Props) {
  const base = size === "md" ? "text-xs px-2.5 py-1" : "text-[10px] px-2 py-0.5";
  const valid = badge in STYLES;
  const safe: Badge = valid ? badge : "VERIFY";

  return (
    <span
      title={GLOSS[safe]}
      className={`inline-flex items-center gap-1.5 ${base} rounded-full font-semibold border ${STYLES[safe]}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${DOTS[safe]}`} />
      {safe}
      {showScore && typeof score === "number" && Number.isFinite(score) && (
        <span className="font-mono font-normal opacity-80">{score.toFixed(2)}</span>
      )}
    </span>
  );
}

/** The three signals shown next to an answer, if the backend returned them. */
interface SignalProps {
  name: string;
  score: number;
  weight: number;
  detail: string;
}

export function SignalRow({ name, score, weight, detail }: SignalProps) {
  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);
  // Colour follows the same three-step logic as the badge so the bar and the
  // badge can never disagree about what they think of a score.
  const tone = score >= 0.8 ? "bg-green-400" : score >= 0.5 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="group">
      <div className="flex items-baseline justify-between gap-2 text-[11px]">
        <span className="text-slate-300 capitalize">{name.replace(/_/g, " ")}</span>
        <span className="text-slate-500 font-mono">
          {score.toFixed(2)} &times; {weight.toFixed(2)}
        </span>
      </div>
      <div className="mt-1 h-1 rounded-full bg-slate-800 overflow-hidden">
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      {detail && (
        <p className="mt-1 text-[11px] leading-snug text-slate-500">{detail}</p>
      )}
    </div>
  );
}
