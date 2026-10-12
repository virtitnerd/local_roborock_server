import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import roborock_local_server.backend  # noqa: F401  (puts the bundled `shared` package on sys.path)
from conftest import write_release_config
from roborock_local_server.config import load_config, resolve_paths
from roborock_local_server.server import ReleaseSupervisor
from shared import schedule_view

QREVO = "2e2txkqKqxVifcIdyOT1lY"
NEW_YORK = "America/New_York"


def _cloud_job(job_id=3549431, cron="00 11 ? * 1,3,5", enabled=True, **extra):
    job = {
        "id": job_id,
        "cron": cron,
        "timeZoneId": NEW_YORK,
        "repeated": True,
        "enabled": enabled,
        "param": {
            "id": 1,
            "method": "server_scheduled_start",
            "params": [{"repeat": 1, "water_box_mode": 203, "segments": "0", "fan_power": 104, "mop_mode": 300}],
        },
    }
    job.update(extra)
    return job


def test_build_cron_from_the_editor_fields():
    assert schedule_view.build_cron("07:30", [1, 3, 5]) == "30 7 * * 1,3,5"
    assert schedule_view.build_cron("07:05", [0, 6]) == "5 7 * * 0,6"
    assert schedule_view.build_cron("23:59", []) == "59 23 * * *"
    assert schedule_view.build_cron("06:00", range(7)) == "0 6 * * *"


@pytest.mark.parametrize(
    ("time_text", "weekdays"),
    [("7:3x", []), ("24:00", []), ("", []), ("07:30", [7]), ("07:30", ["mon"])],
)
def test_build_cron_rejects_bad_input(time_text, weekdays):
    with pytest.raises(schedule_view.ScheduleInputError):
        schedule_view.build_cron(time_text, weekdays)


def test_job_view_reads_a_simple_weekly_cloud_schedule():
    now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
    view = schedule_view.job_view(_cloud_job(), now=now)

    assert view["simple"] is True
    assert (view["time"], view["weekdays"]) == ("11:00", [1, 3, 5])
    assert view["next_fire_time"] == "2026-09-28T15:00:00Z"
    assert view["settings"]["water_box_mode"] == 203


def test_job_view_marks_every_day_and_unrepresentable_crons():
    every_day = schedule_view.job_view(_cloud_job(cron="30 7 * * *"))
    assert (every_day["simple"], every_day["weekdays"]) == (True, [])

    dated = schedule_view.job_view(_cloud_job(cron="03 13 15 12 ?"))
    assert dated["simple"] is False and dated["time"] is None

    twice_daily = schedule_view.job_view(_cloud_job(cron="0 7,19 * * *"))
    assert twice_daily["simple"] is False


def test_disabled_job_has_no_next_run():
    assert schedule_view.job_view(_cloud_job(enabled=False))["next_fire_time"] is None


def _client(tmp_path: Path, jobs: list[dict]) -> tuple[TestClient, Path]:
    config_file = write_release_config(tmp_path)
    config = load_config(config_file)
    paths = resolve_paths(config_file, config)
    paths.inventory_path.parent.mkdir(parents=True, exist_ok=True)
    paths.inventory_path.write_text(
        json.dumps(
            {
                "home": {"id": 1, "name": "Home"},
                "devices": [{"duid": QREVO, "name": "Quevo"}],
                "schedules": {QREVO: jobs},
            }
        ),
        encoding="utf-8",
    )
    supervisor = ReleaseSupervisor(config=config, paths=paths)
    supervisor.refresh_inventory_state()
    client = TestClient(supervisor.app)
    assert client.post("/admin/api/login", json={"password": "correct horse battery staple"}).status_code == 200
    return client, paths.inventory_path


def _stored(inventory_path: Path) -> list[dict]:
    return json.loads(inventory_path.read_text(encoding="utf-8"))["schedules"][QREVO]


def test_schedules_are_listed_for_a_vacuum(tmp_path):
    client, _ = _client(tmp_path, [_cloud_job()])

    payload = client.get(f"/admin/api/vacuums/{QREVO}/schedules").json()

    assert payload["duid"] == QREVO
    (job,) = payload["schedules"]
    assert (job["time"], job["weekdays"], job["enabled"]) == ("11:00", [1, 3, 5], True)
    assert job["next_fire_time"]


