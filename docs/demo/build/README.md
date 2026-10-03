# Demo video build

`../TrustHUB-demo.mp4` is the base video: **2 min 26 s**, 1280x720, H.264,
4.1 MB. It is built, not recorded, so every frame can be checked against the
running system before anyone watches it. It also ships with a narration track
laid over it as `../TrustHUB-demo-vo.mp4`; see `../remotion/README.md`.

```
npm install
npm run capture     # drive the real UI, one PNG per beat + beats.json
npm run caption     # burn the narration onto each frame
npm run encode      # crossfade the frames into the MP4
npm run verify      # check every caption against the text its frame rendered
```

Both servers must be up first: backend on `:8000`, `npm run dev` in
`frontend/`. Nothing is mocked. `capture.mjs` fails on any console error, page
error or failed request and writes what it found to `beats.json`, so a broken
frame cannot quietly become part of the submission.

## Why it is built rather than screen-recorded

A screen recording shows whatever happened, including a spinner that had not
finished. Every frame here is a completed state, and `verify.py` asserts that
the caption sitting under each frame is true of the text that frame actually
rendered. Two captions were caught this way and rewritten: one described the
graph as "134 nodes, 126 links" while the screen said `47 nodes, 39 relations
shown`, and one described downtime as `434.0 h` when the UI rounds to `434 h`.

The second reason is that a recording is unrepeatable. This is.

## Why the captions are baked in

Judges watch muted. So the caption carries the argument, not a voice, and the
captions stay legible with the sound off no matter what happens to the audio.

No music either, for the same reason, plus the licensing question.

The video was built with no narration at all, on the grounds that a synthesised
voice reading technical prose is worse than silence. That judgement was made
without hearing one, so it was left as a test rather than a rule: `../vo/` renders
one line per beat with Windows SAPI, offline, and `../remotion/` lays them under
the video. Both are additions to the original, not replacements, so if the voice
turns out to flatten the argument then `../TrustHUB-demo.mp4` is still the file
to ship.

## The beat list is the argument

The order is deliberate. Six guardrails, then the pages. `verify.py` fails if a
figure in a caption is not on the frame it describes, and it also fails if any
frame contains `production data`, `real plant data`, `15 verified`, or
`spec v1.1` — the four ways this submission could quietly overclaim itself.

## Regenerating after a change

`beats.json` carries the rendered text of every frame, so `verify.py` runs with
no servers and no browser. Re-run `capture.mjs` only when the UI actually
changed; the dataset page alone costs 17 to 25 seconds because it walks the
dataset filesystem.

## Dependencies

`puppeteer-core`, not `puppeteer`, so no Chromium is downloaded. Point
`CHROME_PATH` at an existing Chrome or Chromium if yours is not in the default
Windows location. `python` must be on `PATH` for the three scripts.

This folder is a build tool, not part of the product, which is why it has its
own `package.json` and is not wired into `frontend/`: `npm ci` on a reviewer's
machine should not download a browser for a script they will never run.
