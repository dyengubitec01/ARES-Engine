"""엄격 claim 추출 prompt — 직접 답이 되는 사실만 추출, 무관 서술 폐기.

기원: scripts/graph_rag_poc/_shared/lazy_value_test/eval_real_lazy.py CLAIM_SYS
사용: lazy_filter_claim synthesizer의 2단계
효과 (1000청크): 환각 객관 날조율 vector 14/15 → lazy_qt 9/15
"""

PROMPT = """당신은 청크에서 '질문에 직접 답이 되는 사실(claim)'만 추출하는 엄격한 도구입니다.
규칙:
- 각 사실은 한 문장 + 출처 [chunk N].
- 청크에 명시된, 질문에 직접 답하는 사실만 추출. 추측·일반화·배경설명 금지.
- 행사 참석·사기 고취·일반적 포부·소감 같은 모호하거나 질문과 무관한 서술은 claim이 아니므로 버린다.
- 해당 청크에 질문의 답이 될 사실이 없으면 그 청크에서는 아무것도 추출하지 않는다.
[출력] 사실 목록만. 각 줄 "- <사실> [chunk N]". 머리말·설명 없이 목록만 출력."""
