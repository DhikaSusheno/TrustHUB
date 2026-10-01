// Capture the demo video frames from the running app.
//
// Drives the real UI against the real dataset. Nothing here is mocked: every
// frame is the product as a judge would see it, which is the only kind of
// screenshot worth putting in a submission.
//
// Requires both servers up:
//
//   cd backend  && python -m uvicorn main:app --port 8000
//   cd frontend && npm run dev
//
// Then, from this directory:
//
//   npm install && npm run capture && npm run caption && npm run encode
//
// Output: ../frames/NN-<slug>.png, ../captioned/NN-<slug>.png, and
// ../beats.json, which records how long each beat is held and what it is meant
// to show. encode.py turns those into the MP4; verify.py checks that each
// caption is true of the frame it sits under.

import puppeteer from "puppeteer-core";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(HERE, "..");
const FRAMES = path.join(OUT, "frames");

// Override on a machine that keeps Chrome elsewhere: CHROME_PATH=/path/to/chrome
const CHROME =
  process.env.CHROME_PATH ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

if (!fs.existsSync(CHROME)) {
  console.error(
    `chrome not found at ${CHROME}\n` +
      `set CHROME_PATH to your Chrome or Chromium binary and re-run`
  );
  process.exit(1);
}

const APP = process.env.TRUSTHUB_APP_URL || "http://localhost:3000";

fs.mkdirSync(FRAMES, { recursive: true });

// Seconds each frame is held. The answer beats are longer because a judge is
// reading them, not just looking at them.
const beats = [];
let n = 0;

async function shot(page, slug, seconds, note) {
  n += 1;
  const file = `frames/${String(n).padStart(2, "0")}-${slug}.png`;
  await page.screenshot({ path: path.join(OUT, file) });
  // The visible text is recorded alongside the image. It is what the frame
  // actually says, so the claims in the video can be checked against it rather
  // than against a screenshot nobody can grep.
  const text = await page.evaluate(() => document.body.innerText);
  beats.push({ frame: file, seconds, note, text: text.replace(/\n{2,}/g, "\n") });
  console.log(
    `  ${String(n).padStart(2, "0")}  ${slug.padEnd(22)} ${seconds}s  ${note}`
  );
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: "new",
  args: ["--no-sandbox", "--force-device-scale-factor=1"],
});

const page = await browser.newPage();
await page.setViewport({ width: 1600, height: 900, deviceScaleFactor: 1 });

// Record failures rather than record an error page as if it were the product.
const problems = [];
page.on("console", (m) => {
  if (m.type() === "error") problems.push(`console: ${m.text()}`);
});
page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
page.on("requestfailed", (r) =>
  problems.push(`requestfailed: ${r.url()} ${r.failure()?.errorText}`)
);

async function open(url, waitText) {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 120000 });
  // Deliberately not waitForNetworkIdle: the backend-status banner polls, so
  // the network never goes idle and that wait would always time out. Readiness
  // is a question about the DOM instead.
  //
  // The needle is matched case-insensitively because innerText reflects CSS
  // text-transform, and several headings are uppercased by the stylesheet.
  if (waitText) {
    await page.waitForFunction(
      (t) => document.body.innerText.toLowerCase().includes(t.toLowerCase()),
      { timeout: 120000 },
      waitText
    );
  }
  // Let data-driven rendering and transitions settle before the shutter.
  await new Promise((r) => setTimeout(r, 2200));
}

// Click one of the six example chips by its visible label. Those six exist
// precisely because each one exercises a different guardrail.
async function askExample(label) {
  const clicked = await page.evaluate((want) => {
    const hit = [...document.querySelectorAll("button")].find((b) => {
      const first = b.querySelector("span");
      return first && first.textContent.trim() === want;
    });
    if (!hit) return false;
    hit.click();
    return true;
  }, label);
  if (!clicked) throw new Error(`example chip not found: ${label}`);
  // The chip grid is replaced once a result exists, so its disappearance is the
  // signal that the answer has arrived.
  await page.waitForFunction(
    () => !document.body.innerText.toLowerCase().includes("try one of these"),
    { timeout: 120000 }
  );
  await new Promise((r) => setTimeout(r, 2200));
}

async function clearAnswer() {
  await page.evaluate(() => {
    const b = [...document.querySelectorAll("button")].find((x) =>
      x.textContent.includes("Clear and pick another question")
    );
    if (b) b.click();
  });
  await page.waitForFunction(
    () => document.body.innerText.toLowerCase().includes("try one of these"),
    { timeout: 60000 }
  );
  await new Promise((r) => setTimeout(r, 500));
}

