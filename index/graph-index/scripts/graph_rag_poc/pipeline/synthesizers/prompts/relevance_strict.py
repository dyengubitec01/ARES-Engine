"""엄격 relevance 필터 prompt — 직접 답 되는 청크만 통과시킴.

기원: scripts/graph_rag_poc/_shared/lazy_value_test/eval_real_lazy.py RELEVANCE_SYS
사용: lazy_filter_claim synthesizer의 1단계
주의 (Phase 1 PoC 교훈): "넓게 보되" 같은 표현은 distractor를 다 통과시켜 합성을 망친다.
기본값=제외 원칙으로 엄격하게 가야 함.
"""

PROMPT = """당신은 질문에 '직접 답이 되는 사실'을 담은 청크만 골라내는 엄격한 필터입니다.
판정 기준:
- 청크가 질문에 대한 구체적 답(사실/관계/수치/사건)을 담고 있을 때만 관련(relevant)으로 판정.
- 질문의 인물·주제를 단지 언급만 하거나, 행사 참석·일반 활동·소감·포부 등 답과 무관한 배경은 제외.
- 애매하면 제외한다(기본값 = 제외).
[출력] 오직 JSON: {"relevant": [직접 답이 되는 chunk 번호들]}"""
