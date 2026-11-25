# -*- coding: utf-8 -*-
"""그래프RAG 방향 평가 엑셀.

- 탭1 기법 전체 평가: 논문 발췌 37기법 카탈로그(유지). **테스트 결과는 초기화**(2026-06-05) —
  이전 벡터baseline 캠페인 점수·판정 폐기, 그래프RAG 통합 방향으로 재평가 예정 → 현재 전부 '미테스트'.
- 탭2 기본 graph RAG 평가(no routing): results/33_vector_plus_graph 산출. 강점/약점.
- 탭3 향후 과제: 라우팅(보류) + 논문기법 조합(step5).
- 탭4 골든셋 50문 / 탭5 청크(Autonova 40): 참고.
"""
import datetime
import glob
import json
import os
import statistics as st

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TODAY = datetime.date.today().strftime("%Y%m%d")
OUT = os.path.join(_DIR, f"CAMPAIGN_EVAL_{_TODAY}.xlsx")
_R33 = os.path.join(_DIR, "results", "35_graph_precise")  # 최선 설정(이름매칭 linking) 런

PAPERS = {
    "2": "RAG Survey for LLMs (Gao, 2023)",
    "3": "MobileRAG (KAIST, 2025)",
    "5": "LightRAG (HKU, ICLR 2025)",
    "6": "MiniRAG (HKU, ICLR 2025)",
    "7": "E2-RAG (CUHK-SZ+Huawei, COLM 2025)",
    "10": "AdaGCRAG (中과학원, ISWC 2025)",
    "11": "Agentic RAG Survey (Singh, 2025)",
    "12": "GraphRAG Survey (PKU+Ant, TOIS 2025)",
    "15": "K²RAG (Sydney+UNSW+Qatar, ICONIP 2025)",
}
def papers_str(nums):
    return " / ".join(PAPERS.get(n.strip(), n.strip()) for n in nums.split(","))

wb = openpyxl.Workbook()
TITLE = Font(bold=True, size=14)
NOTE = Font(size=10, color="444444")
HDR = Font(bold=True, color="FFFFFF", size=11)
HDR_FILL = PatternFill("solid", fgColor="305496")
WRAP = Alignment(wrap_text=True, vertical="top")
CTR = Alignment(wrap_text=True, vertical="center", horizontal="center")
thin = Side(style="thin", color="D0D0D0")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
GREEN, RED, YEL, GRAY = "C6EFCE", "FFC7CE", "FFF2CC", "F2F2F2"


# ===== results/33 (기본 graph RAG, no routing) 집계 =====
def load_g33():
    data = json.load(open(os.path.join(_R33, "rescore_summary.json"), encoding="utf-8"))
    hal = {"vector": 0, "vplus": 0}
    for qf in glob.glob(os.path.join(_R33, "q*.json")):
        q = json.load(open(qf, encoding="utf-8"))
        for t, r in q.get("results", {}).items():
            if t in hal and not r.get("score", {}).get("hallucination_free", True):
                hal[t] += 1
    def cj(cats, t):
        xs = [r["tracks"][t]["judge"] for r in data
              if r["category"] in cats and t in r.get("tracks", {}) and r["tracks"][t].get("judge") is not None]
        return round(st.mean(xs), 3) if xs else None
    return data, hal, cj

G33, HAL, CJ = load_g33()


def exp_overall(expdir, track, metric):
    """기법 실험 디렉터리에서 특정 트랙의 전체 평균(4지표). recall은 q*.json."""
    p = os.path.join(_DIR, expdir)
    if metric == "recall":
        xs = []
        for qf in glob.glob(os.path.join(p, "q*.json")):
            q = json.load(open(qf, encoding="utf-8"))
            sc = q.get("results", {}).get(track, {}).get("score", {})
            if sc.get("chunk_recall") is not None:
                xs.append(sc["chunk_recall"])
        return round(st.mean(xs), 3) if xs else None
    data = json.load(open(os.path.join(p, "rescore_summary.json"), encoding="utf-8"))
    xs = [r["tracks"][track][metric] for r in data
          if track in r.get("tracks", {}) and r["tracks"][track].get(metric) is not None]
    return round(st.mean(xs), 3) if xs else None


# ============ 탭 1: 기법 카탈로그 (테스트 결과 초기화) ============
ws = wb.active; ws.title = "기법 전체 평가"
ws["A1"] = "Graph RAG 기법 37개 — 카탈로그 + 그래프RAG 프레임 테스트 결과"; ws["A1"].font = TITLE
ws["A2"] = ("[안내]  논문 9편 발췌 37기법. **그래프RAG 통합 프레임**(vector+graph baseline 위 격리)으로 평가한 결과입니다. "
            "상태: ✅채택 / 🔶후보·조합 / ⚪효과없음 / ❌탈락 / ⬜기준·사용중·graph_rag에 흡수 / 🔁중복 / ⛔불가·스킵·보류.  "
            "상세 4지표는 ‘기법 적용 결과’ 탭. → **확정 채택 = A-3 Critic** (graph RAG 유일 robust 승자). 검색확장(R-2/5/7/3/6)은 relation↑/나머지↓로 net 무이득.")
ws["A2"].font = NOTE; ws["A2"].alignment = WRAP
ws.merge_cells("A2:H2"); ws.row_dimensions[2].height = 56

HROW = 3
hdr = ["단계", "기법 ID", "기법 이름", "어떤 기법인가 (쉬운 설명)", "출처 논문", "상태", "테스트 결과 (그래프RAG 기준)", "비고"]
for c, h in enumerate(hdr, 1):
    ws.cell(row=HROW, column=c, value=h)

