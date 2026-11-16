"""Experimental TURN over WebSocket at /turn, so a phone can reach the embedded coturn through an HTTPS-only tunnel."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

TURN_WEBSOCKET_PATH = "/turn"
_SUBPROTOCOL = "turn"
_CHUNK = 65536
IDLE_TIMEOUT_SECONDS = 120.0
MAX_CONNECTIONS = 8


def register_turn_websocket_route(
    app: FastAPI,
    *,
    target: Callable[[], tuple[str, int]],
    authorize: Callable[[WebSocket], tuple[bool, str]],
    logger: logging.Logger,
    idle_timeout: float = IDLE_TIMEOUT_SECONDS,
    max_connections: int = MAX_CONNECTIONS,
) -> None:
    """Relay each authorized WebSocket as raw TURN-over-TCP bytes to coturn on loopback."""
    active = 0
    logger.info("TURN over WebSocket (experimental) enabled at %s", TURN_WEBSOCKET_PATH)

    @app.websocket(TURN_WEBSOCKET_PATH)
    async def turn_websocket(websocket: WebSocket) -> None:
        nonlocal active
        client = websocket.client
        peer = f"{client.host}:{client.port}" if client else "unknown"
        allowed, auth_reason = authorize(websocket)
        if not allowed:
            logger.warning("TURN WebSocket (experimental) refused from %s: %s", peer, auth_reason)
            await websocket.close(code=1008)
            return
        if active >= max_connections:
            logger.warning("TURN WebSocket (experimental) refused from %s: %d connections already open", peer, active)
            await websocket.close(code=1013)
            return
        active += 1
        try:
            await _relay(websocket, peer, target, logger, idle_timeout)
        finally:
            active -= 1


async def _relay(
    websocket: WebSocket,
    peer: str,
    target: Callable[[], tuple[str, int]],
    logger: logging.Logger,
    idle_timeout: float,
) -> None:
    host, port = target()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=10)
    except (OSError, asyncio.TimeoutError) as exc:
        logger.warning("TURN WebSocket (experimental): could not reach coturn at %s:%s: %s", host, port, exc)
        await websocket.close(code=1011)
        return
    offered = websocket.scope.get("subprotocols") or []
    await websocket.accept(subprotocol=_SUBPROTOCOL if _SUBPROTOCOL in offered else None)
    logger.info("TURN WebSocket (experimental) opened from %s", peer)
    last_activity = time.monotonic()

    async def ws_to_turn() -> None:
        nonlocal last_activity
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            data = message.get("bytes")
            if data is None:
                raise ValueError("text frames are not allowed")
            last_activity = time.monotonic()
            if data:
                writer.write(data)
                await writer.drain()

    async def turn_to_ws() -> None:
        nonlocal last_activity
        while chunk := await reader.read(_CHUNK):
            last_activity = time.monotonic()
            await websocket.send_bytes(chunk)

    async def watch_idle() -> None:
        while True:
            remaining = idle_timeout - (time.monotonic() - last_activity)
            if remaining <= 0:
                return
            await asyncio.sleep(remaining)

    tasks = {
        asyncio.create_task(ws_to_turn()): "the app",
        asyncio.create_task(turn_to_ws()): "coturn",
        asyncio.create_task(watch_idle()): "the idle timeout",
    }
    reason = "unknown"
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        first = next(iter(done))
        error = first.exception() if not first.cancelled() else None
        reason = f"{tasks[first]} closed it" + (f" ({type(error).__name__}: {error})" if error else "")
    except WebSocketDisconnect:
        reason = "the app disconnected"
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, OSError, RuntimeError, ValueError):
                await task
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
        with contextlib.suppress(RuntimeError, OSError):
            await websocket.close()
        logger.info("TURN WebSocket (experimental) closed: %s", reason)
