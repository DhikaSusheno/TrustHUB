// components/landing/PetroProcessMotif.tsx
// Line drawing of a petrochemical process train, drawn the way a P&ID is
// drawn: vessels resting on one pipe run, orthogonal pipe runs between them,
// instrument bubbles above each, equipment tags in monospace.
//
// It is deliberately generic. No company name, no logo, no proprietary
// drawing. The reference is the notation engineers already read every day, not
// any particular plant, so nothing on the page implies an endorsement.
//
// Line art rather than a photograph or a gradient: the landing page sits on the
// app surface with panels one step above it, and a photo would fight the canvas
// instead of settling into it. Stroke uses the accent-blue token.
//
// The vessel fill and the tag text read from the theme variables rather than a
// fixed hex, because SVG attributes take CSS colours. A hardcoded panel colour
// here would leave the vessels sitting near-black on a light theme, reading as
// holes punched in the page.
const VESSEL_FILL = "rgb(var(--panel))";
const PIPE = "#3b82f6";

export default function PetroProcessMotif({ className = "" }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 640 240"
      className={className}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {/* Pipe run: one header along the bottom, risers up to each vessel. */}
      <g stroke={PIPE} strokeWidth={1.4} opacity={0.45}>
        <path d="M20 196 H 604" />
        <path d="M182 84 H 236 V 132 H 272" />
        <path d="M368 130 H 420 V 118 H 452" />
        <path d="M150 62 V 44" />
        <path d="M320 112 V 96" />
        <path d="M470 154 V 96" />
      </g>

      {/* Feed pump. */}
      <g stroke={PIPE} strokeWidth={1.5}>
        <circle cx="40" cy="196" r="17" fill={VESSEL_FILL} />
        <path d="M33 188 L47 196 L33 204 Z" fill={PIPE} fillOpacity={0.22} />
      </g>

      {/* Distillation column, with trays. */}
      <g stroke={PIPE} strokeWidth={1.5}>
        <rect x="118" y="62" width="64" height="134" rx="9" fill={VESSEL_FILL} />
        <g strokeWidth={1} opacity={0.5}>
          <path d="M128 86 H 172" />
          <path d="M128 108 H 172" />
          <path d="M128 130 H 172" />
          <path d="M128 152 H 172" />
          <path d="M128 174 H 172" />
        </g>
      </g>

      {/* Reactor, with a baffle line. */}
      <g stroke={PIPE} strokeWidth={1.5}>
        <rect x="272" y="112" width="96" height="84" rx="10" fill={VESSEL_FILL} />
        <path d="M272 156 H 368" strokeWidth={1} opacity={0.5} />
      </g>

      {/* Heat exchanger: circle within a circle, cut by a diagonal. */}
      <g stroke={PIPE} strokeWidth={1.5}>
        <circle cx="470" cy="154" r="42" fill={VESSEL_FILL} />
        <circle cx="470" cy="154" r="27" />
        <path d="M440 124 L 500 184" strokeWidth={1} opacity={0.5} />
      </g>

      {/* Product granules leaving the train. */}
      <g stroke={PIPE} strokeWidth={1.4} opacity={0.6}>
        <circle cx="556" cy="190" r="7" />
        <circle cx="580" cy="202" r="7" />
        <circle cx="604" cy="190" r="7" />
      </g>

      {/* Instrument bubbles, the small circles a P&ID hangs above a vessel. */}
      <g stroke={PIPE} strokeWidth={1.4}>
        <circle cx="150" cy="40" r="8" fill={VESSEL_FILL} />
        <circle cx="320" cy="90" r="8" fill={VESSEL_FILL} />
        <circle cx="470" cy="90" r="8" fill={VESSEL_FILL} />
      </g>

      {/* Equipment tags, in the notation the documents in the index use. */}
      <g
        stroke="none"
        fill="rgb(var(--ink-4))"
        fontSize="10"
        fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
        textAnchor="middle"
      >
        <text x="40" y="228">P-001</text>
        <text x="150" y="228">T-101</text>
        <text x="320" y="228">R-201</text>
        <text x="470" y="228">E-301</text>
      </g>
    </svg>
  );
}