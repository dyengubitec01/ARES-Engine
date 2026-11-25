# 기법 도입 캠페인 — 핸드오프 요약 (2026-06-02)

> 대상: 검색/생성 담당 협업 개발자 + 미래 세션. 상세 원장은 [experiments/LEDGER.md](experiments/LEDGER.md).
> baseline = `lazy_qt` (vector_topk → relevance_filter → claim_extraction → reduce). 측정 = LLM judge(gemma) + keyword/recall, 1000청크 40문(Autonova 통제 도메인).

## TL;DR

- **채택 = R-5 multi-hop retrieval** (회수 기법). 유일하게 두 도메인서 robust 양성.
- **critic(A-3)은 도메인 옵션** (관계트랩엔 도움, 오귀속/나열엔 무해~해). A-1 라우팅으로 조건부 적용 가능하나 always 대비 wash.
- **8기법 중 R-5만 채택, 6 기각.** 추가 기법 시도 가치 낮음(아래 "축" 설명).
- **사업 결론: Qwen3 Full 그래프 PoC 디프리** — Lazy(vector)+R-5+critic이 Full 우위 예측 실질갭 5/5 커버.

## 채택 스택: R-5 multi-hop

**작동**: 1차 dense 회수 → LLM이 "추가로 찾을 연결 대상" 검색어 생성 → 2차 타깃 재검색 → 풀 확장. 연결 질문 아니면 빈 followup(=vector_topk와 동일, 자기 게이팅).
- 모듈: [pipeline/retrievers/multihop.py](pipeline/retrievers/multihop.py)
- 효과: Autonova judge 0.835→0.848(N=3 확정), **실도메인 0.738→0.812**(집계 +0.11). recall +0.06~0.09.
- 왜 통하나: 1차 결과의 *실제 엔티티*로 정밀 확장 → 노이즈 없이 회수만 늘림.

**실행**:
```bash
python eval/runner.py experiments/11_multihop.yaml          # R-5 vs baseline (Autonova)
python eval/runner.py experiments/14_realdomain.yaml        # 실도메인(53청크) lazy/R-5/critic/gated
```

**critic (옵션)**: `pipeline/synthesizers/stages/critic_gated.py`(A-1 라우팅: 관계트랩 분류시만 적용) 또는 `verify`+`critic_relation`(always). 관계-환각 트랩 많은 도메인에만 권장.

## 기각 기법 (재시도 방지)

| 기법 | 축 | 기각 이유 |
|---|---|---|
| I-3 엔티티 그룹핑 | 생성 재조직 | 환각 −0.14 (엔티티 인접배치가 거짓관계 유발) |
| A-2 Sub-Q 분해 (+gated) | 생성 분해 | net −0.03, 나열형 분해 역효과 |
| R-2 Hybrid (BM25+dense) | 회수(broad) | recall↑이나 lexical 노이즈로 keyword −0.09 |
| R-7 Rerank+trim | 정밀도 | relevance_filter와 중복+손실, keyword −0.07 |
| A-7 HyDE | 회수(drift) | recall −0.20 붕괴 (가상답변이 사적 코퍼스서 drift) |
| critic_v2 | critic 튜닝 | 프롬프트 재작성이 전 답변 파괴(0.46) |

**축 교훈**: 회수가 유일한 병목이었으나 **R-5의 타깃·grounded 재검색만** 통함. broad lexical·HyDE drift·정밀도 트림·생성 재조직은 전부 노이즈/손실. 남은 미시도(R-9 정밀·G-4 집계)도 실패 축이라 가치 낮음.

## 측정 프로토콜 (필수)

- **생성 temperature=0** (`gen_temperature: 0` in YAML). judge는 이미 temp=0.
- **채택/기각 판정 = N=3 런 평균** (judge 노이즈가 효과만큼 큼: 카테고리 ±0.06, 개별 ±0.3 at temp=0.1; temp=0서 ±0.1).
- 전체(n=40) ±0.016은 단일런 가능, 카테고리/개별은 N=3 필요.
- critic 프롬프트는 극도로 취약 — 작은 변경이 catastrophic(critic_v2 사례).

## 결론 & 다음

- **핵심 가설 "Lazy+기법으로 Full 대체" = 실질 YES**. Tier-1 8문 중 실질갭 5문(Q6·8·15·16·28)을 R-5+critic 커버. → **Qwen3 Full PoC 디프리.** (근거: [[per_question_advantage]] 메모리)
- **일반화**: R-5는 실제 도메인(사내 사업 문서 53청크)서 더 큰 효과(집계 중심). critic은 도메인별.
- **남은 마일스톤(양산 단계)**: 실제 100 PDF 전체코퍼스 + 검수된 golden QA로 본격 일반화. 현재 `data/qa/production_qa.json`은 draft(도메인 owner 검수 필요).

## 포인터
- 실험 원장/Tier-1 보드: [experiments/LEDGER.md](experiments/LEDGER.md)
- 메모리: `technique_campaign_ledger`(전말·종료요약), `per_question_advantage`(Full PoC 결정)
- 코드: `pipeline/retrievers/multihop.py`, `pipeline/synthesizers/stages/{critic_gated,rerank,entity_group}.py`, `experiments/11~17_*.yaml`
