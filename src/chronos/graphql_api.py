"""GraphQL query layer for CHRONOS v0.6."""

from __future__ import annotations

import os
from typing import Any

from chronos.server_security import ChronosSecurityMiddleware, ServerSecuritySettings

JSONDict = dict[str, Any]
_MAX_MEMORIES_PAGE_SIZE = 500
_MAX_MEMORIES_OFFSET = 10_000


def _coerce_big_int(value: Any) -> int:
    """Accept integer values outside GraphQL's built-in 32-bit Int range."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("BigInt must be an integer")
    return value


class ChronosGraphQL:
    """GraphQL resolver mapping CHRONOS operations to schema types.

    The returned ASGI app uses the same authentication, rate-limit and request
    size boundary as the FastAPI server.
    """

    def __init__(
        self,
        repo: Any,
        llm: Any = None,
        security_settings: ServerSecuritySettings | None = None,
    ):
        self._repo = repo
        self._llm = llm
        self._security = security_settings or ServerSecuritySettings.from_env()

    def get_app(self) -> Any:
        """Return authenticated Starlette/ASGI GraphQL application."""
        try:
            from ariadne import MutationType, QueryType, ScalarType, make_executable_schema
            from ariadne.asgi import GraphQL as AriadneGraphQL

            configured_host = os.environ.get("CHRONOS_HOST")
            if configured_host:
                self._security.validate_bind_host(configured_host)

            query = QueryType()
            mutation = MutationType()
            big_int = ScalarType(
                "BigInt",
                serializer=_coerce_big_int,
                value_parser=_coerce_big_int,
            )

            async def resolve_memory(_obj: Any, info: Any, id: str) -> JSONDict | None:
                return await self.resolve_memory(info, id)

            async def resolve_recall(
                _obj: Any,
                info: Any,
                query: str,
                topK: int = 10,
                context: str | None = None,
            ) -> list[JSONDict]:
                return await self.resolve_recall(info, query, topK, context)

            async def resolve_memories(
                _obj: Any,
                info: Any,
                context: str | None = None,
                minImportance: float | None = None,
                since: int | None = None,
                limit: int = 50,
                offset: int = 0,
            ) -> list[JSONDict]:
                return await self.resolve_memories(
                    info,
                    context=context,
                    minImportance=minImportance,
                    since=since,
                    limit=limit,
                    offset=offset,
                )

            async def resolve_nlq(_obj: Any, info: Any, question: str) -> str:
                return await self.resolve_nlq(info, question)

            async def resolve_remember(
                _obj: Any,
                info: Any,
                content: str,
                source: str = "graphql",
                importance: float = 0.5,
                context: str | None = None,
                metadata: JSONDict | None = None,
            ) -> JSONDict:
                return await self.resolve_remember(
                    info,
                    content=content,
                    source=source,
                    importance=importance,
                    context=context,
                    metadata=metadata,
                )

            async def resolve_forget(_obj: Any, info: Any, id: str) -> bool:
                return await self.resolve_forget(info, id)

            query.set_field("memory", resolve_memory)
            query.set_field("recall", resolve_recall)
            query.set_field("memories", resolve_memories)
            query.set_field("nlq", resolve_nlq)

            mutation.set_field("remember", resolve_remember)
            mutation.set_field("forget", resolve_forget)

            schema = make_executable_schema(self._type_defs(), query, mutation, big_int)
            graphql_app = AriadneGraphQL(schema)
            return ChronosSecurityMiddleware(graphql_app, self._security)
        except ImportError:
            return None

    async def resolve_memory(self, info: Any, id: str) -> JSONDict | None:
        try:
            memory_id = bytes.fromhex(id)
        except ValueError:
            return None
        memory = self._repo.get_memory(memory_id)
        if memory is None:
            return None
        return self._memory_to_dict(memory)

    async def resolve_recall(
        self,
        info: Any,
        query: str,
        top_k: int = 10,
        context: str | None = None,
    ) -> list[JSONDict]:
        results = self._repo.recall(query, top_k=max(1, min(top_k, 200)), context=context)
        return [{"memory": self._memory_to_dict(r.memory), "score": r.score} for r in results]

    async def resolve_memories(
        self,
        info: Any,
        context: str | None = None,
        minImportance: float | None = None,
        since: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[JSONDict]:
        safe_limit = max(1, min(int(limit), _MAX_MEMORIES_PAGE_SIZE))
        safe_offset = max(0, int(offset))
        if safe_offset > _MAX_MEMORIES_OFFSET:
            raise ValueError(f"offset must be <= {_MAX_MEMORIES_OFFSET}")

        active_persona = self._repo.persona.active()
        persona_id = getattr(active_persona, "id", None)
        if not isinstance(persona_id, (bytes, bytearray)):
            raise RuntimeError("Active persona must have a binary ID")
        persona_id = bytes(persona_id)

        joins = ""
        clauses = ["m.persona_id = ?", "m.is_active = 1"]
        params: list[Any] = [persona_id]
        order_by = "m.created_at DESC, m.id DESC"

        if context:
            joins = (
                " JOIN context_memories cm ON cm.memory_id = m.id"
                " JOIN contexts c ON c.id = cm.context_id"
            )
            clauses.extend(["c.persona_id = ?", "c.name = ?"])
            params.extend([persona_id, context])
            order_by = "cm.position DESC, m.created_at DESC, m.id DESC"
        elif since is not None:
            clauses.append("m.created_at >= ?")
            params.append(int(since))

        if minImportance is not None:
            clauses.append("m.importance >= ?")
            params.append(float(minImportance))

        params.extend([safe_limit, safe_offset])
        rows = self._repo.storage.conn.execute(
            f"SELECT m.id FROM memories m{joins} "
            f"WHERE {' AND '.join(clauses)} "
            f"ORDER BY {order_by} LIMIT ? OFFSET ?",
            tuple(params),
        ).fetchall()

        results: list[JSONDict] = []
        for row in rows:
            memory = self._repo.get_memory(bytes(row["id"]))
            if memory is not None:
                results.append(self._memory_to_dict(memory))
        return results

    async def resolve_nlq(self, info: Any, question: str) -> str:
        from chronos.nlq import NaturalLanguageQuery

        nlq = NaturalLanguageQuery(self._llm)
        return str(await nlq.answer(question, self._repo))

    async def resolve_remember(
        self,
        info: Any,
        content: str,
        source: str = "graphql",
        importance: float = 0.5,
        context: str | None = None,
        metadata: JSONDict | None = None,
    ) -> JSONDict:
        memory = self._repo.remember(
            content=content,
            source=source,
            importance=importance,
            context=context or "",
            metadata=metadata or {},
        )
        return self._memory_to_dict(memory)

    async def resolve_forget(self, info: Any, id: str) -> bool:
        # Repository.forget owns hex decoding. Passing bytes here previously
        # double-converted the identifier and raised a type error.
        self._repo.forget(id)
        return True

    def _memory_to_dict(self, memory: Any) -> dict[str, Any]:
        return {
            "id": memory.id.hex() if memory.id else "",
            "content": memory.content,
            "importance": memory.importance,
            "context": getattr(memory, "context", ""),
            "source": getattr(memory, "source", ""),
            "createdAt": memory.created_at,
            "lastAccessedAt": getattr(memory, "last_accessed_at", 0),
            "accessCount": getattr(memory, "access_count", 0),
        }

    def _type_defs(self) -> str:
        return """
            type Query {
                memory(id: ID!): Memory
                recall(query: String!, topK: Int = 10, context: String): [RecallResult!]!
                memories(context: String, minImportance: Float, since: BigInt, limit: Int = 50, offset: Int = 0): [Memory!]!
                nlq(question: String!): String!
            }
            type Mutation {
                remember(content: String!, source: String = "graphql", importance: Float = 0.5, context: String, metadata: JSON): Memory!
                forget(id: ID!): Boolean!
            }
            scalar JSON
            scalar BigInt
            type Memory {
                id: ID!
                content: String!
                importance: Float!
                context: String
                source: String
                createdAt: BigInt!
                lastAccessedAt: BigInt
                accessCount: Int
            }
            type RecallResult {
                memory: Memory!
                score: Float!
            }
        """
