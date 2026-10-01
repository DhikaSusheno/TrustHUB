# Deck build

`../TrustHUB-CALIBER2026-Case1.pdf` is the submission deliverable. It is generated,
not hand-edited, so it can be regenerated after any change to the system or its
figures.

## The PDF is not committed, on purpose

`.gitignore` carries a blanket `*.pdf`, and it should. The official dataset
contains 87 PDFs under a committee licence, and a rule that says "no PDFs" cannot
accidentally commit one. Narrowing that rule to admit the deck would weaken the
only guard standing between the dataset and a public repository, in exchange for
convenience.

So `deck.html` is version-controlled and the PDF is a build output. Anyone can
regenerate it in one command, and the panel receives the file through the
submission itself.

## Regenerate

```bash
cd frontend
npm install --no-save puppeteer-core     # not in package.json; see below
node ../docs/deck/build/render.mjs
```

`render.mjs` writes the PDF and one PNG per slide into `../shots/`. It also runs
an overflow audit and fails loudly if any element leaves its slide box.

```bash
node ../docs/deck/build/audit.mjs
```

`audit.mjs` reports per-slide content height against the footer position, so a
slide that is about to collide is visible without opening the images.

## Why puppeteer-core is not a dependency

The deck is a build artifact, not part of the product. Adding a headless-browser
dependency to `frontend/package.json` would make every `npm ci` on the judging
panel's machine download Chromium, for a script they will never run. It is
installed with `--no-save` instead, which leaves `package.json` and the lockfile
untouched and keeps CI unaffected.

## Layout is verified mechanically, not by eye

The PDF is text, so it is searchable and copy-pasteable by the panel, and it is
323 KB rather than several megabytes of embedded images.

Slides are fixed 1280x720 px, which prints as exactly 960x540 pt, a 1.778 ratio.
The `@page` rule pins that so no renderer decides the page size.

## Source of the numbers

Every figure on a slide was read from the running API, not typed. The cross-check
that proves this is described in `../../../TRUSTHUB.md`; it re-extracts the PDF
text and asserts each claim against `GET /api/plant/*`, and it also asserts that
three forbidden phrasings are absent:

  - `15 verified groups`  - a claim that was never measured and is wrong
  - `production data`     - the dataset is labelled sample data by its authors
  - `real plant data`     - same reason

If the deck ever drifts from the system, that check fails instead of the drift
reaching a judge.