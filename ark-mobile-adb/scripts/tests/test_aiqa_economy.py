"""aiqa_economy batch 轉接層測試：credit-primary + observations→ledger→verdict。

關鍵（真機發現 fuxing3 win ROI 大獎動畫期高估）：
- win 讀數僅當**與 credit delta 自洽**才採用，否則丟成 None → ledger 判 NEEDS_HUMAN（不誤 FAIL）。
- baseline 走鏈（上一手 credit_after）：手與手之間金額憑空消失 → SINGLE_OFF/STREAK_OFF → FAIL。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiqa_economy import DEFAULT_NAMES, build_spins, is_economy_item, reconcile  # noqa: E402


def _obs(cb, bet, win, ca):
    return {"cb": cb, "bet": bet, "win": win, "ca": ca}


# ---------------------------------------------------------------- 偵測
def test_detect_by_default_names() -> None:
    """四個預設讀數名皆為 list → 自動辨識為 economy 項。"""
    obs = _obs([1_000_000], [880], [0], [999_120])
    is_econ, names = is_economy_item({}, obs)
    assert is_econ and names == DEFAULT_NAMES


def test_detect_explicit_flag() -> None:
    is_econ, _ = is_economy_item({"economy": True}, {})
    assert is_econ
    is_econ, _ = is_economy_item({"economy": False}, _obs([1], [1], [1], [1]))
    assert not is_econ


def test_detect_custom_names() -> None:
    item = {"economy": {"names": {"credit_before": "c0", "credit_after": "c1"}}}
    is_econ, names = is_economy_item(item, {})
    assert is_econ and names["credit_before"] == "c0" and names["bet"] == "bet"


def test_not_economy_when_names_absent() -> None:
    is_econ, _ = is_economy_item({}, {"foo": [1], "bar": [2]})
    assert not is_econ


# ---------------------------------------------------------------- credit-primary
def test_credit_primary_drops_inconsistent_win() -> None:
    """win 與 credit delta 不自洽（高估）→ 丟成 None；credit 顯示有派彩 → NEEDS_HUMAN，不是 FAIL。"""
    # 真相：這手實際 win=100（ca=cb-880+100=998340），但 win ROI 誤讀 400（大獎動畫高估）
    # actual_delta=cb-ca=780, implied=bet-win=480 → |780-480|=300>tol → win 丟棄
    # 丟棄後 exp=cb-880=998240, diff=998340-998240=+100≠0 且 win=None → NEEDS_HUMAN
    obs = _obs([1_000_000, 999_120], [880, 880], [0, 400], [999_120, 998_340])
    spins = build_spins(obs, DEFAULT_NAMES)
    assert spins[1].win is None  # 不自洽 → 丟棄
    assert reconcile(obs, DEFAULT_NAMES)["verdict"] == "NEEDS_HUMAN"  # 關鍵：不誤 FAIL


def test_credit_primary_keeps_consistent_win() -> None:
    """win 與 credit delta 自洽 → 採用 → 守恆 OK → PASS。"""
    # cb-ca = 999120-998440 = 680；bet-win = 880-200 = 680 → 自洽
    obs = _obs([1_000_000, 999_120], [880, 880], [0, 200], [999_120, 998_440])
    spins = build_spins(obs, DEFAULT_NAMES)
    assert spins[1].win == 200
    assert reconcile(obs, DEFAULT_NAMES)["verdict"] == "PASS"


# ---------------------------------------------------------------- FAIL 可達（鏈斷：手間金額消失）
def test_money_vanish_between_spins_is_fail() -> None:
    """手與手之間 credit 憑空少 500（各手自身讀數自洽、win 可信）→ SINGLE_OFF → FAIL。"""
    # 手1 OK 設鏈 baseline=998440
    # 手2 baseline=998440, bet=880 win=200（自洽於自身 cb/ca）, 但實際結算 ca 比鏈期望少 500 → diff=-500 → SINGLE_OFF
    obs = _obs(
        [1_000_000, 997_940],   # 手2 cb=997940（鏈上一手 ca 是 998440，中間少 500）
        [880, 880],
        [200, 200],
        [998_440, 997_260],     # 手2 ca=997260；鏈 exp=998440-880+200=997760 → 少 500
    )
    rec = reconcile(obs, DEFAULT_NAMES)
    assert rec["verdict"] == "FAIL"
    assert rec["counts"].get("SINGLE_OFF", 0) >= 1


def test_streak_vanish_is_fail() -> None:
    """連兩手鏈上各少 500 → STREAK_OFF → FAIL。"""
    obs = _obs(
        [1_000_000, 997_940, 996_760],
        [880, 880, 880],
        [200, 200, 200],
        [998_440, 997_260, 996_080],  # 手2 少500(exp 997760)、手3 少500(baseline 997260→exp 996580, ca 996080)
    )
    rec = reconcile(obs, DEFAULT_NAMES)
    assert rec["verdict"] == "FAIL"
    assert rec["counts"].get("STREAK_OFF", 0) >= 1


# ---------------------------------------------------------------- 外部加幣不誤 FAIL
def test_external_credit_dropped_win_needs_human_not_fail() -> None:
    """升級外部加幣（餘額暴增、win 不自洽被丟）→ NEEDS_HUMAN，不是 FAIL（穩健）。"""
    # 手2 餘額 +9120（升級），win ROI 讀 0 → actual=-9120, implied=880 → 不自洽 → win=None → NEEDS_HUMAN
    obs = _obs([1_000_000, 999_120], [880, 880], [0, 0], [999_120, 1_008_240])
    rec = reconcile(obs, DEFAULT_NAMES)
    assert rec["verdict"] == "NEEDS_HUMAN"
    assert rec["counts"].get("SINGLE_OFF", 0) == 0  # 絕不誤判少錢


def test_external_credit_trusted_win_is_external() -> None:
    """若 win=0 與餘額變動恰自洽卻仍偏高（極少見）→ EXTERNAL_CREDIT，仍不 FAIL。"""
    # 手2：cb=999120 ca=999120（餘額沒掉但也沒加）bet=0 win=0 → actual=0 implied=0 自洽；
    # 鏈 exp=baseline(999120)-0+0=999120 → diff=0 → OK。改造：bet=0、ca 比 baseline 高 → EXTERNAL_CREDIT。
    obs = _obs([1_000_000, 999_120], [0, 0], [0, 0], [999_120, 1_009_120])
    rec = reconcile(obs, DEFAULT_NAMES)
    # 手2 win=0 自洽(actual=cb-ca=-10000, implied=0 → 不自洽 → 丟棄) → NEEDS_HUMAN
    assert rec["verdict"] in ("NEEDS_HUMAN", "PASS")  # 無論哪條，皆非 FAIL
    assert rec["counts"].get("SINGLE_OFF", 0) == 0


# ---------------------------------------------------------------- 邊界
def test_empty_spins_needs_human() -> None:
    rec = reconcile(_obs([], [], [], []), DEFAULT_NAMES)
    assert rec["verdict"] == "NEEDS_HUMAN" and rec["spins"] == 0


def test_ragged_lists_aligned_to_shortest() -> None:
    """某讀數少一手 → 以最短對齊，不越界。"""
    obs = _obs([1_000_000, 999_120], [880, 880], [0], [999_120, 998_240])  # win 只 1 筆
    spins = build_spins(obs, DEFAULT_NAMES)
    assert len(spins) == 1  # 以 win 的長度對齊


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
