"""OCR 바이크오프 실행기 (2단계).

find_bad_ocr_chunks.py --render 로 뽑은 페이지 이미지(out/pageimg/*.png)를
챌린저 OCR 모델(Replicate 호스팅)에 돌려 텍스트를 받고,
Nemotron(현행) 기준선 텍스트와 함께 out/bakeoff/results.json 에 모은다.

채점은 이후 Claude가 원본 이미지 + 각 출력물을 직접 비교(별도 LLM API 불필요).

준비:
    1) https://replicate.com 가입 → API 토큰 발급
    2) 환경변수: export REPLICATE_API_TOKEN=r8_...
        (PowerShell: $env:REPLICATE_API_TOKEN="r8_...")

실행 (Vector_RAG_Index 루트):
    ./.venv/Scripts/python.exe scripts/ocr_bakeoff/run_ocr_bakeoff.py
    ./.venv/Scripts/python.exe scripts/ocr_bakeoff/run_ocr_bakeoff.py --models deepseek-ocr,dots-ocr

출력:
    out/bakeoff/<image>__<model>.txt   각 모델 원문
    out/bakeoff/results.json           이미지별 {baseline(nemotron), 모델별 출력}
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests  # noqa: E402

from db.connection import get_db_session  # noqa: E402
from models.rdb_models import RagChunk  # noqa: E402

# ============================================================
# 챌린저 모델 정의 (Replicate)
#   slug        : Replicate "owner/name" (최신 버전 자동)
#   image_key   : 이미지 입력 파라미터명 (모델마다 다름)
#   extra       : 추가 입력 (prompt 등)
#   confirmed   : 슬러그 실재 확인 여부 — False 는 실행 전 확인 필요
# 참고: 정확한 슬러그/입력 스키마는 각 모델 Replicate 페이지에서 확인.
# ============================================================
# 2026-07 Replicate OCR 컬렉션에서 실재 확인된 슬러그.
# (dots.ocr / 전용 GLM-OCR 0.9B 는 Replicate 미제공 → 자체 vLLM 필요, 이번 MVP 제외)
# 입력 스키마는 모델마다 달라서 첫 호출에서 400 나면 image_key/extra 를 해당
# 모델 Replicate 페이지 기준으로 수정 (에러 메시지에 스키마 힌트 나옴).
MODELS = {
    "deepseek-ocr": {
        "slug": "lucataco/deepseek-ocr",
        "image_key": "image",
        "extra": {},
        "confirmed": True,
    },
    "dolphin": {  # ByteDance Dolphin — 문서 레이아웃+텍스트 파싱 VLM
        "slug": "bytedance/dolphin",
        "image_key": "image",
        "extra": {},
        "confirmed": True,
    },
    "marker": {  # datalab Marker/Surya — 표·마크다운 구조 보존 강점
        "slug": "datalab-to/marker",
        "image_key": "document",
        "extra": {},
        "confirmed": True,
    },
    "glm-4v": {  # GLM-4V-9B 범용 VLM (프롬프트로 OCR 지시)
        "slug": "cuuupid/glm-4v-9b",
        "image_key": "image",
        "extra": {"prompt": "이 이미지의 모든 텍스트를 표/제목 구조를 유지해 그대로 옮겨써 주세요. 설명 없이 텍스트만."},
        "confirmed": True,
    },
}

REPLICATE_API = "https://api.replicate.com/v1/models/{slug}/predictions"


def _data_uri(png_path: Path) -> str:
    b64 = base64.b64encode(png_path.read_bytes()).decode()
    return f"data:image/png;base64,{b64}"


def _run_replicate(token: str, cfg: dict, png_path: Path, timeout: int = 180) -> str:
    """Replicate 모델 1회 실행 → 출력 텍스트."""
    url = REPLICATE_API.format(slug=cfg["slug"])
    body = {"input": {cfg["image_key"]: _data_uri(png_path), **cfg["extra"]}}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "wait",  # 최대 60s 동기 대기
    }
    r = requests.post(url, json=body, headers=headers, timeout=timeout)
    r.raise_for_status()
    pred = r.json()

    # Prefer: wait 로 끝났으면 output 존재. 아니면 폴링.
    poll_url = pred.get("urls", {}).get("get")
    deadline = time.time() + timeout
    while pred.get("status") not in ("succeeded", "failed", "canceled"):
        if time.time() > deadline:
            raise TimeoutError("Replicate 예측 타임아웃")
        time.sleep(2)
        pred = requests.get(poll_url, headers=headers, timeout=30).json()

    if pred.get("status") != "succeeded":
        raise RuntimeError(f"예측 실패: {pred.get('status')} / {pred.get('error')}")

    out = pred.get("output")
    if isinstance(out, list):
        return "".join(str(x) for x in out)
    return str(out)


def _load_candidates(out_dir: Path) -> dict:
    """candidates.json → {png_basename: {chunk_id, page_start, score}}."""
    cand = json.loads((out_dir / "candidates.json").read_text(encoding="utf-8"))
    mapping = {}
    for c in cand:
        rp = c.get("rendered_png")
        if rp:
            mapping[Path(rp).name] = c
    return mapping


def _baseline_text(session, chunk_id: str) -> str:
    r = session.query(RagChunk).filter(RagChunk.id == chunk_id).first()
    return r.text if r else ""


def main():
    ap = argparse.ArgumentParser(description="OCR 바이크오프 실행기")
    ap.add_argument("--out", type=str, default=str(Path(__file__).parent / "out"))
    ap.add_argument("--models", type=str,
                    default="deepseek-ocr,dolphin,marker,glm-4v",
                    help="쉼표구분. 가능: deepseek-ocr,dolphin,marker,glm-4v")
    ap.add_argument("--limit", type=int, default=0, help="이미지 N장만 (0=전체)")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not token:
        print("❌ REPLICATE_API_TOKEN 환경변수가 없습니다.")
        print("   https://replicate.com 가입 → 토큰 발급 후:")
        print('   PowerShell:  $env:REPLICATE_API_TOKEN="r8_..."')
        sys.exit(1)

    out_dir = Path(args.out)
    img_dir = out_dir / "pageimg"
    bake_dir = out_dir / "bakeoff"
    bake_dir.mkdir(parents=True, exist_ok=True)

    pngs = sorted(img_dir.glob("*.png"))
    if args.limit:
        pngs = pngs[: args.limit]
    if not pngs:
        print(f"❌ 페이지 이미지가 없습니다: {img_dir}")
        print("   먼저: find_bad_ocr_chunks.py --render")
        sys.exit(1)

    model_keys = [m.strip() for m in args.models.split(",") if m.strip()]
    for mk in model_keys:
        if mk not in MODELS:
            print(f"❌ 알 수 없는 모델: {mk} (가능: {', '.join(MODELS)})")
            sys.exit(1)
        if not MODELS[mk]["confirmed"]:
            print(f"⚠️  '{mk}' 슬러그({MODELS[mk]['slug']}) 미확인 — "
                  f"Replicate에서 정확한 owner/name 확인 후 MODELS 수정 필요.")

    cand_map = _load_candidates(out_dir)

    results = {}
    with get_db_session() as session:
        for png in pngs:
            info = cand_map.get(png.name, {})
            chunk_id = info.get("chunk_id")
            baseline = _baseline_text(session, chunk_id) if chunk_id else ""
            entry = {
                "page_start": info.get("page_start"),
                "score": info.get("score"),
                "baseline_nemotron": baseline,
                "models": {},
            }
            print(f"\n=== {png.name} (page {info.get('page_start')}, "
                  f"corruption {info.get('score')}) ===")
            for mk in model_keys:
                cfg = MODELS[mk]
                try:
                    print(f"  → {mk} ({cfg['slug']}) ...", end=" ", flush=True)
                    text = _run_replicate(token, cfg, png)
                    (bake_dir / f"{png.stem}__{mk}.txt").write_text(
                        text, encoding="utf-8")
                    entry["models"][mk] = text
                    print(f"OK ({len(text)}자)")
                except Exception as e:
                    entry["models"][mk] = f"[ERROR] {e}"
                    print(f"실패: {e}")
            results[png.name] = entry

    (bake_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {bake_dir / 'results.json'}")
    print("다음: Claude에게 out/pageimg/ 이미지 + results.json 을 주고 채점 요청.")


if __name__ == "__main__":
    main()
