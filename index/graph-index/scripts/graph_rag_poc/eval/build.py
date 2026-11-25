"""그래프 빌드 파이프라인 — YAML 1개로 extractor → graph_builder 통합 실행.

사용:
  python eval/build.py build_configs/gliner2_lazy_40.yaml
  python eval/build.py build_configs/gemma3_full_40.yaml

YAML 스키마:
  name: gliner2_lazy_40
  description: GLiNER2 + 공출현+Louvain (LLM-free), 40청크
  extractor:
    type: gliner2          # gliner2 / gemma3 / qwen3
    chunks: data/chunks/golden_40.json
    limit: null            # null = 전체, 또는 N
  graph:
    type: lazy_community   # lazy_community / full_relational / community_summarized
    min_entity_len: 2
    # full_relational만 사용:
    strict_validation: true
    relation_weight_factor: 1.0
  outputs:
    extracted: data/graphs/gliner2/extracted_40.json
    graph: data/graphs/gliner2/lazy_community_40.json
"""
import argparse
import importlib
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

import yaml  # noqa: E402


def abs_path(rel_path: str) -> str:
    return rel_path if os.path.isabs(rel_path) else os.path.abspath(os.path.join(ROOT, rel_path))


def run_extractor(cfg: dict, chunks_path: str, out_path: str):
    """type별 extractor 호출. 각 모듈은 run(chunks_path, out_path, ...) 함수 보유."""
    ext_type = cfg["type"]
    mod = importlib.import_module(f"pipeline.extractors.{ext_type}")
    limit = cfg.get("limit")

    if ext_type == "gliner2":
        mod.run(chunks_path, out_path, limit)
    elif ext_type == "gemma3":
        # gemma3 extractor: run(chunks_path, output_path, limit, resume=False)
        mod.run(chunks_path, out_path, limit, cfg.get("resume", False))
    elif ext_type == "qwen3":
        mod.run(chunks_path, out_path, limit)
    else:
        raise ValueError(f"알 수 없는 extractor type: {ext_type}")


def run_graph_builder(cfg: dict, extracted_path: str, out_path: str, chunks_path: str):
    """type별 graph_builder 호출."""
    gb_type = cfg["type"]
    mod = importlib.import_module(f"pipeline.graph_builders.{gb_type}")

    if gb_type == "lazy_community":
        mod.build(extracted_path, out_path, cfg.get("min_entity_len", 2))
    elif gb_type == "full_relational":
        mod.build(
            extracted_path, out_path, chunks_path,
            strict_validation=cfg.get("strict_validation", True),
            min_entity_len=cfg.get("min_entity_len", 2),
            relation_weight_factor=cfg.get("relation_weight_factor", 1.0),
        )
    elif gb_type == "community_summarized":
        mod.build(extracted_path, out_path)
    else:
        raise ValueError(f"알 수 없는 graph_builder type: {gb_type}")


def run(config_path: str, skip_extract: bool = False, skip_build: bool = False):
    cfg = yaml.safe_load(open(config_path, encoding="utf-8"))
    print(f"[build] config: {cfg['name']}")
    if cfg.get("description"):
        print(f"[build] {cfg['description']}")

    chunks_path = abs_path(cfg["extractor"]["chunks"])
    extracted_path = abs_path(cfg["outputs"]["extracted"])
    graph_path = abs_path(cfg["outputs"]["graph"])
    t0 = time.time()

    if not skip_extract:
        os.makedirs(os.path.dirname(extracted_path), exist_ok=True)
        print(f"\n[1/2] 추출 ({cfg['extractor']['type']}): {chunks_path}")
        print(f"      → {extracted_path}")
        run_extractor(cfg["extractor"], chunks_path, extracted_path)
    else:
        print(f"\n[1/2] 추출 skip (--skip-extract). 기존 {extracted_path} 재사용")

    if not skip_build:
        os.makedirs(os.path.dirname(graph_path), exist_ok=True)
        print(f"\n[2/2] 그래프 빌드 ({cfg['graph']['type']}): {extracted_path}")
        print(f"      → {graph_path}")
        run_graph_builder(cfg["graph"], extracted_path, graph_path, chunks_path)
    else:
        print(f"\n[2/2] 빌드 skip (--skip-build)")

    print(f"\n[build] 완료, 총 {time.time()-t0:.0f}s")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("config", help="build_configs/*.yaml 경로")
    p.add_argument("--skip-extract", action="store_true", help="추출 건너뛰기 (이미 있을 때)")
    p.add_argument("--skip-build", action="store_true", help="그래프 빌드 건너뛰기")
    args = p.parse_args()
    run(args.config, skip_extract=args.skip_extract, skip_build=args.skip_build)


if __name__ == "__main__":
    sys.exit(main() or 0)
