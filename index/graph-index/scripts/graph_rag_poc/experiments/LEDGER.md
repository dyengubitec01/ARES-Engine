# 기법 도입 캠페인 원장 (LEDGER)

> 목적: [[techniques_catalog]]의 기법을 lazy_qt baseline에 하나씩(또는 조합으로) 도입하며 **Tier-1 8문 잠식**을 추적.
> baseline = `lazy_qt` (relevance_filter + claim_extraction + reduce, 1000청크 measurement).
> 측정·보고 규칙은 메모리 `technique_campaign_ledger` / `per_question_advantage` 참조.

## 네이밍 규칙
- 실험 파일 = `NN_<태그>.yaml`, YAML 안에 `techniques: [카탈로그ID]` 명시.
- 단일: `07_egroup` (`techniques: [I-3qt]`) / 조합: `NN_egroup+subq` (`techniques: [I-3qt, A-2]`).
- 같은 YAML에 항상 `baseline + 처리` 트랙 동시 측정(격리). 조합은 구성 단일 측정 후.

## Tier-1 8문 누적 보드

목표: 6+/8 잠식 시 Qwen3 Full PoC 캔슬. "도달" = 해당 문항에서 처리 트랙이 baseline(lazy_qt) 대비 명확 개선 + Full 예측 수준 도달.

| Q | 카테고리 | 질문 | Full이 이기는 이유 | 도달시킨 실험/기법 | 상태 |
|---|---|---|---|---|---|
| 5  | 분산통합 | 김지훈 경력 종합 | 인물 디스크립션 pre-aggregate | (lazy_qt 이미 0.9) | 갭 아님 |
| 6  | 분산통합 | 박서연 경력 종합 | 인물 디스크립션 | **R-5 0.7→0.9 (N=3 확정)** | ✅ 도달 |
| 8  | 분산통합 | KAIST 협력 결과 | 기관 디스크립션 6청크 통합 | **R-5 0.7→0.9 (N=3 확정)** | ✅ 도달 |
| 15 | 관계 | 박서연 직간접 영향력 | 다중 hop traversal | **R-5 0.7→0.8** (A-1 gated가 critic 충돌 회피해 보존) | ✅ 도달 |
| 16 | 관계 | 오태경 영입+보고라인 | 관계 라벨 체인 | **R-5 0.4→1.0 (N=3 확정)** | ✅ 도달 |
| 21 | fanout | 김지훈 연결 인물 | 엣지 1-hop traversal | — | 미도달 |
| 23 | fanout | 한수정 연결 인물 | 영입/동료 엣지 | — | 미도달 |
| 28 | 환각 | 최영민-강현우 | 클린 엣지 부재 | **R-5+critic(A-3) 0.7→1.0** | ✅ 도달 |

**누적 잠식: 5 / 8 (N=3 확정, 0분산)** — 채택 스택 R-5+critic(v1): Q5·Q6·Q8·Q16·Q28 WIN. 전체 judge 0.835→**0.872**(+0.037) 확정. 잔여: Q15(R-5 0.8↔critic 0.7 충돌), Q21·Q23(비실질갭, baseline 0.8~0.9; Q23은 R-5 fanout 부작용 0.9→0.7).

| **15_routed** (A-1) | R-5+A-1 gated critic | lazy_qt | 5/8 | 전체 judge lazy 0.838 / always-critic 0.873 / **gated 0.880**(최고). gated가 Q15 회복(0.7→0.8, critic 충돌 회피) + Q16·Q28 관계트랩 유지(1.0). **실질갭 5/5(Q6·8·15·16·28) 전부 커버.** 분류로 critic 조건부 적용 성공 | +1콜(분류) | 🟡 **메커니즘 OK, always 대비 wash** |

**A-1 핵심(정직 정정)**: critic을 'relation-pair 질문'에만 조건부 적용(`critic_gated` + 명시 분류). 분류 정확히 작동(Q14·15→skip, Q16→적용), Autonova선 Q15 회복하며 최고 0.880. **그러나 always-critic 대비 깨끗한 승리 아님**: Autonova +0.007(노이즈), 실도메인 **gated 0.787 < always 0.819**(critic 집계 정리효과 포기 + 트랩 안전이득은 vLLM 노이즈에 묻힘). → gated≈always, 도메인의존. **확정: R-5만 robust 채택, critic은 형태 무관 작고 도메인의존적.**

