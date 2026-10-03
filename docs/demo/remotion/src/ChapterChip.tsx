import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { BEATS, beatAt } from "./timeline";

/**
 * Chapter marker for the current beat.
 *
 * The captions in the base MP4 already carry the argument, so this does not
 * repeat it. It states where in the fourteen beats the viewer is, and it gets
 * out of the way: it appears at the beat boundary and is gone before the
 * narration starts, so it only ever sits over the app's own header, and only
 * for about two and a half seconds.
 *
 * Typography matches the caption kicker already burned into the source video:
 * monospace, uppercase, wide tracking, same accent colour.
 */

const FADE_IN = 8;
const HOLD_UNTIL = 58;
const GONE_BY = 78;

export const ChapterChip: React.FC = () => {
  const frame = useCurrentFrame();
  const beat = beatAt(frame);

  if (!beat) {
    return null;
  }

  const local = frame - beat.startFrame;
  if (local > GONE_BY) {
    return null;
  }

  const opacity = interpolate(
    local,
    [0, FADE_IN, HOLD_UNTIL, GONE_BY],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <div
      style={{
        position: "absolute",
        top: 16,
        left: 20,
        display: "flex",
        alignItems: "baseline",
        gap: 10,
        padding: "7px 12px 8px",
        backgroundColor: "rgba(8, 12, 20, 0.74)",
        border: "1px solid rgba(125, 211, 252, 0.20)",
        borderRadius: 3,
        fontFamily:
          '"IBM Plex Mono", "Cascadia Mono", Consolas, "Courier New", monospace',
        whiteSpace: "nowrap",
        opacity,
      }}
    >
      <span
        style={{
          fontSize: 11,
          letterSpacing: "0.14em",
          color: "rgba(230, 237, 246, 0.55)",
        }}
      >
        {`${String(beat.n).padStart(2, "0")} / ${String(BEATS.length).padStart(2, "0")}`}
      </span>
      <span
        style={{
          fontSize: 12,
          fontWeight: 600,
          letterSpacing: "0.10em",
          textTransform: "uppercase",
          color: "#7dd3fc",
        }}
      >
        {beat.chapter}
      </span>
    </div>
  );
};