"""Unit tests for the loop-mode segment expander.

Exercises clip-space repetition of source-track subtitles across multiple
iterations of a looped video clip.
"""
from __future__ import annotations

from app.loop_segments import expand_loop_segments
from app.models import Segment, Word


def _seg(start: float, end: float, text: str = "x",
         words: list[tuple[float, float, str]] | None = None) -> Segment:
    ws = [Word(start=s, end=e, text=t) for s, e, t in (words or [])]
    return Segment(start=start, end=end, text=text, words=ws)


def test_empty_segments_returns_empty() -> None:
    assert expand_loop_segments([], trim_in=0.0,
                                 loop_clip_duration=5.0, total_duration=15.0) == []


def test_single_segment_repeats_n_times() -> None:
    seg = _seg(0.0, 2.0, "hello", [(0.0, 2.0, "hello")])
    out = expand_loop_segments([seg], trim_in=0.0,
                                loop_clip_duration=5.0, total_duration=12.0)
    # Iterations begin at offset 0, 5, 10. The 10-offset copy survives because
    # 10 < 12; its end at 10+2=12 stays in-bounds.
    assert len(out) == 3
    assert abs(out[0].start - 0.0) < 1e-6
    assert abs(out[0].end - 2.0) < 1e-6
    assert abs(out[1].start - 5.0) < 1e-6
    assert abs(out[1].end - 7.0) < 1e-6
    assert abs(out[2].start - 10.0) < 1e-6
    assert abs(out[2].end - 12.0) < 1e-6
    # Words follow the same offsetting.
    assert out[1].words[0].text == "hello"
    assert abs(out[1].words[0].start - 5.0) < 1e-6
    assert abs(out[1].words[0].end - 7.0) < 1e-6


def test_segment_clamps_at_total_duration() -> None:
    seg = _seg(3.0, 6.0, "spans")
    # loop_clip=5, total=8 → only one iteration, segment clamps to 8.
    out = expand_loop_segments([seg], trim_in=0.0,
                                loop_clip_duration=5.0, total_duration=8.0)
    assert len(out) == 1
    assert abs(out[0].start - 3.0) < 1e-6
    assert abs(out[0].end - 6.0) < 1e-6


def test_segment_dropped_if_starts_past_end() -> None:
    seg = _seg(4.0, 4.5, "tail")
    # loop_clip=5, total=12 → offsets 0, 5, 10. Copy at offset=10 starts at
    # 14 which is past total=12 and must be dropped.
    out = expand_loop_segments([seg], trim_in=0.0,
                                loop_clip_duration=5.0, total_duration=12.0)
    starts = [round(s.start, 3) for s in out]
    assert starts == [4.0, 9.0]


def test_word_clamping_at_boundary() -> None:
    seg = _seg(0.0, 5.0, "ab", [(0.0, 2.5, "a"), (2.5, 5.0, "b")])
    # loop_clip=5, total=8 → first copy 0..5 clean, second copy 5..10 clamps
    # to 8. Word "a" 5..7.5 fits. Word "b" 7.5..10 clamps to 7.5..8.
    out = expand_loop_segments([seg], trim_in=0.0,
                                loop_clip_duration=5.0, total_duration=8.0)
    assert len(out) == 2
    second = out[1]
    assert abs(second.end - 8.0) < 1e-6
    assert len(second.words) == 2
    assert second.words[0].text == "a"
    assert abs(second.words[0].start - 5.0) < 1e-6
    assert abs(second.words[0].end - 7.5) < 1e-6
    assert second.words[1].text == "b"
    assert abs(second.words[1].start - 7.5) < 1e-6
    assert abs(second.words[1].end - 8.0) < 1e-6


def test_zero_loop_clip_returns_input() -> None:
    seg = _seg(0.0, 2.0)
    assert expand_loop_segments([seg], trim_in=0.0,
                                 loop_clip_duration=0.0, total_duration=10.0) == [seg]


def test_zero_total_duration_returns_input() -> None:
    seg = _seg(0.0, 2.0)
    assert expand_loop_segments([seg], trim_in=0.0,
                                 loop_clip_duration=5.0, total_duration=0.0) == [seg]
