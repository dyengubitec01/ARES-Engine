# -*- coding: utf-8 -*-
"""골든 Q&A 생성 (그래프 시드 → 청크 근거 → LLM 질문/정답).

sample_seeds.py 산출물(seeds_build{N}.json)을 받아, 각 시드의 '근거 청크'를 LLM(KT Cloud
gemma-4-31b)에 주고 질문·정답·필수키워드를 생성한다. 정답은 청크에만 근거(순환편향 방지).
출력은 기존 eval 하니스 호환 포맷 + required_chunk_ids(UUID, prod 회수 채점용).

자격증명(.env 또는 인자):
  GEMMA_API_URL=http://localhost:8000
  GEMMA_API_KEY=sk-...

실행:
  .venv/Scripts/python.exe scripts/graph_eval/generate_golden.py \
      --seeds scripts/graph_rag_poc/data/qa/seeds_build15.json
  # 스모크(앞 4개만, 유형 확인):  --limit 4
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import requests

# 유형별 질문 성격 지시 — 그래프 강점 유형을 겨냥.
TYPE_GUIDE = {
    "relation": (
        "두 엔티티 '{a}'와(과) '{b}'의 관계를 묻는 질문. 근거 청크가 말하는 둘의 실제 연결"
        "(역할·위치·인과·보고라인 등)을 통합해야 답할 수 있어야 한다. 단일 사실 나열이 아니라 관계 추론."),
    "synthesis": (
        "엔티티 '{a}'에 대해 여러 청크에 흩어진 정보를 종합해야 답할 수 있는 질문. "
        "한 청크만으로는 부분답만 나오도록."),
    "sensemaking": (
        "이 문서군의 공통 주제('{a}')에 대한 광범위·종합 이해를 묻는 질문. "
        "개별 사실이 아니라 전반적 경향/구성을 파악해야 함."),
    "control": (
        "근거 청크 하나에 명시된 단일 사실을 묻는 짧고 명확한 질문(벡터검색으로 충분한 유형)."),
}

SYSTEM = (
    "너는 한국어 RAG 평가용 골든 Q&A를 만드는 전문가다. 반드시 제공된 '근거 청크'에만 근거해 "
    "질문과 정답을 만들어라. 청크에 없는 사실을 지어내지 마라. 출력은 JSON 하나만.")

PROMPT_TMPL = """다음은 '{doc}' 등에서 뽑은 근거 청크다. {guide}

[근거 청크]
{chunks}

