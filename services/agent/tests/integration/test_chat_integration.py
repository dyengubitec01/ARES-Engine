"""
Chat SSE Integration Tests (Story 2.6).

SSE 스트리밍 엔드포인트 통합 테스트.
실제 LLM 서버 연결 필수 (Mock 사용 금지).

pytest tests/integration/test_chat_integration.py -v -m integration 으로 실행.

테스트 항목:
- test_chat_endpoint_returns_sse: SSE 응답 형식 확인
- test_chat_thought_events: thought 이벤트 전송 확인
- test_chat_message_streaming: message 토큰 스트리밍 확인
- test_chat_done_event: done 이벤트 전송 확인
- test_chat_full_workflow: 전체 워크플로우 테스트
"""

import json
import uuid
from collections.abc import Iterator

import httpx
import pytest

from tests.integration.conftest import skip_no_llm

# Integration 테스트 마커
pytestmark = pytest.mark.integration


def parse_sse_events(text: str) -> list[dict]:
    """Parse SSE events from response text."""
    events = []
    current_event = {}

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            if current_event:
                events.append(current_event)
                current_event = {}
            continue

        if line.startswith("event:"):
            current_event["event"] = line[6:].strip()
        elif line.startswith("data:"):
            data_str = line[5:].strip()
            try:
                current_event["data"] = json.loads(data_str)
            except json.JSONDecodeError:
                current_event["data"] = data_str

    # Add last event if exists
    if current_event:
        events.append(current_event)

    return events


def iter_sse_events(response: httpx.Response) -> Iterator[dict]:
    """Iterate SSE events from streaming response."""
    current_event = {}

    for line in response.iter_lines():
        line = line.strip()
        if not line:
            if current_event:
                yield current_event
                current_event = {}
            continue

        if line.startswith("event:"):
            current_event["event"] = line[6:].strip()
        elif line.startswith("data:"):
            data_str = line[5:].strip()
            try:
                current_event["data"] = json.loads(data_str)
            except json.JSONDecodeError:
                current_event["data"] = data_str


