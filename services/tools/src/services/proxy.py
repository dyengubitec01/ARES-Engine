"""외부 API 프록시 서비스.

config/proxy.yaml에 정의된 대상 API로 비동기 HTTP 요청을 프록시한다.
"""

import logging
import time
from typing import Any

import httpx

from src.config.proxy import ProxyTargetConfig, load_proxy_config
from src.exceptions.exceptions import ExternalAPIError
from src.middleware.langfuse import create_span
from src.middleware.trace_id import TRACE_ID_HEADER, get_trace_id

logger = logging.getLogger(__name__)


def get_proxy_target(api_name: str) -> ProxyTargetConfig:
    """프록시 대상 API 설정 조회.

    Args:
        api_name: 프록시 대상 API 이름.

    Returns:
        ProxyTargetConfig 인스턴스.

    Raises:
        ExternalAPIError: 등록되지 않은 API 이름.
    """
    config = load_proxy_config()
    target = config.get_target(api_name)
    if target is None:
        registered = config.get_target_names()
        raise ExternalAPIError(
            api_name=api_name,
            detail=f"등록되지 않은 프록시 대상: {api_name}. "
            f"등록된 대상: {registered}",
        )
    return target


async def proxy_request(
    api_name: str,
    method: str = "GET",
    path: str = "",
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    trace_context: dict[str, str] | None = None,
) -> dict[str, Any]:
    """외부 API로 프록시 요청 수행.

    Args:
        api_name: 프록시 대상 API 이름 (proxy.yaml에 정의).
        method: HTTP 메서드.
        path: base_url에 추가할 경로.
        params: 쿼리 파라미터.
        body: 요청 본문 (JSON).
        headers: 추가 요청 헤더.
        trace_context: Langfuse trace 연결 정보 (cross-service).

    Returns:
        외부 API 응답 데이터 (status_code, headers, body).

    Raises:
        ExternalAPIError: 외부 API 호출 실패.
    """
    target = get_proxy_target(api_name)

    url = f"{target.base_url.rstrip('/')}/{path.lstrip('/')}" if path else target.base_url

    # 헤더 구성: 설정 헤더 + Trace-ID + 사용자 헤더
    request_headers = dict(target.headers)
    trace_id = get_trace_id()
    if trace_id:
        request_headers[TRACE_ID_HEADER] = trace_id
    if headers:
        request_headers.update(headers)

    # Langfuse span
    span = create_span(
        name="proxy-request",
        input_data={
            "api_name": api_name,
            "method": method,
            "url": url,
        },
        trace_context=trace_context,
    )

    start_time = time.monotonic()
    last_error: Exception | None = None

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(target.timeout),
    ) as client:
        for attempt in range(1, target.max_retries + 1):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=body if body is not None else None,
                    headers=request_headers,
                )

                elapsed = time.monotonic() - start_time

                # 4xx/5xx 에러 처리
                if response.status_code >= 400:
                    logger.warning(
                        "프록시 응답 에러: api=%s, status=%d, attempt=%d/%d",
                        api_name, response.status_code, attempt, target.max_retries,
                    )
                    last_error = ExternalAPIError(
                        api_name=api_name,
                        status_code=response.status_code,
                        detail=f"HTTP {response.status_code}",
                    )
                    # 4xx는 재시도하지 않음 (클라이언트 에러)
                    if response.status_code < 500:
                        break
                    continue

                # 응답 본문 파싱 (JSON 파싱 실패 시 text fallback)
                content_type = response.headers.get("content-type", "")
                if content_type.startswith("application/json"):
                    try:
                        parsed_body = response.json()
                    except (ValueError, UnicodeDecodeError):
                        parsed_body = response.text
                else:
                    parsed_body = response.text

                result = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": parsed_body,
                }

                if span:
                    span.update(
                        output={
                            "status": "success",
                            "status_code": response.status_code,
                            "elapsed_ms": round(elapsed * 1000, 2),
                        },
                    )
                    span.end()

                logger.info(
                    "프록시 성공: api=%s, status=%d, elapsed=%.2fs",
                    api_name, response.status_code, elapsed,
                )
                return result

            except httpx.TimeoutException:
                elapsed = time.monotonic() - start_time
                logger.warning(
                    "프록시 타임아웃: api=%s, attempt=%d/%d, elapsed=%.2fs",
                    api_name, attempt, target.max_retries, elapsed,
                )
                last_error = ExternalAPIError(
                    api_name=api_name,
                    detail=f"타임아웃 ({target.timeout}s)",
                )

            except httpx.ConnectError as e:
                elapsed = time.monotonic() - start_time
                logger.warning(
                    "프록시 연결 실패: api=%s, attempt=%d/%d, error=%s",
                    api_name, attempt, target.max_retries, e,
                )
                last_error = ExternalAPIError(
                    api_name=api_name,
                    detail=f"연결 실패: {e}",
                )

    # 재시도 소진
    elapsed = time.monotonic() - start_time

    if span:
        span.update(
            output={
                "status": "failed",
                "elapsed_ms": round(elapsed * 1000, 2),
                "detail": str(last_error),
            },
            level="ERROR",
        )
        span.end()

    if isinstance(last_error, ExternalAPIError):
        raise last_error

    raise ExternalAPIError(
        api_name=api_name,
        detail="알 수 없는 에러",
    )