### 🌐 실제 도메인 일반화 (2026-06-02, `14_realdomain`)
- 사내 사업 문서 53청크 + draft QA 16문, top_k=8. judge lazy/R-5/R-5+critic = 0.738/0.812/0.825.
- **R-5 robust 일반화**(judge +0.074, 집계 +0.11, 트랩 +0.20) — 실제 도메인서 효과 더 큼. **A-3 critic은 도메인특이적**(오귀속트랩 Q14 0.4→0.0 파괴, 환각 0.70→0.57). 새 실패모드 "역할 오귀속".
- 한계: 소코퍼스+draft QA. 진짜 검증=전체 100PDF + 검수 QA(양산 시).

### 🏁 캠페인 결론 (2026-06-01)
- **채택 스택 = R-5 multihop + A-3 critic(critic_relation v1)**. 기각 4(egroup·A-2·A-2gated·R-2·critic_v2), 채택 2(R-5·A-3v1).
- **핵심 가설 "Lazy+기법으로 Full 대체" → 실질적 YES.** 예측된 Full우위 8문 중 5문 잠식(N=3). 미잠식 3문 중 Q21·Q23은 baseline이 이미 0.8~0.9(진짜 Full갭 아님), Q15는 R-5 단독으론 도달(critic과 충돌일 뿐). **즉 진짜 Full갭은 거의 다 query-time으로 닫힘.**
- **Qwen3 Full 그래프 PoC 권고: 디프리/불필요 쪽.** 17h/1000청크 추출비용 대비, query-time R-5+critic이 갭을 메움. 단 5/8은 결정룰 "부분대체" 상단이라 ROI·고객 도메인 분포 감안한 최종 판단 필요.
- 한계: 통제 도메인(Autonova) 40문 한정, judge=동일 Gemma, 스택 콜 ~2배.

| **11_multihop** (R-5) | R-5 (multi-hop iterative) | lazy_qt | 4/8 | ✅ **첫 net 양성**: judge 0.835→0.848(+0.013), kw+0.010, f1+0.005, **recall+0.088**. 타깃 적중 Q16 0.4→1.0·Q15 0.7→0.8, relation+0.150. 경미 손해 fanout−0.04·환각−0.03(Q23 0.9→0.6). 자기게이팅 대체로 작동 | 3→3(retriever LLM콜 미집계) | ✅ **채택 (N=3 확정)** |

**11_multihop N=3 확정 (2026-06-01)**: 3회 완전 동일(이번엔 temp=0 노이즈 0). 전체 judge +0.013 확정 양성. **Tier-1 4/8 잠식(Q6·Q8·Q15·Q16) 안정**. R-5 = 캠페인 첫 채택 기법. 2차 재검색이 multi-hop(Q15·16) + 흩어진집계(Q6·8) 둘 다 커버. 손해 = Q23 fanout 0.9→0.6(2차 노이즈) + 환각/multilayer 경미 → **게이팅 v2로 회수 시도 가치.**

