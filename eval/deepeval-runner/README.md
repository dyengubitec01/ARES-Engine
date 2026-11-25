# deepeval-runner

Langfuse에 쌓인 LLM trace(질문·답변)를 **DeepEval** 메트릭으로 평가하고, 그 점수를 다시 **Langfuse score**로 기록하는 배치 평가 도구입니다.
빌드·실행은 **Jenkins 파이프라인**이 Docker로 수행합니다.

---

## 전체 흐름

```
Jenkins (Jenkinsfile)
   │  [수동] 파라미터 입력 (ENV / MODE / 날짜·trace-id·tag / FORCE)
   │  [자동] 매일 새벽 1시 cron → dev / 전날 하루치
   ▼
[1] Checkout      → 트리거(수동/cron) 판별 후 ENV·credential 결정
[2] Docker Build  → registry.example.com/ares/deepeval-runner
[3] Docker Push   → 레지스트리 업로드
[4] Run Evaluation→ docker run --env-file <비밀 env> ... <args>
   │
   ▼
scripts/evaluate.py  (컨테이너 ENTRYPOINT)
   │
   ├─ Langfuse에서 trace 조회 (trace-id / date-range / tag)
   ├─ trace에서 query · answer · context 추출
   ├─ DeepEval 평가
   │     • AnswerRelevancy  (항상)
   │     • Faithfulness     (retrieval context 있을 때만)
   └─ 점수를 Langfuse score로 push
         (deepeval/relevancy, deepeval/faithfulness)
```

---

## 구성 파일

| 파일 | 역할 |
|------|------|
| `Jenkinsfile` | CI/CD 파이프라인. 수동 파라미터 실행 + 새벽 cron 자동 실행 |
| `scripts/evaluate.py` | 실제 평가 로직 (trace 조회 → 추출 → 평가 → score 기록) |
| `Dockerfile` | `python:3.11-slim` 기반, `evaluate.py`를 ENTRYPOINT로 |
| `docker-compose.yml` | Jenkins 없이 로컬에서 돌릴 때 사용 (Langfuse 네트워크에 연결) |
| `requirements.txt` | `deepeval`, `langfuse`, `litellm` |
| `.env.example` | 필요한 환경변수 템플릿 |

---

## 환경변수

| 변수 | 설명 |
|------|------|
| `LANGFUSE_HOST` | Langfuse 서버 주소 |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `JUDGE_BASE_URL` | judge 엔드포인트 (`…/v1` 까지) — **필수** |
| `JUDGE_API_KEY` | judge bearer 토큰 (`Bearer ` 접두사 없이 값만) |
| `JUDGE_MODEL` | judge 모델명 — **필수** (기본값 없음) |
| `JUDGE_DISABLE_THINKING` | `true` 면 thinking 생성을 끔 (선택, 기본 꺼지지 않음). **Qwen3 계열 전용** |

> Jenkins에서는 dev/prod 값을 credential(`env-deepeval-dev` / `env-deepeval-prod`)로 주입합니다.
> `docker run --env-file` 로 통째로 넘기므로, credential 파일 내용만 고치면 자동 반영됩니다.

---

## Judge 엔드포인트

judge는 **클라우드 vLLM 직결**입니다. (예전에는 사내 LiteLLM 게이트웨이를 경유했습니다.)

```
JUDGE_BASE_URL=http://localhost:8000/v1
JUDGE_API_KEY=<bearer-token>
JUDGE_MODEL=qwen3-14b
JUDGE_DISABLE_THINKING=true
```

**엔드포인트 하나가 모델 하나만 서빙합니다.** 그래서 주소와 모델명은 항상 한 쌍으로 함께
바꿔야 합니다 — 주소만 바꾸거나 모델명만 바꾸면 404입니다. (`/v1/models` 로 그 주소가 무엇을
서빙하는지 확인할 수 있습니다.)

LiteLLM 시절과 달라진 점:

| | LiteLLM 경유 (구) | vLLM 직결 (현) |
|---|---|---|
| 모델 | 게이트웨이 별칭 `judge-qwen3-14b` | 실제 모델명 `qwen3-14b` |
| thinking | 게이트웨이가 `reasoning_content` 로 분리해 줌 | 분리 필드 없음 → `content` 에 `<think>` 가 섞임. 요청 옵션으로 아예 끔 |
| 네트워크 | 사내망 | 외부 HTTPS (아웃바운드 443 필요) |

