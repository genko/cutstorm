import { test, expect } from "@playwright/test";
import { uploadEnglish, SAMPLE_LONG } from "./_helpers";

test("progress bar advances during export encoding", async ({ page }) => {
  const encodeFrames: Array<{ percent: number }> = [];
  page.on("websocket", (ws) => {
    if (!ws.url().includes("/ws/progress/")) return;
    ws.on("framereceived", ({ payload }) => {
      if (typeof payload !== "string") return;
      try {
        const msg = JSON.parse(payload);
        if (msg && msg.phase === "encode" && typeof msg.percent === "number") {
          encodeFrames.push({ percent: msg.percent });
        }
      } catch {
        /* ignore */
      }
    });
  });

  await uploadEnglish(page, SAMPLE_LONG);
  await expect(page.getByTestId("segment-0")).toBeVisible({ timeout: 120_000 });

  await page.getByTestId("export-button").click();
  try {
    await page.waitForEvent("download", { timeout: 120_000 });
  } catch {
    /* ignore — we assert on frames */
  }

  const distinct = new Set(encodeFrames.map((f) => f.percent));
  expect(distinct.size).toBeGreaterThanOrEqual(2);
  expect(Math.max(...distinct, 0)).toBeGreaterThan(0);
});
