"""Gemma-3-27B vLLM 멀티모달 OCR 클라이언트

vLLM의 OpenAI 호환 chat/completions API로 이미지를 보내 텍스트를 추출합니다.
GPU 동시성을 제한해 검색·답변 응답에 영향을 최소화합니다.
"""
from __future__ import annotations

import base64
import logging
import re
import threading
import time
from typing import Optional, Tuple

import requests

from config import settings

logger = logging.getLogger(__name__)


# 기본 OCR 프롬프트
# 의도: "이미지에서 추출한 텍스트:" 같은 메타 헤더, **상단:**/**하단:** 같은 위치 라벨,
# [이미지] placeholder 등 검색 노이즈가 될 표현 출력 금지.
OCR_PROMPT = (
    "이 이미지에서 텍스트만 그대로 추출해주세요. "
    "표가 있으면 markdown 표 형식으로, 목록은 markdown 목록 형식으로 변환하세요. "
    "단, '이미지에서 추출한 텍스트:' 같은 메타 헤더, "
    "'**상단:**', '**중앙:**', '**하단:**' 같은 위치 라벨, "
    "[이미지] 같은 placeholder는 출력하지 마세요. "
    "원문 텍스트만 빠짐없이 출력하세요. "
    "이미지에 텍스트가 전혀 없으면 [텍스트 없음]이라고만 답해주세요."
)


# 모델이 프롬프트를 무시하고 출력할 수 있는 메타 토큰 후처리 패턴.
# 프롬프트 + 후처리 두 단계로 노이즈를 차단한다.
_OCR_META_HEADERS = re.compile(
    r"^#{1,6}\s*이미지에서\s*추출한?\s*텍스트\s*[:：]?\s*$",
    re.MULTILINE,
)
_OCR_POSITION_LABELS = re.compile(
    r"\*\*\s*("
    r"상단|중앙|하단|좌측|우측|"
    r"상단\s*좌측|상단\s*우측|"
    r"중앙\s*좌측|중앙\s*우측|"
    r"하단\s*좌측|하단\s*우측|"
    r"좌측\s*상단|좌측\s*중앙|좌측\s*하단|"
    r"우측\s*상단|우측\s*중앙|우측\s*하단"
    r")\s*[:：]?\s*\*\*"
)
_OCR_PLACEHOLDER_IMAGE = re.compile(r"\[\s*이미지\s*\]")


def _post_process_ocr(text: str) -> str:
    """OCR 응답에서 검색 노이즈가 될 수 있는 메타 토큰 제거.

    제거 대상:
    - '## 이미지에서 추출한 텍스트:' 같은 헤더 (line 단위)
    - '**상단:**', '**중앙 좌측:**' 등 위치 라벨
    - '[이미지]' placeholder

    `[텍스트 없음]` 응답은 보존 (is_no_text 판정에 사용).
    """
    if not text:
        return text
    text = _OCR_META_HEADERS.sub("", text)
    text = _OCR_POSITION_LABELS.sub("", text)
    text = _OCR_PLACEHOLDER_IMAGE.sub("", text)
    # 정리 후 빈 줄이 3개 이상 연속되면 2개로 압축
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class GemmaOCRClient:
    """Gemma-3-27B vLLM OCR 클라이언트

    멀티 스레드 환경에서 GPU 동시성을 제한하기 위해 세마포어 사용.
    기본 동시성=1로 검색·답변 응답을 보호한다.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_concurrency: Optional[int] = None,
        prompt: str = OCR_PROMPT,
    ):
        self.host = host or settings.gemma_ocr_host
        self.port = port or settings.gemma_ocr_port
        self.model = model or settings.gemma_ocr_model
        self.timeout = timeout or settings.gemma_ocr_timeout_seconds
        self.prompt = prompt
        self.api_url = f"http://{self.host}:{self.port}/v1/chat/completions"

        max_conc = max_concurrency or settings.gemma_ocr_max_concurrency
        self._semaphore = threading.Semaphore(max_conc)

        logger.info(
            "Gemma OCR 클라이언트 초기화: %s, model=%s, max_concurrency=%d, timeout=%ds",
            self.api_url, self.model, max_conc, self.timeout,
        )

    def extract_from_image_bytes(
        self,
        image_bytes: bytes,
        mime: str = "image/png",
    ) -> Tuple[str, float]:
        """이미지 바이트 → OCR 텍스트.

        Returns:
            (text, elapsed_seconds)
        """
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return self._call_ocr(b64, mime)

    def _call_ocr(self, image_b64: str, mime: str) -> Tuple[str, float]:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                        },
                        {"type": "text", "text": self.prompt},
                    ],
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.1,
        }

        start = time.time()
        # GPU 동시성 제한 — 검색 응답 영향 최소화
        with self._semaphore:
            try:
                resp = requests.post(
                    self.api_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                raw_text = data["choices"][0]["message"]["content"]
                # 메타 토큰 후처리 (검색 노이즈 방지)
                text = _post_process_ocr(raw_text)
                elapsed = time.time() - start
                return text, elapsed
            except Exception as e:
                logger.error("Gemma OCR 호출 실패: %s", e)
                raise

    def is_no_text(self, ocr_result: Optional[str]) -> bool:
        """OCR 결과가 '[텍스트 없음]' 응답인지 판정"""
        if not ocr_result:
            return True
        stripped = ocr_result.strip()
        return stripped == "[텍스트 없음]" or stripped.startswith("[텍스트 없음")

    def health_check(self) -> bool:
        """vLLM 서버 헬스체크 (/v1/models 응답 확인)"""
        try:
            resp = requests.get(
                f"http://{self.host}:{self.port}/v1/models",
                timeout=5,
            )
            return resp.ok
        except Exception as e:
            logger.warning("Gemma OCR 헬스체크 실패: %s", e)
            return False
