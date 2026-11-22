"""MQTT over WebSocket at /mqtt, for apps that can only reach the server through an HTTPS-only tunnel."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import ssl
from collections.abc import Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

MQTT_WEBSOCKET_PATH = "/mqtt"
_SUBPROTOCOLS = ("mqtt", "mqttv3.1")
_CHUNK = 65536


def _local_tls_context() -> ssl.SSLContext:
    # Loopback to our own proxy, whose certificate names the public host, not 127.0.0.1.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def register_mqtt_websocket_route(
    app: FastAPI,
    *,
    target: Callable[[], tuple[str, int, bool]],
    logger: logging.Logger,
) -> None:
    """Relay each WebSocket to the MQTT TLS proxy, so it gets the same handling as a direct connection."""

    @app.websocket(MQTT_WEBSOCKET_PATH)
    async def mqtt_websocket(websocket: WebSocket) -> None:
        offered = websocket.scope.get("subprotocols") or []
        subprotocol = next((p for p in offered if p in _SUBPROTOCOLS), None)
        host, port, tls = target()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port, ssl=_local_tls_context() if tls else None),
                timeout=10,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            logger.warning("MQTT WebSocket: could not reach the MQTT listener %s:%s: %s", host, port, exc)
            await websocket.close(code=1011)
            return
        await websocket.accept(subprotocol=subprotocol)
        client = websocket.client
        logger.info("MQTT WebSocket opened from %s", f"{client.host}:{client.port}" if client else "unknown")

        async def ws_to_mqtt() -> None:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return
                data = message.get("bytes")
                if data is None and message.get("text") is not None:
                    data = message["text"].encode()
                if data:
                    writer.write(data)
                    await writer.drain()

        async def mqtt_to_ws() -> None:
            while chunk := await reader.read(_CHUNK):
                await websocket.send_bytes(chunk)

        tasks = {
            asyncio.create_task(ws_to_mqtt()): "the app",
            asyncio.create_task(mqtt_to_ws()): "the MQTT listener",
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
                with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, OSError, RuntimeError):
                    await task
            writer.close()
            with contextlib.suppress(OSError, ssl.SSLError):
                await writer.wait_closed()
            with contextlib.suppress(RuntimeError, OSError):
                await websocket.close()
            logger.info("MQTT WebSocket closed: %s", reason)
