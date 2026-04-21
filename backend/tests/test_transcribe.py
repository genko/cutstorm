from __future__ import annotations

import io
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_transcribe_and_cache(sample_video: Path, monkeypatch) -> None:
    monkeypatch.setenv("WHISPERX_SKIP_ALIGN", "1")
    monkeypatch.setenv("WHISPER_MODEL", os.environ.get("WHISPER_MODEL", "tiny"))
    client = TestClient(app)
    data = sample_video.read_bytes()

    t0 = time.perf_counter()
    r = client.post(
        "/api/transcribe",
        files={"file": ("sample_5s.mp4", io.BytesIO(data), "video/mp4")},
        data={"language": "en"},
    )
    t1 = time.perf_counter()
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["video_id"]
    assert body["width"] == 320
    assert body["height"] == 240
    assert 4.9 <= body["duration"] <= 5.2
    assert isinstance(body["segments"], list)
    for seg in body["segments"]:
        assert seg["start"] >= 0.0
        assert seg["end"] <= 5.2
        assert isinstance(seg["text"], str)
        assert isinstance(seg["words"], list)
        for w in seg["words"]:
            assert w["start"] >= seg["start"] - 0.05
            assert w["end"] <= seg["end"] + 0.05
            assert isinstance(w["text"], str) and w["text"]

    video_id_first = body["video_id"]
    first_elapsed = t1 - t0

    t0 = time.perf_counter()
    r2 = client.post(
        "/api/transcribe",
        files={"file": ("sample_5s.mp4", io.BytesIO(data), "video/mp4")},
        data={"language": "en"},
    )
    t1 = time.perf_counter()
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["video_id"] == video_id_first
    second_elapsed = t1 - t0
    assert second_elapsed < first_elapsed or second_elapsed < 1.0


