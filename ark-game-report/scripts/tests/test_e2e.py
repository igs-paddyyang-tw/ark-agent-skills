"""ark-game-report 端到端測試（合成資料）。可用 pytest 或直接 `python test_e2e.py` 執行。"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
FIX = SCRIPTS / "tests" / "make_fixture.py"


def run(stage, *args, cwd, env=None):
    r = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "gr_run.py"), stage, *map(str, args)], cwd=cwd,
                       capture_output=True, text=True, encoding="utf-8", env=env)
    lines = [l for l in r.stdout.strip().splitlines() if l.startswith("{")]
    d = json.loads(lines[-1]) if lines else {}
    d["rc"] = r.returncode
    return d


def setup(tmp: pathlib.Path, days=7, extra=(), drop=(), stage=None):
    import yaml
    d = run("init", "--slug", "demo", "--name", "範例機台", "--game-id", "DEMO-001", "--launch-date", "2026-10-01",
            "--stage", stage or days, "--out", "report.yaml", cwd=tmp)
    assert d["rc"] == 0, d
    cfg = yaml.safe_load((tmp / "report.yaml").read_text(encoding="utf-8"))
    cfg.update({"data_dir": "data", "out_dir": "out", "kb": {"wiki_dirs": []},
                "spec": {"target_rtp": 0.965, "sigma": 12.0, "triggers": {"Free Game": 180, "Hold & Spin": 95}},
                "views": [{"name": "全體"}, {"name": "CN", "column": "market", "values": ["CN"]}, {"name": "非CN", "column": "market", "not_values": ["CN"]}]})
    (tmp / "report.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    subprocess.run([sys.executable, str(FIX), str(tmp / "data"), "--days", str(days), *extra], check=True, capture_output=True)
    for x in drop:
        p = tmp / "data" / x
        if p.is_dir():
            import shutil
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()


def test_full_d7():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        setup(tmp)
        p = run("probe", "--config", "report.yaml", cwd=tmp)
        assert p["rc"] == 0 and set(p["data"]["sections"].values()) == {"ok"}, p
        b = run("build", "--config", "report.yaml", cwd=tmp)
        assert b["rc"] == 0 and set(b["data"]["lights"]) == {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "H"}
        assert all(v != "na" for v in b["data"]["lights"].values()), b["data"]["lights"]
        i = run("insight", "--config", "report.yaml", "--no-kb", cwd=tmp)
        assert i["rc"] == 0 and (tmp / "data" / "insights.md").is_file()
        rep = json.loads((tmp / "data" / "report.json").read_text(encoding="utf-8"))
        assert rep["views"]["全體"]["verdict"]["headline"].endswith("（草稿）")
        assert len(rep["views"]["全體"]["share"]["game"]) == 7 and rep["views"]["全體"]["retention"]["days"] == [1, 2, 3, 4, 5, 6, 7]
        r = run("render", "--config", "report.yaml", cwd=tmp)
        html = pathlib.Path(tmp / r["data"]["html"])
        assert r["rc"] == 0 and html.is_file() and "__REPORT_DATA__" not in html.read_text(encoding="utf-8")
        assert html.with_suffix(".json").is_file()


def test_degraded_data_still_renders():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        setup(tmp, extra=["--no-win"], drop=["bench", "slot_users.csv", "erosion.csv", "hours.csv", "slot_daily.csv"])
        p = run("probe", "--config", "report.yaml", cwd=tmp)
        s = p["data"]["sections"]
        assert s["Q1"] == "partial" and s["Q6"] == "skip" and s["Q2"] == "partial", s
        b = run("build", "--config", "report.yaml", cwd=tmp)
        assert b["rc"] == 0 and b["data"]["lights"]["Q1"] == "na" and b["data"]["lights"]["Q6"] == "na"
        rep = json.loads((tmp / "data" / "report.json").read_text(encoding="utf-8"))
        assert "rtp" not in rep["views"]["全體"] and "share" not in rep["views"]["全體"]
        assert rep["footnote"]
        assert run("all", "--config", "report.yaml", "--no-kb", cwd=tmp)["rc"] == 0


def test_d30_retention_days_and_fast_decay():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        setup(tmp, days=30)
        assert run("all", "--config", "report.yaml", "--no-kb", cwd=tmp)["rc"] == 0
        rep = json.loads((tmp / "data" / "report.json").read_text(encoding="utf-8"))
        assert rep["views"]["全體"]["retention"]["days"] == [1, 2, 3, 5, 7, 10, 14, 21, 30]
        ins = json.loads((tmp / "data" / "insights.json").read_text(encoding="utf-8"))
        assert "FAST_DECAY" in [f["id"] for f in ins["全體"]["fired"]]


def test_query_sql_and_adapter_todo():
    import yaml
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        setup(tmp)
        cfg = yaml.safe_load((tmp / "report.yaml").read_text(encoding="utf-8"))
        ad = yaml.safe_load((SCRIPTS.parent / "assets" / "adapters" / "bigquery-igs.yaml").read_text(encoding="utf-8"))
        # uid/bet/spins 是 TODO → 不產 SQL，列在 skipped（正式 adapter 已於 0.1.1 回填，這裡用刻意留 TODO 的副本）
        todo = dict(ad, columns={**ad["columns"], "uid": "TODO: 玩家 ID", "bet": "TODO: 押注", "spins": "TODO: 次數"})
        (tmp / "todo.yaml").write_text(yaml.safe_dump(todo, allow_unicode=True), encoding="utf-8")
        cfg["adapter"] = str(tmp / "todo.yaml")
        (tmp / "report.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
        q = run("query", "--config", "report.yaml", cwd=tmp)
        assert q["rc"] == 0 and not q["data"]["jobs"][0]["sql"] and q["data"]["jobs"][0]["skipped"]
        p = run("probe", "--config", "report.yaml", cwd=tmp)
        assert any("uid" in x for x in p["data"]["adapter_todo"])
        # 補齊欄位 → 產出 4 份 SQL（hours 仍 TODO）
        ad["columns"].update({"uid": "UserID", "bet": "CoinBet", "spins": "CoinBetTimes", "market": "Country", "win": "CoinWin"})
        ad["triggers"] = {"Free Game": "FGTimes"}
        (tmp / "ad.yaml").write_text(yaml.safe_dump(ad, allow_unicode=True), encoding="utf-8")
        cfg["adapter"] = str(tmp / "ad.yaml")
        (tmp / "report.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
        q = run("query", "--config", "report.yaml", cwd=tmp)
        sql = q["data"]["jobs"][0]["sql"]
        assert set(sql) == {"game_user_daily", "slot_daily", "slot_users", "erosion"}, q
        g = (tmp / sql["game_user_daily"]).read_text(encoding="utf-8")
        assert "'Slot_DEMO-001'" in g and "SUM(CoinWin) AS win" in g and "trig_Free Game" in g and "BQDate BETWEEN '2026-10-01' AND '2026-10-07'" in g
        s = (tmp / sql["slot_daily"]).read_text(encoding="utf-8")
        assert "'非CN' AS view" in s and "NOT IN ('CN')" in s
        u = (tmp / sql["slot_users"]).read_text(encoding="utf-8")
        assert "QUALIFY ROW_NUMBER()" in u, "slot_users 要取期間內最後一筆快照（只取期末那天會讓分層欄位大量空白）"


def test_render_check_catches_mismatch():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        setup(tmp)
        run("all", "--config", "report.yaml", "--no-kb", cwd=tmp)
        rep = json.loads((tmp / "data" / "report.json").read_text(encoding="utf-8"))
        rep["views"]["全體"]["share"]["game"].pop()
        (tmp / "bad.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
        r = run("render", "--data", "bad.json", "--check", cwd=tmp)
        assert r["rc"] == 3 and any("share.game" in e for e in r["data"]["errors"])


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except AssertionError as e:
                fails += 1
                print("FAIL", name, str(e)[:300])
    sys.exit(1 if fails else 0)


def test_closeout_report():
    """closeout：十階段狀態、⑩ 紅燈 → P1／needs-work、⑨ 待拍板 → P2、人工區重產保留（合成資料）。"""
    with tempfile.TemporaryDirectory() as t:
        repo = pathlib.Path(t)
        d = repo / "data" / "slot" / "x"
        (d / "quicktest" / "qt-report").mkdir(parents=True)
        (d / "quicktest" / "qt-report" / "rtp-report.json").write_text(json.dumps(
            {"spins": 1000000, "games": {"Total": {"rtp": 0.96}, "MainGame": {"rtp": 0.6}, "Free": {"rtp": 0.36, "freq": 150.0, "multi": 54.0}}}), encoding="utf-8")
        (d / "docs" / "reports").mkdir(parents=True)
        (d / "docs" / "reports" / "2026-01-07-x-d7.json").write_text(json.dumps(
            {"meta": {"stage": 7, "data_through": "2026-01-07", "launch_date": "2026-01-01", "benchmark_label": "歷史新機同期（3 款）"},
             "verdict": {"headline": "D+7 初判", "lights": {"Q1": "r", "Q2": "g", "Q5": "y"}, "next": ["加曝光"]}, "views": {}}), encoding="utf-8")
        b = d / "review" / "x-decision"
        b.mkdir(parents=True)
        (b / "book.yaml").write_text("slug: x-decision\n", encoding="utf-8")
        (b / "02-feel.md").write_text("# R-1\n\n### 拍板欄\n\n| 項目 | 決議 | 拍板人 | 日期 |\n|---|---|---|---|\n| R-1 體感是否到位 | （待拍板：建議先玩） | | |\n", encoding="utf-8")
        (d / "review" / "index.html").write_text("<html></html>", encoding="utf-8")
        args = [sys.executable, "-X", "utf8", str(SCRIPTS / "gr_run.py"), "closeout", "--slug", "x", "--repo", str(repo), "--date", "2026-01-08", "--no-lint"]
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
        out = json.loads([l for l in r.stdout.splitlines() if l.startswith("{")][-1])
        assert r.returncode == 0 and out["success"], r.stdout + r.stderr
        assert out["data"]["verdict"] == "needs-work"
        assert any(f.startswith("P1 ⑩ D+7 未達標") for f in out["data"]["findings"]) and any(f.startswith("P2 ⑨ 送審拍板") for f in out["data"]["findings"])
        md_p = d / "docs" / "reports" / "2026-01-08-x-closeout.md"
        md = md_p.read_text(encoding="utf-8")
        for sec in ("## Verdict", "## 十階段完成度", "## ⑨ 送審拍板", "## ⑩ 上線成效", "## Findings", "## Evidence", "## Actions", "## 邊界聲明"):
            assert sec in md, sec
        assert "### E-1（支持 F-1）" in md and "findings: { p0: 0, p1: 1, p2: 1, p3: 0 }" in md
        md_p.write_text(md.replace("（人工填寫：案例敘事、技術亮點、結案後還要決定的事；重產時保留本區）", "人工：本機成功"), encoding="utf-8")
        subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
        assert "人工：本機成功" in md_p.read_text(encoding="utf-8")
        assert (d / "docs" / "reports" / "2026-01-08-x-closeout.html").is_file()


def test_query_parallel_export():
    """匯出並行：假 bq_export 每支睡 3 秒，13 支在 --workers 4 下應遠低於循序的 39 秒（Windows 起 Python 每支約 1 秒，睡久一點讓並行效果蓋過啟動成本）。"""
    import os
    import time
    import yaml
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        setup(tmp)
        fake = tmp / "fakedb"
        fake.mkdir()
        (fake / "bq_export.py").write_text(
            "import sys, time, pathlib\n"
            "a = sys.argv; out = pathlib.Path(a[a.index('--out') + 1])\n"
            "time.sleep(3); out.parent.mkdir(parents=True, exist_ok=True); out.write_text('x\\n1\\n')\n",
            encoding="utf-8")
        cfg = yaml.safe_load((tmp / "report.yaml").read_text(encoding="utf-8"))
        ad = yaml.safe_load((SCRIPTS.parent / "assets" / "adapters" / "bigquery-igs.yaml").read_text(encoding="utf-8"))
        (tmp / "ad.yaml").write_text(yaml.safe_dump(ad, allow_unicode=True), encoding="utf-8")
        cfg["adapter"] = str(tmp / "ad.yaml")
        cfg["benchmark_games"] = [{"name": f"B{i}", "ids": [str(i)], "launch_date": "2026-09-01"} for i in range(3)]
        (tmp / "report.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
        env = dict(os.environ, ARK_DB_QUERY_DIR=str(fake))
        t0 = time.time()
        q = run("query", "--config", "report.yaml", "--run", "--bench", "--workers", "4", cwd=tmp, env=env)
        el = time.time() - t0
        n = sum(len(j["export"]) for j in q["data"]["jobs"])
        assert q["rc"] == 0 and q["data"]["workers"] == 4 and n == 13, q
        assert all(v["rc"] == 0 for j in q["data"]["jobs"] for v in j["export"].values())
        assert el < n * 3 * 0.6, f"並行無效：{n} 支耗時 {el:.1f}s"
