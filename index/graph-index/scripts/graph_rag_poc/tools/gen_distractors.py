"""방해 청크(distractor) 벌크 생성 — 청크 수 스케일업 실험용

목적: 골든 40청크에 같은 Autonova 도메인의 "정답을 담지 않는" 배경 청크를 대량으로
섞어, top-k가 코퍼스의 소수만 덮게 만들어 "전체화" 회수 문제를 깨고 회수 변별력을 측정.

설계:
  - Gemma-27B로 1콜에 여러 개씩 벌크 생성 (콜당 비용 절감)
  - 기존 엔티티(인물/자회사/기술/협력사)를 재사용 → 그래프에 연결되는 distractor
  - 새 단역 인물 + 중립적 사내 이벤트 중심 → 28개 평가 질문의 정답을 진술/모순하지 않음
  - 생성 후 누수(answer leakage) 필터 + 길이/중복 검증
  - 골든과 같은 schema, chunk_index는 --start(기본 40)부터 부여

실행:
  # 스모크 (20개)
  python gen_distractors.py --count 20 --per-call 10 --out data/distractors_smoke.json
  # 본생성 (1000개 풀)
  python gen_distractors.py --count 1000 --per-call 10 --out data/distractors.json

출력: data/distractors.json  [{chunk_index, page_start, category, text}, ...]
"""
import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

import requests  # noqa: E402

from pipeline.shared.config import Config as C, CHUNKS_DIR, QA_DIR  # noqa: E402

# 그래프 연결용으로 distractor가 재사용할 표준 엔티티 목록
ENTITY_VOCAB = """[인물] 김지훈(CEO), 박서연(CTO), 이도현(COO), 정민호(Vision대표), 한수정(Drive대표),
윤재혁(Maps대표), 최영민(Vision 카메라팀장), 강현우(Drive 제어팀장), 김나래(Maps V2X팀장),
송지윤(Vision 연구원), 임승호(Drive 연구원), 오태경(Maps 연구원)
[조직] Autonova, Autonova-Vision, Autonova-Drive, Autonova-Maps
[기술] YOLO-Auto v3, LiDAR-Fusion-Net, PathPlanner-X, SafetyShield, HD-Map-Engine,
Sim-Replay, Edge AI Box, V2X-Protocol, Cloud-Sync, Sensor-Calib
[협력사] KAIST, 현대자동차, 만도, LG전자, 삼성SDS, 네이버, 카카오모빌리티, Waymo
[지역] 서울 강남, 대전, 판교"""

# 콜마다 돌려가며 다양성 확보용 테마 (중립적 배경 소재)
THEMES = [
    "사내 해커톤·기술 세미나 등 일상적 사내 행사",
    "신입/단역 직원의 입사·교육·소소한 수상 소식",
    "사옥 이전·복지·동아리·체육대회 등 총무성 소식",
    "ESG·사회공헌·지역사회 봉사 활동",
    "전시회/컨퍼런스 부스 운영 등 일반 홍보 활동(구체적 기술수치·관계 언급 없이)",
    "사내 워크숍·타운홀·송년회 등 조직문화 이벤트",
    "인턴십 설명회·채용 박람회 참가 등 일반 채용 활동",
    "특허 출원·논문 게재 건수 등 일반적 R&D 동향(구체 수치/모델명 단정 없이)",
]

SYSTEM_PROMPT = """당신은 가상 자율주행 스타트업 'Autonova' 도메인의 '배경 채움용(distractor) 문서 청크'를 생성하는 도구입니다.
이 청크들은 검색 실험에서 노이즈 역할을 하며, 어떤 평가 질문의 정답도 담거나 암시해서는 안 됩니다.

[필수 규칙]
1. 각 청크는 한국어 단락이며 길이는 반드시 260자 이상 360자 이하. 260자 미만은 절대 금지(너무 짧으면 무효).
2. 연결용으로 다음만 사용: 조직명(Autonova, Autonova-Vision/Drive/Maps), 기술 컴포넌트명, 지역명. 각 청크에 1~3개 포함.
3. 사내 행사·운영 활동 중심의 '중립적 배경 정보'만 작성한다. 등장인물이 필요하면 새 가상의 단역 직원(예: 김도윤 연구원)을 만들고, 그들에 대해서도 학력·전직장·출신 같은 배경은 적지 않는다.
4. 절대 금지 (위반 시 무효):
   - 협력사·외부기관 언급 자체 금지: KAIST, 현대자동차, 만도, LG전자, 삼성SDS, 네이버, 카카오모빌리티, Waymo 등을 쓰지 말 것.
   - 인물의 학력/학위/전공/전직장/출신/근무경력/사제·지도·동료·영입·보고라인 등 경력·관계 사실을 절대 서술하지 말 것(신규 가상 인물 포함).
   - 기존 12명 핵심 인물(김지훈·박서연·이도현·정민호·한수정·윤재혁·최영민·강현우·김나래·송지윤·임승호·오태경)은 가급적 등장시키지 말고, 부득이 언급해도 새로운 사실/관계를 붙이지 말 것.
   - 기술 컴포넌트의 카테고리/성능수치/담당 자회사/Phase 산출물을 단정하지 말 것.
   - 아래 '보호된 사실'을 진술하거나 그와 모순되는 내용 금지.
5. 출력은 순수 JSON 배열만. 설명·마크다운 없이 [{"text": "..."}, ...] 형식으로 정확히 N개."""

