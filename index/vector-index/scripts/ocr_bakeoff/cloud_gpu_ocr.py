"""클라우드 GPU 박스에서 실행하는 자립형 OCR 추론 (바이크오프 챌린저).

이 스크립트는 우리 파이프라인 코드에 의존하지 않는다 — 그냥 GPU 박스에
transformers/torch 만 있으면 이미지 1장을 OCR 해서 텍스트를 출력한다.

사용 (GPU 박스에서):
    # 1) GLM-OCR (0.9B, VRAM ~3GB, 제일 쉬움 — 먼저 이걸로)
    pip install "git+https://github.com/huggingface/transformers.git" torch pillow accelerate
    python cloud_gpu_ocr.py --model glm-ocr --image page.png

    # 2) DeepSeek-OCR (~3B, flash-attn 필요, VRAM ~8GB+)
    pip install torch==2.6.0 transformers==4.46.3 tokenizers==0.20.3 flash-attn==2.7.3
    python cloud_gpu_ocr.py --model deepseek-ocr --image page.png

출력:
    <image>.<model>.txt 로 저장 + stdout 출력.
    이 텍스트를 로컬로 가져와 Claude에게 채점 요청.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def run_glm_ocr(image_path: str) -> str:
    """GLM-OCR (zai-org/GLM-OCR, 0.9B). transformers 최신 필요."""
    from transformers import AutoProcessor, AutoModelForImageTextToText

    model_path = "zai-org/GLM-OCR"
    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "url": image_path},
            {"type": "text", "text": "Text Recognition:"},
        ],
    }]
    processor = AutoProcessor.from_pretrained(model_path)
    model = AutoModelForImageTextToText.from_pretrained(
        model_path, torch_dtype="auto", device_map="auto",
    )
    inputs = processor.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True,
        return_dict=True, return_tensors="pt",
    ).to(model.device)
    inputs.pop("token_type_ids", None)
    gen = model.generate(**inputs, max_new_tokens=8192)
    text = processor.decode(
        gen[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True,
    )
    return text


def run_deepseek_ocr(image_path: str) -> str:
    """DeepSeek-OCR (deepseek-ai/DeepSeek-OCR, ~3B). flash-attn 필요."""
    import os
    import torch
    from transformers import AutoModel, AutoTokenizer

    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
    model_name = "deepseek-ai/DeepSeek-OCR"
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModel.from_pretrained(
        model_name, _attn_implementation="flash_attention_2",
        trust_remote_code=True, use_safetensors=True,
    )
    model = model.eval().cuda().to(torch.bfloat16)

    out_dir = Path(image_path).parent / "ds_out"
    out_dir.mkdir(exist_ok=True)
    # infer 는 결과를 파일로도 저장하지만, 반환/캡처를 위해 텍스트도 받는다.
    res = model.infer(
        tokenizer, prompt="<image>\nFree OCR. ", image_file=image_path,
        output_path=str(out_dir), base_size=1024, image_size=640,
        crop_mode=True, save_results=True, test_compress=True,
    )
    # 일부 버전은 텍스트 반환, 일부는 out_dir 에 result.mmd 저장
    if isinstance(res, str) and res.strip():
        return res
    mmd = list(out_dir.glob("*.mmd")) + list(out_dir.glob("*.txt"))
    if mmd:
        return mmd[0].read_text(encoding="utf-8")
    return str(res)


RUNNERS = {"glm-ocr": run_glm_ocr, "deepseek-ocr": run_deepseek_ocr}


def main():
    ap = argparse.ArgumentParser(description="클라우드 GPU OCR 챌린저")
    ap.add_argument("--model", required=True, choices=list(RUNNERS))
    ap.add_argument("--image", required=True, help="OCR 할 이미지 경로")
    args = ap.parse_args()

    print(f"[{args.model}] {args.image} 추론 중 ...")
    text = RUNNERS[args.model](args.image)

    out_txt = Path(args.image).with_suffix(f".{args.model}.txt")
    out_txt.write_text(text, encoding="utf-8")
    print(f"\n===== {args.model} 출력 =====\n{text}\n")
    print(f"저장: {out_txt}")


if __name__ == "__main__":
    main()