| **12_multihop_critic** (A-3) | R-5 + A-3 critic | lazy_qt | **5/8** | 전체 0.835/0.840/**0.872**. **Q28 0.7→1.0**(환각 distractor 기각), 환각카테고리 0.69→0.78. R-5 win 보존(Q6·8·16) but **Q15 0.8→0.7 과잉교정**. distributed/relation 소폭 −0.03~0.04 | +1콜(critic) | ✅ **채택 후보 — Q15 회수 위해 critic 보수화 검토** |

| 13_multihop_critic_v2 | A-3-v2 (critic 보수화 시도) | lazy_qt | 1/8 | ❌ **폭망 0.46**. critic_v2가 교정 템플릿("관계 없음")을 전 질문에 그대로 출력→draft(R-5 win 포함) 파괴. 환각만 0.90(우연). | — | ❌ **폐기, v1 복귀** |

**critic v2 교훈**: Q15(5→6/8) 회수하려 critic 프롬프트 재작성 → 모델이 교정 케이스를 universal 적용, 정상 답변까지 "관계 없음"으로 덮음. **critic 프롬프트는 매우 취약(작은 재작성이 catastrophic)**. v1(critic_relation, 0.872/5-8)이 채택본. Q15 회수는 마진 작고 리스크 커서 중단.

### 🔬 Tier-1 8문 정성 진단 (2026-06-01, judge 독립, baseline lazy_qt 답변 직독)
- **이미 해결(갭 아님)**: Q5(kw4/4)·Q23(체인 정확)·Q21(거의) → "Full 우위 8문" 예측이 과대평가. **실질 갭 ~5문**.
- **실질 갭 = 3개 이질적 실패모드**:
  - multi-hop 체인 (Q15 간접 영향력·Q16 보고라인): 직접 hop은 맞히나 간접 체인 못 조립 → **R-5 타깃 재검색** 후보
  - 흩어진 엔티티 집계 (Q6 공동창업 누락·Q8 recall0.33+distractor환각): 정보가 수십청크 분산 → top_k 한계, Full 디스크립션이 진짜 우위
  - distractor 환각 (Q28): 노이즈 청크가 가짜 관계 → **A-3 critic/엄격 필터** 후보
- **3연속 기법 실패의 진짜 원인**: 갭이 이질적인데 egroup·A-2·R-2는 모든 질문에 동일 적용 → 한 모드 도우면 다른 모드 손상. **broad 기법 구조적 불가, 모드별 타깃+라우팅 필요.** (확정 기준 = 노이즈 넘는 안정적 개선. 아래 judge 분산 문제로 단일런 판정 보류 중)

> ⚠️ **측정 신뢰성 (2026-06-01 조사 완료)**:
> - 노이즈 뿌리 = **생성(chat) temperature=0.1** (judge는 이미 temp=0). 답변이 런마다 달라져 점수 흔들림.
> - 대책으로 `gen_temperature: 0` 도입(runner가 전역 오버라이드). **but temp=0도 vLLM 비결정성으로 답변이 런마다 다름** — probe 2런에서 5문 중 2문 답변/점수 상이(kw·f1까지 변동). greedy여도 배칭·prefix cache·부동소수점 탓.
> - **노이즈 크기**: temp=0.1 개별 ±0.3 → temp=0 개별 ±0.1(60% 동일). ~3배 감소했으나 잔여 존재.
> - **측정 프로토콜(확정)**: 모든 평가 `gen_temperature: 0` + **결정 판정은 N=3 런 평균**. 단일런은 방향 참고만. 카테고리/전체(n↑)가 개별문항보다 안정. 효과 < ~0.05는 다중런 없이는 단정 금지.
> - egroup −0.140는 노이즈 한참 초과 → 기각 유효. A-2 ±0.02~0.07 효과는 다중런 평균으로 재확인 필요.

## 마스터 원장 (실험별)

| 실험 | 기법(ID) | baseline | Tier1 잠식 ?/8 | 카테고리 breakdown | 평균콜 | 판정 |
|---|---|---|---|---|---|---|
| 07_egroup_smoke | I-3qt (엔티티별 청크 그룹핑) | lazy_qt | 미확정(스모크 5문) | 분산통합 Q5~9: judge 평균 0.88=0.88, **kw +0.10**(Q6·Q8 0.5→0.75), Q8 judge 0.8→0.9, Q9 −0.1 회귀 | 3→4 | 약한 양성 → full 필요 |
| 07_egroup (1차 시도) | I-3qt | lazy_qt | ❌ 무효 | GPU 서버 런 ~1분 후 DNS 끊김 → 재실행 | — | 무효 |
| **07_egroup** (2차, 정상) | I-3qt | lazy_qt | **1/8** (Q23만, 실질 0) | judge 0.830→**0.775(−0.055)**. 환각 0.713→0.573(**−0.140**💥), 타깃 분산통합 0.84→0.82(−0.02), Q28 0.9→0.4 | 3→4 | ❌ **기각** |

| **08_subq** (A-2 ungated) | A-2 (Sub-Q 분해) | lazy_qt | 4/8(노이즈內) | judge 0.845→0.812(−0.032, **temp=0.1·temp=0 양런 동일 → 확정**), kw −0.050, 콜 2배. 집계형↑(분산+0.02·sense+0.067·관계+0.075), 나열형↓(fanout−0.12·multilayer−0.10) | 3→6.1 | ❌ **ungated 기각** → v2 |

| **09_subq_gated** (A-2 v2) | A-2-gated | lazy_qt | 2/8 | judge 0.835→0.792(**−0.042**, ungated보다 나쁨). 프롬프트 게이팅 실패(24/40 분해, fanout −0.12 그대로). 카테고리 노이즈 폭로: sensemaking baseline 08런 0.90 vs 09런 0.767(±0.13, n=3) | 3→? | ❌ **기각** |

| **10_hybrid** (R-2) | R-2 (dense+BM25 hybrid, α=0.7) | lazy_qt | 2/8 | **recall +0.059**(첫 회수 개선!) but **keyword −0.092**, judge −0.015. 회수 풀에 gold↑이나 lexical 노이즈도↑→dense 고품질 청크 밀어냄(top_k=20 고정). | 3→3 | ❌ **기각(α=0.7)** |

**R-2 핵심 발견**: baseline dense recall 0.808 = gold 81% 이미 회수 → **recall은 binding constraint 아님**. 회수 늘리면 노이즈 동반 → 답변 악화. egroup·A-2(재조직)+hybrid(회수확대) **3연속 net 부정**. → 생성측·회수측 단순 기법으론 Tier-1 못 깸 정황. Tier-1은 구조(엔티티 디스크립션·multi-hop·엣지)가 진짜 필요할 가능성↑.

| **16_rerank** (R-7) | R-7 (LLM listwise rerank+trim) | multihop(R-5) | — | ❌ judge −0.013, **keyword −0.067**(deterministic), recall 불변. 풀 트림이 gold는 유지하나 보조청크 손실→답변 덜완전. relevance_filter와 중복. | +1콜 | ❌ **기각** (N=3 불필요, 명확 부정) |

| **17_hyde** (A-7) | A-7 (HyDE 가상답변 시드) | multihop(R-5) | — | ❌ **recall −0.205 붕괴**, keyword −0.077, judge −0.045. HyDE 가상답변이 사적 코퍼스 실내용과 어긋나 retrieval 오도. | +1콜 | ❌ **기각** (N=3 불필요) |

**A-7 교훈**: HyDE는 일반지식 도메인용. 고유명사 많은 사적 코퍼스선 가상답변이 drift→recall 붕괴. **recall 축이라고 다 좋은 게 아님 — R-5(타깃·grounded 재검색)만 통하고, R-2(broad lexical)·A-7(HyDE drift)은 노이즈/drift로 해침.**

| **18_subanswer** (G-4) | G-4 Sub-Answer 집계 | lazy_qt(+R-5) | 2/8 | ❌ judge 0.845→0.823(−0.022), **f1 −0.108**(sub답변 종합 장황), kw +0.023. fanout −0.08·multilayer −0.07 | +N콜 | ❌ **기각** (예상대로 분해 축) |
| **19_multistage** (R-6) | R-6 Multi-Stage(dense→BM25) | lazy_qt(vector) | — | ❌ judge 0.870→0.755(**−0.115**), **환각 0.79→0.51(−0.28)**, kw −0.077, recall +0.027. BM25 재정렬이 lexical 겹침 상위화→관계 날조 | +0콜 | ❌ **기각** (R-2 실패모드 심화) |
| **20_duallevel** (R-3) | R-3 Dual-Level(low/high 키워드) | lazy_qt(vector) | — | ⚪ judge 0.835→0.833(**−0.002 무효**), kw +0.027·recall +0.026(노이즈 내). LLM 타깃 키워드라 R-2보다 무해하나 이득 없음 | +1콜 | ⚪ **중립(무효)** |
| **21_answertype** (R-9) | R-9 Answer-Type 예측 | lazy_qt(vector) | — | ⚪ judge 0.853→0.882(+0.029)·kw −0.037 혼재(net 중립). ※Q1~34만 유효(서버 다운으로 Q35~40 err 제외) | +1콜 | ⚪ **중립** |

| **22_graphkhop** (R-8) | R-8 Graph k-hop(2-hop, GLiNER2) | lazy_qt(vector) | — | ⚪ judge 0.835→0.830(−0.005)·**recall 0 불변**·kw −0.031. 그래프가 vector 대비 추가회수 없음(exp04 재확인). 기존 그래프 사용 | +0콜 | ⚪ **중립** |
| **23_graphpath** (R-4) | R-4 Path Discovery(GLiNER2) | lazy_qt(vector) | — | ❌ judge 0.835→0.767(−0.068)·**recall −0.146**(경로 노드로만 제한→관련 청크 누락)·kw −0.050. 기존 그래프 사용 | +0콜 | ❌ **기각** |
| **24_raptor** (I-5) | I-5 RAPTOR(1레벨 요약40) | lazy_qt(원청크) | — | ❌ judge 0.838→0.805(−0.033). **sensemaking +0.13·distributed +0.04(설계대로 global↑)** but **fanout −0.20·환각 −0.06**(요약이 엔티티 specificity 흐림). net 부정, 카테고리 trade-off | +0콜(빌드 40콜) | ❌ **기각** (sensemaking 도메인이면 재검토) |
| **27_i7route** (I-7) | I-7 K²RAG 압축 설명층(additive). 엔티티281(band2~30)+커뮤11 설명, 압축본/full A/B 빌드 후 full 레이어로 다운스트림. route=라우팅전용 / gen=설명도 답변포함 | lazy_qt(vector, max_index) | — | **N=3 결정론(±0.000)**. recall 0.808→**0.897(+0.089)** 양트랙 동일=R-5 수준 도달하나 **볼륨발**. ❌ route judge **−0.023**·kw −0.065(추가청크 distractor). gen judge **+0.012**(미미)지만 **환각 10→12**(conflation 누출, Maps←Vision류). 설명빌드: full retention 69%·conflation 발견 | +0콜(빌드 단계 압축100+설명292×2) | ❌ **기각** (R-5에 모든 축 dominated: 같은 recall, judge↓, 환각↑) |

### 🧩 MAX 스택 검증 (조합 시너지, 차수별 — 탐색 중)
- **1차 (25_maxstack, 2026-06-04)**: R-5(검색)+R-9(답유형필터)+A-1/A-3(게이팅 critic). 같은 런 baseline 0.853 / R-5만 0.835 / **MAX 0.820**. **시너지 없음**(MAX≈R-5, judge −0.015). 카테고리 R-5와 거의 동일(이득은 R-5 몫), 환각만 critic이 0.68→0.64로 악화. keyword +0.075(장황). Tier-1 R-5 4/8→MAX 5/8(critic Q28). ⚠️ 이 런 baseline 높게 뽑힘=노이즈 → 정밀판정 N=3 필요. 별도 엑셀 탭에 누적.
- (인프라: 1차 시도 서버 다운으로 무효→재실행. 캠페인 6번째 다운)

### 📋 보강 라운드 종합 (7기법, 2026-06-02)
Full그래프 불요 기법 전수(데이터 완성용). **결과: R-5 외 신규 채택 0.** G-4❌·R-6❌·R-4❌·I-5❌(net 부정) / R-3⚪·R-9⚪·R-8⚪(중립). 
- **재확인된 패턴**: 회수=R-5 타깃재검색만 통함(broad/path/hybrid 다 실패). 정밀/필터(R-7·R-9)·분해(A-2·G-4)·그래프회수(R-8·R-4·exp04) 무효~부정.
- **유일한 신규 관찰**: I-5 RAPTOR가 sensemaking +0.13(설계대로)이나 fanout −0.20으로 net 부정. critic과 같은 "카테고리 trade-off" 부류 → 도메인 따라 옵션.
- 미시도 남은 것 = Full그래프 필요(I-4·I-11·G-2 등)뿐 = Qwen3 Full PoC 영역.

**I-7 추가 기각 (27_i7route, 2026-06-04)**: K²RAG 압축을 "설명층 cheap 생성" 용도로 재해석해 테스트(lazy 그래프에 엔티티/커뮤니티 설명 additive). 빌드 검증: 압축이 설명을 죽이진 않음(full 대비 fact retention 69%)이나 **cross-entity conflation 오류 발생**(같은 압축윈도우의 타 엔티티 사실 혼입). 다운스트림 N=3 결정론: **recall +0.089(볼륨발, R-5 수준 도달)이나 답변 전환 실패** — route judge −0.023, gen +0.012뿐+환각↑. **R-5에 dominated**. → I-3/I-5/I-6에 이은 "설명/요약 레이어 = 우리 셋업서 손해" 4번째 확증. **양산 결론 불변: 설명층 불요, R-5만.** (압축 자체는 관계 9571층에서만 비용이득이나 그 층이 가장 환각 위험이라 미추진)

> ⚠️ **infra 불안정 기록**: `*.example.com`(LLM main + 임베딩 gateway, 내부망 192.168.x) 캠페인 중 **4~5회 간헐 DNS 실패** (07 / R-9×2 / R-8×1). VPN/내부DNS 깜빡임 추정. 생성 살면 judge만 재실행(run_judge_on_dir). **양산 측정 신뢰성에 영향 — 네트워크/서버 안정화 필요.**

**R-7 교훈**: 정밀도 축(rerank+trim)은 도움 안 됨 — lazy_qt에 이미 relevance_filter(정밀 선별) 있어 중복+손실. **회수(R-5)는 병목이었지만 정밀도는 이미 충분**. egroup·A-2·R-2·R-7 = 회수확대(R-5) 외 단순 재조직/정밀 기법 4연속 기각. **R-5만 robust 재확인.**

**A-2 계열 최종 기각 (08+09)**: 전체 net 일관 부정(ungated −0.032, gated −0.042). 프롬프트 기반 게이팅은 LLM이 안 따름(나열형까지 분해). **핵심 부산물**: temp=0에서도 n=3 카테고리 baseline이 런마다 ±0.13 흔들림 → **카테고리/Tier-1 단위 단일런 판정 불가 확정**. 신뢰 가능 = 전체(n=40, ±0.016)뿐.

**08_subq 관찰**: 패턴이 가설과 일치(집계·종합형 개선, 나열형 분해 역효과). egroup과 달리 환각 파괴는 경미(−0.06, 분해프롬프트가 관계질문 분해 억제 덕). 다만 **net은 약간 마이너스 + 2배 콜** → ungated 채택 불가. **단, judge 분산 때문에 카테고리 ±0.06 효과는 단정 불가** → 측정 경화 선행 필요. 유망 후속 = fanout/multilayer도 분해 억제하는 **게이팅 v2**.

**07_egroup 기각 사유**: (1) 타깃(분산통합) 미개선. (2) 엔티티 그룹핑이 두 엔티티 청크를 인접 배치 → 없는 관계 날조 = lazy_qt 핵심강점(환각 억제) 파괴(−0.140). graph_rag_principle의 "클러스터링→거짓관계 착각" 실패모드 재현. **방법론 교훈: 스모크는 강점영역(환각) 포함해야 net 회귀 포착** — 분산통합만 본 스모크는 착시(약한 양성)였음.

**관찰 메모(07 스모크)**: 메커니즘 정상 작동(엔티티 추출 +1콜 → 청크 엔티티별 재정렬). 타깃 Q6·Q8에서 keyword 완성도 상승 = "집계 시 항목 누락" 약점 직격 확인. 단 judge는 비타깃 Q9 회귀로 평균 상쇄. full 40문에서 노이즈 줄여 재확인 필요. Q9 회귀 원인(비타깃 질문에서 엔티티 그룹핑이 오히려 방해?) 주시.

## 보고 형식 (실험 완료 시 채움)
```
[Tier 1] Full 우위 8문 잠식: ?/8
  - 분산통합(Q5,6,8): ?/3
  - 관계(Q15,16):     ?/2
  - fanout(Q21,23):   ?/2
  - 환각(Q28):        ?/1
[Tier 2] Lazy 우위 확장: 9→?문
[참고] Vector 우위 영역: 9→?문 / 평균콜: 3→?
```

---

## 🔗 그래프RAG 통합 캠페인 (2026-06-05, 신규 방향)

**배경**: 운영 벡터RAG에 그래프RAG를 *통합*하는 게 목적(대체 아님). 이전 37기법(벡터baseline) 테스트데이터는 초기화하고 새 프레임으로 재출발.

**프레임 확정**: `vector` vs `vector+graph`(always-both). 골든셋 50문(`exclude_ids:[11,46]`) = 그래프유리(relation9·sensemaking8) + 무회귀(control4·distributed5·multilayer4·fanout5·trap15). 보강 12문 `golden_qa_graphtypes.json`.

**구현**: `graph_rag`(entity_linking 이름매칭+neighborhood1hop+path+community off, 랭킹=시드가중 hits+focus) / `vector_plus_graph`(union, always-both) / runner `exclude_ids`+query_text 주입.

**실험 원장**:
| 실험 | 내용 | 결과(같은런 ALL Δ) | 판정 |
|---|---|---|---|
| 33_vector_plus_graph | 초기 always-both(구 graph_rag) | −0.020. graph가 일반목록·distractor 끌어옴(희석) | graph_rag 정밀화 필요 |
| 34_vplus_rerank | +R-7 rerank(top15) | rerank가 희석 회복(vplus −0.048→rerank −0.018, uplift +0.018) | rerank 효과 있음 |
| 35_graph_precise | **graph_rag 정밀화(이름매칭 linking+focus)** | **−0.008(거의 break-even)**. recall 0.729→**0.778**. relation+0.011·dist+0.040·fanout+0.040 양수, **trap −0.053만 발목** | **✅ 최선 설정** |
| 36_graph_canon | 정규화 그래프(엔티티1164→955·엣지9571→6819) | **−0.030 악화**. relation +0.011→**−0.100**. recall 동일(0.778) | ❌ **정규화 폐기**(변형엣지가 실은 랭킹 도움) |

**graph_rag 튜닝 소진**: cosine→엔티티밀도→focus→min_rel→이름매칭(✓)→정규화(✗). 최선=run35.

**구축 냉정감사(2026-06-05)**: 구축 정상(entity_chunks 100%정확·관계엣지 포착·추출누락 0, 만도만 누락=무영향). 단 **그래프 84%엣지·88%엔티티가 distractor 구조**(합성 distractor 960개) → traversal이 distractor 헤맴. **더 보완할 빌드 개선 없음 — 한계는 빌드가 아니라 테스트 코퍼스 아티팩트.** 측정 가치는 distractor로 과소평가 가능, **실코퍼스에선 더 나을 여지.**

**현 결론**: 그래프 가치는 작지만 실재(relation/distributed/fanout 양수). always-both 거의 break-even, **유일 발목=hallucination_trap**(그래프 관계청크가 환각 유혹 강화, 본질문제). → 다음: **A-3 Critic**(trap 공략) 또는 **라우팅**(trap/sensemaking 제외), 또는 **실 운영코퍼스 검증**.

### step5 논문기법 적용 (2026-06-06)
graph baseline(vplus=vector+graph_rag) 위에 기법 격리→조합. 4지표(judge/f1/recall/keyword) 측정.

| 실험 | 기법 | vs 기준 | 판정 |
|---|---|---|---|
| 37/39/40 | **A-3 Critic(gated)** | **N=3: vs vector judge +0.011·kw +0.016 (3런 전부+)** trap +0.122·relation −0.048(대가) | ✅ **채택** |
| 38 | R-7 Rerank(top15) | 전체 judge −0.022. fanout −0.10 등 추림 손실(정밀 graph_rag엔 희석 적어 역효과) | ❌ 기각 |
| 39 | critic v3(정제청크+보수프롬프트) | v1보다 못함(trap 잡는 힘도 약해짐) | ❌ 기각 |
| 41 | R-5 Multihop+graph 단독 | judge −0.018(trap −0.113 발목). relation +0.022·recall +0.066 강함 | 🔶 단독 기각·조합후보 |
| 42 | **graph+R-5+Critic 조합** | vs 채택본 judge +0.002(무승부)·recall +0.066. **relation +0.156**(R-5가 critic 과교정 회복)·trap −0.087. net 무변+비용2배 | 🔶 미채택(관계중시면 옵션) |

**🏁 사이클 결론**: **확정 채택 = vector + graph_rag + A-3 Critic.** 운영 벡터RAG를 N=3로 넘는 첫 구성. graph+critic=trap강/relation약, graph+R-5+critic=relation강/trap약(비용2배). 그래프 가치는 작지만 실재, distractor 코퍼스라 과소평가 가능 → 실 운영코퍼스가 진짜 측정처. 신규 구현물: `graph_rag`(이름매칭 linking), `vector_plus_graph`, `multihop_plus_graph`, `canonicalize_graph.py`(폐기), critic_gated `use_relevant` 옵션, runner `exclude_ids`.

### step6 구조 축(그래프 설명) + 라우팅 (2026-06-07)
"그래프에 엔티티/관계/커뮤니티 설명이 없다"는 미련 → 설명 3종 체계 테스트. real청크서 LLM 요약 추출.
- ❌ 엔티티 설명(I-7): 청크와 중복 → 이미 기각.
- 🔶 **관계 요약**(`46` relation_inject): 채택본 위 judge +0.004(노이즈)·keyword +0.035·**recall 무희석**. relation +0.033·trap +0.020. 검색축과 달리 구조축은 희석 없이 보탬. 단 fanout −0.060(나열질문 누수).
- 🔶 **커뮤니티 요약**(`47` community_inject, real 서브그래프 4커뮤니티): **sensemaking judge +0.050 성공**(관계요약이 못한 곳!). 단 마커 게이팅 누수 → trap −0.107 등 collateral → 전체 −0.032.
- **🔑 두 구조요약 다 "타깃엔 보탬, 엉뚱한 질문엔 노이즈" → 정밀 분류(A-1 라우팅)가 열쇠.**
- ★ **A-1 라우팅+구조축 통합**(`48`→`49` N=3): 1 LLM콜 질문분류→맞는 요약만 주입. **route−critic N=3 +0.010(3런 전부+), 동력 relation +0.093(일관)**. 단 단일런의 무회귀(trap/fanout↑)는 미재현 — N=3선 trap −0.022·fanout −0.020 소폭↓, sensemaking 노이즈. vs vector +0.005(얇음)·+1콜. → 🔶 **조건부 채택**(relation 중시 도메인).

**🏁 갱신 결론**: 확정 채택 = vector+graph_rag+A-3 Critic(robust). + 라우팅 구조주입은 relation 중심 소폭 개선(조건부). 검색축(R-2/5/7/3/6) 전부 무이득. 구조축(관계/커뮤니티 요약)은 직교라 보태나 작고 라우팅 의존. 신규 구현물: relation_inject·community_inject·route_inject stage, build_relation_summaries.py·build_community_summaries.py. 미래: Full 관계라벨 그래프(relation 정공법) + 실운영 코퍼스 검증.

### step7 관계라벨 깨끗그래프 통합 (2026-06-08) — 캠페인 최종
"기법 전부 통합" 요청 → 이긴 것 다 합치고 + relation 정공법(관계라벨 그래프) 추가.
- 관계라벨 그래프(`build_relation_labeled_graph.py`): real 97관계쌍→라벨엣지(58엔티티·96엣지)+real청크만. lazy(1164·9571·84%distractor) 대비 깨끗.
- ★ **통합 N=3**(`50`→`51` r1~3): vector+관계라벨graph+critic+라우팅. **라벨풀−vector judge +0.048(3/3)·recall +0.176**. 라벨풀−lazy풀 +0.016(3런≥0)·recall +0.117. relation +0.085·trap +0.067(3/3). 대가 fanout −0.133(3/3, sparse 그래프 breadth 누락)·distributed 약간↓.
- 🔑 **최대 발견**: 깨끗그래프 >> distractor그래프(recall 0.79→0.97). 구축감사의 "84% distractor가 가치 깎음"을 N=3 입증 → **실운영 코퍼스선 그래프RAG 훨씬 강할 것**(직접증거).
- 인프라: LLM chat()에 재시도(4회 백오프) 추가(`llm.py`) — 서버 블립 매달림/크래시 방지. judge null은 `run_judge_on_dir` 재실행 복구.

**🏁 캠페인 최종 결론**: **최종 스택 = vector + 관계라벨 graph + A-3 Critic + A-1 라우팅 구조주입**. 운영 벡터RAG 대비 judge +0.048·recall +0.176(N=3). 검색축(R-2/5/7/3/6) 무이득, 구조축(관계/커뮤니티 요약)+라우팅 보탬, 관계라벨 그래프가 결정타(특히 깨끗화 효과). 잔여 트레이드오프=fanout(sparse). 미래: fanout breadth 보강 + 실운영 코퍼스 검증(그래프 진짜 강세 측정처).
