from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.main import app


@pytest.fixture
def fresh_uploads(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    uploads.mkdir()
    outputs.mkdir()
    monkeypatch.setattr(app_main, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(app_main, "OUTPUTS_DIR", outputs)
    return uploads


def _seed_meta(uploads: Path, video_id: str) -> Path:
    path = uploads / f"{video_id}.json"
    path.write_text(json.dumps({
        "video_id": video_id,
        "duration": 5.0, "width": 320, "height": 240,
        "segments": [],
        "status": "done", "percent": 100, "job_id": "j1",
    }))
    return path


def test_put_project_persists_and_returns_on_get(fresh_uploads) -> None:
    video_id = "0123456789abcdef"
    meta_path = _seed_meta(fresh_uploads, video_id)

    client = TestClient(app)
    project = {
        "style": {"font_family": "Inter", "font_size": 72, "text_color": "#FF0000"},
        "position": {"x_pct": 50, "y_pct": 90},
        "trim_range": {"in_sec": 1.0, "out_sec": 4.0},
        "use_subs": False,
        "display_mode": "karaoke",
    }
    r = client.put(f"/api/transcripts/{video_id}", json={"project": project})
    assert r.status_code == 200, r.text

    stored = json.loads(meta_path.read_text())
    assert stored["project"]["position"] == {"x_pct": 50.0, "y_pct": 90.0}
    assert stored["project"]["use_subs"] is False
    # style partially patched → pydantic fills defaults for omitted fields.
    assert stored["project"]["style"]["font_family"] == "Inter"
    assert stored["project"]["style"]["font_size"] == 72

    # GET round-trips project field.
    g = client.get(f"/api/transcripts/{video_id}")
    assert g.status_code == 200
    body = g.json()
    assert body["project"]["position"] == {"x_pct": 50.0, "y_pct": 90.0}
    assert body["project"]["use_subs"] is False


def test_put_segments_only_still_works(fresh_uploads) -> None:
    """Backwards-compat: old clients send only {segments}."""
    video_id = "1111222233334444"
    meta_path = _seed_meta(fresh_uploads, video_id)

    client = TestClient(app)
    r = client.put(
        f"/api/transcripts/{video_id}",
        json={"segments": [{"start": 0.0, "end": 1.0, "text": "hi"}]},
    )
    assert r.status_code == 200

    stored = json.loads(meta_path.read_text())
    assert len(stored["segments"]) == 1
    assert stored["segments"][0]["text"] == "hi"
    # No project key means we didn't accidentally initialise one.
    assert "project" not in stored or stored["project"] is None


def test_put_project_is_partial_merge(fresh_uploads) -> None:
    """Subsequent PUT with a subset of fields does not wipe previously
    stored ones."""
    video_id = "2222333344445555"
    meta_path = _seed_meta(fresh_uploads, video_id)

    client = TestClient(app)
    client.put(f"/api/transcripts/{video_id}", json={"project": {
        "position": {"x_pct": 10, "y_pct": 80},
        "use_subs": True,
    }})
    client.put(f"/api/transcripts/{video_id}", json={"project": {
        "position": {"x_pct": 25, "y_pct": 25},
    }})

    stored = json.loads(meta_path.read_text())
    assert stored["project"]["position"] == {"x_pct": 25.0, "y_pct": 25.0}
    # use_subs from first PUT survives the second.
    assert stored["project"]["use_subs"] is True


def test_put_rejects_missing_transcript(fresh_uploads) -> None:
    client = TestClient(app)
    r = client.put("/api/transcripts/deadbeefcafebabe", json={"project": {}})
    assert r.status_code == 404
