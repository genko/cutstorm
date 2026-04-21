import { test, expect } from "@playwright/test";
import { uploadEnglish } from "./_helpers";

test("preview renders subtitle text for playing time", async ({ page }) => {
  await uploadEnglish(page);
  await expect(page.getByTestId("segment-0")).toBeVisible({ timeout: 120_000 });

  const video = page.getByTestId("preview-video");
  await expect(video).toBeVisible();

  const firstSegStart = await page.evaluate(() => {
    const input = document.querySelector<HTMLInputElement>('[data-testid="segment-0-start"]');
    return input ? Number(input.value) : 0;
  });

  await video.evaluate((v, t: number) => {
    const vid = v as HTMLVideoElement;
    vid.currentTime = t + 0.1;
  }, firstSegStart);

  await expect(page.getByTestId("subtitle-text")).not.toHaveText("", { timeout: 5000 });
});
