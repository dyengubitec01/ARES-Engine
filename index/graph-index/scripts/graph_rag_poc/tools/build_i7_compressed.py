# -*- coding: utf-8 -*-
"""I-7 (K²RAG Corpus Pre-Summarization) 옵션2 빌드 — 청크 압축 → 설명 생성(압축본/full A/B).

상세 설계·이력: experiments/I7_BUILD_LOG.md
- band 2~30 = 281 엔티티 + 11 커뮤니티 (총 1164 중 의식적 선택)
- Phase1 그룹 압축(~10청크/그룹, ~89%) → Phase2 설명(압축본) → Phase3 설명(full 대조군)
- 체크포인트: 각 산출 파일에 증분 저장. 재실행하면 done 항목 skip하고 이어서 진행(DNS 끊김 대비).
"""
import io
import json
import os
import re
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from pipeline.shared.llm import chat  # noqa: E402

SRC = os.path.join(ROOT, "data", "chunks", "scaled_1000.json")
GRAPH = os.path.join(ROOT, "data", "graphs", "gliner2", "lazy_community_1000.json")
COMP_OUT = os.path.join(ROOT, "data", "chunks", "scaled_1000_compressed.json")
DESC_C_OUT = os.path.join(ROOT, "data", "chunks", "i7_desc_compressed.json")
DESC_F_OUT = os.path.join(ROOT, "data", "chunks", "i7_desc_full.json")

WIN = 10                      # 압축 그룹당 청크 수
BAND_LO, BAND_HI = 2, 30      # 엔티티 설명 대상 band
CHUNK_CAP = 12                # 엔티티당 사용할 청크 상한(공정 비교용)
ENT_BASE, COMM_BASE = 210000, 200000

COMPRESS_PROMPT = ("다음 여러 청크를 하나로 압축 요약하라. 고유명사·인물·기관·숫자·날짜·관계 등 핵심 사실은 "
                   "반드시 보존하고, 원문의 약 1/9 분량으로 줄여라. 불필요한 수식어와 중복만 제거한다.")
ENT_PROMPT = ("다음은 한 엔티티가 등장하는 텍스트다. 이 엔티티가 '무엇이며 어떤 관계·역할을 가지는지' "
              "1~2문장으로 요약하라. 핵심 사실·관계만.")
COMM_PROMPT = "다음은 한 군집의 텍스트다. 이 군집이 다루는 핵심 주제·인물·관계를 2~3문장으로 요약하라."

JOSA = ("이며", "으로서", "로서", "라는", "이라는", "의", "은", "는", "이", "가", "을", "를",
        "에", "와", "과", "도", "로", "에서", "에게", "부터", "까지", "만", "들")


def norm(e):
    e = e.strip()
    for j in sorted(JOSA, key=len, reverse=True):
        if e.endswith(j) and len(e) - len(j) >= 2:
            return e[:-len(j)].strip()
    return e


def call(system, user, max_tokens=200, tries=3):
    """재시도 래퍼. 연속 실패 시 예외 → 호출부에서 체크포인트 저장 후 종료."""
    last = None
    for _ in range(tries):
        try:
            out, _ = chat(system, user, max_tokens=max_tokens)
            return out.strip()
        except Exception as e:
            last = e
            time.sleep(3)
    raise RuntimeError(f"call failed x{tries}: {str(last)[:80]}")


def load(path, default):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def save(path, obj):
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False)


