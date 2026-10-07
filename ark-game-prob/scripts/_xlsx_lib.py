"""_xlsx_lib — ark-game-prob Excel 共用庫（樣式／版面／活公式／檢核／戳記）。

黃金律（吸收自 game-prob-table-excel）：
- 零手抄：所有值從 canonical JSON dump，不貼結果。
- 派生＝活公式：Σ / COUNTIF / VLOOKUP / 偏差 / 檢核都是公式。
- 輸入(淡藍) / 公式(灰) / 參考(白) 三色分區。
- 每頁一個總閘；門檻放格子不寫死；_meta 戳記驗 STALE。
- openpyxl 不算公式 → 公式字串以 '=' 開頭；文字型 '=' 開頭強制字串避免被當公式。

本庫只做 openpyxl 繪製與 map 讀取；envelope/sha/yaml 重用 ps_common。
"""
from __future__ import annotations

import hashlib
import pathlib

import ps_common as C

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_MAP = C.SKILL_DIR / "references" / "config-map.fasttest.yaml"


def _openpyxl():
    """集中 import 與缺依賴處置。"""
    try:
        import openpyxl  # noqa: F401
        from openpyxl.styles import Alignment, Font, PatternFill  # noqa: F401
        from openpyxl.utils import get_column_letter  # noqa: F401
    except ImportError:
        C.fail("MISSING_DEP", "需要 openpyxl", "pip install openpyxl")
    return openpyxl


# ── 樣式主題（單一真相來源，取代散落的 Font/Fill 定義）──
def theme() -> dict:
    from openpyxl.styles import Alignment, Font, PatternFill
    return {
        "H": Font(bold=True, color="FFFFFF"),              # 表頭字（白）
        "HF": PatternFill("solid", fgColor="5B4636"),      # 表頭底（深棕）
        "TF": Font(bold=True),                             # 標題/總和粗體
        "PF": PatternFill("solid", fgColor="FFE699"),      # 待決議黃底
        "IN": PatternFill("solid", fgColor="DDEBF7"),      # 輸入格淡藍（人可改）
        "FM": PatternFill("solid", fgColor="F2F2F2"),      # 公式格灰（鎖定）
        "SRC": Font(color="7F7F7F", italic=True),          # 來源灰斜體
        "OK": PatternFill("solid", fgColor="C6EFCE"),      # OK 綠
        "WARN": PatternFill("solid", fgColor="FFEB9C"),    # ! 黃
        "BAD": PatternFill("solid", fgColor="FFC7CE"),     # X 紅
        "CENTER": Alignment(horizontal="center", vertical="center"),
    }


def new_workbook():
    op = _openpyxl()
    return op.Workbook()


def colL(c: int) -> str:
    from openpyxl.utils import get_column_letter
    return get_column_letter(c)


def set_widths(ws, widths: dict) -> None:
    """widths: {'A': 18, 'B': 12, ...}。"""
    for k, v in widths.items():
        ws.column_dimensions[k].width = v


# ── 版面：表頭 + 資料塊 ──
def block_table(ws, r: int, c: int, header: list, rows: list, *, th=None, pending="待決議") -> tuple:
    """畫一塊表：表頭(H/HF/置中) + 逐列值。None 值 → 待決議黃底。
    回傳 (end_row, n_pending)。
    """
    th = th or theme()
    n_pending = 0
    for j, h in enumerate(header):
        cell = ws.cell(r, c + j, h)
        cell.font = th["H"]; cell.fill = th["HF"]; cell.alignment = th["CENTER"]
    rr = r + 1
    for row in rows:
        for j, v in enumerate(row):
            _, is_p = gate_cell(ws, rr, c + j, v, th=th, pending=pending)
            n_pending += int(is_p)
        rr += 1
    return rr - 1, n_pending