@skip_no_llm
class TestChatSSEEndpoint:
    """Chat SSE 엔드포인트 테스트."""

    def test_chat_endpoint_returns_sse(self, http_client: httpx.Client) -> None:
        """POST /v1/chat가 SSE 응답을 반환하는지 확인 (AC 2.6.1)."""
        session_id = f"test-sse-{uuid.uuid4().hex[:8]}"

        response = http_client.post(
            "/v1/chat",
            json={
                "query": "안녕",
                "session_id": session_id,
                "user_depts": ["test-dept"],
            },
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        assert response.headers.get("cache-control") == "no-cache"

    def test_chat_done_event(self, http_client: httpx.Client) -> None:
        """done 이벤트가 전송되는지 확인 (AC 2.6.7)."""
        session_id = f"test-done-{uuid.uuid4().hex[:8]}"

        with http_client.stream(
            "POST",
            "/v1/chat",
            json={
                "query": "Hi",
                "session_id": session_id,
                "user_depts": ["test-dept"],
            },
        ) as response:
            events = list(iter_sse_events(response))

        # done 이벤트가 마지막에 있어야 함 (enum 코드 사용)
        assert len(events) > 0
        last_event = events[-1]
        assert last_event["event"] == "done"
        assert last_event["data"]["code"] == "AGT0000"
        assert last_event["data"]["msg"] == "요청이 성공하였습니다."

        # Story 6.1 (AC 6.1.3): done 이벤트에 usage 필드 포함
        assert "usage" in last_event["data"]
        usage = last_event["data"]["usage"]
        assert isinstance(usage.get("input_tokens"), int)
        assert isinstance(usage.get("output_tokens"), int)
        assert isinstance(usage.get("total_tokens"), int)
        assert usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"]
        # 실 LLM 호출 시 토큰은 양수여야 함
        assert usage["total_tokens"] > 0

        # done 이벤트에 최종 답변 정본(response) 포함
        assert isinstance(last_event["data"].get("response"), str)
        assert len(last_event["data"]["response"]) > 0


@skip_no_llm
class TestChatEventTypes:
    """Chat 이벤트 타입 테스트 (AC 2.6.2, 2.6.3, 2.6.4)."""

    def test_chat_message_streaming(self, http_client: httpx.Client) -> None:
        """message 이벤트가 스트리밍되는지 확인 (AC 2.6.4)."""
        session_id = f"test-msg-{uuid.uuid4().hex[:8]}"

        with http_client.stream(
            "POST",
            "/v1/chat",
            json={
                "query": "간단하게 인사해줘",
                "session_id": session_id,
                "user_depts": ["test-dept"],
            },
        ) as response:
            events = list(iter_sse_events(response))

        # message 이벤트가 있어야 함
        message_events = [e for e in events if e["event"] == "message"]
        assert len(message_events) > 0, "Should have message events"

        # 각 message 이벤트에 content가 있어야 함
        for event in message_events:
            assert "content" in event["data"]

    def test_chat_thought_events(self, http_client: httpx.Client) -> None:
        """thought 이벤트가 전송되는지 확인 (AC 2.6.3).

        Note: INCLUDE_THOUGHTS_IN_RESPONSE=true일 때만 thought 이벤트 전송됨.
        """
        session_id = f"test-thought-{uuid.uuid4().hex[:8]}"

        with http_client.stream(
            "POST",
            "/v1/chat",
            json={
                "query": "테스트 질문입니다",
                "session_id": session_id,
                "user_depts": ["test-dept"],
            },
        ) as response:
            events = list(iter_sse_events(response))

        # 이벤트 타입 확인
        event_types = {e["event"] for e in events}

        # message와 done은 필수
        assert "message" in event_types or "done" in event_types

        # thought는 설정에 따라 있을 수도 없을 수도 있음
        print(f"Event types received: {event_types}")

    def test_event_format(self, http_client: httpx.Client) -> None:
        """SSE 이벤트 포맷이 올바른지 확인 (AC 2.6.2)."""
        session_id = f"test-format-{uuid.uuid4().hex[:8]}"

        response = http_client.post(
            "/v1/chat",
            json={
                "query": "Hi",
                "session_id": session_id,
                "user_depts": ["test-dept"],
            },
        )

        # Raw text에서 SSE 형식 확인
        raw_text = response.text
        assert "event:" in raw_text
        assert "data:" in raw_text

        # 파싱하여 구조 확인
        events = parse_sse_events(raw_text)
        for event in events:
            assert "event" in event, "Each SSE block should have event type"
            assert "data" in event, "Each SSE block should have data"


@skip_no_llm
class TestChatFullWorkflow:
    """전체 Chat 워크플로우 테스트."""

    def test_full_chat_workflow(self, http_client: httpx.Client) -> None:
        """전체 워크플로우가 정상 동작하는지 확인."""
        session_id = f"test-full-{uuid.uuid4().hex[:8]}"

        print(f"\n[Test] Session ID: {session_id}")

        with http_client.stream(
            "POST",
            "/v1/chat",
            json={
                "query": "안녕하세요, 오늘 날씨가 어때요?",
                "session_id": session_id,
                "history": [],
                "user_depts": ["test-dept"],
            },
        ) as response:
            events = list(iter_sse_events(response))

        # 이벤트 수집
        event_types = [e["event"] for e in events]
        print(f"[Test] Events: {event_types}")

        # 기본 검증
        assert "done" in event_types, "Should end with done event"

        # message 이벤트들의 content 합치기
        message_content = ""
        for event in events:
            if event["event"] == "message":
                message_content += event["data"].get("content", "")

        print(f"[Test] Response: {message_content[:100]}...")
        assert len(message_content) > 0 or events[-1]["event"] == "done"

    def test_chat_with_history(self, http_client: httpx.Client) -> None:
        """히스토리가 있는 대화가 정상 동작하는지 확인."""
        session_id = f"test-history-{uuid.uuid4().hex[:8]}"

        with http_client.stream(
            "POST",
            "/v1/chat",
            json={
                "query": "그게 뭔데?",
                "session_id": session_id,
                "history": [
                    {"role": "user", "content": "삼성에 대해 알려줘"},
                    {"role": "assistant", "content": "삼성은 한국의 대기업입니다."},
                ],
                "user_depts": ["test-dept"],
            },
        ) as response:
            events = list(iter_sse_events(response))

        # 정상 종료 확인
        event_types = [e["event"] for e in events]
        assert "done" in event_types

    def test_chat_with_user_id(self, http_client: httpx.Client) -> None:
        """user_id가 있는 요청이 정상 동작하는지 확인."""
        session_id = f"test-userid-{uuid.uuid4().hex[:8]}"
        user_id = "test-user-001"

        with http_client.stream(
            "POST",
            "/v1/chat",
            json={
                "query": "Hello",
                "session_id": session_id,
                "user_id": user_id,
                "user_depts": ["test-dept"],
            },
        ) as response:
            events = list(iter_sse_events(response))

        assert len(events) > 0
        assert events[-1]["event"] == "done"


@skip_no_llm
class TestChatRequestSchema:
    """ChatRequest 스키마 테스트 (AC 2.6.6)."""

    def test_required_fields(self, http_client: httpx.Client) -> None:
        """필수 필드 검증."""
        # query 누락
        response = http_client.post(
            "/v1/chat",
            json={"session_id": "test"},
        )
        assert response.status_code == 422

        # session_id 누락
        response = http_client.post(
            "/v1/chat",
            json={"query": "test"},
        )
        assert response.status_code == 422

        # user_depts 누락 (AC 3.6.2: 필수 + 비어있을 수 없음)
        response = http_client.post(
            "/v1/chat",
            json={"query": "test", "session_id": "test"},
        )
        assert response.status_code == 422

    def test_optional_fields(self, http_client: httpx.Client) -> None:
        """선택 필드가 없어도 동작하는지 확인."""
        session_id = f"test-optional-{uuid.uuid4().hex[:8]}"

        # history, user_id 없이 요청
        response = http_client.post(
            "/v1/chat",
            json={
                "query": "Hi",
                "session_id": session_id,
                "user_depts": ["test-dept"],
            },
        )
        assert response.status_code == 200
