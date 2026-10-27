"""aiqa_ledger golden 測試：證明連轉核帳不再把外部加幣/未讀 win 誤判 FAIL。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiqa_ledger import Spin, Verdict, classify, has_fail  # noqa: E402


def _verdicts(spins: list[Spin]) -> list[Verdict]:
    return [r.verdict for r in classify(spins)]


def test_fuxing3_unread_win_not_fail() -> None:
    """fuxing3 FX3-11-001：win 未讀、餘額高 +38,888 → NEEDS_HUMAN，不是 FAIL（單轉 oracle 的誤判根治）。"""
    spins = [
        Spin(credit_before=1_490_550, bet=3_300, win=None, credit_after=1_490_550),  # 首手設基準
        Spin(credit_before=1_490_550, bet=3_300, win=None, credit_after=1_526_138),  # +38,888、win 未讀
    ]
    res = classify(spins)
    assert res[1].verdict is Verdict.NEEDS_HUMAN
    assert not has_fail(res)  # 關鍵：不進 FAIL


def test_level_up_external_credit_not_fail() -> None:
    """已讀 win=0 但餘額偏高一個整額（升級 +10,000）→ EXTERNAL_CREDIT，不判 FAIL。"""
    spins = [
        Spin(credit_before=1_000_000, bet=880, win=0, credit_after=999_120),  # OK 設基準
        Spin(credit_before=999_120, bet=880, win=0, credit_after=1_008_240),  # 999120-880+0=998240，+10,000
    ]
    res = classify(spins)
    assert res[1].verdict is Verdict.EXTERNAL_CREDIT
    assert not has_fail(res)


def test_clean_spins_ok() -> None:
    """乾淨連轉守恆成立 → 全 OK。"""
    spins = [
        Spin(1_000_000, 880, 0, 999_120),
        Spin(999_120, 880, 200, 998_440),
        Spin(998_440, 880, 0, 997_560),
    ]
    assert _verdicts(spins) == [Verdict.BASELINE_BROKEN, Verdict.OK, Verdict.OK]
    assert not has_fail(classify(spins))


def test_missing_payout_is_fail() -> None:
    """已讀 win 但少錢（派彩未入帳/錯帳）→ SINGLE_OFF，進 FAIL。"""
    spins = [
        Spin(1_000_000, 880, 0, 999_120),
        Spin(999_120, 880, 500, 998_240),  # 期望 998740，實際少 500
    ]
    res = classify(spins)
    assert res[1].verdict is Verdict.SINGLE_OFF
    assert has_fail(res)


def test_streak_off() -> None:
    """連續兩手少錢 → STREAK_OFF。"""
    spins = [
        Spin(1_000_000, 880, 0, 999_120),
        Spin(999_120, 880, 0, 998_040),  # 少 200
        Spin(998_040, 880, 0, 996_960),  # 再少 200
    ]
    res = classify(spins)
    assert res[1].verdict is Verdict.SINGLE_OFF
    assert res[2].verdict is Verdict.STREAK_OFF
    assert has_fail(res)


def test_baseline_breaker_not_judged() -> None:
    """breaker 動作（tap）後該手不判（基準失效）。"""
    spins = [
        Spin(1_000_000, 880, 0, 999_120),
        Spin(999_120, 0, None, 1_050_000, action="tap"),  # 非旋轉、令基準失效
        Spin(1_050_000, 880, 0, 1_049_120),  # 前一手是 breaker → BASELINE_BROKEN
    ]
    res = classify(spins)
    assert res[2].verdict is Verdict.BASELINE_BROKEN
    assert not has_fail(res)


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
