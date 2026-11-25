"""
Chat SSE Unit Tests (Story 2.6).

SSE 이벤트 포맷, ChatRequest 스키마, 에러 처리 단위 테스트.
pytest tests/test_chat.py -v 으로 실행.

테스트 항목:
- test_format_sse_*: SSE 이벤트 포맷 검증
- test_chat_request_*: ChatRequest 스키마 검증
- test_error_event_*: 에러 이벤트 생성 검증
"""

import json
from typing import Any

import pytest
from pydantic import ValidationError


class TestFormatSSE:
    """SSE 이벤트 포맷 테스트."""

    def test_format_sse_thought(self) -> None:
        """thought 이벤트 포맷 확인."""
        from app.api.v1.chat import format_sse

        result = format_sse("thought", {"content": "질문을 재구성하고 있습니다..."})

        assert result.startswith("event: thought\n")
        assert "data: " in result
        assert result.endswith("\n\n")

        # JSON 파싱 확인
        data_line = result.split("\n")[1]
        data_json = data_line.replace("data: ", "")
        parsed = json.loads(data_json)
        assert parsed["content"] == "질문을 재구성하고 있습니다..."

    def test_format_sse_message(self) -> None:
        """message 이벤트 포맷 확인."""
        from app.api.v1.chat import format_sse

        result = format_sse("message", {"content": "갤럭시"})

        assert result.startswith("event: message\n")
        data_line = result.split("\n")[1]
        data_json = data_line.replace("data: ", "")
        parsed = json.loads(data_json)
        assert parsed["content"] == "갤럭시"

    def test_format_sse_error(self) -> None:
        """error 이벤트 포맷 확인."""
        from app.api.v1.chat import format_sse

        result = format_sse("error", {"code": "AGT5001", "msg": "LLM 연결 실패"})

        assert result.startswith("event: error\n")
        data_line = result.split("\n")[1]
        data_json = data_line.replace("data: ", "")
        parsed = json.loads(data_json)
        assert parsed["code"] == "AGT5001"
        assert parsed["msg"] == "LLM 연결 실패"

    def test_format_sse_done(self) -> None:
        """done 이벤트 포맷 확인 (enum 코드 사용)."""
        from app.api.v1.chat import format_sse
        from app.core.enums import ErrorCode

        result = format_sse("done", {"code": ErrorCode.SUCCESS.code, "msg": ErrorCode.SUCCESS.msg})

        assert result.startswith("event: done\n")
        data_line = result.split("\n")[1]
        data_json = data_line.replace("data: ", "")
        parsed = json.loads(data_json)
        assert parsed["code"] == "AGT0000"
        assert parsed["msg"] == "요청이 성공하였습니다."

    def test_format_sse_done_with_sources(self) -> None:
        """done 이벤트에 sources 포함 확인 (AC 2.7.6)."""
        from app.api.v1.chat import format_sse
        from app.core.enums import ErrorCode

        sources = [{"doc_id": "doc-001", "doc_title": "테스트 문서", "doc_content": "내용..."}]
        result = format_sse(
            "done",
            {
                "code": ErrorCode.SUCCESS.code,
                "msg": ErrorCode.SUCCESS.msg,
                "sources": sources,
            },
        )

        data_line = result.split("\n")[1]
        data_json = data_line.replace("data: ", "")
        parsed = json.loads(data_json)
        assert parsed["code"] == "AGT0000"
        assert parsed["sources"] == sources

    def test_format_sse_done_error_with_empty_sources(self) -> None:
        """에러 시 done 이벤트에 빈 sources 배열 확인 (AC 2.7.8)."""
        from app.api.v1.chat import format_sse
        from app.core.enums import ErrorCode

        result = format_sse(
            "done",
            {
                "code": ErrorCode.INTERNAL_ERROR.code,
                "msg": ErrorCode.INTERNAL_ERROR.msg,
                "sources": [],
            },
        )

        data_line = result.split("\n")[1]
        data_json = data_line.replace("data: ", "")
        parsed = json.loads(data_json)
        assert parsed["code"] == "AGT5000"
        assert parsed["sources"] == []

    def test_format_sse_korean(self) -> None:
        """한글 데이터 처리 확인."""
        from app.api.v1.chat import format_sse

        result = format_sse("message", {"content": "안녕하세요"})

        # ensure_ascii=False로 한글 그대로 출력
        assert "안녕하세요" in result

    def test_format_sse_done_with_usage(self) -> None:
        """done 이벤트에 usage 포함 확인 (AC 6.1.3)."""
        from app.api.v1.chat import format_sse
        from app.core.enums import ErrorCode

        usage = {"input_tokens": 1200, "output_tokens": 300, "total_tokens": 1500}
        result = format_sse(
            "done",
            {
                "code": ErrorCode.SUCCESS.code,
                "msg": ErrorCode.SUCCESS.msg,
                "sources": [],
                "usage": usage,
            },
        )

        data_line = result.split("\n")[1]
        data_json = data_line.replace("data: ", "")
        parsed = json.loads(data_json)
        assert parsed["usage"] == usage
        assert parsed["usage"]["input_tokens"] == 1200
        assert parsed["usage"]["output_tokens"] == 300
        assert parsed["usage"]["total_tokens"] == 1500


