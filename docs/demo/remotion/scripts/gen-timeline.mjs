// Generate src/timeline.generated.ts from the files the rest of the video
// pipeline already treats as the source of truth, then refuse to write
// anything unless the numbers agree.
//
//   node scripts/gen-timeline.mjs          write the file
//   node scripts/gen-timeline.mjs --check  fail if it is stale
//
// Inputs:
//   ../build/encode.py   FPS, XFADE, WIDTH, HEIGHT, HOLD_PAD. The MP4 was
//                        encoded with these, so they are parsed rather than
//                        copied: a second copy would be free to drift.
//   ../beats.json        slot lengths and the caption text
//   ../vo/script.json    one narration line per beat, plus voice and rate
//   ../vo/wav/*.wav      real line lengths, read from the RIFF header
//
// A line that overruns its slot is a hard error here rather than something to
// discover in the rendered MP4: the next beat's caption is what a muted judge
// reads, and the narration must not talk over it.

import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REMOTION = path.join(HERE, "..");
const DEMO = path.join(REMOTION, "..");
const VOICE_DIR = path.join(DEMO, "vo", "wav");

const fail = (msg) => {
  console.error(`timeline: ${msg}`);
  process.exit(1);
};

// --- encode.py constants -------------------------------------------------

const encodePy = readFileSync(path.join(DEMO, "build", "encode.py"), "utf8");
const pyConst = (name, cast = Number) => {
  const m = encodePy.match(new RegExp(`^${name} = (.+)$`, "m"));
  if (!m) {
    fail(`could not find ${name} in build/encode.py`);
  }
  return cast(m[1].trim());
};

const FPS = pyConst("FPS");
const XFADE = pyConst("XFADE");
const HOLD_PAD = pyConst("HOLD_PAD");
const [WIDTH, HEIGHT] = (() => {
  const m = encodePy.match(/^WIDTH, HEIGHT = (\d+), (\d+)$/m);
  if (!m) {
    fail("could not find WIDTH, HEIGHT in build/encode.py");
  }
  return [Number(m[1]), Number(m[2])];
})();

// --- beats.json and vo/script.json --------------------------------------

const beats = JSON.parse(readFileSync(path.join(DEMO, "beats.json"), "utf8")).beats;
const vo = JSON.parse(readFileSync(path.join(DEMO, "vo", "script.json"), "utf8"));
const LEAD_IN = Number(vo.lead_in_seconds);
const TAIL = Number(vo.tail_seconds);

if (beats.length !== vo.beats.length) {
  fail(
    `beats.json has ${beats.length} beats, vo/script.json has ${vo.beats.length}.`,
  );
}
if (!Number.isInteger(FPS) || FPS <= 0) {
  fail(`FPS from encode.py is not a usable integer: ${FPS}`);
}

// --- WAV headers ---------------------------------------------------------

/** Duration in seconds from a RIFF/WAVE header. No decoding, no ffmpeg. */
const wavSeconds = (file) => {
  const b = readFileSync(file);
  if (
    b.length < 44 ||
    b.toString("ascii", 0, 4) !== "RIFF" ||
    b.toString("ascii", 8, 12) !== "WAVE"
  ) {
    fail(`${path.basename(file)} is not a RIFF/WAVE file`);
  }
  let fmt = null;
  let dataBytes = null;
  let offset = 12;
  while (offset + 8 <= b.length) {
    const id = b.toString("ascii", offset, offset + 4);
    const size = b.readUInt32LE(offset + 4);
    if (id === "fmt ") {
      fmt = {
        channels: b.readUInt16LE(offset + 10),
        sampleRate: b.readUInt32LE(offset + 12),
        bits: b.readUInt16LE(offset + 22),
      };
    } else if (id === "data") {
      dataBytes = size;
    }
    offset += 8 + size + (size % 2);
  }
  if (!fmt || dataBytes === null) {
    fail(`${path.basename(file)} has no fmt or data chunk`);
  }
  return dataBytes / ((fmt.sampleRate * fmt.channels * fmt.bits) / 8);
};

const wavs = readdirSync(VOICE_DIR)
  .filter((f) => /^beat-\d+\.wav$/.test(f))
  .sort((a, b) => Number(a.match(/\d+/)[0]) - Number(b.match(/\d+/)[0]));

if (wavs.length !== beats.length) {
  fail(
    `${wavs.length} WAVs in vo/wav, expected ${beats.length}. Run docs/demo/vo/build_vo.ps1.`,
  );
}

// --- derive --------------------------------------------------------------

const rows = [];
const problems = [];
let cursor = 0;

