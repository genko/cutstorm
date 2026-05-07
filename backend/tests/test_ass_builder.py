from __future__ import annotations

import re

from app import ass_builder
from app.models import Position, Segment, Size, Style, Word


def _seg(start, end, text, words=None):
    return Segment(start=start, end=end, text=text, words=words or [])


def test_ass_has_required_sections() -> None:
    segs = [_seg(0.0, 1.0, "hello world")]
    text = ass_builder.build(
        segs,
        Style(),
        Position(x_pct=50, y_pct=80),
        Size(),
        video_w=1920,
        video_h=1080,
    )
    assert "[Script Info]" in text
    assert "PlayResX: 1920" in text
    assert "PlayResY: 1080" in text
    assert "[V4+ Styles]" in text
    assert "[Events]" in text
    assert "Style: Default," in text


def test_ass_pos_and_style() -> None:
    segs = [_seg(0.0, 1.25, "abc")]
    style = Style(
        font_family="DejaVu Sans",
        font_size=36,
        text_color="#FF0000",
        outline_color="#000000",
        outline_width=3,
    )
    text = ass_builder.build(segs, style, Position(x_pct=10, y_pct=90), Size(), 1000, 500)
    assert re.search(r"DejaVu Sans", text)
    assert re.search(r",36,", text)
    assert re.search(r"&H000000FF", text)
    assert re.search(r",3,\d+,7,0,0,0,1", text)
    assert "\\pos(100,450)" in text


def test_ass_escapes_text() -> None:
    segs = [_seg(0.0, 1.0, "a {b} c\nd")]
    text = ass_builder.build(segs, Style(), Position(), Size(), 640, 480)
    assert "a \\{b\\} c\\Nd" in text


def test_ass_timing_format() -> None:
    segs = [_seg(0.0, 65.5, "x")]
    text = ass_builder.build(segs, Style(), Position(), Size(), 640, 480)
    assert "0:00:00.00" in text
    assert "0:01:05.50" in text


def test_ass_bg_box_uses_border_style_3() -> None:
    segs = [_seg(0.0, 1.0, "x")]
    s = Style(bg_color="#112233", bg_opacity=0.7)
    text = ass_builder.build(segs, s, Position(), Size(), 640, 480)
    assert re.search(r",3,\d+,\d+,7,0,0,0,1", text)
    assert "&H4D332211" in text


def test_ass_no_bg_uses_border_style_1() -> None:
    segs = [_seg(0.0, 1.0, "x")]
    s = Style(bg_opacity=0.0)
    text = ass_builder.build(segs, s, Position(), Size(), 640, 480)
    assert re.search(r",1,\d+,\d+,7,0,0,0,1", text)


def test_ass_alignment_tags() -> None:
    for align, code in [("left", 7), ("center", 8), ("right", 9)]:
        segs = [_seg(0.0, 1.0, "x")]
        s = Style(alignment=align)
        text = ass_builder.build(segs, s, Position(), Size(), 640, 480)
        assert f"\\an{code}" in text


def test_ass_phrase_mode_is_default_and_emits_one_per_segment() -> None:
    segs = [
        _seg(0.0, 1.0, "first"),
        _seg(1.0, 2.5, "second"),
    ]
    text = ass_builder.build(segs, Style(), Position(), Size(), 640, 480)
    assert text.count("\nDialogue: ") == 2
    assert "first" in text and "second" in text


def test_ass_word_mode_emits_one_dialogue_per_chunk() -> None:
    words = [
        Word(start=0.0, end=0.5, text="hello"),
        Word(start=0.5, end=1.1, text="brave"),
        Word(start=1.1, end=1.8, text="new"),
        Word(start=1.8, end=2.4, text="world"),
    ]
    segs = [_seg(0.0, 2.4, "hello brave new world", words)]

    s = Style(mode="word", words_per_chunk=1)
    text = ass_builder.build(segs, s, Position(), Size(), 640, 480)
    assert text.count("\nDialogue: ") == 4
    assert "hello" in text and "brave" in text and "new" in text and "world" in text

    s2 = Style(mode="word", words_per_chunk=2)
    text2 = ass_builder.build(segs, s2, Position(), Size(), 640, 480)
    assert text2.count("\nDialogue: ") == 2
    assert "hello brave" in text2
    assert "new world" in text2


def test_ass_word_mode_chunks_use_word_timings() -> None:
    words = [
        Word(start=1.0, end=1.5, text="foo"),
        Word(start=2.0, end=2.8, text="bar"),
    ]
    segs = [_seg(1.0, 3.0, "foo bar", words)]
    text = ass_builder.build(
        segs, Style(mode="word", words_per_chunk=1), Position(), Size(), 640, 480
    )
    # First chunk ends at 1.50, second starts at 2.00
    assert "0:00:01.00,0:00:01.50" in text
    assert "0:00:02.00,0:00:02.80" in text


