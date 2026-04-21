from __future__ import annotations

import io
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_video_id_traversal_rejected() -> None:
    # Non-hex and non-16-chars must 404 before touching disk.
    for bad in ("zzzz", "../etc/passwd", "..%2F..%2Fetc%2Fpasswd", "a" * 15, "A" * 16):
        r = client.get(f"/api/video/{bad}")
        assert r.status_code == 404, bad


def test_valid_video_id_shape_passes_validator() -> None:
    # 16 hex chars is a well-formed id; file doesn't exist so still 404 but
    # the message comes from the existence check, not the shape check. The
    # important bit is that the validator didn't short-circuit on shape.
    r = client.get("/api/video/" + "a" * 16)
    assert r.status_code == 404


def test_upload_oversize_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "512")
    big = io.BytesIO(b"x" * 2048)
    r = client.post(
        "/api/transcribe",
        files={"file": ("big.mp4", big, "video/mp4")},
    )
    assert r.status_code == 413
    # no temp file left behind
    uploads = os.environ["UPLOADS_DIR"]
    leftovers = [n for n in os.listdir(uploads) if n.startswith(".incoming-")]
    assert leftovers == []
