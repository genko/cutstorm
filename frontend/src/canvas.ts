/**
 * JS mirror of backend/app/canvas.py. Used by preview to compute target
 * dimensions + how the source video should be positioned in the frame.
 *
 * Backend is the source of truth for export. This JS version drives preview
 * only — it must agree with the backend on (targetW, targetH) to keep the
 * preview=export invariant intact.
 */

import type { CanvasConfig, CropAnchor } from "./store";

const PRESET_TARGETS: Record<string, [number, number]> = {
  "9:16": [1080, 1920],
  "16:9": [1920, 1080],
  "1:1": [1080, 1080],
  "4:5": [1080, 1350],
};

export type CropRect = { x: number; y: number; w: number; h: number };

export type ResolvedCanvas = {
  /** Canvas dimensions of the exported MP4 (also the preview-frame logical size). */
  targetW: number;
  targetH: number;
  /** How the source <video> element should render inside the canvas frame. */
  sourceFit: "cover" | "contain" | "fill" | "none";
  sourceObjectPosition: string; // CSS object-position value
  /**
   * When mode="custom": crop rectangle in PERCENTS of source. Preview shows
   * full source uncropped + CropEditor rect at these percents. When mode is
   * preset (or no crop), null.
   */
  customCropPct: CropRect | null;
};

function even(n: number, minVal = 0): number {
  return Math.max(minVal, Math.round(n / 2) * 2);
}

function anchorObjectPosition(anchor: CropAnchor, direction: "horizontal" | "vertical"): string {
  if (direction === "horizontal") {
    if (anchor === "left") return "left center";
    if (anchor === "right") return "right center";
    return "50% 50%";
  }
  if (anchor === "top") return "center top";
  if (anchor === "bottom") return "center bottom";
  return "50% 50%";
}

export function resolveCanvas(
  canvas: CanvasConfig,
  sourceW: number,
  sourceH: number,
  isAudioOnly: boolean,
): ResolvedCanvas {
  // Audio-only: no source; render at preset target always. No crop UI.
  if (isAudioOnly || sourceW <= 0 || sourceH <= 0) {
    const preset = canvas.preset === "source" ? "9:16" : canvas.preset;
    const [tw, th] = PRESET_TARGETS[preset] ?? [1080, 1920];
    return {
      targetW: tw,
      targetH: th,
      sourceFit: "none",
      sourceObjectPosition: "center",
      customCropPct: null,
    };
  }

  // Custom mode: preview renders full source, CropEditor overlays the crop rect.
  if (canvas.mode === "custom") {
    const c = canvas.custom;
    return {
      targetW: even(c.w_pct / 100 * sourceW, 2),
      targetH: even(c.h_pct / 100 * sourceH, 2),
      sourceFit: "fill",           // we render full source into the frame, no scaling
      sourceObjectPosition: "0 0",
      customCropPct: { x: c.x_pct, y: c.y_pct, w: c.w_pct, h: c.h_pct },
    };
  }

  // Preset mode.
  if (canvas.preset === "source") {
    return {
      targetW: even(sourceW, 2),
      targetH: even(sourceH, 2),
      sourceFit: "fill",
      sourceObjectPosition: "center",
      customCropPct: null,
    };
  }

  const [targetW, targetH] = PRESET_TARGETS[canvas.preset];
  const srcRatio = sourceW / sourceH;
  const tgtRatio = targetW / targetH;

  if (Math.abs(srcRatio - tgtRatio) < 1e-3) {
    return {
      targetW, targetH,
      sourceFit: "fill",
      sourceObjectPosition: "center",
      customCropPct: null,
    };
  }

  if (srcRatio > tgtRatio) {
    // Horizontal crop → object-fit: cover + anchor position.
    return {
      targetW, targetH,
      sourceFit: "cover",
      sourceObjectPosition: anchorObjectPosition(canvas.crop_anchor, "horizontal"),
      customCropPct: null,
    };
  }

  // Vertical pad → object-fit: contain.
  return {
    targetW, targetH,
    sourceFit: "contain",
    sourceObjectPosition: "50% 50%",
    customCropPct: null,
  };
}
