"""ps_html 通用表：並排子表切分、旁註欄、超長格摺疊（金猴驗證 F-1b：表 F-4 攤平成 17 欄跑版）。"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import ps_html as H  # noqa: E402

GO = " {39, 56, 55, 55, 55, 55, 60, 65, 65, 69, 81, 60, 50, 40, 30, 30, 20, 15, 10, 10, 5, 54, 18, 3},"


def rows(*cells_list):
    return [{"r": i, "cells": list(c)} for i, c in enumerate(cells_list, 1)]


def test_side_by_side_subtables_with_caption_and_note_column():
    """F-4 版型：說明列 → caption；表頭首格 NORMAL 重出現 → 左右兩表；空欄後的 Go 陣列欄 → 旁註表。"""
    t = rows([None, "(最終珠子上分數要乘上LineBet)", "暫定基準", None, None, "暫定基準", None, None],
             ["NORMAL", "包子分數", "綠", "NORMAL", "辣椒分數", "紫", None, None],
             [None, 15, 39, None, 15, 35, None, GO],
             [None, 20, 56, None, 20, 70, None, None])
    s = H.split_generic(t, c0=2)
    assert [x["head"] for x in s] == [["NORMAL", "包子分數", "綠"], ["NORMAL", "辣椒分數", "紫"], [""]]
    assert s[0]["captions"] == ["(最終珠子上分數要乘上LineBet)", "暫定基準"] and s[1]["captions"] == ["暫定基準"]
    assert s[2]["captions"] == ["xlsx I 欄旁註"] and len(s[2]["rows"]) == 1      # c0=2(B) + 第 7 欄 → I；空列略過
    assert s[0]["rows"] == [[None, 15, 39], [None, 20, 56]]


def test_blank_top_left_header_not_split():
    """左上角空白（列標籤欄）的表：首格是「綠」且不重複 → 不切（保底表回歸）。"""
    t = rows([None, "綠", "紅", "紫"], [1, 20, 30, 30], [2, 20, 30, 30])
    s = H.split_generic(t)
    assert len(s) == 1 and s[0]["head"] == ["", "綠", "紅", "紫"] and len(s[0]["rows"]) == 2


def test_headless_table_kept_whole():
    """無表頭（如合計列）不依空欄切，維持原表一張。"""
    t = rows([None, 10, 20, None, None, 30])
    s = H.split_generic(t)
    assert len(s) == 1 and s[0]["head"] == [""] * 6


def test_long_cell_folded():
    assert H.cell(None) == "" and H.cell(15) == "15" and H.cell("短字") == "短字"
    folded = H.cell(GO)
    assert folded.startswith('<details class="cell-fold"><summary>陣列 24 項</summary>') and "69, 81" in folded
    assert "<summary>" in H.cell("說" * 50) and H.cell("<b>" * 20).count("<b>") == 0      # 摺疊時仍跳脫