def test_creating_a_vac_only_schedule(tmp_path):
    client, inventory = _client(tmp_path, [])
    body = {
        "time": "07:30",
        "weekdays": [2, 4],
        "enabled": True,
        "settings": {"water_box_mode": 200, "fan_power": 102, "repeat": 1, "mop_mode": None},
    }

    response = client.post(f"/admin/api/vacuums/{QREVO}/schedules", json=body)

    assert response.status_code == 200
    (stored,) = _stored(inventory)
    assert stored["cron"] == "30 7 * * 2,4"
    entry = stored["param"]["params"][0]
    assert (entry["water_box_mode"], entry["fan_power"]) == (200, 102)
    assert "mop_mode" not in entry
    assert stored["timeZoneId"]


def test_changing_the_time_keeps_a_cloud_schedules_vac_and_mop_settings(tmp_path):
    client, inventory = _client(tmp_path, [_cloud_job()])

    response = client.put(
        f"/admin/api/vacuums/{QREVO}/schedules/3549431",
        json={"time": "09:15", "weekdays": [1, 3, 5]},
    )

    assert response.status_code == 200
    (stored,) = _stored(inventory)
    assert stored["cron"] == "15 9 * * 1,3,5"
    entry = stored["param"]["params"][0]
    assert (entry["water_box_mode"], entry["fan_power"], entry["mop_mode"]) == (203, 104, 300)
    assert stored["timeZoneId"] == NEW_YORK


def test_switching_a_schedule_to_vacuum_only_and_toggling_it_off(tmp_path):
    client, inventory = _client(tmp_path, [_cloud_job()])
    url = f"/admin/api/vacuums/{QREVO}/schedules/3549431"

    assert client.put(url, json={"settings": {"water_box_mode": 200}}).status_code == 200
    assert client.put(url, json={"enabled": False}).status_code == 200

    (stored,) = _stored(inventory)
    assert stored["enabled"] is False
    entry = stored["param"]["params"][0]
    assert (entry["water_box_mode"], entry["fan_power"]) == (200, 104)


def test_deleting_a_schedule(tmp_path):
    client, inventory = _client(tmp_path, [_cloud_job(), _cloud_job(job_id=7, cron="0 6 * * *")])

    assert client.delete(f"/admin/api/vacuums/{QREVO}/schedules/3549431").status_code == 200

    assert [job["id"] for job in _stored(inventory)] == [7]


def test_bad_requests_are_rejected_and_nothing_changes(tmp_path):
    client, inventory = _client(tmp_path, [_cloud_job()])
    base = f"/admin/api/vacuums/{QREVO}/schedules"

    assert client.post(base, json={"time": "99:99"}).status_code == 400
    assert client.post(base, json={"time": "07:00", "settings": {"fan_power": "loud"}}).status_code == 400
    assert client.post(base, json={"time": "07:00", "settings": {"bogus": 1}}).status_code == 400
    assert client.put(f"{base}/3549431", json={"time": "07:00"}).status_code == 400  # needs weekdays too
    assert client.put(f"{base}/999", json={"enabled": False}).status_code == 404
    assert client.delete(f"{base}/999").status_code == 404
    assert client.get("/admin/api/vacuums/nope/schedules").status_code == 404

    assert len(_stored(inventory)) == 1


def test_schedule_api_requires_admin_login(tmp_path):
    client, _ = _client(tmp_path, [_cloud_job()])
    client.cookies.clear()

    assert client.get(f"/admin/api/vacuums/{QREVO}/schedules").status_code == 401
    assert client.post(f"/admin/api/vacuums/{QREVO}/schedules", json={"time": "07:00"}).status_code == 401
    assert client.delete(f"/admin/api/vacuums/{QREVO}/schedules/3549431").status_code == 401


def test_dashboard_page_includes_the_schedule_editor(tmp_path):
    client, _ = _client(tmp_path, [])

    page = client.get("/admin").text

    for needle in ('id="scheduleList"', 'id="scheduleForm"', 'id="saveSchedule"', "/schedules"):
        assert needle in page
