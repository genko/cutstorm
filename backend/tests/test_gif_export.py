from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Position, Size, Style


def _ffprobe_codec(path: Path) -> str:
    out = subprocess.run(
        ["ffprobe", "-v", "error",
         "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height",
         "-of", "default=noprint_wrappers=1",
         str(path)],
        check=True, capture_output=True, text=True,
    )
    return out.stdout


def test_gif_export_low_quality(sample_video: Path) -> None:
    client = TestClient(app)
    with client:
        r = client.post(
            "/api/transcribe",
            files={"file": ("sample_5s.mp4", io.BytesIO(sample_video.read_bytes()), "video/mp4")},
            data={"language": "en", "generate_subs": "false"},
        )
        assert r.status_code == 200
        video_id = r.json()["video_id"]

        export = client.post("/api/export", json={
            "video_id": video_id,
            "segments": [],
            "style": Style().model_dump(),
            "position": Position().model_dump(),
            "size": Size().model_dump(),
            "format": "gif",
            "gif_quality": "low",
            "trim": {"in_sec": 0.0, "out_sec": 3.0},
        })
        assert export.status_code == 200, export.text
        body = export.json()
        assert body["output_format"] == "gif"
        gif_path = Path(body["output_path"])
        assert gif_path.exists()
        assert gif_path.suffix == ".gif"

        info = _ffprobe_codec(gif_path)
        assert "codec_name=gif" in info
        assert "width=320" in info  # low preset

        # Download endpoint serves the gif when format=gif is passed.
        dl = client.get(f"/api/download/{video_id}?format=gif")
        assert dl.status_code == 200
        assert dl.headers["content-type"].startswith("image/gif")
        assert len(dl.content) > 0


def test_export_mp4_default_unchanged(sample_video: Path) -> None:
    """Sanity: omitting format still yields MP4 (backwards-compat)."""
    client = TestClient(app)
    with client:
        r = client.post(
            "/api/transcribe",
            files={"file": ("sample_5s.mp4", io.BytesIO(sample_video.read_bytes()), "video/mp4")},
            data={"language": "en", "generate_subs": "false"},
        )
        video_id = r.json()["video_id"]
        export = client.post("/api/export", json={
            "video_id": video_id,
            "segments": [],
            "style": Style().model_dump(),
            "position": Position().model_dump(),
            "size": Size().model_dump(),
        })
        assert export.status_code == 200
        body = export.json()
        assert body["output_format"] == "mp4"
        assert body["output_path"].endswith(".mp4")
