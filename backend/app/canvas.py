from __future__ import annotations

from dataclasses import dataclass

from .models import Canvas, CropAnchor


PRESET_TARGETS: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1":  (1080, 1080),
    "4:5":  (1080, 1350),
}


@dataclass
class ResolvedCanvas:
    target_w: int
    target_h: int
    ffmpeg_filter: str  # before `ass=` / overlay; empty for no-op
    bg_color_hex: str


def _even(n: float, min_val: int = 0) -> int:
    """Round to nearest even int (libx264 requires even dims).

    `min_val=2` for widths/heights (avoid 0-size crops).
    `min_val=0` (default) for offsets (cx/cy can legitimately be 0).
    """
    i = int(round(n / 2.0) * 2)
    return max(min_val, i)


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def resolve(canvas: Canvas, source_w: int, source_h: int) -> ResolvedCanvas:
    if canvas.mode == "custom":
        return _resolve_custom(canvas, source_w, source_h)
    return _resolve_preset(canvas, source_w, source_h)


def _resolve_preset(canvas: Canvas, source_w: int, source_h: int) -> ResolvedCanvas:
    bg = canvas.bg_color

    if canvas.preset == "source":
        if source_w <= 0 or source_h <= 0:
            tw, th = PRESET_TARGETS["9:16"]
            return ResolvedCanvas(target_w=tw, target_h=th, ffmpeg_filter="", bg_color_hex=bg)
        return ResolvedCanvas(
            target_w=_even(source_w, 2), target_h=_even(source_h, 2),
            ffmpeg_filter="",
            bg_color_hex=bg,
        )

    target_w, target_h = PRESET_TARGETS[canvas.preset]

    # Audio-only (no source): renderer pipeline builds video from scratch.
    if source_w <= 0 or source_h <= 0:
        return ResolvedCanvas(
            target_w=target_w, target_h=target_h,
            ffmpeg_filter="",
            bg_color_hex=bg,
        )

    src_ratio = source_w / source_h
    tgt_ratio = target_w / target_h
    anchor: CropAnchor = canvas.crop_anchor

    if abs(src_ratio - tgt_ratio) < 1e-3:
        # Same aspect, possibly different resolution.
        if (source_w, source_h) == (target_w, target_h):
            return ResolvedCanvas(target_w, target_h, "", bg)
        return ResolvedCanvas(
            target_w=target_w, target_h=target_h,
            ffmpeg_filter=f"scale={target_w}:{target_h}",
            bg_color_hex=bg,
        )

    if src_ratio > tgt_ratio:
        # Source wider than target → crop horizontal (width).
        crop_h = _even(source_h, 2)
        crop_w = _even(source_h * target_w / target_h, 2)
        crop_w = _clamp(crop_w, 2, _even(source_w, 2))
        if anchor == "left":
            crop_x = 0
        elif anchor == "right":
            crop_x = _even(source_w - crop_w)
        else:  # center (or top/bottom fallback for horizontal crop)
            crop_x = _even((source_w - crop_w) / 2)
        crop_y = 0
        return ResolvedCanvas(
            target_w=target_w, target_h=target_h,
            ffmpeg_filter=f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={target_w}:{target_h}",
            bg_color_hex=bg,
        )

    # src_ratio < tgt_ratio: source narrower than target → pad (letterbox).
    scale_h = _even(target_h, 2)
    scale_w = _even(source_w * target_h / source_h, 2)
    scale_w = _clamp(scale_w, 2, _even(target_w, 2))
    pad_left = _even((target_w - scale_w) / 2)
    pad_top = 0
    ff_bg = _hex_to_ffmpeg_rgb(bg)
    return ResolvedCanvas(
        target_w=target_w, target_h=target_h,
        ffmpeg_filter=f"scale={scale_w}:{scale_h},pad={target_w}:{target_h}:{pad_left}:{pad_top}:{ff_bg}",
        bg_color_hex=bg,
    )


def _resolve_custom(canvas: Canvas, source_w: int, source_h: int) -> ResolvedCanvas:
    bg = canvas.bg_color
    if source_w <= 0 or source_h <= 0:
        # Custom crop requires a source.
        tw, th = PRESET_TARGETS["9:16"]
        return ResolvedCanvas(tw, th, "", bg)

    c = canvas.custom
    src_w_even = _even(source_w, 2)
    src_h_even = _even(source_h, 2)
    cw = _even(c.w_pct / 100.0 * source_w, 2)
    ch = _even(c.h_pct / 100.0 * source_h, 2)
    cx = _even(c.x_pct / 100.0 * source_w)
    cy = _even(c.y_pct / 100.0 * source_h)

    # Clamp to stay inside source after rounding.
    max_cw = src_w_even - cx
    max_ch = src_h_even - cy
    cw = _clamp(cw, 2, max(2, max_cw))
    ch = _clamp(ch, 2, max(2, max_ch))

    # No-op: full-frame custom crop = no filter.
    if cw >= src_w_even and ch >= src_h_even and cx == 0 and cy == 0:
        return ResolvedCanvas(
            target_w=src_w_even, target_h=src_h_even,
            ffmpeg_filter="",
            bg_color_hex=bg,
        )

    return ResolvedCanvas(
        target_w=cw, target_h=ch,
        ffmpeg_filter=f"crop={cw}:{ch}:{cx}:{cy}",
        bg_color_hex=bg,
    )


def _hex_to_ffmpeg_rgb(hex_color: str) -> str:
    c = hex_color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return f"0x{c.upper()}"


def hex_to_ffmpeg_color(hex_color: str) -> str:
    """Public alias kept for renderer.py compatibility."""
    return _hex_to_ffmpeg_rgb(hex_color)