class TestChatRequestSchema:
    """ChatRequest 스키마 테스트."""

    def test_valid_request_minimal(self) -> None:
        """최소 필수 필드로 생성."""
        from app.api.v1.chat import ChatRequest

        request = ChatRequest(query="테스트", session_id="sess-001", user_depts=["D001"])

        assert request.query == "테스트"
        assert request.session_id == "sess-001"
        assert request.summary is None  # Story 2.7
        assert request.history == []
        assert request.user_id is None
        assert request.user_position is None  # Story 2.7
        assert request.user_depts == ["D001"]

    def test_valid_request_full(self) -> None:
        """모든 필드로 생성."""
        from app.api.v1.chat import ChatRequest

        request = ChatRequest(
            query="테스트 질문",
            session_id="sess-002",
            summary="테스트 요약",  # Story 2.7
            history=[
                {"role": "user", "content": "이전 질문"},
                {"role": "assistant", "content": "이전 답변"},
            ],
            user_id="user-001",
            user_position="대리",  # Story 2.7
            user_depts=["D002"],
        )

        assert request.query == "테스트 질문"
        assert request.session_id == "sess-002"
        assert request.summary == "테스트 요약"  # Story 2.7
        assert len(request.history) == 2
        assert request.user_id == "user-001"
        assert request.user_position == "대리"  # Story 2.7
        assert request.user_depts == ["D002"]

    def test_missing_query(self) -> None:
        """query 누락 시 ValidationError."""
        from app.api.v1.chat import ChatRequest

        with pytest.raises(ValidationError):
            ChatRequest(session_id="sess-001", user_depts=["D001"])

    def test_missing_session_id(self) -> None:
        """session_id 누락 시 ValidationError."""
        from app.api.v1.chat import ChatRequest

        with pytest.raises(ValidationError):
            ChatRequest(query="테스트", user_depts=["D001"])

    def test_empty_history(self) -> None:
        """빈 history 허용."""
        from app.api.v1.chat import ChatRequest

        request = ChatRequest(
            query="테스트", session_id="sess-001", user_depts=["D001"], history=[]
        )

        assert request.history == []

    def test_blank_query_rejected(self) -> None:
        """공백 query 거부 (AC 2.7.2)."""
        from app.api.v1.chat import ChatRequest

        with pytest.raises(ValidationError):
            ChatRequest(query="", session_id="sess-001", user_depts=["D001"])

        with pytest.raises(ValidationError):
            ChatRequest(query="   ", session_id="sess-001", user_depts=["D001"])

    def test_blank_session_id_rejected(self) -> None:
        """공백 session_id 거부 (AC 2.7.2)."""
        from app.api.v1.chat import ChatRequest

        with pytest.raises(ValidationError):
            ChatRequest(query="테스트", session_id="", user_depts=["D001"])

        with pytest.raises(ValidationError):
            ChatRequest(query="테스트", session_id="   ", user_depts=["D001"])