beats.forEach((b, i) => {
  const line = vo.beats[i];
  if (line.n !== i + 1) {
    fail(`vo/script.json beat ${i + 1} has n=${line.n}`);
  }
  const holdSec = Number(b.seconds) + HOLD_PAD;
  const startFrame = Math.round(cursor * FPS);
  const slotFrames = Math.round(holdSec * FPS);
  const voiceFrame = startFrame + Math.round(LEAD_IN * FPS);
  const seconds = wavSeconds(path.join(VOICE_DIR, wavs[i]));
  const voiceFrames = Math.round(seconds * FPS);
  const audio = `vo/${wavs[i]}`;

  const overrun = LEAD_IN + seconds + TAIL - holdSec;
  if (overrun > 0.005) {
    problems.push(
      `beat ${i + 1} overruns by ${overrun.toFixed(2)}s ` +
        `(line ${seconds.toFixed(2)}s, lead ${LEAD_IN}s, tail ${TAIL}s, slot ${holdSec.toFixed(2)}s)`,
    );
  }
  if (voiceFrame + voiceFrames > startFrame + slotFrames) {
    problems.push(
      `beat ${i + 1} audio reaches ${voiceFrame + voiceFrames} but the slot ends at ${startFrame + slotFrames}`,
    );
  }

  rows.push({
    n: i + 1,
    chapter: line.chapter,
    note: b.note,
    seconds: Number(b.seconds),
    holdSec,
    startFrame,
    slotFrames,
    voiceFrame,
    voiceFrames,
    audio,
  });

  cursor += holdSec - XFADE;
});

if (problems.length > 0) {
  console.error("timeline: narration does not fit:");
  for (const p of problems) {
    console.error(`  ${p}`);
  }
  process.exit(1);
}

// The last beat keeps its full slot. A crossfade only ever overlaps two beats,
// so subtracting one for the end would shorten the video that is being revised.
const last = rows[rows.length - 1];
const DURATION_IN_FRAMES = last.startFrame + last.slotFrames;

// encode.py computes the same total a different way. If they ever disagree, the
// narration is being laid out against a timeline that no longer exists.
const encodeTotal =
  rows.reduce((sum, r) => sum + r.holdSec, 0) - (rows.length - 1) * XFADE;
if (Math.abs(encodeTotal * FPS - DURATION_IN_FRAMES) > 1) {
  fail(
    `total is ${DURATION_IN_FRAMES} frames here but ${(encodeTotal * FPS).toFixed(1)} by the encode.py formula`,
  );
}

// --- emit ----------------------------------------------------------------

const num = (n) => Number(n.toFixed(3));

const body = rows
  .map(
    (r) =>
      `  {\n` +
      `    n: ${r.n},\n` +
      `    chapter: ${JSON.stringify(r.chapter)},\n` +
      `    note: ${JSON.stringify(r.note)},\n` +
      `    seconds: ${r.seconds},\n` +
      `    holdSec: ${num(r.holdSec)},\n` +
      `    startFrame: ${r.startFrame},\n` +
      `    slotFrames: ${r.slotFrames},\n` +
      `    voiceFrame: ${r.voiceFrame},\n` +
      `    voiceFrames: ${r.voiceFrames},\n` +
      `    audio: ${JSON.stringify(r.audio)},\n` +
      `  },`,
  )
  .join("\n");

const out = `// Generated by scripts/gen-timeline.mjs. Do not edit by hand.
//
// Inputs: docs/demo/build/encode.py, docs/demo/beats.json,
//         docs/demo/vo/script.json, docs/demo/vo/wav/*.wav
// Run \`npm run timeline\` after changing any of them.

import type { Beat, TimelineConstants } from "./types";

export const CONSTANTS: TimelineConstants = {
  FPS: ${FPS},
  WIDTH: ${WIDTH},
  HEIGHT: ${HEIGHT},
  XFADE: ${XFADE},
  HOLD_PAD: ${HOLD_PAD},
  LEAD_IN: ${LEAD_IN},
  TAIL: ${TAIL},
  DURATION_IN_FRAMES: ${DURATION_IN_FRAMES},
  TOTAL_SLOT_FRAMES: ${rows.reduce((s, r) => s + r.slotFrames, 0)},
};

export const BEATS: Beat[] = [
${body}
];
`;

const target = path.join(REMOTION, "src", "timeline.generated.ts");

// This repo has core.autocrlf=true and no .gitattributes, so on a fresh Windows
// clone the committed file comes back with CRLF while the generated string above
// has LF. Compare with endings normalised, or every Windows checkout reports a
// stale file it did not actually change.
const normalise = (text) => text.replace(/\r\n/g, "\n");

if (process.argv.includes("--check")) {
  if (normalise(readFileSync(target, "utf8")) !== out) {
    fail("src/timeline.generated.ts is stale. Run: npm run timeline");
  }
  console.log(
    `timeline.generated.ts is current: ${rows.length} beats, ${DURATION_IN_FRAMES} frames (${(DURATION_IN_FRAMES / FPS).toFixed(1)}s)`,
  );
} else {
  writeFileSync(target, out);
  const longest = Math.max(...rows.map((r) => r.voiceFrames / FPS));
  console.log(
    `wrote src/timeline.generated.ts: ${rows.length} beats, ${DURATION_IN_FRAMES} frames @ ${FPS}fps, longest line ${longest.toFixed(2)}s`,
  );
}