"""LLM-as-judge (reference-based) + char-level F1.

이전: scripts/graph_rag_poc/_shared/lazy_value_test/rescore.py
"""
import json
import re
from collections import Counter
from typing import Optional, Tuple

import requests

from pipeline.shared.config import Config as C


# ────────── char-level F1 (KorQuAD 스타일) ──────────
def normalize_ko(s: str) -> str:
    return re.sub(r"[\s\W_]", "", (s or "").lower())


def char_f1(pred: str, gold: str) -> Tuple[float, float, float]:
    """음절 단위 precision, recall, f1."""
    p, g = Counter(normalize_ko(pred)), Counter(normalize_ko(gold))
    common = sum((p & g).values())
    if common == 0 or sum(p.values()) == 0 or sum(g.values()) == 0:
        return 0.0, 0.0, 0.0
    precision = common / sum(p.values())
    recall = common / sum(g.values())
    f1 = 2 * precision * recall / (precision + recall)
    return round(precision, 3), round(recall, 3), round(f1, 3)


# ────────── LLM-judge (Gemma, reference-based correctness) ──────────
JUDGE_PROMPT = """당신은 RAG 답변을 채점하는 엄정한 평가자입니다.
질문, 모범답안(정답), 생성답안을 보고, 생성답안이 모범답안의 핵심 사실을 정확히 담았는지 평가하세요.

[채점 기준]
- 1.0: 모범답안의 핵심 사실을 모두 정확히 포함, 오류 없음
- 0.7~0.9: 핵심 대부분 포함하나 일부 누락 또는 사소한 부정확
- 0.4~0.6: 부분적으로 맞으나 중요 누락 또는 방향 오류 존재
- 0.1~0.3: 대부분 틀리거나 핵심 누락
- 0.0: 완전히 틀림 또는 무관

[출력] 오직 JSON: {"score": 0.0~1.0, "reason": "한 줄 이유"}"""


def llm_judge(question: str, gold: str, pred: str) -> Tuple[Optional[float], str]:
    """LLM judge 호출. (score, reason) 반환. 실패 시 (None, err)."""
    payload = {
        "model": C.VLLM_MODEL,
        "messages": [
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": f"[질문]\n{question}\n\n[모범답안]\n{gold}\n\n[생성답안]\n{pred}"},
        ],
        "temperature": 0.0,
        "max_tokens": 200,
    }
    try:
        r = requests.post(C.vllm_chat_url(), json=payload, timeout=60)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = re.sub(r"^```\w*\n?|\n?```$", "", content).strip()
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            parsed = json.loads(m.group())
            return float(parsed.get("score", 0.0)), parsed.get("reason", "")
    except Exception as e:
        return None, f"judge error: {e}"
    return None, "parse fail"


# ────────── CLI: 디렉터리 내 q*.json에 judge 채점 → rescore_summary.json ──────────
def run_judge_on_dir(results_dir: str, tracks: list) -> str:
    """results_dir의 q*.json 전체를 judge 채점하고 rescore_summary.json 저장."""
    import os
    from collections import defaultdict

    files = sorted(f for f in os.listdir(results_dir)
                   if f.startswith("q") and f.endswith(".json")
                   and not f.startswith("q_"))
    summary = []
    by_cat = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for fn in files:
        q = json.load(open(os.path.join(results_dir, fn), encoding="utf-8"))
        qid, cat = q["id"], q["category"]
        gold = q["expected_answer"]
        question = q["question"]
        print(f"  [Q{qid}] ({cat}) {question[:36]}...")
        row = {"id": qid, "category": cat, "tracks": {}}
        for t in tracks:
            if t not in q["results"] or "answer" not in q["results"][t]:
                continue
            pred = q["results"][t]["answer"]
            kw = q["results"][t].get("score", {}).get("keyword_score")
            p, rec, f1 = char_f1(pred, gold)
            js, jr = llm_judge(question, gold, pred)
            row["tracks"][t] = {"keyword": kw, "f1": f1, "f1_p": p, "f1_r": rec,
                                "judge": js, "judge_reason": jr}
            by_cat[cat][t]["keyword"].append(kw if kw is not None else 0)
            by_cat[cat][t]["f1"].append(f1)
            by_cat[cat][t]["judge"].append(js if js is not None else 0)
            print(f"    {t:18s}: kw={kw} f1={f1} judge={js}")
        summary.append(row)

    out_path = os.path.join(results_dir, "rescore_summary.json")
    json.dump(summary, open(out_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2, default=str)
    print(f"[judge] 저장: {out_path}  ({len(summary)}문)")
    return out_path


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dir", required=True, help="results 디렉터리")
    p.add_argument("--tracks", nargs="+", required=True, help="채점할 트랙 이름들")
    args = p.parse_args()
    run_judge_on_dir(args.dir, args.tracks)


if __name__ == "__main__":
    main()