# distractor에 등장 금지 — 협력사/외부기관(인물 경력·소속 오염의 주원인)
PARTNER_TOKENS = ["KAIST", "현대자동차", "현대 자동차", "만도", "LG전자", "LG 전자",
                  "삼성SDS", "삼성 SDS", "네이버", "카카오모빌리티", "카카오 모빌리티", "Waymo", "웨이모"]
# distractor에 등장 금지 — 경력/학력/관계 단정 트리거 (인물 사실 오염 방지)
BIO_KEYWORDS = ["박사", "석사", "학위", "지도 아래", "지도교수", "교수", "출신", "영입",
                "동료", "입사", "사제", "직제자", "전직장", "졸업", "경력을 쌓", "경험을 쌓",
                "근무한", "근무했", "보고 라인", "보고라인", "직속"]


def load_qa_constraints():
    """두 QA 파일에서 answer_must_contain / expected_answer 수집"""
    specific = set()       # 숫자/% 포함 → 정답 고유 토큰. 단독 등장만으로 누수 판정
    multitoken = []        # 2토큰 이상 must_contain 집합 → 전부 등장 시 누수 판정
    protected = []         # 프롬프트에 넣을 '보호된 사실' (expected_answer)
    curated_unique = ["Waymo", "이종 센서 융합", "확률 그래프 모델"]
    for fn in ("golden_qa.json", "golden_qa_fanout.json"):
        path = os.path.join(QA_DIR, fn)
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        for qa in data.get("qa_set", []):
            mc = qa.get("answer_must_contain", []) or []
            for t in mc:
                if any(ch.isdigit() for ch in t) or "%" in t:
                    specific.add(t)
            if len(mc) >= 2:
                multitoken.append(set(mc))
            ea = qa.get("expected_answer")
            if ea:
                protected.append(f"- {ea}")
    specific.update(curated_unique)
    return specific, multitoken, "\n".join(protected)


def reject_reason(text: str, specific, multitoken) -> str | None:
    """거부 사유 반환 (통과 시 None). 순서: partner > bio > leak."""
    for t in PARTNER_TOKENS:
        if t in text:
            return "partner"
    for kw in BIO_KEYWORDS:
        if kw in text:
            return "bio"
    for t in specific:
        if t in text:
            return "leak"
    for s in multitoken:
        if all(tok in text for tok in s):
            return "leak"
    return None


def gen_batch(n: int, theme: str, protected: str, temperature: float) -> list[str]:
    user_msg = (
        f"[표준 엔티티]\n{ENTITY_VOCAB}\n\n"
        f"[보호된 사실 — 절대 진술/모순 금지]\n{protected}\n\n"
        f"[이번 배치 테마]\n{theme}\n\n"
        f"위 규칙에 따라 서로 다른 배경 청크 {n}개를 JSON 배열로 생성하세요. "
        f"각 text는 반드시 260자 이상 360자 이하로 충분히 길게 작성할 것."
    )
    payload = {
        "model": C.VLLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": temperature,
        "max_tokens": 4096,
    }
    r = requests.post(C.vllm_chat_url(), json=payload, timeout=C.VLLM_TIMEOUT)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    return parse_texts(content)


