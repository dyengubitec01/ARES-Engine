"""파이프라인 공통 설정 — 환경변수 기반.

이전: scripts/graph_rag_poc/_shared/config_poc.py
"""
import os


class Config:
    # 답변 LLM (Gemma vLLM)
    VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000")
    VLLM_MODEL = os.getenv("VLLM_MODEL", "gemma-3-27b")
    VLLM_TIMEOUT = int(os.getenv("VLLM_TIMEOUT", "180"))

    # 운영 Qdrant
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "rag_chunks_v1_dev")

    # BGE-M3 임베딩
    BGE_M3_API_URL = os.getenv("BGE_M3_API_URL", "http://localhost:4000/v1/embeddings")
    BGE_M3_API_KEY = os.getenv("BGE_M3_API_KEY", "")
    BGE_M3_MODEL = os.getenv("BGE_M3_MODEL_NAME", "embed-bge-m3")

    @classmethod
    def vllm_chat_url(cls) -> str:
        return f"{cls.VLLM_BASE_URL}/v1/chat/completions"

    @classmethod
    def vllm_models_url(cls) -> str:
        return f"{cls.VLLM_BASE_URL}/v1/models"

    @classmethod
    def qdrant_url(cls) -> str:
        return f"http://{cls.QDRANT_HOST}:{cls.QDRANT_PORT}"


# 데이터 디렉터리 (graph_rag_poc/data 기준)
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "data"))
CHUNKS_DIR = os.path.join(DATA_DIR, "chunks")
QA_DIR = os.path.join(DATA_DIR, "qa")
GRAPHS_DIR = os.path.join(DATA_DIR, "graphs")
