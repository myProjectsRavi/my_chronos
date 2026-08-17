"""Security tests for operator-configured outbound endpoints."""

import pytest

from chronos.outbound_security import validate_operator_https_url


def test_accepts_public_https_hostname_and_global_literal() -> None:
    assert (
        validate_operator_https_url("https://telemetry.example.com/v1")
        == "https://telemetry.example.com/v1"
    )
    assert validate_operator_https_url("https://8.8.8.8/v1") == "https://8.8.8.8/v1"


def test_rejects_empty_and_plain_http() -> None:
    with pytest.raises(ValueError, match="empty"):
        validate_operator_https_url("  ")
    with pytest.raises(ValueError, match="HTTPS"):
        validate_operator_https_url("http://example.com")


def test_rejects_missing_host_localhost_and_private_literal_ip() -> None:
    with pytest.raises(ValueError, match="hostname"):
        validate_operator_https_url("https:///v1")
    with pytest.raises(ValueError, match="Local"):
        validate_operator_https_url("https://localhost/v1")
    with pytest.raises(ValueError, match="globally routable"):
        validate_operator_https_url("https://127.0.0.1/v1")


def test_rejects_embedded_credentials_and_fragments() -> None:
    with pytest.raises(ValueError, match="credentials"):
        validate_operator_https_url("https://user:pass@example.com/v1")
    with pytest.raises(ValueError, match="fragments"):
        validate_operator_https_url("https://example.com/v1#secret")


def test_rejects_invalid_port() -> None:
    with pytest.raises(ValueError, match="invalid port"):
        validate_operator_https_url("https://example.com:99999/v1")


def test_exact_allowlist_is_enforced_and_normalized() -> None:
    assert (
        validate_operator_https_url(
            "https://plugins.example.com/api",
            allowed_hosts=[" PLUGINS.EXAMPLE.COM. "],
        )
        == "https://plugins.example.com/api"
    )
    with pytest.raises(ValueError, match="allowlist is empty"):
        validate_operator_https_url("https://plugins.example.com/api", allowed_hosts=[])
    with pytest.raises(ValueError, match="allowlist"):
        validate_operator_https_url(
            "https://plugins.example.com/api", allowed_hosts=["registry.example.com"]
        )