def gate_cell(ws, r: int, c: int, v, *, src=None, th=None, pending="待決議") -> tuple:
    """寫單格。v is None → pending + 黃底（回 is_pending=True）。src 不為 None → 右一格灰斜體來源。
    文字型以 '=' 開頭 → 強制字串（避免被當公式）。回傳 (cell, is_pending)。
    """
    th = th or theme()
    is_pending = v is None
    if is_pending:
        cell = ws.cell(r, c, pending); cell.fill = th["PF"]
    else:
        cell = ws.cell(r, c, v)
        if isinstance(v, str) and v.startswith("=") and not _is_formula(v):
            cell.data_type = "s"
    if src is not None:
        s = ws.cell(r, c + 1, str(src)); s.font = th["SRC"]
    return cell, is_pending


def _is_formula(v: str) -> bool:
    """以 '=' 開頭且後接函式名/參照樣式才算公式；'=待決議' 這種不是。"""
    import re
    return bool(re.match(r"^=\s*[A-Z(]|^=[A-Za-z]+\$?\d|^=\$?[A-Z]+\$?\d", v))


# ── 活公式 ──
def sigma_row(ws, r: int, c: int, first_row: int, last_row: int, *, th=None, label=None) -> None:
    """在 (r,c) 寫 =SUM(col{first}:col{last})，粗體。label 寫在左一格。"""
    th = th or theme()
    cl = colL(c)
    if label is not None:
        lc = ws.cell(r, c - 1, label); lc.font = th["TF"]
    cell = ws.cell(r, c, f"=SUM({cl}{first_row}:{cl}{last_row})"); cell.font = th["TF"]


def symbol_cf(ws, r: int, c: int, data_col: str, first: int, last: int, match_cell: str) -> None:
    """寫 =COUNTIF(data_col$first:data_col$last, match_cell) 活公式。"""
    ws.cell(r, c, f"=COUNTIF({data_col}${first}:{data_col}${last},{match_cell})")


def check_column(ws, r: int, first: int, last: int, cols: list, *, th=None, label="Total") -> None:
    """資料區底部補一列多欄 SUM 檢查。"""
    th = th or theme()
    if cols:
        lc = ws.cell(r, cols[0] - 1, label); lc.font = th["TF"]
    for c in cols:
        cl = colL(c)
        cell = ws.cell(r, c, f"=SUM({cl}{first}:{cl}{last})"); cell.font = th["TF"]


def strip_group(ws, r0: int, group_name: str, reels: list, *, th=None) -> int:
    """畫單一輪帶組：Reels_g 標題 + R1..Rn 符號縱排 + 右側每符號顆數 COUNTIF + Total SUM。
    reels: list[list[symbol_code]]。回傳下一個 r0。
    """
    th = th or theme()
    tc = ws.cell(r0, 1, group_name); tc.font = th["TF"]
    ncol = len(reels)
    maxlen = max((len(r) for r in reels), default=0)
    for ci in range(ncol):
        hc = ws.cell(r0 + 1, 2 + ci, f"R{ci + 1}"); hc.font = th["H"]; hc.fill = th["HF"]
    first = r0 + 2
    for ri in range(maxlen):
        for ci in range(ncol):
            if ri < len(reels[ci]):
                ws.cell(first + ri, 2 + ci, reels[ci][ri])
    last = first + maxlen - 1
    # 總顆數列
    tot = ws.cell(last + 1, 1, "總顆數"); tot.font = th["TF"]
    for ci in range(ncol):
        cl = colL(2 + ci)
        c = ws.cell(last + 1, 2 + ci, f"=COUNTA({cl}{first}:{cl}{last})"); c.font = th["TF"]
    return last + 3


def transpose_block(ws, r: int, c: int, matrix: list, *, headers=None, th=None) -> int:
    """把 list-of-rows 以列↔欄互換寫入。回傳結束列。"""
    th = th or theme()
    if headers:
        for j, h in enumerate(headers):
            cell = ws.cell(r, c + j, h); cell.font = th["H"]; cell.fill = th["HF"]
        r += 1
    # 轉置
    if matrix:
        ncol = max(len(row) for row in matrix)
        for i in range(ncol):
            for j, row in enumerate(matrix):
                ws.cell(r + i, c + j, row[i] if i < len(row) else None)
        return r + ncol - 1
    return r


