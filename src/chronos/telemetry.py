"""Anonymous opt-in usage telemetry — CHRONOS v1.0."""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import asdict, dataclass
from typing import Any

from chronos.outbound_security import validate_operator_https_url

JSONDict = dict[str, Any]


@dataclass
class TelemetryEvent:
    event_type: str
    event_data: JSONDict
    session_id: str
    timestamp: int
    version: str = "1.0.0"


@dataclass
class TelemetryConfig:
    enabled: bool = False
    endpoint: str = ""
    session_id: str = ""
    flush_interval_sec: int = 300
    buffer_size: int = 100
    anonymize: bool = True


class TelemetryCollector:
    """Collect anonymous usage telemetry only after explicit opt-in."""

    def __init__(self, config: TelemetryConfig | None = None):
        self._cfg = config or TelemetryConfig()
        self._buffer: list[TelemetryEvent] = []
        self._session_id = self._cfg.session_id or hashlib.sha256(os.urandom(16)).hexdigest()[:16]
        self._opted_in = self._cfg.enabled
        self._total_sent = 0

    def track(self, event_type: str, data: JSONDict) -> None:
        if not self._opted_in:
            return
        clean_data = self._anonymize(data) if self._cfg.anonymize else dict(data)
        event = TelemetryEvent(
            event_type=event_type,
            event_data=clean_data,
            session_id=self._session_id,
            timestamp=int(time.time() * 1000),
        )
        self._buffer.append(event)
        if len(self._buffer) >= self._cfg.buffer_size:
            self.flush()

    def flush(self) -> int:
        """Deliver buffered events and retain them when delivery fails."""
        if not self._buffer or not self._opted_in:
            return 0
        events = list(self._buffer)
        if not self._send(events):
            return 0
        del self._buffer[: len(events)]
        self._total_sent += len(events)
        return len(events)

    def opt_in(self) -> None:
        self._opted_in = True

    def opt_out(self) -> None:
        self._opted_in = False
        self._buffer.clear()

    def status(self) -> JSONDict:
        return {
            "opted_in": self._opted_in,
            "session_id": self._session_id,
            "buffered_events": len(self._buffer),
            "total_sent": self._total_sent,
            "endpoint": self._cfg.endpoint if self._opted_in and self._cfg.endpoint else "disabled",
        }

    def _anonymize(self, data: JSONDict) -> JSONDict:
        clean: JSONDict = {}
        sensitive_keys = {
            "user",
            "username",
            "email",
            "api_key",
            "authorization",
            "token",
            "password",
            "secret",
            "ip",
            "path",
            "content",
            "prompt",
            "query",
        }
        for key, value in data.items():
            if key.lower() in sensitive_keys:
                clean[key] = "[redacted]"
            elif isinstance(value, dict):
                clean[key] = self._anonymize(value)
            elif isinstance(value, list):
                clean[key] = [
                    self._anonymize(item) if isinstance(item, dict) else item for item in value
                ]
            elif isinstance(value, str) and len(value) > 200:
                clean[key] = f"[string:{len(value)}chars]"
            else:
                clean[key] = value
        return clean

    def _validated_endpoint(self) -> str | None:
        endpoint = self._cfg.endpoint.strip()
        if not endpoint:
            return None
        return validate_operator_https_url(endpoint)

    def _send(self, events: list[TelemetryEvent]) -> bool:
        endpoint = self._validated_endpoint()
        if endpoint is None:
            return False

        try:
            import httpx
        except ImportError:
            return False

        try:
            response = httpx.post(
                endpoint,
                json={"events": [asdict(event) for event in events]},
                timeout=10.0,
                follow_redirects=False,
            )
            return 200 <= response.status_code < 300
        except (OSError, httpx.HTTPError):
            return False
