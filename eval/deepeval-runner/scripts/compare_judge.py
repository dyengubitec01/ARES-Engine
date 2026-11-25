"""judge 엔드포인트 A/B 비교 스크립트.

현재 env에 설정된 judge(A)와 다른 엔드포인트(B)가 같은 판정을 하는지 확인한다.
judge를 갈아탈 때 점수 기준이 유지되는지 볼 때 쓴다.
Langfuse에는 읽기만 하므로(score 기록 없음) 운영 데이터에 영향이 없다.

세 단계로 확인한다.
  1. 신원 확인  : 모델 목록, 응답 model 필드, thinking 처리(<think> 누출 여부)
  2. 흔들림 측정: A judge를 2회 실행해 '정상 편차'가 얼마인지 먼저 잰다
  3. A/B 비교   : 같은 테스트케이스를 양쪽에 돌려 점수 차를 1의 편차와 견준다

로컬에는 deepeval이 없으므로(도커에서만 실행) 컨테이너 안에서 돌린다.
entrypoint가 evaluate.py로 고정돼 있어 python으로 덮어써야 한다.

  # 신원/thinking 처리만 빠르게 확인
  docker compose run --rm --entrypoint python deepeval-runner scripts/compare_judge.py \
      --probe-only --b-base-url http://localhost:8000/v1 \
      --b-api-key <key> --b-model gemma-4-31b

  # 점수 A/B 비교 (편차 기준선 포함)
  docker compose run --rm --entrypoint python deepeval-runner scripts/compare_judge.py \
      --self-check --b-base-url http://localhost:8000/v1 \
      --b-api-key <key> --b-model gemma-4-31b

  # 실제 trace로 비교 (읽기 전용)
  docker compose run --rm --entrypoint python deepeval-runner scripts/compare_judge.py \
      --trace-id <id> --b-base-url ... --b-api-key ... --b-model ...

B가 Qwen3 계열이면 `--b-disable-thinking` 을 함께 준다. thinking on/off는 같은 모델에서도
점수를 바꿀 수 있어, 비교하려는 조건과 일치시켜야 한다.
"""

import argparse
import os
import sys

from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase

# 프로덕션과 완전히 같은 judge 래퍼를 쓴다 (타임아웃·재시도·<think> 제거까지 동일).
from evaluate import LocalJudgeModel, extract_input_output, langfuse, JUDGE_CONFIG


# 점수가 높게/낮게 갈리도록 의도적으로 대비되는 케이스를 넣어야 judge 차이가 드러난다.
# (전부 만점 나오는 케이스만 쓰면 다른 모델이어도 똑같아 보인다.)
DEFAULT_CASES = [
    {
        "name": "정상답변",
        "input": "연차는 며칠까지 쓸 수 있어?",
        "actual_output": "입사 1년 미만은 1개월 개근 시 1일씩, 1년 이상은 연 15일이 부여됩니다.",
        "retrieval_context": [
            "근로기준법상 1년간 80퍼센트 이상 출근한 근로자에게 15일의 유급휴가를 준다.",
            "계속 근로기간이 1년 미만인 근로자에게는 1개월 개근 시 1일의 유급휴가를 준다.",
        ],
    },
    {
        "name": "환각답변",
        "input": "연차는 며칠까지 쓸 수 있어?",
        "actual_output": "연차는 무제한이며 쓰지 않으면 현금 300만원으로 자동 환급됩니다.",
        "retrieval_context": [
            "근로기준법상 1년간 80퍼센트 이상 출근한 근로자에게 15일의 유급휴가를 준다.",
        ],
    },
    {
        "name": "무관답변",
        "input": "연차 규정 알려줘",
        "actual_output": "오늘 서울 날씨는 맑고 기온은 24도입니다.",
        "retrieval_context": [
            "근로기준법상 연차 유급휴가는 15일이다.",
        ],
    },
]

METRICS = ("relevancy", "faithfulness")


