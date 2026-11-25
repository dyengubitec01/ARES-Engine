"""data/qa/*.json → 통합 xlsx (행=질문). 사람 편집용.

각 JSON 파일이 시트 하나가 됨. 컬럼은 모든 qa 항목의 표준 키 + source_file.
편집 후 tools/excel_to_qa.py 로 다시 JSON으로 변환.

사용:
  python tools/qa_to_excel.py
  python tools/qa_to_excel.py --out data/qa/_editable.xlsx
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

import openpyxl  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402

from pipeline.shared.config import QA_DIR  # noqa: E402


COLUMNS = [
    "id", "category", "subtype", "question", "expected_answer",
    "required_chunks", "answer_must_contain", "answer_must_not_contain",
    "evaluation_notes",
]


def _list_to_cell(v):
    """list → '|' 구분 문자열 (Excel에서 콤마는 헷갈리니까)."""
    if v is None:
        return ""
    if isinstance(v, list):
        return " | ".join(str(x) for x in v)
    return str(v)


def export(qa_dir: str, out_path: str):
    files = sorted(f for f in os.listdir(qa_dir) if f.startswith("golden_qa") and f.endswith(".json"))
    if not files:
        print("qa 파일 없음", file=sys.stderr)
        return

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    for fn in files:
        path = os.path.join(qa_dir, fn)
        data = json.load(open(path, encoding="utf-8"))
        qa_set = data.get("qa_set", [])

        sheet_name = fn.replace("golden_qa", "").replace(".json", "").lstrip("_") or "main"
        ws = wb.create_sheet(sheet_name)

        # meta는 시트 상단에 주석으로
        meta = data.get("meta", {})
        ws.append([f"meta.purpose: {meta.get('purpose', '')}"])
        ws.append([f"meta.note: {meta.get('note', '')}"])
        ws.append([])

        # 헤더
        ws.append(COLUMNS)
        header_row = ws.max_row
        for cell in ws[header_row]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="DDDDDD")
            cell.alignment = Alignment(horizontal="center", wrap_text=True)

        # 행
        for qa in qa_set:
            row = [_list_to_cell(qa.get(c, "")) for c in COLUMNS]
            ws.append(row)

        # 폭/줄바꿈
        widths = {"id": 5, "category": 18, "subtype": 22, "question": 40, "expected_answer": 50,
                  "required_chunks": 14, "answer_must_contain": 22, "answer_must_not_contain": 22,
                  "evaluation_notes": 35}
        for i, c in enumerate(COLUMNS, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = widths.get(c, 14)
        for r in range(header_row + 1, ws.max_row + 1):
            for cell in ws[r]:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

    wb.save(out_path)
    print(f"[qa→xlsx] 저장: {out_path}  (시트 {len(files)}개)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--qa-dir", default=QA_DIR)
    p.add_argument("--out", default=os.path.join(QA_DIR, "_editable.xlsx"))
    args = p.parse_args()
    export(args.qa_dir, args.out)


if __name__ == "__main__":
    main()
