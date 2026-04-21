import { test, expect } from "@playwright/test";
import { uploadEnglish } from "./_helpers";

test("edit segment text propagates to overlay", async ({ page }) => {
  await uploadEnglish(page);
  await expect(page.getByTestId("segment-0")).toBeVisible({ timeout: 120_000 });

  await page.getByTestId("mode-phrase").click();

  const startInput = page.getByTestId("segment-0-start");
  const endInput = page.getByTestId("segment-0-end");
  const startVal = Number(await startInput.inputValue());
  const endVal = Number(await endInput.inputValue());
  const mid = (startVal + endVal) / 2;

  const NEW_TEXT = "CUSTOM_SUBTITLE_XYZ";
  await page.getByTestId("segment-0-text").fill(NEW_TEXT);

  await page.getByTestId("preview-video").evaluate((v, t: number) => {
    (v as HTMLVideoElement).currentTime = t;
  }, mid);

  await expect(page.getByTestId("subtitle-text")).toHaveText(NEW_TEXT);
});

test("delete removes segment from list", async ({ page }) => {
  await uploadEnglish(page);
  await expect(page.getByTestId("segment-0")).toBeVisible({ timeout: 120_000 });

  const rowsBefore = await page.getByTestId(/^segment-\d+$/).count();
  await page.getByTestId("segment-0-delete").click();
  const rowsAfter = await page.getByTestId(/^segment-\d+$/).count();
  expect(rowsAfter).toBe(rowsBefore - 1);
});
