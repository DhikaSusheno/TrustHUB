// Render deck.html to PDF and screenshot every slide so layout can be checked.
// Run `npm ci` in this directory first; node resolves puppeteer-core from the
// node_modules next to this file, not from your shell's working directory.
import puppeteer from "puppeteer-core";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

// Resolved from this script's own location so a checkout in any directory works.
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
].filter(Boolean);
const CHROME = CHROME_CANDIDATES.find((p) => fs.existsSync(p));
if (!CHROME) {
  console.error(
    "no Chrome/Chromium found. Set CHROME_PATH to the executable, e.g.\n" +
      "  CHROME_PATH=/usr/bin/chromium npm run render"
  );
  process.exit(2);
}

const html = "file:///" + path.join(ROOT, "deck.html").replace(/\\/g, "/");
const pdf = path.join(ROOT, "TrustHUB-CALIBER2026-Case1.pdf");
const shotDir = path.join(ROOT, "shots");

fs.mkdirSync(shotDir, { recursive: true });
// Clear stale shots first. The deck used to be 15 slides and is now 13, so
// slide-14.png and slide-15.png survived the rewrite. Leaving them in place
// makes the folder claim a longer deck than the PDF actually has, which is
// the same class of drift the audit exists to catch.
for (const f of fs.readdirSync(shotDir)) {
  if (f.endsWith(".png")) fs.unlinkSync(path.join(shotDir, f));
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: "new",
  args: ["--no-sandbox", "--font-render-hinting=none"],
});

const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 720, deviceScaleFactor: 1 });
await page.goto(html, { waitUntil: "networkidle0" });

const slides = await page.$$(".slide");
console.log("slides found:", slides.length);

// Overflow audit: any element sticking outside its slide box.
const overflow = await page.evaluate(() => {
  const bad = [];
  document.querySelectorAll(".slide").forEach((slide, i) => {
    const sb = slide.getBoundingClientRect();
    slide.querySelectorAll("*").forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return;
      if (
        r.right > sb.right + 1 ||
        r.bottom > sb.bottom + 1 ||
        r.left < sb.left - 1
      ) {
        bad.push({
          slide: i + 1,
          tag: el.tagName.toLowerCase(),
          cls: el.className && String(el.className).slice(0, 40),
          text: (el.textContent || "").trim().slice(0, 52),
          overRight: Math.round(r.right - sb.right),
          overBottom: Math.round(r.bottom - sb.bottom),
        });
      }
    });
  });
  return bad;
});

if (overflow.length === 0) {
  console.log("OVERFLOW: none");
} else {
  console.log("OVERFLOW: " + overflow.length + " element(s)");
  for (const o of overflow.slice(0, 25)) {
    console.log(
      `  slide ${o.slide}  <${o.tag} class="${o.cls}">  right+${o.overRight} bottom+${o.overBottom}  "${o.text}"`
    );
  }
}

for (let i = 0; i < slides.length; i++) {
  await slides[i].screenshot({
    path: path.join(shotDir, `slide-${String(i + 1).padStart(2, "0")}.png`),
  });
}
console.log("screenshots:", slides.length);

await page.pdf({
  path: pdf,
  width: "1280px",
  height: "720px",
  printBackground: true,
  preferCSSPageSize: true,
});

await browser.close();

const kb = (fs.statSync(pdf).size / 1024).toFixed(0);
console.log(`pdf: ${pdf}  (${kb} KB)`);