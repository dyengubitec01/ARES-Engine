"""Graph RAG ORM 모델 (rag_graph_* 7테이블).

원래 models/rdb_models.py 에 정의돼 있던 것을 그래프 애드온 분리(base/graph 레포 분할)를
위해 이관. Base 는 base(벡터) 쪽 declarative_base 를 그대로 공유한다 → 동일 metadata,
동일 DB. 그래프 레포 분리 후에도 이 import 경로(models.rdb_models.Base)만 base 패키지를
가리키면 된다.

설계: 버전드 빌드(build_id) / chunk·doc 참조 FK 디커플 / 요약=edge·community 컬럼 + 별도 해시캐시
참조: 메모리 graphrag-build-plan-2026-06-16
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.sql import func

from models.rdb_models import Base


class GraphBuild(Base):
    """그래프 재빌드 런 (버전드). 서빙은 status='active' 빌드만 조회. GC=row 삭제 시 CASCADE."""

    __tablename__ = "rag_graph_builds"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    status = Column(String(20), nullable=False, server_default=text("'building'"))  # building/active/superseded/failed
    started_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=False))
    corpus_chunk_count = Column(Integer)
    entity_count = Column(Integer)
    edge_count = Column(Integer)
    community_count = Column(Integer)
    params = Column(JSONB)
    note = Column(Text)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)


class GraphCommunity(Base):
    """커뮤니티(Louvain 클러스터). flat=level 0, 계층 대비 level 컬럼. summary=LLM 요약."""

    __tablename__ = "rag_graph_communities"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    build_id = Column(BigInteger, ForeignKey("rag_graph_builds.id", ondelete="CASCADE"), nullable=False, index=True)
    level = Column(Integer, nullable=False, server_default=text("0"))
    label = Column(Text)
    summary = Column(Text)
    entity_count = Column(Integer, nullable=False, server_default=text("0"))
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)


class GraphEntity(Base):
    """노드(cross-doc 병합된 정규 엔티티). 엔티티 임베딩은 Qdrant(qdrant_point_id)."""

    __tablename__ = "rag_graph_entities"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    build_id = Column(BigInteger, ForeignKey("rag_graph_builds.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(Text, nullable=False)
    entity_type = Column(String(64), nullable=False, server_default=text("'UNKNOWN'"))
    normalized_name = Column(Text, nullable=False, index=True)  # 병합/매칭 키
    qdrant_point_id = Column(String(128))  # 엔티티 벡터(Qdrant 별도 컬렉션)
    description = Column(Text)  # LLM 엔티티 설명(describe_entities, 청크 근거 1~2문장)
    community_id = Column(PGUUID(as_uuid=True), ForeignKey("rag_graph_communities.id", ondelete="SET NULL"), index=True)
    chunk_count = Column(Integer, nullable=False, server_default=text("0"))
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("build_id", "normalized_name", "entity_type", name="uq_rag_graph_entity_canon"),
    )


class GraphEntityChunk(Base):
    """엔티티↔청크 라우팅(회수 핵심, N:M). chunk_id/doc_content_id는 FK 디커플(stale 허용·쿼리타임 JOIN)."""

    __tablename__ = "rag_graph_entity_chunks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    build_id = Column(BigInteger, ForeignKey("rag_graph_builds.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id = Column(PGUUID(as_uuid=True), ForeignKey("rag_graph_entities.id", ondelete="CASCADE"), nullable=False)
    chunk_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)        # rag_chunks.id (FK 없음)
    doc_content_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)  # doc_document_content.id (FK 없음)
    occurrence_count = Column(Integer, nullable=False, server_default=text("1"))
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_gec_build_entity", "build_id", "entity_id"),
        # entity_id 단독: 엔티티 삭제 cascade(WHERE entity_id=?) 가속. 없으면 GC 풀스캔 폭사.
        Index("ix_gec_entity", "entity_id"),
    )


class GraphEdge(Base):
    """관계 엣지(공출현 weight + LLM 라벨/요약)."""

    __tablename__ = "rag_graph_edges"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    build_id = Column(BigInteger, ForeignKey("rag_graph_builds.id", ondelete="CASCADE"), nullable=False, index=True)
    source_entity_id = Column(PGUUID(as_uuid=True), ForeignKey("rag_graph_entities.id", ondelete="CASCADE"), nullable=False)
    target_entity_id = Column(PGUUID(as_uuid=True), ForeignKey("rag_graph_entities.id", ondelete="CASCADE"), nullable=False)
    weight = Column(Float, nullable=False, server_default=text("1"))  # 공출현 강도
    relation_label = Column(Text)     # LLM 관계 라벨
    relation_summary = Column(Text)   # LLM 관계 요약(캐시 재사용)
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_gedge_build_source", "build_id", "source_entity_id"),
        Index("ix_gedge_build_target", "build_id", "target_entity_id"),
        # source/target 단독: 엔티티 삭제 cascade(WHERE source/target_entity_id=?) 가속. GC 필수.
        Index("ix_gedge_source_entity", "source_entity_id"),
        Index("ix_gedge_target_entity", "target_entity_id"),
    )


class GraphSummaryCache(Base):
    """빌드 간 LLM 요약 캐시(비용절감). content 해시 키, 빌드 비종속(cross-build)."""

    __tablename__ = "rag_graph_summary_cache"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    cache_key = Column(String(128), nullable=False, unique=True)  # hash(엔티티쌍/멤버 + 청크 checksum)
    summary_kind = Column(String(20), nullable=False)             # relation / community
    summary_text = Column(Text, nullable=False)
    model_name = Column(String(128))
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=False))


class GraphDocStatus(Base):
    """문서별 그래프 구축 상태 (embedding status 의 그래프 버전).
    벡터RAG가 doc_document_content.status로 임베딩 완료를 보듯, 어느 문서가 그래프됐나 RDB서 직접 조회."""

    __tablename__ = "rag_graph_doc_status"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    build_id = Column(BigInteger, ForeignKey("rag_graph_builds.id", ondelete="CASCADE"), nullable=False, index=True)
    doc_content_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    original_filename = Column(Text)  # 조회 편의 위해 denormalize
    status = Column(String(20), nullable=False)  # done / no_entities
    chunk_count = Column(Integer, nullable=False, server_default=text("0"))
    entity_count = Column(Integer, nullable=False, server_default=text("0"))
    processed_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("build_id", "doc_content_id", name="uq_rag_graph_doc_status"),
    )
