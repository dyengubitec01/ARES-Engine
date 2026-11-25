"""도구 관련 스키마."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolFunction(BaseModel):
    """OpenAI Function Calling Spec — function 내부."""

    name: str = Field(..., description="도구 이름")
    description: str = Field(..., description="도구 설명")
    parameters: dict[str, Any] = Field(..., description="도구 파라미터 JSON Schema")


class ToolDefinition(BaseModel):
    """OpenAI Function Calling Spec — 도구 정의."""

    type: Literal["function"] = Field(default="function", description="도구 타입")
    function: ToolFunction


class ToolsData(BaseModel):
    """GET /tools 응답 data 모델."""

    tools: list[ToolDefinition] = Field(
        ...,
        description="도구 목록 (OpenAI Function Calling Spec)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "summary",
                                "description": "텍스트 요약",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "text": {
                                            "type": "string",
                                            "description": "요약할 텍스트",
                                        }
                                    },
                                    "required": ["text"],
                                },
                            },
                        }
                    ]
                }
            ]
        },
    )
