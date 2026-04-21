import { test, expect } from "@playwright/test";
import { uploadEnglish } from "./_helpers";

async function seekToFirstSegmentMid(page: import("@playwright/test").Page) {
  const start = await page.evaluate(() => {
    const el = document.querySelector<HTMLInputElement>('[data-testid="segment-0-start"]');
    return el ? Number(el.value) : 0;
  });
  const end = await page.evaluate(() => {
    const el = document.querySelector<HTMLInputElement>('[data-testid="segment-0-end"]');
    return el ? Number(el.value) : 1;
  });
  // seek slightly past the midpoint to avoid falling exactly on a word boundary
  const t = (start + end) / 2 + 0.05;
  await page.getByTestId("preview-video").evaluate((v, ct: number) => {
    (v as HTMLVideoElement).currentTime = ct;
  }, t);
}

test("word mode: overlay shows only a subset of the segment text", async ({ page }) => {
  await uploadEnglish(page);
  await expect(page.getByTestId("segment-0")).toBeVisible({ timeout: 120_000 });

  await page.getByTestId("segment-0-text").fill("one two three four five");

  await seekToFirstSegmentMid(page);

  await page.getByTestId("mode-word").click();
  await expect(page.getByTestId("subtitle-overlay")).toHaveAttribute("data-mode", "word");

  await page.getByTestId("style-words-per-chunk").fill("1");

  const rendered = (await page.getByTestId("subtitle-text").innerText()).trim();
  expect(rendered.length).toBeGreaterThan(0);
  expect(rendered.split(/\s+/).length).toBe(1);
  expect(["one", "two", "three", "four", "five"]).toContain(rendered);
});

test("phrase mode: overlay shows the whole segment text", async ({ page }) => {
  await uploadEnglish(page);
  await expect(page.getByTestId("segment-0")).toBeVisible({ timeout: 120_000 });

  await page.getByTestId("segment-0-text").fill("alpha beta gamma");

  await seekToFirstSegmentMid(page);

  await page.getByTestId("mode-phrase").click();
  await expect(page.getByTestId("subtitle-overlay")).toHaveAttribute("data-mode", "phrase");

  await expect(page.getByTestId("subtitle-text")).toHaveText("alpha beta gamma");
});

test("karaoke mode: shows full line with exactly one active word span", async ({ page }) => {
  await uploadEnglish(page);
  await expect(page.getByTestId("segment-0")).toBeVisible({ timeout: 120_000 });

  await page.getByTestId("segment-0-text").fill("red green blue yellow");

  await seekToFirstSegmentMid(page);

  await page.getByTestId("mode-karaoke").click();
  await expect(page.getByTestId("subtitle-overlay")).toHaveAttribute("data-mode", "karaoke");

  await expect(page.getByTestId("subtitle-text")).toContainText("red");
  await expect(page.getByTestId("subtitle-text")).toContainText("green");
  await expect(page.getByTestId("subtitle-text")).toContainText("blue");
  await expect(page.getByTestId("subtitle-text")).toContainText("yellow");

  const activeCount = await page
    .getByTestId("subtitle-text")
    .locator('span[data-active="1"]')
    .count();
  expect(activeCount).toBe(1);
});
