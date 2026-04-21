from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models import Position, Size, Style


def test_export_pushes_progress(sample_video: Path) -> None:
    client = TestClient(app)
    with client:
        data = sample_video.read_bytes()
        r = client.post(
            "/api/transcribe",
            files={"file": ("sample_5s.mp4", io.BytesIO(data), "video/mp4")},
        )
        assert r.status_code == 200
        video_id = r.json()["video_id"]

        messages: list[dict] = []
        with client.websocket_connect(f"/ws/progress/job-1") as ws:
            import threading

            def export_call() -> None:
                client.post(
                    "/api/export?job_id=job-1",
                    json={
                        "video_id": video_id,
                        "segments": [{"start": 0.0, "end": 1.0, "text": "hello"}],
                        "style": Style().model_dump(),
                        "position": Position().model_dump(),
                        "size": Size().model_dump(),
                    },
                )

            t = threading.Thread(target=export_call)
            t.start()

            while t.is_alive() or True:
                try:
                    msg = ws.receive_json(mode="text")
                    messages.append(msg)
                    if msg.get("phase") == "encode" and msg.get("percent") == 100:
                        break
                except Exception:
                    break
            t.join(timeout=30)

        encode_messages = [m for m in messages if m.get("phase") == "encode"]
        assert len(encode_messages) >= 2
        percents = [m["percent"] for m in encode_messages]
        assert percents[0] <= percents[-1]
        assert percents[-1] == 100
