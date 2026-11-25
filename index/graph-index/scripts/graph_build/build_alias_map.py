# -*- coding: utf-8 -*-
"""엔티티 resolution(alias) 맵 빌더 — 큐레이션 동의어를 canonical로 접는 {변형norm→대표norm}.

설계(2026-06-26 단순화): **명시 alias만 유지, cosine 자동병합 폐기.**
  retrieval 실측 결과 resolution의 회수 이득 ≈0(build4 vs build5 하이브리드 Δ +0.006, 노이즈).
  반면 cosine+cc 기반 맵을 매빌드 *post-resolution 엔티티*에서 재생성하다 보니 자기 규칙을 까먹는
  **퇴화 버그**(병합된 변형은 다음 refresh에 안 보여 규칙 탈락 → 다음 빌드 resolution 퇴행) 발생.
  → 고가치 동의어 11쌍만 **고정 정적 맵**(variant→canonical 하드코딩, 존재여부·cc 무관 항상 방출)으로
    내보내 퇴화 원천 차단. cosine/숫자가드/union-find/Qdrant 의존 전부 제거.

저장: rag_graph_summary_cache 에 summary_kind='alias_map' 단일 JSON 행(cross-build 키=norm).
  JSON = {"map": {변형norm: 대표norm}, "names": {대표norm: 대표surface}, "meta": {...}}
build_graph 가 이 행을 로드해 추출 누적 시 norm→대표 치환. extract_relations Phase B 도 동일 적용.

실행:
  .venv/Scripts/python.exe scripts/graph_build/build_alias_map.py --db dev
  .venv/Scripts/python.exe scripts/graph_build/build_alias_map.py --db prod
"""
from __future__ import annotations
import argparse, json, os, re, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
from sqlalchemy import text
import build_graph as B  # make_engine 재사용

_WS = re.compile(r"\s+")
def nrm(s): return _WS.sub("", (s or "").strip()).casefold()

CACHE_KEY = "alias_map:v1"
CACHE_KIND = "alias_map"

# 큐레이션 동의어 (변형 → 대표). 대표=완전/표준형으로 고정(가독성·결정성). 항상 무조건 방출.
# 추가 시 이 리스트만 수정하면 됨. 숫자/스펙코드는 의도적으로 제외(오병합 위험, 상류 큐레이션 담당).
ALIAS = [
    ("스마트시티", "스마트도시"),
    ("ai", "인공지능"),
    ("iot", "사물인터넷"),
    ("ict", "정보통신기술"),
    ("국토부", "국토교통부"),
    ("행안부", "행정안전부"),
    ("과기정통부", "과학기술정보통신부"),
    ("vr", "가상현실"),
    ("ar", "증강현실"),
    ("gis", "지리정보시스템"),
    ("빅데이타", "빅데이터"),
]


def main():
    ap = argparse.ArgumentParser(description="엔티티 alias(resolution) 정적 맵 빌더")
    ap.add_argument("--db", default="dev")
    ap.add_argument("--topn", type=int, default=20000, help="(미사용·하위호환) 정적 맵이라 무시")
    args = ap.parse_args()

    eng, db, schema = B.make_engine(args.db)
    amap, names = {}, {}
    for variant, canon in ALIAS:
        v, c = nrm(variant), nrm(canon)
        if v and c and v != c:
            amap[v] = c
            names[c] = canon  # 대표 surface(표시용)

    payload = json.dumps({
        "map": amap, "names": names,
        "meta": {"mode": "static_explicit", "pairs": len(ALIAS), "eliminated": len(amap)}},
        ensure_ascii=False)
    with eng.begin() as conn:
        # DO UPDATE 에 model_name 포함 — 빠뜨리면 폐기된 생성기 이름
        # (cosine0.93+alias+digitguard)이 그대로 남아 이력을 오독하게 된다.
        # (정적맵 전환 후에도 prod 에 stale 로 남아 있었음)
        conn.execute(text(
            "INSERT INTO rag_graph_summary_cache (cache_key, summary_kind, summary_text, model_name) "
            "VALUES (:k, :kind, :s, :m) "
            "ON CONFLICT (cache_key) DO UPDATE SET summary_text=EXCLUDED.summary_text, "
            "model_name=EXCLUDED.model_name, last_used_at=now()"),
            {"k": CACHE_KEY, "kind": CACHE_KIND, "s": payload, "m": "static_explicit_alias"})
    print(f"[{db}.{schema}] alias_map(정적): 명시 동의어 {len(amap)}쌍 → summary_cache['{CACHE_KEY}']")
    print(f"  {amap}")


if __name__ == "__main__":
    main()
