"""Security regressions for the experimental plugin marketplace."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from chronos.marketplace import MarketplaceConfig, PluginMarketplace


def _repo() -> MagicMock:
    repo = MagicMock()
    repo.storage.conn.execute.return_value.fetchall.return_value = []
    return repo


def _manifest(plugin_id: str = "plugin.example") -> dict[str, object]:
    return {
        "plugin_id": plugin_id,
        "name": "Synthetic Plugin",
        "version": "1.0.0",
        "author_did": "did:example:test",
        "description": "synthetic test manifest",
        "hooks": [],
    }


def _install_fake_httpx(
    monkeypatch: pytest.MonkeyPatch,
    *,
    status_code: int = 200,
    payload: dict[str, object] | None = None,
) -> None:
    class FakeHTTPError(Exception):
        pass

    class FakeResponse:
        def __init__(self) -> None:
            self.status_code = status_code

        def json(self) -> dict[str, object]:
            return payload or {}

    class FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, _url: str, **_kwargs: object) -> FakeResponse:
            return FakeResponse()

    fake = types.ModuleType("httpx")
    fake.AsyncClient = FakeClient  # type: ignore[attr-defined]
    fake.HTTPError = FakeHTTPError  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "httpx", fake)


@pytest.mark.asyncio
async def test_marketplace_search_is_inert_when_disabled() -> None:
    marketplace = PluginMarketplace(_repo(), MarketplaceConfig())
    assert await marketplace.search("anything") == []


@pytest.mark.asyncio
async def test_marketplace_install_is_blocked_when_disabled() -> None:
    marketplace = PluginMarketplace(_repo(), MarketplaceConfig())
    with pytest.raises(RuntimeError, match="disabled"):
        await marketplace.install("plugin.example")


@pytest.mark.asyncio
async def test_marketplace_enabled_requires_registry() -> None:
    marketplace = PluginMarketplace(_repo(), MarketplaceConfig(enabled=True))
    with pytest.raises(RuntimeError, match="registry_url"):
        await marketplace.install("plugin.example")


@pytest.mark.asyncio
async def test_marketplace_rejects_local_registry() -> None:
    marketplace = PluginMarketplace(
        _repo(),
        MarketplaceConfig(enabled=True, registry_url="http://127.0.0.1:9000"),
    )
    with pytest.raises(ValueError, match="HTTPS"):
        await marketplace.install("plugin.example")


@pytest.mark.asyncio
async def test_marketplace_signature_verification_fails_closed() -> None:
    marketplace = PluginMarketplace(
        _repo(),
        MarketplaceConfig(
            enabled=True,
            registry_url="https://plugins.example.com/api",
            verify_signatures=True,
        ),
    )
    with pytest.raises(RuntimeError, match="trusted signature verification is not implemented"):
        await marketplace.install("plugin.example")


@pytest.mark.asyncio
async def test_marketplace_search_parses_manifest_when_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_httpx(
        monkeypatch,
        payload={"plugins": [_manifest()]},
    )
    marketplace = PluginMarketplace(
        _repo(),
        MarketplaceConfig(enabled=True, registry_url="https://plugins.example.com/api"),
    )
    results = await marketplace.search("synthetic")
    assert len(results) == 1
    assert results[0].plugin_id == "plugin.example"


@pytest.mark.asyncio
async def test_marketplace_search_non_success_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_httpx(monkeypatch, status_code=503)
    marketplace = PluginMarketplace(
        _repo(),
        MarketplaceConfig(enabled=True, registry_url="https://plugins.example.com/api"),
    )
    assert await marketplace.search("synthetic") == []


@pytest.mark.asyncio
async def test_marketplace_operator_trusted_install_requires_explicit_verification_disable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_httpx(monkeypatch, payload={"manifest": _manifest()})
    repo = _repo()
    marketplace = PluginMarketplace(
        repo,
        MarketplaceConfig(
            enabled=True,
            registry_url="https://plugins.example.com/api",
            verify_signatures=False,
        ),
    )
    await marketplace.install("plugin.example")
    assert marketplace.installed()[0].plugin_id == "plugin.example"
    assert repo.storage.conn.commit.called


@pytest.mark.asyncio
async def test_marketplace_install_non_success_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_httpx(monkeypatch, status_code=503)
    marketplace = PluginMarketplace(
        _repo(),
        MarketplaceConfig(
            enabled=True,
            registry_url="https://plugins.example.com/api",
            verify_signatures=False,
        ),
    )
    with pytest.raises(RuntimeError, match="HTTP 503"):
        await marketplace.install("plugin.example")
