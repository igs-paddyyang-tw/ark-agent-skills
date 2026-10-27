"""aiqa_gamepack_autobox — 核帳驅動的機台檔驗證（draft → verify → promote）。

借鏡 ai-qa-agent `autobox.py` 設計、在 aiqa 自行重做（不搬 code）。
不另花押注試轉：用正常玩的連轉讀數，經 aiqa_ledger 核帳，通過才把機台檔從「待確認」升「有效」。

通過門檻（可調）：
- 無進 FAIL 的核帳判定（SINGLE_OFF / STREAK_OFF）。
- 乾淨守恆對數（OK）≥ min_clean。
- 至少一手有讀到贏分（win > 0 且該手 OK）—— 確認贏分 roi 真的讀得到。

人保最終否決：verify 只「可升」；是否標 verified 由人確認（本模組不改檔）。

供 aiqa_pack verify 子命令併用（verify_profile / _load_spins），亦可獨立 CLI 執行。
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aiqa_ledger import Spin, Verdict, classify, has_fail  # noqa: E402


@dataclass(frozen=True)
class VerifyResult:
    """機台檔核帳驗證結果。"""

    verified: bool
    reason: str
    clean_pairs: int
    wins: int
    fails: int


def verify_profile(
    spins: list[Spin], *, min_clean: int = 3, require_win: bool = True, tol: float = 1.0
) -> VerifyResult:
    """對連轉讀數做核帳驗證，回傳機台檔是否「可升為有效」。"""
    results = classify(spins, tol=tol)
    fails = sum(1 for r in results if r.verdict in (Verdict.SINGLE_OFF, Verdict.STREAK_OFF))
    clean = sum(1 for r in results if r.verdict is Verdict.OK)
    wins = sum(
        1
        for r, s in zip(results, spins)
        if r.verdict is Verdict.OK and (s.win or 0) > 0
    )

    if has_fail(results):
        return VerifyResult(False, f"核帳不符（{fails} 手 FAIL）→ 框選/roi 需修", clean, wins, fails)
    if clean < min_clean:
        return VerifyResult(False, f"乾淨守恆對數不足（{clean} < {min_clean}）", clean, wins, fails)
    if require_win and wins == 0:
        return VerifyResult(False, "未確認贏分框（無任一手讀到 win>0）", clean, wins, fails)
    return VerifyResult(True, f"核帳通過（乾淨 {clean}、有贏分 {wins}）→ 可升 verified（待人確認）", clean, wins, fails)


def _load_spins(path: Path) -> list[Spin]:
    """讀 spins JSON：list of {credit_before,bet,win,credit_after,action?}。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        Spin(
            credit_before=float(d["credit_before"]),
            bet=float(d["bet"]),
            win=None if d.get("win") is None else float(d["win"]),
            credit_after=float(d["credit_after"]),
            action=d.get("action", "spin"),
        )
        for d in data
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description="機台檔核帳驗證（draft→verify）")
    ap.add_argument("--spins", required=True, help="spins JSON 路徑")
    ap.add_argument("--min-clean", type=int, default=3)
    ap.add_argument("--no-require-win", action="store_true")
    ap.add_argument("--tol", type=float, default=1.0)
    a = ap.parse_args()
    r = verify_profile(
        _load_spins(Path(a.spins)),
        min_clean=a.min_clean,
        require_win=not a.no_require_win,
        tol=a.tol,
    )
    print(json.dumps({"verified": r.verified, "reason": r.reason,
                      "clean_pairs": r.clean_pairs, "wins": r.wins, "fails": r.fails},
                     ensure_ascii=False))
    sys.exit(0 if r.verified else 1)


if __name__ == "__main__":
    main()
