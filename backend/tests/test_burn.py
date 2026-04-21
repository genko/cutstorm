from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from app import ass_builder
from app.burn import run as burn_run
from app.main import app
from app.models import Position, Segment, Size, Style
from app.transcribe import probe


def _ffprobe_duration(path: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


def test_burn_produces_valid_mp4(sample_video: Path, tmp_path: Path) -> None:
    info = probe(sample_video)
    segs = [
        Segment(start=0.0, end=2.0, text="first"),
        Segment(start=2.0, end=4.0, text="second"),
    ]
    ass_text = ass_builder.build(
        segs,
        Style(font_size=24),
        Position(x_pct=20, y_pct=80),
        Size(w_pct=60, h_pct=10),
        info.width,
        info.height,
    )
    ass_path = tmp_path / "subs.ass"
    ass_path.write_text(ass_text)
    out = tmp_path / "out.mp4"
    burn_run(sample_video, ass_path, out)
    assert out.exists() and out.stat().st_size > 0

    out_info = probe(out)
    assert out_info.width == info.width
    assert out_info.height == info.height
    dur_in = _ffprobe_duration(sample_video)
    dur_out = _ffprobe_duration(out)
    assert abs(dur_in - dur_out) < 0.2


def test_export_endpoint(sample_video: Path) -> None:
    client = TestClient(app)
    data = sample_video.read_bytes()
    r = client.post(
        "/api/transcribe",
        files={"file": ("sample_5s.mp4", io.BytesIO(data), "video/mp4")},
    )
    assert r.status_code == 200
    video_id = r.json()["video_id"]

    req = {
        "video_id": video_id,
        "segments": [{"start": 0.0, "end": 1.0, "text": "hello"}],
        "style": Style().model_dump(),
        "position": Position().model_dump(),
        "size": Size().model_dump(),
    }
    r2 = client.post("/api/export", json=req)
    assert r2.status_code == 200, r2.text

    r3 = client.get(f"/api/download/{video_id}")
    assert r3.status_code == 200
    assert r3.headers["content-type"] == "video/mp4"
    assert len(r3.content) > 0
