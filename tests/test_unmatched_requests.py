import json
from pathlib import Path

from fastapi.testclient import TestClient

from conftest import write_release_config
from roborock_local_server.config import load_config, resolve_paths
from roborock_local_server.server import ReleaseSupervisor


def _logged_routes(tmp_path: Path, requests) -> list[str]:
    config_file = write_release_config(tmp_path)
    config = load_config(config_file)
    paths = resolve_paths(config_file, config)
    supervisor = ReleaseSupervisor(config=config, paths=paths)
    client = TestClient(supervisor.app)
    for method, path in requests:
        client.request(method, path)
    if not paths.http_jsonl_path.exists():
        return []
    return [
        (entry.get("method"), entry.get("clean_path"))
        for entry in map(json.loads, paths.http_jsonl_path.read_text(encoding="utf-8").splitlines())
    ]


def test_unmatched_writes_are_kept_in_the_log_but_plain_probes_are_not(tmp_path):
    logged = _logged_routes(
        tmp_path,
        [
            ("GET", "/favicon.ico"),
            ("HEAD", "/healthz"),
            ("POST", "/upload/map/backup"),
            ("PUT", "/some/robot/thing"),
        ],
    )

    assert ("POST", "/upload/map/backup") in logged
    assert ("PUT", "/some/robot/thing") in logged
    assert not any(path in ("/favicon.ico", "/healthz") for _method, path in logged)
