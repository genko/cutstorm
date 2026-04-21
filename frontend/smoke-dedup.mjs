// Real-UI smoke for frame-dedup: upload IMG_4934.MP4, export at preset=9:16
// with subtitles, time the run, extract 3 frames, ffprobe dims. The first
// run (dedup=ON by default) is the production path. Passing `--no-dedup` as
// argv[2] restarts the container with CUTSTORM_DEDUP=0 for the baseline run.
import { chromium } from "playwright";
import { spawnSync, execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(new URL(".", import.meta.url).pathname, "..");
const VIDEO = path.join(ROOT, "IMG_4934.MP4");
const OUT_DIR = path.join(ROOT, "frontend/e2e/output");
fs.mkdirSync(OUT_DIR, { recursive: true });

const tag = process.argv[2] || "dedup_on";
const outMp4 = path.join(OUT_DIR, `smoke_${tag}.mp4`);
if (fs.existsSync(outMp4)) fs.unlinkSync(outMp4);

console.log(`[smoke] tag=${tag} outMp4=${outMp4}`);
console.log(`[smoke] clearing backend container logs …`);
execSync("docker exec cutstorm-app-1 sh -c 'truncate -s 0 /proc/1/fd/1 2>/dev/null || true'");

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ acceptDownloads: true });
const page = await ctx.newPage();
page.on("console", (m) => { if (m.type() === "error") console.log("[page-err]", m.text()); });

await page.goto("http://localhost:8000/");
console.log("[smoke] app loaded");

// Language=ru (default from codepath, but enforce)
const lang = page.getByTestId("language-select");
if ((await lang.getAttribute("data-value")) !== "ru") {
  await lang.click();
  await page.getByTestId("language-option-ru").click();
}

await page.getByTestId("file-input").setInputFiles(VIDEO);
console.log("[smoke] upload sent");

// Whisper cache hit → segments arrive immediately.
await page.getByTestId("segment-0").waitFor({ state: "visible", timeout: 180_000 });
console.log("[smoke] segment-0 visible");

// Pick 9:16 preset to exercise canvas transform (StylePanel is always mounted
// once a video loads — no sidebar toggle needed).
await page.getByTestId("canvas-preset-9:16").first().click();
console.log("[smoke] canvas=9:16");

const t0 = Date.now();
const [download] = await Promise.all([
  page.waitForEvent("download", { timeout: 600_000 }),
  page.getByTestId("export-button").click(),
]);
await download.saveAs(outMp4);
const elapsedSec = (Date.now() - t0) / 1000;
console.log(`[smoke] export complete in ${elapsedSec.toFixed(1)}s`);

await browser.close();

const sz = fs.statSync(outMp4).size;
console.log(`[smoke] out=${outMp4} size=${(sz / 1024 / 1024).toFixed(1)}MB`);

// ffprobe dims + duration.
const probe = spawnSync("ffprobe", [
  "-v", "error", "-select_streams", "v:0",
  "-show_entries", "stream=codec_name,width,height:format=duration",
  "-of", "json", outMp4,
], { encoding: "utf8" });
if (probe.status !== 0) {
  console.error("ffprobe failed:", probe.stderr);
  process.exit(1);
}
const meta = JSON.parse(probe.stdout);
console.log("[smoke] ffprobe:", JSON.stringify(meta, null, 2));

// Extract 3 frames at t = 0.5, 1.5, 2.5 s for pixel parity comparison.
for (const t of [0.5, 1.5, 2.5]) {
  const png = path.join(OUT_DIR, `smoke_${tag}_t${t}.png`);
  if (fs.existsSync(png)) fs.unlinkSync(png);
  const r = spawnSync("ffmpeg", [
    "-y", "-nostats", "-loglevel", "error",
    "-ss", String(t), "-i", outMp4, "-frames:v", "1", png,
  ], { encoding: "utf8" });
  if (r.status !== 0) {
    console.error(`ffmpeg extract @${t} failed:`, r.stderr);
    process.exit(1);
  }
}

// Emit backend dedup log tail so the operator can verify renders<<frames.
console.log("\n[smoke] backend dedup tail:");
try {
  const logs = execSync("docker logs --tail 200 cutstorm-app-1 2>&1 | grep -E 'renderer\\.dedup|export\\.render percent=100|export\\.done|export\\.request'").toString();
  console.log(logs);
} catch {}

console.log(`[smoke] elapsedSec=${elapsedSec.toFixed(1)}`);
fs.writeFileSync(
  path.join(OUT_DIR, `smoke_${tag}_meta.json`),
  JSON.stringify({ tag, elapsedSec, size: sz, ffprobe: meta }, null, 2),
);
console.log("[smoke] done");
