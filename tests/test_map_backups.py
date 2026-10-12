import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from roborock.roborock_typing import RoborockCommand

import roborock_local_server.backend  # noqa: F401  (puts the bundled `shared` package on sys.path)
from conftest import write_release_config
from roborock_local_server.config import load_config, resolve_paths
from roborock_local_server.server import ReleaseSupervisor
from shared import map_backups
from shared.routine_runner import RoutineExecutionError

QREVO = "2e2txkqKqxVifcIdyOT1lY"

# Shaped like python-roborock's MultiMapsList: one saved map, one backup snapshot.
LISTING = [
    {
        "max_multi_map": 4,
        "max_bak_map": 1,
        "multi_map_count": 1,
        "map_info": [
            {
                "mapFlag": 0,
                "add_time": 1759796753,
                "length": 12,
                "name": "Downstairs",
                "bak_maps": [{"mapFlag": 4, "add_time": 1760000000}],
                "rooms": [{"id": 16, "tag": 14, "iot_name_id": "1", "iot_name": "Kitchen"}, {"id": 17}],
            }
        ],
    }
]


def test_summary_reads_maps_backups_and_limits():
    summary = map_backups.summarize_multi_maps(LISTING)

    assert (summary["max_multi_map"], summary["max_bak_map"], summary["multi_map_count"]) == (4, 1, 1)
    (only,) = summary["maps"]
    assert (only["map_flag"], only["name"], only["room_count"]) == (0, "Downstairs", 2)
    assert only["backups"] == [{"map_flag": 4, "add_time": 1760000000}]


@pytest.mark.parametrize("answer", [None, [], "unknown_method", {"map_info": "nope"}, [{"map_info": [5, None]}]])
def test_summary_survives_answers_in_an_unexpected_shape(answer):
    summary = map_backups.summarize_multi_maps(answer)

    assert summary["maps"] == []


def test_a_map_with_no_backups_lists_none():
    summary = map_backups.summarize_multi_maps([{"map_info": [{"mapFlag": 0, "name": ""}]}])

    assert summary["maps"][0]["backups"] == []


def _read(send):
    return asyncio.run(map_backups.read_map_backups(object(), QREVO, send=send))


def test_reading_asks_only_for_the_two_read_only_listings():
    asked = []

    async def send(command):
        asked.append(command)
        return LISTING if command == RoborockCommand.GET_MULTI_MAPS_LIST else ["whatever"]

    payload = _read(send)

    assert asked == [RoborockCommand.GET_MULTI_MAPS_LIST, RoborockCommand.GET_RECOVER_MAPS]
    assert payload["raw"]["get_recover_maps"] == ["whatever"]
    assert payload["summary"]["maps"][0]["map_flag"] == 0


def test_a_robot_that_will_not_answer_get_recover_maps_still_returns_the_map_list():
    async def send(command):
        if command == RoborockCommand.GET_RECOVER_MAPS:
            raise RoutineExecutionError("Command get_recover_maps timed out after 15.0s")
        return LISTING

    payload = _read(send)

    assert payload["summary"]["maps"][0]["name"] == "Downstairs"
    assert "timed out" in payload["raw"]["get_recover_maps_error"]


def _client(tmp_path: Path) -> TestClient:
    config_file = write_release_config(tmp_path)
    config = load_config(config_file)
    paths = resolve_paths(config_file, config)
    paths.inventory_path.parent.mkdir(parents=True, exist_ok=True)
    paths.inventory_path.write_text(
        json.dumps({"home": {"id": 1}, "devices": [{"duid": QREVO, "name": "Quevo"}]}), encoding="utf-8"
    )
    supervisor = ReleaseSupervisor(config=config, paths=paths)
    supervisor.refresh_inventory_state()
    client = TestClient(supervisor.app)
    assert client.post("/admin/api/login", json={"password": "correct horse battery staple"}).status_code == 200
    return client


def test_maps_endpoint_returns_the_summary(tmp_path, monkeypatch):
    async def fake(ctx, device_id, **kwargs):
        assert device_id == QREVO
        return {"summary": map_backups.summarize_multi_maps(LISTING), "raw": {"get_multi_maps_list": LISTING}}

    monkeypatch.setattr(map_backups, "read_map_backups", fake)

    response = _client(tmp_path).get(f"/admin/api/vacuums/{QREVO}/maps")

    assert response.status_code == 200
    body = response.json()
    assert body["duid"] == QREVO
    assert body["summary"]["maps"][0]["backups"][0]["map_flag"] == 4


def test_maps_endpoint_reports_a_silent_robot_as_a_gateway_timeout(tmp_path, monkeypatch):
    async def fake(ctx, device_id, **kwargs):
        raise RoutineExecutionError("Command get_multi_maps_list timed out after 15.0s")

    monkeypatch.setattr(map_backups, "read_map_backups", fake)

    response = _client(tmp_path).get(f"/admin/api/vacuums/{QREVO}/maps")

    assert response.status_code == 504
    assert "timed out" in response.json()["error"]


def test_maps_endpoint_requires_login_and_a_known_vacuum(tmp_path):
    client = _client(tmp_path)
    assert client.get("/admin/api/vacuums/nope/maps").status_code == 404
    client.cookies.clear()
    assert client.get(f"/admin/api/vacuums/{QREVO}/maps").status_code == 401
