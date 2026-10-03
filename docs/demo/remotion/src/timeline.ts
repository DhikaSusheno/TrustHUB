import { BEATS, CONSTANTS } from "./timeline.generated";
import type { Beat } from "./types";

export { BEATS, CONSTANTS };
export type { Beat, TimelineConstants } from "./types";

/** The beat visible at a given frame, or undefined past the last crossfade. */
export const beatAt = (frame: number): Beat | undefined =>
  BEATS.find(
    (b) => frame >= b.startFrame && frame < b.startFrame + b.slotFrames,
  );