class TestChatRequestUserDeptArray:
    """user_depts 배열 검증 테스트 (AC 3.6.1, 3.6.2)."""

    def test_user_depts_array_accepted(self) -> None:
        """user_depts 배열 정상 수락 (AC 3.6.1)."""
        from app.api.v1.chat import ChatRequest

        request = ChatRequest(query="테스트", session_id="sess-001", user_depts=["D001", "D002"])
        assert request.user_depts == ["D001", "D002"]

    def test_user_depts_single_item_array(self) -> None:
        """user_depts 단일 항목 배열 수락."""
        from app.api.v1.chat import ChatRequest

        request = ChatRequest(query="테스트", session_id="sess-001", user_depts=["D001"])
        assert request.user_depts == ["D001"]

    def test_user_depts_empty_list_rejected(self) -> None:
        """빈 배열 거부 (AC 3.6.2)."""
        from app.api.v1.chat import ChatRequest

        with pytest.raises(ValidationError, match="user_depts"):
            ChatRequest(query="테스트", session_id="sess-001", user_depts=[])

    def test_user_depts_null_rejected(self) -> None:
        """null 거부 (AC 3.6.2)."""
        from app.api.v1.chat import ChatRequest

        with pytest.raises(ValidationError):
            ChatRequest(query="테스트", session_id="sess-001", user_depts=None)

    def test_user_depts_missing_rejected(self) -> None:
        """미전송 거부 (AC 3.6.2)."""
        from app.api.v1.chat import ChatRequest

        with pytest.raises(ValidationError):
            ChatRequest(query="테스트", session_id="sess-001")

    def test_user_depts_blank_item_rejected(self) -> None:
        """빈 문자열 항목 거부 (AC 3.6.2)."""
        from app.api.v1.chat import ChatRequest

        with pytest.raises(ValidationError, match="user_depts"):
            ChatRequest(query="테스트", session_id="sess-001", user_depts=[""])

        with pytest.raises(ValidationError, match="user_depts"):
            ChatRequest(query="테스트", session_id="sess-001", user_depts=["D001", ""])

    def test_user_depts_whitespace_item_rejected(self) -> None:
        """공백 문자열 항목 거부 (AC 3.6.2)."""
        from app.api.v1.chat import ChatRequest

        with pytest.raises(ValidationError, match="user_depts"):
            ChatRequest(query="테스트", session_id="sess-001", user_depts=["  "])


class TestChatRequestExcludedDocs:
    """excluded_docs 필드 테스트 (AC 3.6.3, 3.6.4)."""

    def test_excluded_docs_accepted(self) -> None:
        """excluded_docs 정상 수락 (AC 3.6.3)."""
        from app.api.v1.chat import ChatRequest

        request = ChatRequest(
            query="테스트",
            session_id="sess-001",
            user_depts=["D001"],
            excluded_docs=["content-id-1", "content-id-2"],
        )
        assert request.excluded_docs == ["content-id-1", "content-id-2"]

    def test_excluded_docs_default_empty(self) -> None:
        """excluded_docs 미전송 시 빈 배열 기본값 (AC 3.6.4)."""
        from app.api.v1.chat import ChatRequest

        request = ChatRequest(query="테스트", session_id="sess-001", user_depts=["D001"])
        assert request.excluded_docs == []

    def test_excluded_docs_empty_list_accepted(self) -> None:
        """excluded_docs 빈 배열 허용."""
        from app.api.v1.chat import ChatRequest

        request = ChatRequest(
            query="테스트",
            session_id="sess-001",
            user_depts=["D001"],
            excluded_docs=[],
        )
        assert request.excluded_docs == []


class TestErrorEventGeneration:
    """에러 이벤트 생성 테스트."""

    def test_business_exception_format(self) -> None:
        """BusinessException이 올바른 에러 이벤트로 변환되는지 확인."""
        from app.api.v1.chat import format_sse
        from app.core.enums import ErrorCode

        # ErrorCode 사용하여 에러 이벤트 생성
        error = ErrorCode.LLM_CONNECTION

        result = format_sse("error", {"code": error.code, "msg": error.msg})

        assert "event: error" in result
        data_line = result.split("\n")[1]
        data_json = data_line.replace("data: ", "")
        parsed = json.loads(data_json)
        assert parsed["code"] == "AGT5001"

    def test_generic_error_format(self) -> None:
        """일반 에러가 AGT5000으로 변환되는지 확인."""
        from app.api.v1.chat import format_sse

        result = format_sse("error", {"code": "AGT5000", "msg": "내부 서버 오류가 발생했습니다."})

        data_line = result.split("\n")[1]
        data_json = data_line.replace("data: ", "")
        parsed = json.loads(data_json)
        assert parsed["code"] == "AGT5000"


