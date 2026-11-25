"""편집된 xlsx → data/qa/*.json (원본 시트 → 원본 파일 1:1 갱신).

qa_to_excel.py의 역변환. 시트 이름이 'main' → golden_qa.json, 'fanout' → golden_qa_fanout.json 등.

사용:
  python tools/excel_to_qa.py
  python tools/excel_to_qa.py --xlsx data/qa/_editable.xlsx --dry-run
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

import openpyxl  # noqa: E402

from pipeline.shared.config import QA_DIR  # noqa: E402


COLUMNS = [
    "id", "category", "subtype", "question", "expected_answer",
    "required_chunks", "answer_must_contain", "answer_must_not_contain",
    "evaluation_notes",
]

# 시트 이름 → 원본 파일 매핑
SHEET_TO_FILE = {
    "main": "golden_qa.json",
    "fanout": "golden_qa_fanout.json",
    "halluc": "golden_qa_halluc.json",
}


def _parse_list(s, as_int=False):
    """'a | b | c' → [a, b, c]. 빈 문자열 → []."""
    if not s:
        return []
    parts = [p.strip() for p in str(s).split("|") if p.strip()]
    if as_int:
        return [int(p) for p in parts]
    return parts


def _row_to_qa(row_values):
    """헤더 위치 기준 dict 만들기 + list 필드 파싱."""
    qa = {}
    for i, col in enumerate(COLUMNS):
        v = row_values[i] if i < len(row_values) else None
        if col == "id":
            qa["id"] = int(v) if v not in (None, "") else None
        elif col == "required_chunks":
            qa["required_chunks"] = _parse_list(v, as_int=True)
        elif col in ("answer_must_contain", "answer_must_not_contain"):
            qa[col] = _parse_list(v)
        else:
            qa[col] = v if v is not None else ""
    return qa


def import_xlsx(xlsx_path: str, qa_dir: str, dry_run: bool = False):
    wb = openpyxl.load_workbook(xlsx_path)
    for sheet_name in wb.sheetnames:
        if sheet_name not in SHEET_TO_FILE:
            print(f"[skip] 알 수 없는 시트: {sheet_name}", file=sys.stderr)
            continue
        target_file = os.path.join(qa_dir, SHEET_TO_FILE[sheet_name])
        ws = wb[sheet_name]

        # 헤더 위치 찾기 (id로 시작하는 행)
        header_row = None
        for r in range(1, ws.max_row + 1):
            if ws.cell(r, 1).value == "id":
                header_row = r
                break
        if header_row is None:
            print(f"[skip] {sheet_name}: 헤더 행 못 찾음", file=sys.stderr)
            continue

        # 데이터 행 파싱
        qa_set = []
        for r in range(header_row + 1, ws.max_row + 1):
            row_values = [ws.cell(r, c + 1).value for c in range(len(COLUMNS))]
            if row_values[0] is None:  # id 비면 종료
                continue
            qa_set.append(_row_to_qa(row_values))

        # 기존 meta 유지 (편집 안 한 부분)
        meta = {}
        if os.path.exists(target_file):
            try:
                existing = json.load(open(target_file, encoding="utf-8"))
                meta = existing.get("meta", {})
                meta["total_questions"] = len(qa_set)
            except Exception:
                pass

        out = {"meta": meta, "qa_set": qa_set}
        print(f"[{sheet_name}] {len(qa_set)}문 → {target_file}{' (dry-run)' if dry_run else ''}")
        if not dry_run:
            json.dump(out, open(target_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--xlsx", default=os.path.join(QA_DIR, "_editable.xlsx"))
    p.add_argument("--qa-dir", default=QA_DIR)
    p.add_argument("--dry-run", action="store_true", help="파일 안 쓰고 미리보기만")
    args = p.parse_args()
    if not os.path.exists(args.xlsx):
        print(f"엑셀 파일 없음: {args.xlsx}", file=sys.stderr)
        sys.exit(1)
    import_xlsx(args.xlsx, args.qa_dir, args.dry_run)


if __name__ == "__main__":
    main()
