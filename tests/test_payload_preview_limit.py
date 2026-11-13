from __future__ import annotations

import pytest

from roborock_local_server.bundled_backend.shared.io_utils import payload_preview


def test_default_keeps_280_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ROBOROCK_SERVER_LOG_PAYLOAD_CHARS", raising=False)
    out = payload_preview(b"a" * 1000)
    assert out == "a" * 280 + "...[truncated]"


def test_environment_raises_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROBOROCK_SERVER_LOG_PAYLOAD_CHARS", "2000")
    assert payload_preview(b"a" * 1000) == "a" * 1000


def test_zero_keeps_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROBOROCK_SERVER_LOG_PAYLOAD_CHARS", "0")
    assert payload_preview(b"a" * 5000) == "a" * 5000
    assert payload_preview(bytes(range(256)) * 20) == (bytes(range(256)) * 20).hex()


def test_a_bad_value_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROBOROCK_SERVER_LOG_PAYLOAD_CHARS", "lots")
    assert payload_preview(b"a" * 1000).endswith("...[truncated]")


def test_an_explicit_argument_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROBOROCK_SERVER_LOG_PAYLOAD_CHARS", "0")
    assert payload_preview(b"a" * 50, max_chars=10) == "a" * 10 + "...[truncated]"
