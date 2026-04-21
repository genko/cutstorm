import { test, expect } from "@playwright/test";
import { uploadEnglish } from "./_helpers";

test("undo restores previous font size", async ({ page }) => {
  await uploadEnglish(page);
  await expect(page.getByTestId("segment-0")).toBeVisible({ timeout: 120_000 });

  await page.getByTestId("style-font-size").fill("36");
  await page.getByTestId("style-font-size").blur();
  await expect(page.getByTestId("style-font-size")).toHaveValue("36");

  await page.getByTestId("style-font-size").fill("72");
  await page.getByTestId("style-font-size").blur();
  await expect(page.getByTestId("style-font-size")).toHaveValue("72");

  await page.evaluate(() => {
    const w = window as unknown as { useStore: { temporal: { getState: () => { undo: () => void } } } };
    w.useStore.temporal.getState().undo();
  });

  await expect(page.getByTestId("style-font-size")).toHaveValue("36");
});
