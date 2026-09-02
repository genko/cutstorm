from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.main import app

client = TestClient(app)


@pytest.fixture
def fresh_server(tmp_path, monkeypatch):
    """Point SERVER_DIR at a clean tmp dir simulating the admin-managed
    symlink under data/server."""
    server = tmp_path / "server"
    server.mkdir()
    monkeypatch.setattr(app_main, "SERVER_DIR", server)
    return server


@pytest.fixture
def fresh_uploads(tmp_path, monkeypatch):
    """Point UPLOADS_DIR/OUTPUTS_DIR at a clean tmp so fixture writes don't
    leak across tests."""
    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    uploads.mkdir()
    outputs.mkdir()
    monkeypatch.setattr(app_main, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(app_main, "OUTPUTS_DIR", outputs)
    return uploads


# ---------- GET /api/import-candidates ----------


def test_import_candidates_lists_untracked_file(fresh_uploads: Path, sample_video: Path) -> None:
    shutil.copyfile(sample_video, fresh_uploads / "manual.mp4")
    r = client.get("/api/import-candidates")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["filename"] == "manual.mp4"
    assert items[0]["duration"] > 1.0
    assert items[0]["width"] > 0 and items[0]["height"] > 0
    assert items[0]["is_audio_only"] is False


def test_import_candidates_skips_already_imported(fresh_uploads: Path, sample_video: Path) -> None:
    r = client.post(
        "/api/transcribe",
        files={"file": ("s.mp4", sample_video.read_bytes(), "video/mp4")},
        data={"generate_subs": "false"},
    )
    assert r.status_code == 200, r.text
    assert client.get("/api/import-candidates").json() == []


def test_import_candidates_skips_extra_audio_and_hidden_files(fresh_uploads: Path) -> None:
    (fresh_uploads / "extra_abc123.mp3").write_bytes(b"\x00" * 16)
    (fresh_uploads / ".incoming-stale").write_bytes(b"\x00" * 16)
    assert client.get("/api/import-candidates").json() == []


def test_import_candidates_ignores_non_media_files(fresh_uploads: Path) -> None:
    (fresh_uploads / "notes.txt").write_text("hi")
    assert client.get("/api/import-candidates").json() == []


def test_import_candidates_lists_server_dir_file(
    fresh_uploads: Path, fresh_server: Path, sample_video: Path,
) -> None:
    shutil.copyfile(sample_video, fresh_server / "admin.mp4")
    r = client.get("/api/import-candidates")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["filename"] == "admin.mp4"
    assert items[0]["source"] == "server"


def test_import_candidates_missing_server_dir_ok(fresh_uploads: Path, monkeypatch) -> None:
    # SERVER_DIR is admin-managed and may not exist (symlink not yet
    # created) — listing must not error.
    monkeypatch.setattr(app_main, "SERVER_DIR", Path("/no/such/dir"))
    assert client.get("/api/import-candidates").json() == []


# ---------- POST /api/import-existing ----------


def test_import_existing_adopts_file(fresh_uploads: Path, sample_video: Path) -> None:
    shutil.copyfile(sample_video, fresh_uploads / "manual2.mp4")
    r = client.post(
        "/api/import-existing",
        json={"filename": "manual2.mp4", "generate_subs": False},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["video_id"]
    assert body["duration"] > 1.0
    assert body["status"] == "done"
    assert body["segments"] == []
    # Stray filename is gone, replaced by the content-hashed video_id path.
    assert not (fresh_uploads / "manual2.mp4").exists()
    assert (fresh_uploads / f"{body['video_id']}.mp4").exists()
    # meta.json now exists → the file no longer shows up as a candidate,
    # and instead is visible via the normal /api/transcripts listing.
    assert client.get("/api/import-candidates").json() == []
    ids = [t["video_id"] for t in client.get("/api/transcripts").json()]
    assert body["video_id"] in ids


def test_import_existing_from_server_dir_copies_not_moves(
    fresh_uploads: Path, fresh_server: Path, sample_video: Path,
) -> None:
    shutil.copyfile(sample_video, fresh_server / "admin.mp4")
    r = client.post(
        "/api/import-existing",
        json={"filename": "admin.mp4", "source": "server", "generate_subs": False},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["video_id"]
    # Admin's file is left in place — never moved or deleted.
    assert (fresh_server / "admin.mp4").exists()
    assert (fresh_uploads / f"{body['video_id']}.mp4").exists()
    ids = [t["video_id"] for t in client.get("/api/transcripts").json()]
    assert body["video_id"] in ids


def test_import_existing_from_server_dir_unknown_file_404(
    fresh_uploads: Path, fresh_server: Path,
) -> None:
    r = client.post(
        "/api/import-existing",
        json={"filename": "nope.mp4", "source": "server"},
    )
    assert r.status_code == 404


@pytest.mark.parametrize("bad", ["../etc/passwd", "a/b.mp4", "a\\b.mp4", "..", "."])
def test_import_existing_rejects_bad_filenames(fresh_uploads: Path, bad: str) -> None:
    r = client.post("/api/import-existing", json={"filename": bad})
    assert r.status_code == 400, bad


def test_import_existing_rejects_empty_filename(fresh_uploads: Path) -> None:
    # Caught by the Pydantic model's min_length=1 before reaching the handler.
    r = client.post("/api/import-existing", json={"filename": ""})
    assert r.status_code == 422


def test_import_existing_unknown_file_404(fresh_uploads: Path) -> None:
    r = client.post("/api/import-existing", json={"filename": "nope.mp4"})
    assert r.status_code == 404


def test_import_existing_unsupported_ext_415(fresh_uploads: Path) -> None:
    (fresh_uploads / "readme.txt").write_text("hi")
    r = client.post("/api/import-existing", json={"filename": "readme.txt"})
    assert r.status_code == 415


def test_import_existing_already_imported_conflict(fresh_uploads: Path, sample_video: Path) -> None:
    r = client.post(
        "/api/transcribe",
        files={"file": ("s.mp4", sample_video.read_bytes(), "video/mp4")},
        data={"generate_subs": "false"},
    )
    video_id = r.json()["video_id"]
    r2 = client.post("/api/import-existing", json={"filename": f"{video_id}.mp4"})
    assert r2.status_code == 409