def check_rows(ws, r: int, c: int, rows: list, *, th=None) -> tuple:
    """檢核表：每列 [輸入..., 判定公式]，判定格依 X/!/OK 條件上色（用條件格式 or 直接判字首）。
    rows: list[list]，最後一欄為判定公式字串（=IF(...)）。回傳 (end_row, n_bad, n_warn)。
    這裡只落公式；X/!/OK 著色靠 add_verdict_cf（LibreOffice/Excel 開啟時生效）。
    """
    th = th or theme()
    rr = r
    for row in rows:
        for j, v in enumerate(row):
            gate_cell(ws, rr, c + j, v, th=th)
        rr += 1
    return rr - 1, 0, 0


def add_verdict_cf(ws, cell_range: str, *, th=None) -> None:
    """對判定欄加條件格式：含 'X' 紅、'!' 黃、'OK' 綠。"""
    from openpyxl.formatting.rule import CellIsRule, FormulaRule
    th = th or theme()
    # 用 FormulaRule 判字首（LEFT）
    ws.conditional_formatting.add(cell_range,
        FormulaRule(formula=[f'LEFT({cell_range.split(":")[0]},1)="X"'], fill=th["BAD"]))
    ws.conditional_formatting.add(cell_range,
        FormulaRule(formula=[f'LEFT({cell_range.split(":")[0]},1)="!"'], fill=th["WARN"]))
    ws.conditional_formatting.add(cell_range,
        FormulaRule(formula=[f'LEFT({cell_range.split(":")[0]},2)="OK"'], fill=th["OK"]))


def gate_summary(ws, r: int, c: int, n_bad: int, n_warn: int, *, th=None) -> str:
    """每頁總閘：X 不可交付 / ! 需簽核 / OK 全部通過。回傳 verdict 字串。"""
    th = th or theme()
    if n_bad:
        txt = f"X 不可交付：{n_bad} 項"; fill = th["BAD"]
    elif n_warn:
        txt = f"! 需簽核：{n_warn} 項"; fill = th["WARN"]
    else:
        txt = "OK 全部通過"; fill = th["OK"]
    cell = ws.cell(r, c, txt); cell.font = th["TF"]; cell.fill = fill
    return txt


# ── _meta 戳記 ──
def _sha16_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]


def stamp_meta(wb, rows: list, *, sheet="_meta") -> None:
    """隱藏 _meta 頁，逐列寫戳記。rows: list[(label, value, sha16)]。"""
    ws = wb.create_sheet(sheet)
    ws.sheet_state = "hidden"
    for i, row in enumerate(rows, 1):
        for j, v in enumerate(row, 1):
            ws.cell(i, j, v)


def meta_rows(sources: dict, *, generated_by="ark-game-prob/ps_xlsx") -> list:
    """sources: {label: Path}。回傳 [(label, path, sha16), ..., ('generated_by', generated_by, '')]。"""
    import datetime
    rows = []
    for label, p in sources.items():
        p = pathlib.Path(p)
        sha = C.sha16(p) if p.exists() else "MISSING"
        rows.append((f"content-src:{label}", p.as_posix(), sha))
    rows.append(("generated_by", generated_by, ""))
    rows.append(("generated_at", datetime.datetime.now().isoformat(timespec="seconds"), ""))
    return rows


# ── map 讀取（與 ps_diff 共用同一份）──
def load_map(path=None) -> list:
    """讀 config-map 的 rules。預設 references/config-map.fasttest.yaml。"""
    p = pathlib.Path(path) if path else DEFAULT_MAP
    if not p.exists():
        C.fail("BAD_INPUT", f"找不到 map：{p}", "指定 --map 或確認 references/config-map.fasttest.yaml")
    return C.yaml_load(p).get("rules") or []


# ── xlsx 原子存檔（補 ps_common.atomic_write 只收 text 的缺口）──
def save_atomic(wb, path: pathlib.Path) -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    wb.save(tmp)
    tmp.replace(path)
