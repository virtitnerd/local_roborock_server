import roborock_local_server.backend  # noqa: F401  (puts the bundled `shared` package on sys.path)
from shared.schedule_store import job_settings, mirrors_server_timer


def _job(**entry_overrides):
    entry = {"repeat": 1, "fan_power": 104, "water_box_mode": 203}
    entry.update(entry_overrides)
    return {"id": "1", "enabled": True, "param": {"params": [entry]}}


def test_job_settings_carries_name_when_present():
    # "name" is the official app's own marker, not a JOB_SETTING_KEYS vac/mop setting, confirmed
    # live in its POST/PUT /user/devices/{duid}/jobs body.
    job = _job(name="1759965417864")
    assert job_settings(job) == {"repeat": 1, "fan_power": 104, "water_box_mode": 203, "name": "1759965417864"}


def test_job_settings_omits_name_when_absent_or_blank():
    assert "name" not in job_settings(_job())
    assert "name" not in job_settings(_job(name=""))
    assert "name" not in job_settings(_job(name=None))


def test_mirrors_server_timer_is_true_only_when_a_name_is_present():
    assert mirrors_server_timer(_job(name="1759965417864")) is True
    assert mirrors_server_timer(_job()) is False
    assert mirrors_server_timer(_job(name="")) is False
    assert mirrors_server_timer({}) is False
