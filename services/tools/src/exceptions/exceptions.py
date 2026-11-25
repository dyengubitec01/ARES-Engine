"""TOL 커스텀 예외 정의."""


class InvalidScopeError(Exception):
    """유효하지 않은 Scope 값 전달 시 발생하는 예외.

    전역 예외 핸들러에서 TOL 표준 응답(TOL010130, HTTP 400)으로 변환된다.

    Attributes:
        scope: 전달된 유효하지 않은 Scope 값.
        allowed_scopes: 허용된 Scope 목록.
    """

    def __init__(
        self,
        scope: str,
        allowed_scopes: list[str] | None = None,
    ) -> None:
        self.scope = scope
        self.allowed_scopes = allowed_scopes or []
        super().__init__(f"유효하지 않은 Scope: {scope}")


class ExternalAPIError(Exception):
    """외부 API 호출 실패 시 발생하는 비즈니스 예외.

    프록시 Service에서 외부 API 호출이 실패했을 때 발생.
    전역 예외 핸들러에서 TOL 표준 응답(TOL030130, HTTP 502)으로 변환된다.

    Attributes:
        api_name: 프록시 대상 API 이름.
        status_code: 외부 API 응답 상태 코드 (없으면 None).
        detail: 에러 상세 메시지.
    """

    def __init__(
        self,
        api_name: str,
        status_code: int | None = None,
        detail: str = "",
    ) -> None:
        self.api_name = api_name
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"외부 API 호출 실패: {api_name} — {detail}")


class LLMProviderError(Exception):
    """Failover 체인 소진 시 발생하는 비즈니스 예외.

    Provider 계층에서 모든 LLM 호출이 실패했을 때 발생.
    전역 예외 핸들러에서 TOL 표준 응답(TOL020130, HTTP 503)으로 변환된다.

    Attributes:
        detail: 사용자 안내 메시지 (models.yaml fallback_message).
        role: 요청된 역할명.
        chain: 시도된 fallback 체인.
    """

    def __init__(
        self,
        detail: str,
        role: str = "",
        chain: list[str] | None = None,
    ) -> None:
        self.detail = detail
        self.role = role
        self.chain = chain or []
        super().__init__(detail)
