import type { Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));

export const SAMPLE_5S = path.resolve(HERE, "fixtures/sample_5s.mp4");
export const SAMPLE_LONG = path.resolve(HERE, "fixtures/sample_long.mp4");

/**
 * Upload a fixture with language=en so whisper doesn't hallucinate on the
 * English TTS sample if the UI default ever drifts away from English.
 */
export async function uploadEnglish(page: Page, fixture: string = SAMPLE_5S) {
  await page.goto("/");
  const trigger = page.getByTestId("language-select");
  if ((await trigger.getAttribute("data-value")) !== "en") {
    await trigger.click();
    await page.getByTestId("language-option-en").click();
  }
  await page.getByTestId("file-input").setInputFiles(fixture);
}
