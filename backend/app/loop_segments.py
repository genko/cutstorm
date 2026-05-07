"""Helpers for the Coub-style loop export path.

When `trim.loop=true` and an extra audio track is present, the source video
slice [trim_in..trim_out] is repeated to cover the extra audio's duration.
Source-track subtitles must be repeated alongside the video so each loop
iteration shows the same captions; extra-track subtitles already live on the
master extra-audio timeline and ride through unchanged.
"""
from __future__ import annotations

from .models import Segment, Word


def expand_loop_segments(
    segments: list[Segment],
    trim_in: float,
    loop_clip_duration: float,
    total_duration: float,
) -> list[Segment]:
    """Repeat source-track segments across loop iterations.

    `segments` are the source segments already shifted into clip-space (i.e.
    times in [0, loop_clip_duration]). We do NOT clip to trim here — caller
    is expected to pass `_clip_segments_to_trim` output. The function emits
    a flat list of segments covering [0, total_duration] by stamping copies
    at iteration offsets 0, loop_clip_duration, 2·loop_clip_duration, ...

    Segments that would fall entirely past `total_duration` are dropped;
    segments that span the boundary are clamped to `total_duration`.
    """
    if loop_clip_duration <= 0 or total_duration <= 0:
        return list(segments)
    if not segments:
        return []

    out: list[Segment] = []
    offset = 0.0
    eps = 1e-6
    while offset < total_duration - eps:
        for s in segments:
            ns = s.start + offset
            ne = s.end + offset
            if ns >= total_duration - eps:
                continue
            if ne > total_duration:
                ne = total_duration
            new_words = []
            for w in (s.words or []):
                ws_ = w.start + offset
                we_ = w.end + offset
                if ws_ >= total_duration - eps:
                    continue
                if we_ > total_duration:
                    we_ = total_duration
                if we_ <= ws_:
                    continue
                new_words.append(Word(start=ws_, end=we_, text=w.text))
            out.append(
                Segment(start=ns, end=ne, text=s.text, words=new_words)
            )
        offset += loop_clip_duration
    return out
