"""
LangFuse 프롬프트 검증 + fallback JSON 생성 스크립트.

Story 3.4 AC 3.4.6, AC 3.4.7

용도:
  - CI/CD: Jenkins 배포 시 프롬프트 변수 검증 + fallback JSON 생성
  - 수동: LangFuse에 프롬프트 등록 후 검증

사용법:
  uv run python scripts/validate_prompts.py                    # 검증만
  uv run python scripts/validate_prompts.py --generate-fallback # 검증 + fallback JSON 생성
  uv run python scripts/validate_prompts.py --label dev         # dev 라벨 대상
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

FALLBACK_DIR = PROJECT_ROOT / "prompts" / "fallback"


def load_prompt_config(config_path: Path | None = None) -> dict:
    """prompts.yaml 로드."""
    if config_path is None:
        config_path = PROJECT_ROOT / "config" / "prompts.yaml"

    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_and_generate(label: str, generate_fallback: bool) -> bool:
    """LangFuse 프롬프트를 검증하고 선택적으로 fallback JSON을 생성한다.

    Returns:
        True if all prompts pass validation, False otherwise.
    """
    from langfuse import Langfuse

    config = load_prompt_config()
    prompts = config.get("prompts", {})
    langfuse = Langfuse()

    all_ok = True
    results = []

    for name, spec in prompts.items():
        expected_vars = set(spec.get("variables", []))
        prompt_type = spec.get("type", "chat")

        try:
            lf_prompt = langfuse.get_prompt(name, label=label, type=prompt_type)

            if lf_prompt.is_fallback:
                results.append((name, "NOT_FOUND", f"No '{label}' label found"))
                all_ok = False
                continue

            # 변수 검증
            # LangFuse chat 프롬프트의 변수 추출
            actual_vars = set()
            if hasattr(lf_prompt, "prompt"):
                # chat 타입: prompt는 메시지 리스트
                import re

                for msg in lf_prompt.prompt:
                    content = msg.get("content", "")
                    actual_vars.update(re.findall(r"\{\{(\w+)\}\}", content))

            if actual_vars != expected_vars:
                results.append(
                    (
                        name,
                        "VAR_MISMATCH",
                        f"expected {sorted(expected_vars)}, got {sorted(actual_vars)}",
                    )
                )
                all_ok = False
                continue

            results.append((name, "OK", f"v{lf_prompt.version}"))

            # fallback JSON 생성
            if generate_fallback and hasattr(lf_prompt, "prompt"):
                FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
                fallback_path = FALLBACK_DIR / f"{name}.json"
                fallback_data = {"messages": lf_prompt.prompt}
                with open(fallback_path, "w", encoding="utf-8") as f:
                    json.dump(fallback_data, f, ensure_ascii=False, indent=2)
                print(f"  -> fallback saved: {fallback_path}")

        except Exception as e:
            results.append((name, "ERROR", str(e)))
            all_ok = False

    # 결과 출력
    print(f"\n{'='*60}")
    print(f"LangFuse Prompt Validation (label: {label})")
    print(f"{'='*60}")

    for name, status, detail in results:
        icon = "OK" if status == "OK" else "FAIL"
        print(f"  {icon} {name}: [{status}] {detail}")

    print(f"{'='*60}")
    if all_ok:
        print("All prompts validated successfully.")
    else:
        print("VALIDATION FAILED — see errors above.")

    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate LangFuse prompts")
    parser.add_argument(
        "--label",
        default="production",
        help="LangFuse label to validate (default: production)",
    )
    parser.add_argument(
        "--generate-fallback",
        action="store_true",
        help="Generate fallback JSON files from validated prompts",
    )
    args = parser.parse_args()

    ok = validate_and_generate(
        label=args.label,
        generate_fallback=args.generate_fallback,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
