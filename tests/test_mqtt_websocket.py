import logging
import socket
import socketserver
import threading

import pytest
from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient

from roborock_local_server.mqtt_websocket import register_mqtt_websocket_route


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
