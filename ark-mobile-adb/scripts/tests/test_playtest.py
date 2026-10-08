"""aiqa playtest（v2.2）：清單 md 三種寫法解析、fake 全鏈（init → 操作 / 判定 / 發現 / 探索 / 對帳 → report）、
完整度檢查（--strict 擋未執行、無證據、探索沒回填）、對帳計算、promote 回歸清單。"""
import json
import os
import pathlib
import subprocess
import sys

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
SKILL = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import aiqa_playtest as P  # noqa: E402

PT = SCRIPTS / "aiqa_playtest.py"


def sh(cwd, *args, expect=0):
    r = subprocess.run([sys.executable, str(PT), *map(str, args)], capture_output=True, text=True, encoding="utf-8", cwd=cwd,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    j = json.loads(r.stdout.strip().splitlines()[-1])
    if expect is not None:
        assert r.returncode == expect, (r.returncode, j, r.stderr[-400:])
    return j


def test_parse_three_styles():
    md = """---
title: T
forbid: [不要按 PLAY BONUS]
---
# 測試
## 基本測試
### 大廳
- [ ] 開 App 進大廳 ｜ 預期：看到餘額
- [x] GHY-LB-002 每日簽到可領 預期：餘額 +獎勵
  - 打開簽到
  - 按領取
### B-020 規則對照
步驟：
- 讀規則頁
- 旋轉到觸發
預期：次數一致
重複：3
| 編號 | 項目 | 步驟 | 預期 |
|---|---|---|---|
| | 魚機能離開 | 開選單→按離開 | 回大廳 |
## 探索重點
- 預設押注
## 禁止
- 不開寶石轉盤
"""
    cl = P.parse_checklist(md)
    ids = [i["id"] for i in cl["items"]]
    titles = [i["title"] for i in cl["items"]]
    assert "GHY-LB-002" in ids and "B-020" in ids
    assert "開 App 進大廳" in titles and "魚機能離開" in titles
    lb = next(i for i in cl["items"] if i["id"] == "GHY-LB-002")
    assert lb["steps"] == ["打開簽到", "按領取"] and lb["expect"].startswith("餘額")
    b20 = next(i for i in cl["items"] if i["id"] == "B-020")
    assert b20["repeat"] == 3 and b20["steps"] == ["讀規則頁", "旋轉到觸發"] and b20["expect"] == "次數一致"
    assert cl["explore_focus"] == ["預設押注"]
    assert "不開寶石轉盤" in cl["forbid"] and "不要按 PLAY BONUS" in cl["forbid"]
    assert len(set(ids)) == len(ids)


def test_parse_plain_list_without_headings():
    cl = P.parse_checklist("- 進大廳\n- 關掉所有彈窗 | 不卡住\n1. 旋轉 10 把\n")
    assert [i["title"] for i in cl["items"]] == ["進大廳", "關掉所有彈窗", "旋轉 10 把"]
    assert cl["items"][1]["expect"] == "不卡住"


def test_example_checklist_parses():
    cl = P.parse_checklist((SKILL / "examples" / "ghy-newbie.checklist.md").read_text(encoding="utf-8"))
    assert len(cl["items"]) >= 8 and cl["explore_focus"] and cl["meta"]["package"] == "com.igs.fafafa"


def test_fake_full_chain(tmp_path):
    cl = tmp_path / "cl.md"
    cl.write_text("# 冒煙\n- [ ] 進大廳 ｜ 預期：看到餘額\n- [ ] 旋轉 20 把 ｜ 預期：餘額變化 = 贏分 − 押注×把數\n- [ ] 斷線重連 ｜ 預期：回原畫面\n", encoding="utf-8")
    init = sh(tmp_path, "init", "--checklist", cl, "--backend", "fake")["data"]
    assert [i["id"] for i in init["items"]] == ["B-001", "B-002", "B-003"]
    run = pathlib.Path(init["run"])
    assert (run / "narrative.md").exists() and (run / "checklist.json").exists()

    # 還沒做事就 strict report → 擋
    r = sh(tmp_path, "report", "--strict", expect=3)
    assert "完整度" in r["error"]["message"]

    s1 = sh(tmp_path, "shot", "--label", "大廳", "--item", "B-001")["data"]["id"]
    assert s1 == "S-0001" and (run / "shots").glob("S-0001-*.png")
    t = sh(tmp_path, "tap", "270", "480", "--basis", "540x960", "--why", "點機台")["data"]
    assert (t["x"], t["y"]) == (360, 640)           # 縮圖座標換算成裝置座標（fake 720x1280）
    sh(tmp_path, "mark", "--outcome", "miss")
    sh(tmp_path, "item", "B-001", "--verdict", "PASS", "--shots", s1)
    sh(tmp_path, "spin", "360", "1180", "--times", "20", "--machine", "甜點寶藏", "--bet", "40000", "--shot-every", "10")
    led = sh(tmp_path, "ledger", "--label", "20 把", "--before", "1,000,000", "--after", "320,000", "--bet", "40000", "--spins", "20", "--win", "120000")["data"]
    assert led["expect_delta"] == -680000 and led["match"] is True
    bad = sh(tmp_path, "ledger", "--label", "錯", "--before", "100", "--after", "90", "--expect-delta", "0")["data"]
    assert bad["match"] is False and bad["diff"] == -10
    sh(tmp_path, "item", "B-002", "--verdict", "PASS", "--shots", "S-0002")
    sh(tmp_path, "item", "B-003", "--verdict", "BLOCK", "--block-reason", "模擬器斷不了網")
    x = sh(tmp_path, "explore", "--heuristic", "E6", "--hypothesis", "說明窗的確定會改押注")["data"]["id"]
    sh(tmp_path, "finding", "--severity", "high", "--category", "newbie", "--title", "確定就開額外押注", "--shots", s1,
       "--suggest", "改成兩個選項", "--explore", x)
    sh(tmp_path, "explore", "--id", x, "--status", "issue", "--result", "880→1,320", "--finding", "F-001")
    sh(tmp_path, "popup", "--name", "儲值禮包", "--kind", "paid", "--action", "按 X")
    sh(tmp_path, "game", "--name", "甜點寶藏", "--rules-read", "--feature", "免費遊戲", "--win", "15162000")
    (run / "narrative.md").write_text("## 摘要\n測完了。\n\n## 流程\n1. **進大廳** 看到餘額\n\n![大廳](S-0001)\n", encoding="utf-8")

    rep = sh(tmp_path, "report", "--strict")["data"]
    assert rep["lint"]["errors"] == [] and any("L-002" in w for w in rep["lint"]["warnings"])
    html = pathlib.Path(rep["html"]).read_text(encoding="utf-8")
    for must in ("基本測試結果", "發現的問題", "自我探索測試", "對帳", "彈窗整理", "優化建議", "做法與限制", "待辦", "data:image/jpeg;base64,",
                 "確定就開額外押注", "模擬器斷不了網", "流程"):
        assert must in html, must
    summ = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    assert summ["verdicts"]["PASS"] == 2 and summ["spins"] == 20 and summ["ledger"] == {"total": 2, "match": 1}
    assert summ["valid_tap_rate"] == "0%"      # 唯一一次點擊被標 miss
    st = sh(tmp_path, "status")["data"]
    assert st["pending"] == [] and st["findings"]["高"] == 1

    nxt = sh(tmp_path, "promote")["data"]
    assert nxt["regression_items"] == 1
    again = P.parse_checklist(pathlib.Path(nxt["out"]).read_text(encoding="utf-8"))
    assert any(i["id"] == "R-001" for i in again["items"])


def test_gates(tmp_path):
    cl = tmp_path / "cl.md"
    cl.write_text("- [ ] A ｜ 預期：B\n", encoding="utf-8")
    sh(tmp_path, "init", "--checklist", cl, "--backend", "fake")
    sh(tmp_path, "tap", "1", "1", "--why", " ", expect=2)                    # 每次點擊都要寫原因
    sh(tmp_path, "item", "B-009", "--verdict", "PASS", expect=2)             # 清單沒有的項目
    sh(tmp_path, "finding", "--title", "x", expect=2)                        # 新發現要嚴重度
    w = sh(tmp_path, "item", "B-001", "--verdict", "PASS")["data"]["warning"]
    assert "證據" in w
    sh(tmp_path, "explore", "--hypothesis", "h")
    rep = sh(tmp_path, "report")["data"]
    errs = " ".join(rep["lint"]["errors"])
    assert "沒有證據" in errs and "還沒回填" in errs
    empty = tmp_path / "empty.md"
    empty.write_text("# 只有標題\n", encoding="utf-8")
    sh(tmp_path, "init", "--checklist", empty, "--backend", "fake", expect=3)


def test_finding_resolved_as_design(tmp_path):
    cl = tmp_path / "cl.md"
    cl.write_text("- [ ] A ｜ 預期：B\n", encoding="utf-8")
    run = pathlib.Path(sh(tmp_path, "init", "--checklist", cl, "--backend", "fake")["data"]["run"])
    s = sh(tmp_path, "shot", "--label", "x")["data"]["id"]
    sh(tmp_path, "finding", "--severity", "中", "--title", "確定就開額外押注", "--shots", s, "--suggest", "改兩個選項", "--confirm")
    sh(tmp_path, "finding", "--id", "F-001", "--no-confirm", "--status", "wontfix", "--detail", "企劃確認為設計如此")
    f = P.merged(P.Run(run), "finding")["F-001"]
    assert f["confirm"] is False and f["status"] == "wontfix"
    sh(tmp_path, "promote")
    assert "R-001" not in (run / "checklist.next.md").read_text(encoding="utf-8")
    html = pathlib.Path(sh(tmp_path, "report")["data"]["html"]).read_text(encoding="utf-8")
    assert "設計如此" in html and "確認 F-001" not in html
