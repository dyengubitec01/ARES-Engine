import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional
from langfuse import Langfuse
from langfuse.api.resources.score.types.create_score_request import CreateScoreRequest
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase
from deepeval.models import DeepEvalBaseLLM
from openai import OpenAI, AsyncOpenAI


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


class LocalJudgeModel(DeepEvalBaseLLM):
    def __init__(self, model_name: str, base_url: str, api_key: str,
                 disable_thinking: bool = False):
        self.model_name = model_name
        # 외부 HTTPS 경유 judge라 지연/일시 오류에 대비해 넉넉한 타임아웃 + 재시도
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=300.0, max_retries=3)
        self.async_client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=300.0, max_retries=3)

        # thinking을 끄는 요청 옵션. Qwen3 계열 chat template 전용 인자라 기본은 끄지 않고,
        # env 스위치가 켜졌을 때만 실어 보낸다. (모르는 인자를 항상 보내면 다른 모델로
        # 갈아탈 때 vLLM이 거부할 수 있다.) 비교 스크립트가 같은 조건으로 프로브할 수
        # 있도록 속성으로 노출한다.
        self.extra = ({"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
                      if disable_thinking else {})

    def load_model(self):
        return self.model_name

    @staticmethod
    def _strip_thinking(content: Optional[str]) -> str:
        """judge 응답에서 thinking 블록을 제거한다.

        thinking 대응의 **2차 안전망**이다. 1차는 요청 단계에서 아예 생성을 끄는
        `JUDGE_DISABLE_THINKING`(→ `self.extra`)이고, 이 함수는 그 스위치가 꺼져 있거나
        새 모델이 스위치를 무시할 때를 받아낸다.

        지우지 않으면 안 되는 이유: 사내 LiteLLM 게이트웨이는 thinking을 `reasoning_content`
        필드로 분리해 `content`를 깨끗하게 유지해 줬지만, vLLM에 직접 붙으면(reasoning parser
        미설정) `content`에 `<think>…</think>`가 그대로 섞여 온다. deepeval은 judge 응답을
        JSON으로 파싱하므로 그대로 두면 전 메트릭이 실패한다. 태그가 없으면 무동작이다.
        """
        text = content or ""
        text = _THINK_BLOCK.sub("", text)
        # 여는 태그가 유실된 채 닫는 태그만 오는 구현도 있어 뒤쪽 본문만 취한다.
        if "</think>" in text:
            text = text.rsplit("</think>", 1)[1]
        return text.strip()

    # 프롬프트 끝에 붙이던 Qwen3 전용 `/nothink` 지시어는 쓰지 않는다. 이 지시어 자체는
    # 실제로 동작하지만(빈 `<think></think>` 블록만 남고 thinking 본문은 생성되지 않는다),
    # 모든 프롬프트에 모델 전용 문자열을 심어야 하고 다른 모델에는 잡음으로 남는다.
    # 같은 효과를 요청 옵션 `enable_thinking=false`(→ self.extra)로 얻으므로 그쪽을 쓴다.
    # 그러면 `<think>` 태그 자체가 나오지 않아 응답이 더 깔끔하다.
    def generate(self, prompt: str, schema: Optional[object] = None) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            **self.extra,
        )
        return self._strip_thinking(response.choices[0].message.content)

    async def a_generate(self, prompt: str, schema: Optional[object] = None) -> str:
        response = await self.async_client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            **self.extra,
        )
        return self._strip_thinking(response.choices[0].message.content)

    def get_model_name(self) -> str:
        return self.model_name


