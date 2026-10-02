// Layout audit that does not rely on looking at the images.
// Checks: content/footer overlap, vertical collisions, bottom clearance,
// and reports the tightest slides so they can be fixed by hand.
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
      "  CHROME_PATH=/usr/bin/chromium npm run audit"
  );
  process.exit(2);
}

const html = "file:///" + path.join(ROOT, "deck.html").replace(/\\/g, "/");

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: "new",
  args: ["--no-sandbox"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 720 });
await page.goto(html, { waitUntil: "networkidle0" });

const report = await page.evaluate(() => {
  const out = [];

  document.querySelectorAll(".slide").forEach((slide, idx) => {
    const n = idx + 1;
    const sr = slide.getBoundingClientRect();
    const foot = slide.querySelector(".foot");
    const footTop = foot ? foot.getBoundingClientRect().top : sr.bottom;

    // Everything that is not the footer and not inside it.
    const body = [...slide.querySelectorAll("*")].filter((el) => {
      if (el.closest(".foot")) return false;
      if (el.classList.contains("kicker")) return false;
      const r = el.getBoundingClientRect();
      return r.width > 1 && r.height > 1;
    });

    let lowest = -Infinity;
    let lowestTag = "";
    let overlapsFoot = 0;
    let offRight = 0;

    for (const el of body) {
      const r = el.getBoundingClientRect();
      // Leaf-ish elements only, so a wrapper does not double count.
      const hasText = [...el.childNodes].some(
        (c) => c.nodeType === 3 && c.textContent.trim()
      );
      if (hasText || el.tagName === "TABLE" || el.classList.contains("flow")) {
        if (r.bottom > lowest) {
          lowest = r.bottom;
          lowestTag = el.tagName.toLowerCase() + "." + String(el.className).split(" ")[0];
        }
        if (r.bottom > footTop + 0.5) overlapsFoot++;
        if (r.right > sr.right + 0.5) offRight++;
      }
    }

    out.push({
      slide: n,
      contentBottom: Math.round(lowest - sr.top),
      footerTop: Math.round(footTop - sr.top),
      clearance: Math.round(footTop - lowest),
      overlapsFoot,
      offRight,
      lowestTag,
      hasFooter: !!foot,
    });
  });
  return out;
});

console.log("slide | content bottom | footer top | clearance | overlap | verdict");
for (const r of report) {
  const verdict =
    r.overlapsFoot > 0
      ? "OVERLAPS FOOTER"
      : r.clearance < 12
        ? "TIGHT"
        : "ok";
  console.log(
    `${String(r.slide).padStart(5)} | ${String(r.contentBottom).padStart(14)} | ${String(
      r.footerTop
    ).padStart(10)} | ${String(r.clearance).padStart(8)} | ${String(
      r.overlapsFoot
    ).padStart(6)} | ${verdict}  (${r.lowestTag})`
  );
}

const bad = report.filter((r) => r.overlapsFoot > 0);
const tight = report.filter((r) => r.clearance < 12);
console.log(`\n${bad.length} overlap(s), ${tight.length} tight, ${report.length} slides`);

await browser.close();