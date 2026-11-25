"""커뮤니티 요약 생성 — 완전한 GraphRAG의 마지막 조각.

build_graph.py 산출물(graph_community.json)의 각 커뮤니티에 대해:
  멤버 엔티티 + 디스크립션 + 커뮤니티 내 관계 → Gemma가 커뮤니티 요약문 생성.

Microsoft GraphRAG의 "community report"에 해당. global sensemaking 질문의 핵심 무기.

입력 : graph_community.json (build_graph.py 산출물)
출력 : graph_community_summarized.json (community[].summary 추가)

실행:
  python scripts/graph_rag_poc/gemma3-27b/build_community_summaries.py \
    --input  scripts/graph_rag_poc/_shared/lazy_value_test/data/graph_community.json \
    --output scripts/graph_rag_poc/_shared/lazy_value_test/data/graph_community_summarized.json
"""
import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

import requests  # noqa: E402

from pipeline.shared.config import Config as C  # noqa: E402


SUMMARY_PROMPT = """당신은 지식 그래프의 주제 클러스터를 요약하는 도구입니다.

아래는 하나의 주제 클러스터를 구성하는 엔티티들과 그 디스크립션, 그리고 엔티티 간 관계입니다.
이 클러스터가 '전체적으로 무엇에 관한 것인지' 핵심 주제와 구조를 요약하세요.

[요약 규칙]
1. 이 클러스터의 핵심 주제를 한 문장으로 먼저 제시
2. 주요 엔티티들이 어떻게 연결되는지 2~4문장으로 설명
3. 추측 금지 — 주어진 엔티티/관계 정보만 사용
4. 전체 200~400자 분량"""


def collect_community_context(comm: Dict[str, Any],
                              entity_descriptions: Dict[str, List[str]],
                              entity_types: Dict[str, str],
                              display_names: Dict[str, str],
                              relation_edges: List[Dict[str, Any]],
                              max_entities: int = 40,
                              max_relations: int = 30) -> str:
    """커뮤니티 요약 LLM 입력 컨텍스트 구성."""
    members = set(comm["members"])
    lines = []

    # 1) 엔티티 + 디스크립션
    lines.append("[엔티티 목록]")
    cnt = 0
    for ent in comm["members"]:
        descs = entity_descriptions.get(ent) or []
        etype = entity_types.get(ent, "?")
        disp = display_names.get(ent, ent)
        desc = descs[0][:150] if descs else ""
        suffix = f" — {desc}" if desc else ""
        lines.append(f"- {disp} ({etype}){suffix}")
        cnt += 1
        if cnt >= max_entities:
            break

    # 2) 커뮤니티 내 관계 (양 끝점이 모두 멤버)
    rel_lines = []
    for rel in relation_edges:
        s, t = rel["source"], rel["target"]
        if s in members and t in members:
            rtype = rel.get("type", "관련")
            sd = display_names.get(s, s)
            td = display_names.get(t, t)
            rel_lines.append(f"- {sd} ←{rtype}→ {td}")
            if len(rel_lines) >= max_relations:
                break
    if rel_lines:
        lines.append("\n[관계 목록]")
        lines.extend(rel_lines)

    return "\n".join(lines)


def summarize_community(context: str, max_tokens: int = 400) -> Dict[str, Any]:
    payload = {
        "model": C.VLLM_MODEL,
        "messages": [
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": context},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    t0 = time.time()
    r = requests.post(C.vllm_chat_url(), json=payload, timeout=120)
    elapsed = time.time() - t0
    r.raise_for_status()
    body = r.json()
    return {
        "summary": body["choices"][0]["message"]["content"].strip(),
        "elapsed": elapsed,
        "usage": body.get("usage", {}),
    }


def build(input_path: str, output_path: str) -> None:
    g = json.load(open(input_path, encoding="utf-8"))
    entity_descriptions = g.get("entity_descriptions", {})
    entity_types = g.get("entity_types", {})
    display_names = g.get("entity_display_names", {})
    relation_edges = g.get("relation_edges", [])

    print(f"커뮤니티 {len(g['communities'])}개 요약 생성 시작\n")
    total_in = total_out = 0
    for comm in g["communities"]:
        ctx = collect_community_context(
            comm, entity_descriptions, entity_types, display_names, relation_edges
        )
        result = summarize_community(ctx)
        comm["summary"] = result["summary"]
        usage = result["usage"]
        total_in += usage.get("prompt_tokens", 0)
        total_out += usage.get("completion_tokens", 0)
        print(f"[C{comm['id']}] size={comm['size']}, {result['elapsed']:.1f}초 "
              f"(in={usage.get('prompt_tokens','?')}, out={usage.get('completion_tokens','?')})")
        print(f"  요약: {result['summary'][:120]}...")
        print()

    g["meta"]["has_community_summaries"] = True
    g["meta"]["summary_total_input_tokens"] = total_in
    g["meta"]["summary_total_output_tokens"] = total_out

    json.dump(g, open(output_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"저장 → {output_path}")
    print(f"커뮤니티 요약 총 비용: in={total_in}, out={total_out} 토큰")


def main() -> int:
    p = argparse.ArgumentParser(description="커뮤니티 요약 생성 (완전한 GraphRAG)")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    if not os.path.exists(args.input):
        print(f"입력 파일 없음: {args.input}", file=sys.stderr)
        return 1
    build(args.input, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
