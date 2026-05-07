from __future__ import annotations

import io
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import UPLOADS_DIR, app


def test_transcribe_extra_endpoint(sample_video: Path, monkeypatch) -> None:
    """Upload an extra audio track, then run whisper on it via the new
    /api/transcribe-extra endpoint. Reuses the same fixture as the source
    transcribe test (it has both video and audio streams; ffmpeg can probe
    it as audio just fine)."""
    monkeypatch.setenv("WHISPERX_SKIP_ALIGN", "1")
    monkeypatch.setenv("WHISPER_MODEL", os.environ.get("WHISPER_MODEL", "tiny"))
    client = TestClient(app)
    with client:
        # The /api/extra-audio whitelist accepts mp3/wav/m4a/etc but rejects
        # mp4 by extension. Repackage the sample's audio stream as a tiny mp3.
        import subprocess
        tmp_mp3 = UPLOADS_DIR.parent / "sample_5s_extra.mp3"
        UPLOADS_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-i", str(sample_video),
             "-vn", "-c:a", "libmp3lame", "-q:a", "9",
             str(tmp_mp3)],
            check=True,
        )
        try:
            payload = tmp_mp3.read_bytes()
            r = client.post(
                "/api/extra-audio",
                files={"file": ("bg.mp3", io.BytesIO(payload), "audio/mpeg")},
            )
            assert r.status_code == 200, r.text
            extra_id = r.json()["extra_audio_id"]

            r2 = client.post(
                "/api/transcribe-extra",
                data={"extra_audio_id": extra_id, "language": "en"},
            )
            assert r2.status_code == 200, r2.text
            body = r2.json()
            assert body["extra_audio_id"] == extra_id
            assert body["duration"] > 4.5
            assert isinstance(body["segments"], list)
        finally:
            tmp_mp3.unlink(missing_ok=True)


def test_transcribe_extra_404_on_unknown_id() -> None:
    client = TestClient(app)
    r = client.post(
        "/api/transcribe-extra",
        data={"extra_audio_id": "f" * 16, "language": "en"},
    )
    assert r.status_code == 404


def test_transcribe_extra_400_on_bad_id_shape() -> None:
    client = TestClient(app)
    r = client.post(
        "/api/transcribe-extra",
        data={"extra_audio_id": "not-hex", "language": "en"},
    )
    assert r.status_code == 400


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


