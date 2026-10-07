"""ps_config_load — 讀 ProbSetting 設定檔 JSON，依 config-map 規則取值並分類。

與 ps_diff 共用同一份 config-map（references/config-map.fasttest.yaml）：
- 用 rule.config 路徑從 JSON 取值（get_path，重用 ps_diff 語意）
- 依 rule.xlsx 選擇器的表號前綴推 phase（M/F/J/A/G），或吃 rule.phase（若 map 已補）
- label 吃 rule.label（若有）否則用 note / id
- tier_axis 吃 rule.tier_axis（供 xlsx 分層著色）

分類（依 Go 形狀 + 角色）：
  scalar  純量（Bet_Cost / 門檻）
  weights 權重陣列（Σ 應為約定和）
  dual    值/權重雙欄（FakeSC...）
  matrix  組別×欄矩陣
  series  橫向序列
  reel    輪帶 strip
  yesno   是否表（二元權重）
  paytable 賠付表
不呼叫 LLM；同輸入 bit-identical。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ps_common as C  # noqa: E402
import _xlsx_lib as X  # noqa: E402

# 表號前綴 → phase（製程階段）
PHASE = {"M": "Main", "F": "Free", "J": "Jackpot", "A": "ItemCard", "G": "General"}

# xlsx 選擇器 → 形狀分類
SEL_SHAPE = [
    (re.compile(r"^board\."), "scalar"),
    (re.compile(r"^reelsets\."), "weights"),
    (re.compile(r"^dual\["), "dual"),
    (re.compile(r"^yesno\["), "yesno"),
    (re.compile(r"^weights\["), "weights"),
    (re.compile(r"^matrix(_head)?\["), "matrix"),
    (re.compile(r"^series\["), "series"),
    (re.compile(r"^scalars\["), "scalar"),
    (re.compile(r"^strips\["), "reel"),
    (re.compile(r"^paytable\."), "paytable"),
]

TABLE_RE = re.compile(r"\[([MFJAG])-")


def get_path(cfg: dict, path: str):
    """重用 ps_diff 語意：以 . 分段，list 用 int index。"""
    cur = cfg
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


def classify(rule: dict) -> tuple:
    """回 (phase, shape, table)。優先吃 map 已補的 phase，否則由 xlsx 選擇器推。"""
    sel = rule.get("xlsx", "")
    # phase：map 明寫優先
    phase = rule.get("phase")
    if not phase:
        m = TABLE_RE.search(sel)
        phase = PHASE.get(m.group(1), "General") if m else "General"
    # shape
    shape = rule.get("shape")
    if not shape:
        shape = next((s for rx, s in SEL_SHAPE if rx.search(sel)), "scalar")
    # table 號（如 M-2）
    tm = re.search(r"\[([MFJAG]-[0-9-]+)\]", sel)
    table = tm.group(1) if tm else None
    return phase, shape, table


def label_of(rule: dict) -> str:
    return rule.get("label") or rule.get("note") or rule.get("id", "")


def load_config(config_path: pathlib.Path, map_path=None) -> dict:
    """讀設定檔 JSON + map → 分類後的結構，供 ps_xlsx 繪表。
    回傳 {phase: [{id, label, shape, table, tier_axis, value, config_key}, ...], ...}。
    """
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    rules = X.load_map(map_path)
    out: dict = {}
    missing = []
    for r in rules:
        phase, shape, table = classify(r)
        v = get_path(cfg, r["config"])
        if v is None:
            missing.append(r.get("id"))
        out.setdefault(phase, []).append({
            "id": r.get("id"),
            "label": label_of(r),
            "shape": shape,
            "table": table,
            "tier_axis": r.get("tier_axis"),
            "config_key": r.get("config"),
            "value": v,
        })
    return {"phases": out, "missing": missing, "total_rules": len(rules)}


def main() -> None:
    ap = argparse.ArgumentParser(description="讀 ProbSetting 設定檔 JSON，依 config-map 分類取值")
    ap.add_argument("--config", required=True, help="ProbSetting JSON 路徑")
    ap.add_argument("--map", help="config-map yaml（預設 references/config-map.fasttest.yaml）")
    ap.add_argument("--json", action="store_true", help="輸出完整分類 JSON")
    if "--help" in sys.argv or "-h" in sys.argv:
        ap.parse_args()
        return
    a = ap.parse_args()
    p = pathlib.Path(a.config)
    if not p.exists():
        C.fail("BAD_INPUT", f"找不到設定檔：{p}", "確認 ProbSetting JSON 路徑")
    result = load_config(p, a.map)
    phases = result["phases"]
    summary = {ph: len(items) for ph, items in phases.items()}
    data = {"phases": phases if a.json else summary,
            "missing": result["missing"], "total_rules": result["total_rules"],
            "resolved": result["total_rules"] - len(result["missing"])}
    C.emit(data, {"stage": "config_load"})


if __name__ == "__main__":
    main()
