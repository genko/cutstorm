import { test, expect } from "@playwright/test";
import { uploadEnglish } from "./_helpers";

test("changing style updates overlay computed styles", async ({ page }) => {
  await uploadEnglish(page);
  await expect(page.getByTestId("segment-0")).toBeVisible({ timeout: 120_000 });

  // Switch to phrase mode so the overlay renders the full text directly on
  // the subtitle-text div (color/size assertions target that node).
  await page.getByTestId("mode-phrase").click();

  const video = page.getByTestId("preview-video");
  const firstSegStart = await page.evaluate(() => {
    const el = document.querySelector<HTMLInputElement>('[data-testid="segment-0-start"]');
    return el ? Number(el.value) : 0;
  });
  await video.evaluate((v, t: number) => {
    (v as HTMLVideoElement).currentTime = t + 0.1;
  }, firstSegStart);

  const subtitle = page.getByTestId("subtitle-text");
  await expect(subtitle).not.toHaveText("");

  await page.getByTestId("style-font-size").fill("72");
  await page.getByTestId("style-text-color").evaluate((el) => {
    const input = el as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )!.set!;
    setter.call(input, "#ff0000");
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });

  await expect(subtitle).toHaveCSS("font-size", "72px");
  await expect(subtitle).toHaveCSS("color", "rgb(255, 0, 0)");
});
