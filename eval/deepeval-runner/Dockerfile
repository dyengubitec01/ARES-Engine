FROM python:3.11-slim

# 로그를 버퍼링 없이 즉시 출력 (Jenkins/도커 로그에서 진행 상황 실시간 확인)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/ ./scripts/

ENTRYPOINT ["python", "scripts/evaluate.py"]