def probe(label, judge):
    """LLM 판정 전에 '무엇에 붙었는지'를 먼저 찍는다."""
    thinking = "off" if judge.extra else "on"
    print(f"\n[{label}] base_url={judge.client.base_url}  요청 모델={judge.model_name}"
          f"  thinking={thinking}")

    try:
        ids = [m.id for m in judge.client.models.list().data]
        print(f"  서빙 모델 목록 : {ids}")
        if judge.model_name not in ids:
            print(f"  [경고] 요청 모델 '{judge.model_name}' 이 목록에 없음 → 404/400 위험")
    except Exception as e:
        print(f"  서빙 모델 목록 : 조회 실패(엔드포인트가 /v1/models 를 막아둘 수 있음) - {e}")

    try:
        # 프로덕션과 같은 요청 옵션(judge.extra = thinking off 스위치)으로 부른다.
        # 여기서 옵션을 빼면 운영과 다른 조건을 보고 판단하게 된다.
        raw = judge.client.chat.completions.create(
            model=judge.model_name,
            messages=[{"role": "user", "content": "1+1은? 숫자만 답해."}],
            temperature=0,
            **judge.extra,
        )
    except Exception as e:
        print(f"  [실패] chat/completions 호출 실패 - {e}")
        if judge.extra:
            print("         thinking off 옵션(enable_thinking)을 이 모델이 거부했을 수 있습니다. "
                  "Qwen3 계열이 아니면 스위치를 끄고 다시 시도하세요.")
        return False

    message = raw.choices[0].message
    text = message.content or ""
    print(f"  응답 model 필드: {raw.model}")
    print(f"  응답 본문(raw) : {text.strip()[:150]!r}")

    # thinking 모델(Qwen3 등)은 사내 LiteLLM 게이트웨이가 reasoning_content로 분리해
    # content를 깨끗하게 유지해 줬지만, vLLM 직결은 reasoning parser가 없으면 content에
    # <think>…</think>가 그대로 섞여 온다.
    # deepeval은 judge 응답을 JSON으로 파싱하므로 이 차이가 전건 실패로 이어진다.
    reasoning = getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None)
    tokens = raw.usage.completion_tokens if raw.usage else None
    print(f"  thinking 분리  : {'reasoning_content 로 분리됨' if reasoning else '분리 필드 없음'}"
          f" (completion 토큰 {tokens}개)")

    if "<think>" in text or "</think>" in text:
        stripped = LocalJudgeModel._strip_thinking(text)
        inner = text.split("<think>", 1)[-1].split("</think>", 1)[0].strip() if "<think>" in text else ""
        print(f"  → content 에 <think> 블록이 섞여 있음(thinking 본문 {len(inner)}자). "
              f"LocalJudgeModel 제거 후: {stripped[:80]!r}")
        if not stripped:
            print("  [치명] 제거 후 본문이 비었습니다(thinking만 오고 잘림). "
                  "max_tokens/reasoning parser 설정을 확인하세요.")
            return False
        if judge.extra and inner:
            # 태그는 남더라도 본문이 0자면 정상(빈 블록). 본문이 있으면 스위치가 안 먹은 것이다.
            print("  [주의] thinking off 를 걸었는데 thinking 본문이 생성됐습니다. "
                  "이 모델이 enable_thinking 을 무시합니다 — _strip_thinking 안전망으로만 버팁니다.")
    elif not reasoning and tokens and tokens > 50:
        print("  [주의] 분리 필드가 없는데 completion 토큰이 많습니다. "
              "긴 프롬프트에서 <think> 누출 가능성 있음")
    return True


def score_case(judge, case):
    """evaluate.py와 동일한 메트릭/임계값으로 한 케이스를 채점한다."""
    test_case = LLMTestCase(
        input=case["input"],
        actual_output=case["actual_output"],
        retrieval_context=case.get("retrieval_context") or None,
    )
    out = {m: None for m in METRICS}
    out["reasons"] = {}

    metric = AnswerRelevancyMetric(model=judge, threshold=0.7)
    try:
        metric.measure(test_case)
        out["relevancy"] = metric.score
        out["reasons"]["relevancy"] = metric.reason or ""
    except Exception as e:
        out["reasons"]["relevancy"] = f"ERROR: {e}"

    if case.get("retrieval_context"):
        metric = FaithfulnessMetric(model=judge, threshold=0.7)
        try:
            metric.measure(test_case)
            out["faithfulness"] = metric.score
            out["reasons"]["faithfulness"] = metric.reason or ""
        except Exception as e:
            out["reasons"]["faithfulness"] = f"ERROR: {e}"

    return out


def run(label, judge, cases):
    print(f"\n===== [{label}] 채점 시작 ({judge.model_name}) =====")
    results = []
    for case in cases:
        res = score_case(judge, case)
        print(f"  {case['name']:<10} relevancy={res['relevancy']}  faithfulness={res['faithfulness']}")
        for metric, reason in res["reasons"].items():
            if reason.startswith("ERROR:"):
                print(f"    └ {metric}: {reason}")
        results.append(res)
    return results


def fmt(value):
    return "실패" if value is None else f"{value:.3f}"


def gap(a, b):
    return None if (a is None or b is None) else abs(a - b)


