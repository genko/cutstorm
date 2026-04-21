import { test, expect } from "@playwright/test";
import { uploadEnglish } from "./_helpers";

async function overlayData(page: import("@playwright/test").Page) {
  return page.evaluate(() => {
    const el = document.querySelector<HTMLElement>('[data-testid="subtitle-overlay"]')!;
    return {
      x: Number(el.dataset.x),
      y: Number(el.dataset.y),
      w: Number(el.dataset.w),
      h: Number(el.dataset.h),
    };
  });
}

test("drag moves overlay, resize changes size", async ({ page }) => {
  await uploadEnglish(page);
  await expect(page.getByTestId("segment-0")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("subtitle-overlay")).toBeVisible();

  const before = await overlayData(page);

  const overlay = page.getByTestId("subtitle-overlay");
  const box = await overlay.boundingBox();
  if (!box) throw new Error("no bbox");

  const startX = box.x + box.width / 2;
  const startY = box.y + box.height / 2;
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(startX - 120, startY - 80, { steps: 10 });
  await page.mouse.up();

  const afterDrag = await overlayData(page);
  expect(afterDrag.x).toBeLessThan(before.x);
  expect(afterDrag.y).toBeLessThan(before.y);

  const handle = page.getByTestId("overlay-handle-br");
  await handle.hover();
  const hbox = await handle.boundingBox();
  if (!hbox) throw new Error("no handle bbox");
  const hx = hbox.x + hbox.width / 2;
  const hy = hbox.y + hbox.height / 2;
  await page.mouse.move(hx, hy);
  await page.mouse.down();
  await page.mouse.move(hx + 30, hy + 20, { steps: 5 });
  await page.mouse.move(hx + 60, hy + 40, { steps: 5 });
  await page.mouse.up();

  const afterResize = await overlayData(page);
  expect(afterResize.w).toBeGreaterThan(afterDrag.w);
  expect(afterResize.h).toBeGreaterThan(afterDrag.h);
});