아래 JSON 스키마로 정확히 하나만 출력(설명·코드펜스 금지):
{{
  "question": "자연스러운 한국어 질문 (근거 청크로만 답 가능)",
  "expected_answer": "근거에 충실한 2~4문장 정답",
  "answer_must_contain": ["정답에 반드시 포함될 핵심어 2~4개(짧게)"],
  "answer_must_not_contain": ["혼동 유발 오답 키워드 0~2개(없으면 빈 배열)"]
}}"""


def gemma(sess, url, key, model, system, user, max_tokens=700, timeout=150, max_retries=4):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = {"model": model, "temperature": 0, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}]}
    endpoint = url.rstrip("/") + "/v1/chat/completions"
    last = None
    for attempt in range(1, max_retries + 1):
        try:
            r = sess.post(endpoint, json=body, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except requests.exceptions.RequestException as e:
            last = e
            if attempt == max_retries:
                break
            time.sleep(min(2 ** attempt, 20))
    raise last


def parse_json(txt: str):
    """코드펜스/잡텍스트 섞여도 최외곽 {...} 추출."""
    txt = txt.strip()
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        raise ValueError(f"JSON 없음: {txt[:120]}")
    return json.loads(m.group(0))


def seed_headword(seed: dict):
    s = seed["seed"]
    if seed["type"] == "relation":
        return s["source"], s["target"]
    if seed["type"] == "synthesis":
        return s["entity"], None
    if seed["type"] == "sensemaking":
        return (s.get("summary") or s.get("community_label") or "이 주제"), None
    return s.get("entity", ""), None


def build_prompt(seed: dict):
    a, b = seed_headword(seed)
    guide = TYPE_GUIDE[seed["type"]].format(a=a, b=b)
    chunks = "\n\n".join(
        f"[청크 {i+1} | {e['filename']} #{e['chunk_index']}]\n{e['text']}"
        for i, e in enumerate(seed["evidence_chunks"]))
    doc = seed["evidence_chunks"][0]["filename"] if seed["evidence_chunks"] else "문서"
    return PROMPT_TMPL.format(doc=doc, guide=guide, chunks=chunks)


def gen_one(sess, url, key, model, idx, seed):
    try:
        raw = gemma(sess, url, key, model, SYSTEM, build_prompt(seed))
        qa = parse_json(raw)
    except Exception as e:
        return {"_error": str(e), "seed_index": idx, "type": seed["type"]}
    evid = seed["evidence_chunks"]
    return {
        "id": idx + 1,
        "category": seed["type"],
        "question": qa.get("question", "").strip(),
        "expected_answer": qa.get("expected_answer", "").strip(),
        "answer_must_contain": qa.get("answer_must_contain", []),
        "answer_must_not_contain": qa.get("answer_must_not_contain", []),
        "required_chunk_ids": seed["required_chunk_ids"],
        "evidence_refs": [{"filename": e["filename"], "chunk_index": e["chunk_index"]} for e in evid],
        "seed": seed["seed"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", required=True, help="sample_seeds.py 산출 json")
    ap.add_argument("--gemma-url", default=os.getenv("GEMMA_API_URL"))
    ap.add_argument("--gemma-key", default=os.getenv("GEMMA_API_KEY", ""))
    ap.add_argument("--gemma-model", default="gemma-4-31b")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="앞 N개만(스모크)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if not args.gemma_url:
        raise SystemExit("GEMMA_API_URL 필요 (.env 또는 --gemma-url). KT Cloud 프록시 URL.")

    data = json.load(open(args.seeds, encoding="utf-8"))
    bid = data.get("build_id")
    seeds = data["seeds"]
    if args.limit:
        seeds = seeds[:args.limit]
    print(f"[generate] build{bid} 시드 {len(seeds)}개 → gemma({args.gemma_model}) 생성 (workers={args.workers})")

    sess = requests.Session()
    results = [None] * len(seeds)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(gen_one, sess, args.gemma_url, args.gemma_key, args.gemma_model, i, s): i
                for i, s in enumerate(seeds)}
        for f in as_completed(futs):
            i = futs[f]
            results[i] = f.result()
            r = results[i]
            tag = "ERR" if r.get("_error") else "ok "
            q = r.get("_error") or r.get("question", "")
            print(f"  [{tag}] {seeds[i]['type']:11s} {q[:56]}")

    ok = [r for r in results if not r.get("_error")]
    errs = [r for r in results if r.get("_error")]
    # id 재부여(에러 제외 후 순번)
    for n, r in enumerate(ok, 1):
        r["id"] = n

    out_path = args.out or os.path.join(os.path.dirname(args.seeds), f"golden_build{bid}_pilot.json")
    payload = {
        "meta": {
            "purpose": "그래프RAG 골든 Q&A (그래프-시드+청크-근거)",
            "build_id": bid, "generator_model": args.gemma_model,
            "total": len(ok), "errors": len(errs),
            "distribution": {t: sum(1 for r in ok if r["category"] == t)
                             for t in ("relation", "synthesis", "sensemaking", "control")},
            "evaluation_metrics": ["keyword_score", "chunk_recall(required_chunk_ids)",
                                   "hallucination_free", "judge(LLM)"],
        },
        "qa_set": ok,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n생성 {len(ok)} / 에러 {len(errs)} → {out_path}")
    if errs:
        for e in errs[:5]:
            print(f"  ERR seed#{e['seed_index']}({e['type']}): {e['_error'][:80]}")


if __name__ == "__main__":
    sys.exit(main() or 0)
