"""GET /tools 엔드포인트 테스트.

Router 통합 테스트 + OpenAI Spec 검증 + 에러 응답 테스트.
"""

import pytest
from fastapi.testclient import TestClient

from src.config.tools import load_tools_config
from src.main import app
from src.schemas.codes import TOLCode, TOLMessage


@pytest.fixture(autouse=True)
def clear_tools_cache():
    """각 테스트마다 도구 설정 캐시 클리어."""
    load_tools_config.cache_clear()
    yield
    load_tools_config.cache_clear()


client = TestClient(app)


# ── 정상 응답 테스트 ──


class TestToolsEndpointSuccess:
    """GET /tools 정상 응답 테스트."""

    def test_agent_scope_returns_200(self):
        """agent Scope → 200 + 도구 목록."""
        resp = client.get("/v1/tools", headers={"X-TOL-Scope": "agent"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == TOLCode.SUCCESS_QUERY.value
        assert body["msg"] == TOLMessage.SUCCESS.value
        assert isinstance(body["data"]["tools"], list)
        assert len(body["data"]["tools"]) > 0

    def test_backend_scope_returns_200(self):
        """backend Scope → 200 + 도구 목록."""
        resp = client.get("/v1/tools", headers={"X-TOL-Scope": "backend"})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]["tools"]) > 0

    def test_frontend_scope_returns_empty_tools(self):
        """frontend Scope → 200 + 빈 도구 목록."""
        resp = client.get("/v1/tools", headers={"X-TOL-Scope": "frontend"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["tools"] == []


# ── OpenAI Function Calling Spec 검증 ──


class TestOpenAISpec:
    """응답이 OpenAI Function Calling Spec을 준수하는지 검증."""

    def test_tool_has_type_function(self):
        """각 도구의 type이 "function"."""
        resp = client.get("/v1/tools", headers={"X-TOL-Scope": "agent"})
        tools = resp.json()["data"]["tools"]
        for tool in tools:
            assert tool["type"] == "function"

    def test_tool_has_function_fields(self):
        """function 내에 name, description, parameters 존재."""
        resp = client.get("/v1/tools", headers={"X-TOL-Scope": "agent"})
        tools = resp.json()["data"]["tools"]
        for tool in tools:
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func

    def test_parameters_has_json_schema_structure(self):
        """parameters가 JSON Schema 구조(type, properties)."""
        resp = client.get("/v1/tools", headers={"X-TOL-Scope": "agent"})
        tools = resp.json()["data"]["tools"]
        for tool in tools:
            params = tool["function"]["parameters"]
            assert params["type"] == "object"
            assert "properties" in params


# ── TOL 표준 응답 형식 검증 ──


class TestTOLResponseFormat:
    """TOL 표준 응답 래핑 검증."""

    def test_success_response_has_code_msg_data(self):
        """성공 응답에 code, msg, data 필드 존재."""
        resp = client.get("/v1/tools", headers={"X-TOL-Scope": "agent"})
        body = resp.json()
        assert "code" in body
        assert "msg" in body
        assert "data" in body

    def test_success_code_is_tol010100(self):
        """성공 코드가 TOL010100."""
        resp = client.get("/v1/tools", headers={"X-TOL-Scope": "agent"})
        assert resp.json()["code"] == "TOL010100"

    def test_data_contains_tools_list(self):
        """data.tools가 리스트."""
        resp = client.get("/v1/tools", headers={"X-TOL-Scope": "agent"})
        assert isinstance(resp.json()["data"]["tools"], list)


# ── 에러 응답 테스트 ──


class TestToolsEndpointErrors:
    """GET /tools 에러 응답 테스트."""

    def test_missing_header_returns_400(self):
        """헤더 미전달 → 400."""
        resp = client.get("/v1/tools")
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == TOLCode.ERROR_INVALID_SCOPE.value
        assert body["msg"] == TOLMessage.INVALID_SCOPE.value
        assert body["data"] is None

    def test_invalid_scope_returns_400(self):
        """유효하지 않은 Scope → 400."""
        resp = client.get("/v1/tools", headers={"X-TOL-Scope": "admin"})
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == TOLCode.ERROR_INVALID_SCOPE.value
        assert body["data"] is None

    def test_error_response_has_code_msg_data(self):
        """에러 응답에도 code, msg, data 필드 존재."""
        resp = client.get("/v1/tools", headers={"X-TOL-Scope": "invalid"})
        body = resp.json()
        assert "code" in body
        assert "msg" in body
        assert "data" in body


# ── Scope별 필터링 검증 ──


class TestScopeFiltering:
    """Scope별 도구 필터링 동작 검증."""

    def test_agent_tools_contain_summary(self):
        """agent Scope → summary 도구 포함."""
        resp = client.get("/v1/tools", headers={"X-TOL-Scope": "agent"})
        tools = resp.json()["data"]["tools"]
        names = [t["function"]["name"] for t in tools]
        assert "summary" in names

    def test_backend_tools_contain_summary(self):
        """backend Scope → summary 도구 포함."""
        resp = client.get("/v1/tools", headers={"X-TOL-Scope": "backend"})
        tools = resp.json()["data"]["tools"]
        names = [t["function"]["name"] for t in tools]
        assert "summary" in names

    def test_frontend_tools_exclude_summary(self):
        """frontend Scope → summary 도구 미포함."""
        resp = client.get("/v1/tools", headers={"X-TOL-Scope": "frontend"})
        tools = resp.json()["data"]["tools"]
        names = [t["function"]["name"] for t in tools]
        assert "summary" not in names
