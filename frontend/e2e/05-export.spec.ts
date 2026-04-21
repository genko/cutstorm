import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import { uploadEnglish } from "./_helpers";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.resolve(HERE, "output");

test("full flow upload → style → drag → export → download → ffprobe valid", async ({
  page,
}) => {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const outPath = path.join(OUT_DIR, "test_out.mp4");
  if (fs.existsSync(outPath)) fs.unlinkSync(outPath);

  await uploadEnglish(page);
  await expect(page.getByTestId("segment-0")).toBeVisible({ timeout: 120_000 });

  await page.getByTestId("style-font-size").fill("36");

  const overlay = page.getByTestId("subtitle-overlay");
  const box = await overlay.boundingBox();
  if (box) {
    const cx = box.x + box.width / 2;
    const cy = box.y + box.height / 2;
    await page.mouse.move(cx, cy);
    await page.mouse.down();
    await page.mouse.move(cx - 40, cy - 40, { steps: 5 });
    await page.mouse.up();
  }

  const [download] = await Promise.all([
    page.waitForEvent("download", { timeout: 120_000 }),
    page.getByTestId("export-button").click(),
  ]);
  await download.saveAs(outPath);

  expect(fs.existsSync(outPath)).toBe(true);
  expect(fs.statSync(outPath).size).toBeGreaterThan(0);

  const probe = spawnSync(
    "ffprobe",
    [
      "-v",
      "error",
      "-select_streams",
      "v:0",
      "-show_entries",
      "stream=codec_type,width,height:format=duration",
      "-of",
      "json",
      outPath,
    ],
    { encoding: "utf8" },
  );
  expect(probe.status).toBe(0);
  const info = JSON.parse(probe.stdout);
  expect(info.streams[0].codec_type).toBe("video");
  expect(info.streams[0].width).toBeGreaterThan(0);
  const dur = Number(info.format.duration);
  expect(dur).toBeGreaterThan(4.5);
  expect(dur).toBeLessThan(5.5);
});
