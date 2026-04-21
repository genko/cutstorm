import { test, expect } from "@playwright/test";
import { uploadEnglish } from "./_helpers";

test("upload produces at least one segment", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("uploader")).toBeVisible();

  await uploadEnglish(page);

  await expect(page.getByTestId("segments-list")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("segment-0")).toBeVisible();
});