def main():
    chunks = json.load(open(SRC, encoding="utf-8"))
    db = {c["chunk_index"]: (c.get("text") or "") for c in chunks}
    order = sorted(db.keys())
    # 위치순 윈도우 그룹핑
    group_of, groups = {}, {}
    for pos, ci in enumerate(order):
        gid = pos // WIN
        group_of[ci] = gid
        groups.setdefault(gid, []).append(ci)

    g = json.load(open(GRAPH, encoding="utf-8"))
    ec = g["entity_chunks"]
    clean = {}
    for e, idxs in ec.items():
        if len(e.strip()) < 2 or re.fullmatch(r"[\d\W]+", e):
            continue
        clean.setdefault(norm(e), set()).update(idxs)
    band = {k: sorted(v) for k, v in clean.items() if BAND_LO <= len(v) <= BAND_HI}
    print(f"[정보] gliner2 원본 {len(ec)} → 정제 {len(clean)} → band {BAND_LO}~{BAND_HI} = {len(band)} 엔티티 "
          f"+ 커뮤니티 {len(g.get('communities', []))} (총 1164 중 의식적 선택)")
    print(f"[정보] 압축 그룹 {len(groups)}개 (윈도우 {WIN}청크)")

    # ===== Phase 1: 그룹 압축 =====
    comp = {str(k): v for k, v in load(COMP_OUT, {}).items()}  # gid(str) -> text
    todo = [gid for gid in groups if str(gid) not in comp]
    print(f"\n[Phase1 압축] 남은 그룹 {len(todo)}/{len(groups)}")
    for n, gid in enumerate(todo):
        body = "\n\n".join(f"- {db[ci][:400]}" for ci in groups[gid])
        comp[str(gid)] = call(COMPRESS_PROMPT, f"[청크 묶음]\n{body}", max_tokens=220)
        if (n + 1) % 10 == 0:
            save(COMP_OUT, comp); print(f"  ...압축 {n+1}/{len(todo)}")
    save(COMP_OUT, comp)
    print(f"[Phase1 완료] 압축 그룹 {len(comp)}개 → {os.path.basename(COMP_OUT)}")

    def comp_text_for(idxs):
        gids = sorted({group_of[i] for i in idxs[:CHUNK_CAP]})
        return "\n\n".join(f"- {comp[str(gid)]}" for gid in gids)

    def full_text_for(idxs):
        return "\n\n".join(f"- {db[i][:400]}" for i in idxs[:CHUNK_CAP])

    # 커뮤니티 멤버 청크
    def comm_chunks(comm):
        cidx = []
        for m in comm.get("members", []):
            cidx += ec.get(m, [])
        return sorted(set(cidx))

    # ===== Phase 2 & 3: 설명 생성 (압축본 / full) =====
    for phase, out_path, text_fn in [("압축본", DESC_C_OUT, comp_text_for),
                                     ("full", DESC_F_OUT, full_text_for)]:
        recs = load(out_path, {})  # key -> record
        # 엔티티
        ent_todo = [e for e in band if f"E:{e}" not in recs]
        print(f"\n[Phase {phase} 엔티티] 남은 {len(ent_todo)}/{len(band)}")
        for n, ent in enumerate(ent_todo):
            idxs = band[ent]
            desc = call(ENT_PROMPT, f"[엔티티] {ent}\n[텍스트]\n{text_fn(idxs)}", max_tokens=200)
            recs[f"E:{ent}"] = {"chunk_index": ENT_BASE + sorted(band).index(ent),
                                "text": f"[엔티티 설명] {ent}: {desc}", "page_start": None,
                                "i7_meta": "entity", "entity": ent, "route_chunks": idxs,
                                "source": phase}
            if (n + 1) % 20 == 0:
                save(out_path, recs); print(f"  ...{phase} 엔티티 {n+1}/{len(ent_todo)}")
        # 커뮤니티
        comms = g.get("communities", [])
        com_todo = [c for c in comms if f"C:{c.get('id')}" not in recs]
        print(f"[Phase {phase} 커뮤니티] 남은 {len(com_todo)}/{len(comms)}")
        for comm in com_todo:
            cid = comm.get("id"); cidx = comm_chunks(comm)
            if not cidx:
                continue
            summ = call(COMM_PROMPT, f"[군집 텍스트]\n{text_fn(cidx)}", max_tokens=300)
            recs[f"C:{cid}"] = {"chunk_index": COMM_BASE + cid,
                                "text": f"[커뮤니티 요약 {cid}] {summ}", "page_start": None,
                                "i7_meta": "community", "route_chunks": cidx, "source": phase}
        save(out_path, recs)
        print(f"[Phase {phase} 완료] 설명 {len(recs)}개 → {os.path.basename(out_path)}")

    print("\n=== 빌드 완료 ===")


if __name__ == "__main__":
    main()
