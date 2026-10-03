import React from "react";
import { AbsoluteFill, interpolate, staticFile } from "remotion";
import { Audio, Video } from "@remotion/media";
import { BEATS } from "./timeline";
import { ChapterChip } from "./ChapterChip";
import { ProgressRail } from "./ProgressRail";

/**
 * The revised demo: the existing captioned MP4, unaltered, with the narration
 * laid over it.
 *
 * The base video is not re-rendered from frames. It is the committed MP4, played
 * back as-is, so the pixels a judge sees are the pixels that were already
 * reviewed and verified against the caption text. Nothing here can change a
 * number on screen or a word of a caption.
 *
 * Narration is one <Audio> per beat rather than one concatenated file, because
 * each beat needs its own slot. build_vo.ps1 already guarantees a line plus its
 * lead-in and tail fits inside the slot encode.py gives that beat; the fades
 * here only exist so no line starts or ends on a click.
 */

const FADE_FRAMES = 5;

export type DemoNarrationProps = {
  /**
   * Off for the Base composition, which exists so the rendered overlay can be
   * diffed against the untouched video. If Base does not match public/base.mp4
   * frame for frame, the pipeline is altering pixels it has no business
   * altering.
   */
  showOverlay: boolean;
};

export const DemoNarration: React.FC<DemoNarrationProps> = ({ showOverlay }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#080c14" }}>
      <Video src={staticFile("base.mp4")} muted />

      {BEATS.map((beat) => (
        <Audio
          key={beat.n}
          name={`vo-${String(beat.n).padStart(2, "0")}`}
          src={staticFile(beat.audio)}
          from={beat.voiceFrame}
          volume={(mediaFrame) =>
            interpolate(
              mediaFrame,
              [0, FADE_FRAMES, beat.voiceFrames - FADE_FRAMES, beat.voiceFrames],
              [0, 1, 1, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            )
          }
        />
      ))}

      {showOverlay ? <ChapterChip /> : null}
      {showOverlay ? <ProgressRail /> : null}
    </AbsoluteFill>
  );
};