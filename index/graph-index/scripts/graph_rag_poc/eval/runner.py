"""실험 runner — YAML config → retriever + synthesizer 조합 실행 → 자동 채점 → 저장.

사용:
  python eval/runner.py experiments/03_lazy_qt_embed.yaml
  python eval/runner.py experiments/03_lazy_qt_embed.yaml --skip-judge --skip-excel
  python eval/runner.py experiments/03_lazy_qt_embed.yaml --limit 4   # smoke

흐름:
  1) YAML 로드 → corpus/qa/tracks 파싱
  2) chunks·entity 임베딩 1회 (트랙 간 공유)
  3) 질문별로: query 임베딩 → 각 트랙(retriever→synthesizer→자동 채점) → q{NN}.json 저장
  4) (옵션) judge LLM 호출하여 rescore_summary.json 생성
  5) (옵션) Excel 비교표 생성
"""
import argparse
import importlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

import yaml  # noqa: E402

from pipeline.shared.embedding import embed_query_dense, embed_chunks, embed_entities  # noqa: E402
from eval.scorer import score_answer  # noqa: E402

# Registry 채우기 위해 import (각 모듈이 @register로 자기 등록)
import pipeline.retrievers.vector_topk  # noqa: F401, E402
import pipeline.retrievers.graph_v2  # noqa: F401, E402
import pipeline.retrievers.hybrid  # noqa: F401, E402
import pipeline.retrievers.multihop  # noqa: F401, E402
import pipeline.retrievers.multistage  # noqa: F401, E402
import pipeline.retrievers.dual_level  # noqa: F401, E402
import pipeline.retrievers.graph_khop  # noqa: F401, E402
import pipeline.retrievers.graph_path  # noqa: F401, E402
import pipeline.retrievers.i7_route  # noqa: F401, E402
import pipeline.retrievers.graph_rag  # noqa: F401, E402
import pipeline.retrievers.vector_plus_graph  # noqa: F401, E402
import pipeline.retrievers.multihop_plus_graph  # noqa: F401, E402
import pipeline.retrievers.retrieval_plus_graph  # noqa: F401, E402
import pipeline.synthesizers.single_shot  # noqa: F401, E402
import pipeline.synthesizers.lazy_filter_claim  # noqa: F401, E402
import pipeline.synthesizers.subq_decompose  # noqa: F401, E402
import pipeline.synthesizers.sub_answer_agg  # noqa: F401, E402
import pipeline.synthesizers.verify  # noqa: F401, E402
import pipeline.synthesizers.pipeline  # noqa: F401, E402  (stage 기반 조합형, stages registry 채움)

from pipeline.retrievers.base import RETRIEVERS  # noqa: E402
from pipeline.synthesizers.base import SYNTHESIZERS  # noqa: E402


def abs_path(rel_path: str) -> str:
    """graph_rag_poc/ 기준으로 절대 경로화."""
    return rel_path if os.path.isabs(rel_path) else os.path.abspath(os.path.join(ROOT, rel_path))


def resolve_prompt(name: str) -> str:
    """synthesizers/prompts/{name}.py → PROMPT 상수 로드."""
    mod = importlib.import_module(f"pipeline.synthesizers.prompts.{name}")
    return mod.PROMPT


def build_retriever_state(rconf: dict, chunk_emb, graphs_cache, entity_emb_cache):
    """retriever 종류별 추가 state(graph/entity_emb 등) 조립."""
    state = {"chunk_emb": chunk_emb}
    if rconf["type"] in ("graph_v2", "graph_khop", "graph_path", "graph_rag", "vector_plus_graph", "multihop_plus_graph",
                         "hybrid_plus_graph", "dual_plus_graph", "multistage_plus_graph"):
        gpath = rconf["graph"]
        state["graph"] = graphs_cache[gpath]
        state["entity_emb"] = entity_emb_cache[gpath]
        if "top_entities" in rconf:
            state["top_entities"] = rconf["top_entities"]
        if "hops" in rconf:
            state["hops"] = rconf["hops"]
    return state


