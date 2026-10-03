// Encode the delivery file from the Remotion intermediate.
//
//   node scripts/finalize.mjs
//
// Why this is a separate step: Remotion's own H.264 output always comes out
// full range and tagged yuvj420p, with bt470bg primaries, because it encodes
// whatever the compositor produced and does not retag it. That is not what a
// browser, a phone, or a submission checker expects from a 720p file. The
// committed source MP4 is plain limited-range yuv420p.
//
// So Remotion renders a near-lossless intermediate with the overlay and audio
// already laid in, and ffmpeg does the single real encode with the tags spelled
// out. One visible encode, not two.
//
// ffmpeg is the binary Remotion already installed, so this adds no dependency
// and works offline.

import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, statSync, unlinkSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REMOTION = path.join(HERE, "..");
const OUT = path.join(REMOTION, "out");

const INTERMEDIATE = path.join(OUT, "intermediate-vo.mp4");
const DELIVERABLE = path.join(OUT, "TrustHUB-demo-vo.mp4");

const CRF = 20;
const AUDIO_BITRATE = "128k";

const findFfmpeg = () => {
  const cli = path.join(REMOTION, "node_modules", "@remotion");
  const pkg = readdirSync(cli).find((d) => d.startsWith("compositor-"));
  if (!pkg) {
    throw new Error("no @remotion/compositor-* package, cannot find ffmpeg");
  }
  const exe = path.join(cli, pkg, process.platform === "win32" ? "ffmpeg.exe" : "ffmpeg");
  if (!existsSync(exe)) {
    throw new Error(`ffmpeg not found at ${exe}`);
  }
  return exe;
};

if (!existsSync(INTERMEDIATE)) {
  console.error(
    `missing ${INTERMEDIATE}. Run: npm run render:intermediate`,
  );
  process.exit(1);
}

const ffmpeg = findFfmpeg();

const args = [
  "-y",
  "-hide_banner",
  "-loglevel", "error",
  "-i", INTERMEDIATE,
  // Limited range, BT.709, 8-bit 4:2:0: what every player assumes for 720p.
  "-c:v", "libx264",
  "-preset", "slow",
  "-crf", String(CRF),
  "-pix_fmt", "yuv420p",
  "-profile:v", "high",
  "-level", "4.0",
  "-color_range", "tv",
  "-colorspace", "bt709",
  "-color_primaries", "bt709",
  "-color_trc", "bt709",
  // One voice. AAC-LC at 128k is transparent for speech.
  "-c:a", "aac",
  "-profile:a", "aac_low",
  "-b:a", AUDIO_BITRATE,
  "-ar", "48000",
  "-ac", "2",
  // The audio track comes out a few milliseconds longer than the video because
  // of AAC frame padding. Cut to the video so the file ends where the last beat
  // ends rather than trailing silence.
  "-shortest",
  "-movflags", "+faststart",
  DELIVERABLE,
];

console.log(`encoding ${path.basename(DELIVERABLE)} at CRF ${CRF}, AAC ${AUDIO_BITRATE}`);
const run = spawnSync(ffmpeg, args, { stdio: "inherit" });
if (run.status !== 0) {
  console.error(`ffmpeg failed with ${run.status}`);
  process.exit(run.status ?? 1);
}

const mb = (f) => (statSync(f).size / 1024 / 1024).toFixed(2);
console.log(`${path.basename(DELIVERABLE)}  ${mb(DELIVERABLE)} MB`);

// The intermediate is 20-30 MB of near-lossless video that nobody needs twice.
unlinkSync(INTERMEDIATE);