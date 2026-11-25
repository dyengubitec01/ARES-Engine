# rag-graph-search

Graph-RAG 검색 서버 — 사용자 쿼리를 엔티티 그래프 기반 3-Step 파이프라인으로 청크 회수하여 JSON으로 응답한다.
벡터 검색·리랭킹·LLM 답변 생성은 이 서버의 역할이 **아니다** (agent 서버가 담당).

- **엔드포인트:** `POST /v1/graph-search`
- **포트:** 컨테이너 내부 8007 / 호스트 8008(prod)·8508(dev compose)
- **원칙:** Fail-open — 내부 예외는 흡수하고 빈 결과 반환
- **플래그:** `GRAPH_ENABLED` (dev `true` / prod `false`)

## 문서

- 전체 구축 스펙(원본 인수인계): [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md)
- 에픽/스토리 백로그: `../_bmad-output/planning-artifacts/epics.md`

## 개발

```bash
pip install -e ".[dev]"
cp .env.example .env.dev   # 실제 시크릿 채우기 (커밋 금지)
uvicorn app.main:app --host 0.0.0.0 --port 8007
pytest
```

## 상태

BMAD 백로그 기반 순차 구현 중. 현재 Story 1.1 (레포 골격 + 패키징) 완료.
나머지 레이어(config, 어댑터, 서비스, API, 테스트, Docker/CI)는 후속 스토리에서 채운다.
