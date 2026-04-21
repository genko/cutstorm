import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { SAMPLE_5S } from "./_helpers";

/**
 * URL-import flow:
 *   1. Seed the backend with a real video via /api/transcribe (subs off, so no
 *      whisper runs). That gives us a video_id whose bytes exist on disk.
 *   2. Intercept /api/fetch-url and return the same TranscribeResponse.
 *   3. Drive the URL field + Import button in the UI.
 *   4. Editor should open with a live <video> served by /api/video/{id}.
 *
 * This proves the URL path enters the SAME post-upload flow as dropzone upload.
 */
test("URL import enters the editor with a playable preview", async ({ page, request }) => {
  const buf = readFileSync(SAMPLE_5S);
  const upload = await request.post("/api/transcribe", {
    multipart: {
      file: { name: "sample_5s.mp4", mimeType: "video/mp4", buffer: buf },
      language: "en",
      generate_subs: "false",
    },
  });
  expect(upload.ok()).toBeTruthy();
  const body = await upload.json();
  expect(body.video_id).toBeTruthy();

  await page.route("**/api/fetch-url*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });

  await page.goto("/");

  // Clear persisted state and reload so the Uploader (not the editor) renders.
  await page.evaluate(() => localStorage.clear());
  await page.reload();

  // Flip subs off — independent of whisper model, fast path.
  const toggle = page.getByTestId("generate-subs-toggle");
  if (await toggle.isChecked()) await toggle.click();

  await expect(page.getByTestId("url-input")).toBeVisible();
  await page.getByTestId("url-input").fill("https://example.com/fake-video");
  await page.getByTestId("url-import").click();

  await expect(page.getByTestId("preview-video")).toBeVisible({ timeout: 20_000 });
});