class TestSSEEventSequence:
    """SSE 이벤트 시퀀스 테스트."""

    def test_event_format_consistency(self) -> None:
        """모든 이벤트 타입이 일관된 포맷을 가지는지 확인."""
        from app.api.v1.chat import format_sse
        from app.core.enums import ErrorCode

        event_types = ["thought", "message", "error", "done"]
        sample_data: dict[str, dict[str, Any]] = {
            "thought": {"content": "생각 중..."},
            "message": {"content": "답변"},
            "error": {"code": ErrorCode.INTERNAL_ERROR.code, "msg": ErrorCode.INTERNAL_ERROR.msg},
            "done": {"code": ErrorCode.SUCCESS.code, "msg": ErrorCode.SUCCESS.msg, "sources": []},
        }

        for event_type in event_types:
            result = format_sse(event_type, sample_data[event_type])

            # 포맷 검증
            lines = result.split("\n")
            assert lines[0].startswith("event: ")
            assert lines[1].startswith("data: ")
            assert lines[2] == ""
            assert lines[3] == ""

            # JSON 파싱 가능
            data_json = lines[1].replace("data: ", "")
            parsed = json.loads(data_json)
            assert isinstance(parsed, dict)


class TestStreamWorkflowUsage:
    """stream_workflow의 usage_metadata 집계·전달 테스트 (Story 6.1)."""

    @staticmethod
    def _make_request() -> Any:
        """최소 ChatRequest 인스턴스."""
        from app.api.v1.chat import ChatRequest

        return ChatRequest(
            query="질문",
            session_id="sess-test",
            history=[],
            user_depts=["dept-a"],
        )

    @staticmethod
    def _make_end_event(input_tokens: int, output_tokens: int, node: str = "rewriter") -> dict:
        """on_chat_model_end 이벤트 생성 헬퍼."""
        from types import SimpleNamespace

        output = SimpleNamespace(
            usage_metadata={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            }
        )
        return {
            "event": "on_chat_model_end",
            "name": "ChatOpenAI",
            "data": {"output": output},
            "metadata": {"langgraph_node": node},
        }

    @staticmethod
    def _make_end_event_no_usage(node: str = "rewriter") -> dict:
        """usage_metadata 없는 on_chat_model_end 이벤트 (AC 6.1.5)."""
        from types import SimpleNamespace

        output = SimpleNamespace(usage_metadata=None)
        return {
            "event": "on_chat_model_end",
            "name": "ChatOpenAI",
            "data": {"output": output},
            "metadata": {"langgraph_node": node},
        }

    @staticmethod
    def _install_fake_graph(
        monkeypatch: Any,
        events: list,
        raise_after: Exception | None = None,
    ) -> None:
        """get_compiled_graph를 가짜 그래프로 패치 (모든 이벤트 yield 후 옵션으로 예외 발생)."""
        from types import SimpleNamespace

        import app.api.v1.chat as chat_mod

        async def fake_astream_events(*_args: Any, **_kwargs: Any):
            for ev in events:
                yield ev
            if raise_after is not None:
                raise raise_after

        fake_graph = SimpleNamespace(astream_events=fake_astream_events)
        monkeypatch.setattr(chat_mod, "get_compiled_graph", lambda: fake_graph)

    @staticmethod
    def _parse_done(sse_chunks: list[str]) -> dict:
        """SSE 청크 리스트에서 마지막 done 이벤트의 data를 파싱."""
        last_done = None
        for chunk in sse_chunks:
            if chunk.startswith("event: done"):
                data_line = chunk.split("\n")[1]
                last_done = json.loads(data_line.replace("data: ", ""))
        assert last_done is not None, "done 이벤트가 없음"
        return last_done

    async def test_multi_on_chat_model_end_summation(self, monkeypatch: Any) -> None:
        """전 LLM 호출(rewriter+router+synthesizer) usage_metadata 합산 (AC 6.1.2, 6.1.7-b)."""
        from app.api.v1.chat import stream_workflow

        events = [
            self._make_end_event(100, 50, node="rewriter"),
            self._make_end_event(200, 30, node="router"),
            self._make_end_event(1500, 400, node="synthesizer"),
        ]
        self._install_fake_graph(monkeypatch, events)

        chunks = [c async for c in stream_workflow(self._make_request())]
        done = self._parse_done(chunks)

        assert done["usage"]["input_tokens"] == 1800
        assert done["usage"]["output_tokens"] == 480
        assert done["usage"]["total_tokens"] == 2280

    async def test_usage_metadata_missing_zero_and_warn(self, monkeypatch: Any) -> None:
        """usage_metadata None 시 0 처리 + usage_metadata_missing WARN (AC 6.1.5, 6.1.7-c)."""
        import app.api.v1.chat as chat_mod
        from app.api.v1.chat import stream_workflow

        warn_calls: list[dict] = []
        monkeypatch.setattr(
            chat_mod.logger,
            "warning",
            lambda event, **kw: warn_calls.append({"event": event, **kw}),
        )

        events = [
            self._make_end_event_no_usage(node="rewriter"),
            self._make_end_event(200, 30, node="router"),
            self._make_end_event_no_usage(node="synthesizer"),
        ]
        self._install_fake_graph(monkeypatch, events)

        chunks = [c async for c in stream_workflow(self._make_request())]
        done = self._parse_done(chunks)

        # 0 처리: 누락 2건은 무시, 정상 1건만 합산
        assert done["usage"]["input_tokens"] == 200
        assert done["usage"]["output_tokens"] == 30
        # usage_metadata_missing WARN 2건, rewriter/synthesizer 노드 명시
        missing_warns = [c for c in warn_calls if c["event"] == "usage_metadata_missing"]
        assert len(missing_warns) == 2
        nodes = {c["langgraph_node"] for c in missing_warns}
        assert nodes == {"rewriter", "synthesizer"}

    async def test_business_exception_partial_usage(self, monkeypatch: Any) -> None:
        """BusinessException 발생 시 done.usage에 부분 누적값 포함 (AC 6.1.6, 6.1.7-d)."""
        from app.api.v1.chat import stream_workflow
        from app.core.enums import ErrorCode
        from app.core.exceptions import BusinessException

        events = [self._make_end_event(120, 80, node="rewriter")]
        self._install_fake_graph(
            monkeypatch,
            events,
            raise_after=BusinessException(ErrorCode.LLM_CONNECTION, detail="test"),
        )

        chunks = [c async for c in stream_workflow(self._make_request())]
        done = self._parse_done(chunks)

        assert done["code"] == ErrorCode.LLM_CONNECTION.code
        # 한 노드 분 부분 누적값
        assert done["usage"]["input_tokens"] == 120
        assert done["usage"]["output_tokens"] == 80
        assert done["usage"]["total_tokens"] == 200

    async def test_stream_completed_log_fields(self, monkeypatch: Any) -> None:
        """stream_completed 로그: token_count 부재 + 실제 토큰 키 존재 (AC 6.1.8/6.1.7-e)."""
        import app.api.v1.chat as chat_mod
        from app.api.v1.chat import stream_workflow

        info_calls: list[dict] = []
        monkeypatch.setattr(
            chat_mod.logger,
            "info",
            lambda event, **kw: info_calls.append({"event": event, **kw}),
        )

        events = [
            self._make_end_event(100, 50, node="rewriter"),
            self._make_end_event(200, 30, node="synthesizer"),
        ]
        self._install_fake_graph(monkeypatch, events)

        async for _ in stream_workflow(self._make_request()):
            pass

        completed = [c for c in info_calls if c["event"] == "stream_completed"]
        assert len(completed) == 1
        log = completed[0]
        # 기존 chunk 카운트 키 제거 확인
        assert "token_count" not in log
        # 실제 토큰 키 존재 확인
        assert log["input_tokens"] == 300
        assert log["output_tokens"] == 80


