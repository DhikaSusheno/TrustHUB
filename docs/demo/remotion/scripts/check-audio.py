"""Check that the narration lands where the timeline says it should.

    python scripts/check-audio.py out/TrustHUB-demo-vo.mp4

Decodes the audio track with the ffmpeg that ships with Remotion and measures
RMS in 100 ms windows. For every beat it asserts that there is speech inside the
line's own window and silence between this line and the next one.

This is not a substitute for listening. It catches the failure modes that are
expensive to find by ear in a two and a half minute file: a line that never made
it into the mix, a line that starts on the wrong beat, a line that runs on and
talks over the next caption.
"""

import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import wave

WINDOW = 0.1
SPEECH_DBFS = -45.0
SILENCE_DBFS = -50.0

HERE = os.path.dirname(os.path.abspath(__file__))
REMOTION = os.path.dirname(HERE)

SPEECH_FLOOR = 10 ** (SPEECH_DBFS / 20)
SILENCE_CEIL = 10 ** (SILENCE_DBFS / 20)


def find_ffmpeg():
    cli = os.path.join(REMOTION, "node_modules", "@remotion")
    for pkg in sorted(os.listdir(cli)):
        if not pkg.startswith("compositor-"):
            continue
        exe = os.path.join(
            cli, pkg, "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        )
        if os.path.exists(exe):
            return exe
    raise SystemExit("no ffmpeg found under node_modules/@remotion")


def load_rms(ffmpeg, media, rate=8000):
    """RMS per WINDOW seconds, plus peak, of the first audio track."""
    tmp = os.path.join(tempfile.gettempdir(), "vo-check.wav")
    subprocess.run(
        [
            ffmpeg, "-y", "-v", "error", "-i", media,
            "-vn", "-ac", "1", "-ar", str(rate), tmp,
        ],
        check=True,
    )
    with wave.open(tmp) as w:
        rate_actual = w.getframerate()
        frames = w.readframes(w.getnframes())
    os.unlink(tmp)

    samples = struct.unpack(f"<{len(frames) // 2}h", frames)
    per = int(WINDOW * rate_actual)
    rms = []
    for i in range(0, len(samples) - per + 1, per):
        chunk = samples[i : i + per]
        rms.append(math.sqrt(sum(s * s for s in chunk) / len(chunk)) / 32768.0)
    peak = max((abs(s) / 32768.0 for s in samples), default=0.0)
    return rms, peak


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    media = sys.argv[1]

    # The timeline lives in a generated TypeScript file, so read the numbers back
    # out of it. gen-timeline.mjs is the only writer, so this cannot disagree with
    # the render: the render was bundled from the same file.
    src = open(os.path.join(REMOTION, "src", "timeline.generated.ts")).read()
    consts = dict(re.findall(r"^\s+(\w+): ([\d.]+),$", src, re.M))

    beats = []
    for block in re.findall(r"\{\n(.*?)\n  \},", src, re.S):
        fields = dict(re.findall(r"^\s+(\w+): ([\d.]+),$", block, re.M))
        beats.append(
            (
                int(fields["n"]),
                int(fields["voiceFrame"]),
                int(fields["voiceFrames"]),
            )
        )

    fps = int(consts["FPS"])
    rms, peak = load_rms(find_ffmpeg(), media)

    print(f"{os.path.basename(media)}: {len(rms)} windows of {WINDOW}s, peak {20 * math.log10(peak):.1f} dBFS")

    problems = []
    for n, start, length in beats:
        first = int(start / fps / WINDOW)
        last = int((start + length) / fps / WINDOW)
        inside = rms[first:last]
        if not inside:
            problems.append(f"beat {n}: window is past the end of the audio")
            continue
        loudest = max(inside)
        if loudest < SPEECH_FLOOR:
            problems.append(
                f"beat {n}: no speech in {start / fps:.2f}-{(start + length) / fps:.2f}s "
                f"(loudest {20 * math.log10(loudest):.1f} dBFS)"
            )
        # Gap between this line and the next beat's line.
        nxt = next((b for b in beats if b[0] == n + 1), None)
        if nxt:
            gap = rms[last : int(nxt[1] / fps / WINDOW)]
            if gap and max(gap) > SILENCE_CEIL:
                problems.append(
                    f"beat {n}: sound continues into beat {n + 1} "
                    f"({20 * math.log10(max(gap)):.1f} dBFS)"
                )

    for p in problems:
        print(f"  FAIL {p}")
    if not problems:
        print(f"  all {len(beats)} lines present, none overlapping the next beat")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())