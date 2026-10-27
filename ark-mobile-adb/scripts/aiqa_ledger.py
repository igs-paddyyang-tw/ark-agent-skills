"""aiqa_ledger — 連轉資產核帳引擎（相鄰兩轉 + 分類，壓誤報）。

借鏡 ai-qa-agent `ledger.py` 的設計、在 aiqa 自行重做（不搬 code）。
解決：單轉守恆 oracle 會被升級/任務外部加幣誤判 FAIL（fuxing3 FX3-11-001 的 +38,888 即此）。

核心判準（見 .kiro/steering/CODE.md「核帳與機台判準」）：
- 守恆式：`credit_after == baseline - bet + (win or 0)`，容差 ±tol。
- baseline 跟狀態走：上一轉結算後餘額；BASELINE_BREAKERS 令基準失效、該對不判。
- 只 SINGLE_OFF / STREAK_OFF 進 FAIL；外部加幣、讀不到、基準失效一律不當 FAIL（靜音/人覆核）。

純函式、無 I/O，可被 aiqa_run 與離線 golden 測試共用（量測即規格）。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# 令對帳基準失效的動作（非旋轉）；observe/note 為中性不影響
BASELINE_BREAKERS: frozenset[str] = frozenset(
    {"tap", "swipe", "back", "wait", "machine_change", "unread"}
)


class Verdict(str, Enum):
    """單對（相鄰兩轉）核帳判定。"""

    OK = "OK"  # 守恆成立
    EXTERNAL_CREDIT = "EXTERNAL_CREDIT"  # 餘額偏高且非本手 win（疑升級/任務加幣）→ 不判 FAIL
    SINGLE_OFF = "SINGLE_OFF"  # 單一對不符、無法解釋 → FAIL
    STREAK_OFF = "STREAK_OFF"  # 連續對不符 → FAIL
    BASELINE_BROKEN = "BASELINE_BROKEN"  # 前一動作令基準失效 → 不判
    NEEDS_HUMAN = "NEEDS_HUMAN"  # win 讀不到且餘額對不上 → 人覆核


# 進 FAIL 的判定（其餘靜音或人覆核）
FAIL_VERDICTS: frozenset[Verdict] = frozenset({Verdict.SINGLE_OFF, Verdict.STREAK_OFF})


@dataclass(frozen=True)
class Spin:
    """一手的讀數。`win=None` 代表未讀到（暫態/讀失敗）。`action` 預設為正常旋轉。"""

    credit_before: float
    bet: float
    win: float | None
    credit_after: float
    action: str = "spin"


@dataclass(frozen=True)
class LedgerResult:
    """逐手核帳結果。"""

    index: int
    verdict: Verdict
    diff: float  # credit_after - 期望值
    detail: str


def _expected(baseline: float, bet: float, win: float | None) -> float:
    """守恆期望餘額：baseline - bet + (win or 0)。"""
    return baseline - bet + (win or 0.0)


def classify(spins: list[Spin], *, tol: float = 1.0) -> list[LedgerResult]:
    """逐手核帳並分類。baseline 取上一手結算後餘額（首手用該手 credit_before）。

    規則摘要：
    - 前一動作在 BASELINE_BREAKERS → 本手 BASELINE_BROKEN（不判、baseline 重設為本手 credit_before）。
    - 守恆成立（|diff| ≤ tol）→ OK。
    - win 讀不到（None）且 diff ≠ 0 → NEEDS_HUMAN（不臆測）。
    - diff > tol（餘額偏高）且已讀 win → EXTERNAL_CREDIT（疑外部加幣，不判 FAIL）。
    - diff < -tol（餘額偏低、少錢）→ SINGLE_OFF（進 FAIL）；連續多手同向 → STREAK_OFF。
    """
    results: list[LedgerResult] = []
    baseline: float | None = None
    neg_streak = 0

    for i, s in enumerate(spins):
        prev_breaker = i > 0 and spins[i - 1].action in BASELINE_BREAKERS
        if baseline is None or prev_breaker:
            baseline = s.credit_before
            results.append(LedgerResult(i, Verdict.BASELINE_BROKEN, 0.0, "基準失效/首手，不判"))
            neg_streak = 0
            baseline = s.credit_after
            continue

        exp = _expected(baseline, s.bet, s.win)
        diff = round(s.credit_after - exp, 2)

        if abs(diff) <= tol:
            v, detail = Verdict.OK, "守恆成立"
            neg_streak = 0
        elif s.win is None:
            v, detail = Verdict.NEEDS_HUMAN, f"win 未讀、餘額差 {diff:+.0f}，不臆測"
            neg_streak = 0
        elif diff > tol:
            v, detail = Verdict.EXTERNAL_CREDIT, f"餘額偏高 {diff:+.0f}，非本手 win（疑升級/任務加幣）"
            neg_streak = 0
        else:  # diff < -tol：少錢
            neg_streak += 1
            if neg_streak >= 2:
                v, detail = Verdict.STREAK_OFF, f"連續 {neg_streak} 手少錢（累 {diff:+.0f}）"
            else:
                v, detail = Verdict.SINGLE_OFF, f"單手少錢 {diff:+.0f}"

        results.append(LedgerResult(i, v, diff, detail))
        baseline = s.credit_after  # 下一手基準＝本手結算後餘額

    return results


def has_fail(results: list[LedgerResult]) -> bool:
    """是否有進 FAIL 的判定（SINGLE_OFF / STREAK_OFF）。"""
    return any(r.verdict in FAIL_VERDICTS for r in results)
