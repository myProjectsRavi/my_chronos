"""Real Ariadne/ASGI regression contract for standalone CHRONOS GraphQL."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from chronos.graphql_api import ChronosGraphQL
from chronos.server_security import ServerSecuritySettings


BIG_CREATED_AT = 1_800_000_000_123
BIG_LAST_ACCESSED_AT = 1_800_000_000_456
MEMORY_ID = bytes.fromhex("00112233445566778899aabbccddeeff")
PERSONA_ID = bytes.fromhex("ffeeddccbbaa99887766554433221100")


class _FakeMemory:
    id = MEMORY_ID
    content = "synthetic graphql integration memory"
    importance = 0.75
    context = "certification"
    source = "synthetic"
    created_at = BIG_CREATED_AT
    last_accessed_at = BIG_LAST_ACCESSED_AT
    access_count = 7


class _FakeCursor:
    def fetchall(self) -> list[dict[str, bytes]]:
        return []


class _FakeConnection:
    def __init__(self) -> None:
        self.last_sql = ""
        self.last_params: tuple[object, ...] = ()

    def execute(self, sql: str, params: tuple[object, ...]) -> _FakeCursor:
        self.last_sql = sql
        self.last_params = params
        return _FakeCursor()


class _FakeRepo:
    def __init__(self) -> None:
        self.storage = SimpleNamespace(conn=_FakeConnection())
        self.persona = SimpleNamespace(active=lambda: SimpleNamespace(id=PERSONA_ID))
        self.memory = _FakeMemory()

    def get_memory(self, memory_id: bytes) -> _FakeMemory | None:
        return self.memory if memory_id == MEMORY_ID else None


@pytest.mark.asyncio
async def test_graphql_real_asgi_bigint_and_auth_contract() -> None:
    repo = _FakeRepo()
    cred = "synthetic-graphql-test-key"
    app = ChronosGraphQL(
        repo,
        security_settings=ServerSecuritySettings(
            api_key=cred,
            allow_unauthenticated_local=False,
        ),
    ).get_app()
    assert app is not None, "Ariadne GraphQL app was not created"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://graphql.test") as client:
        unauthorized = await client.post("/", json={"query": "{ __typename }"})
        assert unauthorized.status_code == 401
        assert unauthorized.json()["code"] == "AUTH_REQUIRED"

        headers = {"X-API-Key": cred}
        response = await client.post(
            "/",
            headers=headers,
            json={
                "query": """
                    query($id: ID!) {
                      memory(id: $id) {
                        id
                        createdAt
                        lastAccessedAt
                        accessCount
                      }
                    }
                """,
                "variables": {"id": MEMORY_ID.hex()},
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert "errors" not in payload, payload
        assert payload["data"]["memory"] == {
            "id": MEMORY_ID.hex(),
            "createdAt": BIG_CREATED_AT,
            "lastAccessedAt": BIG_LAST_ACCESSED_AT,
            "accessCount": 7,
        }

        response = await client.post(
            "/",
            headers=headers,
            json={
                "query": """
                    query($since: BigInt!) {
                      memories(since: $since, limit: 1) { id }
                    }
                """,
                "variables": {"since": BIG_CREATED_AT},
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert "errors" not in payload, payload
        assert payload["data"]["memories"] == []
        assert BIG_CREATED_AT in repo.storage.conn.last_params
        assert "m.created_at >= ?" in repo.storage.conn.last_sql

        response = await client.post(
            "/",
            headers=headers,
            json={
                "query": """
                    query($since: BigInt!) {
                      memories(since: $since, limit: 1) { id }
                    }
                """,
                "variables": {"since": True},
            },
        )
        assert response.status_code in {200, 400}, response.text
        payload = response.json()
        assert payload.get("errors"), payload
        assert "BigInt" in str(payload["errors"])
