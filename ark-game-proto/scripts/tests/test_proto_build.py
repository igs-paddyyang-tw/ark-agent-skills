"""ark-game-proto 建置測試：兩款 golden（彌勒佛 collect-mult、Tiger and Dragon coin-lock）md → config → html。

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
    assert len(cfg["gaps"]) == c["gaps"] and all({"id", "what", "spec", "assume", "check"} <= set(g) for g in cfg["gaps"])
    assert d["go_check"]["mismatch"] == 0 and d["go_check"]["match"] == c["match"] and d["go_check"]["gap"] == c["gap"]
    assert cfg["targets"]["summary"]["rtp_total"] > 90
    golden = json.loads((GOLDEN / slug / "game-config.json").read_text(encoding="utf-8"))
    for k in ("board", "paytable", "strips", "reelsets", "mg", "fg", "targets", "gaps"):
        assert cfg[k] == golden[k], f"{k} 與 golden 不一致（改了 adapter 請重產 golden）"


def test_html_single_file_and_parity_embed(tmp_path):
    d = build("milefo", tmp_path, "--go-parity", str(GOLDEN / "milefo" / "go-parity.seed42.json"))
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert d["bytes"] > 50_000 and "window.GAME_CONFIG=" in html and "SlotCore" in html and "SlotArt" in html
    assert '"go_parity"' in html and (tmp_path / "vendor" / "pixi.min.js").exists()
    assert "/*CORE*/" not in html and "__TITLE__" not in html


def test_old_md_without_strips_fails_clearly(tmp_path):
    md = tmp_path / "prob-spec.md"
    md.write_text((GOLDEN / "milefo" / "prob-spec.md").read_text(encoding="utf-8").split("## 輪帶 Strip（附錄）")[0], encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "proto_build.py"), "--md", str(md), "--out", str(tmp_path / "o")], capture_output=True, text=True, encoding="utf-8")
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
