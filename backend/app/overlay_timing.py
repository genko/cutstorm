from __future__ import annotations

from typing import Iterable

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
    """
    points: set[float] = {0.0, round(max(0.0, duration), 3)}
    for seg in segments:
        points.add(round(seg.start, 3))
        points.add(round(seg.end, 3))
        if style.mode == "karaoke":
            for w in (seg.words or []):
                points.add(round(w.start, 3))
        elif style.mode == "word":
            ws = list(seg.words or [])
            chunk = max(1, style.words_per_chunk)
            for i in range(0, len(ws), chunk):
                points.add(round(ws[i].start, 3))
    return sorted(p for p in points if p >= 0.0)
