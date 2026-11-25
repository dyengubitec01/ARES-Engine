# -*- coding: utf-8 -*-
"""GLiNER2 엔티티 추출 API 서버 — NEXUS GPU 세션에 앱으로 배포.

텍스트 배치를 받아 엔티티를 반환. build_graph.py 와 동일한 라벨/정제 로직(결과 일관).
사내 오케스트레이터(build_graph)가 이 API를 호출해 GPU 추출을 위임.

배포 (NEXUS GPU 세션에서):
  pip install fastapi "uvicorn[standard]" gliner2 torch     # torch는 CUDA 빌드
  uvicorn gliner2_server:app --host 0.0.0.0 --port 8000
  # 백그라운드: nohup uvicorn gliner2_server:app --host 0.0.0.0 --port 8000 > gliner2.log 2>&1 &

테스트:
  curl http://localhost:8000/health
  curl -X POST http://localhost:8000/extract -H "Content-Type: application/json" \
       -d '{"texts":["증평군은 충북에 있는 스마트도시다","포항시 생활밀착형 사업"]}'
"""
import re
from typing import List

from fastapi import FastAPI
from pydantic import BaseModel
from gliner2 import GLiNER2

MODEL_NAME = "fastino/gliner2-multi-v1"

# build_graph.py 와 동일
ENTITY_LABELS = {
    "organization": "company, institution, department, university, agency",
    "product": "specific product name, service name, solution name",
    "system": "software system, platform, framework",
    "technology": "technology term, algorithm, methodology, AI/ML technique",
    "project": "project name, initiative, business name",
    "person": "person name",
    "location": "place, region, country, city",
    "equipment": "hardware, sensor, device",
}
LABEL_TO_TYPE = {
    "organization": "ORG", "product": "PRODUCT", "system": "SYSTEM",
    "technology": "CONCEPT", "project": "PROJECT", "person": "PERSON",
    "location": "LOCATION", "equipment": "PRODUCT",
}
_TRAILING_JOSA = re.compile(
    r"(을|를|이|가|은|는|의|에|와|과|도|로|으로|에서|에게|으로서|에는|이라|라|만|까지|부터)\s*$"
)
_MAX_SPAN_CHARS = 50


def clean_entity_text(t: str) -> str:
    cleaned = (t or "").strip().rstrip(",.;:")
    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = _TRAILING_JOSA.sub("", cleaned).strip()
    return cleaned


# 모델 로드 (import 시 1회).
# GLiNER2 는 그 자체가 torch nn.Module (encoder=mdeberta-v3 + heads). from_pretrained 의
# device 인자는 실제 이동을 보장하지 않으므로, 로드 후 무조건 .to() 로 옮기고
# 실제 파라미터 device 로 검증한다(_REAL_DEVICE). ONNX 백엔드 미사용.
import torch  # noqa: E402

_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
extractor = GLiNER2.from_pretrained(MODEL_NAME)
extractor.to(_DEVICE)
try:
    _REAL_DEVICE = str(next(extractor.parameters()).device)
except StopIteration:
    _REAL_DEVICE = "unknown"
print(f"[GLiNER2] requested={_DEVICE} actual={_REAL_DEVICE} "
      f"(cuda_available={torch.cuda.is_available()})", flush=True)
if _DEVICE == "cuda" and not _REAL_DEVICE.startswith("cuda"):
    print("[GLiNER2][경고] cuda 요청했으나 파라미터가 GPU에 없음 — CPU로 추론됨(느림)", flush=True)
schema = extractor.create_schema().entities(ENTITY_LABELS)

app = FastAPI(title="GLiNER2 Extract API")


class ExtractRequest(BaseModel):
    texts: List[str]


@app.get("/health")
def health():
    # device 는 '요청'이 아니라 '실제 파라미터 위치'(_REAL_DEVICE) — 검증된 값
    return {"status": "ok", "model": MODEL_NAME,
            "cuda": torch.cuda.is_available(), "device": _REAL_DEVICE}


@app.post("/extract")
def extract(req: ExtractRequest):
    """texts[i] → results[i].entities = [{name, type}, ...] (정제됨, 중복 span 포함).
    정규화(normalize_name)·병합은 오케스트레이터(build_graph)가 수행."""
    results = []
    for text in req.texts:
        ents = []
        if text and text.strip():
            raw = extractor.extract(text, schema)
            for label, spans in (raw.get("entities") or {}).items():
                etype = LABEL_TO_TYPE.get(label, "OTHER")
                if not isinstance(spans, list):
                    continue
                for s in spans:
                    if not isinstance(s, str) or len(s) > _MAX_SPAN_CHARS:
                        continue
                    name = clean_entity_text(s)
                    if not name or len(name) <= 1:
                        continue
                    ents.append({"name": name, "type": etype})
        results.append({"entities": ents})
    return {"results": results}
