"""Nemotron OCR v2 원격 OCR 클라이언트

GPU 서버에서 띄운 scripts/nemotron_server.py (FastAPI)와 통신.
OCR 클라이언트 표준 인터페이스 (extract_from_image_bytes, is_no_text)를 제공.

정책: 워커는 무조건 이 클라이언트만 사용. 다른 OCR(Gemma/Tesseract/PaddleOCR 등) 미허용.

서버 동작:
  POST /ocr (multipart) → 1차 추론 후 신뢰도 threshold 미만 영역만 crop+upscale 재추론.
  threshold/upscale/merge_level은 요청 파라미터로 넘긴다.

스레드 안전: 다중 워커 스레드에서 호출될 수 있으므로 GPU 동시성 제한용 세마포어 사용.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional, Tuple

import requests

from config import settings

logger = logging.getLogger(__name__)


class NemotronOCRClient:
    """Nemotron OCR v2 (FastAPI) 클라이언트"""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout: Optional[int] = None,
        max_concurrency: Optional[int] = None,
        retry_threshold: Optional[float] = None,
        retry_upscale: Optional[float] = None,
        merge_level: Optional[str] = None,
    ):
        self.host = host or settings.nemotron_ocr_host
        self.port = port or settings.nemotron_ocr_port
        self.timeout = timeout or settings.nemotron_ocr_timeout_seconds
        self.retry_threshold = (
            retry_threshold
            if retry_threshold is not None
            else settings.nemotron_ocr_retry_threshold
        )
        self.retry_upscale = (
            retry_upscale
            if retry_upscale is not None
            else settings.nemotron_ocr_retry_upscale
        )
        self.merge_level = merge_level or settings.nemotron_ocr_merge_level
        self.api_url = f"http://{self.host}:{self.port}/ocr"
        self.health_url = f"http://{self.host}:{self.port}/health"

        max_conc = max_concurrency or settings.nemotron_ocr_max_concurrency
        self._semaphore = threading.Semaphore(max_conc)

        logger.info(
            "Nemotron OCR 클라이언트 초기화: %s, retry_threshold=%.2f, retry_upscale=%.1f, "
            "merge_level=%s, max_concurrency=%d, timeout=%ds",
            self.api_url, self.retry_threshold, self.retry_upscale,
            self.merge_level, max_conc, self.timeout,
        )

    def extract_from_image_bytes(
        self,
        image_bytes: bytes,
        mime: str = "image/png",
    ) -> Tuple[str, float]:
        """이미지 바이트 → OCR 텍스트.

        Returns:
            (text, elapsed_seconds) — Gemma 인터페이스와 동일
        """
        filename = "page.png" if mime == "image/png" else "image.bin"
        files = {"file": (filename, image_bytes, mime)}
        params = {
            "merge_level": self.merge_level,
            "retry": True,
            "retry_threshold": self.retry_threshold,
            "retry_upscale": self.retry_upscale,
        }

        start = time.time()
        with self._semaphore:
            try:
                resp = requests.post(
                    self.api_url,
                    files=files,
                    params=params,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                text = (data.get("text") or "").strip()
                elapsed = time.time() - start
                return text, elapsed
            except Exception as e:
                logger.error("Nemotron OCR 호출 실패: %s", e)
                raise

    def is_no_text(self, ocr_result: Optional[str]) -> bool:
        """OCR 결과가 사실상 빈 텍스트인지 판정.

        Nemotron 서버는 텍스트가 없으면 빈 문자열을 반환한다 (Gemma의 '[텍스트 없음]' 같은
        센티넬은 사용하지 않음). Gemma 호환을 위해 해당 토큰도 함께 처리.
        """
        if not ocr_result:
            return True
        stripped = ocr_result.strip()
        if not stripped:
            return True
        return stripped == "[텍스트 없음]" or stripped.startswith("[텍스트 없음")

    def health_check(self) -> bool:
        """FastAPI 서버 헬스체크 (/health)"""
        try:
            resp = requests.get(self.health_url, timeout=5)
            return resp.ok
        except Exception as e:
            logger.warning("Nemotron OCR 헬스체크 실패: %s", e)
            return False
