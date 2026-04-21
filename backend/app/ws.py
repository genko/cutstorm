from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)

_subscribers: Dict[str, Set[WebSocket]] = defaultdict(set)
_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


async def handle(ws: WebSocket, job_id: str) -> None:
    await ws.accept()
    _subscribers[job_id].add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover
        log.debug("ws closed: %s", exc)
    finally:
        _subscribers[job_id].discard(ws)


async def _broadcast(job_id: str, payload: Dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    for ws in list(_subscribers.get(job_id, set())):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for d in dead:
        _subscribers[job_id].discard(d)


def push(job_id: str | None, payload: Dict[str, Any]) -> None:
    if not job_id or _loop is None:
        return
    asyncio.run_coroutine_threadsafe(_broadcast(job_id, payload), _loop)
