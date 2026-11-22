import logging
import socket
import socketserver
import threading

import pytest
from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient

from conftest import write_release_config
from roborock_local_server.config import load_config, resolve_paths
from roborock_local_server.mqtt_websocket import register_mqtt_websocket_route
from roborock_local_server.server import ReleaseSupervisor


class _Echo(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        while data := self.request.recv(4096):
            self.request.sendall(data)


def _echo_server() -> socketserver.ThreadingTCPServer:
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Echo)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _app(port: int) -> FastAPI:
    app = FastAPI()
    register_mqtt_websocket_route(app, target=lambda: ("127.0.0.1", port, False), logger=logging.getLogger("test"))
    return app


def test_bytes_are_relayed_both_ways_with_the_mqtt_subprotocol() -> None:
    server = _echo_server()
    try:
        client = TestClient(_app(server.server_address[1]))
        connect = bytes.fromhex("101000044d5154540402003c0004746573740000")
        with client.websocket_connect("/mqtt", subprotocols=["mqtt"]) as ws:
            assert ws.accepted_subprotocol == "mqtt"
            ws.send_bytes(connect)
            assert ws.receive_bytes() == connect
    finally:
        server.shutdown()
        server.server_close()


def test_an_unreachable_listener_closes_the_websocket() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    client = TestClient(_app(free_port))
    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect("/mqtt", subprotocols=["mqtt"]):
            pass
    assert closed.value.code == 1011


def _supervisor_client(tmp_path, *, enabled: bool) -> TestClient:
    config_file = write_release_config(tmp_path)
    if enabled:
        config_file.write_text(config_file.read_text().replace("[network]\n", "[network]\nmqtt_websocket = true\n", 1))
    config = load_config(config_file)
    assert config.network.mqtt_websocket is enabled
    return TestClient(ReleaseSupervisor(config=config, paths=resolve_paths(config_file, config)).app)


def test_the_route_exists_only_when_mqtt_websocket_is_enabled(tmp_path) -> None:
    # Enabled with no broker listening, the handler accepts the route and closes with 1011.
    with pytest.raises(WebSocketDisconnect) as enabled:
        with _supervisor_client(tmp_path / "on", enabled=True).websocket_connect("/mqtt", subprotocols=["mqtt"]):
            pass
    with pytest.raises(WebSocketDisconnect) as disabled:
        with _supervisor_client(tmp_path / "off", enabled=False).websocket_connect("/mqtt", subprotocols=["mqtt"]):
            pass
    assert enabled.value.code == 1011
    assert disabled.value.code != 1011
