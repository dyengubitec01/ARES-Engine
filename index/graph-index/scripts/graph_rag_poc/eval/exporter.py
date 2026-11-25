"""실험 결과 → Excel 비교표.

입력:
  results/<exp>/q01.json ~ qNN.json    (질문별 결과, score 포함)
  results/<exp>/rescore_summary.json   (있으면 judge 점수 합쳐서 표기)

출력:
  results/<exp>/summary.xlsx

시트:
  - 요약: 카테고리 × 트랙(judge/recall/calls/out_tok) 매트릭스 + 전체 평균
  - 질문별: 행=질문, 열=각 트랙의 judge·recall·답변 일부 (사람 검토용)
"""
import argparse
import json
import os
import sys
from collections import defaultdict

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill


CATS = ["control", "distributed_integration", "sensemaking", "relation_reasoning",
        "multilayer_classification", "fanout_relation", "hallucination_trap"]
SHORT = {
    "control": "control", "distributed_integration": "분산", "sensemaking": "sense",
    "relation_reasoning": "관계", "multilayer_classification": "다층",
    "fanout_relation": "fanout", "hallucination_trap": "환각",
}


def _safe_mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _load_results(results_dir: str):
    """q*.json 전체 + (있으면) rescore_summary.json의 judge 합본."""
    qfiles = sorted(f for f in os.listdir(results_dir)
                    if f.startswith("q") and f.endswith(".json"))
    data = [json.load(open(os.path.join(results_dir, f), encoding="utf-8")) for f in qfiles]

    # judge map (있으면)
    rescore = os.path.join(results_dir, "rescore_summary.json")
    judge_map = {}
    if os.path.exists(rescore):
        for r in json.load(open(rescore, encoding="utf-8")):
            for t, sc in r.get("tracks", {}).items():
                if sc.get("judge") is not None:
                    judge_map[(r["id"], t)] = sc["judge"]
    return data, judge_map


def _aggregate(data, judge_map):
    """카테고리별·트랙별 평균 통계."""
    tracks = list(data[0]["results"].keys())
    by_cat = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for q in data:
        cat = q["category"]
        for t in tracks:
            res = q["results"].get(t, {})
            by_cat[cat][t]["judge"].append(judge_map.get((q["id"], t)))
            by_cat[cat][t]["recall"].append(res.get("score", {}).get("chunk_recall"))
            by_cat[cat][t]["calls"].append(res.get("llm_calls", 0))
            by_cat[cat][t]["out_tok"].append(res.get("usage", {}).get("completion_tokens", 0))
    return tracks, by_cat


def _write_summary_sheet(ws, data, judge_map, tracks, by_cat):
    """카테고리 × 트랙 매트릭스."""
    headers = ["카테고리", "n"]
    for t in tracks:
        headers += [f"{t}\njudge", f"{t}\nrecall", f"{t}\ncalls", f"{t}\nout_tok"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDDDDD")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 32

    # 카테고리 행
    for cat in CATS:
        if cat not in by_cat:
            continue
        n = len(next(iter(by_cat[cat].values()))["calls"])
        row = [SHORT[cat], n]
        for t in tracks:
            s = by_cat[cat][t]
            jm = _safe_mean(s["judge"])
            rm = _safe_mean(s["recall"])
            cm = _safe_mean(s["calls"])
            om = _safe_mean(s["out_tok"])
            row += [
                round(jm, 3) if jm is not None else "",
                round(rm, 3) if rm is not None else "",
                round(cm, 1) if cm is not None else "",
                int(om) if om is not None else "",
            ]
        ws.append(row)

    # 전체 평균
    ws.append([])
    total = ["전체", len(data)]
    for t in tracks:
        all_j = [judge_map.get((q["id"], t)) for q in data]
        all_r = [q["results"].get(t, {}).get("score", {}).get("chunk_recall") for q in data]
        all_c = [q["results"].get(t, {}).get("llm_calls", 0) for q in data]
        all_o = [q["results"].get(t, {}).get("usage", {}).get("completion_tokens", 0) for q in data]
        jm = _safe_mean(all_j); rm = _safe_mean(all_r); cm = _safe_mean(all_c); om = _safe_mean(all_o)
        total += [
            round(jm, 3) if jm is not None else "",
            round(rm, 3) if rm is not None else "",
            round(cm, 1) if cm is not None else "",
            int(om) if om is not None else "",
        ]
    ws.append(total)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="FFF2CC")

    # 컬럼 폭
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 5
    for col_idx in range(3, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 11


def _write_per_q_sheet(ws, data, judge_map, tracks):
    """질문별 상세: 행=질문, 열=각 트랙의 judge·recall·답변 200자."""
    headers = ["id", "category", "question", "expected_answer"]
    for t in tracks:
        headers += [f"{t}\njudge", f"{t}\nanswer"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDDDDD")
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    ws.row_dimensions[1].height = 32

    for q in data:
        row = [q["id"], SHORT.get(q["category"], q["category"]),
               q["question"], q.get("expected_answer", "")]
        for t in tracks:
            j = judge_map.get((q["id"], t))
            ans = q["results"].get(t, {}).get("answer", "")
            row += [round(j, 3) if j is not None else "", ans]
        ws.append(row)

    # 컬럼 폭/줄바꿈
    widths = [4, 8, 40, 40] + [9, 50] * len(tracks)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    for row_idx in range(2, ws.max_row + 1):
        for cell in ws[row_idx]:
            cell.alignment = Alignment(wrap_text=True, vertical="top")


def export(results_dir: str, out_xlsx: str = None):
    data, judge_map = _load_results(results_dir)
    if not data:
        print("q*.json 없음", file=sys.stderr)
        return None
    tracks, by_cat = _aggregate(data, judge_map)

    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "요약"
    _write_summary_sheet(ws1, data, judge_map, tracks, by_cat)

    ws2 = wb.create_sheet("질문별")
    _write_per_q_sheet(ws2, data, judge_map, tracks)

    out = out_xlsx or os.path.join(results_dir, "summary.xlsx")
    wb.save(out)
    print(f"[exporter] 저장: {out}  ({len(data)}문 × {len(tracks)}트랙)")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dir", help="results 디렉터리")
    p.add_argument("--out", help="출력 xlsx (기본: <dir>/summary.xlsx)")
    args = p.parse_args()
    export(args.dir, args.out)


if __name__ == "__main__":
    main()
