// Render a captioned copy of each captured frame.
//
// The video has no narration, because the alternative is a synthesised voice
// reading technical prose, which is worse than silence. Judges watch muted. So
// the caption is the narration, and it has to be there.
//
// Rendering it through the browser rather than ffmpeg drawtext keeps the text
// out of a filtergraph escaping problem: these captions contain commas,
// semicolons, colons and apostrophes, all of which drawtext treats as syntax.
//
//   npm run caption     (after npm run capture)

import puppeteer from "puppeteer-core";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(HERE, "..");
const DIR = path.join(OUT, "captioned");

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

fs.mkdirSync(DIR, { recursive: true });

const beatsPath = path.join(OUT, "beats.json");
if (!fs.existsSync(beatsPath)) {
  console.error("beats.json not found. Run `npm run capture` first.");
  process.exit(1);
}
const beats = JSON.parse(fs.readFileSync(beatsPath, "utf8")).beats;

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: "new",
  args: ["--no-sandbox"],
});
const page = await browser.newPage();
// 1920x1080 so the captions stay crisp when the encoder scales to 1280x720.
await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });

console.log(`rendering ${beats.length} captioned frames`);

for (const b of beats) {
  const src = path.join(OUT, b.frame);
  if (!fs.existsSync(src)) {
    console.error(`  missing frame ${src}`);
    process.exit(1);
  }
  const data =
    "data:image/png;base64," + fs.readFileSync(src).toString("base64");

  await page.setContent(
    `<!doctype html><html><head><meta charset="utf-8"><style>
       * { box-sizing: border-box; margin: 0; padding: 0; }
       html, body { background: #000; }
       .stage { position: relative; width: 1920px; height: 1080px; overflow: hidden; }
       img { display: block; width: 1920px; height: 1080px; }
       .cap {
         position: absolute; left: 0; right: 0; bottom: 0;
         padding: 26px 54px 34px;
         background: linear-gradient(to top,
                     rgba(8,12,20,.94) 0%, rgba(8,12,20,.86) 62%,
                     rgba(8,12,20,0) 100%);
       }
       .cap .t {
         font: 700 34px/1.25 "Segoe UI", Inter, Arial, sans-serif;
         color: #7dd3fc; letter-spacing: .04em; text-transform: uppercase;
         margin-bottom: 12px;
       }
       .cap .n {
         font: 400 40px/1.35 "Segoe UI", Inter, Arial, sans-serif;
         color: #f1f5f9; max-width: 1500px;
       }
     </style></head><body>
       <div class="stage">
         <img src="${data}">
         <div class="cap">
           <div class="t">TrustHUB &middot; CALIBER 2026 Case 1</div>
           <div class="n">${escapeHtml(b.note)}</div>
         </div>
       </div>
     </body></html>`,
    { waitUntil: "load" }
  );

  // Wait for the image to actually decode before the shutter.
  await page.waitForFunction(
    () => {
      const im = document.querySelector("img");
      return im && im.complete && im.naturalWidth > 0;
    },
    { timeout: 60000 }
  );

  const name = path.basename(b.frame);
  await page.screenshot({ path: path.join(DIR, name) });
  console.log(`  ${name}`);
}

await browser.close();
console.log(`\ndone -> ${DIR}`);

// The caption text is interpolated into HTML, so it is escaped rather than
// trusted, even though it currently comes from our own beats.json.
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
