import { test, expect } from "@playwright/test";
import { uploadEnglish } from "./_helpers";

test("Space toggles video playback", async ({ page }) => {
  await uploadEnglish(page);
  await expect(page.getByTestId("segment-0")).toBeVisible({ timeout: 120_000 });

  // Move focus away from any input so the global hotkey handler fires.
  await page.locator("body").click();

  const video = page.getByTestId("preview-video");
  await expect(video).toHaveJSProperty("paused", true);

  await page.keyboard.press("Space");
  await expect(video).toHaveJSProperty("paused", false);

  await page.keyboard.press("Space");
  await expect(video).toHaveJSProperty("paused", true);
});
