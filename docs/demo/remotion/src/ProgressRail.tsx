import React from "react";
import { useCurrentFrame } from "remotion";
import { BEATS, CONSTANTS } from "./timeline";

/**
 * Playback position along the bottom edge, with a tick at every beat boundary.
 *
 * Three pixels tall at 720p, so it covers nothing. Its job is to make the shape
 * of the fourteen beats legible while the video plays: the ticks show where the
 * argument turns, which is information the captions cannot carry.
 */

const RAIL = 3;
const TICK = 9;
const TICK_WIDTH = 1;

export const ProgressRail: React.FC = () => {
  const frame = useCurrentFrame();
  const { DURATION_IN_FRAMES } = CONSTANTS;

  const progress = Math.min(1, Math.max(0, frame / DURATION_IN_FRAMES));
  const lastBoundary = DURATION_IN_FRAMES - 1;

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 0,
        height: RAIL,
        backgroundColor: "rgba(125, 211, 252, 0.16)",
      }}
    >
      {BEATS.map((beat) =>
        beat.n === 1 ? null : (
          <div
            key={beat.n}
            style={{
              position: "absolute",
              left: `${(beat.startFrame / lastBoundary) * 100}%`,
              bottom: RAIL,
              width: TICK_WIDTH,
              height: TICK,
              backgroundColor: "rgba(230, 237, 246, 0.30)",
            }}
          />
        ),
      )}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          height: "100%",
          width: `${progress * 100}%`,
          backgroundColor: "#7dd3fc",
        }}
      />
    </div>
  );
};