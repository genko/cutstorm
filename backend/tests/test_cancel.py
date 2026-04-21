from __future__ import annotations

import asyncio
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


def test_cancel_noop_when_no_task(fresh_uploads) -> None:
    client = TestClient(app)
    r = client.post("/api/transcribe/0123456789abcdef/cancel")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "cancelled": False}


def test_cancel_rejects_bad_id(fresh_uploads) -> None:
    client = TestClient(app)
    r = client.post("/api/transcribe/NOPE/cancel")
    assert r.status_code == 404


def test_cancel_interrupts_running_task(fresh_uploads, monkeypatch) -> None:
    """Register a fake 'running' task + cancel flag, then verify the endpoint
    flips the flag, cancels the task, and writes status=cancelled to meta."""
    video_id = "aaaaaaaaaaaaaaaa"
    meta_path = fresh_uploads / f"{video_id}.json"
    meta_path.write_text(json.dumps({
        "video_id": video_id,
        "duration": 5.0, "width": 320, "height": 240,
        "segments": [], "status": "pending", "percent": 20, "job_id": "j1",
    }))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def runner() -> dict:
        # Long-running placeholder task. Real whisper would be driven from
        # within this, polling a cancel flag between segments.
        done = asyncio.Event()
        async def coro() -> None:
            try:
                await done.wait()
            except asyncio.CancelledError:
                raise
        task = loop.create_task(coro())
        flag = {"v": False}
        app_main._transcribe_tasks[video_id] = (task, flag)

        client = TestClient(app)
        r = client.post(f"/api/transcribe/{video_id}/cancel")

        # Give the loop a tick so the cancellation propagates.
        await asyncio.sleep(0.1)
        return {
            "response": (r.status_code, r.json()),
            "task_cancelled": task.cancelled(),
            "flag": flag["v"],
        }

    try:
        result = loop.run_until_complete(runner())
    finally:
        loop.close()

    status, body = result["response"]
    assert status == 200
    assert body == {"ok": True, "cancelled": True}
    assert result["flag"] is True
    # Meta was updated to cancelled
    meta = json.loads(meta_path.read_text())
    assert meta["status"] == "cancelled"