`JUDGE_MODEL` 은 **기본값을 두지 않고 필수**로 만들었습니다(기본값을 두면 모델 교체 시 코드
안의 옛 이름이 남아 같은 사고가 반복됩니다). 구 변수명(`LITELLM_*`)이 남은 채 새 변수가
비어 있으면, 조용히 옛 엔드포인트로 평가하지 않고 시작 시점에 `[FATAL]` 로 중단합니다.

어느 judge로 채점했는지는 콘솔 첫 줄 `[JUDGE] model=… base_url=… thinking=off` 와 결과 JSON의
`judge` 필드에 남습니다(과거 아티팩트와 점수를 비교할 때 기준 판별용, API key는 제외).

> **judge 응답 형식**: judge는 JSON을 ` ```json ` 코드펜스로 감싸 반환하지만, deepeval의
> `trimAndLoadJson` 이 첫 `{` ~ 마지막 `}` 만 잘라내므로 파싱에 문제가 없습니다.
> (`deepeval/metrics/utils.py`, 호출 경로: `generate_with_schema` → `LocalJudgeModel.generate`
> → `trimAndLoadJson`)

### thinking 처리

Qwen3는 thinking 모델이고, LiteLLM 게이트웨이 없이 vLLM에 직결하면 `reasoning_content` 분리
필드가 없어 **`content` 에 `<think>…</think>` 가 그대로 섞여 옵니다.** deepeval은 judge 응답을
JSON으로 파싱하므로 이걸 방치하면 전 메트릭이 실패합니다.

thinking을 끄는 방법을 실측 비교했습니다 (동일 프롬프트, `temperature=0`):

| 요청 | completion 토큰 | `<think>` 태그 | thinking 본문 |
|---|---|---|---|
| 아무 것도 안 함 | 392 | 있음 | 1427자 |
| 프롬프트에 `/nothink` | 67 | 있음 (빈 블록) | 0자 |
| 프롬프트에 `/no_think` | 67 | 있음 (빈 블록) | 0자 |
| `chat_template_kwargs.enable_thinking=false` | **48** | **없음** | — |

**`JUDGE_DISABLE_THINKING=true` → 요청 옵션 `enable_thinking=false`** 를 씁니다. `<think>` 태그
자체가 나오지 않아 가장 깔끔하고, 프롬프트에 모델 전용 문자열을 심지 않아도 됩니다.
Qwen3 계열 chat template 전용 인자라, 다른 모델로 갈아탈 때는 이 변수를 비우면 아무 것도
보내지 않습니다(모르는 인자를 항상 보내면 vLLM이 거부할 수 있습니다).

thinking을 끄는 이유는 두 가지입니다.

- **속도/비용**: 같은 프롬프트에 대해 생성 토큰이 **약 6배**(320 → 49) 차이납니다. 체감 지연은
  엔드포인트 부하에 따라 흔들리지만 반복 측정에서 **3~6배**(3.5초 → 1.1초, 2.9초 → 0.5초)였습니다.
  deepeval은 trace 1건당 메트릭별로 judge를 여러 번 호출하므로 배치 전체 시간에 그대로 곱해집니다.
- **잘림 위험**: thinking이 길어져 응답이 잘리면 본문이 비어 메트릭이 통째로 실패할 수 있습니다.

> `/nothink` 도 실제로 동작합니다(위 표 — thinking 본문 0자). 과거 LiteLLM 시절 코드가
> 프롬프트 끝에 `/nothink` 를 붙이고 있었으므로, **당시 `judge-qwen3-14b` 점수 baseline도
> thinking이 꺼진 상태에서 나온 것**입니다. 지금 방식은 같은 효과를 프롬프트 오염 없이 얻는
> 것이라 채점 조건이 그대로 유지됩니다.

`LocalJudgeModel._strip_thinking` 은 **2차 안전망**으로 남겨둡니다. 스위치가 꺼져 있거나 새
모델이 `enable_thinking` 을 무시할 때 `content` 에 섞인 `<think>…</think>` 를 제거해 JSON
파싱을 지킵니다(태그가 없으면 무동작).

### 컨텍스트 창 한계 (알려진 제약)

`qwen3-14b` 의 `max_model_len` 은 **32,768** 입니다. Faithfulness는 retrieval context 전체를
프롬프트에 싣기 때문에, context가 긴 trace에서는 이 한도를 넘겨 400으로 실패합니다.

```
[ERROR] trace … - faithfulness 평가 실패: Error code: 400 -
  This model's maximum context length is 32768 tokens. However, you requested 0 output
  tokens and your prompt contains at least 32769 input tokens …