console.log(`capturing demo frames from ${APP}`);

// ---------------------------------------------------------------- 1. landing
await open(`${APP}/landing`, "TrustHUB");
await shot(page, "landing", 7, "What the system is, before any data");

// -------------------------------------------------------------- 2. overview
// The trust model is published here, not on the Verification page.
await open(`${APP}/?page=overview`, "TrustHUB");
await shot(
  page,
  "overview",
  8,
  "System state: 95 documents, 211 work orders, 8 units. And the trust model itself - five weights, three thresholds, published"
);

// ------------------------------------------------------------ 3. ask, empty
await open(`${APP}/?page=ask`, "Try one of these");
await shot(
  page,
  "ask-idle",
  6,
  "Six questions, each exercising a different guardrail"
);

// --------------------------------------------------- 4. the answered case
await askExample("Measured setpoint");
await shot(
  page,
  "ask-answered",
  11,
  "7.1 mm/s with six citing documents, VERIFY. The value is read, not generated"
);

// -------------------------------------------------- 5. missing document
await clearAnswer();
await askExample("Missing document");
await shot(
  page,
  "ask-missing-doc",
  10,
  "That one-point lesson is not in the dataset. It refuses instead of guessing"
);

// ------------------------------------------------------- 6. out of scope
await clearAnswer();
await askExample("Out of scope");
await shot(
  page,
  "ask-out-of-scope",
  9,
  "Refused, and it says why. A deliberate refusal, not a failure"
);

// ------------------------------------------------------ 7. safety bypass
await clearAnswer();
await askExample("Safety-critical");
await shot(
  page,
  "ask-safety",
  12,
  "Asking to bypass a trip. DO NOT EXECUTE, whatever the score says"
);

console.log("  -- pages --");

// ------------------------------------------------------------ 8. equipment
await open(`${APP}/?page=equipment`, "GA-1201A");
await shot(
  page,
  "equipment",
  8,
  "Eight units; GA-1201A has the most documents"
);

// ----------------------------------------------------------------- 9. graph
await open(`${APP}/?page=graph`, "TrustHUB");
await shot(
  page,
  "graph",
  9,
  "134 nodes in the data. The ring draws the 47 non-document ones; the 87 documents are the relation counts beside it"
);

// -------------------------------------------------------- 10. verification
await open(`${APP}/?page=verification`, "TrustHUB");
// The page runs all 63 locked cases on open, so it is briefly empty.
await page.waitForFunction(() => /63 of 63/i.test(document.body.innerText), {
  timeout: 180000,
});
await new Promise((r) => setTimeout(r, 1500));
await shot(
  page,
  "verification",
  12,
  "The locked set runs live on page open, so this 63 of 63 cannot drift from the number in the deck. Plus the 7 cross-confirmed groups, and what the measurement does not prove"
);

// --------------------------------------------------------- 11. maintenance
await open(`${APP}/?page=maintenance`, "TrustHUB");
await shot(
  page,
  "maintenance",
  9,
  "Failure Memory: 31 breakdowns, 434 h, and the 12 breakdowns nobody has written a lesson for"
);

// --------------------------------------------------------------- 12. audit
await open(`${APP}/?page=audit`, "TrustHUB");
await shot(page, "audit", 7, "Provenance for every answer, not just the good ones");

// ------------------------------------------------------------ 13. documents
await open(`${APP}/?page=documents`, "TrustHUB");
await shot(
  page,
  "documents",
  6,
  "Revision and approval read from the documents themselves"
);

// --------------------------------------------------------------- 14. dataset
// This page walks the dataset filesystem, so it is genuinely slow, 17 to 25
// seconds. It is where the licence note and the honest "this is sample data"
// framing live. The accuracy number is not here: that is the Verification page,
// which runs the locked set on demand so the UI figure cannot drift from the
// CLI figure.
await open(`${APP}/?page=dataset`, "TrustHUB");
await page.waitForFunction(
  () => /one-point lessons/i.test(document.body.innerText),
  { timeout: 180000 }
);
await new Promise((r) => setTimeout(r, 2000));
await shot(
  page,
  "dataset",
  11,
  "Where the data came from, and the committee licence note on every document"
);

fs.writeFileSync(
  path.join(OUT, "beats.json"),
  JSON.stringify({ beats, problems }, null, 2) + "\n",
  "utf8"
);

await browser.close();

console.log(`\n${beats.length} frames -> ${FRAMES}`);
console.log(`problems during capture: ${problems.length}`);
for (const p of problems.slice(0, 12)) console.log(`  ${p}`);
if (problems.length === 0) console.log("  (none: clean capture)");
