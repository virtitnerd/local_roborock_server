import asyncio

from fastapi.testclient import TestClient

from conftest import write_release_config
from roborock_local_server.cloud import CloudImportManager
from roborock_local_server.config import load_config, resolve_paths
from roborock_local_server.server import ReleaseSupervisor


def _manager(tmp_path, monkeypatch):
    manager = CloudImportManager(inventory_path=tmp_path / "inv.json", snapshot_path=tmp_path / "snap.json")
    calls: list = []

    async def iot(path, params=None):
        calls.append(("iot", path, params))
        if "boom" in path:
            raise RuntimeError("cloud said no")
        return {"ok": path}

    async def web(path, params=None):
        calls.append(("web", path, params))
        return {"web": path}

    monkeypatch.setattr(manager, "iot_get", iot)
    monkeypatch.setattr(manager, "web_get", web)
    return manager, calls


def test_allowed_paths_are_read_and_failures_are_isolated(tmp_path, monkeypatch) -> None:
    manager, calls = _manager(tmp_path, monkeypatch)
    rows = asyncio.run(manager.explore([
        {"path": "/ota/firmware/d1/update", "params": {"lang": "en"}},
        {"path": "/ota/boom"},
        {"path": "/api/v1/beta/user/info", "api": "web"},
        {"path": "/home/checkversion", "params": {"duid": "d1"}},
    ]))

    assert [row.get("result") or row.get("error") for row in rows] == [
        {"ok": "/ota/firmware/d1/update"}, "cloud said no", {"web": "/api/v1/beta/user/info"}, {"ok": "/home/checkversion"},
    ]
    assert calls == [
        ("iot", "/ota/firmware/d1/update", {"lang": "en"}), ("iot", "/ota/boom", None),
        ("web", "/api/v1/beta/user/info", None), ("iot", "/home/checkversion", {"duid": "d1"}),
    ]


def test_anything_outside_the_allowlist_is_refused_without_a_request(tmp_path, monkeypatch) -> None:
    manager, calls = _manager(tmp_path, monkeypatch)
    rows = asyncio.run(manager.explore([
        {"path": "/user/devices/d1"}, {"path": "/ota/../user/homes"}, {"path": "/ota/x?y=1"},
        {"path": "https://evil.example/ota/x"}, "not a dict",
    ]))

    assert all(row["error"] == "path not allowed" for row in rows)
    assert calls == []


def test_the_number_of_requests_is_capped(tmp_path, monkeypatch) -> None:
    manager, calls = _manager(tmp_path, monkeypatch)
    rows = asyncio.run(manager.explore([{"path": f"/ota/{i}"} for i in range(100)]))

    assert len(rows) == len(calls) == manager.EXPLORE_LIMIT


def test_the_admin_endpoint_needs_login_and_a_request_list(tmp_path, monkeypatch) -> None:
    config_file = write_release_config(tmp_path)
    config = load_config(config_file)
    supervisor = ReleaseSupervisor(config=config, paths=resolve_paths(config_file, config))
    client = TestClient(supervisor.app)
    assert client.post("/admin/api/debug/cloud_get", json={"requests": [{"path": "/ota/x"}]}).status_code == 401

    client.post("/admin/api/login", json={"password": "correct horse battery staple"})
    assert client.post("/admin/api/debug/cloud_get", json={}).status_code == 400

    async def fake(requests):
        return [{"path": "/ota/x", "result": 1}]

    monkeypatch.setattr(supervisor.cloud_manager, "explore", fake)
    assert client.post("/admin/api/debug/cloud_get", json={"requests": [{"path": "/ota/x"}]}).json() == {
        "success": True, "rows": [{"path": "/ota/x", "result": 1}],
    }


def test_only_the_firmware_address_route_is_open_under_user_devices(tmp_path, monkeypatch) -> None:
    manager, calls = _manager(tmp_path, monkeypatch)
    rows = asyncio.run(manager.explore([
        {"path": "/user/devices/abc123/fw", "params": {"version": "02.15.26"}},
        {"path": "/user/devices/abc123"}, {"path": "/user/devices/abc123/fw/extra"},
        {"path": "/user/devices/abc123/jobs"}, {"path": "/user/devices//fw"},
    ]))

    assert "result" in rows[0] and all(row["error"] == "path not allowed" for row in rows[1:])
    assert calls == [("iot", "/user/devices/abc123/fw", {"version": "02.15.26"})]
