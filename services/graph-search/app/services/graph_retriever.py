"""Graph-RAG 3-Step 조회 조율 서비스."""

import logging

from app.adapters.entity_qdrant_adapter import EntityQdrantAdapter
from app.adapters.gliner_adapter import GLinerAdapter
from app.adapters.postgres_adapter import PostgresAdapter
from app.core.config import Settings
from app.core.interfaces import EmbeddingInterface, GraphRetrieverInterface
from app.core.monitoring import noop_span, observe

logger = logging.getLogger(__name__)


def _span(trace_context, name, as_type="span", **inp):
    """trace_context가 있으면 부모 span에 nest, 없으면(로컬/테스트) no-op."""
    if trace_context is None:
        return noop_span()
    return observe(name=name, as_type=as_type, trace_context=trace_context, input=inp)


class GraphRetriever(GraphRetrieverInterface):
    def __init__(
        self,
        settings: Settings,
        gliner: GLinerAdapter,
        postgres: PostgresAdapter,
        entity_store: EntityQdrantAdapter,
        embedding: EmbeddingInterface,
    ) -> None:
        self._settings = settings
        self._gliner = gliner
        self._postgres = postgres
        self._entity_store = entity_store
        self._embedding = embedding

    async def retrieve(self, query: str, trace_context: dict | None = None) -> list[dict]:
        if not self._settings.GRAPH_ENABLED:
            return []
        try:
            build_id = await self._postgres.get_active_build_id()
            if build_id is None:
                logger.warning("Graph-RAG: active build 없음 — 스킵")
                return []

            with _span(trace_context, "graph-entity-link", as_type="retriever", query=query) as span:
                seed_ids = await self._link_seeds(build_id, query)
                span.update(output={"seeds": len(seed_ids)})
            if not seed_ids:
                return []

            with _span(trace_context, "graph-neighbor-expand", seeds=len(seed_ids)) as span:
                neighbors = await self._postgres.expand_neighbors(
                    build_id, seed_ids, limit=self._settings.GRAPH_NEIGHBOR_LIMIT,
                )
                span.update(output={"neighbors": len(neighbors)})
            candidates = list({*seed_ids, *neighbors})

            with _span(trace_context, "graph-chunk-rank", as_type="retriever", candidates=len(candidates)) as span:
                rows = await self._postgres.rank_chunks_by_entities(
                    build_id=build_id,
                    seed_ids=seed_ids,
                    candidate_ids=candidates,
                    limit=self._settings.GRAPH_CHUNK_LIMIT,
                )
                span.update(output={"chunks": len(rows)})
            return [self._to_result(r) for r in rows]

        except Exception as exc:
            logger.warning("Graph-RAG 파이프라인 실패 — 빈 결과: %s", exc)
            return []

    async def _link_seeds(self, build_id: int, query: str) -> list[str]:
        entities = await self._gliner.extract_entities(query)
        if not entities:
            return []

        seeds, seen = [], set()
        for ent in entities:
            entity_id = await self._postgres.find_entity_by_name(
                build_id, ent["normalized"]
            )
            if entity_id is None:
                try:
                    surface_vec = await self._embedding.embed(ent["surface"])
                except Exception as exc:
                    logger.warning("surface 임베딩 실패 skip: %s", exc)
                    continue
                hits = await self._entity_store.search_by_vector(
                    query_vector=surface_vec, build_id=build_id, limit=1,
                )
                if not hits:
                    continue
                entity_id = str(hits[0]["entity_id"])

            if entity_id and entity_id not in seen:
                seen.add(entity_id)
                seeds.append(entity_id)
        return seeds

    @staticmethod
    def _to_result(row: dict) -> dict:
        return {
            "chunk_id": row["chunk_id"],
            "content": row["content"],
            "metadata": {
                "doc_id": row.get("doc_content_id", ""),
                "original_filename": row.get("original_filename", ""),
                "_source": "graph",
            },
            "score": row.get("score", 0.0),
            "hits": row.get("hits", 0),
        }