# 카탈로그 (단계, ID, 이름, 설명, 출처번호) — 결과/판정 컬럼은 빈칸으로 초기화
rows = [
 ["①인덱싱","I-1","Naive Chunking + Dense Vector (기본 벡터 인덱스)","문서를 잘라(청크) 임베딩해 벡터 DB에 저장하는 표준 방식","2"],
 ["①인덱싱","I-2","Sparse+Dense Hybrid Index (키워드+의미 혼합 인덱스)","BM25(키워드) + 임베딩(의미) 두 가지로 색인","15,10,2"],
 ["①인덱싱","I-3","Entity/Relation KV Store (엔티티별 정리 저장)","인물·기관마다 설명과 출처청크를 묶어 따로 저장","5"],
 ["①인덱싱","I-4","Heterogeneous Graph (청크+엔티티 그래프)","청크와 엔티티를 노드로, 관계를 엣지로 만든 그래프","6,12"],
 ["①인덱싱","I-5","Hierarchical Tree / RAPTOR (계층 요약 트리)","청크들을 묶어 요약하고, 요약을 또 요약하는 트리","12"],
 ["①인덱싱","I-6","Community Detection + Report (군집 요약)","비슷한 엔티티를 군집으로 묶어 군집별 요약 생성","12"],
 ["①인덱싱","I-7","Corpus Pre-Summarization (코퍼스 사전 요약, K²RAG)","청크를 압축해 엔티티/커뮤니티 '설명'을 싸게 생성","15"],
 ["①인덱싱","I-8","KV Cache Compression (캐시 압축)","청크를 LLM 내부 캐시 형태로 미리 인코딩","7"],
 ["①인덱싱","I-9","Incremental Graph Update (점진적 갱신)","새 문서를 그래프 재구성 없이 추가","5"],
 ["①인덱싱","I-10","EcoVector (모바일 경량 인덱스)","메모리 절약형 벡터 색인(모바일/임베디드용)","3"],
 ["①인덱싱","I-11","Text-Attributed Edge (엣지 설명 부착)","그래프 엣지에 LLM이 만든 관계 설명을 붙임","5,6"],
 ["②검색","R-1","Once Retrieval (1회 검색)","질문으로 한 번만 검색","5,6,12"],
 ["②검색","R-2","Hybrid Search (키워드+의미 혼합 검색)","의미검색과 키워드검색 점수를 가중 합산","15,2"],
 ["②검색","R-3","Dual-Level Retrieval (구체+주제 두 갈래 검색)","질문에서 구체 키워드·주제 키워드를 뽑아 각각 검색","5"],
 ["②검색","R-4","Path Discovery (엔티티 경로 탐색)","질문 속 두 대상을 잇는 경로를 그래프에서 찾아 회수","6"],
 ["②검색","R-5","Iterative / Multi-hop Retrieval (반복·다단계 검색)","1차 검색 후 LLM이 ‘더 찾을 대상’을 짚어 2차 검색","12,2"],
 ["②검색","R-6","Multi-Stage Retrieval (다단계 검색)","넓게 검색 후 키워드(BM25)로 다시 정렬","10,12"],
 ["②검색","R-7","Triple Reranking (재정렬)","검색 결과를 관련도순으로 다시 정렬해 상위만 사용","10"],
 ["②검색","R-8","Graph Expansion / k-hop (그래프 확장)","질문 엔티티에서 그래프를 2단계까지 따라가 청크 회수","10,12"],
 ["②검색","R-9","Answer Type Prediction (답 유형 예측)","답의 유형(인물/날짜 등)을 예측해 그 유형 청크 위주 선별","6"],
 ["②검색","R-10","Selective Content Reduction (입력 축소)","상위 청크만 재선별해 LLM 입력 토큰을 줄임","3"],
 ["③생성","G-1","Direct Context Augmentation (검색결과 붙이기)","검색 결과를 프롬프트에 그대로 붙여 답변 생성","2"],
 ["③생성","G-2","Graph Linearization-Text (그래프→문장 변환)","그래프 관계를 자연어 문장으로 바꿔 LLM에 주입","5,12"],
 ["③생성","G-3","Graph Linearization-GNN (그래프 신경망)","GNN으로 그래프를 임베딩해 LLM과 정렬","12"],
 ["③생성","G-4","Sub-Answer Aggregation (부분답변 합치기)","질문을 쪼개 각각 답한 뒤 합쳐 최종 답변","15"],
 ["③생성","G-5","KV Cache Editor (캐시 편집)","LoRA로 LLM 캐시를 직접 수정(빠른 지식 갱신)","7"],
 ["③생성","G-6","Hybrid Thinking (추론모드 전환)","Qwen3의 ‘깊게 생각/빠르게’ 모드를 질문 따라 전환","10"],
 ["④제어","A-1","Query Routing (질문 유형 라우팅)","질문 유형을 분류해 그에 맞는 기법만 골라 적용","10,11"],
 ["④제어","A-2","Sub-Question Decomposition (질문 쪼개기)","복잡한 질문을 작은 질문들로 나눠 각각 답함","15,11"],
 ["④제어","A-3","Self-Reflection / Critic (답변 자가 검증)","답변을 다른 LLM이 검토해 틀린 관계 주장을 교정","11"],
 ["④제어","A-4","Multi-Agent Orchestration (다중 에이전트)","역할별 에이전트를 나눠 협업","11"],
 ["④제어","A-5","Tool Use (외부 도구 호출)","주가·계산기·SQL 등 외부 API 호출","11,2"],
 ["④제어","A-6","Iterative Refinement (계획·실행 반복)","계획→실행→평가→재계획 루프","11"],
 ["④제어","A-7","Query Rewriting / HyDE (질문 재작성·가상답변)","질문을 다시 쓰거나 가상 답변을 만들어 검색에 사용","2"],
 ["⑤모델","M-1","Quantized LLM 단일화 (양자화 모델 통일)","추출·검색·생성을 같은 양자화 LLM으로 통일","15,6,10"],
 ["⑤모델","M-2","BGE-M3 + Reranker (임베딩+재정렬 모델)","BGE-M3 임베딩 + 재정렬 모델 조합","5,10"],
 ["⑤모델","M-3","SLM Entity Extraction (경량 추출 모델)","LLM 대신 GLiNER 같은 전용 경량 모델로 엔티티 추출","6,12"],
]
# 기법별 그래프RAG-프레임 테스트 상태 (ID → 상태, 결과, 비고). step5(11기법) + 이전 graph 실험 반영.
STATUS = {
 "I-1": ("⬜ 기준", "—", "기본 벡터 인덱스 = 비교 기준점"),
 "I-2": ("🔁 중복", "—", "검색단계 R-2(Hybrid)로 테스트"),
 "I-3": ("❌ 탈락", "judge −0.040", "entity-group: 엔티티 그룹핑이 graph서도 희석/환각"),
 "I-4": ("⬜ 사용중", "—", "우리 lazy 그래프(graph_rag)가 이 구조 = 채택 기반"),
 "I-5": ("❌ 탈락", "judge −0.033", "RAPTOR 요약층(이전 graph 실험 24): net 부정"),
 "I-6": ("⛔ 미재현", "—", "커뮤니티 리포트: 옛 MS GraphRAG PoC서 환각악화 기각. 현 graph 프레임선 미재현(lazy 커뮤니티가 distractor 도배라 graph_rag서 off)"),
 "I-7": ("❌ 탈락", "net무이득", "K²RAG 압축 설명층(run27): 환각↑·R-5에 dominated"),
 "I-8": ("⛔ 불가", "—", "LoRA 학습 필요(속도용). 환경 불가"),
 "I-9": ("⛔ 불가", "—", "운영 갱신기능. 품질무관"),
 "I-10": ("⛔ 불가", "—", "모바일 경량용. 서버환경 무관"),
 "I-11": ("⛔ 불가", "—", "비싼 Full 그래프(관계라벨) 필요 → Full PoC 영역"),
 "R-1": ("⬜ 기준", "—", "1회 검색 = 기본 동작"),
 "R-2": ("🔶 후보", "judge +0.036", "Hybrid+graph 단독 양수(어휘+엔티티 recall)이나 run노이즈(+0.036→+0.012)·critic위선 −0.010. N=3 미확정"),
 "R-3": ("❌ 탈락", "judge −0.042", "Dual+graph: LLM 2갈래 키워드 효과없음"),
 "R-4": ("⬜ 흡수", "—", "Path = graph_rag의 path 컴포넌트로 통합됨"),
 "R-5": ("🔶 조합후보", "judge −0.018", "Multihop+graph: 단독 net−(relation강자·trap발목). critic위 조합도 net무변(relation↑/rest↓)"),
 "R-6": ("⚪ 효과없음", "judge ±0.000", "Multistage+graph: dense→BM25 재정렬 무변"),
 "R-7": ("❌ 탈락", "judge −0.022", "Rerank(top15): fanout 등 유용청크 추림손실"),
 "R-8": ("⬜ 흡수", "—", "k-hop = graph_rag neighborhood로 통합됨"),
 "R-9": ("❌ 탈락", "judge −0.042", "Answer-type 필터: 효과없음/희석"),
 "R-10": ("⛔ 불가", "—", "입력 축소(비용절감용). 품질기법 아님"),
 "G-1": ("⬜ 기준", "—", "검색결과 붙이기 = 기본 생성"),
 "G-2": ("⛔ 스킵", "—", "lazy 그래프는 관계라벨 없어 co-occur뿐 → i7 설명층과 중복 + stage가 graph 접근불가(구현난)"),
 "G-3": ("⛔ 불가", "—", "GNN 학습 인프라 필요"),
 "G-4": ("⛔ 미시도", "—", "Sub-answer 집계 = A-2(분해) 동류, A-2 graph서 −0.044 기각이라 동일 예상"),
 "G-5": ("⛔ 불가", "—", "LoRA 학습 필요"),
 "G-6": ("⛔ 불가", "—", "Qwen3 추론모델 인프라"),
 "A-1": ("⛔ 보류", "—", "Routing = 향후 과제(질문유형별 최적 스택). 데이터로 정당화됨"),
 "A-2": ("❌ 탈락", "judge −0.044", "Sub-Q 분해: 나열형 항목누락·장황(keyword −0.112)"),
 "A-3": ("✅ 채택", "vs vector +0.011~0.018", "Critic(gated) N=3 확정. trap 해결(judge +0.122). graph RAG 유일 robust 승자. 대가 relation −0.048"),
 "A-4": ("⛔ 불가", "—", "다중에이전트: 단일문서QA에 과함"),
 "A-5": ("⛔ 불가", "—", "외부도구: 폐쇄문서 무관"),
 "A-6": ("⛔ 불가", "—", "반복정제: 복합작업용, 과함"),
 "A-7": ("⛔ 스킵", "—", "HyDE: 옛 recall −0.205 붕괴(사적코퍼스 drift) 강한 사전기각 → 스킵"),
 "M-1": ("⛔ 불가", "—", "양자화 통일 = 배포 인프라 결정"),
 "M-2": ("🔁 중복", "—", "BGE-M3 사용중 / 재정렬은 R-7로 테스트→탈락"),
 "M-3": ("⬜ 사용중", "—", "GLiNER2로 엔티티 추출 이미 채택"),
}
def st_fill(s):
    if s.startswith("✅"): return GREEN
    if s.startswith("❌"): return RED
    if s.startswith(("🔶", "⚪", "🔁")): return YEL
    return GRAY  # ⬜ 기준/사용중/흡수, ⛔ 불가/스킵/보류

