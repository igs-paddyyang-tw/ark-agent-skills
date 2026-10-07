"""verify_xlsx_formulas — xlsx 活公式真值驗證（純 python，免 soffice）。

openpyxl 不算公式；本工具用 `formulas` 引擎實際重算每一格，掃出
#REF!/#VALUE!/#DIV/0!/#NAME?/#NULL!/#NUM! 等錯誤，證明「活公式真的算得出」。

用法：
    python verify_xlsx_formulas.py <xlsx 檔或目錄> [--json]
    # 目錄 → 遞迴驗所有 *.xlsx

退出碼：0 全通過；3 有公式錯誤（GATE_BLOCKED）；8 缺 formulas。

> 這是 soffice 之外的輕量替代（`uv pip install formulas`）。formulas 足以抓
> #REF!/門檻引錯格等真錯誤；要驗「機率同仁實際 Excel 相容性」才需 LibreOffice。
"""
from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys
import warnings

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ps_common as C  # noqa: E402

ERR_TOKENS = ("#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#NULL!", "#NUM!", "#N/A")


def recalc(xlsx_path: pathlib.Path) -> dict:
    """載入並真算一本 xlsx，回 {path, formulas, cells, errors:[{cell,value}]}。"""
    warnings.filterwarnings("ignore")
    logging.disable(logging.CRITICAL)
    import formulas  # 延遲 import，缺則由 main 回 MISSING_DEP
    import openpyxl

    wb = openpyxl.load_workbook(xlsx_path)
    n_formula = sum(
        1 for ws in wb.worksheets for row in ws.iter_rows()
        for c in row if isinstance(c.value, str) and c.value.startswith("=")
    )
    xl = formulas.ExcelModel().loads(str(xlsx_path)).finish()
    sol = xl.calculate()
    errors = []
    for k, v in sol.items():
        try:
            val = v.value[0, 0] if hasattr(v, "value") else v
        except Exception:
            val = str(v)
        s = str(val)
        if any(t in s for t in ERR_TOKENS):
            errors.append({"cell": str(k), "value": s})
    return {
        "path": str(xlsx_path),
        "formulas": n_formula,
        "cells": len(sol),
        "errors": errors,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="xlsx 活公式真值驗證（formulas 引擎重算）")
    ap.add_argument("target", help="xlsx 檔或目錄")
    ap.add_argument("--json", action="store_true", help="輸出機器可讀 JSON")
    if "--help" in sys.argv or "-h" in sys.argv:
        ap.parse_args()
        return
    a = ap.parse_args()

    try:
        import formulas  # noqa: F401
    except ImportError:
        C.fail("MISSING_DEP", "缺 formulas 套件",
               "uv pip install formulas（純 python，免 sudo/soffice）")

    t = pathlib.Path(a.target)
    if t.is_dir():
        targets = sorted(t.rglob("*.xlsx"))
    elif t.is_file():
        targets = [t]
    else:
        C.fail("BAD_INPUT", f"找不到：{t}", "給 xlsx 檔或目錄")

    if not targets:
        C.fail("BAD_INPUT", f"{t} 底下無 *.xlsx", "確認路徑")

    reports = [recalc(x) for x in targets]
    total_err = sum(len(r["errors"]) for r in reports)
    total_formula = sum(r["formulas"] for r in reports)
    verdict = "OK" if total_err == 0 else "X"
    deliver = (
        f"驗 {len(reports)} 本 xlsx｜活公式 {total_formula}｜"
        f"{'✅ 0 公式錯誤' if total_err == 0 else f'🔴 {total_err} 個公式錯誤'}"
    )
    data = {"verdict": verdict, "files": reports,
            "total_errors": total_err, "total_formulas": total_formula,
            "delivery": deliver}
    if total_err:
        C.fail("GATE_BLOCKED", deliver, "見 errors 清單，修公式引用/範圍後重跑", data)
    C.emit(data, {"stage": "verify_xlsx"})


if __name__ == "__main__":
    main()