def test_ass_karaoke_emits_per_word_color_animations() -> None:
    words = [
        Word(start=0.0, end=0.4, text="the"),
        Word(start=0.4, end=1.0, text="quick"),
        Word(start=1.0, end=1.5, text="fox"),
    ]
    segs = [_seg(0.0, 1.5, "the quick fox", words)]
    s = Style(
        mode="karaoke",
        words_per_chunk=3,  # whole segment in one chunk
        text_color="#FFFFFF",
        active_word_color="#FFD400",
    )
    text = ass_builder.build(segs, s, Position(), Size(), 640, 480)

    # one Dialogue (single chunk of 3 words)
    assert text.count("\nDialogue: ") == 1

    assert "the" in text and "quick" in text and "fox" in text

    # per-word color flips via \t(start,start,\1c...) and \t(end,end,\1c...)
    # times in centiseconds, relative to chunk start (= seg start here):
    # the(0→40), quick(40→100), fox(100→150)
    active = "&H00D4FF&"
    base = "&HFFFFFF&"
    assert f"\\t(0,0,\\1c{active})" in text
    assert f"\\t(40,40,\\1c{base})" in text
    assert f"\\t(40,40,\\1c{active})" in text
    assert f"\\t(100,100,\\1c{base})" in text
    assert f"\\t(100,100,\\1c{active})" in text
    assert f"\\t(150,150,\\1c{base})" in text
    assert f"\\1c{base}" in text

    style_line = [l for l in text.splitlines() if l.startswith("Style: Default,")][0]
    parts = style_line.split(",")
    assert parts[3] == "&H00FFFFFF"


def test_ass_karaoke_active_word_color_used() -> None:
    words = [
        Word(start=0.0, end=0.5, text="hi"),
        Word(start=0.5, end=1.0, text="there"),
    ]
    segs = [_seg(0.0, 1.0, "hi there", words)]
    s = Style(mode="karaoke", words_per_chunk=2, active_word_color="#FF0000")
    text = ass_builder.build(segs, s, Position(), Size(), 640, 480)
    # #FF0000 → BGR "0000FF" → inline "&H0000FF&"
    assert "\\1c&H0000FF&" in text


def test_ass_karaoke_chunks_by_words_per_chunk() -> None:
    words = [
        Word(start=0.0, end=0.3, text="one"),
        Word(start=0.3, end=0.7, text="two"),
        Word(start=0.7, end=1.2, text="three"),
        Word(start=1.2, end=1.6, text="four"),
        Word(start=1.6, end=2.1, text="five"),
    ]
    segs = [_seg(0.0, 2.1, "one two three four five", words)]
    s = Style(mode="karaoke", words_per_chunk=2)
    text = ass_builder.build(segs, s, Position(), Size(), 640, 480)
    # 5 words / 2 per chunk = 3 Dialogue lines (2+2+1)
    assert text.count("\nDialogue: ") == 3
    # First chunk covers 0.0-0.7, second 0.7-1.6, third 1.6-2.1
    assert "0:00:00.00,0:00:00.70" in text
    assert "0:00:00.70,0:00:01.60" in text
    assert "0:00:01.60,0:00:02.10" in text


def test_ass_word_mode_breaks_chunk_on_sentence_end() -> None:
    # 4 words fit in chunk_size=4, but "world." forces a break.
    words = [
        Word(start=0.0, end=0.5, text="Hello"),
        Word(start=0.5, end=1.0, text="world."),
        Word(start=1.0, end=1.5, text="Foo"),
        Word(start=1.5, end=2.0, text="bar"),
    ]
    segs = [_seg(0.0, 2.0, "Hello world. Foo bar", words)]
    text = ass_builder.build(
        segs, Style(mode="word", words_per_chunk=4), Position(), Size(), 640, 480
    )
    # Without sentence break: 1 dialogue. With it: 2.
    assert text.count("\nDialogue: ") == 2
    assert "Hello world." in text
    assert "Foo bar" in text


def test_ass_karaoke_breaks_chunk_on_sentence_end() -> None:
    words = [
        Word(start=0.0, end=0.5, text="Hello"),
        Word(start=0.5, end=1.0, text="world."),
        Word(start=1.0, end=1.5, text="Foo"),
        Word(start=1.5, end=2.0, text="bar"),
    ]
    segs = [_seg(0.0, 2.0, "Hello world. Foo bar", words)]
    text = ass_builder.build(
        segs, Style(mode="karaoke", words_per_chunk=4), Position(), Size(), 640, 480
    )
    # 4 words would fit in one karaoke chunk; sentence break splits to 2.
    assert text.count("\nDialogue: ") == 2


def test_ass_fade_emitted_when_set() -> None:
    segs = [_seg(0.0, 1.0, "x")]
    s = Style(fade_in_ms=200, fade_out_ms=300)
    text = ass_builder.build(segs, s, Position(), Size(), 640, 480)
    assert "\\fad(200,300)" in text


def test_ass_word_mode_synthesizes_words_if_missing() -> None:
    segs = [_seg(0.0, 2.0, "one two three four")]
    text = ass_builder.build(
        segs, Style(mode="word", words_per_chunk=1), Position(), Size(), 640, 480
    )
    assert text.count("\nDialogue: ") == 4