for r in rows:
    s, res, note = STATUS.get(r[1], ("⬜ 미테스트", "—", "그래프RAG 기준 재평가 예정"))
    ws.append([r[0], r[1], r[2], r[3], papers_str(r[4]), s, res, note])

for c in range(1, len(hdr) + 1):
    cell = ws.cell(row=HROW, column=c); cell.font = HDR; cell.fill = HDR_FILL; cell.alignment = CTR; cell.border = BORDER
for ri in range(HROW + 1, HROW + 1 + len(rows)):
    for c in range(1, len(hdr) + 1):
        ws.cell(row=ri, column=c).border = BORDER
        if c in (3, 4, 5, 6, 7, 8):
            ws.cell(row=ri, column=c).alignment = WRAP
    ws.cell(row=ri, column=6).fill = PatternFill("solid", fgColor=st_fill(ws.cell(row=ri, column=6).value))
for col, w in zip("ABCDEFGH", [9, 7, 30, 40, 30, 14, 24, 28]):
    ws.column_dimensions[col].width = w
ws.freeze_panes = "A4"


# ============ 탭 2: 기본 graph RAG 평가 (no routing) ============
g = wb.create_sheet("기본 graph RAG 평가")
def gput(r, v, bold=False, size=11, fill=None):
    cell = g.cell(row=r, column=1, value=v); cell.font = Font(bold=bold, size=size); cell.alignment = WRAP
    if fill: cell.fill = PatternFill("solid", fgColor=fill)
