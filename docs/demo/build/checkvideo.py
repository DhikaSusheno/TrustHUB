"""Confirm the encoded MP4 actually carries the UI, not black frames.

Two checks, because either alone is weak:

  blackdetect over the whole timeline, so a gap between beats or a broken
  xfade offset would show up as an unexplained black stretch rather than being
  averaged away.

  mean luminance of evenly spaced samples, which catches a video that is
  technically non-black but blank - a white or single-colour frame would pass
  blackdetect and still be a broken submission.
"""

import pathlib
import subprocess

VIDEO = pathlib.Path(__file__).resolve().parent.parent / "TrustHUB-demo.mp4"

print("=== blackdetect over the full timeline ===")
p = subprocess.run(
    ["ffmpeg", "-hide_banner", "-i", str(VIDEO),
     "-vf", "blackdetect=d=0.4:pix_th=0.10", "-f", "null", "-"],
    capture_output=True, text=True,
)
black = [ln for ln in p.stderr.splitlines() if "black_start" in ln]
print(f"  {len(black)} black stretch(es)")
for ln in black:
    print(f"    {ln.strip()}")

print()
print("=== mean luminance, 12 samples across the timeline ===")
import json

dur = float(
    subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(VIDEO)],
        capture_output=True, text=True,
    ).stdout and json.loads(
        subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(VIDEO)],
            capture_output=True, text=True,
        ).stdout
    )["format"]["duration"]
)
print(f"  duration {dur:.1f}s")

worst = None
for i in range(12):
    t = 1.5 + (dur - 3.0) * i / 11
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-v", "info", "-ss", f"{t:.2f}",
         "-i", str(VIDEO), "-frames:v", "1",
         "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG",
         "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    y = None
    for ln in out.splitlines():
        if "YAVG" in ln:
            y = float(ln.split("=")[-1].strip())
    if y is None:
        print(f"  t={t:6.1f}s  Y_avg=  (no frame decoded)")
        continue
    flag = "" if y > 15 else "  <-- SUSPECT"
    if worst is None or y < worst[1]:
        worst = (t, y)
    print(f"  t={t:6.1f}s  Y_avg={y:6.1f}{flag}")

print()
if black:
    print(f"FAIL: {len(black)} black stretch(es) in the video")
elif worst and worst[1] <= 15:
    print(f"FAIL: darkest sample t={worst[0]:.1f}s has Y_avg={worst[1]:.1f}")
else:
    print(f"ok: no black stretches; darkest sample "
          f"t={worst[0]:.1f}s Y_avg={worst[1]:.1f}")
