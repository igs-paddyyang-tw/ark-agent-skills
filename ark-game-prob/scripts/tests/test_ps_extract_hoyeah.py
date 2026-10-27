"""1.5.1：金猴爺／逸修機率表格式（參數分頁叫「參照表」、Pay table 同列右側有 Bet Multiplier 1～10、F 系列 Index|multi|WEIGHT 表）。"""
from __future__ import annotations

import json
import pathlib

import pytest

from test_ps_pipeline import run  # noqa: E402

openpyxl = pytest.importorskip("openpyxl")


def _xlsx(p: pathlib.Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "參照表"
    ws["C4"] = "Pay table"
    for c, v in zip("CDEFG", ["Description", "Symbol", 3, 4, 5]):
        ws[f"{c}5"] = v
    for c, v in zip("IJKLM", ["Bet Multiplier", 1, 2, 3, 4]):     # 同列右側的倍數表（不可混進賠率）
        ws[f"{c}5"] = v
    for r, (sym, o) in enumerate([("M1", (50, 100, 200)), ("A", (5, 10, 20))], start=6):
        ws[f"C{r}"] = "High Pay Symbols" if sym == "M1" else "Low Pay Symbols"
        ws[f"D{r}"] = sym
        ws[f"E{r}"], ws[f"F{r}"], ws[f"G{r}"] = o
    ws["I6"], ws["J6"], ws["K6"], ws["L6"], ws["M6"] = "Max Bet", 75, 150, 225, 300
    ws["C10"], ws["D10"] = "表M-1", "Main Game轉輪帶設定"
    for c, v in zip("CDEFGHIJ", ["Index", "R1", "R2", "R3", "R4", "R5", "Weight", "組合說明"]):
        ws[f"{c}11"] = v
    for i, row in enumerate([[0, 0, 0, 0, 0, 0, 106, "一般"], [1, 1, 1, 2, 3, 3, 21, "5SC"]], start=12):
        for c, v in zip("CDEFGHIJ", row):
            ws[f"{c}{i}"] = v
    ws["C16"], ws["D16"] = "表F-6", "免費遊戲的銀箱獎勵"
    for c, v in zip("CDE", ["Index", "multi", "WEIGHT"]):
        ws[f"{c}17"] = v
    for i, row in enumerate([[0, 150, 500], [1, 300, 285]], start=18):
        for c, v in zip("CDE", row):
            ws[f"{c}{i}"] = v
    wb.save(p)


def test_hoyeah_params_sheet_paytable_and_reelsets(tmp_path):
    x = tmp_path / "金猴爺_測試機.xlsx"
    _xlsx(x)
    r = run("ps_extract.py", "--xlsx", str(x), "--out", str(tmp_path / "prob"), "--slug", "t")
    assert r["success"], r
    K = json.loads((tmp_path / "prob" / "prob-data.json").read_text(encoding="utf-8"))["known"]
    pt = {p["sym"]: p["odds"] for p in K["paytable"]}
    assert pt["M1"] == {"3": 50, "4": 100, "5": 200}, pt          # 不可吃到 Bet Multiplier 欄
    assert pt["A"] == {"3": 5, "4": 10, "5": 20}
    assert K["reelsets"]["block"] == "M-1"                         # F-6（無 R 欄）不可蓋掉 M-1
    assert [s["weight"] for s in K["reelsets"]["sets"]] == [106, 21]
