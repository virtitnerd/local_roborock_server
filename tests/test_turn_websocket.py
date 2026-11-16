import logging
import socketserver
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient

from conftest import write_release_config
from roborock_local_server.config import load_config, resolve_paths
from roborock_local_server.server import ReleaseSupervisor
from roborock_local_server.turn_websocket import register_turn_websocket_route
from shared.protocol_auth import ProtocolAuthStore, build_hawk_authorization
from test_protocol_auth import _seed_cloud_snapshot, _write_json


class _Echo(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        while data := self.request.recv(4096):
            self.request.sendall(data)


def _echo_server() -> socketserver.ThreadingTCPServer:
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Echo)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _supervisor(tmp_path: Path, echo_port: int, *, protocol_auth_enabled: bool = True) -> ReleaseSupervisor:
    config_file = write_release_config(tmp_path, protocol_auth_enabled=protocol_auth_enabled)
    config_file.write_text(
        config_file.read_text()
        + f'\n[turn]\nmode="provided"\nhost="127.0.0.1"\npassword="secret"\nport={echo_port}\nwebsocket=true\n'
    )
    config = load_config(config_file)
    paths = resolve_paths(config_file, config)
    _write_json(paths.inventory_path, {"home": {"id": 12345, "name": "Test Home"}, "devices": []})
    _seed_cloud_snapshot(paths.cloud_snapshot_path)
    return ReleaseSupervisor(config=config, paths=paths)


def _hawk(tmp_path: Path, **overrides: object) -> dict[str, str]:
    user = ProtocolAuthStore(resolve_paths(tmp_path / "config.toml", load_config(tmp_path / "config.toml")).cloud_snapshot_path).availability().user
    assert user is not None
    args = {"user": user, "path": "/turn", "timestamp": int(time.time()), "nonce": "turn-nonce"}
    args.update(overrides)
    return {"Authorization": build_hawk_authorization(**args)}


def _connect(client: TestClient, headers: dict[str, str] | None = None):
    return client.websocket_connect("/turn", subprotocols=["turn"], headers=headers or {})


def _refused_code(client: TestClient, headers: dict[str, str] | None = None) -> int:
    with pytest.raises(WebSocketDisconnect) as closed:
        with _connect(client, headers):
            pass
    return closed.value.code


def test_connection_without_authorization_is_refused(tmp_path: Path) -> None:
    server = _echo_server()
    try:
        client = TestClient(_supervisor(tmp_path, server.server_address[1]).app)
        assert _refused_code(client) == 1008
    finally:
        server.shutdown()
        server.server_close()


def test_connection_with_a_bad_hawk_is_refused(tmp_path: Path) -> None:
    server = _echo_server()
    try:
        client = TestClient(_supervisor(tmp_path, server.server_address[1]).app)
        headers = _hawk(tmp_path)
        headers["Authorization"] = headers["Authorization"][:-3] + 'xx"'
        assert _refused_code(client, headers) == 1008
        assert _refused_code(client, _hawk(tmp_path, path="/other", nonce="n2")) == 1008
    finally:
        server.shutdown()
        server.server_close()


def test_valid_hawk_relays_bytes_both_ways(tmp_path: Path) -> None:
    server = _echo_server()
    try:
        client = TestClient(_supervisor(tmp_path, server.server_address[1]).app)
        with _connect(client, _hawk(tmp_path)) as ws:
            assert ws.accepted_subprotocol == "turn"
            ws.send_bytes(b"\x00\x01stun-binding")
            assert ws.receive_bytes() == b"\x00\x01stun-binding"
    finally:
        server.shutdown()
        server.server_close()


def test_connection_is_refused_when_protocol_auth_is_disabled(tmp_path: Path) -> None:
    server = _echo_server()
    try:
        client = TestClient(_supervisor(tmp_path, server.server_address[1], protocol_auth_enabled=False).app)
        assert _refused_code(client, _hawk(tmp_path)) == 1008
    finally:
        server.shutdown()
        server.server_close()


def test_route_is_absent_unless_websocket_is_enabled(tmp_path: Path) -> None:
    config_file = write_release_config(tmp_path)
    config = load_config(config_file)
    paths = resolve_paths(config_file, config)
    client = TestClient(ReleaseSupervisor(config=config, paths=paths).app)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/turn"):
            pass


def _plain_app(port: int, **kwargs: object) -> FastAPI:
    app = FastAPI()
    register_turn_websocket_route(
        app, target=lambda: ("127.0.0.1", port), authorize=lambda ws: (True, "ok"),
        logger=logging.getLogger("test"), **kwargs,
    )
    return app


def test_connections_beyond_the_cap_are_closed_with_1013() -> None:
    server = _echo_server()
    try:
        client = TestClient(_plain_app(server.server_address[1], max_connections=1))
        with _connect(client):
            assert _refused_code(client) == 1013
    finally:
        server.shutdown()
        server.server_close()


def test_idle_connection_is_closed() -> None:
    server = _echo_server()
    try:
        client = TestClient(_plain_app(server.server_address[1], idle_timeout=0.3))
        with _connect(client) as ws:
            with pytest.raises(WebSocketDisconnect):
                ws.receive_bytes()
    finally:
        server.shutdown()
        server.server_close()
