"""Sprite-sheet thumbnail generation via ffmpeg.

A single horizontal strip of `count` frames at `width` px each, evenly
distributed across the source duration. One ffmpeg invocation produces the
sprite as a JPEG — the frontend draws the sprite under the trim bar using
background-position offsets.

Cached on disk as `thumbs_{video_id}_{count}_{width}.jpg` so regenerations
on reload are instant.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def sprite_path(cache_dir: Path, video_id: str, count: int, width: int) -> Path:
    return cache_dir / f"thumbs_{video_id}_{count}_{width}.jpg"


def build_sprite(
    source: Path,
    duration: float,
    out_path: Path,
    count: int,
    width: int,
) -> None:
    """Build a horizontal sprite sheet of `count` thumbs, each `width` px wide."""
    if duration <= 0:
        raise ValueError("duration must be positive")
    if count <= 0:
        raise ValueError("count must be positive")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # fps = count / duration captures one frame every `duration/count` seconds.
    # The `tile=Nx1` filter assembles them into a single row.
    vf = f"fps={count}/{duration:.6f},scale={width}:-2:force_original_aspect_ratio=decrease,tile={count}x1"
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-nostdin",
        "-i", str(source),
        "-frames:v", "1",
        "-vf", vf,
        "-q:v", "4",
        str(out_path),
    ]
    log.info("thumbnails.build cmd=%s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg thumbs exit={proc.returncode}: {proc.stderr.decode('utf-8', 'replace')[-300:]}"
        )
