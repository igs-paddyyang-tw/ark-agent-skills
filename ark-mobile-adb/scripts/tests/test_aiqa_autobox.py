"""aiqa_gamepack_autobox 測試：核帳驅動的機台檔驗證門檻。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiqa_gamepack_autobox import verify_profile  # noqa: E402
from aiqa_ledger import Spin  # noqa: E402


def _clean(n_win: int = 1) -> list[Spin]:
    """產 3 手乾淨守恆（首手設基準），其中 n_win 手有贏分。"""
    spins = [Spin(1_000_000, 880, 0, 999_120)]  # 首手 → BASELINE_BROKEN
    bal = 999_120
    for i in range(3):
        win = 200 if i < n_win else 0
        after = bal - 880 + win
        spins.append(Spin(bal, 880, win, after))
        bal = after
    return spins


def test_verified_when_clean_with_win() -> None:
    r = verify_profile(_clean(n_win=1), min_clean=3, require_win=True)
    assert r.verified and r.wins >= 1 and r.fails == 0


def test_not_verified_on_fail() -> None:
    spins = _clean(n_win=1)
    spins.append(Spin(spins[-1].credit_after, 880, 500, spins[-1].credit_after - 880))  # 少 500 → FAIL
    r = verify_profile(spins, min_clean=3, require_win=True)
    assert not r.verified and r.fails >= 1


def test_not_verified_without_win() -> None:
    r = verify_profile(_clean(n_win=0), min_clean=3, require_win=True)
    assert not r.verified and "贏分" in r.reason


def test_not_verified_insufficient_clean() -> None:
    spins = [Spin(1_000_000, 880, 0, 999_120), Spin(999_120, 880, 200, 998_440)]  # clean=1
    r = verify_profile(spins, min_clean=3, require_win=True)
    assert not r.verified and r.clean_pairs < 3


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
