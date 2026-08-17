"""Unit tests for Telemetry Collector — CHRONOS v1.0."""

import sys
import types

import pytest

from chronos.telemetry import TelemetryCollector, TelemetryConfig


@pytest.fixture
def collector() -> TelemetryCollector:
    return TelemetryCollector(TelemetryConfig(enabled=True))


def _install_fake_httpx(
    monkeypatch: pytest.MonkeyPatch,
    *,
    status_code: int = 204,
    raise_http_error: bool = False,
) -> None:
    class FakeHTTPError(Exception):
        pass

    class FakeResponse:
        def __init__(self) -> None:
            self.status_code = status_code

    def post(*_args: object, **_kwargs: object) -> FakeResponse:
        if raise_http_error:
            raise FakeHTTPError("synthetic transport failure")
        return FakeResponse()

    fake = types.ModuleType("httpx")
    fake.HTTPError = FakeHTTPError  # type: ignore[attr-defined]
    fake.post = post  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "httpx", fake)


def test_track(collector: TelemetryCollector) -> None:
    collector.track("feature_used", {"feature": "recall"})
    assert len(collector._buffer) == 1


def test_track_without_anonymization_copies_input() -> None:
    payload = {"feature": "recall"}
    collector = TelemetryCollector(TelemetryConfig(enabled=True, anonymize=False))
    collector.track("feature_used", payload)
    payload["feature"] = "mutated"
    assert collector._buffer[0].event_data["feature"] == "recall"


def test_flush_without_endpoint_retains_buffer(collector: TelemetryCollector) -> None:
    collector.track("event", {"key": "value"})
    assert collector.flush() == 0
    assert len(collector._buffer) == 1
    assert collector._total_sent == 0


def test_flush_clears_only_after_success(
    collector: TelemetryCollector, monkeypatch: pytest.MonkeyPatch
) -> None:
    collector.track("event", {"key": "value"})
    monkeypatch.setattr(collector, "_send", lambda events: bool(events))
    assert collector.flush() == 1
    assert collector._buffer == []
    assert collector._total_sent == 1


def test_real_send_success_clears_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_httpx(monkeypatch, status_code=204)
    collector = TelemetryCollector(
        TelemetryConfig(enabled=True, endpoint="https://telemetry.example.com/v1")
    )
    collector.track("event", {"feature": "recall"})
    assert collector.flush() == 1
    assert collector._buffer == []


def test_real_send_non_success_retains_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_httpx(monkeypatch, status_code=503)
    collector = TelemetryCollector(
        TelemetryConfig(enabled=True, endpoint="https://telemetry.example.com/v1")
    )
    collector.track("event", {"feature": "recall"})
    assert collector.flush() == 0
    assert len(collector._buffer) == 1


def test_real_send_transport_error_retains_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_httpx(monkeypatch, raise_http_error=True)
    collector = TelemetryCollector(
        TelemetryConfig(enabled=True, endpoint="https://telemetry.example.com/v1")
    )
    collector.track("event", {"feature": "recall"})
    assert collector.flush() == 0
    assert len(collector._buffer) == 1


def test_missing_httpx_retains_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "httpx", None)
    collector = TelemetryCollector(
        TelemetryConfig(enabled=True, endpoint="https://telemetry.example.com/v1")
    )
    collector.track("event", {"feature": "recall"})
    assert collector.flush() == 0
    assert len(collector._buffer) == 1


def test_opt_out(collector: TelemetryCollector) -> None:
    collector.opt_out()
    collector.track("event", {"key": "value"})
    assert len(collector._buffer) == 0


def test_opt_in() -> None:
    c = TelemetryCollector(TelemetryConfig(enabled=False))
    c.track("event", {})
    assert len(c._buffer) == 0
    c.opt_in()
    c.track("event", {})
    assert len(c._buffer) == 1


def test_status(collector: TelemetryCollector) -> None:
    status = collector.status()
    assert status["opted_in"] is True
    assert "session_id" in status
    assert status["endpoint"] == "disabled"


def test_anonymize_is_recursive(collector: TelemetryCollector) -> None:
    data = {
        "user": "synthetic-user",
        "email": "synthetic@example.com",
        "feature": "recall",
        "nested": {"authorization": "Bearer secret", "safe": "ok"},
        "items": [{"content": "private text", "count": 1}],
        "long": "x" * 201,
    }
    clean = collector._anonymize(data)
    assert clean["user"] == "[redacted]"
    assert clean["email"] == "[redacted]"
    assert clean["feature"] == "recall"
    assert clean["nested"] == {"authorization": "[redacted]", "safe": "ok"}
    assert clean["items"] == [{"content": "[redacted]", "count": 1}]
    assert clean["long"] == "[string:201chars]"


def test_auto_flush_failure_retains_events(collector: TelemetryCollector) -> None:
    collector._cfg.buffer_size = 2
    collector.track("e1", {})
    collector.track("e2", {})
    assert len(collector._buffer) == 2


def test_auto_flush_success_clears_events(
    collector: TelemetryCollector, monkeypatch: pytest.MonkeyPatch
) -> None:
    collector._cfg.buffer_size = 2
    monkeypatch.setattr(collector, "_send", lambda events: bool(events))
    collector.track("e1", {})
    collector.track("e2", {})
    assert collector._buffer == []
    assert collector._total_sent == 2


def test_invalid_endpoint_fails_closed_and_retains_buffer() -> None:
    collector = TelemetryCollector(
        TelemetryConfig(enabled=True, endpoint="http://127.0.0.1:9000/telemetry")
    )
    collector.track("event", {"safe": "value"})
    with pytest.raises(ValueError, match="HTTPS"):
        collector.flush()
    assert len(collector._buffer) == 1