gput(1, "기본 graph RAG 평가 (라우팅 없음)", True, 14)
gput(2, "실험 35_graph_precise(최선 설정) — vector(운영 기준) vs vector+graph_rag(통합), 골든셋 50문, temp=0. "
        "graph_rag = entity_linking(이름 문자열매칭)+neighborhood+path 순회, 시드가중 hits+focus로 청크 회수. "
        "‘always-both(라우팅 없이 모든 질문에 그래프도 태움)’ 방식. ※단일런이라 작은 Δ는 judge 노이즈(±0.03) 유의.")
g.merge_cells("A2:F2"); g.row_dimensions[2].height = 46

# ---- 4지표 집계 (judge/f1/keyword=rescore, chunk_recall=q*.json) ----
_recall, _qcat = {}, {}
for qf in glob.glob(os.path.join(_R33, "q*.json")):
    q = json.load(open(qf, encoding="utf-8")); _qcat[q["id"]] = q["category"]
    _recall[q["id"]] = {t: q["results"][t].get("score", {}).get("chunk_recall")
                        for t in ("vector", "vplus") if t in q.get("results", {})}
def METRIC(metric, cats, t):
    if metric == "recall":
        xs = [_recall[i][t] for i in _recall if _qcat[i] in cats and t in _recall[i] and _recall[i][t] is not None]
    else:
        xs = [r["tracks"][t][metric] for r in G33 if r["category"] in cats
              and t in r["tracks"] and r["tracks"][t].get(metric) is not None]
    return round(st.mean(xs), 3) if xs else None

ALLCATS = {"relation_reasoning","sensemaking","control","distributed_integration",
           "fanout_relation","hallucination_trap","multilayer_classification"}
ov_v = METRIC("judge", ALLCATS, "vector"); ov_g = METRIC("judge", ALLCATS, "vplus")
gput(4, f"■ 전체 50문 LLM-judge: vector {ov_v:.3f} → vector+graph {ov_g:.3f} (Δ {ov_g-ov_v:+.3f})   "
        f"|   환각 문항수: vector {HAL['vector']} → vector+graph {HAL['vplus']}", True, 11,
     fill=(GREEN if ov_g-ov_v >= 0.01 else (RED if ov_g-ov_v <= -0.01 else YEL)))

# ---- 4지표 비교표 (vector → vector+graph (Δ)) ----
HR = 6
def vcell(metric, cats):
    v = METRIC(metric, cats, "vector"); gg = METRIC(metric, cats, "vplus")
    return "—" if (v is None or gg is None) else f"{v:.3f} → {gg:.3f}  ({gg-v:+.3f})"
mhdr = ["구간 (역할)", "n", "① LLM-judge", "② F1", "③ chunk_recall", "④ keyword"]
for c, h in enumerate(mhdr, 1):
    cell = g.cell(row=HR, column=c, value=h); cell.font = HDR; cell.fill = HDR_FILL; cell.alignment = CTR; cell.border = BORDER
