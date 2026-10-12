#!/usr/bin/env python3
"""qt_target — 產生快測目標檔 quicktest.yaml（P-003 第①②向的來源），讓 qt_report 不再因「無目標」SKIP。

單一版本原則：一份 quicktest.yaml 只對一個設定檔（例：彌勒佛 A 版 a-standard.json）。
數字由人給（golden RTP、容許誤差、體感分級）；本腳本只負責格式正確、區間合法、記下設定檔 sha。

用法:
  python qt_target.py --out <game>/quicktest/quicktest.yaml --slug <slug> [--game <名>] --target-rtp 1.0003 [--tolerance 0.005]
                      [--feel SpecialGameTotal=稀有大事件] [--feel FreeGame=1/300~1/150] [--config <設定檔.json>] [--basis "逸修 golden …"] [--force]
  --feel 值：P-005 分級名（驚喜型／期待型／節奏型／核心體驗型／稀有大事件／標準節奏／高頻小獎）或 `1/300~1/150` 或 `0.0033,0.0067`
exit: 0 / 2 BAD_INPUT / 3 GATE_BLOCKED（已存在且未 --force）
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qt_common as C  # noqa: E402
from qt_report import FEEL_BANDS  # noqa: E402


def parse_feel(spec: str) -> dict:
    if "=" not in spec:
        C.fail("BAD_INPUT", f"--feel 需為 <game>=<分級或區間>：{spec}")
    game, val = (x.strip() for x in spec.split("=", 1))
    if val in FEEL_BANDS:
        return {"game": game, "preset": val}
    m = re.match(r"^1/(\d+(?:\.\d+)?)\s*~\s*1/(\d+(?:\.\d+)?)$", val)
    if m:
        a, b = 1 / float(m.group(1)), 1 / float(m.group(2))
    else:
        try:
            a, b = (float(x) for x in val.split(","))
        except ValueError:
            C.fail("BAD_INPUT", f"--feel 區間看不懂：{val}", "用 P-005 分級名、1/300~1/150 或 0.0033,0.0067")
    lo, hi = sorted((a, b))
    if not (0 < lo < hi <= 1):
        C.fail("BAD_INPUT", f"--feel 區間需落在 (0,1]：{val}")
    return {"game": game, "band": [round(lo, 6), round(hi, 6)]}


def main() -> None:
    ap = argparse.ArgumentParser(description="產生 quicktest.yaml（單一版本快測目標）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--game")
    ap.add_argument("--target-rtp", type=float, required=True, help="小數（1.0003 = 100.03%）")
    ap.add_argument("--tolerance", type=float, default=0.005)
    ap.add_argument("--feel", action="append", default=[])
    ap.add_argument("--config", help="這份目標對應的設定檔（記 sha，單一版本）")
    ap.add_argument("--basis", help="目標值的依據（例：逸修 golden，參數表 R32）")
    ap.add_argument("--scatter-id")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if not re.match(r"^[a-z][a-z0-9-]{1,48}$", a.slug):
        C.fail("BAD_INPUT", f"slug 需 kebab-case：{a.slug}")
    if not (0.5 <= a.target_rtp <= 1.5):
        C.fail("BAD_INPUT", f"--target-rtp 用小數表示（1.0003 = 100.03%），收到 {a.target_rtp}")
    if not (0 < a.tolerance < 0.1):
        C.fail("BAD_INPUT", f"--tolerance 需在 (0, 0.1)：{a.tolerance}")
    out = pathlib.Path(a.out)
    if out.exists() and not a.force:
        C.fail("GATE_BLOCKED", f"{out} 已存在", "確認要覆寫再加 --force")
    doc: dict = {"contract": C.CONTRACT, "kind": "quicktest-targets", "game": a.game or a.slug, "slug": a.slug,
                 "target_rtp": a.target_rtp, "rtp_tolerance": a.tolerance}
    if a.basis:
        doc["basis"] = a.basis
    feels = [parse_feel(f) for f in a.feel]
    if feels:
        doc["feel"] = feels
    if a.scatter_id:
        doc["scatter_id"] = a.scatter_id
    if a.config:
        cp = pathlib.Path(a.config)
        if not cp.exists():
            C.fail("BAD_INPUT", f"找不到設定檔 {cp}")
        rel = pathlib.Path(os.path.relpath(cp.resolve(), out.resolve().parent)).as_posix()
        doc["config"] = {"path": rel, "sha256_16": C.sha16(cp)}
    doc["generated_by"] = f"ark-game-quicktest {C.SKILL_VERSION} qt_target"
    C.atomic_write(out, C.yaml_dump(doc))
    C.emit({"targets": out.as_posix(), "target_rtp": a.target_rtp, "tolerance": a.tolerance, "feel": feels, "config": doc.get("config"),
            "delivery": f"quicktest.yaml 已落盤 {out.as_posix()}｜目標 {a.target_rtp:.4%} ±{a.tolerance:.1%}｜體感 {len(feels)} 項",
            "next": "qt_report --report <result.txt>（會自動找到本檔）"}, {"stage": "qt_target"})


if __name__ == "__main__":
    main()
