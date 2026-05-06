from __future__ import annotations

from typing import Iterable

from .ass_builder import _words_or_synth
from .models import Segment, Style


def compute_overlay_change_times(
    segments: Iterable[Segment],
    style: Style,
    duration: float,
) -> list[float]:
    """Sorted list of timestamps where the subtitle overlay content changes.

    Between consecutive points the overlay renders identically, so a caller
    can reuse the same rasterized frame for every output frame whose
    timestamp falls in that interval.

    Always starts with 0.0 and includes `duration` so callers can index
    pairs (points[i], points[i+1]) to cover the whole timeline.

    For karaoke/word modes, segments without word-level alignment fall back
    to synthesized even-spaced word boundaries (mirrors the frontend's
    `wordsOf` helper) so dedup still emits per-word change points instead
    of freezing the whole segment on one frame.
    """
    points: set[float] = {0.0, round(max(0.0, duration), 3)}
    for seg in segments:
        points.add(round(seg.start, 3))
        points.add(round(seg.end, 3))
        if style.mode == "karaoke":
            for w in _words_or_synth(seg):
                points.add(round(w.start, 3))
        elif style.mode == "word":
            ws = _words_or_synth(seg)
            chunk = max(1, style.words_per_chunk)
            for i in range(0, len(ws), chunk):
                points.add(round(ws[i].start, 3))
    return sorted(p for p in points if p >= 0.0)
