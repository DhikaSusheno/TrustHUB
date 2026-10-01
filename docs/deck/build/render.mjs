// Render deck.html to PDF and screenshot every slide so layout can be checked.
// Run from frontend\ so node_modules resolves puppeteer-core.
import puppeteer from "puppeteer-core";
import path from "node:path";
import fs from "node:fs";

const CHROME =
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const ROOT = "C:\\Users\\dhika\\TrustHUB\\docs\\deck";
const html = "file:///" + path.join(ROOT, "deck.html").replace(/\\/g, "/");
const pdf = path.join(ROOT, "TrustHUB-CALIBER2026-Case1.pdf");
const shotDir = path.join(ROOT, "shots");

fs.mkdirSync(shotDir, { recursive: true });

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