class TestStreamWorkflowNoticeAndResponse:
    """검색 0건/오류 고지 선전송 + done.response 전달 테스트."""

    @staticmethod
    def _make_chain_start(node: str) -> dict:
        """on_chain_start 이벤트 생성 헬퍼."""
        return {"event": "on_chain_start", "name": node, "data": {}}

    @staticmethod
    def _make_chain_end(node: str, output: dict) -> dict:
        """on_chain_end 이벤트 생성 헬퍼."""
        return {"event": "on_chain_end", "name": node, "data": {"output": output}}

    @staticmethod
    def _make_stream_event(content: str, node: str = "synthesizer") -> dict:
        """on_chat_model_stream 이벤트 생성 헬퍼."""
        from types import SimpleNamespace

        return {
            "event": "on_chat_model_stream",
            "name": "ChatOpenAI",
            "data": {"chunk": SimpleNamespace(content=content)},
            "metadata": {"langgraph_node": node},
        }

    @staticmethod
    def _parse_messages(sse_chunks: list[str]) -> list[str]:
        """SSE 청크 리스트에서 message 이벤트 content 목록 추출."""
        contents = []
        for chunk in sse_chunks:
            if chunk.startswith("event: message"):
                data_line = chunk.split("\n")[1]
                contents.append(json.loads(data_line.replace("data: ", ""))["content"])
        return contents

    async def test_notice_sent_on_rag_empty(self, monkeypatch: Any) -> None:
        """rag 경로 검색 0건 시 고지가 답변 앞에 전송되고 done.response에 포함된다."""
        from app.api.v1.chat import RETRIEVAL_NOTICE_EMPTY, stream_workflow

        events = [
            self._make_chain_end("router", {"route": "rag"}),
            self._make_chain_end("retriever", {"sources": [], "retrieval_status": "empty"}),
            self._make_chain_start("synthesizer"),
            self._make_stream_event("일반 지식 답변"),
            self._make_chain_end("synthesizer", {"response": "일반 지식 답변"}),
        ]
        TestStreamWorkflowUsage._install_fake_graph(monkeypatch, events)

        chunks = [c async for c in stream_workflow(TestStreamWorkflowUsage._make_request())]
        messages = self._parse_messages(chunks)
        done = TestStreamWorkflowUsage._parse_done(chunks)

        assert messages[0] == RETRIEVAL_NOTICE_EMPTY
        assert messages[1] == "일반 지식 답변"
        assert done["response"] == RETRIEVAL_NOTICE_EMPTY + "일반 지식 답변"
        assert done["sources"] == []

    async def test_notice_sent_on_rag_error(self, monkeypatch: Any) -> None:
        """rag 경로 검색 오류 시 오류 고지 문구가 전송된다."""
        from app.api.v1.chat import RETRIEVAL_NOTICE_ERROR, stream_workflow

        events = [
            self._make_chain_end("router", {"route": "rag"}),
            self._make_chain_end("retriever", {"sources": [], "retrieval_status": "error"}),
            self._make_chain_start("synthesizer"),
            self._make_chain_end("synthesizer", {"response": "답변"}),
        ]
        TestStreamWorkflowUsage._install_fake_graph(monkeypatch, events)

        chunks = [c async for c in stream_workflow(TestStreamWorkflowUsage._make_request())]
        messages = self._parse_messages(chunks)
        done = TestStreamWorkflowUsage._parse_done(chunks)

        assert messages[0] == RETRIEVAL_NOTICE_ERROR
        assert done["response"] == RETRIEVAL_NOTICE_ERROR + "답변"

    async def test_no_notice_on_rag_ok(self, monkeypatch: Any) -> None:
        """검색 정상 시 고지가 전송되지 않고 done.response는 정본 그대로다."""
        from app.api.v1.chat import stream_workflow

        events = [
            self._make_chain_end("router", {"route": "rag"}),
            self._make_chain_end(
                "retriever",
                {"sources": [{"doc_title": "문서"}], "retrieval_status": "ok"},
            ),
            self._make_chain_start("synthesizer"),
            self._make_stream_event("문서 기반 답변"),
            self._make_chain_end("synthesizer", {"response": "문서 기반 답변"}),
        ]
        TestStreamWorkflowUsage._install_fake_graph(monkeypatch, events)

        chunks = [c async for c in stream_workflow(TestStreamWorkflowUsage._make_request())]
        messages = self._parse_messages(chunks)
        done = TestStreamWorkflowUsage._parse_done(chunks)

        assert messages == ["문서 기반 답변"]
        assert done["response"] == "문서 기반 답변"

    async def test_no_notice_on_non_rag_route(self, monkeypatch: Any) -> None:
        """rag 외 경로에서는 검색 0건이어도 고지가 전송되지 않는다."""
        from app.api.v1.chat import stream_workflow

        events = [
            self._make_chain_end("router", {"route": "both"}),
            self._make_chain_end("retriever", {"sources": [], "retrieval_status": "empty"}),
            self._make_chain_start("synthesizer"),
            self._make_chain_end("synthesizer", {"response": "답변"}),
        ]
        TestStreamWorkflowUsage._install_fake_graph(monkeypatch, events)

        chunks = [c async for c in stream_workflow(TestStreamWorkflowUsage._make_request())]
        done = TestStreamWorkflowUsage._parse_done(chunks)

        assert self._parse_messages(chunks) == []
        assert done["response"] == "답변"

    async def test_done_response_uses_postprocessed_value(self, monkeypatch: Any) -> None:
        """done.response는 스트리밍 청크 누적이 아닌 노드의 후처리 정본을 사용한다."""
        from app.api.v1.chat import stream_workflow

        events = [
            self._make_chain_start("synthesizer"),
            self._make_stream_event("AI: 답변"),
            self._make_chain_end("synthesizer", {"response": "답변"}),
        ]
        TestStreamWorkflowUsage._install_fake_graph(monkeypatch, events)

        chunks = [c async for c in stream_workflow(TestStreamWorkflowUsage._make_request())]
        done = TestStreamWorkflowUsage._parse_done(chunks)

        assert done["response"] == "답변"

    async def test_error_done_partial_response(self, monkeypatch: Any) -> None:
        """예외 발생 시 done.response에 그때까지의 부분 청크가 담긴다."""
        from app.api.v1.chat import stream_workflow
        from app.core.enums import ErrorCode
        from app.core.exceptions import BusinessException

        events = [
            self._make_chain_start("synthesizer"),
            self._make_stream_event("부분1"),
            self._make_stream_event("부분2"),
        ]
        TestStreamWorkflowUsage._install_fake_graph(
            monkeypatch,
            events,
            raise_after=BusinessException(ErrorCode.LLM_CONNECTION, detail="test"),
        )

        chunks = [c async for c in stream_workflow(TestStreamWorkflowUsage._make_request())]
        done = TestStreamWorkflowUsage._parse_done(chunks)

        assert done["code"] == ErrorCode.LLM_CONNECTION.code
        assert done["response"] == "부분1부분2"

    async def test_done_response_default_empty(self, monkeypatch: Any) -> None:
        """synthesizer 이벤트가 없는 스트림에서도 done.response는 빈 문자열로 안전하다."""
        from app.api.v1.chat import stream_workflow

        TestStreamWorkflowUsage._install_fake_graph(monkeypatch, [])

        chunks = [c async for c in stream_workflow(TestStreamWorkflowUsage._make_request())]
        done = TestStreamWorkflowUsage._parse_done(chunks)

        assert done["response"] == ""

    async def test_stream_gate_filters_non_synthesizer_chunks(self, monkeypatch: Any) -> None:
        """synthesizer 외 노드의 LLM 청크는 중계되지 않는다."""
        from app.api.v1.chat import stream_workflow

        events = [
            self._make_chain_start("synthesizer"),
            self._make_stream_event("유출 청크", node="rewriter"),
            self._make_stream_event("정상 청크", node="synthesizer"),
        ]
        TestStreamWorkflowUsage._install_fake_graph(monkeypatch, events)

        chunks = [c async for c in stream_workflow(TestStreamWorkflowUsage._make_request())]

        assert self._parse_messages(chunks) == ["정상 청크"]
