"""검색 서비스 - 임베딩 → (dense + BM25) → RRF → 리랭킹 파이프라인."""

import asyncio
import logging

from app.core.config import Settings
from app.core.exceptions import RerankerException, VectorStoreException
from app.core.interfaces import (
    EmbeddingInterface,
    RerankerInterface,
    VectorStoreInterface,
)
from app.core.monitoring import observe, safe_update_span
from app.core.payload_fields import (
    PayloadField,
    RESPONSE_METADATA_FIELDS,
    RESPONSE_METADATA_KEY_MAP,
)

logger = logging.getLogger(__name__)


class SearchService:
    """검색 파이프라인을 조율하는 서비스.

    EmbeddingInterface, VectorStoreInterface, RerankerInterface를 주입받아
    임베딩 → (dense + BM25) → RRF → 리랭킹 파이프라인을 수행한다.

    Settings가 주입되고 HYBRID_SEARCH_ENABLED=True이면 hybrid 모드로 동작한다.
    Settings가 None이거나 flag가 False면 기존 dense-only 동작을 유지한다.
    """

    def __init__(
        self,
        embedding: EmbeddingInterface,
        vector_store: VectorStoreInterface,
        reranker: RerankerInterface,
        settings: Settings | None = None,
    ) -> None:
        self._embedding = embedding
        self._vector_store = vector_store
        self._reranker = reranker
        self._settings = settings

    def _is_hybrid_enabled(self) -> bool:
        return bool(
            self._settings is not None
            and getattr(self._settings, "HYBRID_SEARCH_ENABLED", False)
        )

    def _is_parent_expansion_enabled(self) -> bool:
        return bool(
            self._settings is not None
            and getattr(self._settings, "PARENT_EXPANSION_ENABLED", False)
        )

    @staticmethod
    def _safe_int(value) -> int | None:
        """int로 변환하고, 불가하면 None (혼재 컬렉션 방어)."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _chunk_results(self, selected: list[dict]) -> list[dict]:
        """확장 없이 청크 단위 결과를 만든다(플래그 off / 확장 실패 폴백)."""
        return [
            {
                "rank": rank,
                "score": s["score"],
                "content": s["content"],
                "metadata": self._filter_metadata(s["metadata"]),
            }
            for rank, s in enumerate(selected, start=1)
        ]

    def _rrf_k(self) -> int:
        if self._settings is not None:
            return int(getattr(self._settings, "RRF_K", 60))
        return 60

    @staticmethod
    def _filter_metadata(metadata: dict) -> dict:
        """응답에 포함할 metadata 필드만 필터링한다."""
        return {
            RESPONSE_METADATA_KEY_MAP.get(k, k): v
            for k, v in metadata.items()
            if k in RESPONSE_METADATA_FIELDS
        }

    @staticmethod
    def _rrf_fuse(
        dense_results: list[dict],
        bm25_results: list[dict],
        k: int = 60,
    ) -> list[dict]:
        """Reciprocal Rank Fusion으로 dense와 BM25 검색 결과를 합산한다.

        중복 판별 키는 `_point_id`(Qdrant point.id)이다. 각 아이템에
        다음 필드를 심어 반환한다:
          - `_rrf_score`: 합산된 RRF 점수 (정렬용)
          - `_source`: "dense" / "bm25" / "dense+bm25"
          - `score`: 원본 score 보존 (dense에 있으면 dense score, BM25-only면 BM25 score)

        한쪽 결과가 비어 있으면 상대편 결과만 반환한다(fallback 경로에서 활용).
        정렬 순서는 `_rrf_score` 내림차순.

        Args:
            dense_results: dense 검색 결과 (rank 1부터 시작).
            bm25_results: BM25 검색 결과 (rank 1부터 시작).
            k: RRF 상수 (기본 60).

        Returns:
            합산 결과 리스트. 빈 입력 두 개면 빈 리스트.
        """
        fused: dict = {}

        for rank, item in enumerate(dense_results, start=1):
            point_id = item.get("_point_id")
            if point_id is None:
                continue
            fused[point_id] = {
                **item,
                "_rrf_score": 1.0 / (k + rank),
                "_source": "dense",
            }

        for rank, item in enumerate(bm25_results, start=1):
            point_id = item.get("_point_id")
            if point_id is None:
                continue
            rrf = 1.0 / (k + rank)
            if point_id in fused:
                fused[point_id]["_rrf_score"] += rrf
                fused[point_id]["_source"] = "dense+bm25"
                # 원본 score는 dense 값 유지
            else:
                fused[point_id] = {
                    **item,
                    "_rrf_score": rrf,
                    "_source": "bm25",
                }

        return sorted(
            fused.values(), key=lambda x: x["_rrf_score"], reverse=True
        )

    async def search(
        self,
        query: str,
        user_depts: list[str],
        search_k: int,
        top_k: int,
        trace_id: str,
        score_threshold: float = 0.0,
        parent_observation_id: str | None = None,
        excluded_docs: list[str] | None = None,
    ) -> dict:
        """검색 파이프라인을 실행한다.

        Args:
            query: 검색 쿼리 문자열.
            user_depts: 부서 UUID 리스트. 검색 필터에는 사용하지 않는다(부서 필터 개방) — 로깅·모니터링 목적으로만 전달된다.
            search_k: 1차 벡터 검색 후보 수.
            top_k: 리랭킹 후 최종 반환 수.
            trace_id: 요청 추적 ID (미들웨어에서 주입).
            score_threshold: 리랭킹 score 임계값. 이 값 미만인 결과는 제외.
            parent_observation_id: 부모 span ID (child span 연결용).
            excluded_docs: 제외할 doc_content_id 리스트.

        Returns:
            query, trace_id, results를 포함하는 응답 데이터 dict.
        """

        # === 임베딩 ===
        trace_ctx: dict = {"trace_id": trace_id}
        if parent_observation_id:
            trace_ctx["parent_span_id"] = parent_observation_id
        with observe(
            as_type="embedding",
            name="embedding",
            input={"query": query},
            trace_context=trace_ctx,
        ) as span:
            query_vector = await self._embedding.embed(query)
            safe_update_span(
                span,
                output={"vector_dim": len(query_vector)},
                usage={"input": len(query)},
            )

        # === 벡터 검색 (dense 단독 또는 dense+BM25 hybrid) ===
        hybrid_enabled = self._is_hybrid_enabled()
        search_mode = "hybrid" if hybrid_enabled else "dense_only"
        with observe(
            as_type="retriever",
            name="vector-search",
            input={
                "search_k": search_k,
                "user_depts": user_depts,
                "excluded_docs": excluded_docs or [],
                "search_mode": search_mode,
            },
            trace_context=trace_ctx,
        ) as span:
            if hybrid_enabled:
                candidates = await self._retrieve_hybrid(
                    query=query,
                    query_vector=query_vector,
                    search_k=search_k,
                    user_depts=user_depts,
                    excluded_docs=excluded_docs,
                    trace_ctx=trace_ctx,
                )
            else:
                candidates = await self._vector_store.search(
                    query_vector=query_vector,
                    top_k=search_k,
                    user_depts=user_depts,
                    excluded_docs=excluded_docs,
                )
            safe_update_span(span, output={
                "result_count": len(candidates),
                "search_mode": search_mode,
                "results": [
                    {
                        "content": r["content"][:200],
                        "score": r.get("score", 0.0),
                        "metadata": r.get("metadata", {}),
                    }
                    for r in candidates
                ],
            })

        # 빈 결과 시 리랭커 호출 스킵
        if not candidates:
            return {
                "query": query,
                "trace_id": trace_id,
                "results": [],
            }

        # === 리랭킹 ===
        texts = [r["content"] for r in candidates]
        with observe(
            as_type="span",
            name="reranking",
            input={"candidate_count": len(texts), "top_k": top_k},
            trace_context=trace_ctx,
        ) as span:
            try:
                reranked = await self._reranker.rerank(
                    query=query, texts=texts, top_k=top_k
                )
                safe_update_span(span, output={
                    "result_count": len(reranked),
                    "results": [
                        {
                            "index": r["index"],
                            "score": r["score"],
                            "text": r["text"][:200],
                        }
                        for r in reranked
                    ],
                })
            except RerankerException as exc:
                logger.warning(
                    "리랭커 장애 — 1차 검색 결과로 Fallback: query=%s, cause=%s",
                    query, exc,
                )
                safe_update_span(
                    span,
                    output={"error": str(exc), "fallback": True},
                    level="ERROR",
                    status_message=str(exc),
                )
                # fallback에서도 원본 score만 노출 (_rrf_score 등 내부 필드 제거)
                results = []
                for rank, item in enumerate(candidates[:top_k], start=1):
                    results.append(
                        {
                            "rank": rank,
                            "score": item.get("score", 0.0),
                            "content": item["content"],
                            "metadata": self._filter_metadata(
                                item.get("metadata", {})
                            ),
                        }
                    )
                return {
                    "query": query,
                    "trace_id": trace_id,
                    "results": results,
                    "fallback": True,
                }

        # 최종 결과 조합 (score 임계값 필터링 적용)
        # parent 확장에 원본 metadata(parent_id 포함)가 필요하므로 selected에는
        # 필터링 전 metadata를 담는다.
        selected = []
        for item in reranked:
            # score 임계값 미만인 결과 제외
            if score_threshold > 0 and item["score"] < score_threshold:
                continue
            idx = item["index"]
            if not (0 <= idx < len(candidates)):
                logger.error(
                    "Reranker returned invalid index: %d (total: %d)",
                    idx, len(candidates),
                )
                continue
            original = candidates[idx]
            selected.append(
                {
                    "score": item["score"],
                    "content": item["text"],
                    "metadata": original.get("metadata", {}),
                }
            )

        if self._is_parent_expansion_enabled():
            try:
                results = await self._expand_to_parents(selected, trace_ctx)
            except Exception as exc:
                # 확장은 부가 단계 — 실패해도 기본 검색 결과(청크)는 살린다
                logger.warning(
                    "parent_expansion_failed_fallback_to_chunks: %s", exc
                )
                results = self._chunk_results(selected)
        else:
            results = self._chunk_results(selected)

        return {
            "query": query,
            "trace_id": trace_id,
            "results": results,
        }

    async def _run_dense_with_span(
        self,
        *,
        query_vector: list[float],
        search_k: int,
        user_depts: list[str],
        excluded_docs: list[str] | None,
        trace_ctx: dict,
    ) -> list[dict]:
        """dense 벡터 검색을 langfuse child span 안에서 실행한다."""
        with observe(
            as_type="retriever",
            name="dense-search",
            input={
                "search_k": search_k,
                "user_depts": user_depts,
                "excluded_docs": excluded_docs or [],
            },
            trace_context=trace_ctx,
        ) as span:
            try:
                result = await self._vector_store.search(
                    query_vector=query_vector,
                    top_k=search_k,
                    user_depts=user_depts,
                    excluded_docs=excluded_docs,
                )
                safe_update_span(span, output={"result_count": len(result)})
                return result
            except Exception as exc:
                safe_update_span(
                    span,
                    output={"error": str(exc)},
                    level="ERROR",
                    status_message=str(exc),
                )
                raise

    async def _run_bm25_with_span(
        self,
        *,
        query: str,
        search_k: int,
        user_depts: list[str],
        excluded_docs: list[str] | None,
        trace_ctx: dict,
    ) -> list[dict]:
        """키워드 full-text 검색을 langfuse child span 안에서 실행한다."""
        with observe(
            as_type="retriever",
            name="bm25-search",
            input={
                "query_text": query,
                "search_k": search_k,
                "user_depts": user_depts,
                "excluded_docs": excluded_docs or [],
            },
            trace_context=trace_ctx,
        ) as span:
            try:
                result = await self._vector_store.text_search(
                    query_text=query,
                    top_k=search_k,
                    user_depts=user_depts,
                    excluded_docs=excluded_docs,
                )
                safe_update_span(span, output={"result_count": len(result)})
                return result
            except Exception as exc:
                safe_update_span(
                    span,
                    output={"error": str(exc)},
                    level="ERROR",
                    status_message=str(exc),
                )
                raise

    async def _retrieve_hybrid(
        self,
        *,
        query: str,
        query_vector: list[float],
        search_k: int,
        user_depts: list[str],
        excluded_docs: list[str] | None,
        trace_ctx: dict,
    ) -> list[dict]:
        """Dense + 키워드 검색을 병렬 실행한 뒤 RRF로 합산한 후보 리스트를 반환한다.

        각 단계(dense-search, bm25-search, rrf-fusion)를 Langfuse child span으로
        기록한다. vector-search 부모 span 아래에 중첩된다.

        실패 매트릭스:
          - Dense ✓ / BM25 ✓ → RRF 합산
          - Dense ✓ / BM25 ✗ → WARN 로그, dense만 사용
          - Dense ✗ / BM25 ✓ → WARN 로그, BM25만 사용
          - Dense ✗ / BM25 ✗ → VectorStoreException 전파

        Returns:
            RRF 정렬된 후보 리스트, 상위 search_k개로 절삭됨.
        """
        dense_raw, bm25_raw = await asyncio.gather(
            self._run_dense_with_span(
                query_vector=query_vector,
                search_k=search_k,
                user_depts=user_depts,
                excluded_docs=excluded_docs,
                trace_ctx=trace_ctx,
            ),
            self._run_bm25_with_span(
                query=query,
                search_k=search_k,
                user_depts=user_depts,
                excluded_docs=excluded_docs,
                trace_ctx=trace_ctx,
            ),
            return_exceptions=True,
        )

        dense_results: list[dict] = []
        bm25_results: list[dict] = []
        dense_failed = isinstance(dense_raw, BaseException)
        bm25_failed = isinstance(bm25_raw, BaseException)

        if dense_failed and bm25_failed:
            logger.error(
                "Hybrid 검색 양쪽 실패: dense=%s bm25=%s", dense_raw, bm25_raw
            )
            raise VectorStoreException(
                msg=f"Hybrid 검색 실패: dense={dense_raw} bm25={bm25_raw}"
            )
        if dense_failed:
            logger.warning(
                "Dense 검색 실패 — BM25만으로 진행: cause=%s", dense_raw
            )
        else:
            dense_results = dense_raw  # type: ignore[assignment]
        if bm25_failed:
            logger.warning(
                "BM25 검색 실패 — Dense만으로 진행: cause=%s", bm25_raw
            )
        else:
            bm25_results = bm25_raw  # type: ignore[assignment]

        with observe(
            as_type="span",
            name="rrf-fusion",
            input={
                "dense_count": len(dense_results),
                "bm25_count": len(bm25_results),
                "rrf_k": self._rrf_k(),
            },
            trace_context=trace_ctx,
        ) as span:
            fused = self._rrf_fuse(
                dense_results, bm25_results, k=self._rrf_k()
            )
            dense_ids = {x.get("_point_id") for x in dense_results}
            bm25_ids = {x.get("_point_id") for x in bm25_results}
            overlap_count = len(dense_ids & bm25_ids)
            safe_update_span(span, output={
                "fused_count": len(fused),
                "overlap_count": overlap_count,
                "truncated_count": min(len(fused), search_k),
            })
        return fused[:search_k]

    async def _expand_to_parents(
        self,
        selected: list[dict],
        trace_ctx: dict,
    ) -> list[dict]:
        """리랭킹된 청크를 parent ±1 단위로 통째 확장·병합한다.

        parent_id가 있는 청크만 확장한다(parent N-1·N·N+1의 모든 청크 회수 →
        (doc_content_id, parent_id) dedup → chunk_index 순 병합). parent_id가 없는
        청크는 단일 result로 통과시킨다(혼재 컬렉션 방어로직). 확장된 parent와 통과
        청크를 대표 score 내림차순으로 통합한다.
        """
        # 1) parent_id 유무로 분기 + 회수 대상/대표 score 수집
        parents_by_doc: dict[str, set[int]] = {}
        seed_score: dict[tuple[str, int], float] = {}
        passthrough: list[dict] = []
        for s in selected:
            meta = s.get("metadata", {})
            doc_id = meta.get(PayloadField.DOC_CONTENT_ID)
            n = self._safe_int(meta.get(PayloadField.PARENT_ID))
            if doc_id is None or n is None:
                passthrough.append(s)  # 방어로직: parent_id 없음/이상치 → 확장 안 함
                continue
            for p in (n - 1, n, n + 1):
                parents_by_doc.setdefault(doc_id, set()).add(p)
                key = (doc_id, p)
                seed_score[key] = max(
                    seed_score.get(key, float("-inf")), s["score"]
                )

        merged: list[dict] = []

        # 2) parent 청크 통째 회수 → _point_id dedup → (doc, parent_id) 병합
        if parents_by_doc:
            with observe(
                as_type="span",
                name="parent-expansion",
                input={
                    "doc_count": len(parents_by_doc),
                    "seed_count": len(selected) - len(passthrough),
                },
                trace_context=trace_ctx,
            ) as span:
                chunks = await self._vector_store.fetch_chunks_by_parents(
                    {doc: sorted(pids) for doc, pids in parents_by_doc.items()}
                )
                groups: dict[tuple[str, int], list[dict]] = {}
                seen_points: set = set()
                for c in chunks:
                    point_id = c.get("_point_id")
                    if point_id is not None:
                        if point_id in seen_points:
                            continue
                        seen_points.add(point_id)
                    cmeta = c.get("metadata", {})
                    c_doc = cmeta.get(PayloadField.DOC_CONTENT_ID)
                    c_pid = self._safe_int(cmeta.get(PayloadField.PARENT_ID))
                    if c_doc is None or c_pid is None:
                        continue
                    groups.setdefault((c_doc, c_pid), []).append(c)

                for (g_doc, g_pid), members in groups.items():
                    members.sort(
                        key=lambda m: self._safe_int(
                            m.get("metadata", {}).get(PayloadField.CHUNK_INDEX)
                        ) or 0
                    )
                    score = seed_score.get((g_doc, g_pid), 0.0)
                    merged.append(
                        {
                            "_sort": score,
                            "_doc": str(g_doc),
                            "_pid": g_pid,
                            "score": score,
                            "content": "\n".join(
                                m.get("content", "") for m in members
                            ),
                            "metadata": self._filter_metadata(
                                members[0].get("metadata", {})
                            ),
                        }
                    )
                safe_update_span(span, output={
                    "fetched_chunks": len(chunks),
                    "parent_count": len(merged),
                    "passthrough_count": len(passthrough),
                })

        # 3) parent_id 없는 청크는 단일 result로 통과
        for s in passthrough:
            meta = s.get("metadata", {})
            merged.append(
                {
                    "_sort": s["score"],
                    "_doc": str(meta.get(PayloadField.DOC_CONTENT_ID, "")),
                    "_pid": self._safe_int(meta.get(PayloadField.CHUNK_INDEX)) or 0,
                    "score": s["score"],
                    "content": s["content"],
                    "metadata": self._filter_metadata(meta),
                }
            )

        # 4) 대표 score 내림차순(동점 doc/parent asc) → rank 부여
        merged.sort(key=lambda r: (-r["_sort"], r["_doc"], r["_pid"]))
        return [
            {
                "rank": rank,
                "score": r["score"],
                "content": r["content"],
                "metadata": r["metadata"],
            }
            for rank, r in enumerate(merged, start=1)
        ]
