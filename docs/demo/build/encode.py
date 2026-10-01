"""Encode the captioned demo frames into the submission MP4.

Reads docs/demo/beats.json so the on-screen hold of each beat is the one the
capture recorded, rather than a second list that could disagree with it.

Two things this deliberately does not do:

  - it does not add a soundtrack. A synthesised voice reading technical prose is
    worse than silence, and a licensed track is not something to ship quietly.
  - it does not add a fake voiceover. The captions carry the narration.

Crossfades between beats, because a hard cut every seven seconds reads as a
slideshow and a crossfade reads as navigation. No zoom: judges have to be able
to read a table of numbers, and a drifting image makes that harder.

Output is H.264 / yuv420p at 1280x720, the combination every browser, phone and
video player accepts.
"""

import json
import pathlib
import shutil
import subprocess
import sys

OUT = pathlib.Path(__file__).resolve().parent.parent
CAPTIONED = OUT / "captioned"
TARGET = OUT / "TrustHUB-demo.mp4"

FPS = 30
XFADE = 0.5
WIDTH, HEIGHT = 1280, 720
HOLD_PAD = 2.0
CAP_SECONDS = 180

beats = json.loads((OUT / "beats.json").read_text(encoding="utf-8"))["beats"]
if not beats:
    sys.exit("beats.json has no beats")

frames = [CAPTIONED / pathlib.Path(b["frame"]).name for b in beats]
missing = [str(f) for f in frames if not f.exists()]
if missing:
    sys.exit(f"missing captioned frames: {missing}")

# Hold a beat a little longer than the capture recorded. A judge who has not
# finished reading needs the extra seconds, and two seconds costs nothing
# against the 180 s budget.
holds = [b["seconds"] + HOLD_PAD for b in beats]
total = sum(holds) - (len(holds) - 1) * XFADE
if total > CAP_SECONDS:
    sys.exit(f"would run {total:.0f}s, over the {CAP_SECONDS}s cap")

if shutil.which("ffmpeg") is None:
    sys.exit("ffmpeg is not on PATH")

# Scale each still to the output size and give it a constant frame rate, so the
# xfade chain has something well-formed to work with.
chain = [
    f"[{i}:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
    f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}[v{i}]"
    for i in range(len(holds))
]

# Each xfade consumes XFADE seconds of timeline, so the next offset is the
# running duration minus the overlap.
running = holds[0]
for i in range(1, len(holds)):
    chain.append(
        f"[{'x' + str(i - 1) if i > 1 else 'v0'}][v{i}]"
        f"xfade=transition=fade:duration={XFADE}:offset={running - XFADE:.3f}[x{i}]"
    )
    running = running - XFADE + holds[i]

filters = ";".join(chain)

cmd = ["ffmpeg", "-y"]
for f, h in zip(frames, holds):
    cmd += ["-loop", "1", "-t", f"{h:.3f}", "-i", str(f)]
cmd += [
    "-filter_complex", filters,
    "-map", f"[x{len(holds) - 1}]",
    "-c:v", "libx264",
    "-preset", "medium",
    "-crf", "20",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    str(TARGET),
]

print(f"encoding {len(beats)} beats, {total:.0f}s, {WIDTH}x{HEIGHT} @ {FPS}fps")
print(f"  holds: {', '.join(f'{h:.0f}s' for h in holds)}")

proc = subprocess.run(cmd, capture_output=True, text=True)
if proc.returncode != 0:
    print(proc.stderr[-3000:])
    sys.exit(f"ffmpeg failed with {proc.returncode}")

print(f"\n{TARGET.name}  {TARGET.stat().st_size / 1024 / 1024:.1f} MB")

probe = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries",
     "format=duration:stream=codec_name,width,height,pix_fmt,nb_frames,r_frame_rate",
     "-of", "default=noprint_wrappers=1", str(TARGET)],
    capture_output=True, text=True,
)
print(probe.stdout.strip())