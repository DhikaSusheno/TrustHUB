# Narration overlay

`../TrustHUB-demo-vo.mp4` is `../TrustHUB-demo.mp4` with a narration track and a
chapter marker laid over it. Same 2 min 26 s, same 1280x720, same frames.

```
npm install
npm run assets            # copy base.mp4 and the 14 WAVs into public/
npm run dev              # Remotion Studio, for looking at it
npm run render           # intermediate -> docs/demo/remotion/out/
python scripts/check-audio.py out/TrustHUB-demo-vo.mp4
```

## It revises the existing MP4, it does not rebuild it

The base layer is the committed MP4, played back. It is not re-rendered from
`frames/`, and the composition has no code that could change a number on screen
or a word of a caption. That is deliberate: the captions in the base video were
checked against the text their frames actually rendered (`../build/verify.py`),
and every pixel a judge sees has already been through that check. Re-encoding
from screenshots would put all of it back at risk for no gain.

`scripts/diff-overlay.py` exists to keep that honest. It compares a still of the
`Base` composition (overlay off) against a still of `Narration` at the same frame
and prints where the pixels changed. Current result:

```
rows   16-46   x   20-211  ok      chapter chip
rows  708-719  x      0-1280  ok      progress rail and beat ticks
changed pixels: 5217 of 921600
```

## Why the overlay is so small

The base video is 14 beats of a real UI, and the thing a judge needs to read is
the caption. So there are two overlay elements and neither one repeats the
argument:

- a chapter chip, 31 px tall, that announces the beat and is gone 2.6 s later,
  before the narration starts
- a 3 px progress rail with a tick at each beat boundary

Nothing is centred, nothing is larger than it needs to be, and there is no
music: the licensing question and the muted-judge argument in `../build/README.md`
still stand.

## The timeline is generated, not written

`src/timeline.generated.ts` is written by `scripts/gen-timeline.mjs` from
`../build/encode.py`, `../beats.json`, `../vo/script.json` and the WAV headers.
Run `npm run timeline` after changing any of them; `npm run lint` fails if the
generated file is stale.

Three things stop it silently drifting:

- the slot lengths come from the same numbers `encode.py` encoded with, parsed
  out of that file rather than copied, so the narration cannot be laid out
  against a timeline that no longer exists
- the length of each line is read from its RIFF header, so the volume fade out
  lands on the real end of the audio
- generation fails outright if a line plus its lead-in and tail does not fit its
  slot, because a line running past its beat talks over the next caption

The staleness check compares with line endings normalised, because this repo has
`core.autocrlf=true` and no `.gitattributes`: a fresh Windows checkout returns
the generated file with CRLF, and comparing it against LF output byte for byte
would report a stale file nobody had touched.

## Why ffmpeg does the final encode

Remotion always tags its H.264 output full range `yuvj420p` with `bt470bg`
primaries, which is not what a browser or a submission checker expects from a
720p file, and `--pixel-format` does not change it. So `npm run render` is two
steps: Remotion renders a near-lossless intermediate with the overlay and audio
already laid in, then `scripts/finalize.mjs` encodes the delivery file once with
the tags spelled out. One visible encode, not two.

`finalize.mjs` uses the ffmpeg that Remotion already installs, so this adds no
dependency and works with the network off. That binary also means
`../build/encode.py` can run on a machine with no system ffmpeg:

```
node_modules/@remotion/compositor-win32-x64-msvc/ffmpeg.exe
node_modules/@remotion/compositor-win32-x64-msvc/ffprobe.exe
```

## What a script cannot check

`check-audio.py` proves each line is present, at the right frame, and does not
run into the next beat. It cannot tell you whether the voice flattens the
argument. `../vo/script.json` spells out how to find out: listen to beat 4 and
beat 7, and if it is worse than silence, delete `../vo/` and ship the original.