from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import main as app_main
from app.main import _safe_external_url, app
from app.models import FetchUrlRequest


# ---------- Pydantic model ----------


def test_request_rejects_empty_url() -> None:
    with pytest.raises(ValidationError):
        FetchUrlRequest(url="")


def test_request_accepts_http_url() -> None:
    req = FetchUrlRequest(url="http://example.com/x")
    assert req.url == "http://example.com/x"
    assert req.generate_subs is True


# ---------- SSRF guard ----------


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://example.com/",
    "http://localhost/",
    "http://127.0.0.1/",
    "http://0.0.0.0/",
    "http://192.168.1.1",
    "http://10.0.0.5",
    "http://169.254.169.254/",
    "http://172.16.0.1",
    "http://172.31.255.255",
    "",
    "not-a-url",
])
def test_ssrf_rejects(url: str) -> None:
    assert _safe_external_url(url) is False


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=xxx",
    "http://example.com/",
    "https://vimeo.com/1234",
    "http://172.15.0.1",  # 172.15.x.x is public
    "http://172.32.0.1",  # 172.32.x.x is public
])
def test_ssrf_accepts(url: str) -> None:
    assert _safe_external_url(url) is True


# ---------- Endpoint (mocked yt-dlp) ----------


class _FakeYDL:
    """Stand-in for yt_dlp.YoutubeDL. Copies fixture into the outtmpl target."""

    source_fixture: Path = Path(__file__).parent / "fixtures" / "sample_5s.mp4"
    duration: float = 5.0
    is_live: bool = False
    raise_on_download: Exception | None = None

    def __init__(self, opts: dict) -> None:
        self.opts = opts

    def __enter__(self) -> "_FakeYDL":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def extract_info(self, url: str, download: bool = True) -> dict:
        info = {
            "title": "sample",
            "duration": self.duration,
            "is_live": self.is_live,
            "ext": "mp4",
        }
        if not download:
            return info
        if self.raise_on_download is not None:
            raise self.raise_on_download
        tmpl = self.opts["outtmpl"]
        # outtmpl looks like "<dir>/.incoming-url-<pid>-<ts>.%(ext)s"
        target = Path(tmpl.replace("%(ext)s", "mp4"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.source_fixture, target)
        info["requested_downloads"] = [{"filepath": str(target)}]
        info["filepath"] = str(target)
        return info

    def prepare_filename(self, info: dict) -> str:
        return info.get("filepath", "")


def _install_fake_ydl(monkeypatch, **attrs) -> type[_FakeYDL]:
    Cls = type("_CfgFakeYDL", (_FakeYDL,), attrs)
    fake_mod = type("FakeYtDlp", (), {"YoutubeDL": Cls})
    monkeypatch.setattr(app_main, "_yt_dlp", fake_mod)
    return Cls


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
    monkeypatch.setattr(app_main, "MAX_FETCH_SEC", 900)
    return uploads


def _mute_bg_transcribe(monkeypatch) -> list[dict]:
    """Replace the bg-transcribe task factory with a spy so tests don't touch
    whisper. The spy records synchronously (before create_task yields) so the
    calls list is populated by the time the HTTP response returns."""
    calls: list[dict] = []

    async def _noop() -> None:
        return None

    def fake_run(**kwargs):
        calls.append(kwargs)
        return _noop()

    monkeypatch.setattr(app_main, "_run_transcribe_stream", fake_run)
    return calls


def test_fetch_url_happy_path(monkeypatch, fresh_uploads) -> None:
    _install_fake_ydl(monkeypatch)
    calls = _mute_bg_transcribe(monkeypatch)

    client = TestClient(app)
    r = client.post("/api/fetch-url", json={
        "url": "https://example.com/video.mp4",
        "language": "en",
        "generate_subs": True,
    })
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["video_id"]
    assert body["width"] == 320
    assert body["height"] == 240
    assert 4.9 <= body["duration"] <= 5.2
    assert body["segments"] == []

    final = fresh_uploads / f"{body['video_id']}.mp4"
    meta = fresh_uploads / f"{body['video_id']}.json"
    assert final.exists()
    assert meta.exists()
    # bg task kicked off with the expected video_id.
    assert len(calls) == 1
    assert calls[0]["video_id"] == body["video_id"]


def test_fetch_url_generate_subs_false_skips_bg(monkeypatch, fresh_uploads) -> None:
    _install_fake_ydl(monkeypatch)
    calls = _mute_bg_transcribe(monkeypatch)

    client = TestClient(app)
    r = client.post("/api/fetch-url", json={
        "url": "https://example.com/video.mp4",
        "generate_subs": False,
    })
    assert r.status_code == 200, r.text
    assert calls == []


def test_fetch_url_invalid_url(monkeypatch, fresh_uploads) -> None:
    client = TestClient(app)
    r = client.post("/api/fetch-url", json={"url": "http://localhost/evil"})
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid url"


def test_fetch_url_file_scheme_rejected(monkeypatch, fresh_uploads) -> None:
    client = TestClient(app)
    r = client.post("/api/fetch-url", json={"url": "file:///etc/passwd"})
    assert r.status_code == 400


def test_fetch_url_download_error_maps_to_502(monkeypatch, fresh_uploads) -> None:
    _mute_bg_transcribe(monkeypatch)
    _install_fake_ydl(monkeypatch, raise_on_download=RuntimeError("HTTP Error 403: Forbidden"))

    client = TestClient(app)
    r = client.post("/api/fetch-url", json={"url": "https://example.com/video.mp4"})
    assert r.status_code == 502
    assert "403" in r.json()["detail"]


def test_fetch_url_unsupported_source_maps_to_415(monkeypatch, fresh_uploads) -> None:
    _mute_bg_transcribe(monkeypatch)
    _install_fake_ydl(monkeypatch, raise_on_download=RuntimeError("Unsupported URL: xyz"))

    client = TestClient(app)
    r = client.post("/api/fetch-url", json={"url": "https://example.com/x"})
    assert r.status_code == 415


def test_fetch_url_too_long(monkeypatch, fresh_uploads) -> None:
    _mute_bg_transcribe(monkeypatch)
    monkeypatch.setattr(app_main, "MAX_FETCH_SEC", 60)
    _install_fake_ydl(monkeypatch, duration=3600.0)

    client = TestClient(app)
    r = client.post("/api/fetch-url", json={"url": "https://example.com/long"})
    assert r.status_code == 413
    assert "MAX_FETCH_SEC" in r.json()["detail"]


def test_fetch_url_live_stream_rejected(monkeypatch, fresh_uploads) -> None:
    _mute_bg_transcribe(monkeypatch)
    _install_fake_ydl(monkeypatch, is_live=True)

    client = TestClient(app)
    r = client.post("/api/fetch-url", json={"url": "https://example.com/live"})
    assert r.status_code == 400
    assert "live" in r.json()["detail"].lower()


# ---------- Error classifier ----------


@pytest.mark.parametrize("raw, expected_status, expected_phrase", [
    ("ERROR: Private video. Sign in if you've been granted access", 403, "private"),
    ("Sign in to confirm your age. This video may be inappropriate", 403, "age-restricted"),
    ("Video unavailable. This video has been removed by the uploader", 404, "unavailable"),
    ("ERROR: Unsupported URL: https://example.com/foo", 415, "not supported"),
    ("HTTP Error 429: Too Many Requests", 429, "rate-limited"),
    ("unable to download webpage: <urlopen error [Errno -3] Name or service not known>", 502, "could not reach"),
    ("HTTP Error 403: Forbidden", 502, "refused"),
    ("HTTP Error 404: Not Found", 404, "not found"),
    ("some totally unfamiliar failure mode", 502, "download failed"),
])
def test_fetch_url_error_classification(monkeypatch, fresh_uploads, raw, expected_status, expected_phrase) -> None:
    _mute_bg_transcribe(monkeypatch)
    _install_fake_ydl(monkeypatch, raise_on_download=RuntimeError(raw))

    client = TestClient(app)
    r = client.post("/api/fetch-url", json={"url": "https://example.com/v"})
    assert r.status_code == expected_status, f"raw={raw!r} got={r.status_code} body={r.text}"
    assert expected_phrase.lower() in r.json()["detail"].lower()
