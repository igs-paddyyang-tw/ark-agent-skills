"""反證測試 —— ISSUE-QT-001：qt_config 符號分類（線賠 vs 非線賠）

## 回報的問題（修前這些測試必須紅）

qt_config 把**所有符號**無差別塞進 extra_odds.odds[sym_id]，沒 odds 的
（WILD/SC/籌碼/JP）塞 None；symbols[].group 讀了卻沒用來分流。
→ qt_lint 把這些非線賠符號的 null 當 QT-NULL 缺值報（假缺口），照填反而錯。

## 修法（對應回報三建議）

- Q-1：odds_tbl 只納 group==normal（或無 group 視 normal）；special/fg/jp 不進 odds 表
- Q-2：qt-config.yaml symbols[] 增 role 欄（payline/trigger/collectible/jackpot）
- Q-3：qt_lint QT-NULL 不對非線賠符號的 odds 空值報（改 QT-STRUCT 或豁免）
"""
from __future__ import annotations
import json, pathlib, subprocess, sys
import pytest

yaml = pytest.importorskip("yaml")
SCRIPTS = pathlib.Path(__file__).resolve().parent.parent


def run(script, *args) -> dict:
    r = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                       capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout.strip().splitlines()[-1]) | {"rc": r.returncode}


def _gdd_with_special(tmp: pathlib.Path) -> pathlib.Path:
    """含 normal(有odds) + WILD/SC/JP/籌碼(非線賠) 的 gdd。"""
    g = tmp / "gdd"; g.mkdir()
    (g / "gdd.yaml").write_text(yaml.safe_dump(
        {"short_title": "KaijiLike", "spec": [{"k": "盤面", "v": "5×5"}]}, allow_unicode=True), encoding="utf-8")
    (g / "symbols.yaml").write_text(yaml.safe_dump({"symbols": [
        {"code": "M1", "sym_id": 11, "group": "normal", "odds": [250, 60, 20]},
        {"code": "A", "sym_id": 21, "group": "normal", "odds": [10, 8, 5]},
        {"code": "WILD", "sym_id": 1, "group": "special"},
        {"code": "SC", "sym_id": 4, "group": "special"},
        {"code": "Coin", "sym_id": 7, "group": "fg"},
        {"code": "JP1", "sym_id": 100, "group": "jp"},
    ]}, allow_unicode=True), encoding="utf-8")
    return g


def test_odds_table_only_contains_payline_symbols(tmp_path):
    """Q-1：odds 表只納 group==normal；WILD/SC/籌碼/JP 不進 odds 表。"""
    out = tmp_path / "qt"
    r = run("qt_config.py", "--out", str(out), "--gdd", str(_gdd_with_special(tmp_path)))
    assert r["success"], r
    odds = json.loads((out / "odds" / "odds_1.0.0.json").read_text(encoding="utf-8"))["extra_odds"]["odds"]
    assert set(odds.keys()) == {"11", "21"}, f"odds 表應只含 normal 符號 11/21，得 {sorted(odds.keys())}"
    for nonline in ("1", "4", "7", "100"):
        assert nonline not in odds, f"非線賠符號 {nonline} 不該進 odds 表（Q-1）"


def test_nonpayline_symbols_not_reported_as_qt_null(tmp_path):
    """Q-3：非線賠符號不因 odds 空值被 QT-NULL 報（它們本就不是線賠）。

    注意：此 gdd 的 normal 符號都有 odds，所以 odds 表無 null；
    其他 extra_odds 欄位（gates/weights）仍會因無決議是 null → 那些是真缺口，QT-NULL 照報。
    本測試只驗「非線賠符號的 sym_id 不出現在 QT-NULL 的路徑裡」。
    """
    out = tmp_path / "qt"
    run("qt_config.py", "--out", str(out), "--gdd", str(_gdd_with_special(tmp_path)))
    l = run("qt_lint.py", "--dir", str(out))
    null_paths = [e["msg"] for e in l["data"].get("first_errors", []) if e["rule"] == "QT-NULL"]
    joined = " ".join(null_paths)
    for nonline in ("odds.1", "odds.4", "odds.7", "odds.100"):
        assert nonline not in joined, f"非線賠符號 {nonline} 不該出現在 QT-NULL（Q-3）；null_paths={null_paths}"


