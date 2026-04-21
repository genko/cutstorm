"""Downsampled waveform peaks computed via ffmpeg.

Extracts mono s16le PCM from any input (video or audio) at 8 kHz, then
reduces to `bins` peak values in [0, 1]. Memory footprint is ~16 KB per
second of source, so a 2-hour podcast fits well under 120 MB — fine for
a one-shot compute cached per id.

Used by GET /api/peaks/{id} to draw the waveform strips under the preview.
"""
from __future__ import annotations

import array
import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

SAMPLE_RATE = 8000


def compute_peaks(source: Path, bins: int) -> list[float]:
    """Return `bins` peak magnitudes in [0, 1] from the source's audio track."""
    if bins <= 0:
        return []
    cmd = [
        "ffmpeg",
        "-v", "error", "-nostdin",
        "-i", str(source),
        "-vn",
        "-ac", "1",
        "-ar", str(SAMPLE_RATE),
        "-f", "s16le",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg peaks exit={proc.returncode}: {proc.stderr.decode('utf-8', 'replace')[-300:]}"
        )
    pcm = array.array("h")
    pcm.frombytes(proc.stdout)
    if len(pcm) == 0:
        return [0.0] * bins
    n = len(pcm)
    peaks: list[float] = []
    for i in range(bins):
        lo = n * i // bins
        hi = n * (i + 1) // bins
        if hi <= lo:
            hi = lo + 1
        hi = min(hi, n)
        m = 0
        for j in range(lo, hi):
            v = pcm[j]
            if v < 0:
                v = -v
            if v > m:
                m = v
        peaks.append(float(m))
    mx = max(peaks) if peaks else 0.0
    if mx <= 0:
        return [0.0] * bins
    return [p / mx for p in peaks]
