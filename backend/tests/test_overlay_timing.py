from __future__ import annotations

from app.models import Segment, Style, Word
from app.overlay_timing import compute_overlay_change_times


def _seg(start: float, end: float, words: list[tuple[float, float, str]] | None = None) -> Segment:
    ws = [Word(start=s, end=e, text=t) for s, e, t in (words or [])]
    return Segment(start=start, end=end, text=" ".join(w.text for w in ws) or "x", words=ws)


def test_empty_segments_bracket_duration() -> None:
    pts = compute_overlay_change_times([], Style(mode="phrase"), duration=10.0)
    assert pts == [0.0, 10.0]


def test_phrase_single_segment_four_points() -> None:
    seg = _seg(2.0, 5.0)
    pts = compute_overlay_change_times([seg], Style(mode="phrase"), duration=8.0)
    assert pts == [0.0, 2.0, 5.0, 8.0]


def test_karaoke_adds_every_word_start() -> None:
    seg = _seg(
        0.0, 3.0,
        [
            (0.0, 0.5, "a"),
            (0.5, 1.0, "b"),
            (1.0, 1.5, "c"),
            (1.5, 2.0, "d"),
            (2.0, 2.5, "e"),
        ],
    )
    pts = compute_overlay_change_times([seg], Style(mode="karaoke"), duration=3.0)
    # 0.0 (bracket + seg.start + word[0].start), 0.5, 1.0, 1.5, 2.0 (word[4].start + seg.start of another?), 2.5 (only if word.end — no, not tracked), 3.0 (seg.end + duration)
    # Distinct: {0.0, 0.5, 1.0, 1.5, 2.0, 3.0}
    assert pts == [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]
    assert len(pts) >= 6


def test_word_mode_chunk_starts_only() -> None:
    # 6 words, chunk=2 → chunk starts at w0, w2, w4 (indices 0, 2, 4)
    seg = _seg(
        0.0, 6.0,
        [
            (0.0, 1.0, "one"),
            (1.0, 2.0, "two"),
            (2.0, 3.0, "three"),
            (3.0, 4.0, "four"),
            (4.0, 5.0, "five"),
            (5.0, 6.0, "six"),
        ],
    )
    pts = compute_overlay_change_times(
        [seg], Style(mode="word", words_per_chunk=2), duration=6.0
    )
    # Expected distinct points: 0.0 (bracket + seg.start + w0), 2.0 (w2), 4.0 (w4), 6.0 (seg.end + duration)
    assert pts == [0.0, 2.0, 4.0, 6.0]


def test_overlapping_segments_merged_sorted_no_dupes() -> None:
    a = _seg(0.0, 5.0)
    b = _seg(3.0, 5.0)  # shares end boundary with a
    c = _seg(7.5, 9.0)
    pts = compute_overlay_change_times([a, b, c], Style(mode="phrase"), duration=10.0)
    assert pts == sorted(set(pts))  # strictly sorted, unique
    assert pts == [0.0, 3.0, 5.0, 7.5, 9.0, 10.0]


def test_points_rounded_to_3_decimals() -> None:
    # Simulate whisper-style floats with >3-decimal precision.
    seg = _seg(0.123456, 1.987654)
    pts = compute_overlay_change_times([seg], Style(mode="phrase"), duration=2.7654321)
    # All values should coincide with 3-decimal rounding.
    for p in pts:
        assert round(p, 3) == p
    assert 0.123 in pts
    assert 1.988 in pts
    assert 2.765 in pts


def test_duration_zero_does_not_produce_negative() -> None:
    pts = compute_overlay_change_times([], Style(mode="phrase"), duration=0.0)
    assert pts == [0.0]


def test_word_mode_single_chunk_covers_all_words() -> None:
    seg = _seg(
        1.0, 5.0,
        [(1.0, 2.0, "hello"), (2.0, 3.0, "world"), (3.0, 4.0, "foo"), (4.0, 5.0, "bar")],
    )
    pts = compute_overlay_change_times(
        [seg], Style(mode="word", words_per_chunk=8), duration=6.0
    )
    # Only first chunk start (w0) + seg.start + seg.end + 0 + duration.
    # 0.0, 1.0 (seg.start + w0.start), 5.0 (seg.end), 6.0
    assert pts == [0.0, 1.0, 5.0, 6.0]