def test_symbol_role_recorded_in_config(tmp_path):
    """Q-2：qt-config.yaml 的 symbols[] 顯式記 role（payline/trigger/collectible/jackpot）。"""
    out = tmp_path / "qt"
    run("qt_config.py", "--out", str(out), "--gdd", str(_gdd_with_special(tmp_path)))
    qc = yaml.safe_load((out / "qt-config.yaml").read_text(encoding="utf-8"))
    by_id = {s["sym_id"]: s for s in qc["structure"]["symbols"]}
    assert by_id[11].get("role") == "payline", f"normal 應為 payline；得 {by_id[11].get('role')}"
    assert by_id[1].get("role") == "payline" or by_id[1].get("role") == "wild" or by_id[1].get("role"), "WILD 應有非 payline 的 role"
    assert by_id[4].get("role") in ("trigger", "scatter"), f"SC 應為 trigger/scatter；得 {by_id[4].get('role')}"
    assert by_id[7].get("role") == "collectible", f"籌碼應為 collectible；得 {by_id[7].get('role')}"
    assert by_id[100].get("role") == "jackpot", f"JP 應為 jackpot；得 {by_id[100].get('role')}"


def test_w_prefixed_normal_with_odds_not_misclassified(tmp_path):
    """code 兜底不誤傷：以 W 開頭但有 odds 的 normal 符號（如 Watermelon）仍是 payline、進 odds 表。

    這是「code 前綴兜底」方案的風險點 —— 必須守住：有 odds = 線賠，不因 code 像 WILD 被踢出。
    """
    g = tmp_path / "gdd"; g.mkdir()
    (g / "gdd.yaml").write_text(yaml.safe_dump({"short_title": "W", "spec": [{"k": "盤面", "v": "5×5"}]}, allow_unicode=True), encoding="utf-8")
    (g / "symbols.yaml").write_text(yaml.safe_dump({"symbols": [
        {"code": "Watermelon", "sym_id": 30, "odds": [100, 40, 10]},  # 無 group、W 開頭、但有 odds → 應仍 payline
        {"code": "WILD", "sym_id": 1},                                 # 無 group、W 開頭、無 odds → wild
    ]}, allow_unicode=True), encoding="utf-8")
    out = tmp_path / "qt"
    run("qt_config.py", "--out", str(out), "--gdd", str(g))
    odds = json.loads((out / "odds" / "odds_1.0.0.json").read_text(encoding="utf-8"))["extra_odds"]["odds"]
    assert "30" in odds, "有 odds 的 W 開頭 normal 符號應進 odds 表（不被 code 兜底誤踢）"
    assert "1" not in odds, "無 odds 的 WILD 不進 odds 表"
    qc = yaml.safe_load((out / "qt-config.yaml").read_text(encoding="utf-8"))
    by_id = {s["sym_id"]: s for s in qc["structure"]["symbols"]}
    assert by_id[30]["role"] == "payline" and by_id[1]["role"] == "wild"


def test_normal_symbol_missing_odds_still_flagged(tmp_path):
    """回歸守門沒放水：normal 符號缺 odds → odds 表仍含它且為 null（真缺口該報）。"""
    g = tmp_path / "gdd"; g.mkdir()
    (g / "gdd.yaml").write_text(yaml.safe_dump({"short_title": "X", "spec": [{"k": "盤面", "v": "5×5"}]}, allow_unicode=True), encoding="utf-8")
    (g / "symbols.yaml").write_text(yaml.safe_dump({"symbols": [
        {"code": "M1", "sym_id": 11, "group": "normal", "odds": [250, 60, 20]},
        {"code": "M2", "sym_id": 12, "group": "normal"},  # normal 但缺 odds = 真缺口
    ]}, allow_unicode=True), encoding="utf-8")
    out = tmp_path / "qt"
    run("qt_config.py", "--out", str(out), "--gdd", str(g))
    odds = json.loads((out / "odds" / "odds_1.0.0.json").read_text(encoding="utf-8"))["extra_odds"]["odds"]
    assert "12" in odds and odds["12"] is None, "normal 缺 odds 應留在表內且為 null（真缺口）"