```

실측 임계선은 **context 약 50,000자**입니다(한국어 기준 대략 1.6자/토큰). 최근 trace 25건 중
context가 있는 16건을 재보면:

| context 문자수 | 건수 | 결과 |
|---|---|---|
| 13,000 ~ 40,000자 | 8건 | 두 메트릭 모두 산출 |
| 51,900 ~ 71,900자 | 8건 | **faithfulness 실패**, relevancy만 기록 |

즉 **context가 있는 trace의 약 절반은 `deepeval/relevancy` 만 남습니다.** Langfuse에서
faithfulness가 비어 있는 trace가 많이 보이는 건 이 때문이며, 버그가 아닙니다.

- 한 메트릭이 실패해도 다른 메트릭 결과는 보존되고 평가는 계속됩니다(빌드도 실패하지 않습니다).
- 다만 이런 trace는 **반쪽 평가** 상태라, 다음 실행에서 `[REEVAL]` 로 매번 재평가를 시도하고
  또 실패합니다(스킵되지 않습니다). 콘솔에 `[REEVAL]` 이 반복돼도 정상 동작입니다.
- `gemma-4-31b`(`max_model_len` 65,536)에서는 같은 trace가 전건 통과합니다. 같은 trace를
  양쪽에 돌린 비교에서 **relevancy는 1.000으로 동일**, faithfulness만 qwen3에서 실패했습니다.

해소하려면 (1) faithfulness에 넘기는 context를 잘라 넣거나, (2) 메트릭별로 judge를 나누거나,
(3) vLLM 운영 쪽에 `qwen3-14b` 의 `max_model_len` 상향을 요청해야 합니다. 현재는 조치 없이
**긴 context의 faithfulness를 포기하는 쪽**으로 두고 있습니다.

### 기존 judge와 판정이 같은지 확인

현재 env의 judge(A)와 임의의 다른 엔드포인트(B)를 비교합니다. 로컬에는 deepeval이 없으므로
(도커에서만 실행) 컨테이너 안에서 돌립니다. entrypoint가 `evaluate.py` 로 고정돼 있어
`--entrypoint python` 으로 덮어씁니다.

```bash
# 신원·thinking 처리 방식만 빠르게 확인
docker compose run --rm --entrypoint python deepeval-runner scripts/compare_judge.py \
    --probe-only --b-base-url http://localhost:8000/v1 \
    --b-api-key <key> --b-model gemma-4-31b

# 점수 A/B 비교 (편차 기준선 포함)
docker compose run --rm --entrypoint python deepeval-runner scripts/compare_judge.py \
    --self-check --b-base-url http://localhost:8000/v1 \
    --b-api-key <key> --b-model gemma-4-31b

# 실제 trace로 비교
docker compose run --rm --entrypoint python deepeval-runner scripts/compare_judge.py \
    --trace-id <id> --b-base-url ... --b-api-key ... --b-model ...
