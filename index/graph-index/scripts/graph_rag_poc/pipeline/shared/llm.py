"""Gemma vLLM 호출 헬퍼 — system/user 메시지 → text + usage.

이전:
- scripts/graph_rag_poc/_shared/lazy_value_test/eval_real_lazy.py: _chat
- scripts/graph_rag_poc/_shared/lazy_value_test/evaluate.py: call_gemma_plain
- scripts/graph_rag_poc/_shared/lazy_value_test/eval_abstain.py: call_strict/call_verify
"""
import time
from typing import Dict, Tuple

import requests

from .config import Config as C


_GEN_TEMPERATURE = 0.1  # 기본 생성 온도. 평가 재현성 위해 runner가 set_gen_temperature(0)으로 오버라이드.


def set_gen_temperature(t: float) -> None:
    """생성 온도 전역 오버라이드 (평가 결정론용). chat() temperature 미지정 호출에 적용."""
    global _GEN_TEMPERATURE
    _GEN_TEMPERATURE = t


def chat(system: str, user: str, max_tokens: int = 800,
         temperature: float | None = None, timeout: int | None = None) -> Tuple[str, Dict]:
    """단일 LLM 호출. (answer, usage) 반환. temperature 미지정 시 전역 기본값(_GEN_TEMPERATURE)."""
    if temperature is None:
        temperature = _GEN_TEMPERATURE
    payload = {
        "model": C.VLLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    per_try = timeout or C.VLLM_TIMEOUT
    last = None
    for attempt in range(4):  # 인프라 간헐 끊김 대비 재시도(1·2·4s 백오프). 매달림/크래시 방지.
        try:
            r = requests.post(C.vllm_chat_url(), json=payload, timeout=per_try)
            r.raise_for_status()
            body = r.json()
            return body["choices"][0]["message"]["content"].strip(), body.get("usage", {})
        except requests.exceptions.RequestException as e:
            last = e
            if attempt < 3:
                time.sleep(2 ** attempt)
    raise last


def chat_timed(system: str, user: str, **kwargs) -> Tuple[str, float, Dict]:
    """chat()의 시간 측정 버전. (answer, elapsed, usage)."""
    t0 = time.time()
    ans, usage = chat(system, user, **kwargs)
    return ans, time.time() - t0, usage


def usage_sum(*usages: Dict) -> Dict[str, int]:
    """여러 단계의 usage 합산."""
    return {
        "prompt_tokens": sum(u.get("prompt_tokens", 0) for u in usages),
        "completion_tokens": sum(u.get("completion_tokens", 0) for u in usages),
    }
