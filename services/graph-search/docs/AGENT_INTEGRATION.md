# rag-graph-search — Agent 연동 가이드

Agent 서버가 그래프 축(rag-graph-search)을 호출·병합하기 위한 계약입니다.
그래프 서버는 **벡터 축과 병렬 호출**되어 청크 후보를 반환하고, union·리랭킹·LLM 답변은 **agent가** 처리합니다.

---

## 1. 엔드포인트

| 환경 | URL |
|---|---|
| dev  | `http://localhost:8508/v1/graph-search` |
| prod | `http://localhost:8008/v1/graph-search` |

- Method: `POST`
- Health: `GET /health` → `{"status":"ok"}`

---

## 2. 요청

```
POST /v1/graph-search
Content-Type: application/json
X-LF-Trace-ID: <optional>     # agent가 시작한 trace 승계
X-LF-Parent-Id: <optional>
```

```json
{
  "query": "증평군 스마트도시 사업",
  "excluded_docs": [],          // optional, 제외할 doc_id 목록
  "chunk_limit": 20             // optional, 기본 설정값(20)
}
```

---

## 3. 응답

### 성공 (RAG100000)

```json
{
  "code": "RAG100000",
  "msg": "그래프 검색 성공",
  "data": {
    "query": "증평군 스마트도시 사업",
    "trace_id": "abc123...",
    "results": [
      {
        "rank": 1,
        "chunk_id": "chunk-uuid",
        "content": "본문 텍스트",
        "metadata": {
          "doc_id": "doc-content-uuid",
          "original_filename": "example.pdf",
          "_source": "graph"
        },
        "score": 15.0,
        "hits": 3
      }
    ]
  }
}
```

### 결과 없음 (RAG100001)

```json
{ "code": "RAG100001", "msg": "검색 결과 없음" }
```

### 실패 (RAG100060, fail-open이라 거의 발생 안 함)

```json
{ "code": "RAG100060", "msg": "그래프 저장소 연동 실패" }
```

> **Fail-open 원칙:** 그래프 서버 내부 예외는 모두 흡수되어 빈 결과/에러 코드로 반환됩니다. 5xx는 없습니다. Agent는 그래프 축이 비어도 **벡터 축만으로 계속 진행**하면 됩니다.

---

## 4. Agent가 지켜야 할 연동 계약

1. **병렬 호출** — 벡터 검색과 그래프 검색을 동시에 호출
2. **chunk_id 기준 union·dedup** — 두 축 결과를 `chunk_id`로 합치고 중복 제거. 겹치면 `_source: "both"` 표기
3. **합쳐진 풀을 리랭커에 태움** — (원장 결론: union 풀 리랭킹이 유의미)
4. **그래프 후보를 벡터 점수로 rerank 금지** — 상보성이 깨져 오히려 악화 (원장 실측)
5. **Fail-open 존중** — 그래프가 빈 배열/에러여도 벡터 축만으로 진행
6. **Trace 승계** — `X-LF-Trace-ID`, `X-LF-Parent-Id` 헤더 전달

---

## 5. 복붙용 호출 예시 (Python / httpx)

```python
import asyncio
import httpx

GRAPH_URL = "http://localhost:8508/v1/graph-search"  # prod: :8008


async def call_graph_search(query: str, trace_id: str | None = None) -> list[dict]:
    """그래프 축 호출. 실패/빈 결과는 [] 로 흡수 (fail-open)."""
    headers = {"Content-Type": "application/json"}
    if trace_id:
        headers["X-LF-Trace-ID"] = trace_id
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(GRAPH_URL, json={"query": query}, headers=headers)
            body = resp.json()
        if body.get("code") != "RAG100000":
            return []                         # 결과없음/에러 → 빈 리스트
        return body["data"]["results"]
    except Exception:
        return []                             # 네트워크 등 실패도 흡수


def union_by_chunk_id(vec: list[dict], graph: list[dict]) -> list[dict]:
    """chunk_id 기준 union + dedup. 겹치면 _source='both'."""
    pool: dict[str, dict] = {}
    for r in vec:
        pool[r["chunk_id"]] = {**r, "metadata": {**r.get("metadata", {}), "_source": "vector"}}
    for r in graph:
        cid = r["chunk_id"]
        if cid in pool:
            pool[cid]["metadata"]["_source"] = "both"
        else:
            pool[cid] = r
    return list(pool.values())


async def hybrid_search(query: str, trace_id: str | None = None):
    # 1) 병렬 호출
    vec_res, graph_res = await asyncio.gather(
        call_rag_search(query),               # 기존 벡터 축
        call_graph_search(query, trace_id),   # 그래프 축
    )
    # 2) union·dedup
    merged = union_by_chunk_id(vec_res, graph_res)
    # 3) 합친 풀을 리랭커에 태움 (그래프를 벡터점수로 rerank 금지)
    reranked = await call_reranker(query, merged)
    # 4) LLM 답변 생성
    return await call_llm(query, reranked)
```

---

## 6. 참고 — 현재 상태

- **prod는 그래프 축이 기본 OFF** (`GRAPH_ENABLED=false`, 라벨 커버리지 80% 완주 전까지). 즉 prod 연동해도 당분간 그래프 결과는 항상 빈 배열 → fail-open으로 무해. 완주 신호 시 flag만 켜면 됨.
- **dev는 ON.** 다만 cosine 폴백은 인덱싱팀이 active build 엔티티 벡터를 적재한 뒤 완전해짐(정확 매칭은 지금도 동작).
- 연동 코드는 위 계약대로 **지금 붙여둬도 안전** (fail-open이라 그래프가 비어도 벡터 축 정상).
