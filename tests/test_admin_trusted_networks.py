from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import write_release_config
from fastapi.testclient import TestClient

from roborock_local_server.config import load_config, resolve_paths
from roborock_local_server.security import (
    address_in_networks,
    parse_trusted_networks,
)
from roborock_local_server.server import ReleaseSupervisor

ENV = "ROBOROCK_SERVER_ADMIN_TRUSTED_NETWORKS"


def test_networks_parse_from_commas_and_spaces_and_reject_bad_entries() -> None:
    networks, rejected = parse_trusted_networks(
        "10.0.50.0/24, 10.0.30.15 fd00::/8 nonsense 0.0.0.0/0"
    )
    assert [str(n) for n in networks] == ["10.0.50.0/24", "10.0.30.15/32", "fd00::/8"]
    assert rejected == ["nonsense", "0.0.0.0/0"]


def test_an_address_matches_only_inside_the_networks() -> None:
    networks, _ = parse_trusted_networks("10.0.50.0/24")
    assert address_in_networks("10.0.50.8", networks)
    assert not address_in_networks("10.0.51.8", networks)
    assert not address_in_networks("fd00::1", networks)
    assert not address_in_networks("testclient", networks)
    assert not address_in_networks(None, networks)
    assert not address_in_networks("10.0.50.8", [])


def _supervisor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, networks: str | None
) -> ReleaseSupervisor:
    if networks is None:
        monkeypatch.delenv(ENV, raising=False)
    else:
        monkeypatch.setenv(ENV, networks)
    config_file = write_release_config(tmp_path)
    config = load_config(config_file)
    paths = resolve_paths(config_file, config)
    paths.inventory_path.parent.mkdir(parents=True, exist_ok=True)
    paths.inventory_path.write_text(
        json.dumps(
            {
                "devices": [
                    {
                        "duid": "debug-duid",
                        "name": "Debug",
                        "model": "roborock.vacuum.a101",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return ReleaseSupervisor(config=config, paths=paths)


@pytest.fixture
def fake_mqtt(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    sent: list[str] = []

    class FakeRoutineMqttClient:
        def __init__(self, context, device, logger):
            pass

        async def connect(self):
            pass

        async def send_command(self, method, params):
            sent.append(method)
            return {"ok": True}

        async def close(self):
            pass

    monkeypatch.setattr(
        "roborock_local_server.standalone_admin._RoutineMqttClient",
        FakeRoutineMqttClient,
    )
    return sent


def _post(client: TestClient, method: str, **extra):
    return client.post(
        "/admin/api/debug/send_command",
        json={"duid": "debug-duid", "method": method},
        **extra,
    )


def test_a_trusted_address_has_full_access_without_a_login(tmp_path, monkeypatch, fake_mqtt) -> None:
    supervisor = _supervisor(tmp_path, monkeypatch, "10.0.50.0/27")
    client = TestClient(supervisor.app, client=("10.0.50.8", 50000))
    assert _post(client, "get_dynamic_map_diff").status_code == 200
    assert _post(client, "app_charge").status_code == 200
    assert fake_mqtt == ["get_dynamic_map_diff", "app_charge"]
    for path in ("/admin/api/status", "/admin/api/vacuums", "/admin/api/activity"):
        assert client.get(path).status_code == 200, path


def test_other_addresses_and_forged_headers_get_nothing(
    tmp_path, monkeypatch, fake_mqtt
) -> None:
    supervisor = _supervisor(tmp_path, monkeypatch, "10.0.50.0/24")
    client = TestClient(supervisor.app, client=("203.0.113.9", 50000))
    assert _post(client, "get_status").status_code == 401
    forged = _post(
        client,
        "get_status",
        headers={"X-Forwarded-For": "10.0.50.8", "X-Real-IP": "10.0.50.8"},
    )
    assert forged.status_code == 401
    assert fake_mqtt == []


def test_nothing_changes_when_the_setting_is_not_used(
    tmp_path, monkeypatch, fake_mqtt
) -> None:
    supervisor = _supervisor(tmp_path, monkeypatch, None)
    client = TestClient(supervisor.app, client=("10.0.50.8", 50000))
    assert _post(client, "get_status").status_code == 401
    assert fake_mqtt == []


def test_the_edges_of_the_range_are_respected(tmp_path, monkeypatch, fake_mqtt) -> None:
    supervisor = _supervisor(tmp_path, monkeypatch, "10.0.50.0/27")
    inside = TestClient(supervisor.app, client=("10.0.50.31", 50000))
    outside = TestClient(supervisor.app, client=("10.0.50.32", 50000))
    assert inside.get("/admin/api/status").status_code == 200
    assert outside.get("/admin/api/status").status_code == 401


def test_the_login_still_works_for_everyone_else(tmp_path, monkeypatch, fake_mqtt) -> None:
    supervisor = _supervisor(tmp_path, monkeypatch, "10.0.50.0/27")
    client = TestClient(supervisor.app, client=("203.0.113.9", 50000))
    assert client.get("/admin/api/status").status_code == 401
    client.post("/admin/api/login", json={"password": "correct horse battery staple"})
    assert client.get("/admin/api/status").status_code == 200