langfuse = Langfuse(
    host=os.getenv("LANGFUSE_HOST"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
)


def resolve_judge_config() -> dict:
    """judge 접속 정보를 환경변수에서 읽는다.

    judge는 클라우드 vLLM 직결이다. 예전 사내 LiteLLM 게이트웨이(`LITELLM_*`) 시절과 달리
    모델명이 게이트웨이 별칭(`judge-qwen3-14b`)이 아니라 vLLM이 서빙하는 실제 모델명
    (`qwen3-14b`)이다. 게다가 엔드포인트 하나가 모델 하나만 서빙해서 주소와 모델명이 한 쌍으로
    묶여 움직인다(주소만 바꾸면 404). 그래서 모델명에 기본값을 두지 않고 주소와 함께 명시하도록
    강제한다. (기본값을 두면 모델이 교체될 때 코드 안의 옛 이름이 그대로 남아 다시 404가 난다.)
    설정 누락은 평가 도중이 아니라 시작 직후에 드러나야 하므로 여기서 즉시 중단한다.

    `JUDGE_DISABLE_THINKING`만 예외로 필수가 아니다(기본 꺼짐). Qwen3 계열 전용 옵션이라,
    다른 모델로 갈아탈 때 변수를 비우면 아무 것도 보내지 않게 하려는 의도다.
    """
    # 구 변수명만 남아 있으면 credential 파일을 아직 갱신하지 않은 것이다. 조용히 옛
    # 엔드포인트로 평가해 버리면 점수 기준이 섞이므로, 힌트를 붙여 명시적으로 세운다.
    legacy_hint = (" (LITELLM_* 가 남아 있습니다. JUDGE_BASE_URL / JUDGE_API_KEY /"
                   " JUDGE_MODEL 로 교체하세요.)"
                   if os.getenv("LITELLM_BASE_URL", "").strip() else "")

    missing = [name for name in ("JUDGE_BASE_URL", "JUDGE_MODEL")
               if not os.getenv(name, "").strip()]
    if missing:
        raise SystemExit(f"[FATAL] {' / '.join(missing)} 가 비어 있습니다. "
                         f"env 파일을 확인하세요.{legacy_hint}")

    return {
        "base_url": os.getenv("JUDGE_BASE_URL", "").strip(),
        "api_key": os.getenv("JUDGE_API_KEY", "").strip() or "EMPTY",
        "model": os.getenv("JUDGE_MODEL", "").strip(),
        "disable_thinking": (os.getenv("JUDGE_DISABLE_THINKING", "").strip().lower()
                             in ("1", "true", "yes")),
    }


JUDGE_CONFIG = resolve_judge_config()
judge_model = LocalJudgeModel(
    model_name=JUDGE_CONFIG["model"],
    base_url=JUDGE_CONFIG["base_url"],
    api_key=JUDGE_CONFIG["api_key"],
    disable_thinking=JUDGE_CONFIG["disable_thinking"],
)

# 평가 결과 요약 파일을 저장할 디렉터리 (Jenkins에서는 /app/results를 마운트해 아티팩트로 보관)
RESULT_DIR = os.getenv("RESULT_DIR", "results")

# 컨테이너 기본 타임존이 UTC라, 결과 시각은 한국시간으로 기록 (고정 +9, DST 없음)
KST = timezone(timedelta(hours=9))


def warmup_judge():
    """평가 시작 전 judge를 한 번 호출해 접속을 확인한다.

    원래는 ollama 콜드 스타트(모델 로딩 수십 초~) 대비였다. 현재 judge는 상시 서빙되는
    vLLM 엔드포인트라 로딩 지연은 없지만, 인증 실패나 모델명 오타 같은 설정 문제를 배치
    첫 trace가 아니라 여기서 먼저 드러내 준다. 실패해도 평가는 계속 진행한다.
    """
    print("[WARMUP] judge 모델 로드 중...")
    try:
        judge_model.generate("ping")
        print("[WARMUP] judge 모델 로드 완료")
    except Exception as e:
        print(f"[WARMUP] 워밍업 실패(무시하고 평가 진행): {e}")


def extract_input_output(trace):
    """trace에서 실제 질문과 최종 답변을 추출"""
    # input에서 query 추출
    query = None
    if isinstance(trace.input, dict):
        query = trace.input.get("query") or trace.input.get("input")
    if not query:
        query = str(trace.input) if trace.input else None

    # synthesizer observation에서 최종 답변 추출
    answer = None
    if hasattr(trace, 'observations') and trace.observations:
        for obs in trace.observations:
            if obs.name == "synthesizer":
                if isinstance(obs.output, dict):
                    answer = obs.output.get("response") or obs.output.get("content")
                elif isinstance(obs.output, str):
                    answer = obs.output
                break

    # synthesizer 못 찾으면 trace output에서 시도
    if not answer:
        if isinstance(trace.output, dict):
            answer = trace.output.get("response") or trace.output.get("content")
        elif isinstance(trace.output, str):
            answer = trace.output

    # retriever에서 context 추출
    contexts = []
    if hasattr(trace, 'observations') and trace.observations:
        for obs in trace.observations:
            if obs.name == "retriever":
                if isinstance(obs.output, dict) and "context" in obs.output:
                    contexts = obs.output["context"]
                break

    return query, answer, contexts


def get_traces(args):
    if args.trace_id:
        trace = langfuse.api.trace.get(args.trace_id)
        return [trace]

    params = {}
    if args.from_date:
        params["from_timestamp"] = datetime.fromisoformat(args.from_date)
    if args.to_date:
        params["to_timestamp"] = datetime.fromisoformat(args.to_date)
    if args.tag:
        params["tags"] = [args.tag]

    # Langfuse list API는 한 페이지(기본 ~50개)만 반환하므로 전체 페이지를 순회한다.
    # (prod처럼 하루 trace가 많을 때 뒤쪽이 누락되지 않도록)
    traces = []
    page = 1
    limit = 100
    while True:
        result = langfuse.api.trace.list(page=page, limit=limit, **params)
        batch = result.data
        traces.extend(batch)
        if len(batch) < limit:
            break
        page += 1
    return traces


def existing_deepeval_metrics(trace):
    """trace에 이미 기록된 deepeval score의 메트릭 이름 집합을 반환한다.

    예: deepeval/relevancy, deepeval/faithfulness 가 있으면
    {"relevancy", "faithfulness"} 를 반환.
    """
    metrics = set()
    if hasattr(trace, 'scores') and trace.scores:
        for score in trace.scores:
            if score.name.startswith("deepeval/"):
                metrics.add(score.name.split("/", 1)[1])
    return metrics


def delete_existing_scores(trace):
    if hasattr(trace, 'scores') and trace.scores:
        for score in trace.scores:
            if score.name.startswith("deepeval/"):
                langfuse.api.score.delete(score.id)


def push_score(trace_id, name, value, comment):
    langfuse.api.score.create(
        request=CreateScoreRequest(
            trace_id=trace_id,
            name=name,
            value=value,
            comment=comment,
        )
    )


def write_summary(results, evaluated, skipped, failed=0):
    """평가 결과 요약을 콘솔에 출력(Jenkins 콘솔 로그)하고 JSON 파일로 저장한다."""
    rel_scores = [r["relevancy"] for r in results if r["relevancy"] is not None]
    faith_scores = [r["faithfulness"] for r in results if r["faithfulness"] is not None]
    avg_rel = round(sum(rel_scores) / len(rel_scores), 4) if rel_scores else None
    avg_faith = round(sum(faith_scores) / len(faith_scores), 4) if faith_scores else None

    # 콘솔 요약 (Jenkins 콘솔 로그에 그대로 남음)
    print("\n" + "=" * 60)
    print("평가 결과 요약")
    print("=" * 60)
    print(f"  평가 완료 : {evaluated}개")
    print(f"  스킵      : {skipped}개")
    print(f"  실패      : {failed}개")
    print(f"  평균 relevancy    : {avg_rel}")
    print(f"  평균 faithfulness : {avg_faith}")
    print("-" * 60)
    for r in results:
        if r.get("error"):
            print(f"  {r['trace_id']}  [실패] {r['error']}")
            continue
        faith = r["faithfulness"] if r["faithfulness"] is not None else "-"
        print(f"  {r['trace_id']}  relevancy={r['relevancy']}  faithfulness={faith}")
    print("=" * 60)

    # JSON 파일로 저장 (Jenkins 아티팩트로 보관 → 빌드 페이지에서 다운로드 가능)
    summary = {
        "generated_at": datetime.now(KST).isoformat(),
        # judge가 바뀌면 점수 수준 자체가 달라질 수 있어, 결과와 judge를 같이 남긴다.
        # (과거 아티팩트와 비교할 때 어느 judge 기준인지 판별용. api key는 남기지 않는다.)
        # thinking 여부도 채점 조건이라 같이 남긴다 — 같은 모델도 thinking on/off로 점수가
        # 달라질 수 있다.
        "judge": {
            "model": JUDGE_CONFIG["model"],
            "base_url": JUDGE_CONFIG["base_url"],
            "disable_thinking": JUDGE_CONFIG["disable_thinking"],
        },
        "evaluated": evaluated,
        "skipped": skipped,
        "failed": failed,
        "avg_relevancy": avg_rel,
        "avg_faithfulness": avg_faith,
        "results": results,
    }
    try:
        os.makedirs(RESULT_DIR, exist_ok=True)
        ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
        path = os.path.join(RESULT_DIR, f"eval_summary_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        # 최신본도 고정 이름으로 한 부 더
        with open(os.path.join(RESULT_DIR, "eval_summary_latest.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"결과 저장: {path}")
    except Exception as e:
        print(f"[WARN] 결과 파일 저장 실패: {e}")


def evaluate(traces, force=False, single=False):
    relevancy = AnswerRelevancyMetric(model=judge_model, threshold=0.7)
    faithfulness = FaithfulnessMetric(model=judge_model, threshold=0.7)

    evaluated = 0
    skipped = 0
    failed = 0
    results = []

    # 평가 도중 무엇이 끊겨도(빌드 타임아웃에 의한 중단, flush 실패 등) 결과 요약과
    # JSON 아티팩트는 반드시 남기기 위해 본 루프를 try/finally로 감싼다.
    # (요약 파일이 없으면 Jenkins의 docker cp 단계까지 실패한다.)
    try:
        for trace in traces:
            trace_id = trace.id
            try:
                # list로 가져온 trace는 observations가 불완전할 수 있으므로 상세 조회
                trace = langfuse.api.trace.get(trace_id)

                query, answer, contexts = extract_input_output(trace)

                if not query or not answer:
                    print(f"[SKIP] trace {trace_id} - query 또는 answer 추출 실패")
                    print(f"  query: {repr(query)[:100]}")
                    print(f"  answer: {repr(answer)[:100]}")
                    skipped += 1
                    continue

                # 이 trace에서 기대되는 메트릭. context가 없으면 relevancy만 평가 대상.
                expected = {"relevancy"}
                if contexts:
                    expected.add("faithfulness")
                existing = existing_deepeval_metrics(trace)

                if single:
                    delete_existing_scores(trace)
                elif not force and expected.issubset(existing):
                    # 기대 메트릭이 모두 기록돼 있을 때만 '이미 평가됨'으로 보고 스킵
                    print(f"[SKIP] trace {trace_id} - 이미 평가됨 ({', '.join(sorted(existing))})")
                    skipped += 1
                    continue
                elif existing:
                    # 반쪽 평가(예: relevancy만 있고 faithfulness 누락)이거나 force 재평가.
                    # 중복 score가 쌓이지 않도록 기존 deepeval score를 먼저 지우고 다시 평가한다.
                    print(f"[REEVAL] trace {trace_id} - 기존 score 삭제 후 재평가 "
                          f"(기존: {', '.join(sorted(existing))} / 기대: {', '.join(sorted(expected))})")
                    delete_existing_scores(trace)

                print(f"[EVAL] trace {trace_id}")
                print(f"  query: {query[:80]}...")
                print(f"  answer: {answer[:80]}...")

                test_case = LLMTestCase(
                    input=query,
                    actual_output=answer,
                    retrieval_context=contexts if contexts else None,
                )

                # 메트릭은 각각 독립적으로 평가한다. 한쪽(특히 무거운 Faithfulness)이
                # judge 타임아웃 등으로 실패해도 다른 쪽 결과는 보존하고 평가를 계속한다.
                relevancy_score = None
                try:
                    relevancy.measure(test_case)
                    relevancy_score = relevancy.score
                    push_score(trace_id, "deepeval/relevancy", relevancy.score, relevancy.reason)
                except Exception as e:
                    print(f"[ERROR] trace {trace_id} - relevancy 평가 실패: {e}")

                faithfulness_score = None
                # Faithfulness — context 있을 때만 실행
                if contexts:
                    try:
                        faithfulness.measure(test_case)
                        faithfulness_score = faithfulness.score
                        push_score(trace_id, "deepeval/faithfulness", faithfulness.score, faithfulness.reason)
                    except Exception as e:
                        print(f"[ERROR] trace {trace_id} - faithfulness 평가 실패: {e}")

                # 두 메트릭 모두 실패한 trace는 실패로 집계 (score가 하나도 안 남음)
                if relevancy_score is None and faithfulness_score is None:
                    print(f"[FAIL] trace {trace_id} - 모든 메트릭 평가 실패")
                    failed += 1
                    results.append({
                        "trace_id": trace_id,
                        "relevancy": None,
                        "faithfulness": None,
                        "has_context": bool(contexts),
                        "error": "all metrics failed",
                    })
                    continue

                print(f"[DONE] trace {trace_id} - relevancy: {relevancy_score}, faithfulness: {faithfulness_score}")
                results.append({
                    "trace_id": trace_id,
                    "relevancy": relevancy_score,
                    "faithfulness": faithfulness_score,
                    "has_context": bool(contexts),
                })
                evaluated += 1

            except Exception as e:
                # trace 단위 안전망: 한 trace의 예기치 못한 오류(상세 조회 실패 등)가
                # 배치 전체를 죽이지 않도록 기록 후 다음 trace로 넘어간다.
                print(f"[ERROR] trace {trace_id} - 평가 중 예외, 건너뜀: {e}")
                failed += 1
                results.append({
                    "trace_id": trace_id,
                    "relevancy": None,
                    "faithfulness": None,
                    "has_context": False,
                    "error": str(e),
                })
                continue
    finally:
        # 요약/아티팩트를 먼저 보장하고, flush 실패는 평가 결과 보존에 영향 주지 않도록 격리한다.
        write_summary(results, evaluated, skipped, failed)
        try:
            langfuse.flush()
        except Exception as e:
            print(f"[WARN] langfuse flush 실패: {e}")

    return evaluated, skipped, failed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DeepEval Runner")
    parser.add_argument("--trace-id", help="개별 trace ID (기존 score 덮어쓰기)")
    parser.add_argument("--from-date", help="시작일 (ISO format)")
    parser.add_argument("--to-date", help="종료일 (ISO format)")
    parser.add_argument("--tag", help="태그 필터")
    parser.add_argument("--force", action="store_true", help="이미 평가된 trace도 재평가")
    args = parser.parse_args()

    # 어느 judge로 채점했는지가 점수 해석에 직결되므로 로그 맨 앞에 남긴다. (api key는 제외)
    print(f"[JUDGE] model={JUDGE_CONFIG['model']} base_url={JUDGE_CONFIG['base_url']} "
          f"thinking={'off' if JUDGE_CONFIG['disable_thinking'] else 'on'}")

    single = args.trace_id is not None
    traces = get_traces(args)
    print(f"평가 대상: {len(traces)}개 trace")
    if traces:
        warmup_judge()
    evaluated, skipped, failed = evaluate(traces, force=args.force, single=single)

    # 종료 코드 정책: 1건이라도 평가에 성공했으면 빌드는 성공으로 둔다.
    # (야간 배치가 단일 judge 타임아웃 같은 부분 실패로 통째로 FAILURE 되지 않도록)
    # 평가 성공이 0건이면서 실패가 발생한 경우에만 비정상 종료한다.
    if evaluated == 0 and failed > 0:
        print(f"[FATAL] 평가 성공 0건, 실패 {failed}건 → 비정상 종료(exit 1)")
        sys.exit(1)