GROUPS = [
    ("전체 50문", ALLCATS), ("그래프유리 (rel+sense)", {"relation_reasoning","sensemaking"}),
    ("relation_reasoning ★", {"relation_reasoning"}), ("sensemaking", {"sensemaking"}),
    ("distributed_integration", {"distributed_integration"}), ("fanout_relation", {"fanout_relation"}),
    ("hallucination_trap ⚠", {"hallucination_trap"}), ("control", {"control"}),
    ("multilayer_classification", {"multilayer_classification"}),
]
ri = HR + 1
for label, cats in GROUPS:
    n = sum(1 for r in G33 if r["category"] in cats)
    g.cell(row=ri, column=1, value=label); g.cell(row=ri, column=2, value=n)
    g.cell(row=ri, column=3, value=vcell("judge", cats)); g.cell(row=ri, column=4, value=vcell("f1", cats))
    g.cell(row=ri, column=5, value=vcell("recall", cats)); g.cell(row=ri, column=6, value=vcell("keyword", cats))
    for c in range(1, 7):
        g.cell(row=ri, column=c).border = BORDER; g.cell(row=ri, column=c).alignment = CTR
    for col, metric in [(3, "judge"), (4, "f1"), (5, "recall"), (6, "keyword")]:
        dv = (METRIC(metric, cats, "vplus") or 0) - (METRIC(metric, cats, "vector") or 0)
        if dv >= 0.01:
            g.cell(row=ri, column=col).fill = PatternFill("solid", fgColor=GREEN)
        elif dv <= -0.01:
            g.cell(row=ri, column=col).fill = PatternFill("solid", fgColor=RED)
    if label == "전체 50문":
        for c in range(1, 7): g.cell(row=ri, column=c).font = Font(bold=True)
    ri += 1
for col, w in zip("ABCDEF", [28, 4, 20, 20, 20, 20]):
    g.column_dimensions[col].width = w
gput(ri, "※ chunk_recall(검색이 정답 근거청크를 가져온 비율)은 judge 노이즈 없는 결정론 지표 — 그래프가 전 구간 ↑ = 검색 개선 확실.")

ri += 1
gput(ri, "■ 강점 (그래프가 vector를 이긴 곳)", True, 12, fill=GREEN); ri += 1
gput(ri, "• relation +0.011 / distributed +0.040 / fanout +0.040. 그래프 순회가 ‘여러 엔티티가 함께 든 관계 청크’를 회수 → "
         "vector가 놓친 근거 보충. gold 근거청크 recall 0.729 → 0.778(↑)."); ri += 2
gput(ri, "■ 약점 (그래프를 더해 깎인 곳)", True, 12, fill=RED); ri += 1
gput(ri, "• hallucination_trap −0.053 (유일한 실질 발목). 트랩=‘없는 관계 단언 유혹’ 질문인데 그래프 관계청크가 이를 강화 "
         "→ 그래프 본질문제(튜닝으로 못 고침). • sensemaking −0.012(경미, ‘순회’보다 ‘커뮤니티 요약’ 영역)."); ri += 2
gput(ri, "■ graph_rag 튜닝 이력 (소진)", True, 12); ri += 1
gput(ri, "cosine→엔티티밀도→focus→min_rel→이름매칭 linking(✓ recall↑)→정규화(✗ 악화·폐기). 최선=현 설정(비정규화+이름매칭)."); ri += 2
gput(ri, "■ 구축 냉정감사 (2026-06-05)", True, 12); ri += 1
gput(ri, "구축 정상: entity_chunks 100% 정확·관계엣지 포착·추출누락 0(만도만 누락=무영향). 단 그래프 84%엣지·88%엔티티가 "
         "합성 distractor 구조 → 한계는 빌드 아니라 테스트 코퍼스. 더 보완할 빌드 개선 없음. 실 운영코퍼스(distractor 없음)에선 더 나을 여지."); ri += 2
gput(ri, "■ 종합 결론", True, 12, fill="DDEBF7"); ri += 1
gput(ri, f"기본 graph RAG는 relation·distributed·fanout에서 양수, always-both 전체 net {ov_g-ov_v:+.3f}(거의 break-even). "
         f"유일 발목=환각트랩. → 트랩만 처리(A-3 critic 또는 라우팅)하면 net+. 그래프 가치는 작지만 실재.")
g.row_dimensions[ri].height = 44


# ============ 탭: 기법 적용 결과 (step5) ============
te = wb.create_sheet("기법 적용 결과")
te["A1"] = "논문 기법 적용 결과 (graph_rag 위에 얹어 테스트)"; te["A1"].font = TITLE
te["A2"] = ("각 기법을 그래프 baseline(vplus = vector+graph_rag) 위에 얹어 4지표 비교. **같은 런 내 baseline→기법**(judge 노이즈 회피). "
            "셀 = baseline → 기법적용 (Δ), 🟢개선/🔴악화(±0.01 미만 무색). ‘vs vector’ = 기법적용본이 운영 벡터RAG(judge)를 넘는지. "
            "원칙: 1기법씩 격리 측정 → 효과 본 것만 조합. 단일런이라 작은 Δ는 노이즈 유의(확정은 N=3).")
te["A2"].font = NOTE; te["A2"].alignment = WRAP; te.merge_cells("A2:G2"); te.row_dimensions[2].height = 56

