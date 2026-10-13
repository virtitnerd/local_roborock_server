import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient
from roborock.roborock_typing import RoborockCommand

import roborock_local_server.backend  # noqa: F401  (puts the bundled `shared` package on sys.path)
from conftest import write_release_config
from roborock_local_server.config import load_config, resolve_paths
from roborock_local_server.server import ReleaseSupervisor
from shared import capabilities
from shared.routine_runner import RoutineExecutionError

QREVO = "2e2txkqKqxVifcIdyOT1lY"

# What the Qrevo answered to get_smart_wash_params on a real dock.
SMART_WASH = {"smart_wash": 0, "wash_interval": 1200}


def _read(send):
    return asyncio.run(capabilities.read_capabilities(object(), QREVO, send=send))


def test_probes_are_getters_only():
    # A setter or an action in this list would change the robot every time the button is pressed.
    for name in capabilities.PROBE_COMMANDS:
        assert name.startswith(("get_", "app_get_")), name


def test_every_probe_is_asked_and_answers_are_kept_raw():
    asked = []

    async def send(command):
        asked.append(command.value)
        return SMART_WASH if command == RoborockCommand.GET_SMART_WASH_PARAMS else ["ok"]

    payload = _read(send)

    assert set(asked) <= set(capabilities.PROBE_COMMANDS)
    assert payload["raw"]["get_smart_wash_params"] == SMART_WASH
    assert payload["errors"] == {}


def test_a_command_the_robot_does_not_answer_is_reported_and_the_rest_still_run():
    async def send(command):
        if command == RoborockCommand.GET_WASH_WATER_TEMPERATURE:
            raise RoutineExecutionError("Command get_wash_water_temperature timed out after 15.0s")
        return ["ok"]

    payload = _read(send)

    assert "timed out" in payload["errors"]["get_wash_water_temperature"]
    assert payload["raw"]["get_smart_wash_params"] == ["ok"]


def test_the_dock_is_decoded_from_status():
    dock = capabilities.decode_dock([{"dock_type": 9, "has_am": 0}])

    assert dock["dock_type"] == 9
    assert isinstance(dock["capabilities"], list)


def test_status_without_a_dock_type_decodes_to_nothing():
    assert capabilities.decode_dock([{"state": 8}])["dock_type"] is None
    assert capabilities.decode_dock("unknown_method")["dock_type"] is None


def test_feature_flags_in_an_unexpected_shape_decode_to_nothing():
    assert capabilities.decode_features(None) == {"supported": [], "unsupported": []}
    assert capabilities.decode_features(["x"]) == {"supported": [], "unsupported": []}


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


def test_endpoint_returns_the_probe_result(tmp_path, monkeypatch):
    async def fake(ctx, device_id, **kwargs):
        assert device_id == QREVO
        return {"features": {}, "dock": {"dock_type": 9}, "raw": {"get_smart_wash_params": SMART_WASH}, "errors": {}}

    monkeypatch.setattr(capabilities, "read_capabilities", fake)

    response = _client(tmp_path).get(f"/admin/api/vacuums/{QREVO}/capabilities")

    assert response.status_code == 200
    assert response.json()["raw"]["get_smart_wash_params"] == SMART_WASH


def test_endpoint_reports_a_silent_robot_as_a_gateway_timeout(tmp_path, monkeypatch):
    async def fake(ctx, device_id, **kwargs):
        raise RoutineExecutionError("Command app_get_init_status timed out after 15.0s")

    monkeypatch.setattr(capabilities, "read_capabilities", fake)

    assert _client(tmp_path).get(f"/admin/api/vacuums/{QREVO}/capabilities").status_code == 504


def test_endpoint_requires_login_and_a_known_vacuum(tmp_path):
    client = _client(tmp_path)
    assert client.get("/admin/api/vacuums/nope/capabilities").status_code == 404
    client.cookies.clear()
    assert client.get(f"/admin/api/vacuums/{QREVO}/capabilities").status_code == 401