def build_synthesizer_state(sconf: dict):
    """synthesizer 종류별 prompt + 옵션 조립. type=pipeline이면 stages 각각도 처리."""
    state = {}
    # 모놀리식 합성기들의 prompt 키 (synthesizer 마다 일부만 적용됨)
    for k in ("system_prompt", "relevance_prompt", "claim_prompt",
              "reduce_prompt", "draft_prompt", "verify_prompt", "decompose_prompt"):
        if k in sconf:
            state[k] = resolve_prompt(sconf[k])
    # 숫자 옵션
    for k in ("max_tokens", "max_chars_per_chunk"):
        if k in sconf:
            state[k] = sconf[k]
    # pipeline synthesizer: stages 안의 prompt도 미리 resolve
    if sconf.get("type") == "pipeline" and "stages" in sconf:
        resolved_stages = []
        for s in sconf["stages"]:
            rs = dict(s)
            if "prompt" in rs:
                rs["prompt"] = resolve_prompt(rs["prompt"])
            resolved_stages.append(rs)
        state["stages"] = resolved_stages
    return state


def run(config_path: str, limit: int = 0, skip_judge: bool = False, skip_excel: bool = False):
    cfg = yaml.safe_load(open(config_path, encoding="utf-8"))
    print(f"[runner] experiment: {cfg['name']}")
    if cfg.get("description"):
        print(f"[runner] {cfg['description']}")

    # 평가 재현성: gen_temperature 지정 시 생성 온도 전역 오버라이드 (judge는 이미 temp=0)
    if "gen_temperature" in cfg:
        from pipeline.shared.llm import set_gen_temperature
        set_gen_temperature(cfg["gen_temperature"])
        print(f"[runner] 생성 temperature = {cfg['gen_temperature']} (결정론 평가)")

    # 1) chunks 로드 + 임베딩
    chunks = json.load(open(abs_path(cfg["corpus"]), encoding="utf-8"))
    chunks_db = {c["chunk_index"]: c for c in chunks}
    print(f"[runner] chunks {len(chunks)}개 임베딩 중...")
    chunk_emb = embed_chunks(chunks)

    # hybrid retriever용 BM25 인덱스 (사용 트랙 있을 때만 1회 구축)
    bm25 = None
    if any(tc["retriever"]["type"] in ("hybrid", "multistage", "hybrid_plus_graph", "multistage_plus_graph") for tc in cfg["tracks"].values()):
        from pipeline.retrievers.hybrid import BM25
        print("[runner] BM25 인덱스 구축...")
        bm25 = BM25(chunks)

    # 2) qa 로드
    qa_set = []
    for qa_path in cfg["qa"]:
        qa_set.extend(json.load(open(abs_path(qa_path), encoding="utf-8"))["qa_set"])
    if cfg.get("categories"):
        qa_set = [q for q in qa_set if q["category"] in cfg["categories"]]
    if cfg.get("exclude_ids"):
        _ex = set(cfg["exclude_ids"])
        qa_set = [q for q in qa_set if q["id"] not in _ex]
    if limit:
        qa_set = qa_set[:limit]
    print(f"[runner] qa {len(qa_set)}문 로드")

    # 3) graph 필요한 retriever용 미리 로드
    graphs_cache, entity_emb_cache = {}, {}
    for tname, tc in cfg["tracks"].items():
        gpath = tc["retriever"].get("graph")
        if gpath and gpath not in graphs_cache:
            print(f"[runner] graph 로드: {gpath}")
            graphs_cache[gpath] = json.load(open(abs_path(gpath), encoding="utf-8"))
            entity_emb_cache[gpath] = embed_entities(graphs_cache[gpath])

    # 4) 실행
    out_dir = abs_path(cfg["output"])
    os.makedirs(out_dir, exist_ok=True)
    cost = {t: [] for t in cfg["tracks"]}
    t0 = time.time()

    for qa in qa_set:
        qid, question = qa["id"], qa["question"]
        print(f"\n[Q{qid}] ({qa['category']}) {question[:46]}...")
        q_emb = embed_query_dense(question)
        results = {}

        for tname, tc in cfg["tracks"].items():
            # retrieve
            ret_fn = RETRIEVERS[tc["retriever"]["type"]]
            ret_state = build_retriever_state(tc["retriever"], chunk_emb, graphs_cache, entity_emb_cache)
            if tc["retriever"]["type"] == "vector_topk" and "max_index" in tc["retriever"]:
                ret_state["max_index"] = tc["retriever"]["max_index"]
            if tc["retriever"]["type"] == "hybrid":
                ret_state["bm25"] = bm25
                ret_state["query_text"] = question
                ret_state["alpha"] = tc["retriever"].get("alpha", 0.7)
            if tc["retriever"]["type"] == "multistage":
                ret_state["bm25"] = bm25
                ret_state["query_text"] = question
                if "stage1_k" in tc["retriever"]:
                    ret_state["stage1_k"] = tc["retriever"]["stage1_k"]
            if tc["retriever"]["type"] == "dual_level":
                ret_state["query_text"] = question
            if tc["retriever"]["type"] == "multihop":
                ret_state["query_text"] = question
                ret_state["chunks_db"] = chunks_db
                if "hop2_k" in tc["retriever"]:
                    ret_state["hop2_k"] = tc["retriever"]["hop2_k"]
                if "use_hyde" in tc["retriever"]:
                    ret_state["use_hyde"] = tc["retriever"]["use_hyde"]
            if tc["retriever"]["type"] in ("graph_rag", "vector_plus_graph", "multihop_plus_graph",
                                           "hybrid_plus_graph", "dual_plus_graph", "multistage_plus_graph"):
                ret_state["query_text"] = question
            if tc["retriever"]["type"] == "multihop_plus_graph":
                ret_state["chunks_db"] = chunks_db
            if tc["retriever"]["type"] in ("hybrid_plus_graph", "multistage_plus_graph"):
                ret_state["bm25"] = bm25
            if tc["retriever"]["type"] == "hybrid_plus_graph" and "alpha" in tc["retriever"]:
                ret_state["alpha"] = tc["retriever"]["alpha"]
            if tc["retriever"]["type"] == "multistage_plus_graph" and "stage1_k" in tc["retriever"]:
                ret_state["stage1_k"] = tc["retriever"]["stage1_k"]
            if tc["retriever"]["type"] == "i7_route":
                ret_state["chunks_db"] = chunks_db
                ret_state["include_desc"] = tc["retriever"].get("include_desc", False)
                ret_state["route_topn"] = tc["retriever"].get("route_topn", 5)
            top_k = tc["retriever"].get("top_k", 20)
            try:
                candidates = ret_fn(q_emb, top_k, **ret_state)
            except Exception as e:
                print(f"  [{tname}] retrieve 실패: {e}", file=sys.stderr)
                candidates = []
            # synthesize
            syn_fn = SYNTHESIZERS[tc["synthesizer"]["type"]]
            syn_state = build_synthesizer_state(tc["synthesizer"])
            try:
                result = syn_fn(question, candidates, chunks_db, **syn_state)
            except Exception as e:
                result = {"answer": f"(err: {e})", "retrieved_chunks": candidates,
                          "usage": {}, "llm_calls": 0}
            result["score"] = score_answer(result, qa)
            results[tname] = result
            cost[tname].append(result.get("llm_calls", 0))
            sc = result["score"]
            print(f"  [{tname:18s}] kw={sc['keyword_hits']} recall={sc['chunk_recall']} "
                  f"calls={result.get('llm_calls',0)} out={sc['output_tokens']}")

        out = {"id": qid, "category": qa["category"], "question": question,
               "expected_answer": qa["expected_answer"],
               "must_contain": qa.get("answer_must_contain", []),
               "results": results}
        json.dump(out, open(os.path.join(out_dir, f"q{qid:02d}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    # manifest (재현용)
    with open(os.path.join(out_dir, "manifest.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    print(f"\n[runner] 완료: {len(qa_set)}문 / {time.time()-t0:.0f}s → {out_dir}")
    print("  비용(질문당 평균 콜):")
    for t, lst in cost.items():
        if lst:
            print(f"    {t:20s} {sum(lst)/len(lst):.1f}콜")

    # 5) 채점 (judge)
    if not skip_judge:
        from eval.judge import run_judge_on_dir
        tracks = list(cfg["tracks"].keys())
        print(f"\n[runner] judge 실행 (tracks={tracks})...")
        run_judge_on_dir(out_dir, tracks)

    # 6) Excel
    if not skip_excel:
        from eval.exporter import export
        print(f"\n[runner] Excel export...")
        export(out_dir)

    return out_dir


def main():
    p = argparse.ArgumentParser()
    p.add_argument("config", help="experiments/*.yaml 경로")
    p.add_argument("--limit", type=int, default=0, help="앞 N문만 (스모크용)")
    p.add_argument("--skip-judge", action="store_true", help="LLM judge 건너뜀")
    p.add_argument("--skip-excel", action="store_true", help="Excel 생성 건너뜀")
    args = p.parse_args()
    run(args.config, limit=args.limit, skip_judge=args.skip_judge, skip_excel=args.skip_excel)


if __name__ == "__main__":
    sys.exit(main() or 0)
