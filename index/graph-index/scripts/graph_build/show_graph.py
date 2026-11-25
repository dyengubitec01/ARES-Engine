# -*- coding: utf-8 -*-
"""그래프에 뭐가 들어있나 간단 조회 (SQL 안 짜도 됨).

  # 들어간 문서 목록 (기본)
  .venv/Scripts/python.exe scripts/graph_build/show_graph.py

  # 특정 문서의 엔티티 (파일명 일부)
  .venv/Scripts/python.exe scripts/graph_build/show_graph.py --doc 증평군

  # 엔티티 전체 빈도순
  .venv/Scripts/python.exe scripts/graph_build/show_graph.py --entities

  # 특정 문서 원본 청크 텍스트
  .venv/Scripts/python.exe scripts/graph_build/show_graph.py --text "증평군 스마트관광"
"""
from __future__ import annotations
import argparse
import os
import sys
from urllib.parse import quote_plus

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
try:
    sys.stdout.reconfigure(encoding="utf-8")  # 한글 출력 (in-place, 안전)
except Exception:
    pass

from sqlalchemy import create_engine, text
from config import settings


def make_engine():
    url = (f"postgresql://{settings.postgres_user}:{quote_plus(settings.postgres_password)}"
           f"@{settings.postgres_host}:{settings.postgres_port}/ragdb_dev")
    return create_engine(url, connect_args={"options": "-csearch_path=rag_dev,public"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", help="이 파일명(일부)의 엔티티 보기")
    ap.add_argument("--entities", action="store_true", help="엔티티 전체 빈도순")
    ap.add_argument("--text", help="이 파일명(일부)의 원본 청크 텍스트")
    args = ap.parse_args()

    eng = make_engine()
    with eng.connect() as c:
        bid = c.execute(text("SELECT id FROM rag_graph_builds WHERE status='active' ORDER BY id DESC LIMIT 1")).scalar()
        b = c.execute(text("SELECT corpus_chunk_count, entity_count, edge_count, community_count "
                           "FROM rag_graph_builds WHERE id=:b"), {"b": bid}).fetchone()
        print(f"[그래프 build {bid}] 청크 {b[0]} / 엔티티 {b[1]} / 엣지 {b[2]} / 커뮤니티 {b[3]}\n")

        if args.text:
            rows = c.execute(text(
                "SELECT ch.chunk_index, ch.text FROM rag_chunks ch "
                "JOIN doc_document_content d ON ch.doc_content_id=d.id "
                "WHERE d.original_filename LIKE :p "
                "AND ch.id IN (SELECT chunk_id FROM rag_graph_entity_chunks WHERE build_id=:b) "
                "ORDER BY ch.chunk_index"), {"p": f"%{args.text}%", "b": bid}).fetchall()
            print(f"'{args.text}' 매칭 청크 {len(rows)}개:\n")
            for ci, t in rows:
                print(f"  [청크 {ci}] {t[:300]}\n")
            return

        if args.doc:
            rows = c.execute(text(
                "SELECT e.name, e.entity_type, count(*) m FROM rag_graph_entity_chunks ec "
                "JOIN rag_graph_entities e ON ec.entity_id=e.id "
                "JOIN rag_chunks ch ON ec.chunk_id=ch.id "
                "JOIN doc_document_content d ON ch.doc_content_id=d.id "
                "WHERE d.original_filename LIKE :p AND ec.build_id=:b "
                "GROUP BY e.name, e.entity_type ORDER BY m DESC"), {"p": f"%{args.doc}%", "b": bid}).fetchall()
            print(f"'{args.doc}' 문서의 엔티티 {len(rows)}개:\n")
            for n, t, m in rows:
                print(f"  {n}  [{t}] x{m}")
            return

        if args.entities:
            rows = c.execute(text("SELECT name, entity_type, chunk_count FROM rag_graph_entities "
                                  "WHERE build_id=:b ORDER BY chunk_count DESC"), {"b": bid}).fetchall()
            print(f"엔티티 {len(rows)}개 (빈도순):\n")
            for n, t, cc in rows:
                print(f"  {n}  [{t}] x{cc}")
            return

        # 기본: 문서 목록
        rows = c.execute(text(
            "SELECT d.original_filename, count(DISTINCT ec.chunk_id) ch, count(DISTINCT ec.entity_id) en "
            "FROM rag_graph_entity_chunks ec "
            "JOIN rag_chunks ch ON ec.chunk_id=ch.id "
            "JOIN doc_document_content d ON ch.doc_content_id=d.id "
            "WHERE ec.build_id=:b GROUP BY d.original_filename ORDER BY en DESC"), {"b": bid}).fetchall()
        print(f"그래프에 들어간 문서 {len(rows)}개 (청크수/엔티티수):\n")
        for fn, ch, en in rows:
            print(f"  [청크{ch:>3} 엔티티{en:>4}]  {fn}")


if __name__ == "__main__":
    main()
