"""Experimental plugin discovery metadata for CHRONOS v0.6.

The marketplace is disabled by default. The secure public-release candidate does
not claim to verify plugin signatures because no trusted signer/key-distribution
model is implemented in this module. When signature verification is requested,
plugin installation therefore fails closed instead of treating a non-empty
signature as proof of authenticity.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from chronos.outbound_security import validate_operator_https_url

logger = logging.getLogger(__name__)


@dataclass
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    author_did: str
    description: str
    hooks: list[str]
    runtime: str = "wasm"
    permissions: list[str] = field(default_factory=list)
    signature: bytes = b""
    size_bytes: int = 0
    downloads: int = 0
    rating: float = 0.0


@dataclass
class MarketplaceConfig:
    enabled: bool = False
    registry_url: str = ""
    auto_update: bool = False
    verify_signatures: bool = True
    max_installed: int = 50


class PluginMarketplace:
    """Experimental plugin metadata lifecycle with fail-closed installation."""

    def __init__(self, repo: Any, config: MarketplaceConfig):
        self._repo = repo
        self._cfg = config
        self._installed: dict[str, PluginManifest] = {}
        self._load_installed()

    def _load_installed(self) -> None:
        try:
            rows = self._repo.storage.conn.execute("SELECT * FROM installed_plugins").fetchall()
            for row in rows:
                manifest = PluginManifest(
                    plugin_id=str(row["plugin_id"]),
                    name=str(row["name"]),
                    version=str(row["version"]),
                    author_did=str(row["author_did"]),
                    description=str(row["description"]),
                    hooks=json.loads(row["hooks"] or "[]"),
                    runtime=str(row["runtime"]),
                )
                self._installed[manifest.plugin_id] = manifest
        except Exception as exc:
            logger.debug("Marketplace state load failed: %s", exc, exc_info=True)

    def _registry_base(self) -> str:
        if not self._cfg.enabled:
            raise RuntimeError("Plugin marketplace is disabled")
        if not self._cfg.registry_url.strip():
            raise RuntimeError("Plugin marketplace registry_url is not configured")
        return validate_operator_https_url(self._cfg.registry_url).rstrip("/")

    async def search(self, query: str) -> list[PluginManifest]:
        if not self._cfg.enabled:
            return []
        registry = self._registry_base()
        try:
            import httpx
        except ImportError:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                resp = await client.get(f"{registry}/search", params={"q": query})
                if resp.status_code == 200:
                    return [PluginManifest(**p) for p in resp.json().get("plugins", [])]
        except (OSError, httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            logger.debug("Marketplace search failed: %s", exc, exc_info=True)
        return []

    async def install(self, plugin_id: str) -> None:
        registry = self._registry_base()
        if len(self._installed) >= self._cfg.max_installed:
            raise ValueError("Max plugins installed")

        if self._cfg.verify_signatures:
            raise RuntimeError(
                "Plugin installation blocked: trusted signature verification is not implemented. "
                "Do not disable verification unless the registry and artifact are operator-trusted."
            )

        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("httpx is required for marketplace installation") from exc

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
                resp = await client.get(f"{registry}/plugin/{plugin_id}")
                if resp.status_code != 200:
                    raise RuntimeError(f"Plugin registry returned HTTP {resp.status_code}")
                data = resp.json()
                manifest = PluginManifest(**data["manifest"])
                self._installed[plugin_id] = manifest
                self._persist_installed(manifest)
                self._emit("marketplace.installed", {"plugin": plugin_id})
        except (OSError, httpx.HTTPError) as exc:
            raise RuntimeError("Plugin registry request failed") from exc

    async def uninstall(self, plugin_id: str) -> None:
        self._installed.pop(plugin_id, None)
        try:
            self._repo.storage.conn.execute(
                "DELETE FROM installed_plugins WHERE plugin_id = ?", (plugin_id,)
            )
            self._repo.storage.conn.commit()
        except Exception as exc:
            logger.debug("Marketplace uninstall persistence failed: %s", exc, exc_info=True)
        self._emit("marketplace.uninstalled", {"plugin": plugin_id})

    def installed(self) -> list[PluginManifest]:
        return list(self._installed.values())

    def _persist_installed(self, manifest: PluginManifest) -> None:
        try:
            self._repo.storage.conn.execute(
                """INSERT OR REPLACE INTO installed_plugins
                   (plugin_id, name, version, author_did, description, hooks, runtime)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    manifest.plugin_id,
                    manifest.name,
                    manifest.version,
                    manifest.author_did,
                    manifest.description,
                    json.dumps(manifest.hooks),
                    manifest.runtime,
                ),
            )
            self._repo.storage.conn.commit()
        except Exception as exc:
            logger.debug("Marketplace install persistence failed: %s", exc, exc_info=True)

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        try:
            self._repo._emit_event(event_type, payload)
        except Exception as exc:
            logger.debug("Marketplace event emission failed: %s", exc, exc_info=True)
