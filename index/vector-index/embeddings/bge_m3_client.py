"""BGE-M3 임베딩 클라이언트 (원격 API 방식)

보조 GPU 서버(TEI)에서 서빙 중인 BGE-M3 모델을 HTTP API로 호출합니다.
컨테이너 내부에서 모델을 직접 로드하지 않습니다.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, TypedDict

import requests

from config import settings

logger = logging.getLogger(__name__)


class SparseVector(TypedDict):
    indices: List[int]
    values: List[float]


class HybridEmbedding(TypedDict):
    dense: List[float]
    sparse: SparseVector


class EmbeddingClient(ABC):
    """임베딩 클라이언트 인터페이스"""

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """텍스트 리스트를 임베딩 벡터로 변환"""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """단일 텍스트를 임베딩 벡터로 변환"""
        pass


class BGEM3Client(EmbeddingClient):
    """BGE-M3 임베딩 클라이언트 — 보조 GPU 서버 TEI API 호출 방식"""

    def __init__(self):
        self.api_url = settings.bge_m3_api_url.rstrip("/")
        self.api_key = settings.bge_m3_api_key
        self.model_name = settings.bge_m3_model_name
        self.batch_size = settings.bge_m3_batch_size
        self.timeout = settings.bge_m3_timeout_seconds

        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        logger.info(
            "BGE-M3 API 클라이언트 초기화: url=%s, model=%s",
            self.api_url,
            self.model_name,
        )
        self._health_check()

    def _health_check(self):
        """서버 연결 확인"""
        try:
            resp = requests.post(
                self.api_url,
                headers=self._headers,
                json={"model": self.model_name, "input": ["health check"]},
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("BGE-M3 API 서버 연결 확인 완료")
        except Exception as e:
            logger.error("BGE-M3 API 서버 연결 실패: %s", e)
            raise RuntimeError(
                f"BGE-M3 API 서버({self.api_url})에 연결할 수 없습니다: {e}"
            )

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """텍스트 리스트를 임베딩 벡터로 변환 (배치 처리)"""
        if not texts:
            return []

        all_vectors: List[List[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            vectors = self._call_api(batch)
            all_vectors.extend(vectors)

        return all_vectors

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        """API 단일 배치 호출"""
        payload = {
            "model": self.model_name,
            "input": texts,
        }

        try:
            resp = requests.post(
                self.api_url,
                headers=self._headers,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            raise RuntimeError(
                f"BGE-M3 API 타임아웃 ({self.timeout}s): 배치 크기={len(texts)}"
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"BGE-M3 API 호출 실패: {e}")

        data = resp.json()

        # OpenAI-compatible 응답 형식: {"data": [{"embedding": [...], "index": N}, ...]}
        try:
            items = data["data"]
            # index 순서대로 정렬 후 벡터 추출
            items_sorted = sorted(items, key=lambda x: x["index"])
            vectors = [item["embedding"] for item in items_sorted]
        except (KeyError, TypeError) as e:
            raise RuntimeError(f"BGE-M3 API 응답 파싱 실패: {e}, response={data}")

        if len(vectors) != len(texts):
            raise RuntimeError(
                f"BGE-M3 API 응답 수 불일치: 요청={len(texts)}, 응답={len(vectors)}"
            )

        logger.debug("임베딩 완료: %d개 텍스트 → %d개 벡터", len(texts), len(vectors))
        return vectors

    def embed_text(self, text: str) -> List[float]:
        """단일 텍스트를 임베딩 벡터로 변환"""
        results = self.embed_texts([text])
        return results[0] if results else []


class BGEM3HybridClient:
    """BGE-M3 하이브리드(dense + sparse) 임베딩 클라이언트

    Mac 서버의 FlagEmbedding 기반 sparse_server를 호출하여
    한 번의 요청으로 dense 벡터와 sparse 벡터를 동시에 받습니다.
    """

    def __init__(self):
        self.api_url = settings.bge_m3_hybrid_api_url.rstrip("/")
        self.batch_size = settings.bge_m3_hybrid_batch_size
        self.timeout = settings.bge_m3_hybrid_timeout_seconds

        self._headers = {
            "Content-Type": "application/json",
        }

        logger.info(
            "BGE-M3 하이브리드 API 클라이언트 초기화: url=%s",
            self.api_url,
        )
        self._health_check()

    def _health_check(self):
        """서버 연결 확인"""
        try:
            resp = requests.post(
                self.api_url,
                headers=self._headers,
                json={"inputs": ["health check"]},
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("BGE-M3 하이브리드 API 서버 연결 확인 완료")
        except Exception as e:
            logger.error("BGE-M3 하이브리드 API 서버 연결 실패: %s", e)
            raise RuntimeError(
                f"BGE-M3 하이브리드 API 서버({self.api_url})에 연결할 수 없습니다: {e}"
            )

    def embed_texts(self, texts: List[str]) -> List[HybridEmbedding]:
        """텍스트 리스트를 하이브리드 임베딩(dense + sparse)으로 변환"""
        if not texts:
            return []

        results: List[HybridEmbedding] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            results.extend(self._call_api(batch))

        return results

    def embed_text(self, text: str) -> HybridEmbedding:
        """단일 텍스트를 하이브리드 임베딩으로 변환"""
        results = self.embed_texts([text])
        return results[0] if results else {"dense": [], "sparse": {"indices": [], "values": []}}

    def _call_api(self, texts: List[str]) -> List[HybridEmbedding]:
        """API 단일 배치 호출"""
        payload = {"inputs": texts}

        try:
            resp = requests.post(
                self.api_url,
                headers=self._headers,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            raise RuntimeError(
                f"BGE-M3 하이브리드 API 타임아웃 ({self.timeout}s): 배치 크기={len(texts)}"
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"BGE-M3 하이브리드 API 호출 실패: {e}")

        data = resp.json()

        try:
            dense_list = data["dense"]
            sparse_list = data["sparse"]
        except (KeyError, TypeError) as e:
            raise RuntimeError(
                f"BGE-M3 하이브리드 API 응답 파싱 실패: {e}, response keys={list(data.keys()) if isinstance(data, dict) else type(data)}"
            )

        if len(dense_list) != len(texts) or len(sparse_list) != len(texts):
            raise RuntimeError(
                f"BGE-M3 하이브리드 API 응답 수 불일치: 요청={len(texts)}, "
                f"dense={len(dense_list)}, sparse={len(sparse_list)}"
            )

        results: List[HybridEmbedding] = []
        for dense_vec, sparse_dict in zip(dense_list, sparse_list):
            results.append(
                {
                    "dense": dense_vec,
                    "sparse": {
                        "indices": sparse_dict["indices"],
                        "values": sparse_dict["values"],
                    },
                }
            )

        logger.debug(
            "하이브리드 임베딩 완료: %d개 텍스트 → dense %d개, sparse %d개",
            len(texts), len(dense_list), len(sparse_list),
        )
        return results