```

`--self-check` 는 A judge를 2회 돌려 **정상 흔들림 폭**을 먼저 재고 A/B 차이를 그 폭과
견줍니다. `temperature=0` 이라도 deepeval은 메트릭당 여러 번 호출해 점수가 흔들리므로,
이 기준선 없이는 "다른 모델"과 "그냥 흔들림"을 구분할 수 없습니다.
Langfuse에는 읽기만 하므로(score 기록 없음) 운영 데이터에 영향이 없습니다.

> B가 Qwen3 계열이면 `--b-disable-thinking` 을 함께 줍니다. thinking on/off는 같은 모델에서도
> 점수를 바꿀 수 있어, 비교하려는 조건을 양쪽에서 일치시켜야 합니다. A쪽은
> `JUDGE_DISABLE_THINKING` 을 그대로 따르고, 각 judge의 적용 상태는 신원 확인 줄의
> `thinking=on/off` 로 표시됩니다.

---

## 평가 메트릭

평가에 쓰는 LLM(judge)은 OpenAI 같은 상용 API가 아닌 **자체 운영 `qwen3-14b`** 입니다
(`scripts/evaluate.py` 의 `LocalJudgeModel`, 접속 정보는 [Judge 엔드포인트](#judge-엔드포인트) 참고).

| 메트릭 | 실행 조건 | Langfuse score 이름 |
|--------|-----------|---------------------|
| **AnswerRelevancy** | 항상 | `deepeval/relevancy` |
| **Faithfulness** | retrieval context가 있을 때만 | `deepeval/faithfulness` |

임계값(threshold)은 두 메트릭 모두 `0.7`.

### trace 구조 가정

`scripts/evaluate.py`는 trace를 다음 구조로 가정하고 값을 추출합니다.

- **질문(input)**: `trace.input.query` 또는 `trace.input.input`, 없으면 `trace.input` 전체
- **답변(output)**: `synthesizer` observation의 `output.response`(또는 `content`), 없으면 `trace.output`
- **context**: `retriever` observation의 `output.context`

list 조회로 가져온 trace는 observation이 불완전할 수 있어 **`trace.id`로 상세 재조회**한 뒤 평가합니다.

---

## 실행 방법

### 1) Jenkins — 수동 실행

빌드 시작 시 파라미터를 선택합니다.

| 파라미터 | 설명 |
|----------|------|
| `ENV` | `dev` / `prod` — 사용할 credential 결정 |
| `MODE` | `trace-id` / `date-range` / `tag` — 평가 대상 지정 방식 |
| `TRACE_ID` | 개별 trace ID (`trace-id` 모드, 기존 점수 덮어씀) |
| `FROM_DATE` / `TO_DATE` | 기간 (`date-range` 모드, 예: `2026-04-27T00:00:00`) |
| `TAG` | 태그 필터 (`tag` 모드) |
| `FORCE` | 이미 평가된 trace도 재평가 |

### 2) Jenkins — 새벽 자동 평가 (별도 잡, `Jenkinsfile.nightly`)

수동/개별 평가(1번)와 **분리된 전용 잡**입니다. 스케줄이 UI가 아니라 코드(`Jenkinsfile.nightly`)에 박혀 있어 버전관리/리뷰됩니다.

**동작:**
- 트리거: `triggers { cron('TZ=Asia/Seoul\n0 1 * * *') }` — **매일 한국시간 새벽 1시 정각** 자동 실행
- 대상: **전날 하루치** (`어제 00:00:00 ~ 23:59:59`, 실행 시점 기준 `date -d 'yesterday'`로 자동 계산)
- 환경: **dev → prod 순차** 평가 (각자 credential `env-deepeval-dev`/`env-deepeval-prod`). 한쪽이 실패해도 다른 쪽은 계속 진행하고, 마지막에 실패 여부를 종합
- 결과: `results/dev/**`, `results/prod/**`로 분리해 아티팩트 보관
- 레지스트리 push 없이 로컬 빌드만 (평가 전용)

**수동 재실행용 파라미터** (기본값 = cron 자동 동작과 동일 → cron은 영향 없음):

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `TARGET_DATE` | (빈값) | 비우면 전날 자동. `YYYY-MM-DD` 넣으면 그 날짜 평가 (놓친 날 재실행용) |
| `TARGETS` | `dev+prod` | `dev`/`prod`만 따로 돌릴 수도 있음 |
| `FORCE` | false | 이미 평가된 trace도 재평가 |

**Jenkins 설정:**
1. 새 **Pipeline 잡**을 만든다 (예: `deepeval-runner-nightly`).
2. Pipeline → "Pipeline script from SCM" → 이 저장소 지정 → **Script Path = `Jenkinsfile.nightly`**.
3. **한 번 수동 빌드**해 cron 트리거를 Jenkins에 등록한다. 그 뒤부터 매일 새벽 자동 실행.
   - 수동 빌드는 즉시 "어제치"를 돌리므로 **테스트 용도로도** 그대로 쓸 수 있다.

**시각 조정:** 현재 `0 1 * * *`(정확히 1:00). 부하 분산이 필요하면 `H 1 * * *`(1시대 임의 분)으로 바꿀 수 있습니다.

> cron 식을 바꿔도 **빌드가 한 번 더 실행되어 Jenkinsfile을 다시 읽어야** 새 시각이 등록됩니다. (push만으로는 기존 등록 트리거가 안 바뀜)

### 3) 로컬 실행 (docker-compose)

```bash
cp .env.example .env   # 값 채우기
docker compose build

# 개별 trace
docker compose run --rm deepeval-runner --trace-id <TRACE_ID>

# 기간
docker compose run --rm deepeval-runner \
  --from-date 2026-04-27T00:00:00 --to-date 2026-04-28T23:59:59

# 태그
docker compose run --rm deepeval-runner --tag <TAG>
```

### CLI 인자

`scripts/evaluate.py`에 전달되는 인자입니다.

| 인자 | 설명 |
|------|------|
| `--trace-id` | 개별 trace 평가 (기존 score 덮어쓰기) |
| `--from-date` | 시작일 (ISO 8601) |
| `--to-date` | 종료일 (ISO 8601) |
| `--tag` | 태그 필터 |
| `--force` | 이미 평가된 trace도 재평가 |

---

## 재실행과 덮어쓰기 규칙

같은 구간을 다시 돌렸을 때 Langfuse score가 어떻게 되는지:

| 상황 | 동작 |
|------|------|
| `relevancy` + `faithfulness` 가 모두 기록된 trace | **스킵** (재평가 안 함) |
| 반쪽만 기록된 trace (예: faithfulness 누락) | 기존 `deepeval/*` score 삭제 후 재평가 (`[REEVAL]`) |
| `--force` | 기존 `deepeval/*` score 삭제 후 전부 재평가 |
| `--trace-id` (개별 모드) | 항상 기존 score 삭제 후 재평가 |

> **judge를 바꿨을 때 주의**: 스킵 판정은 "이미 채점됨"만 보고 **어느 judge로 채점했는지는
> 보지 않습니다.** judge 교체 후 같은 기간을 그냥 다시 돌리면 과거 trace는 스킵되어 **옛
> judge 점수가 그대로 남습니다.** 새 judge 기준으로 통일하려면 `--force`(Jenkins `FORCE`)로
> 돌려야 합니다. 결과 JSON의 `judge` 필드로 어느 기준이었는지 구분할 수 있습니다.

### judge 엔드포인트 이전 절차

1. Jenkins credential 파일 2개(`env-deepeval-dev` / `env-deepeval-prod`) 내용 갱신
   — `JUDGE_BASE_URL` + `JUDGE_MODEL` 은 **항상 같이** 바꿉니다(엔드포인트당 모델 1개).
   **옛 값은 지우지 말고 `#` 으로 주석 처리해 남겨둡니다.** 되돌릴 때 그대로 쓸 수 있습니다.
2. 코드 커밋/푸시
3. `--force`로 과거 구간 재채점 (위 주의 참고 — 안 하면 옛 judge 점수가 남습니다)

> **주석 처리 시 주의**: `docker run --env-file` 은 `#` 으로 시작하는 줄을 무시하므로
> 되돌리기용 값을 같은 파일에 남겨둬도 안전합니다(검증 완료). 다만 **`#` 은 줄 맨 앞에**
> 있어야 하고, 주석을 푸는 순간 같은 키가 두 번 나오면 **뒤에 있는 값이 이깁니다.**
> 되돌릴 때는 새 값을 주석 처리하고 옛 값을 살리는 식으로, 활성 상태의 키가 한 번만
> 나오도록 맞추세요.

> **1번을 빼먹으면 빌드는 실패하지 않고 조용히 옛 judge로 계속 채점합니다.** `JUDGE_*` 가
> 이미 채워져 있으면 시작 시점 `[FATAL]` 검사가 걸리지 않기 때문입니다(그 검사는 변수가
> *비어 있을* 때만 동작합니다). 콘솔 첫 줄 `[JUDGE] model=…` 로 실제 채점에 쓰인 judge를
> 반드시 확인하세요.

**기존 cron 잡을 멈출 필요가 없고, 서버에 접속할 일도 없습니다.** 이유:

- cron은 서버 crontab이 아니라 `Jenkinsfile.nightly` 의 `triggers { cron(...) }` 입니다.
  (`Jenkinsfile` 의 `DEPLOY_SERVER` / `SSH_CREDENTIALS` 는 선언만 있고 쓰이지 않습니다 —
  SSH 배포 스테이지가 없습니다.)
- 매 실행이 `checkout scm` → `docker build` 이므로 다음 실행이 새 코드를 자동으로 씁니다.
  이미지는 `post { always }` 에서 `docker rmi` 로 지워져 캐시가 남지 않습니다.
- 평가 컨테이너는 실행 후 `docker rm -f` 로 정리됩니다. 상주 컨테이너가 없습니다.

**정말 멈춰야 할 때** (실행 중인 빌드를 중단):

- Jenkins UI에서 해당 빌드의 중단(X) 버튼. 별도 중단 스크립트는 없습니다.
- 중단 시 컨테이너가 남으면: `docker rm -f deepeval-nightly-<빌드번호>-dev` (수동 잡은
  `deepeval-<빌드번호>`)
- 중단해도 그 시점까지의 score는 Langfuse에 남고 요약 JSON도 저장됩니다
  (`evaluate()` 가 `try/finally` 로 요약을 보장). 반쪽 평가된 trace는 다음 실행에서
  `[REEVAL]` 로 자동 복구됩니다.

> **동시 실행**: `disableConcurrentBuilds()` 는 **같은 잡** 안에서만 적용됩니다. nightly와
> 수동 잡은 별개 잡이라 서로를 막지 않습니다. 컨테이너 이름은 겹치지 않지만
> (`deepeval-nightly-N-dev` vs `deepeval-N`) 같은 trace에 동시에 score를 쓰면 중복될 수
> 있으니, 겹치는 구간을 동시에 돌리지 않는 편이 좋습니다.

---

## 결과 확인

평가 결과는 **세 곳**에 남습니다.

1. **Langfuse score** — 각 trace에 `deepeval/relevancy`, `deepeval/faithfulness`가 점수+사유(comment)와 함께 기록됨 (영구 보관, 가장 정확한 기록).
2. **Jenkins 콘솔 로그** — 실행 중 per-trace 점수와 마지막의 **요약 블록**(평가/스킵 개수, 평균 점수, trace별 점수)이 그대로 출력됨.
3. **Jenkins 빌드 아티팩트** — 요약 JSON이 빌드 페이지에 첨부됨. `results/eval_summary_<타임스탬프>.json` 과 `results/eval_summary_latest.json`.

요약 JSON 예시:

```json
{
  "generated_at": "2026-06-26T01:02:03",
  "evaluated": 12,
  "skipped": 3,
  "avg_relevancy": 0.83,
  "avg_faithfulness": 0.79,
  "results": [
    { "trace_id": "abc...", "relevancy": 0.9, "faithfulness": 0.8, "has_context": true }
  ]
}
```

> 저장 위치는 `RESULT_DIR` 환경변수로 바꿀 수 있습니다(기본 `results`). Jenkins는 컨테이너의 `/app/results`를 `docker cp`로 워크스페이스에 복사해 아티팩트로 보관합니다. (Jenkins가 컨테이너로 동작해 `-v` 바인드 마운트로는 워크스페이스와 파일이 공유되지 않기 때문)

## 안정성 (judge 첫 호출 대비)

judge가 준비되지 않은 상태에서 평가 첫 호출이 타임아웃/실패하는 것을 막기 위해:

- 평가 루프 전에 **워밍업 호출**(`warmup_judge`)을 한 번 보냅니다. 실패해도 무시하고 평가를 계속합니다.
- judge용 OpenAI 클라이언트에 **타임아웃 300초 + 재시도 3회**를 설정했습니다.

> 원래는 ollama 콜드 스타트(모델 로딩 수십 초) 대비였습니다. 현재 judge는 상시 서빙되는
> vLLM 엔드포인트라 로딩 지연은 없지만, 외부 HTTPS 경유이므로 타임아웃·재시도 설정은
> 그대로 유지합니다.
