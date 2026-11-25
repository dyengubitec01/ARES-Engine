"""요약 엔드포인트 요청/응답 스키마."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """대화 메시지."""

    role: Literal["user", "assistant"] = Field(
        ...,
        description="메시지 역할",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="메시지 내용",
    )


class SummaryRequest(BaseModel):
    """POST /v1/summary 요청 모델."""

    history: list[ChatMessage] = Field(
        ...,
        min_length=1,
        description="대화 이력 (최소 1건)",
    )
    summary: str | None = Field(
        default=None,
        min_length=1,
        description="이전 요약 (갱신 시 전달)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "summary": "이전 대화 요약 내용",
                    "history": [
                        {"role": "user", "content": "그래서 결론이 뭐야?"},
                        {"role": "assistant", "content": "핵심은 ...입니다."},
                    ],
                },
                {
                    "history": [
                        {"role": "user", "content": "안녕"},
                        {"role": "assistant", "content": "안녕하세요!"},
                    ],
                },
            ]
        },
    )


class SummaryData(BaseModel):
    """POST /v1/summary 응답 data 모델."""

    summary: str = Field(
        ...,
        description="요약 결과 텍스트",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "summary": "AI는 인간 지적 능력의 컴퓨터 구현 기술이며, LLM 발전으로 자연어 처리에서 혁신을 이루고 있다."
                }
            ]
        },
    )
