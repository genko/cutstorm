from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Callable, Optional


class BurnError(RuntimeError):
    pass


ProgressCb = Callable[[int], None]


def run(
    video: Path,
    ass: Path,
    out: Path,
    total_duration: float = 0.0,
    on_progress: Optional[ProgressCb] = None,
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    filter_arg = f"ass={_escape_filter_path(str(ass))}"
    cmd = [
        "ffmpeg",
        "-y",
        "-nostats",
        "-progress", "pipe:1",
        "-stats_period", "0.1",
        "-i", str(video),
        "-vf", filter_arg,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "slow",
        "-crf", "16",
        "-c:a", "copy",
        str(out),
    ]
    _run_ffmpeg(cmd, total_duration, on_progress)


def run_with_cuts(
    video: Path,
    ass: Path,
    out: Path,
    select_expr: str,
    total_duration: float = 0.0,
    on_progress: Optional[ProgressCb] = None,
) -> None:
    """Encode `out` keeping only frames where `select_expr` is non-zero, burning ASS on top.

    `total_duration` is the NEW (post-cut) duration for progress reporting.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    ass_arg = _escape_filter_path(str(ass))
    filter_complex = (
        f"[0:v]select='{select_expr}',setpts=N/FRAME_RATE/TB,ass={ass_arg}[v];"
        f"[0:a]aselect='{select_expr}',asetpts=N/SR/TB[a]"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-nostats",
        "-progress", "pipe:1",
        "-stats_period", "0.1",
        "-i", str(video),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "slow",
        "-crf", "16",
        "-c:a", "aac",
        "-b:a", "192k",
        str(out),
    ]
    _run_ffmpeg(cmd, total_duration, on_progress)


def run_audio_only(
    audio: Path,
    ass: Path,
    out: Path,
    width: int,
    height: int,
    bg_color: str,
    duration: float,
    select_expr: Optional[str] = None,
    on_progress: Optional[ProgressCb] = None,
) -> None:
    """Render a video from a solid background + audio + burned ASS subtitles.

    If `select_expr` is given (from auto-cut silences), the audio is trimmed
    via `aselect` + re-timed via `asetpts`, and the synthetic video track uses
    the post-cut `duration` so ffmpeg produces a matching length.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    ass_arg = _escape_filter_path(str(ass))
    c = bg_color.lstrip("#").upper()
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    color_hex = f"0x{c}"

    video_filter = f"ass={ass_arg}"
    color_input = f"color=c={color_hex}:s={width}x{height}:r=30:d={duration:.3f}"
    if select_expr:
        filter_complex = (
            f"[0:v]{video_filter}[v];"
            f"[1:a]aselect='{select_expr}',asetpts=N/SR/TB[a]"
        )
        cmd = [
            "ffmpeg", "-y", "-nostats",
            "-progress", "pipe:1",
            "-stats_period", "0.1",
            "-f", "lavfi", "-i", color_input,
            "-i", str(audio),
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            "-shortest",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "slow",
            "-crf", "16",
            "-c:a", "aac",
            "-b:a", "192k",
            str(out),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-nostats",
            "-progress", "pipe:1",
            "-stats_period", "0.1",
            "-f", "lavfi", "-i", color_input,
            "-i", str(audio),
            "-shortest",
            "-vf", video_filter,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "slow",
            "-crf", "16",
            "-c:a", "aac",
            "-b:a", "192k",
            str(out),
        ]
    _run_ffmpeg(cmd, duration, on_progress)


def _run_ffmpeg(
    cmd: list[str],
    total_duration: float,
    on_progress: Optional[ProgressCb],
) -> None:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("out_time_ms=") and on_progress and total_duration > 0:
                try:
                    us = int(line.split("=", 1)[1])
                except ValueError:
                    continue
                pct = max(0, min(100, int(us / 1_000_000 / total_duration * 100)))
                on_progress(pct)
            elif line == "progress=end" and on_progress:
                on_progress(100)
    finally:
        proc.wait()
    if proc.returncode != 0:
        err = proc.stderr.read() if proc.stderr else ""
        raise BurnError(
            f"ffmpeg failed (code {proc.returncode}):\n"
            f"cmd: {shlex.join(cmd)}\nstderr:\n{err[-2000:]}"
        )


def _escape_filter_path(p: str) -> str:
    return p.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
