"""ark-game-proto 建置測試：golden（彌勒佛 collect-mult、Tiger and Dragon coin-lock、Huff N' Puff huff-house）md → config → html。

需要 ark-game-prob 1.4+ 的 ps_mdview（ARK_GAME_PROB_SCRIPTS 或 .kiro/skills/ark-game-prob/scripts）。
node 相關：快速 smoke 預設跑；完整 core_test（約 1 分鐘 / 款）設 SLOTPROTO_SLOW=1 才跑。
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
GOLDEN = SCRIPTS.parent / "golden"
CASES = {
    "milefo": {"adapter": "milefo", "go": "go-config.a-standard.json", "model": "collect-mult", "gaps": 6, "match": 27, "gap": 1},
    "tiger-and-dragon": {"adapter": "tiger_dragon", "go": "go-odds_1.0.0.json", "model": "coin-lock", "gaps": 8, "match": 32, "gap": 0},
    "huffnpuff-open-house": {"adapter": "huffnpuff_open_house", "go": "go-odds_1.0.0.json", "model": "huff-house", "gaps": 5, "match": 40, "gap": 2},
}


def build(slug: str, out: pathlib.Path, *extra: str) -> dict:
    c = CASES[slug]
    args = [sys.executable, "-X", "utf8", str(SCRIPTS / "proto_build.py"), "--md", str(GOLDEN / slug / "prob-spec.md"),
            "--adapter", c["adapter"], "--out", str(out), "--go-config", str(GOLDEN / slug / c["go"]), *extra]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    assert r.stdout.strip(), r.stderr[-800:]
    env = json.loads(r.stdout.strip().splitlines()[-1])
    assert env["success"], env
    return env["data"]


@pytest.mark.parametrize("slug", sorted(CASES))
def test_build_config_and_go_check(slug, tmp_path):
    c = CASES[slug]
    d = build(slug, tmp_path, "--config-only")
    cfg = json.loads((tmp_path / "game-config.json").read_text(encoding="utf-8"))
    assert cfg["schema"] == "slot-proto-config/1" and cfg["fg"]["model"] == c["model"] and cfg["art"] == c["adapter"]
    assert cfg["art"] in _art_sets(), f"src/art.js 沒有美術套 {cfg['art']}"
    assert len(cfg["gaps"]) == c["gaps"] and all({"id", "what", "spec", "assume", "check"} <= set(g) for g in cfg["gaps"])
    assert d["go_check"]["mismatch"] == 0 and d["go_check"]["match"] == c["match"] and d["go_check"]["gap"] == c["gap"]
    assert cfg["targets"]["summary"]["rtp_total"] > 90
    golden = json.loads((GOLDEN / slug / "game-config.json").read_text(encoding="utf-8"))
    for k in ("board", "paytable", "strips", "reelsets", "mg", "fg", "targets", "gaps"):
        assert cfg[k] == golden[k], f"{k} 與 golden 不一致（改了 adapter 請重產 golden）"


def _art_sets() -> set[str]:
    import re
    m = re.search(r"const SETS = \{([^}]*)\}", (SCRIPTS / "src" / "art.js").read_text(encoding="utf-8"))
    return {x.split(":")[0].strip() for x in m.group(1).split(",")}


def test_html_single_file_and_parity_embed(tmp_path):
    d = build("milefo", tmp_path, "--go-parity", str(GOLDEN / "milefo" / "go-parity.seed42.json"))
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert d["bytes"] > 50_000 and "window.GAME_CONFIG=" in html and "SlotCore" in html and "SlotArt" in html
    assert '"go_parity"' in html and (tmp_path / "vendor" / "pixi.min.js").exists()
    assert "/*CORE*/" not in html and "__TITLE__" not in html


def test_old_md_without_strips_fails_clearly(tmp_path):
    md = tmp_path / "prob-spec.md"
    md.write_text((GOLDEN / "milefo" / "prob-spec.md").read_text(encoding="utf-8").split("## 輪帶 Strip（附錄）")[0], encoding="utf-8")
    r = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "proto_build.py"), "--md", str(md), "--out", str(tmp_path / "o")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode != 0 and "strip" in (r.stderr + r.stdout)


@pytest.mark.skipif(not shutil.which("node"), reason="需要 node")
@pytest.mark.parametrize("slug", sorted(CASES))
def test_node_smoke(slug):
    js = ("const S=require(process.argv[1]),C=S.compile(require(process.argv[2]));"
          "const a=S.spin(C,7,{present:true}),b=S.spin(C,7);if(a.totalWin!==b.totalWin)process.exit(1);"
          "const e=S.exact(C,{bonusN:3000});console.log(JSON.stringify({mg:e.rtp_main,trig:e.fg_rate}))")
    r = subprocess.run(["node", "-e", js, str(SCRIPTS / "src" / "slot-core.js"), str(GOLDEN / slug / "game-config.json")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    v = json.loads(r.stdout)
    T = json.loads((GOLDEN / slug / "game-config.json").read_text(encoding="utf-8"))["targets"]["summary"]
    assert abs(v["mg"] - T["rtp_main"]) < 0.5 and abs(v["trig"] / T["fg_rate"] - 1) < 0.02


@pytest.mark.skipif(not (shutil.which("node") and os.environ.get("SLOTPROTO_SLOW")), reason="SLOTPROTO_SLOW=1 才跑完整 core_test")
@pytest.mark.parametrize("slug", sorted(CASES))
def test_node_core_full(slug):
    r = subprocess.run(["node", str(HERE / "core_test.js"), str(GOLDEN / slug / "game-config.json")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-1500:]


@pytest.mark.skipif(not shutil.which("node"), reason="需要 node")
@pytest.mark.parametrize("slug", sorted(CASES))
def test_recorded_go_parity_zero_mismatch(slug):
    """golden 內記錄的逐局對照結果必須 0 差異（重跑：scripts/go_parity.py）。"""
    for p in (GOLDEN / slug).glob("go-parity.*.json"):
        x = json.loads(p.read_text(encoding="utf-8"))
        assert x["mismatch"] == 0 and x["spins"] >= 200_000, p.name


@pytest.mark.skipif(not shutil.which("node"), reason="需要 node")
@pytest.mark.parametrize("slug", sorted(CASES) + ["three-pigs"])
def test_ui_smoke(slug):
    """驗證台 UI 無頭冒煙：DOM / Pixi / Worker 替身跑完整 app.js（L1、缺口、Go 對照、L2、每種玩法各演一局含特色遊戲演出）。"""
    cfg = GOLDEN / slug / "game-config.json"
    if not cfg.exists():
        pytest.skip(f"沒有 golden/{slug}")
    r = subprocess.run(["node", str(HERE / "ui_smoke.js"), str(cfg)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-800:]


@pytest.mark.skipif(not shutil.which("node"), reason="需要 node")
def test_huff_parity_tool_on_recorded_trace(tmp_path):
    """huff-house：golden 內 Go 對照紀錄 0 差異且涵蓋五種玩法；tests/huff_parity.js 對小 trace 可重跑（tests/fixtures 有時）。"""
    recs = sorted((GOLDEN / "huffnpuff-open-house").glob("go-parity.*.json"))
    assert len(recs) >= 2
    for p in recs:
        x = json.loads(p.read_text(encoding="utf-8"))
        assert x["mismatch"] == 0 and x["model"] == "huff-house" and set(x["byType"]) == {"ST", "SK", "BR", "GD", "OH"}, p.name


# ───────── three-pigs（house-collect；Python 引擎，無 Go 對照，雙觸發線）─────────
# 註：three_pigs adapter 讀 data/slot/three-pigs 下的 configB.json 與 rtp-report.json（workspace-root 相對路徑），
# 故這組測試需從 workspace root 執行（CWD）。no-Go：不跑 --go-config / go-parity。
REPO_ROOT = SCRIPTS.parents[3]  # .kiro/skills/ark-game-proto/scripts → workspace root
TP_MD = REPO_ROOT / "data" / "slot" / "three-pigs" / "prob" / "prob-spec.md"
TP_CFGB = REPO_ROOT / "data" / "slot" / "three-pigs" / "quicktest" / "engine" / "configB.json"
_tp_ready = TP_MD.exists() and TP_CFGB.exists()


def _build_tp(out: pathlib.Path) -> dict:
    args = [sys.executable, "-X", "utf8", str(SCRIPTS / "proto_build.py"), "--md", str(TP_MD),
            "--adapter", "three_pigs", "--out", str(out), "--config-only"]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT))
    assert r.stdout.strip(), r.stderr[-800:]
    env = json.loads(r.stdout.strip().splitlines()[-1])
    assert env["success"], env
    return env["data"]


@pytest.mark.skipif(not _tp_ready, reason="需要 data/slot/three-pigs 的 prob-spec.md 與 configB.json")
def test_three_pigs_build(tmp_path):
    d = _build_tp(tmp_path)
    cfg = json.loads((tmp_path / "game-config.json").read_text(encoding="utf-8"))
    assert cfg["schema"] == "slot-proto-config/1"
    assert cfg["fg"]["model"] == "house-collect" and cfg["art"] == "three_pigs"
    assert cfg["fg"]["trigger"]["model"] == "house"  # 雙觸發線
    assert all({"id", "what", "spec", "assume", "check"} <= set(g) for g in cfg["gaps"])
    assert d["gaps"] >= 6
    # 房子三變體目標已從 rtp-report.json 併入
    assert "bonus" in cfg["targets"] and "mega_hat" in cfg["targets"]["bonus"]
    golden = json.loads((GOLDEN / "three-pigs" / "game-config.json").read_text(encoding="utf-8"))
    for k in ("board", "paytable", "strips", "reelsets", "fg", "gaps"):
        assert cfg[k] == golden[k], f"{k} 與 golden 不一致（改了 adapter 請重產 golden）"


@pytest.mark.skipif(not (shutil.which("node") and _tp_ready), reason="需要 node 與 three-pigs 資料")
def test_three_pigs_node_core():
    """house-collect L1 精算對 §2（含房子守恆、三變體、總 RTP ±0.88pp）。"""
    r = subprocess.run(["node", str(HERE / "core_test.js"), str(GOLDEN / "three-pigs" / "game-config.json")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO_ROOT))
    assert r.returncode == 0, r.stdout[-1500:]