def parse_texts(content: str) -> list[str]:
    """LLM 응답에서 JSON 배열 추출 → text 리스트. 마크다운 펜스/잡텍스트 방어."""
    content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE).strip()
    start, end = content.find("["), content.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        arr = json.loads(content[start:end + 1])
    except json.JSONDecodeError:
        return []
    out = []
    for item in arr:
        if isinstance(item, dict) and item.get("text"):
            out.append(str(item["text"]).strip())
        elif isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def save_chunks(out_path: str, accepted: list[str], start: int) -> None:
    """원자적 저장(.tmp → replace)으로 중간에 끊겨도 파일 손상 방지."""
    out = [
        {"chunk_index": start + i, "page_start": start + i + 1,
         "category": "distractor", "text": t}
        for i, t in enumerate(accepted)
    ]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    json.dump(out, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.replace(tmp, out_path)


def load_existing(out_path: str) -> tuple[list[str], set]:
    """기존 출력 로드 → 이어하기(resume). 없거나 깨지면 빈 상태."""
    if not os.path.exists(out_path):
        return [], set()
    try:
        arr = json.load(open(out_path, encoding="utf-8"))
    except Exception:
        return [], set()
    texts = [c["text"] for c in arr if isinstance(c, dict) and c.get("text")]
    return texts, {t[:40] for t in texts}


def main() -> int:
    p = argparse.ArgumentParser(description="distractor 청크 벌크 생성")
    p.add_argument("--count", type=int, default=1000, help="목표 distractor 수")
    p.add_argument("--per-call", type=int, default=10, help="콜당 생성 수")
    p.add_argument("--start", type=int, default=40, help="chunk_index 시작값 (골든 40개 다음)")
    p.add_argument("--min-len", type=int, default=230, help="골든 청크 최소(233)에 맞춤")
    p.add_argument("--max-len", type=int, default=430, help="골든 청크 최대(421)에 맞춤")
    p.add_argument("--temperature", type=float, default=0.9)
    p.add_argument("--out", default=os.path.join(CHUNKS_DIR, "distractor_pool.json"))
    p.add_argument("--fresh", action="store_true", help="기존 출력 무시하고 처음부터")
    args = p.parse_args()

    specific, multitoken, protected = load_qa_constraints()
    print(f"[제약] specific 토큰 {len(specific)}개, multitoken 집합 {len(multitoken)}개")

    if args.fresh:
        accepted, seen = [], set()
    else:
        accepted, seen = load_existing(args.out)
        if accepted:
            print(f"[이어하기] 기존 {len(accepted)}개 로드 → {args.count}까지 계속 "
                  f"(처음부터 하려면 --fresh)")
    rej_len = rej_leak = rej_dup = rej_partner = rej_bio = 0
    call_i = 0
    t0 = time.time()

    while len(accepted) < args.count:
        theme = THEMES[call_i % len(THEMES)]
        call_i += 1
        try:
            texts = gen_batch(args.per_call, theme, protected, args.temperature)
        except Exception as e:
            print(f"  [call {call_i}] 실패: {e}", file=sys.stderr)
            if call_i > args.count // args.per_call + 30:
                print("  과도한 실패 — 중단", file=sys.stderr)
                break
            continue

        for t in texts:
            if not (args.min_len <= len(t) <= args.max_len):
                rej_len += 1
                continue
            key = t[:40]
            if key in seen:
                rej_dup += 1
                continue
            reason = reject_reason(t, specific, multitoken)
            if reason == "partner":
                rej_partner += 1
                continue
            if reason == "bio":
                rej_bio += 1
                continue
            if reason == "leak":
                rej_leak += 1
                continue
            seen.add(key)
            accepted.append(t)
            if len(accepted) >= args.count:
                break

        if call_i % 5 == 0 or len(accepted) >= args.count:
            save_chunks(args.out, accepted, args.start)  # 중간 저장 (이어하기 대비)
            print(f"  [call {call_i}] 누적 {len(accepted)}/{args.count} "
                  f"(rej len={rej_len} partner={rej_partner} bio={rej_bio} "
                  f"leak={rej_leak} dup={rej_dup}) {time.time()-t0:.0f}s [저장됨]")

    save_chunks(args.out, accepted, args.start)

    lens = [len(t) for t in accepted]
    print(f"\n완료: {len(accepted)}개 → {args.out}")
    if lens:
        print(f"  길이 min/avg/max: {min(lens)}/{sum(lens)//len(lens)}/{max(lens)}")
    print(f"  콜 {call_i}회, 소요 {time.time()-t0:.0f}s, "
          f"거부 len={rej_len} partner={rej_partner} bio={rej_bio} leak={rej_leak} dup={rej_dup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
