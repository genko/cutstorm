/**
 * Branded watermark overlay. Positioned in the bottom-right of whatever
 * parent it's rendered into. Intentionally uses a single PNG (served from
 * /watermark.png in public/) so the Playwright-based renderer captures it
 * into the overlay frame PNGs alongside the subtitles — no extra ffmpeg
 * filter needed on the renderer path.
 */
export function Watermark() {
  return (
    <img
      src="/watermark.png"
      alt="Cut/Storm"
      data-testid="watermark"
      style={{
        position: "absolute",
        right: "2%",
        bottom: "3%",
        width: "16%",
        minWidth: 80,
        maxWidth: 240,
        height: "auto",
        opacity: 0.85,
        pointerEvents: "none",
        userSelect: "none",
        filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.4))",
      }}
    />
  );
}
