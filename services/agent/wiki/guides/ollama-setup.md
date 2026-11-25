# Ollama 로컬 LLM 설정 가이드

## 개요

이 가이드는 로컬 환경에서 Ollama를 사용하여 LLM 테스트를 수행하는 방법을 설명합니다.

## 1. Ollama 설치

### Windows

1. [Ollama 공식 사이트](https://ollama.com/download)에서 Windows 설치 파일 다운로드
2. 설치 파일 실행 후 안내에 따라 설치
3. 설치 확인:
   ```bash
   ollama --version
   ```

### macOS

```bash
# Homebrew 사용
brew install ollama

# 또는 공식 사이트에서 다운로드
# https://ollama.com/download
```

### Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

## 2. 모델 다운로드

프로젝트에서 사용하는 권장 모델:

```bash
# 경량 모델 (빠른 테스트용, ~2GB)
ollama pull qwen2.5:3b

# 고품질 모델 (실제 테스트용, ~4.7GB)
ollama pull qwen2.5:7b
```

### 설치된 모델 확인

```bash
ollama list
```

예상 출력:
```
NAME           ID              SIZE      MODIFIED
qwen2.5:7b     845dbda0ea48    4.7 GB    ...
qwen2.5:3b     357c53fb659c    2.0 GB    ...
```

## 3. Ollama 서버 실행

Ollama는 기본적으로 `http://localhost:11434`에서 실행됩니다.

```bash
# 서버 시작 (백그라운드에서 자동 실행되는 경우가 많음)
ollama serve
```

### 서버 상태 확인

```bash
curl http://localhost:11434/api/tags
```

## 4. 환경 설정

### .env 파일 설정

프로젝트 루트의 `.env` 파일을 다음과 같이 설정:

```bash
# Ollama 서버 URL (OpenAI 호환 API)
PRIMARY_LLM_BASE_URL=http://localhost:11434/v1
SECONDARY_LLM_BASE_URL=http://localhost:11434/v1
```

### config/models.yaml 설정

```yaml
roles:
  fast:
    model: "qwen2.5:3b"
    server: "primary"
    fallback_role: "balanced"
    description: "빠른 응답용 경량 모델"

  balanced:
    model: "qwen2.5:7b"
    server: "primary"
    fallback_role: null
    description: "품질과 속도 균형 모델"

servers:
  primary:
    base_url_env: "PRIMARY_LLM_BASE_URL"

fallback_message: "서비스가 일시적으로 불안정합니다."
```

## 5. 연결 테스트

### curl로 직접 테스트

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5:3b",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Python으로 테스트

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="qwen2.5:3b",
    base_url="http://localhost:11434/v1",
    api_key="not-needed",
)

response = llm.invoke("안녕하세요!")
print(response.content)
```

## 6. 프로젝트 테스트 실행

```bash
# 전체 테스트
uv run pytest

# Query Rewriter 테스트만
uv run pytest tests/test_query_rewriter.py -v
```

## 7. 문제 해결

### Ollama 서버가 실행되지 않음

```bash
# Windows: 작업 관리자에서 Ollama 프로세스 확인
# 또는 수동으로 시작
ollama serve
```

### 모델 로딩이 느림

- 첫 번째 요청 시 모델을 메모리에 로드하므로 시간이 걸릴 수 있음
- 이후 요청은 빠르게 처리됨

### 메모리 부족

- `qwen2.5:3b` 모델은 약 4GB RAM 필요
- `qwen2.5:7b` 모델은 약 8GB RAM 필요
- 메모리가 부족하면 더 작은 모델 사용:
  ```bash
  ollama pull qwen2.5:1.5b
  ```

### GPU 가속

- NVIDIA GPU가 있으면 자동으로 CUDA 사용
- GPU 상태 확인: `nvidia-smi`

## 8. 추가 모델 (선택사항)

```bash
# 코드 특화 모델
ollama pull codellama:7b

# 한국어 특화 (Llama 기반)
ollama pull llama2:7b

# 초경량 모델 (테스트용)
ollama pull phi:latest
```

## 참고 링크

- [Ollama 공식 문서](https://ollama.com/)
- [Ollama GitHub](https://github.com/ollama/ollama)
- [지원 모델 목록](https://ollama.com/library)
