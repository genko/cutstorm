from __future__ import annotations

from typing import Iterable

from .models import Position, Segment, Size, Style, Word
from .sentence_chunks import chunks_by_sentence


def _hex_to_bgr(color: str) -> str:
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    r, g, b = c[0:2], c[2:4], c[4:6]
    return (b + g + r).upper()


def _ass_color(color: str, alpha: float = 1.0) -> str:
    a = max(0, min(255, int(round((1.0 - alpha) * 255))))
    return f"&H{a:02X}{_hex_to_bgr(color)}"


def _ass_color_inline(color: str) -> str:
    """Format for inline `\\1c` / `\\3c` overrides in dialogue text."""
    return f"&H{_hex_to_bgr(color)}&"


def _fmt_time(t: float) -> str:
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _escape_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", "\\N")
    )


def _alignment_code(a: str) -> int:
    return {"left": 7, "center": 8, "right": 9}.get(a, 8)


def _words_or_synth(seg: Segment) -> list[Word]:
    if seg.words:
        return seg.words
    toks = seg.text.strip().split()
    if not toks:
        return []
    total = max(seg.end - seg.start, 0.01)
    step = total / len(toks)
    return [
        Word(start=seg.start + i * step, end=seg.start + (i + 1) * step, text=t)
        for i, t in enumerate(toks)
    ]


def build(
    segments: Iterable[Segment],
    style: Style,
    position: Position,
    size: Size,
    video_w: int,
    video_h: int,
) -> str:
    segs = list(segments)
    mode = style.mode

    text_primary = _ass_color(style.text_color, 1.0)
    outline = _ass_color(style.outline_color, 1.0)
    back = _ass_color(style.bg_color, style.bg_opacity)

    # Karaoke is rendered via per-word `\t` color animations in the dialogue
    # text (matches the live preview where one word at a time flashes). The
    # base style is just the regular text color; we override per-word inline.
    primary = text_primary
    secondary = "&H000000FF"

    border_style = 3 if style.bg_opacity > 0.0 else 1

    style_line = (
        "Style: Default,"
        f"{style.font_family},"
        f"{style.font_size},"
        f"{primary},"
        f"{secondary},"
        f"{outline},"
        f"{back},"
        f"{-1 if style.bold else 0},"
        f"{-1 if style.italic else 0},"
        "0,0,100,100,0,0,"
        f"{border_style},"
        f"{style.outline_width},"
        f"{style.shadow_offset},"
        "7,0,0,0,1"
    )

    x_px = int(round(position.x_pct / 100.0 * video_w))
    y_px = int(round(position.y_pct / 100.0 * video_h))
    align_tag = _alignment_code(style.alignment)

    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        f"PlayResX: {video_w}",
        f"PlayResY: {video_h}",
        "YCbCr Matrix: None",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        style_line,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    fade = ""
    if style.fade_in_ms > 0 or style.fade_out_ms > 0:
        fade = f"\\fad({style.fade_in_ms},{style.fade_out_ms})"

    override_base = f"\\an{align_tag}\\pos({x_px},{y_px})\\q2{fade}"

    dialogues: list[str] = []

    if mode == "phrase":
        for seg in segs:
            start = _fmt_time(seg.start)
            end = _fmt_time(seg.end)
            text = _escape_text(seg.text)
            dialogues.append(
                f"Dialogue: 0,{start},{end},Default,,0,0,0,,{{{override_base}}}{text}"
            )

    elif mode == "word":
        chunk_size = max(1, style.words_per_chunk)
        for seg in segs:
            words = _words_or_synth(seg)
            if not words:
                continue
            for chunk in chunks_by_sentence(words, chunk_size):
                c_start = _fmt_time(chunk[0].start)
                c_end = _fmt_time(chunk[-1].end)
                chunk_text = _escape_text(" ".join(w.text.strip() for w in chunk))
                dialogues.append(
                    f"Dialogue: 0,{c_start},{c_end},Default,,0,0,0,,{{{override_base}}}{chunk_text}"
                )

    elif mode == "karaoke":
        # Break each segment into N-word chunks (rolling window). Each chunk
        # becomes one Dialogue showing those N words, with per-word \t color
        # animations flashing the currently-spoken word. Matches the live
        # HTML/CSS preview's chunked karaoke rendering.
        chunk_size = max(1, style.words_per_chunk)
        base_inline = _ass_color_inline(style.text_color)
        active_inline = _ass_color_inline(style.active_word_color)
        for seg in segs:
            words = _words_or_synth(seg)
            if not words:
                continue
            for chunk in chunks_by_sentence(words, chunk_size):
                chunk_start = chunk[0].start
                chunk_end = chunk[-1].end
                line_start = _fmt_time(chunk_start)
                line_end = _fmt_time(chunk_end)
                parts: list[str] = []
                for wi, w in enumerate(chunk):
                    # Times in centiseconds, relative to the CHUNK start.
                    s_cs = max(0, round((w.start - chunk_start) * 100))
                    e_cs = max(s_cs + 1, round((w.end - chunk_start) * 100))
                    txt = _escape_text(w.text.strip())
                    parts.append(
                        "{"
                        f"\\t({s_cs},{s_cs},\\1c{active_inline})"
                        f"\\t({e_cs},{e_cs},\\1c{base_inline})"
                        "}"
                    )
                    parts.append(txt)
                    if wi < len(chunk) - 1:
                        parts.append(" ")
                line_text = "".join(parts)
                override = f"\\an{align_tag}\\pos({x_px},{y_px})\\q2\\1c{base_inline}{fade}"
                dialogues.append(
                    f"Dialogue: 0,{line_start},{line_end},Default,,0,0,0,,{{{override}}}{line_text}"
                )

    return "\n".join(header + dialogues) + "\n"
