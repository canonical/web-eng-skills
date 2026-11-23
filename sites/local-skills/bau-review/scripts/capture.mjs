#!/usr/bin/env node
// Capture a page for review: screenshots at desktop/tablet/mobile, the rendered
// HTML, and axe-core accessibility violations.
//
// Usage: node capture.mjs <out-dir> <url> [--selector "#main-content"]
//
// Writes to <out-dir>: desktop.png, tablet.png, mobile.png, rendered.html, axe.json
// Install dependencies once with `npm install` in this directory. If no browser
// is found, run `npx playwright install chromium`.

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { chromium } from "playwright";

const args = process.argv.slice(2);
const selIdx = args.indexOf("--selector");
const selector = selIdx >= 0 ? args.splice(selIdx, 2)[1] : "#main-content";
const [outDir, url] = args;
if (!outDir || !url) {
  console.error("Usage: node capture.mjs <out-dir> <url> [--selector <css>]");
  process.exit(2);
}
fs.mkdirSync(outDir, { recursive: true });

// Prefer an installed Chrome; fall back to Playwright's bundled Chromium.
const systemChrome = [
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
  "/snap/bin/chromium",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].find((p) => fs.existsSync(p));

let browser;
try {
  browser = await chromium.launch(systemChrome ? { executablePath: systemChrome } : {});
} catch (e) {
  console.error(`Could not launch a browser: ${e.message}\nRun: npx playwright install chromium`);
  process.exit(1);
}

// Things that get in the way of clean full-page screenshots on Canonical sites:
// the cookie notice, the nav search overlay (a fixed full-viewport layer) and
// sticky headers (which repeat down a full-page capture).
const HIDE_CSS = `
  .cookie-policy, dialog.cookie-policy, .cookie-notification-modal,
  #cookie-policy-preferences, .p-navigation__search-overlay { display: none !important; }
  .l-sticky-header, .p-navigation.is-sticky { position: static !important; }
  body { overflow: auto !important; }`;

const summary = { url, selector, screenshots: [], axeViolations: null };

for (const [name, width] of [["desktop", 1440], ["tablet", 768], ["mobile", 375]]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  const res = await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
  if (name === "desktop") summary.status = res?.status();

  const accept = page
    .locator('#cookie-policy-button-accept-all, .cookie-policy .js-close-all, button:has-text("Accept all")')
    .first();
  if (await accept.isVisible().catch(() => false)) {
    await accept.click();
    await page.waitForTimeout(500);
  }
  await page.addStyleTag({ content: HIDE_CSS });

  // Scroll slowly so lazy-loaded images load, then wait for them.
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 400) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 250));
    }
    window.scrollTo(0, 0);
  });
  await page.evaluate(async () => {
    await Promise.all(
      [...document.images].map((i) =>
        i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; setTimeout(r, 5000); }),
      ),
    );
  });
  await page.waitForTimeout(500);

  const file = path.join(outDir, `${name}.png`);
  const region = await page.$(selector);
  if (region) await region.screenshot({ path: file });
  else await page.screenshot({ path: file, fullPage: true });
  summary.screenshots.push(file);

  if (name === "desktop") {
    fs.writeFileSync(path.join(outDir, "rendered.html"), await page.content());
    const axePath = createRequire(import.meta.url).resolve("axe-core/axe.min.js");
    await page.addScriptTag({ content: fs.readFileSync(axePath, "utf8") });
    const violations = await page.evaluate(async (sel) => {
      const r = await window.axe.run(document.querySelector(sel) || document, {
        runOnly: ["wcag2a", "wcag2aa", "wcag21aa", "best-practice"],
      });
      return r.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        help: v.help,
        nodes: v.nodes.map((n) => ({
          target: n.target.join(" "),
          html: n.html.slice(0, 200),
          summary: n.failureSummary.slice(0, 300),
        })),
      }));
    }, selector);
    fs.writeFileSync(path.join(outDir, "axe.json"), JSON.stringify(violations, null, 1));
    summary.axeViolations = violations.length;
  }
  await page.close();
}
await browser.close();

// Plain-text summary for agents that can't view images.
console.log(JSON.stringify(summary, null, 1));
