// Real-UI smokes for stream-copy + filter-only fast paths.
// Runs three scenarios (case A, case B, case C) through the actual UI and
// records timing + ffprobe dims + backend log line identifying which path
// the dispatcher took. Pass the scenario as argv[2]: "A" | "B" | "C".
import { chromium } from "playwright";
import { spawnSync, execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(new URL(".", import.meta.url).pathname, "..");
const VIDEO = path.join(ROOT, "IMG_4934.MP4");
const OUT_DIR = path.join(ROOT, "frontend/e2e/output");
fs.mkdirSync(OUT_DIR, { recursive: true });

const scenario = process.argv[2] || "A";
const outMp4 = path.join(OUT_DIR, `smoke_case_${scenario}.mp4`);
if (fs.existsSync(outMp4)) fs.unlinkSync(outMp4);

console.log(`[fastpath] case=${scenario} outMp4=${outMp4}`);
execSync("docker exec cutstorm-app-1 sh -c 'truncate -s 0 /proc/1/fd/1 2>/dev/null || true'");

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ acceptDownloads: true });
const page = await ctx.newPage();
page.on("console", (m) => { if (m.type() === "error") console.log("[page-err]", m.text()); });

await page.goto("http://localhost:8000/");
const lang = page.getByTestId("language-select");
if ((await lang.getAttribute("data-value")) !== "ru") {
  await lang.click();
  await page.getByTestId("language-option-ru").click();
}
await page.getByTestId("file-input").setInputFiles(VIDEO);
console.log("[fastpath] upload sent");

// Wait until the editor is ready (StylePanel visible) — NOT for segments.
await page.getByTestId("style-panel").waitFor({ state: "visible", timeout: 180_000 });
console.log("[fastpath] editor visible");

async function setSubs(on) {
  const cb = page.getByTestId("use-subs-toggle");
  const checked = await cb.isChecked();
  if (checked !== on) await cb.click();
}
async function setPresetSource() {
  // Reset to source preset — the only one of the preset buttons whose
  // testid we know persists in both video and audio panes.
  const srcBtn = page.getByTestId("canvas-preset-source").first();
  if (await srcBtn.isVisible()) await srcBtn.click();
}

if (scenario === "A") {
  // No subs, preset=source.
  await setSubs(false);
  await setPresetSource();
  console.log("[fastpath] A: useSubs=off, canvas=source");
} else if (scenario === "B") {
  // No subs, canvas=9:16 → filter-only
  await setSubs(false);
  await page.getByTestId("canvas-preset-9:16").first().click();
  console.log("[fastpath] B: useSubs=off, canvas=9:16");
} else if (scenario === "C") {
  // Subs on, canvas=9:16 → renderer (with dedup)
  await setSubs(true);
  await page.getByTestId("segment-0").waitFor({ state: "visible", timeout: 180_000 });
  await page.getByTestId("canvas-preset-9:16").first().click();
  console.log("[fastpath] C: useSubs=on, canvas=9:16");
}

const t0 = Date.now();
const [download] = await Promise.all([
  page.waitForEvent("download", { timeout: 600_000 }),
  page.getByTestId("export-button").click(),
]);
await download.saveAs(outMp4);
const elapsedSec = (Date.now() - t0) / 1000;
console.log(`[fastpath] export complete in ${elapsedSec.toFixed(2)}s`);

await browser.close();

// ffprobe.
const probe = spawnSync("ffprobe", [
  "-v", "error", "-select_streams", "v:0",
  "-show_entries", "stream=codec_name,width,height:format=duration",
  "-of", "json", outMp4,
], { encoding: "utf8" });
const meta = JSON.parse(probe.stdout);
console.log("[fastpath] ffprobe:", JSON.stringify(meta, null, 2));

// Backend log — show which dispatcher path was taken.
console.log("\n[fastpath] dispatcher log:");
const logs = execSync(
  "docker logs --tail 200 cutstorm-app-1 2>&1 | grep -E 'export\\.path|renderer\\.dedup|export\\.done|simple_export'"
).toString();
console.log(logs);

fs.writeFileSync(
  path.join(OUT_DIR, `smoke_case_${scenario}_meta.json`),
  JSON.stringify({ scenario, elapsedSec, ffprobe: meta }, null, 2),
);
console.log(`[fastpath] done case=${scenario} elapsedSec=${elapsedSec.toFixed(2)}`);