def report(cases, a_res, b_res, a2_res, label_a, label_b):
    print("\n" + "=" * 82)
    print("judge 비교 결과")
    print("=" * 82)

    # 같은 judge를 두 번 돌린 편차 = temperature=0에서도 남는 '정상 흔들림'.
    # A/B 차이를 이 값과 견줘야 '다른 모델'인지 '그냥 흔들림'인지 구분된다.
    jitter = 0.0
    if a2_res:
        for r1, r2 in zip(a_res, a2_res):
            for metric in METRICS:
                d = gap(r1[metric], r2[metric])
                if d is not None:
                    jitter = max(jitter, d)
        print(f"\n[기준선] {label_a} judge 2회 실행 최대 편차 = {jitter:.3f}")
    else:
        print("\n[기준선] --self-check 미사용 → 편차 미측정 (판정은 0.05 고정 기준)")

    threshold = max(jitter, 0.05)

    print(f"\n{'케이스':<12}{'메트릭':<15}{label_a:>10}{label_b:>10}{'차이':>9}")
    print("-" * 82)
    max_delta = 0.0
    verdict_ok = True
    for case, ra, rb in zip(cases, a_res, b_res):
        for metric in METRICS:
            if ra[metric] is None and rb[metric] is None:
                continue
            d = gap(ra[metric], rb[metric])
            mark = ""
            if d is None:
                mark, verdict_ok = "  <- 한쪽 실패", False
            else:
                max_delta = max(max_delta, d)
                if d > threshold:
                    mark, verdict_ok = "  <- 차이 큼", False
            print(f"{case['name']:<12}{metric:<15}{fmt(ra[metric]):>10}{fmt(rb[metric]):>10}"
                  f"{('-' if d is None else f'{d:.3f}'):>9}{mark}")

    print("-" * 82)
    print(f"판정 기준: 차이 <= {threshold:.3f} 이면 동일 판정으로 본다")
    if verdict_ok:
        print(f"[결과] 두 judge 판정이 일치합니다 (최대 차이 {max_delta:.3f}). 교체해도 무방합니다.")
    else:
        print(f"[결과] 판정이 갈립니다 (최대 차이 {max_delta:.3f}). 같은 judge로 보기 어렵습니다.")
        print("       모델 가중치/양자화, 채팅 템플릿, thinking 처리, 샘플링 기본값 중")
        print("       하나가 다를 가능성이 큽니다. 위 [신원 확인] 출력을 함께 보세요.")
    print("=" * 82)


def main():
    parser = argparse.ArgumentParser(
        description="judge 엔드포인트 A/B 비교 (A = 현재 env의 judge, B = 인자로 지정)")
    parser.add_argument("--b-base-url", required=True, help="비교할 엔드포인트 (…/v1)")
    parser.add_argument("--b-api-key", default=os.getenv("JUDGE_B_API_KEY", "EMPTY"),
                        help="비교 대상 API key (미지정 시 JUDGE_B_API_KEY 환경변수)")
    parser.add_argument("--b-model", required=True, help="비교 대상 모델명")
    parser.add_argument("--b-disable-thinking", action="store_true",
                        help="비교 대상이 Qwen3 계열이면 thinking 생성을 끈다 "
                             "(A쪽은 JUDGE_DISABLE_THINKING 을 따른다)")
    parser.add_argument("--trace-id", help="실제 Langfuse trace로 비교 (읽기만, score 기록 안 함)")
    parser.add_argument("--self-check", action="store_true",
                        help="A judge를 2회 실행해 '정상 흔들림' 폭을 먼저 측정")
    parser.add_argument("--probe-only", action="store_true", help="신원 확인만 하고 종료")
    args = parser.parse_args()

    judge_a = LocalJudgeModel(JUDGE_CONFIG["model"], JUDGE_CONFIG["base_url"],
                              JUDGE_CONFIG["api_key"], JUDGE_CONFIG["disable_thinking"])
    judge_b = LocalJudgeModel(args.b_model, args.b_base_url, args.b_api_key,
                              args.b_disable_thinking)
    label_a, label_b = "현재(env)", "비교대상"

    print("[신원 확인]")
    ok_a = probe(label_a, judge_a)
    ok_b = probe(label_b, judge_b)
    if not (ok_a and ok_b):
        print("\n[FATAL] 한쪽 엔드포인트가 정상 응답하지 않습니다. 위 오류를 먼저 해결하세요.")
        sys.exit(1)
    if args.probe_only:
        print("\n신원 확인 통과. 점수 비교는 --self-check 로 실행하세요.")
        return

    cases = DEFAULT_CASES
    if args.trace_id:
        if not os.getenv("LANGFUSE_HOST"):
            print("[FATAL] --trace-id 를 쓰려면 LANGFUSE_* 환경변수가 필요합니다.")
            sys.exit(1)
        trace = langfuse.api.trace.get(args.trace_id)
        query, answer, contexts = extract_input_output(trace)
        if not query or not answer:
            print(f"[FATAL] trace {args.trace_id} 에서 query/answer 추출 실패")
            sys.exit(1)
        cases = [{
            "name": "실trace",
            "input": query,
            "actual_output": answer,
            "retrieval_context": contexts,
        }]
        print(f"\n실제 trace {args.trace_id} 로 비교합니다 (context {len(contexts)}건)")

    a_res = run(label_a, judge_a, cases)
    a2_res = run(f"{label_a} 재실행", judge_a, cases) if args.self_check else None
    b_res = run(label_b, judge_b, cases)

    report(cases, a_res, b_res, a2_res, label_a, label_b)


if __name__ == "__main__":
    main()
