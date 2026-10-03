// Copy the two media sets the composition reads into public/.
//
// Remotion only serves files from public/, and the source MP4 plus the 14 WAVs
// are 7.7 MB between them. Keeping one canonical copy in the repo matters more
// than keeping public/ a symlink, so the copy is made here and public/ is
// gitignored. RemapAudio deliberately renders from public/, not from a temp
// directory, so it has to exist before any render.

import { copyFileSync, mkdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REMOTION = path.join(HERE, "..");
const DEMO = path.join(REMOTION, "..");

const VOICE_DIR = path.join(DEMO, "vo", "wav");

/** Copy only when the size differs, so repeated renders stay fast. */
const copyIfChanged = (from, to) => {
  const a = statSync(from).size;
  let b = 0;
  try {
    b = statSync(to).size;
  } catch {
    b = -1;
  }
  if (a === b) {
    return false;
  }
  copyFileSync(from, to);
  return true;
};

mkdirSync(path.join(REMOTION, "public"), { recursive: true });
mkdirSync(path.join(REMOTION, "public", "vo"), { recursive: true });

let copied = 0;

if (
  copyIfChanged(
    path.join(DEMO, "TrustHUB-demo.mp4"),
    path.join(REMOTION, "public", "base.mp4"),
  )
) {
  copied++;
}

// beat-01.wav .. beat-14.wav. Sorted numerically, not lexically, so a future
// beat 10 cannot land between 1 and 2.
const { readdirSync } = await import("node:fs");
const wavs = readdirSync(VOICE_DIR)
  .filter((f) => /^beat-\d+\.wav$/.test(f))
  .sort((a, b) => Number(a.match(/\d+/)[0]) - Number(b.match(/\d+/)[0]));

if (wavs.length === 0) {
  console.error(`No WAVs in ${VOICE_DIR}. Run docs/demo/vo/build_vo.ps1 first.`);
  process.exit(1);
}

for (const w of wavs) {
  if (copyIfChanged(path.join(VOICE_DIR, w), path.join(REMOTION, "public", "vo", w))) {
    copied++;
  }
}

console.log(
  `public/ ready: base.mp4 + ${wavs.length} wav (${copied} copied, ${
    wavs.length + 1 - copied
  } unchanged)`,
);