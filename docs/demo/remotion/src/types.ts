export type Beat = {
  /** 1-based beat number, as shown in the caption and the chapter chip. */
  n: number;
  /** Chapter title. Comes from the narration script, not invented here. */
  chapter: string;
  /** Caption note from beats.json. Carried so the chip can be checked against it. */
  note: string;
  /** Still seconds for this beat, before HOLD_PAD. */
  seconds: number;
  /** Usable slot: seconds + HOLD_PAD, because the crossfade already elapsed. */
  holdSec: number;
  /** Frame where this beat is first fully visible. */
  startFrame: number;
  /** Frames until the next beat takes over. */
  slotFrames: number;
  /** Frame where the narration line starts. script.json adds a lead-in. */
  voiceFrame: number;
  /** Real length of the WAV in frames, read from its header. Used for the fade out. */
  voiceFrames: number;
  /** Path under public/. */
  audio: string;
};

export type TimelineConstants = {
  FPS: number;
  WIDTH: number;
  HEIGHT: number;
  XFADE: number;
  HOLD_PAD: number;
  LEAD_IN: number;
  TAIL: number;
  /** Total frames. Matches the length of docs/demo/TrustHUB-demo.mp4. */
  DURATION_IN_FRAMES: number;
  /** Sum of slotFrames, for the progress rail. */
  TOTAL_SLOT_FRAMES: number;
};