# (기법명, 실험dir, baseline트랙, 기법트랙, 핵심메모) — 기법 테스트할 때마다 행 추가
TECHNIQUES = [
    ("A-3 Critic (gated) ✅채택", "results/40_critic_n3_r2", "vplus", "vplus_critic",
     "✅ N=3 확정 채택. vector 대비 judge +0.011·keyword +0.016 (3런 전부 양수=노이즈 아님). "
     "trap judge +0.122(3런 일관·핵심동력)·환각↓. 대가: relation −0.048 과교정(3런 일관). "
     "= 운영 벡터RAG를 확실히 넘는 첫 구성(vector+graph+critic). v3 정밀화 시도는 v1보다 못해 폐기. ※셀은 r2런 대표값."),
    ("R-7 Rerank (top15)", "results/38_vplus_rerank", "vplus", "vplus_rerank",
     "합친 풀 top15 추림. relation +0.022·distributed +0.060 도왔으나 fanout −0.100·trap −0.053·sensemaking −0.037 더 깎임. "
     "원인: 추림이 fanout처럼 ‘여러 청크 필요’ 질문서 유용청크 손실. (정밀 graph_rag엔 희석 적어 추림 역효과). ❌ 전체 net 손해 → 기각."),
    ("R-5 Multihop+graph", "results/41_mhg", "vplus", "mhg",
     "🔶 단독 net −0.018이나 조합 후보. relation +0.022(recall +0.111!)·distributed +0.060·sensemaking +0.050·전체 recall +0.066 강함(R-5=검색 강자). "
     "단 trap judge −0.113·keyword −0.200 발목(추가검색이 트랩 유혹↑). → 그 trap을 A-3 critic이 잡으면 강력 조합 기대. 단독 기각·조합 대기."),
    ("R-2 Hybrid+graph", "results/44_rettech_batch2", "vplus", "hybrid_g",
     "🔶 BM25어휘+dense+graph. judge +0.036·recall +0.051·keyword +0.032 (vs vector도 +0.014). "
     "옛 벡터선 기각됐으나 graph 프레임선 양수(어휘recall+엔티티recall 보완). 신규 후보 → N=3 확인 필요. ※단일런."),
    ("R-3 Dual+graph", "results/44_rettech_batch2", "vplus", "dual_g",
     "LLM 키워드 2갈래(구체/주제)+graph. judge −0.042. ❌ 기각."),
    ("R-6 Multistage+graph", "results/44_rettech_batch2", "vplus", "multistage_g",
     "dense→BM25 재정렬+graph. judge ±0.000(무변)·keyword −0.012. ⚪ 효과없음."),
    ("R-9 Answer-type", "results/43_gentech_batch1", "vplus", "vplus_r9",
     "답유형 예측 필터(relevance_filter 대체). judge −0.042·keyword −0.049. ❌ 기각."),
    ("I-3 Entity-group", "results/43_gentech_batch1", "vplus", "vplus_i3",
     "엔티티별 청크 그룹핑(claim 직전). judge −0.040. ❌ 기각(옛 벡터캠페인과 동일)."),
    ("A-2 Sub-Question", "results/43_gentech_batch1", "vplus", "subq",
     "복잡질문 분해. judge −0.044·keyword −0.112(나열형 항목누락·장황). ❌ 기각."),
    ("graph+R-5+Critic 조합", "results/42_mhg_critic", "vplus_critic", "mhg_critic",
     "조합 vs 채택본(graph+critic). 전체 judge +0.002(무승부)·recall +0.066. relation judge +0.156(R-5가 critic 과교정 회복! 0.689→0.844, vector도 넘음)·fanout +0.060 "
     "but trap −0.087(R-5가 트랩 재자극, critic이 다 못잡음). = 프로파일 재균형(relation↑ trap↓), 전체 net 무변. R-5 추가콜로 비용 ~2배. "
     "🔶 전체로는 채택본 대비 미채택(net 무변+고비용). 단 ‘관계 질문 중시’면 조합이 relation 본질가치 살림."),
    ("hybrid+graph+Critic 조합", "results/45_hybrid_critic", "vplus_critic", "hybrid_g_critic",
     "조합 vs 채택본. judge −0.010·keyword −0.050·recall +0.052. relation +0.156(hybrid recall이 critic 과교정 회복) but distributed/sensemaking/trap/fanout 각 −0.05~0.06. "
     "= R-5 조합과 동일 패턴(relation↑ rest↓), net 채택본 못 넘음. R-2 단독 양수도 run간 노이즈(+0.036→+0.012). 🔶 미채택, graph+critic이 best 유지."),
    ("relation_summary 주입 (구조축)", "results/46_relation_inject", "vplus_critic", "vplus_critic_rel",
     "🔶 I-7요약을 ‘관계’에 적용(엔티티설명 아님·real청크 97관계쌍). 채택본 위 주입. judge +0.004(노이즈內)·keyword +0.035·recall 불변=검색 무희석. "
     "relation +0.033·distributed +0.020·trap +0.020 동시↑(검색확장과 질적으로 다름) but fanout −0.060(나열질문 관계요약 노이즈). "
     "= ‘구조 축’ 첫 additive 신호 — 검색축이 못한 보탬. 발목 fanout은 게이팅으로 제거가능 → 정밀화 후 N=3."),
    ("community_summary 주입 (구조축·global)", "results/47_community_inject", "vplus_critic", "vplus_critic_comm",
     "🔶 real 서브그래프 커뮤니티(4개) 요약→sensemaking 주입. sensemaking judge +0.050·keyword +0.042 성공(관계요약이 못한 곳!). "
     "BUT 게이팅 누수(이유/근거/구조 마커가 trap/relation/fanout서도 발화)→trap −0.107 등 collateral→전체 net −0.032. "
     "기법 유효, 정밀 게이팅(=A-1 라우팅) 필요. relation_inject와 같은 교훈."),
    ("A-1 라우팅+구조축 통합 ★조건부", "results/49_route_n3_r1", "vplus_critic", "vplus_critic_route",
     "★ N=3 확정(49_r1~3). 1 LLM콜 분류→relation질문 관계요약/global질문 커뮤니티요약/그외 없음. "
     "route−critic judge +0.010(3런 전부+). 동력=relation +0.093(3런 일관·강력). "
     "단 단일런(48)의 ‘무회귀’는 미재현 — N=3선 trap −0.022·fanout −0.020 소폭↓, sensemaking +0.004(노이즈, 단일런 +0.050 미재현). vs vector +0.005(1런 −). "
     "= relation 중심 소폭 개선·+1콜. 🔶 조건부 채택(relation 중시 도메인이면). 미중시면 graph+critic이 더 단순·근접."),
    ("★ 관계라벨 그래프 통합 (N=3 최종)", "results/51_labeled_n3_r1", "vplus_critic_route", "rlabel_critic_route",
     "★ 캠페인 최종 best. real 관계쌍을 라벨엣지로(58엔티티·96엣지)+real청크만=깨끗그래프(lazy 1164·9571·84%distractor 대비). "
     "N=3: 라벨풀−lazy풀 judge +0.016(3런≥0)·**recall +0.117(결정론)**, 라벨풀−vector +0.048(3/3). relation +0.085·trap +0.067(둘다 3/3). 대가 fanout −0.133(3/3, sparse 그래프 breadth 누락). "
     "🔑 **distractor 정리=실운영 코퍼스서 그래프 강세 직접증거**(recall 0.79→0.97). 최종 스택=vector+관계라벨graph+critic+라우팅."),
    ("I-5 RAPTOR ※이전frame", "results/24_raptor", "lazy_qt", "raptor",
     "※이전 frame(lazy baseline·40문, step5 vplus 아님). 계층요약 트리. judge 0.838→0.805. sensemaking +0.13이나 fanout −0.20 → net 부정. ❌ 기각."),
    ("I-7 K²RAG 설명층 ※이전frame", "results/27_i7route", "lazy_qt", "i7_gen",
     "※이전 frame(run27·lazy baseline). 압축 엔티티/커뮤니티 설명층. lazy→i7_gen 미미·환각↑·recall 볼륨발. R-5에 dominated → ❌ 기각."),
]
# 🏁 step5 결론: 검색확장(R-2·R-5·R-7·R-3·R-6)은 전부 relation↑/rest↓로 net 무이득. 답변측 A-3 Critic만 net+. 최종 = vector+graph_rag+A-3.
HRt = 4
thdr = ["기법", "① LLM-judge", "② F1", "③ chunk_recall", "④ keyword", "vs vector\n(judge)", "핵심 메모"]
for c, h in enumerate(thdr, 1):
    cell = te.cell(row=HRt, column=c, value=h); cell.font = HDR; cell.fill = HDR_FILL; cell.alignment = CTR; cell.border = BORDER
