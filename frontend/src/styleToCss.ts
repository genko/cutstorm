import type { CSSProperties } from "react";
import type { Style } from "./store";

export function styleToCss(style: Style): CSSProperties {
  const justify =
    style.alignment === "left"
      ? "flex-start"
      : style.alignment === "right"
        ? "flex-end"
        : "center";

  const textAlign = style.alignment;

  const textShadow: string[] = [];
  if (style.outline_width > 0) {
    const w = style.outline_width;
    for (let dx = -w; dx <= w; dx++) {
      for (let dy = -w; dy <= w; dy++) {
        if (dx === 0 && dy === 0) continue;
        textShadow.push(`${dx}px ${dy}px 0 ${style.outline_color}`);
      }
    }
  }
  if (style.shadow_offset > 0) {
    textShadow.push(
      `${style.shadow_offset}px ${style.shadow_offset}px ${style.shadow_offset}px ${style.shadow_color}`,
    );
  }

  const bg =
    style.bg_opacity > 0
      ? `${hexToRgba(style.bg_color, style.bg_opacity)}`
      : "transparent";

  return {
    fontFamily: style.font_family,
    fontSize: `${style.font_size}px`,
    fontWeight: style.bold ? 700 : 400,
    fontStyle: style.italic ? "italic" : "normal",
    textTransform: style.uppercase ? "uppercase" : "none",
    color: style.text_color,
    textShadow: textShadow.length ? textShadow.join(", ") : "none",
    background: bg,
    padding: `${style.bg_padding}px`,
    borderRadius: `${style.bg_radius}px`,
    textAlign,
    justifyContent: justify,
    lineHeight: 1.15,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  };
}

function hexToRgba(hex: string, a: number): string {
  const c = hex.replace("#", "");
  const full = c.length === 3 ? c.split("").map((ch) => ch + ch).join("") : c;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
}
