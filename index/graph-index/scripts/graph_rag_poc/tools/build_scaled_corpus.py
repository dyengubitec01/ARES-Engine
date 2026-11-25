"""스케일업 코퍼스 조립 — 골든 40청크 + distractor N개.

골든(chunks.json, idx 0~39)은 항상 포함. distractor(gen_distractors.py 산출, idx 40~)를
앞에서부터 잘라 붙여 총 크기 T의 코퍼스를 만든다. required_chunks(0~39)는 그대로 유효.

실행:
  python build_scaled_corpus.py --sizes 200 500 1000
출력:
  data/chunks_scaled_200.json, _500.json, _1000.json  (각각 골든40 + distractor)
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from pipeline.shared.config import CHUNKS_DIR  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--golden", default=os.path.join(CHUNKS_DIR, "golden_40.json"))
    p.add_argument("--distractors", default=os.path.join(CHUNKS_DIR, "distractor_pool.json"))
    p.add_argument("--sizes", nargs="+", type=int, default=[200, 500, 1000],
                   help="총 코퍼스 크기들 (골든 포함)")
    args = p.parse_args()

    golden = json.load(open(args.golden, encoding="utf-8"))
    if not os.path.exists(args.distractors):
        print(f"distractor 파일 없음: {args.distractors}", file=sys.stderr)
        print("먼저 gen_distractors.py로 생성하세요.", file=sys.stderr)
        return 1
    distractors = json.load(open(args.distractors, encoding="utf-8"))

    n_gold = len(golden)
    print(f"골든 {n_gold}개, distractor 풀 {len(distractors)}개")
    # 골든 인덱스 무결성 확인 (required_chunks가 가리키는 0~39 보존)
    gold_idx = sorted(c["chunk_index"] for c in golden)
    if gold_idx != list(range(n_gold)):
        print(f"[경고] 골든 chunk_index가 0~{n_gold-1} 연속이 아님: {gold_idx[:5]}...", file=sys.stderr)

    for T in sorted(args.sizes):
        need = T - n_gold
        if need < 0:
            print(f"  size {T}: 골든({n_gold})보다 작음 — 건너뜀", file=sys.stderr)
            continue
        if need > len(distractors):
            print(f"  size {T}: distractor 부족({len(distractors)} < {need}) — 가능한 만큼만", file=sys.stderr)
            need = len(distractors)
        corpus = golden + distractors[:need]
        out = os.path.join(CHUNKS_DIR, f"scaled_{T}.json")
        json.dump(corpus, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"  size {len(corpus)}: 골든{n_gold} + distractor{need} → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