te.row_dimensions[HRt].height = 30
rt = HRt + 1
for name, expdir, base, tech, memo in TECHNIQUES:
    te.cell(row=rt, column=1, value=name)
    for col, mt in [(2, "judge"), (3, "f1"), (4, "recall"), (5, "keyword")]:
        bv = exp_overall(expdir, base, mt); tv = exp_overall(expdir, tech, mt)
        te.cell(row=rt, column=col, value=(f"{bv:.3f} → {tv:.3f} ({tv-bv:+.3f})" if bv is not None and tv is not None else "—"))
        if bv is not None and tv is not None:
            dv = tv - bv
            if dv >= 0.01: te.cell(row=rt, column=col).fill = PatternFill("solid", fgColor=GREEN)
            elif dv <= -0.01: te.cell(row=rt, column=col).fill = PatternFill("solid", fgColor=RED)
    jv = exp_overall(expdir, "vector", "judge"); jt = exp_overall(expdir, tech, "judge")
    te.cell(row=rt, column=6, value=(f"{jt-jv:+.3f}" if jv is not None and jt is not None else "—"))
    if jv is not None and jt is not None:
        te.cell(row=rt, column=6).fill = PatternFill("solid", fgColor=(GREEN if jt-jv >= 0.01 else (RED if jt-jv <= -0.01 else YEL)))
    te.cell(row=rt, column=7, value=memo)
    for c in range(1, 8):
        te.cell(row=rt, column=c).border = BORDER
        te.cell(row=rt, column=c).alignment = WRAP if c in (1, 7) else CTR
    te.row_dimensions[rt].height = 60
    rt += 1
for col, w in zip("ABCDEFG", [18, 21, 21, 21, 21, 12, 52]):
    te.column_dimensions[col].width = w
te.freeze_panes = "A5"


# ============ 탭 3: 향후 과제 ============
t = wb.create_sheet("향후 과제")
def tput(r, v, bold=False, size=11, fill=None):
    cell = t.cell(row=r, column=1, value=v); cell.font = Font(bold=bold, size=size); cell.alignment = WRAP
    if fill: cell.fill = PatternFill("solid", fgColor=fill)
tput(1, "향후 과제", True, 14)
tput(3, "1. 다음 기법 — A-3 Critic (유일 발목 ‘환각트랩’ 공략)", True, 12, fill="DDEBF7")
tput(4, "• always-both의 유일한 net 손해 = hallucination_trap(−0.053). 그래프 관계청크가 트랩 환각을 유혹.")
tput(5, "• A-3 Critic = 답변의 관계 주장을 다른 LLM이 검증 → 트랩 환각 억제 → net+ 시도. (비정규화 graph_rag 위에 얹음)")
tput(6, "• 참고: R-7 Rerank(34번 테스트)는 희석 회복 효과 있었음(uplift +0.018) → critic과 조합 가능.")
tput(8, "2. 라우팅 (보류 — 데이터로 정당화됨)", True, 12, fill=YEL)
tput(9, "• 관계추론형만 그래프, trap/sensemaking은 vector 단독 → 강점만 취하고 희석 회피. 투영 ~+0.01(무회귀).")
tput(11, "3. 실제 운영 100 PDF 코퍼스 검증 (그래프 진짜 가치 측정처)", True, 12)
tput(12, "• 현 테스트 코퍼스는 합성 distractor 960개 → 그래프 84%가 distractor 구조 → 그래프 가치 과소평가 가능.")
tput(13, "• 운영 코퍼스(distractor 없음)에선 그래프가 더 잘 작동할 여지. 단 도메인 owner 검수 QA 필요(외부 의존).")
tput(15, "원칙: 기법 1개씩 격리 측정 → 효과 본 것만 조합. 같은 50문, baseline=vector 고정. 신호 확정은 N=3(judge 노이즈 ±0.03).", False, 10)
t.column_dimensions["A"].width = 130
for r in range(3, 16): t.row_dimensions[r].height = 26


# ============ 탭 4: 골든셋 50문 ============
def jload(rel):
    return json.load(open(os.path.join(_DIR, rel), encoding="utf-8"))
GF = {"relation_reasoning", "sensemaking"}
EXCLUDE = {11, 46}
qa_all = []
for fn in ["golden_qa.json", "golden_qa_fanout.json", "golden_qa_halluc.json", "golden_qa_graphtypes.json"]:
    qa_all += jload(f"data/qa/{fn}")["qa_set"]
qa_all = [q for q in qa_all if q["id"] not in EXCLUDE]
gs = wb.create_sheet("골든셋 50문")
gs["A1"] = "그래프RAG 평가 골든셋 50문 (uplift=그래프유리 / 무회귀=벡터유리)"; gs["A1"].font = TITLE
gs["A2"] = ("그래프유리(relation_reasoning·sensemaking) = 그래프가 회복해야 할 질문.  "
            "무회귀(control·distributed·multilayer·fanout·hallucination_trap) = 그래프 더해도 안 깎여야 할 질문.  "
            "제외: Q11(단일청크=벡터유리)·Q46(Q16 중복).")
gs["A2"].font = NOTE; gs["A2"].alignment = WRAP
gs.merge_cells("A2:E2"); gs.row_dimensions[2].height = 34
gh = ["ID", "카테고리", "역할", "질문", "근거 청크"]
for c, h in enumerate(gh, 1):
    cell = gs.cell(row=3, column=c, value=h); cell.font = HDR; cell.fill = HDR_FILL; cell.alignment = CTR; cell.border = BORDER
for q in sorted(qa_all, key=lambda x: x["id"]):
    role = "⭐ uplift(그래프유리)" if q["category"] in GF else "무회귀(벡터유리)"
    gs.append([q["id"], q.get("category", ""), role, q.get("question", ""),
               ", ".join(map(str, q.get("required_chunks", [])))])
for ri in range(4, 4 + len(qa_all)):
    for c in range(1, 6):
        gs.cell(row=ri, column=c).border = BORDER
        if c in (2, 3, 4):
            gs.cell(row=ri, column=c).alignment = WRAP
    if gs.cell(row=ri, column=2).value in GF:
        gs.cell(row=ri, column=3).fill = PatternFill("solid", fgColor=GREEN)
for col, w in zip("ABCDE", [5, 24, 20, 60, 14]):
    gs.column_dimensions[col].width = w
gs.freeze_panes = "A4"


# ============ 탭 5: 청크(Autonova 40) 참고 ============
g40 = sorted(jload("data/chunks/golden_40.json"), key=lambda c: c["chunk_index"])
cs = wb.create_sheet("청크(Autonova 40)")
cs["A1"] = "Autonova 테스트 코퍼스 — 실제 내용 청크 40개 (나머지 960개는 검색부하용 distractor)"; cs["A1"].font = TITLE
ch = ["청크번호", "페이지", "카테고리", "본문"]
for c, h in enumerate(ch, 1):
    cell = cs.cell(row=2, column=c, value=h); cell.font = HDR; cell.fill = HDR_FILL; cell.alignment = CTR; cell.border = BORDER
for c in g40:
    cs.append([c["chunk_index"], c.get("page_start"), c.get("category", ""), (c.get("text") or "").strip()])
for ri in range(3, 3 + len(g40)):
    for c in range(1, 5):
        cs.cell(row=ri, column=c).border = BORDER
    cs.cell(row=ri, column=4).alignment = WRAP
for col, w in zip("ABCD", [9, 7, 20, 110]):
    cs.column_dimensions[col].width = w
cs.freeze_panes = "A3"


for old in glob.glob(os.path.join(_DIR, "CAMPAIGN_EVAL*.xlsx")):
    if os.path.abspath(old) != os.path.abspath(OUT):
        try: os.remove(old)
        except OSError: pass
wb.save(OUT)
print("저장:", OUT, "| 탭:", wb.sheetnames)
